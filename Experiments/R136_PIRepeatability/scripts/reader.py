"""Translation from common image regions; image-only registration, no PI input."""
import numpy as np
from scipy import fft,ndimage

def dft_peak(cross,center,steps):
    h,w=cross.shape;fy=fft.fftfreq(h);fx=fft.fftfreq(w);c=np.array(center,dtype=float)
    for step,radius in steps:
        ys=c[0]+np.arange(-radius,radius+1)*step;xs=c[1]+np.arange(-radius,radius+1)*step
        ey=np.exp(2j*np.pi*ys[:,None]*fy[None,:]);ex=np.exp(2j*np.pi*fx[:,None]*xs[None,:])
        score=(ey@cross@ex).real;j,k=np.unravel_index(np.argmax(score),score.shape);c=np.array([ys[j],xs[k]])
    return c

def correlation_shift(a,b,refine=True,local=False):
    fa=fft.fft2(a,workers=1);fb=fft.fft2(b,workers=1);cross=fa*np.conj(fb)
    if local:return dft_peak(cross,[0.,0.],[(.1,10),(.01,7),(.001,7)])
    corr=fft.ifft2(cross,workers=1).real;peak=np.unravel_index(np.argmax(corr),corr.shape);s=np.array(peak,dtype=float)
    shape=np.array(a.shape);s[s>shape//2]-=shape[s>shape//2]
    if refine:s=dft_peak(cross,s,[(.1,7),(.01,7),(.001,7)])
    return s

def overlap(a,b,s):
    si=np.rint(s).astype(int);h,w=a.shape;ra=np.maximum(si,0);rb=np.maximum(-si,0);size=np.array([h,w])-np.abs(si)
    if np.any(size<64):raise ValueError('Insufficient image overlap')
    aa=a[ra[0]:ra[0]+size[0],ra[1]:ra[1]+size[1]];bb=b[rb[0]:rb[0]+size[0],rb[1]:rb[1]+size[1]]
    return aa,bb,si

def measure(a,b,roi,mode='highpass',coarse=None):
    x,y,w,h=roi;a=np.asarray(a[y:y+h,x:x+w],np.float64);b=np.asarray(b[y:y+h,x:x+w],np.float64)
    if coarse is None:coarse=correlation_shift(a-a.mean(),b-b.mean(),False)
    aa,bb,integer=overlap(a,b,coarse)
    if mode=='highpass':aa=aa-ndimage.gaussian_filter(aa,3);bb=bb-ndimage.gaussian_filter(bb,3)
    aa=aa-aa.mean();bb=bb-bb.mean();window=np.outer(np.hanning(aa.shape[0]),np.hanning(aa.shape[1]))
    aa*=window;bb*=window;s=correlation_shift(aa,bb,local=True)+integer
    residual=s-integer
    return dict(dx_px=float(-s[1]),dy_px=float(-s[0]),coarse_dx_px=float(-coarse[1]),coarse_dy_px=float(-coarse[0]),refinement_px=float(np.linalg.norm(residual)),overlap_pixels=int(aa.size))
