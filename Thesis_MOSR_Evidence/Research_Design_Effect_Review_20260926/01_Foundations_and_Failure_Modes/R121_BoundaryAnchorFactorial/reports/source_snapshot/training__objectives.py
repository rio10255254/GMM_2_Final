"""Every reported training objective is explicit and connected to its owner."""
from __future__ import annotations
import torch
import torch.nn.functional as F
from model.network import geometric_normals

def per_scene(value,weight=None):
    value=value.float()
    if weight is None:return value.flatten(1).mean(1)
    w=weight.float()
    return (value*w).flatten(1).sum(1)/w.flatten(1).sum(1).clamp_min(1e-7)

def gradient(x):
    gx=F.pad((x[...,2:]-x[...,:-2])*.5,(1,1,0,0),mode='replicate')
    gy=F.pad((x[...,2:,:]-x[...,:-2,:])*.5,(0,0,1,1),mode='replicate')
    return gx,gy

def location_xy(prediction,target,weight=None):
    """Local least-squares x/y shift of prediction relative to fixed reference.

    Opposing sides add information through a 2x2 system rather than cancel in
    a signed radial mean. Rank-deficient patches downweight the invisible axis.
    """
    x,y=gradient(target.float());residual=prediction.float()-target.float()
    w=torch.ones_like(x) if weight is None else weight.float()
    reduce=lambda z:(z*w).flatten(1).sum(1)
    xx,xy,yy=reduce(x*x),reduce(x*y),reduce(y*y)
    a=torch.stack((xx,xy,xy,yy),-1).reshape(-1,2,2)
    b=-torch.stack((reduce(x*residual),reduce(y*residual)),-1)
    ridge=1e-4*(xx+yy).clamp_min(.01)
    matrix=a+ridge[:,None,None]*torch.eye(2,device=a.device)[None]
    displacement=torch.linalg.solve(matrix,b[...,None])[...,0]
    # Reliability describes information in the two directions, not a learned gate.
    eigenvalues=torch.linalg.eigvalsh(a)
    confidence=(eigenvalues[:,0].clamp_min(0)/(eigenvalues[:,0].clamp_min(0)+.01)).detach()
    return displacement,confidence

def shift_image(value,delta):
    n,c,h,w=value.shape;theta=value.new_zeros(n,2,3)
    theta[:,0,0]=theta[:,1,1]=1
    theta[:,0,2]=-2*delta[:,0]/max(w-1,1)
    theta[:,1,2]=-2*delta[:,1]/max(h-1,1)
    grid=F.affine_grid(theta,value.shape,align_corners=True)
    return F.grid_sample(value,grid,align_corners=True,padding_mode='reflection')

def geometry_terms(details,batch):
    truth=batch['sdf'].float()
    band=torch.exp(-truth.abs()/3)
    nonflat=(~batch['flat'])[:,None,None,None].float()
    boundary=torch.exp(-truth.abs()/2.5)*nonflat
    sdf=F.smooth_l1_loss(details.sdf.float(),truth.clamp(-16,16),reduction='none',beta=.5)
    sdf_loss=per_scene(sdf,.02+.98*band).mean()
    # Balance each scene and each side; dense arrays cannot dominate by perimeter.
    bce=F.binary_cross_entropy_with_logits(details.boundary_logits.float(),boundary,reduction='none')
    positive=per_scene(bce,boundary)
    negative=per_scene(bce,1-boundary)
    boundary_loss=(.5*(positive+negative)).mean()
    nx,ny=geometric_normals(truth)
    normal=1-(details.normals[:,0:1]*nx+details.normals[:,1:2]*ny)
    normal_loss=per_scene(normal,band*nonflat).mean()
    return {'geometry_sdf':sdf_loss,'geometry_boundary':boundary_loss,'geometry_normal':normal_loss}

def objective(model,details,batch,weights,geometry_only=False):
    terms=geometry_terms(details,batch)
    if geometry_only:return sum(weights[k]*v for k,v in terms.items()),terms
    output=details.output.float();target=batch['target'].float();residual=output-target
    band=torch.exp(-batch['sdf'].abs()/4)
    fine_reliability=batch['fine_reliability']
    low_residual=F.avg_pool2d(F.pad(residual,(1,1,1,1),mode='reflect'),3,1)
    high_residual=residual-low_residual
    penalty=(torch.sqrt(low_residual.square()+1e-6)-.001)+(torch.sqrt(high_residual.square()+1e-6)-.001)*fine_reliability
    terms['image_reference']=per_scene(penalty,.2+.8*band).mean()
    gx,gy=gradient(residual)
    terms['gradient_reference']=per_scene((gx.abs()+gy.abs())*fine_reliability,.2+.8*band).mean()
    displacement,confidence=location_xy(output,target,.05+.95*band)
    confidence=confidence*(~batch['flat']).float()
    # Dimensionless 0.1-pixel scale gives position a measurable learning signal.
    # This is an optimization scale, not a pass/fail threshold.
    terms['location_xy']=(F.smooth_l1_loss(displacement/.1,torch.zeros_like(displacement),beta=1.,reduction='none').mean(1)*confidence).sum()/confidence.sum().clamp_min(1)
    # Pointwise absolute edge mismatch cannot cancel on opposite sides.
    tgx,tgy=gradient(target)
    scale=torch.sqrt(tgx.square()+tgy.square()+1e-6)
    terms['local_edge_error']=per_scene(F.smooth_l1_loss(residual/scale.clamp_min(.02),torch.zeros_like(residual),beta=.2,reduction='none'),band).mean()
    identity=batch['identity']
    terms['identity']=(torch.sqrt((output[identity]-target[identity]).square()+1e-6)-.001).mean() if identity.any() else output.sum()*0
    # Low-pass observable mismatch relative to reference. No raw radiometry
    # inversion is demanded, and no high-pass projection is applied to output.
    terms['observable_reference_error']=F.avg_pool2d(residual,5,1,2).abs().mean()
    a,b=slice(0,None,2),slice(1,None,2);delta=batch['shift_xy'];crop=lambda t:t[...,20:-20,20:-20]
    pair_error=residual[b]-shift_image(residual[a],delta)
    terms['pair_reference_error']=crop(pair_error).abs().mean()
    # Subtract target warp discrepancy: a perfect sampled target has zero error
    # even where bilinear image translation is not exact sensor integration.
    sdf_error=details.sdf-batch['sdf'].clamp(-16,16)
    terms['pair_geometry']=crop(sdf_error[b]-shift_image(sdf_error[a],delta)).abs().mean()
    pair_confidence=torch.minimum(confidence[a],confidence[b])
    terms['pair_location_xy']=(F.smooth_l1_loss(displacement[b]/.1,displacement[a]/.1,beta=1.,reduction='none').mean(1)*pair_confidence).sum()/pair_confidence.sum().clamp_min(1)
    return sum(weights[k]*v for k,v in terms.items()),terms
