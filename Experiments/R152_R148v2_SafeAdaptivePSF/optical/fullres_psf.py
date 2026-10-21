"""Measured PSF bank on native pixels with known-index training and mean inference."""
from __future__ import annotations
from pathlib import Path
import numpy as np,torch
from torch import nn
from torch.nn import functional as F

def reflect_pad(x,width):
    if min(x.shape[-2:])<=width:raise ValueError('Image smaller than PSF support')
    x=torch.cat((x[...,1:width+1].flip(-1),x,x[...,-width-1:-1].flip(-1)),-1)
    return torch.cat((x[...,1:width+1,:].flip(-2),x,x[...,-width-1:-1,:].flip(-2)),-2)

class FullResPSF(nn.Module):
    def __init__(self,path:str|Path):
        super().__init__()
        with np.load(path,allow_pickle=False) as z:bank=z['all_kernels'].astype(np.float64)
        if bank.shape!=(25,101,101) or not np.isfinite(bank).all() or (bank<0).any():raise ValueError('Expected 25 nonnegative 101x101 PSFs')
        bank/=bank.sum((1,2),keepdims=True);mean=bank.mean(0);mean/=mean.sum()
        if np.max(np.abs(mean-mean[::-1,::-1]))>1e-7:raise ValueError('Mean PSF is not centrosymmetric')
        self.register_buffer('bank',torch.from_numpy(bank.astype(np.float32))[:,None])
        self.register_buffer('mean_kernel',torch.from_numpy(mean.astype(np.float32))[None,None])
        self._cache={}
    def _apply(self,fn):self._cache.clear();return super()._apply(fn)
    def _transfer(self,h,w,index,device):
        key=(h,w,int(index),str(device));old=self._cache.get(key)
        if old is not None:return old
        kernel=self.mean_kernel if index<0 else self.bank[index:index+1]
        y=h-101;x=w-101;top,left=y//2,x//2
        with torch.inference_mode(False),torch.no_grad():
            placed=F.pad(kernel.to(device),(left,x-left,top,y-top));origin=torch.roll(placed,(-(top+50),-(left+50)),(-2,-1));value=torch.fft.rfft2(origin)
        self._cache[key]=value;return value
    def blur(self,image,indices=None):
        if image.ndim!=4 or image.shape[1]!=1 or image.dtype!=torch.float32:raise ValueError('Expected FP32 N1HW')
        n=image.shape[0]
        if indices is None:indices=torch.full((n,),-1,dtype=torch.long,device=image.device)
        if indices.shape!=(n,) or ((indices<-2)|(indices>=25)).any():raise ValueError('Invalid PSF indices')
        padded=reflect_pad(image,50);h,w=padded.shape[-2:];spectra=torch.fft.rfft2(padded);transfer=torch.cat([torch.ones_like(spectra[0:1]) if int(i)==-2 else self._transfer(h,w,int(i),image.device) for i in indices.tolist()],0)
        result=torch.fft.irfft2(spectra*transfer,s=(h,w))
        return result[...,50:-50,50:-50]
    def consistency(self,estimate,observation,indices=None):
        residual=observation-self.blur(estimate,indices)
        return residual,self.blur(residual,indices)
