"""Native optical conditioning followed by shared reconstruction and genuine AA decoding."""
from dataclasses import dataclass
import math
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint


def reflect_pad(x,pad):
    if not pad:return x
    x=torch.cat([x[...,1:pad+1].flip(-1),x,x[...,-pad-1:-1].flip(-1)],-1)
    return torch.cat([x[...,1:pad+1,:].flip(-2),x,x[...,-pad-1:-1,:].flip(-2)],-2)

def replicate_one(x):
    x=torch.cat([x[...,:1],x,x[...,-1:]],-1)
    return torch.cat([x[...,:1,:],x,x[...,-1:,:]],-2)

class Bilinear2x(torch.autograd.Function):
    @staticmethod
    def forward(ctx,x):return F.interpolate(x,scale_factor=2,mode='bilinear',align_corners=False)
    @staticmethod
    def backward(ctx,g):
        even,odd=g[...,0::2,:],g[...,1::2,:]
        y=.75*(even+odd)
        y[...,1:,:]+=.25*odd[...,:-1,:]
        y[...,:-1,:]+=.25*even[...,1:,:]
        y[...,:1,:]+=.25*even[...,:1,:]
        y[...,-1:,:]+=.25*odd[...,-1:,:]
        even,odd=y[...,0::2],y[...,1::2]
        x=.75*(even+odd)
        x[...,1:]+=.25*odd[...,:-1]
        x[...,:-1]+=.25*even[...,1:]
        x[...,:1]+=.25*even[...,:1]
        x[...,-1:]+=.25*odd[...,-1:]
        return x

class MeasuredOptics(nn.Module):
    def __init__(self,mean_psf,candidates):
        super().__init__();self.register_buffer('mean_psf',mean_psf/mean_psf.sum());self.register_buffer('candidates',candidates/candidates.sum((-2,-1),keepdim=True))
        self.gating=nn.Sequential(nn.Linear(4,8),nn.SiLU(),nn.Linear(8,len(candidates)))
        self.alpha=nn.Parameter(torch.tensor(.10));self.beta=nn.Parameter(torch.tensor(.02));self.reg=.0565;self.last_weights=None
    def otf(self,kernel,h,w):
        # Preserve the measured kernel; explicitly choose its intensity centroid as optical origin.
        kh,kw=kernel.shape;yy,xx=torch.meshgrid(torch.arange(kh,device=kernel.device),torch.arange(kw,device=kernel.device),indexing='ij')
        cy=(kernel*yy).sum()/kernel.sum();cx=(kernel*xx).sum()/kernel.sum()
        padded=F.pad(kernel,(0,w-kw,0,h-kh));H=torch.fft.rfft2(padded)
        fy=torch.fft.fftfreq(h,device=kernel.device)[:,None];fx=torch.fft.rfftfreq(w,device=kernel.device)[None,:]
        return H*torch.exp(2j*math.pi*(fy*cy+fx*cx))
    def forward(self,x,enabled=True,trace=False):
        if not enabled:return x,dict(enabled=False)
        pad=max(self.mean_psf.shape)//2
        if min(x.shape[-2:])<=pad:raise ValueError('Full image needs more optical context')
        xp=reflect_pad(x,pad);h,w=xp.shape[-2:];X=torch.fft.rfft2(xp)
        def inv(k):
            H=self.otf(k,h,w);G=(1+self.reg)*H.conj()/(H.abs().square()+self.reg)
            return torch.fft.irfft2(X*G,s=(h,w))[...,pad:-pad,pad:-pad]
        mean=inv(self.mean_psf);dx=x[...,1:]-x[...,:-1];dy=x[...,1:,:]-x[...,:-1,:]
        stats=torch.stack([x.mean((1,2,3)),x.std((1,2,3),unbiased=False),dx.abs().mean((1,2,3)),dy.abs().mean((1,2,3))],1)
        weights=torch.softmax(self.gating(stats)/2.5,1);mix=sum(weights[:,i,None,None,None]*inv(k) for i,k in enumerate(self.candidates))
        alpha=self.alpha.clamp(.05,.35);beta=self.beta.clamp(.005,.10)
        result=(x+alpha*(mean-x)+beta*(mix-x)).clamp(0,1)
        self.last_weights=weights.detach()
        info=dict(enabled=True,weights=weights,mean_residual=mean-x,adaptive_residual=mix-x,alpha=alpha,beta=beta) if trace else dict(enabled=True)
        return result,info

class Block(nn.Module):
    def __init__(self,c,d):
        super().__init__();self.a=nn.Conv2d(c,c,3,padding=d,dilation=d);self.b=nn.Conv2d(c,c,3,padding=d,dilation=d)
    def forward(self,x):return x+.1*self.b(F.silu(self.a(x)))

