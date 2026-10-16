"""Explicit reference-based objectives; no target enters the reconstruction model."""
from __future__ import annotations
import torch
import torch.nn.functional as F

def crop(x):return x[...,256:384,256:384]
def per_view_weighted(value,weight):
    return ((value*weight).flatten(1).sum(1)/weight.flatten(1).sum(1).clamp_min(1e-8)).mean()
def robust_gray(residual):
    eps=.5/255
    square=residual.square()
    return (square/(torch.sqrt(square+eps*eps)+eps)).mean()*255
def translated(value,delta):
    n,c,h,w=value.shape
    theta=value.new_zeros(n,2,3);theta[:,0,0]=theta[:,1,1]=1
    theta[:,0,2]=-2*delta[0]/max(w-1,1);theta[:,1,2]=-2*delta[1]/max(h-1,1)
    grid=F.affine_grid(theta,value.shape,align_corners=True)
    return F.grid_sample(value,grid,mode='bilinear',padding_mode='zeros',align_corners=True)

def objective(model,details,source,arrays,metadata,weights,geometry_enabled):
    y0,y1,x0,x1=metadata.get('training_core_slice',[256,384,256,384])
    def crop(x):return x[...,y0:y1,x0:x1]
    target=arrays['target'];latent=arrays['latent_target'];residual=details.output-target
    terms={}
    terms['image_gray']=robust_gray(crop(residual))
    factor=details.latent.shape[-1]//target.shape[-1]
    assert details.latent.shape==latent.shape and factor==4
    terms['latent_gray']=robust_gray((details.latent-latent)[...,y0*factor:y1*factor,x0*factor:x1*factor])
    c=crop(residual)
    terms['gradient_gray']=.5*(robust_gray(c[...,1:]-c[...,:-1])+robust_gray(c[...,1:,:]-c[...,:-1,:]))
    obs_error=crop(model.observation(details.latent)-source)
    terms['observation_noise_units']=.5*(obs_error.square()/model.observation.noise_variance).mean()
    # Reference residual, not aligned predictions alone. Exact references give
    # zero pair error despite the difference between native interpolation and
    # the physical high-resolution motion used in data creation.
    if metadata['motion_observable']:
        pair=residual[1:2]-translated(residual[0:1],metadata['shift_xy'])
        terms['pair_reference_residual_gray']=robust_gray(crop(pair))
    else:
        terms['pair_reference_residual_gray']=details.output.sum()*0
    if geometry_enabled:
        truth=crop(arrays['sdf']).clamp(-16,16);pred=crop(details.geometry['sdf'])
        band=torch.exp(-truth.abs()/3)
        terms['geometry_sdf']=per_view_weighted(F.smooth_l1_loss(pred/4,truth/4,reduction='none',beta=.25),band)
        btruth=crop(arrays['boundary']);logits=crop(details.geometry['boundary_logits'])
        bce=F.binary_cross_entropy_with_logits(logits,btruth,reduction='none')
        if bool(btruth.any()):
            terms['geometry_boundary']=.5*(per_view_weighted(bce,btruth)+per_view_weighted(bce,1-btruth))
        else:
            terms['geometry_boundary']=bce.mean()
        if not metadata['flat']:
            photo=metadata['photometry'];contrast=max(float(photo['high'])-float(photo['low']),.01)*int(metadata['polarity'])
            # Compare errors relative to each reference, not an unsupported
            # assertion that optical intensity equals material occupancy.
            geom_error=torch.sigmoid(pred/2)-torch.sigmoid(truth/2)
            image_error=crop(residual)/contrast
            terms['geometry_image_reference_consistency']=per_view_weighted((geom_error-image_error).abs(),band)
        else:
            terms['geometry_image_reference_consistency']=details.output.sum()*0
    else:
        for k in ['geometry_sdf','geometry_boundary','geometry_image_reference_consistency']:terms[k]=details.output.sum()*0
    loss=sum(weights[k]*value for k,value in terms.items())
    return loss,terms
