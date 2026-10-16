"""Fixed true-simulator convolution for supervision, never part of model input."""
import torch
from torch import nn
from torch.nn import functional as F

class Observation(nn.Module):
    def __init__(self,kernel,factor=4):
        super().__init__();k=torch.as_tensor(kernel)
        if k.ndim!=2 or k.shape[0]!=k.shape[1] or k.shape[0]%2!=1 or not torch.isfinite(k).all() or (k<0).any():raise ValueError('Invalid physical PSF')
        if abs(float(k.sum())-1)>2e-6:raise ValueError('PSF mass must already be1')
        self.register_buffer('kernel',k.clone());self.factor=factor
    @property
    def radius_native(self):return (self.kernel.shape[0]-1)//2/self.factor
    def forward(self,x):
        if x.ndim!=4 or x.shape[1]!=1 or x.dtype!=self.kernel.dtype or x.device!=self.kernel.device:raise ValueError('Operator/image contract mismatch')
        if x.shape[-1]%self.factor or x.shape[-2]%self.factor:raise ValueError('Unaligned native integration')
        if self.kernel.numel()==1:return F.avg_pool2d(x,self.factor)
        h,w=x.shape[-2:];k=self.kernel.shape[0];shape=(h+k-1,w+k-1);r=k//2
        spectrum=torch.fft.rfft2(self.kernel,s=shape)
        full=torch.fft.irfft2(torch.fft.rfft2(x,s=shape)*spectrum,s=shape)
        centered=full[...,r:r+h,r:r+w]
        return F.avg_pool2d(centered,self.factor)
