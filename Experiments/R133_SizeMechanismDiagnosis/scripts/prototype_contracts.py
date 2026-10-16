"""Executable requirements for a future model; not trained replacement weights."""
from common133 import *
from types import SimpleNamespace
from engine import objective

def coverage_objective(image,target_coverage,foreground,background):
    """Only for independently identified two-level optical/material correspondence.
    Uses the actual output image, not a free auxiliary geometry head.
    Not valid for arbitrary real SEM brightness, halos, or unknown illumination.
    """
    coverage=(image-background)/(foreground-background)
    boundary=torch.mean(abs(coverage-target_coverage))
    area=abs(coverage.mean()-target_coverage.mean())
    return boundary+area

def main():
    out=ROOT/'results/contracts';out.mkdir(exist_ok=False)
    torch.manual_seed(13301);raw=.2+.6*torch.rand(1,1,21,23,dtype=torch.float64)
    axis=torch.arange(-6,7,dtype=torch.float64);kernel=torch.exp(-.5*(axis/2)**2);kernel/=kernel.sum();dummy=SimpleNamespace(anchor_kernel=kernel)
    q=torch.tensor([.5],dtype=torch.float64)
    checks=[]
    for highpass in [True,False]:
        result=corrected_output(dummy,raw,raw,q,highpass);assert torch.equal(result,raw)
        fn=lambda n:corrected_output(dummy,raw,n,q,highpass)
        small=raw.detach().clone().requires_grad_(True)
        # Directional finite difference of the complete output, rather than huge
        # full-image Jacobian gradcheck.
        direction=torch.randn_like(small);weight=torch.randn_like(small);value=(fn(small)*weight).sum();g=torch.autograd.grad(value,small)[0];eps=1e-6
        numeric=((fn(small.detach()+eps*direction)-fn(small.detach()-eps*direction))*weight).sum()/(2*eps)
        diff=float(abs(numeric-(g*direction).sum()));assert diff<1e-7 and float(g.norm())>0
        checks.append(dict(highpass=highpass,neutral_exact=True,gradient_norm=float(g.norm()),directional_derivative_error=diff))
    # The actual old image objective can train a radius: lack of an explicit
    # size term does not prove an intrinsic inability to learn geometry.
    yy,xx=torch.meshgrid(torch.arange(96,dtype=torch.float64),torch.arange(96,dtype=torch.float64),indexing='ij');rr=((xx-47.5)**2+(yy-47.5)**2).sqrt();target_cov=torch.sigmoid((18-rr)/.8)
    rows=[]
    for polarity in ['dark','bright']:
        foreground,background=(.2,.8) if polarity=='dark' else (.8,.2)
        radius=torch.tensor(19.,dtype=torch.float64,requires_grad=True);cov=torch.sigmoid((radius-rr)/.8);prediction=(background+(foreground-background)*cov)[None,None];target=(background+(foreground-background)*target_cov)[None,None]
        outputs=torch.cat([prediction,torch.roll(prediction,1,-1)],0);targets=torch.cat([target,torch.roll(target,1,-1)],0)
        class Fixed(torch.nn.Module):
            def forward(self,source):return outputs
        loss,terms=objective(Fixed(),dict(source=targets,target=targets,core=(16,80),metadata=dict(shift_xy=[1.,0.],motion_observable=True)))
        gradient=torch.autograd.grad(loss,radius,retain_graph=True)[0];geom=coverage_objective(prediction,target_cov[None,None],foreground,background);gg=torch.autograd.grad(geom,radius)[0]
        assert float(terms['pair'])==0 and float(gradient)>0 and float(gg)>0
        rows.append(dict(polarity=polarity,diameter_bias_px=2.,actual_image_objective=float(loss),pair_penalty=float(terms['pair']),existing_loss_radius_gradient=float(gradient),qualified_coverage_loss=float(geom),coverage_radius_gradient=float(gg)))
    save(out/'verified.json',dict(output_contracts=checks,radius_gradient_examples=rows,scope='Prototype contracts on known mathematical inputs; no neural training or SEM efficacy claim',geometry_term_qualification='Only valid with known output intensity-to-material coverage relationship; this relationship has NOT been qualified on current realSEM',source=rec(__file__)))
    print('Prototype contracts and real-objective radius gradients verified',flush=True)
if __name__=='__main__':main()
