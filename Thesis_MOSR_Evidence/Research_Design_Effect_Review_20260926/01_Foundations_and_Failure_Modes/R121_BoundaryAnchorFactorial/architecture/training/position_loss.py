"""Local normal-position supervision before and after additive detail.

Regress local brightness gain and offset out of the reference derivative before
measuring shift. No global-center cancellation, model gate, or raw-fixed target.
"""
import torch
import torch.nn.functional as F
from training.objectives import objective as original_objective,gradient,per_scene
from model.network import geometric_normals

WEIGHT=.02
WINDOW=11

def local_position(output,target,sdf,flat):
    target=target.float();output=output.float();sdf=sdf.float()
    gx,gy=gradient(target);nx,ny=geometric_normals(sdf)
    derivative=gx*nx+gy*ny;residual=output-target
    def avg(x):return F.avg_pool2d(F.pad(x,(WINDOW//2,)*4,mode='reflect'),WINDOW,1)
    mt,mg,mr=avg(target),avg(derivative),avg(residual)
    vt=(avg(target.square())-mt.square()).clamp_min(1e-7)
    vg=(avg(derivative.square())-mg.square()).clamp_min(0)
    gt=avg(derivative*target)-mg*mt
    gr=avg(derivative*residual)-mg*mr
    tr=avg(target*residual)-mt*mr
    information=(vg-gt.square()/vt).clamp_min(0)
    numerator=gr-gt*tr/vt
    displacement=-numerator/(information+1e-6)
    # Reference-only information weights cannot be optimized by a model gate.
    weight=((sdf.abs()<=1.5).float()*(~flat)[:,None,None,None].float()*information/(information+1e-5)).detach()
    penalty=F.smooth_l1_loss(displacement/.1,torch.zeros_like(displacement),reduction='none',beta=1.)
    return per_scene(penalty,weight).mean(),displacement,weight

def objective(model,details,batch,weights,geometry_only=False,arm='A'):
    loss,terms=original_objective(model,details,batch,weights,geometry_only)
    if geometry_only or arm not in ['C','D']:return loss,terms
    before,_,_=local_position(details.geometry_output.clamp(0,1),batch['target'],batch['sdf'],batch['flat'])
    after,_,_=local_position(details.output,batch['target'],batch['sdf'],batch['flat'])
    terms={**terms,'position_before_detail':before,'position_after_detail':after}
    return loss+WEIGHT*(before+after),terms
