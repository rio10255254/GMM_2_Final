"""Complete software-side shape fixtures, without asserting real material calibration."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
from torch.nn import functional as F

def coverage_loss(image,target,foreground,background,qualified):
    if not qualified:raise ValueError('Material-to-optical relationship not qualified')
    coverage=(image-background)/(foreground-background)
    error=coverage-target
    return error.square().mean()+error.mean().square()

def main():
    y,x=torch.meshgrid(torch.linspace(-1,1,96,dtype=torch.float64),torch.linspace(-1,1,96,dtype=torch.float64),indexing='ij')
    sigmoid=lambda s:torch.sigmoid(s/.025)
    shapes={'ellipse':sigmoid(1-(x/.6)**2-(y/.4)**2),'corner':sigmoid(.5-x.abs())*sigmoid(.5-y.abs()),'thin_ring':sigmoid(.55-torch.sqrt(x*x+y*y))*sigmoid(torch.sqrt(x*x+y*y)-.42),'narrow_gap':sigmoid(.6-x.abs())*sigmoid(.3-y.abs())*(1-sigmoid(.04-x.abs())),'crescent':sigmoid(.6-torch.sqrt(x*x+y*y))*(1-sigmoid(.5-torch.sqrt((x-.2)**2+y*y)))}
    rows=[]
    for name,target in shapes.items():
        for polarity in ['dark','bright']:
            fg,bg=(.2,.8) if polarity=='dark' else (.8,.2);truth=target[None,None];identity=bg+(fg-bg)*truth
            same=coverage_loss(identity,truth,fg,bg,True);assert float(same)<1e-14
            for mode,bad in [('translation',torch.roll(truth,2,-1)),('width_only_blur',F.avg_pool2d(F.pad(truth,(1,1,1,1),mode='replicate'),3,1)),('expansion',F.max_pool2d(truth,3,1,1))]:
                image=(bg+(fg-bg)*bad).detach().requires_grad_(True);loss=coverage_loss(image,truth,fg,bg,True);gradient=torch.autograd.grad(loss,image)[0];assert float(loss)>0 and torch.isfinite(gradient).all() and gradient.norm()>0
                improved=coverage_loss(image-.001*gradient,truth,fg,bg,True);assert improved<loss
                rows.append(dict(shape=name,polarity=polarity,case=mode,loss=float(loss),after_gradient_step=float(improved),gradient_norm=float(gradient.norm())))
    rejected=False
    try:coverage_loss(identity,truth,fg,bg,False)
    except ValueError:rejected=True
    assert rejected
    save(ROOT/'results/geometry_contracts.json',dict(cases=rows,identity_cases=10,unqualified_mapping_rejected=True,geometry_enabled_in_A_C=False,meaning='Tests an output-image coverage objective on known soft shapes. Responds to blur AND position, not a pure-position estimator. No realSEM mapping qualification inferred.',source=record(__file__)));print('30geometryfixtures,10identities,unqualifiedmappingrejection passed',flush=True)
if __name__=='__main__':main()
