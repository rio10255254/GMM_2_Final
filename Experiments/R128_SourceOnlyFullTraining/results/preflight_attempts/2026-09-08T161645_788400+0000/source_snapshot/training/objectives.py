"""Reference supervision and properly censored sensor residuals after forward."""
import torch
from torch.nn import functional as F
from model.observation import Observation

def robust_gray(residual):
    e=.5/255;s=residual.square()
    return (s/(torch.sqrt(s+e*e)+e)).mean()*255

def translated(value,delta):
    n,c,h,w=value.shape;theta=value.new_zeros(n,2,3);theta[:,0,0]=theta[:,1,1]=1
    theta[:,0,2]=-2*delta[0]/(w-1);theta[:,1,2]=-2*delta[1]/(h-1)
    return F.grid_sample(value,F.affine_grid(theta,value.shape,align_corners=True),mode='bilinear',padding_mode='zeros',align_corners=True)

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
