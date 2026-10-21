"""Global optical/quality operations; finite-support prior evaluated in exact-context tiles."""
import torch
from torch.nn import functional as F

def tiled_prior(prior,features,native_core=512,native_halo=16):
    # Prior receptive support: stem1 + residual blocks18 =19 feature pixels;
    # bilinear+AA+head add <=3, below 32 feature pixels (=16 native halo).
    if native_halo<16:raise ValueError('Unverified prior context')
    h,w=features.shape[-2:];core=native_core*2;halo=native_halo*2
    output=features.new_empty((features.shape[0],1,h*2,w*2))
    for y in range(0,h,core):
        for x in range(0,w,core):
            ey=min(h,y+core);ex=min(w,x+core);sy=max(0,y-halo);sx=max(0,x-halo);ty=min(h,ey+halo);tx=min(w,ex+halo)
            value=prior(features[...,sy:ty,sx:tx])
            output[...,y*2:ey*2,x*2:ex*2]=value[...,(y-sy)*2:(ey-sy)*2,(x-sx)*2:(ex-sx)*2]
    return output

def predict(model,raw,core=512,halo=16,return_latent=False):
    # No per-tile optics, quality estimation, interpolation of camera frames, or extra padding.
    conditioned,_=model.optics(raw,True,False)
    lift=lambda x,f:x.repeat_interleave(f,-2).repeat_interleave(f,-1)
    original=lift(conditioned,4);o2=lift(conditioned,2);state=original
    p=torch.cat([conditioned[...,:1],conditioned,conditioned[...,-1:]],-1)
    p=torch.cat([p[...,:1,:],p,p[...,-1:,:]],-2)
    dx=(p[...,1:-1,2:]-p[...,1:-1,:-2])*.5;dy=(p[...,2:,1:-1]-p[...,:-2,1:-1])*.5
    lap=p[...,1:-1,2:]+p[...,1:-1,:-2]+p[...,2:,1:-1]+p[...,:-2,1:-1]-4*conditioned
    mean=F.avg_pool2d(conditioned,5,1,2,count_include_pad=False);fixed=[lift(v,2) for v in [dx,dy,lap,mean]]
    for i in range(4):
        native=conditioned+F.avg_pool2d(state-original,4)
        features=torch.cat([F.avg_pool2d(state,2),o2,lift(conditioned-native,2),*fixed],1)
        correction=tiled_prior(model.prior,features,core,halo)
        state=(state+.25*torch.sigmoid(model.step_logits[i])*correction).clamp(0,1)
    neural=(conditioned+F.avg_pool2d(state-original,4)).clamp(0,1)
    out,_=model.anchor(raw,neural)
    return (out,state) if return_latent else out
