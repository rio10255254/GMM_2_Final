"""Differentiable per-image top-K choice from a complete measured PSF bank.

The forward pass mixes exactly K kernels. A straight-through softmax supplies
gradients to scores for all N candidates, including candidates outside top K.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


class AdaptivePSFCue(nn.Module):
    def __init__(self, in_ch: int, psf_path: str | Path, expected_count: int,
                 top_k: int, prior_indices: list[int] | None = None,
                 regularization: float = 30.0, beta_init: float = 0.02,
                 temperature: float = 1.0, lowfreq_ratio: float = 0.25):
        super().__init__()
        path=Path(psf_path)
        if not path.is_file():
            raise FileNotFoundError(f"Measured PSF bank missing: {path}. Do not use a synthetic test bank for inference.")
        with np.load(path,allow_pickle=False) as z:
            if "all_kernels" not in z.files:
                raise ValueError("PSF bank needs all_kernels")
            kernels=z["all_kernels"]
        expected=(int(expected_count),101,101)
        if kernels.shape!=expected or kernels.dtype.kind not in "fiu":
            raise ValueError(f"PSF bank must contain {expected} real kernels")
        kernels=np.asarray(kernels,dtype=np.float32)
        if not np.isfinite(kernels).all() or (kernels<0).any():
            raise ValueError("PSF bank has nonfinite or negative values")
        sums=kernels.sum((1,2),keepdims=True)
        if (sums<=0).any():raise ValueError("PSF bank has empty kernels")
        kernels=kernels/sums
        n=int(expected_count);k=int(top_k)
        if n<2 or not 1<=k<n:raise ValueError("Expected 1 <= top_k < PSF count")
        if regularization<=0 or beta_init<0 or not 0<temperature or not 0<=lowfreq_ratio<=1:
            raise ValueError("Invalid optical settings")
        prior_indices=[] if prior_indices is None else [int(i) for i in prior_indices]
        if len(set(prior_indices))!=len(prior_indices) or len(prior_indices)>k or any(i<0 or i>=n for i in prior_indices):
            raise ValueError("Invalid prior indices")
        self.expected_count=n;self.top_k=k
        self.register_buffer("PSFs",torch.from_numpy(kernels))
        self.register_buffer("reg",torch.tensor(float(regularization)))
        self.register_buffer("temperature",torch.tensor(float(temperature)))
        self.register_buffer("lowfreq_ratio",torch.tensor(float(lowfreq_ratio)))
        self.register_buffer("beta_scale",torch.tensor(0.0))
        self.beta=nn.Parameter(torch.tensor(float(beta_init)))
        self.beta_min=0.0;self.beta_max=0.1
        hidden=max(16,in_ch//2)
        # Extract blur/edge cues before global pooling; pooling raw features
        # first would erase most spatial information needed for PSF choice.
        self.selector=nn.Sequential(nn.Conv2d(in_ch,in_ch,3,padding=1,groups=in_ch),
                                    nn.SiLU(),nn.Conv2d(in_ch,hidden,1),nn.SiLU(),
                                    nn.Conv2d(hidden,hidden,3,padding=1,groups=hidden),
                                    nn.SiLU(),nn.AdaptiveAvgPool2d(1),
                                    nn.Conv2d(hidden,n,1))
        # A nonzero last layer leaves a gradient path to the first layer.
        nn.init.normal_(self.selector[-1].weight,mean=0.0,std=0.01)
        nn.init.zeros_(self.selector[-1].bias)
        prior=torch.zeros(n)
        for i in prior_indices:prior[i]=0.10
        self.register_buffer("prior_logits",prior)
        self.last_logits=None
        self.last_soft_weights=None
        self.last_sparse_weights=None
        self.last_indices=None
        self.last_beta=0.0

    def set_beta_scale(self,value:float):
        if not 0.0<=float(value)<=1.0:raise ValueError("Optical scale outside [0,1]")
        self.beta_scale.fill_(float(value))

    def select(self,x:torch.Tensor):
        if x.ndim!=4 or x.shape[1]!=self.selector[0].in_channels:
            raise ValueError("Unexpected decoder features")
        logits=self.selector(x).flatten(1)+self.prior_logits
        soft=torch.softmax(logits/self.temperature.clamp_min(1e-6),dim=1)
        indices=torch.topk(logits,self.top_k,dim=1,sorted=True).indices
        mask=torch.zeros_like(soft).scatter_(1,indices,1.0)
        sparse=soft*mask
        sparse=sparse/sparse.sum(dim=1,keepdim=True).clamp_min(1e-8)
        # Exactly K positive weights in the forward pass; dense surrogate
        # gradient through softmax makes every candidate trainable.
        weights=sparse.detach()+soft-soft.detach()
        self.last_logits=logits
        self.last_soft_weights=soft.detach()
        self.last_sparse_weights=sparse.detach()
        self.last_indices=indices.detach()
        return weights,indices

    def _lowfreq_mask(self,h:int,w:int,device):
        ratio=float(self.lowfreq_ratio)
        fy=torch.fft.fftfreq(h,device=device).unsqueeze(1)
        fx=torch.fft.rfftfreq(w,device=device).unsqueeze(0)
        radius=torch.sqrt(fy.square()+fx.square())/0.5
        return (radius<=ratio).float()[None,None]

    def forward(self,x:torch.Tensor):
        b,c,h,w=x.shape
        if min(h,w)<101:raise ValueError("Half-resolution feature map too small for 101-pixel PSF")
        weights,_=self.select(x)
        kernels=torch.einsum("bn,nhw->bhw",weights,self.PSFs.to(x.device,dtype=torch.float32))
        ph,pw=kernels.shape[-2:]
        padw=w-pw;padh=h-ph
        pad=(padw//2,padw-padw//2,padh//2,padh-padh//2)
        psf_f=torch.fft.rfft2(F.pad(kernels[:,None],pad))
        img_f=torch.fft.rfft2(x.float())
        reg=self.reg.clamp_min(1e-6)
        inverse=psf_f.conj()/(psf_f.abs().square()+reg+1e-6)
        mask=self._lowfreq_mask(h,w,x.device)
        filt=inverse*mask+(1.0-mask)
        restored=torch.fft.irfft2(img_f*filt,s=(h,w)).clamp(-100,100)
        beta=self.beta.clamp(self.beta_min,self.beta_max)*self.beta_scale.clamp(0,1)
        self.last_beta=float(beta.detach())
        return (x.float()+beta*(restored-x.float())).to(x.dtype)

    def selector_loss(self,psf_index:torch.Tensor):
        if self.last_logits is None:raise RuntimeError("Run forward before selector loss")
        if psf_index.ndim!=1 or len(psf_index)!=len(self.last_logits):
            raise ValueError("PSF labels must be one index per image")
        valid=psf_index>=0
        if not bool(valid.any()):
            return self.last_logits.sum()*0
        return F.cross_entropy(self.last_logits[valid],psf_index[valid].long())
