"""Fixed explicitly supplied PSF bank cue; no neural checkpoint import or spatial mapping inference."""
import math
from pathlib import Path
import numpy as np,torch
from torch import nn
from torch.nn import functional as F
class OpticalCue(nn.Module):
 def __init__(self,path,reg,count=100):
  super().__init__()
  if not Path(path).is_file():raise FileNotFoundError('Please supply a real 100-PSF NPZ bank first: '+str(path))
  with np.load(path,allow_pickle=False) as z:
   if 'all_kernels' not in z.files:raise ValueError('NPZ must contain all_kernels')
   raw=z['all_kernels']
   if raw.dtype.kind not in 'fiu':raise ValueError('PSFs must be real numeric arrays')
   k=raw.astype('float64')
  if k.shape!=(count,101,101) or not np.isfinite(k).all() or k.min()<0 or (k.sum((1,2))<=0).any():raise ValueError(f'Expected exactly {count} finite nonnegative 101x101 PSFs with positive sums')
  k=k/k.sum((1,2),keepdims=True);mean=k.mean(0);mean=mean/mean.sum()
  self.register_buffer('mean_psf',torch.tensor(mean,dtype=torch.float32));self.reg=float(reg);self.calls=0;self._cache={}
 def forward(self,x):
  from model_r137_psf import reflect_pad
  self.calls+=1;p=50
  if min(x.shape[-2:])<=p:raise ValueError('PSF requires image dimensions >50')
  xp=reflect_pad(x,p);h,w=xp.shape[-2:];key=(h,w,str(x.device))
  if key not in self._cache:
   k=self.mean_psf;yy,xx=torch.meshgrid(torch.arange(101,device=x.device),torch.arange(101,device=x.device),indexing='ij');cy=(k*yy).sum()/k.sum();cx=(k*xx).sum()/k.sum()
   H=torch.fft.rfft2(F.pad(k,(0,w-101,0,h-101)));fy=torch.fft.fftfreq(h,device=x.device)[:,None];fx=torch.fft.rfftfreq(w,device=x.device)[None,:]
   H=H*torch.exp(2j*math.pi*(fy*cy+fx*cx));G=(1+self.reg)*H.conj()/(H.abs().square()+self.reg)
   if len(self._cache)>4:self._cache.clear()
   self._cache[key]=G
  y=torch.fft.irfft2(torch.fft.rfft2(xp)*self._cache[key],s=(h,w))[...,p:-p,p:-p]
  return y-x