class SharedDecoder(nn.Module):
    def __init__(self,channels=64,aa=True):
        super().__init__();self.aa=aa;self.stem=nn.Conv2d(7,channels,3,padding=1);self.blocks=nn.ModuleList(Block(channels,d) for d in (1,2,4,2));self.head=nn.Conv2d(channels,1,3,padding=1)
        kernel=torch.tensor([[1,2,1],[2,4,2],[1,2,1]],dtype=torch.float32)/16
        self.register_buffer('blur_kernel',kernel[None,None].repeat(channels,1,1,1))
    def forward(self,x):
        h=F.silu(self.stem(x))
        for block in self.blocks:h=checkpoint(block,h,use_reentrant=False) if self.training and torch.is_grad_enabled() else block(h)
        h=Bilinear2x.apply(h)
        if self.aa:h=F.conv2d(reflect_pad(h,1),self.blur_kernel,groups=h.shape[1])
        return torch.tanh(self.head(h))

@dataclass
class Details:
    output:torch.Tensor
    latent:torch.Tensor
    optical:dict
    neural:torch.Tensor
    quality:torch.Tensor

class Hybrid(nn.Module):
    def __init__(self,mean_psf,candidates,optical=True,aa=True):
        super().__init__();self.optical_enabled=optical;self.optics=MeasuredOptics(mean_psf,candidates);self.prior=SharedDecoder(64,aa);self.step_logits=nn.Parameter(torch.zeros(4));self.required_halo=80
        a=torch.arange(-6,7,dtype=torch.float32);k=torch.exp(-.5*(a/2).square());k/=k.sum();self.register_buffer('anchor_kernel',k)
    def initialize_from_r128(self,state):
        # Common conversion in all four arms; original phase-dependent head cannot be exactly retained.
        own=self.state_dict()
        for key,value in state.items():
            if key in own and own[key].shape==value.shape:own[key]=value.detach().clone()
        own['prior.head.weight']=state['prior.head.weight'].mean(0,keepdim=True);own['prior.head.bias']=state['prior.head.bias'].mean().reshape(1)
        self.load_state_dict(own)
    def backbone(self,raw):
        lift=lambda x,f:x.repeat_interleave(f,-2).repeat_interleave(f,-1)
        original=lift(raw,4);o2=lift(raw,2);state=original;p=replicate_one(raw)
        dx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;dy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5
        lap=p[...,1:-1,2:]+p[...,1:-1,:-2]+p[...,2:,1:-1]+p[...,:-2,1:-1]-4*raw
        mean=F.avg_pool2d(raw,5,1,2,count_include_pad=False);fixed=[lift(v,2) for v in [dx,dy,lap,mean]]
        for i in range(4):
            native=raw+F.avg_pool2d(state-original,4)
            features=torch.cat([F.avg_pool2d(state,2),o2,lift(raw-native,2),*fixed],1)
            state=(state+.25*torch.sigmoid(self.step_logits[i])*self.prior(features)).clamp(0,1)
        return (raw+F.avg_pool2d(state-original,4)).clamp(0,1),state
    def anchor(self,raw,neural):
        k=self.anchor_kernel
        low=F.conv2d(torch.cat([neural[...,1:7].flip(-1),neural,neural[...,-7:-1].flip(-1)],-1),k[None,None,None,:])
        low=F.conv2d(torch.cat([low[...,1:7,:].flip(-2),low,low[...,-7:-1,:].flip(-2)],-2),k[None,None,:,None])
        # Image statistics set a bounded correction scale, not a calibrated reliability probability.
        dx=raw[...,1:]-raw[...,:-1];dy=raw[...,1:,:]-raw[...,:-1,:]
        signal=(dx.abs().mean((1,2,3))+dy.abs().mean((1,2,3)))*.5
        smooth=F.avg_pool2d(raw,5,1,2,count_include_pad=False);noise=(raw-smooth).abs().mean((1,2,3));q=signal/(signal+3*noise+1e-8)
        strength=.78+.30*q;result=raw+.35*strength[:,None,None,None]*(neural-low)
        result=result-result.mean((2,3),keepdim=True)+raw.mean((2,3),keepdim=True)
        return result.clamp(0,1),q
    def forward_details(self,raw,trace=False):
        conditioned,info=self.optics(raw,self.optical_enabled,trace);neural,latent=self.backbone(conditioned);out,q=self.anchor(raw,neural)
        return Details(out,latent,info,neural,q)
    def forward(self,raw):return self.forward_details(raw).output
