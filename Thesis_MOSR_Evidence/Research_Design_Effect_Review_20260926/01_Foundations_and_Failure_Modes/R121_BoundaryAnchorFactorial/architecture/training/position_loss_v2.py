"""Position readout centered on reference boundaries, not offset image pixels.

The v1 2D sliding window misread width changes as displacement. This version
samples symmetric normal profiles at the GT boundary and projects brightness
gain/offset nuisance terms out before measuring reference-relative displacement.
"""
import torch
import torch.nn.functional as F
from model.network import geometric_normals
from training.objectives import objective as original_objective

WEIGHT=.02
ANCHORS=128

def profile_reference(target,sdf,flat):
    target=target.float();sdf=sdf.float();n,_,h,w=sdf.shape
    nx,ny=geometric_normals(sdf)
    eligible=sdf[:,0].abs()<=1.5
    eligible[:,:8]=False;eligible[:,-8:]=False;eligible[:,:,:8]=False;eligible[:,:,-8:]=False
    indexes=[];enabled=[]
    for b in range(n):
        ids=torch.nonzero(eligible[b].flatten(),as_tuple=False).flatten()
        if len(ids)==0 or bool(flat[b]):indexes.append(torch.zeros(ANCHORS,device=sdf.device,dtype=torch.long));enabled.append(False)
        else:indexes.append(ids[torch.linspace(0,len(ids)-1,ANCHORS,device=sdf.device).long()]);enabled.append(True)
    indexes=torch.stack(indexes)
    grab=lambda a:torch.gather(a[:,0].flatten(1),1,indexes)
    px=(indexes%w).float();py=(indexes//w).float();distance=grab(sdf);normal_x,normal_y=grab(nx),grab(ny)
    # Project each selected pixel onto the same geometric edge before sampling.
    cx=px-distance*normal_x;cy=py-distance*normal_y
    t=torch.linspace(-6,6,25,device=sdf.device)
    gx=2*(cx[:,:,None]+normal_x[:,:,None]*t)/(w-1)-1
    gy=2*(cy[:,:,None]+normal_y[:,:,None]*t)/(h-1)-1
    grid=torch.stack([gx,gy],-1).detach()
    reference=F.grid_sample(target,grid,mode='bilinear',padding_mode='border',align_corners=True)[:,0]
    derivative=F.pad((reference[:,:,2:]-reference[:,:,:-2]),(1,1),mode='replicate') # central difference / (2*0.5)
    tc=reference-reference.mean(-1,keepdim=True);gc=derivative-derivative.mean(-1,keepdim=True)
    var=tc.square().mean(-1).clamp_min(1e-7)
    coefficient=(tc*gc).mean(-1)/var
    orthogonal=gc-coefficient[:,:,None]*tc
    information=orthogonal.square().mean(-1)
    weight=(information/(information+1e-5)*torch.tensor(enabled,device=sdf.device)[:,None]).detach()
    return grid,reference,orthogonal,information,weight

def profile_position(output,reference):
    grid,target,g,information,weight=reference
    sampled=F.grid_sample(output.float(),grid,mode='bilinear',padding_mode='border',align_corners=True)[:,0]
    residual=sampled-target
    displacement=-(g*residual).mean(-1)/(information+1e-6)
    penalty=F.smooth_l1_loss(displacement/.1,torch.zeros_like(displacement),reduction='none',beta=1.)
    loss=((penalty*weight).sum(-1)/weight.sum(-1).clamp_min(1e-7)).mean()
    return loss,displacement,weight

def local_position(output,target,sdf,flat):
    return profile_position(output,profile_reference(target,sdf,flat))

def objective(model,details,batch,weights,geometry_only=False,arm='A'):
    loss,terms=original_objective(model,details,batch,weights,geometry_only)
    if geometry_only or arm not in ['C','D']:return loss,terms
    reference=profile_reference(batch['target'],batch['sdf'],batch['flat'])
    before,_,_=profile_position(details.geometry_output.clamp(0,1),reference)
    after,_,_=profile_position(details.output,reference)
    return loss+WEIGHT*(before+after),{**terms,'position_before_detail':before,'position_after_detail':after}
