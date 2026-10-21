"""Four shared image-only updates; no privileged acquisition or truth inputs."""
from dataclasses import dataclass,asdict
import math
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint

@dataclass(frozen=True)
class Config:
    channels:int=64
    dilations:tuple=(1,2,4,2)
    iterations:int=4
    checkpoint_blocks:bool=True
    maximum_step:float=.25
    initial_fraction:float=.4
    def __post_init__(self):
        object.__setattr__(self,'dilations',tuple(self.dilations))
        if self.channels<1 or self.iterations<1 or any(int(d)!=d or d<1 for d in self.dilations):raise ValueError('Invalid dimensions')
        if not 0<self.initial_fraction<1 or not 0<self.maximum_step<=1:raise ValueError('Invalid update bound')

class Block(nn.Module):
    def __init__(self,c,d):
        super().__init__();self.a=nn.Conv2d(c,c,3,padding=d,dilation=d);self.b=nn.Conv2d(c,c,3,padding=d,dilation=d)
    def forward(self,x):return x+.1*self.b(F.silu(self.a(x)))

class Prior(nn.Module):
    def __init__(self,c):
        super().__init__();self.stem=nn.Conv2d(7,c.channels,3,padding=1);self.blocks=nn.ModuleList(Block(c.channels,d) for d in c.dilations);self.head=nn.Conv2d(c.channels,4,3,padding=1);self.checkpoint_blocks=c.checkpoint_blocks
        nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
    def forward(self,x):
        h=F.silu(self.stem(x))
        for block in self.blocks:h=checkpoint(block,h,use_reentrant=False) if self.checkpoint_blocks and self.training and torch.is_grad_enabled() else block(h)
        return F.pixel_shuffle(torch.tanh(self.head(h)),2)

@dataclass
class Details:
    output:torch.Tensor
    latent:torch.Tensor
    traces:list
    metadata:dict

class Model(nn.Module):
    def __init__(self,config=None):
        super().__init__();self.config=config if isinstance(config,Config) else Config(**(config or {}));self.prior=Prior(self.config);p=self.config.initial_fraction;self.step_logits=nn.Parameter(torch.full((self.config.iterations,),math.log(p/(1-p))))
    def config_dict(self):return asdict(self.config)
    @property
    def required_halo(self):
        per_step=math.ceil((2*(2+2*sum(self.config.dilations))+3)/4)+1
        return math.ceil((self.config.iterations*per_step+2)/16)*16
    @staticmethod
    def _validate_input(raw):
        if raw.ndim!=4 or raw.shape[1]!=1 or min(raw.shape)<1 or not raw.is_floating_point():raise ValueError('Expected normalizedN1HW')
        if not torch.isfinite(raw).all() or (raw<0).any() or (raw>1).any():raise ValueError('Invalid image intensity')
    def forward_details(self,raw,trace=False):
        self._validate_input(raw);lift=lambda a,f:a.repeat_interleave(f,-2).repeat_interleave(f,-1)
        original=lift(raw,4);original2=lift(raw,2);state=original
        padded=F.pad(raw,(1,1,1,1),mode='replicate')
        dx=(padded[...,1:-1,2:]-padded[...,1:-1,:-2])*.5
        dy=(padded[...,2:,1:-1]-padded[...,:-2,1:-1])*.5
        lap=padded[...,1:-1,2:]+padded[...,1:-1,:-2]+padded[...,2:,1:-1]+padded[...,:-2,1:-1]-4*raw
        mean=F.avg_pool2d(raw,5,stride=1,padding=2,count_include_pad=False)
        fixed=[lift(v,2) for v in [dx,dy,lap,mean]];traces=[]
        for i in range(self.config.iterations):
            native=raw+F.avg_pool2d(state-original,4)
            features=torch.cat([F.avg_pool2d(state,2),original2,lift(raw-native,2),*fixed],1)
            correction=self.config.maximum_step*torch.sigmoid(self.step_logits[i])*self.prior(features)
            proposal=state+correction;next_state=proposal.clamp(0,1)
            if trace:traces.append(dict(state_before=state,learned_correction=correction,projection_correction=next_state-proposal,state_after=next_state,native_after=raw+F.avg_pool2d(next_state-original,4)))
            state=next_state
        unconstrained=raw+F.avg_pool2d(state-original,4);output=unconstrained.clamp(0,1)
        return Details(output,state,traces,dict(model_kind='source_only_recurrent4x',inputs=['observed_image_only'],required_halo=self.required_halo,geometry_output=False,calibrated_confidence_output=False,real_physical_accuracy_qualified=False,final_roundoff_projection_max=float((output-unconstrained).detach().abs().max()) if trace else None))
    def forward(self,raw):return self.forward_details(raw).output

def boundary_guard(raw,reconstruction,halo=64,transition=16):
    """At global FOV only, retain Raw where full neural context is unavailable."""
    h,w=raw.shape[-2:];yy=torch.arange(h,device=raw.device);xx=torch.arange(w,device=raw.device)
    distance=torch.minimum(torch.minimum(yy,h-1-yy)[:,None],torch.minimum(xx,w-1-xx)[None,:]).to(raw.dtype)
    weight=((distance-halo)/transition).clamp(0,1)
    return raw+(reconstruction-raw)*weight,weight
