"""Native-resolution local shared refinement, initialized without any checkpoint."""
import math
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from optical.feature import WeakPSFDeconvBlock
from pathlib import Path

def reflect_pad(x,p):
    if not p:return x
    if min(x.shape[-2:])<=p:raise ValueError('Input smaller than reflect support')
    x=torch.cat([x[...,1:p+1].flip(-1),x,x[...,-p-1:-1].flip(-1)],-1)
    return torch.cat([x[...,1:p+1,:].flip(-2),x,x[...,-p-1:-1,:].flip(-2)],-2)

class LocalConv(nn.Conv2d):
    def __init__(self,cin,cout,d=1):super().__init__(cin,cout,3,padding=0,dilation=d);self.reflect_radius=d
    def forward(self,x):return super().forward(reflect_pad(x,self.reflect_radius))

class Block(nn.Module):
    def __init__(self,c,d):super().__init__();self.a=LocalConv(c,c,d);self.b=LocalConv(c,c,d)
    def forward(self,h):return h+.1*self.b(F.silu(self.a(h)))

class SharedBackbone(nn.Module):
    def __init__(self,channels,dilations,checkpoint_blocks):
        super().__init__();self.stem=LocalConv(7,channels);self.blocks=nn.ModuleList(Block(channels,d) for d in dilations);self.head=LocalConv(channels,1);self.checkpoint_blocks=checkpoint_blocks
        # Fresh initialization with a zero residual head permits exact identity.
        nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
    def forward(self,f,optical_module=None):
        h=self.stem(f)
        if optical_module is not None:h=optical_module(h)
        h=F.silu(h)
        for block in self.blocks:h=checkpoint(block,h,use_reentrant=False) if self.checkpoint_blocks and self.training and torch.is_grad_enabled() else block(h)
        return self.head(h) # logits; tanh is applied once in the update

class Model(nn.Module):
    def __init__(self,cfg):
        super().__init__();self.cfg=dict(cfg)
        if cfg['optical_mode']!='v42_select8':raise ValueError('Expected v42_select8')
        self.backbone=SharedBackbone(cfg['channels'],cfg['dilations'],cfg['checkpoint_blocks'])
        q=cfg['eta_initial']/cfg['eta_max'];self.step_logits=nn.Parameter(torch.full((cfg['iterations'],),math.log(q/(1-q))))
        self.loaded_pretrained_parameters=0;self.optical_mode='v42_select8';self.optical_files_loaded=1
        self.optics=WeakPSFDeconvBlock(in_ch=cfg['channels'],psf_path=str(Path(__file__).resolve().parent/cfg['psf_bank']),k=8,psf_indices=None,**cfg['weak_psf'])
        self.optical_enabled=True
        self.per_step_radius=2+2*sum(cfg['dilations'])
        self.dependency_radius=cfg['iterations']*self.per_step_radius+2 # 4*20+local mean radius2=82
        self.required_halo=math.ceil(self.dependency_radius/16)*16
    def features(self,x):
        p=reflect_pad(x,1)
        dx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5
        dy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5
        lap=p[...,1:-1,2:]+p[...,1:-1,:-2]+p[...,2:,1:-1]+p[...,:-2,1:-1]-4*x
        mean=F.avg_pool2d(reflect_pad(x,2),5,stride=1)
        return dx,dy,lap,mean
    def forward(self,x,trace=False):
        if x.ndim!=4 or x.shape[1]!=1 or x.dtype!=torch.float32:raise ValueError('Expected FP32 N1HW')
        if min(x.shape[-2:])<5:raise ValueError('Spatial dimensions must be >=5')
        if not torch.isfinite(x).all() or x.min()<0 or x.max()>1:raise ValueError('Expected finite normalized observation')
        fixed=self.features(x);r=torch.zeros_like(x);z=x;states=[]
        for i in range(self.cfg['iterations']):
            f=torch.cat([z,x,z-x,*fixed],dim=1)
            delta=torch.tanh(self.backbone(f,self.optics if self.optical_enabled else None))
            eta=self.cfg['eta_max']*torch.sigmoid(self.step_logits[i])
            r=(r+eta*delta).clamp(-self.cfg['r_max'],self.cfg['r_max'])
            z=(x+r).clamp(0,1)
            if trace:states.append(dict(residual=r.detach().clone(),output=z.detach().clone()))
        return (z,states) if trace else z
