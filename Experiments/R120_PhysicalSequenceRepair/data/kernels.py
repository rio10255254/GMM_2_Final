"""Centered asymmetric optical prior; explicit convolution orientation."""
import numpy as np
from scipy.signal import fftconvolve


def centered_asymmetric(factor=1):
    radius=int(np.ceil(6*2.8*factor+3*factor))
    a=np.arange(-radius,radius+1,dtype=float)/factor
    y,x=np.meshgrid(a,a,indexing='ij')
    w=.23;dx,dy=3.,-.4
    first=np.exp(-.5*(((x+w*dx)/1.45)**2+((y+w*dy)/1.)**2));first/=first.sum()
    second=np.exp(-.5*(((x-(1-w)*dx)/2.8)**2+((y-(1-w)*dy)/1.3)**2));second/=second.sum()
    k=(1-w)*first+w*second
    # Correct the tiny finite-window moment without negative weights.
    for _ in range(8):
        m=np.array([(k*x).sum(),(k*y).sum()])
        if np.linalg.norm(m)<1e-12:break
        c=np.array([[(k*x*x).sum(),(k*x*y).sum()],[(k*x*y).sum(),(k*y*y).sum()]])-np.outer(m,m)
        d=np.linalg.solve(c,m)
        k*=np.exp(-d[0]*x-d[1]*y);k/=k.sum()
    return k


def centroid(kernel):
    y,x=np.indices(kernel.shape,dtype=float)
    return np.array([(kernel*(x-kernel.shape[1]//2)).sum(),(kernel*(y-kernel.shape[0]//2)).sum()])/kernel.sum()


def convolve(image,kernel):
    radius=kernel.shape[0]//2
    return fftconvolve(np.pad(image,radius,mode='reflect'),kernel,mode='valid')
