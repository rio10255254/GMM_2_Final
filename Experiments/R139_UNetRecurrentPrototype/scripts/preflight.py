"""Architecture preflight on real project input shape and scratch gradients.

The only outputs are prototype feasibility evidence. It does not create weights
or claim real metrology performance.
"""
from pathlib import Path
import json,hashlib,time,os,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,torch
from model import Model
from training_policy import optimizer,apply_epoch_policy,project_beta_after_step
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'config/model.json').read_text(encoding='utf-8-sig'))

def save(name,data):
    p=ROOT/'results'/name
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    torch.manual_seed(139001)
    torch.set_num_threads(8)
    model=Model(CFG,ROOT)
    selected=list(model.refiner.optics.psf_indices)
    assert selected==[0,3,7,10,14,17,21,24]
    assert model.refiner.optics.beta_scale.item()==0
    counts={"down":0,"up":0,"skip":0,"psf":0}
    hooks=[]
    for module in (model.refiner.down1,model.refiner.down2,model.refiner.down3):
        hooks.append(module.register_forward_hook(lambda _m,_a,_o:counts.__setitem__("down",counts["down"]+1)))
    for module in (model.refiner.up3,model.refiner.up2,model.refiner.up1):
        hooks.append(module.register_forward_hook(lambda _m,_a,_o:counts.__setitem__("up",counts["up"]+1)))
    hooks.append(model.refiner.optics.register_forward_hook(lambda _m,_a,_o:counts.__setitem__("psf",counts["psf"]+1)))
    x=torch.rand(1,1,257,263,dtype=torch.float32)*0.8+0.1
    model.eval()
    with torch.inference_mode():
        y,states=model(x,trace=True)
    assert torch.equal(x,y)
    assert y.shape==x.shape and len(states)==4
    assert counts['down']==12 and counts['up']==12 and counts['psf']==0
    for state in states:
        f=state['features']
        assert f['full_skip'].shape[-2:]==x.shape[-2:]
        assert f['half_skip'].shape[-2:]==(129,132)
        assert f['quarter_skip'].shape[-2:]==(65,66)
    for hook in hooks:hook.remove()
    stage0=apply_epoch_policy(model,0)
    stage2=apply_epoch_policy(model,2)
    assert stage0['beta_scale']==0 and abs(stage2['beta_scale']-.12)<1e-7
    assert all(p.requires_grad for p in model.refiner.optics.parameters())
    calls=[]
    hook=model.refiner.optics.register_forward_hook(lambda _m,_a,_o:calls.append(1))
    with torch.inference_mode():active=model(x)
    assert len(calls)==1 and torch.equal(active,x)
    hook.remove()
    with torch.no_grad():model.refiner.head.weight.normal_(0,.001)
    model.train()
    opt=optimizer(model)
    opt.zero_grad(set_to_none=True)
    target=torch.clamp(x+0.01,0,1)
    y=model(x)
    loss=(y-target).square().mean()
    loss.backward()
    grad_gate=model.refiner.optics.gating[-1].weight.grad
    grad_beta=model.refiner.optics.beta.grad
    assert grad_gate is not None and torch.isfinite(grad_gate).all()
    assert grad_beta is not None and torch.isfinite(grad_beta).all()
    opt.step();project_beta_after_step(model)
    assert 0 <= model.refiner.optics.beta.item() <= .1
    # This verifies the boundary behavior that failed in R138.
    with torch.no_grad():model.refiner.optics.beta.fill_(-.01)
    project_beta_after_step(model)
    assert model.refiner.optics.beta.item()==0
    model.zero_grad(set_to_none=True)
    loss=model(x).mean();loss.backward()
    assert model.refiner.optics.beta.grad is not None
    assert torch.isfinite(model.refiner.optics.beta.grad)
    beta_boundary_gradient=float(model.refiner.optics.beta.grad.abs())
    assert beta_boundary_gradient>1e-12
    result={
        "model":"R139-UNetRecurrentPrototype",
        "status":"untrained_prototype_preflight_only",
        "parameter_count":sum(p.numel() for p in model.parameters()),
        "input_shape":[1,1,257,263],"output_shape":list(y.shape),
        "exact_initial_identity":True,
        "three_down_and_three_up_per_iteration":True,
        "skip_shapes":{"full":[257,263],"half":[129,132],"quarter":[65,66]},
        "shared_iterations":4,
        "V42_module_auto_selected_indices":selected,
        "PSF_insertion":"half-resolution decoder on final iteration only",
        "PSF_calls_when_scale_zero":0,"PSF_calls_when_active":1,
        "gating_gradient_finite":True,"beta_gradient_finite":True,
        "beta_recoverable_at_zero":True,
        "beta_boundary_gradient_abs":beta_boundary_gradient,
        "optical_training_scale_after_first_two_epochs":[0,.12],
        "real_validation_performed":False,"full_size_1544x2064_checked":False,
    }
    save('preflight.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
