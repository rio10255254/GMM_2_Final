"""Integer-shift-stable native-grid recurrent reconstruction."""
from __future__ import annotations
import math
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
from optical.fullres_psf import FullResPSF

def reflect_pad(x,p):
    if p==0:return x
    if min(x.shape[-2:])<=p:raise ValueError('Input smaller than reflect support')
    x=torch.cat((x[...,1:p+1].flip(-1),x,x[...,-p-1:-1].flip(-1)),-1)
    return torch.cat((x[...,1:p+1,:].flip(-2),x,x[...,-p-1:-1,:].flip(-2)),-2)
class LocalConv(nn.Conv2d):
    def __init__(self,cin,cout,d=1):super().__init__(cin,cout,3,padding=0,dilation=d);self.radius=d
    def forward(self,x):return super().forward(reflect_pad(x,self.radius))
class PixelChannelNorm(nn.Module):
    def __init__(self,c,eps=1e-4):super().__init__();self.scale=nn.Parameter(torch.ones(1,c,1,1));self.bias=nn.Parameter(torch.zeros(1,c,1,1));self.eps=eps
    def forward(self,x):q=x-x.mean(1,keepdim=True);return q*torch.rsqrt(q.square().mean(1,keepdim=True)+self.eps)*self.scale+self.bias
class Block(nn.Module):
    def __init__(self,c,d):super().__init__();self.a=LocalConv(c,c,d);self.na=PixelChannelNorm(c);self.b=LocalConv(c,c,d);self.nb=PixelChannelNorm(c)
    def forward(self,x):return x+.1*self.nb(self.b(F.silu(self.na(self.a(x)))))
class NativeRefiner(nn.Module):
    def __init__(self,cfg):
        super().__init__();c=cfg['channels'];self.checkpoint_blocks=cfg['checkpoint_blocks'];self.gain=cfg['output_logit_gain'];self.stem=LocalConv(9,c);self.norm=PixelChannelNorm(c);self.blocks=nn.ModuleList(Block(c,d) for d in cfg['dilations']);self.head=LocalConv(c,1);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias);self.dependency_radius=2+2*sum(cfg['dilations'])
    def forward(self,f):
        h=F.silu(self.norm(self.stem(f)))
        for block in self.blocks:h=checkpoint(block,h,use_reentrant=False) if self.checkpoint_blocks and self.training and torch.is_grad_enabled() else block(h)
        return self.gain*self.head(h)
class Model(nn.Module):
    def __init__(self,cfg,root:Path|None=None):
        super().__init__();self.cfg=dict(cfg);root=Path(root) if root else Path(__file__).resolve().parent
        if cfg['iterations']!=4 or cfg['psf_mode']!='known_or_mean_native_pixel_consistency':raise ValueError('Unexpected R148 model contract')
        self.refiner=NativeRefiner(cfg);self.optics=FullResPSF(root/cfg['psf_bank']);q=cfg['eta_initial']/cfg['eta_max'];self.step_logits=nn.Parameter(torch.full((4,),math.log(q/(1-q))));q=cfg['optical_step_initial']/cfg['optical_step_max'];self.optical_step_logits=nn.Parameter(torch.full((4,),math.log(q/(1-q))))
    def raw_features(self,x):
        p=reflect_pad(x,1);dx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;dy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5;lap=p[...,1:-1,2:]+p[...,1:-1,:-2]+p[...,2:,1:-1]+p[...,:-2,1:-1]-4*x;mean=F.avg_pool2d(reflect_pad(x,2),5,stride=1);return dx,dy,lap,mean
    def _step(self,z,x,r,fixed,i,indices,tiled=False):
        obs,bp=self.optics.consistency(z,x,indices);features=torch.cat((z,x,z-x,self.cfg['optical_feature_gain']*obs,self.cfg['optical_feature_gain']*bp,*fixed),1)
        logits=self._refine_tiled(features) if tiled else self.refiner(features);eta=self.cfg['eta_max']*torch.sigmoid(self.step_logits[i]);alpha=self.cfg['optical_step_max']*torch.sigmoid(self.optical_step_logits[i]);r=(r+eta*torch.tanh(logits)+alpha*bp).clamp(-self.cfg['r_max'],self.cfg['r_max']);return (x+r).clamp(0,1),r,obs,bp
    def forward(self,x,psf_indices=None,return_states=False):
        if x.ndim!=4 or x.shape[1]!=1 or x.dtype!=torch.float32 or min(x.shape[-2:])<202:raise ValueError('Expected FP32 N1HW native image')
        if not torch.isfinite(x).all() or x.min()<0 or x.max()>1:raise ValueError('Invalid normalized image')
        fixed=self.raw_features(x);z=x;r=torch.zeros_like(x);states=[]
        for i in range(4):
            z,r,obs,bp=self._step(z,x,r,fixed,i,psf_indices,False)
            if return_states:states.append(z)
        return (z,states) if return_states else z
    def _refine_tiled(self,features):
        core=self.cfg['inference_core'];halo=self.cfg['inference_halo']
        if halo<self.refiner.dependency_radius:raise ValueError('Inference halo too small')
        n,c,h,w=features.shape
        if n!=1:raise ValueError('Tiled inference requires batch one')
        out=torch.empty((1,1,h,w),device=features.device,dtype=features.dtype)
        for y in range(0,h,core):
            for x in range(0,w,core):
                y1=min(h,y+core);x1=min(w,x+core);a=max(0,y-halo);b=min(h,y1+halo);l=max(0,x-halo);rr=min(w,x1+halo);value=self.refiner(features[...,a:b,l:rr]);out[...,y:y1,x:x1]=value[...,y-a:y1-a,x-l:x1-l]
        return out
    def forward_tiled(self,x,return_states=False):
        if x.shape[0]!=1:raise ValueError('Full tiled inference is one image at a time')
        fixed=self.raw_features(x);z=x;r=torch.zeros_like(x);states=[]
        for i in range(4):
            z,r,_,_=self._step(z,x,r,fixed,i,None,True)
            if return_states:states.append(z)
        return (z,states) if return_states else z
