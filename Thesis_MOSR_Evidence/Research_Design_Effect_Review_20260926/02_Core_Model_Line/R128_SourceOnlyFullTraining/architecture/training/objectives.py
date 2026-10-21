"""Reference supervision and properly censored sensor residuals after forward."""
import math
import torch
from torch.nn import functional as F
from model.observation import Observation

def robust_gray(residual):
    e=.5/255;s=residual.square()
    return (s/(torch.sqrt(s+e*e)+e)).mean()*255

def translated(value,delta):
    # A constant known translation needs four slice copies. Unlike CUDA
    # grid_sample backward, these copies never scatter competing atomic sums.
    h,w=value.shape[-2:];nx=math.floor(-delta[0]);ny=math.floor(-delta[1]);fx=-delta[0]-nx;fy=-delta[1]-ny
    def sample(dy,dx):
        out=torch.zeros_like(value);y0=max(0,-dy);y1=min(h,h-dy);x0=max(0,-dx);x1=min(w,w-dx)
        if y1>y0 and x1>x0:out[...,y0:y1,x0:x1]=value[...,y0+dy:y1+dy,x0+dx:x1+dx]
        return out
    return (1-fy)*((1-fx)*sample(ny,nx)+fx*sample(ny,nx+1))+fy*((1-fx)*sample(ny+1,nx)+fx*sample(ny+1,nx+1))

def sensor_nll(mean,source,sigma_gray):
    # Interior quantized bins use a Gaussian approximation with quantization
    # variance 1/12 gray^2. Clipped bins are tail probabilities, never exact
    # equality targets. The predeclared .5-gray floor also covers noiseless data.
    scale=mean.new_tensor((max(float(sigma_gray),.5)**2+1/12)**.5)
    gray_mean=mean*255;gray_source=source*255
    middle=.5*((gray_mean-gray_source)/scale).square()
    low=-torch.special.log_ndtr((.5-gray_mean)/scale)
    high=-torch.special.log_ndtr((gray_mean-254.5)/scale)
    return torch.where(source==0,low,torch.where(source==1,high,middle)).mean()

def observation_prediction(latent,kernel,core):
    lo,hi=core;radius=(kernel.shape[-1]-1)//2
    margin=(radius+3)//4
    small=latent[...,(lo-margin)*4:(hi+margin)*4,(lo-margin)*4:(hi+margin)*4]
    if lo-margin<0:raise ValueError('Insufficient actual observation context')
    prediction=Observation(kernel)(small)
    n=hi-lo
    return prediction[...,margin:margin+n,margin:margin+n]

def objective(details,batch,weights,observation_weight):
    lo,hi=batch['core'];crop=lambda a:a[...,lo:hi,lo:hi]
    residual=details.output-batch['target'];r=crop(residual)
    terms=dict(image_gray=robust_gray(r),
               latent_gray=robust_gray((details.latent-batch['latent_target'])[...,lo*4:hi*4,lo*4:hi*4]),
               gradient_gray=.5*(robust_gray(r[...,1:]-r[...,:-1])+robust_gray(r[...,1:,:]-r[...,:-1,:])))
    m=batch['metadata']
    terms['pair_reference_residual_gray']=robust_gray(crop(residual[1:2]-translated(residual[0:1],m['shift_xy']))) if m['motion_observable'] else residual.sum()*0
    # I logs the identical observation diagnostic without its backward graph.
    if observation_weight:
        pred=observation_prediction(details.latent,batch['kernel'],batch['core'])
        terms['observation_noise_units']=sensor_nll(pred,crop(batch['source']),m['noise_sigma_gray'])
    else:
        with torch.no_grad():
            pred=observation_prediction(details.latent,batch['kernel'],batch['core'])
            terms['observation_noise_units']=sensor_nll(pred,crop(batch['source']),m['noise_sigma_gray'])
    loss=sum(weights[k]*terms[k] for k in weights)+observation_weight*terms['observation_noise_units']
    return loss,terms
