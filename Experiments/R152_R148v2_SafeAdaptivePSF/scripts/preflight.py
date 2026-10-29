from __future__ import annotations
import json,sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dataset import Bank
from losses import objective
from model import Model
from utils import model_config,now,save,setup,sha,train_config,verify_bank_lock
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def main():
 setup(1522001);lock=verify_bank_lock();mc=model_config();cfg=train_config();assert sha(str(PROJECT_ROOT / mc['base_checkpoint']))==mc['base_checkpoint_sha256'];device='cuda' if torch.cuda.is_available() else 'cpu';model=Model(mc,ROOT).to(device);bank=Bank(cfg);batch=bank.batch('dev',0,device);model.eval();model.set_deployment_scale(0)
 with torch.inference_mode():out0,parts0=model(batch['source'],batch['operator_psf_indices'],True)
 exact=float((out0-parts0['base']).abs().max());model.set_deployment_scale(1)
 with torch.inference_mode():out1,parts1=model(batch['source'],batch['operator_psf_indices'],True)
 initial_rms=float((out1-parts1['base']).double().square().mean().sqrt()*255);model.train();out,parts=model(batch['source'],batch['operator_psf_indices'],True);loss,terms=objective(out,parts,batch,model,cfg);loss.backward();trainable_grad=sum(float(p.grad.detach().double().square().sum()) for p in model.parameters() if p.requires_grad and p.grad is not None)**.5;base_grad=sum(1 for p in model.base.parameters() if p.grad is not None);single=batch['source'][:1];model.eval();model.set_deployment_scale(0)
 with torch.inference_mode():full=model(single);tiled=model.forward_tiled(single)
 result=dict(status='passed' if exact==0 and trainable_grad>0 and base_grad==0 else 'failed',completed_utc=now(),device=device,base_checkpoint_sha256=mc['base_checkpoint_sha256'],psf_bank_sha256=lock['bank_sha256'],total_parameters=sum(p.numel() for p in model.parameters()),trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),frozen_parameters=sum(p.numel() for p in model.parameters() if not p.requires_grad),deployment_zero_max_abs=exact,initial_extension_rms_gray=initial_rms,trainable_gradient_l2=trainable_grad,base_parameters_with_gradient=base_grad,tiled_full_at_fallback_max_gray=float((full-tiled).abs().max()*255),initial_safe_scale=float(model.safe_scale()),psf_beta=float(model.psf_fusion.beta_value()),weight_min=float(model.psf_fusion.last_weights.min()),weight_max=float(model.psf_fusion.last_weights.max()));save(ROOT/'results/preflight.json',result);print(json.dumps(result,indent=2));assert result['status']=='passed'
if __name__=='__main__':main()
