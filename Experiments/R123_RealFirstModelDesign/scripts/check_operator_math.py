"""Small independent arithmetic checks for the proposed observation step.

These are software/mathematical checks, not a trained model or real validation.
Uses zero-boundary test operators; production calibrated boundaries remain to verify.
"""
import json,pathlib
import numpy as np
import torch
import torch.nn.functional as F
E=pathlib.Path(__file__).resolve().parents[1]
def main():
    torch.manual_seed(1239001);torch.set_num_threads(2);dtype=torch.float64
    raw=torch.rand(1,1,19,23,dtype=dtype)
    up=lambda y:y.repeat_interleave(2,-2).repeat_interleave(2,-1)
    integrate=lambda x:F.avg_pool2d(x,2)
    kernel=torch.tensor([[1,2,1],[2,4,2],[1,2,1]],dtype=dtype)[None,None]/16
    observe=lambda x:integrate(F.conv2d(x,kernel,padding=1))
    # Adjoint of averaging repeats with area weight, followed by transposed convolution.
    adjoint=lambda y:F.conv_transpose2d(up(y)/4,kernel,padding=1)
    x=torch.rand_like(up(raw));v=torch.randn_like(raw)
    lhs=(observe(x)*v).sum();rhs=(x*adjoint(v)).sum();adjoint_error=float(abs(lhs-rhs))
    assert adjoint_error<1e-12
    target=observe(x);p=(x+.05*torch.randn_like(x)).requires_grad_(True)
    loss=.5*((observe(p)-target)**2).sum();autograd=torch.autograd.grad(loss,p)[0];manual=adjoint(observe(p.detach())-target)
    graderr=float((autograd-manual).abs().max());assert graderr<1e-12
    direction=torch.randn_like(p);h=1e-5
    q=lambda a:.5*((observe(a)-target)**2).sum()
    finite=(q(p.detach()+h*direction)-q(p.detach()-h*direction))/(2*h)
    differential=(manual*direction).sum();fd_error=float(abs(finite-differential));assert fd_error<1e-9
    eta=1.;next_state=p.detach()-eta*manual;before=float(q(p.detach()));after=float(q(next_state));assert after<before
    init=up(raw);init_identity=float((integrate(init)-raw).abs().max());assert init_identity==0
    corrected=init-adjoint(observe(init)-raw)
    changed=float((integrate(corrected)-raw).abs().max());assert changed>0
    # In an identity-optics case, integration matches exactly and the correction is zero.
    identity_residual=integrate(init)-raw;identity_final=init-up(identity_residual)/4
    identity_error=float((integrate(identity_final)-raw).abs().max());assert identity_error==0
    result={'native_repeat_integrate_identity_error':init_identity,'identity_optics_zero_update_error':identity_error,'blurred_operator_zero_prior_still_changes_raw_max':changed,'adjoint_inner_product_error':adjoint_error,'manual_vs_autograd_gradient_error':graderr,'finite_difference_gradient_error':fd_error,'one_step_observation_loss_before':before,'one_step_observation_loss_after':after,'ineffective_proximity_term_removed':True,'scope':'2x linear zero-boundary arithmetic only; not production forward-model qualification, tile certification, or evidence of real image improvement'}
    (E/'results/operator_math_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
