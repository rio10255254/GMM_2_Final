"""Read-only, fixed-checkpoint PSF gate diagnosis; does not save modified weights."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,torch
from torch.nn import functional as F
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from model import Model
from dataset import Bank
from losses import objective
from training_policy import apply_epoch_policy,optimizer
from utils import ROOT,config,model_config,setup,sha

def stats(a):
    a=a.detach().float()
    return dict(rms=float(a.square().mean().sqrt()),maximum=float(a.abs().max()))

def candidate_features(block,x,reg):
    psf=block.PSFs.float();_,_,h,w=x.shape;_,_,ph,pw=psf.shape
    pad_w=w-pw;pad_h=h-ph;pad=(pad_w//2,pad_w-pad_w//2,pad_h//2,pad_h-pad_h//2)
    img=torch.fft.rfft2(x.float());mask=block._lowfreq_mask(h,w,x.device)
    responses=[]
    for k in range(block.k):
        z=torch.fft.rfft2(F.pad(psf[:,k:k+1],pad))
        filt=(z.conj()/(z.abs().square()+reg+1e-6))*mask+(1-mask)
        y=torch.fft.irfft2(img*filt,s=(h,w)).clamp(-100,100)
        responses.append(y)
    return torch.stack(responses,dim=0)

def main():
    cfg=config();setup(cfg['model_seed']);torch.set_num_threads(4)
    checkpoints=ROOT/'runs/formal_8192/checkpoints'
    zero=torch.load(checkpoints/'step00000.pth',map_location='cpu',weights_only=False)
    final=torch.load(checkpoints/'step08192.pth',map_location='cpu',weights_only=False)
    model=Model(model_config(),ROOT).cuda()
    model.load_state_dict(final['model'],strict=True)
    model.eval();apply_epoch_policy(model,15)
    block=model.refiner.optics
    opt=optimizer(model,base_lr=cfg['optimizer']['max_lr'],weight_decay=cfg['optimizer']['weight_decay'],optical_lr_multiplier=model.cfg['psf_lr_multiplier'])
    index=int(sys.argv[1]) if len(sys.argv)>1 else 0
    bank=Bank(cfg);batch=bank.batch('test',index,'cuda')
    captured=[]
    handle=block.register_forward_pre_hook(lambda module,args:captured.append(args[0].detach()))
    logits=[]
    h2=model.refiner.head.register_forward_hook(lambda module,args,out:logits.append(out.detach()))
    model.zero_grad(set_to_none=True)
    pred=model(batch['source']);loss,_=objective(pred,batch);loss.backward()
    handle.remove();h2.remove()
    grads={name:(None if p.grad is None else float(p.grad.norm())) for name,p in model.named_parameters()
           if name.startswith('refiner.optics.gating') or name in ('refiner.optics.beta','refiner.head.weight')}
    x=captured[0].detach()
    with torch.no_grad():
        res30=candidate_features(block,x,30.0)
        res1=candidate_features(block,x,1.0)
        res003=candidate_features(block,x,.03)
        def spread(res):
            center=res.mean(0)
            diff=res-center
            return dict(rms=float(diff.square().mean().sqrt()),maximum=float(diff.abs().max()),
                        candidate_pair_max_rms=float(max((res[i]-res[j]).square().mean().sqrt() for i in range(8) for j in range(i))))
        w=torch.softmax(block.gating(x).view(x.shape[0],8)/block.psf_temp,dim=1)
        kernels=block.PSFs[0].cpu().numpy().reshape(8,-1)
        cosine=(kernels@kernels.T)/(np.linalg.norm(kernels,axis=1)[:,None]*np.linalg.norm(kernels,axis=1)[None,:])
        cosine_pair=cosine[np.triu_indices(8,1)]
        beta=float(block.beta*block.beta_scale)
        # Counterfactual single-candidate selection is confined to this in-memory diagnostic.
        output_uniform=pred.detach()
        outputs=[]
        for selected in range(8):
            def force(module,args,out):
                v=torch.full_like(out,-30);v[:,selected,:,:]=30;return v
            h=block.gating.register_forward_hook(force)
            y=model(batch['source']);h.remove();outputs.append(y)
        stack=torch.stack(outputs)
        delta=(stack-output_uniform).abs()
        forced=dict(max_rms_gray=float(max((v-output_uniform).square().mean().sqrt() for v in outputs)*255),
                    max_abs_gray=float(delta.max()*255),
                    pair_max_rms_gray=float(max((outputs[i]-outputs[j]).square().mean().sqrt() for i in range(8) for j in range(i))*255))
    initial=zero['model'];final_state=final['model']
    state={name:dict(max_change=float((final_state[name]-initial[name]).abs().max()),
                     final_max_abs=float(final_state[name].abs().max())) for name in final_state
           if name.startswith('refiner.optics.gating')}
    result=dict(checkpoint_sha256=sha(checkpoints/'step08192.pth'),model_step=final['step'],test_parent=batch['parent_id'],
                psf_indices=list(block.psf_indices),reg=float(block.reg),psf_temp=float(block.psf_temp),
                beta_effective=beta,gate_weights_first_sample=[float(z) for z in w[0]],
                gate_weight_max_deviation_from_equal=float((w-.125).abs().max()),
                psf_kernel_pair_cosine_min=float(cosine_pair.min()),psf_kernel_pair_cosine_max=float(cosine_pair.max()),
                candidate_feature_spread_reg30=spread(res30),candidate_feature_spread_reg1=spread(res1),
                candidate_feature_spread_reg0p03=spread(res003),
                uniform_optics_output_change=stats(block(x)-x),
                loss=float(loss),grad_norms=grads,gate_state_changes=state,
                optical_optimizer_includes_gate=all(any(p is gp for group in opt.param_groups if group['name']=='optical'
                                                        for gp in group['params']) for p in block.gating.parameters()),
                forced_selection_vs_uniform=forced,
                head_logit_abs_p99=float(torch.quantile(torch.cat([z.abs().flatten() for z in logits]),.99)),
                no_saved_weights_modified=True)
    out=Path(__file__).with_name(f'psf_gate_diagnostic_test{index:03d}.json')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
