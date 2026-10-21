"""Predeclared disposable R140 pilot. Never supplies weights to formal training."""
from pathlib import Path
import sys,os,time,json,numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import config,model_config,setup,save,now
from model import Model
from training_policy import optimizer,apply_epoch_policy,project_beta_after_step
from dataset import Bank
from losses import objective

def inspect(model,bank,device):
 model.eval();losses=[];head=[];rawdiff=[]
 def capture(module,args,out):head.append(out.detach())
 hook=model.refiner.head.register_forward_hook(capture)
 with torch.inference_mode():
  for index in range(16):
   batch=bank.batch('dev',index,device);y=model(batch['source']);loss,_=objective(y,batch);losses.append(float(loss));rawdiff.append(float((y-batch['source']).abs().mean()))
 hook.remove();logits=torch.cat([v.flatten() for v in head]);absolute=logits.abs()
 return dict(dev16_loss=float(np.mean(losses)),logit_abs_p99=float(torch.quantile(absolute,.99)),logit_abs_max=float(absolute.max()),tanh_saturated_fraction=float((absolute>8).float().mean()),raw_change_mean=float(np.mean(rawdiff)))

def main():
 cfg=config();mc=model_config();setup(cfg['model_seed']);device='cuda';m=Model(mc,ROOT).to(device);opt=optimizer(m,base_lr=cfg['optimizer']['max_lr'],weight_decay=cfg['optimizer']['weight_decay'],optical_lr_multiplier=mc['psf_lr_multiplier']);bank=Bank(cfg)
 stages=[0,32,128,256];rows=[];state=inspect(m,bank,device);state.update(step=0,head_grad_norm=None);rows.append(state);print('PILOT',state,flush=True)
 start=time.perf_counter();policy=apply_epoch_policy(m,0)
 for step in range(1,257):
  i=int(bank.order(0)[step-1]);b=bank.batch('train',i,device,0)
  lr=(cfg['optimizer']['max_lr']*step/cfg['warmup'] if step<=cfg['warmup'] else cfg['optimizer']['min_lr']+.5*(cfg['optimizer']['max_lr']-cfg['optimizer']['min_lr'])*(1+np.cos(np.pi*(step-cfg['warmup'])/(cfg['updates']-cfg['warmup']))))
  for group in opt.param_groups:group['lr']=lr*(mc['psf_lr_multiplier'] if group['name']=='optical' else 1)
  m.train();opt.zero_grad(set_to_none=True);y=m(b['source']);loss,_=objective(y,b);assert torch.isfinite(loss);loss.backward();grad=m.refiner.head.weight.grad;gn=float(grad.norm());torch.nn.utils.clip_grad_norm_(m.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);opt.step();project_beta_after_step(m)
  if step in stages:
   state=inspect(m,bank,device);state.update(step=step,head_grad_norm=gn,elapsed_seconds=time.perf_counter()-start);rows.append(state);print('PILOT',state,flush=True)
 gates=cfg['stability_gate'];initial=rows[0]['dev16_loss'];passed=all(row['logit_abs_p99']<gates['logit_abs_p99_max'] and row['tanh_saturated_fraction']<gates['saturation_fraction_abs_gt8_max'] and row['head_grad_norm']>gates['head_gradient_norm_min'] for row in rows[1:]) and rows[-1]['dev16_loss']<=initial*gates['dev16_loss_max_ratio_to_initial']
 result=dict(state='pilot_complete',updates=256,passed=passed,rows=rows,PSF_stage='off_first_two_epochs',weights_discarded=True,no_real_images_read=True,completed_utc=now())
 save(ROOT/'results/pilot_256.json',result);print('PILOT_VERDICT',passed,flush=True)
 if not passed:raise RuntimeError('Pilot stability gates failed; do not run formal training')
if __name__=='__main__':main()
