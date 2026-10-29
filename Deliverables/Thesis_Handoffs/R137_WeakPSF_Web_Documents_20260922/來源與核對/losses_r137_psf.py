"""Same R129 image/gradient/paired-reference-residual objective; no optics."""
import math
import torch
def robust_gray(residual):
    e=.5/255;s=residual.square();return (s/(torch.sqrt(s+e*e)+e)).mean()*255
def translated(value,delta):
    h,w=value.shape[-2:];nx=math.floor(-delta[0]);ny=math.floor(-delta[1]);fx=-delta[0]-nx;fy=-delta[1]-ny
    def sample(dy,dx):
        out=torch.zeros_like(value);y0=max(0,-dy);y1=min(h,h-dy);x0=max(0,-dx);x1=min(w,w-dx)
        if y1>y0 and x1>x0:out[...,y0:y1,x0:x1]=value[...,y0+dy:y1+dy,x0+dx:x1+dx]
        return out
    return (1-fy)*((1-fx)*sample(ny,nx)+fx*sample(ny,nx+1))+fy*((1-fx)*sample(ny+1,nx)+fx*sample(ny+1,nx+1))
def objective(pred,batch):
    lo,hi=batch['core'];crop=lambda a:a[...,lo:hi,lo:hi];res=pred-batch['target'];r=crop(res)
    terms=dict(image=robust_gray(r),gradient=.5*(robust_gray(r[...,1:]-r[...,:-1])+robust_gray(r[...,1:,:]-r[...,:-1,:])))
    terms['pair']=robust_gray(crop(res[1:2]-translated(res[0:1],batch['shift_xy']))) if batch['motion_observable'] else res.sum()*0
    return terms['image']+.2*terms['gradient']+.2*terms['pair'],terms
