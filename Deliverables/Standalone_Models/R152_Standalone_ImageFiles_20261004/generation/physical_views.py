"""Original R148 physical views, using the package-local PSF bank."""
import hashlib
import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.signal import fftconvolve
from settings import ROOT

SPLIT_OFFSET={'train':0,'dev':7,'test':13}
SUB=(.25,.5,.75)
LARGE=(2.,4.,6.,8.)
DIR=((1,0),(0,1),(-1,0),(0,-1))
CONTRAST=(.85,.95,1.,1.15)
BRIGHT=(-5.,0.,3.,5.)
NOISE=(.5,1.,1.5,3.)
_BANK4=None

def digest_array(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()

def bank4():
 global _BANK4
 if _BANK4 is None:
  with np.load(ROOT/'calibration/psf25_bank.npz',allow_pickle=False) as z:bank=z['all_kernels'].astype(np.float64)
  x=np.arange(-50,51,dtype=float);xx=np.linspace(-50,50,401);values=[]
  for kernel in bank:
   k=RectBivariateSpline(x,x,kernel,kx=3,ky=3)(xx,xx);k=np.maximum(k,0);k/=k.sum();values.append(k)
  _BANK4=np.stack(values)
 return _BANK4

def shift4(image,dx,dy):
 ix=int(round(dx*4));iy=int(round(dy*4));assert abs(ix/4-dx)<1e-12 and abs(iy/4-dy)<1e-12;p=40;v=np.pad(image,p,mode='reflect');h,w=image.shape
 return v[p-iy:p-iy+h,p-ix:p-ix+w]

def avg4(x):return x.reshape(384,4,384,4).mean((1,3)).astype(np.float32)

def convolve4(x,kernel):
 p=200;v=np.pad(x,p,mode='reflect');return fftconvolve(v,kernel,mode='same')[p:-p,p:-p]

def specs(split,index,category):
 off=SPLIT_OFFSET[split];sub=SUB[(index+off)%len(SUB)];large=LARGE[(index+off)%len(LARGE)];d0=DIR[(index+off)%4];d1=DIR[(index+off+1)%4]
 shifts=[(0.,0.),(d0[0]*sub,d0[1]*sub),(d1[0]*large,d1[1]*large),(d0[0]*large,d1[1]*sub)]
 rows=[]
 for view,(dx,dy) in enumerate(shifts):
  rotation=(index+off+view)%4;c=1. if view==0 else CONTRAST[rotation];b=0. if view==0 else BRIGHT[(rotation+view)%4];noise=NOISE[(rotation+2*view)%4];psf=(index*4+view+off)%25
  if view==0 and category in ('clean_identity','noisy_identity'):psf=-1
  rows.append(dict(view=view,shift_xy=[dx,dy],contrast=c,brightness_gray=b,noise_sigma_gray=noise,psf_index=psf))
 return rows


def generate_views(latent_float32, metadata):
    """Same photometric headroom, shifts, measured blur and historical rounding."""
    latent = latent_float32.astype(np.float64)
    mid = (metadata['photometry']['low_gray']+metadata['photometry']['high_gray'])/(2*255)
    targets=[]
    noiseless=[]
    views=specs(metadata['split'],metadata['index'],metadata['category'])
    clips=[]
    kernels=bank4()
    for v in views:
        requested_contrast=v['contrast'];requested_brightness=v['brightness_gray']
        span=float(latent.max()-latent.min())
        effective_contrast=min(requested_contrast,.996/max(span,1e-9))
        base=mid+effective_contrast*(latent-mid)
        lower=.002-float(base.min());upper=.998-float(base.max())
        offset=float(np.clip(requested_brightness/255,lower,upper))
        v['requested_contrast']=requested_contrast;v['requested_brightness_gray']=requested_brightness
        v['contrast']=effective_contrast;v['brightness_gray']=offset*255
        clear=base+offset;clips.append(float(((clear<0)|(clear>1)).mean()))
        clear=np.clip(clear,0,1);clear=shift4(clear,*v['shift_xy'])
        targets.append(avg4(clear))
        blurred=clear if v['psf_index']<0 else convolve4(clear,kernels[v['psf_index']])
        noiseless.append(avg4(blurred))
    if max(clips) != 0:
        raise RuntimeError('Original no-clipping contract failed')
    return {'target':np.stack(targets).astype(np.float16),
            'noiseless':np.stack(noiseless).astype(np.float16)},views
