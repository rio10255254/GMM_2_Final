"""Fixed scratch training for R148."""
from __future__ import annotations
import argparse,json,math,os,time
from pathlib import Path
from types import SimpleNamespace
import torch
from dataset import Bank
from losses import objective
from model import Model
from training_policy import optimizer
from utils import ROOT,load,save,sha,now,setup,model_config,train_config,verify_bank_lock
CFG=SimpleNamespace(MODEL_NAME=model_config()['model_name']);MODEL_NAME_BASE=CFG.MODEL_NAME
def lr_for(step,cfg):
 o=cfg['optimizer']
 if step<=cfg['warmup']:return o['max_lr']*step/cfg['warmup']
 return o['min_lr']+.5*(o['max_lr']-o['min_lr'])*(1+math.cos(math.pi*(step-cfg['warmup'])/(cfg['updates']-cfg['warmup'])))
def assess(model,bank,split,device,limit=None):
 model.eval();cfg=train_config();values=[];parts=[];count=cfg['splits'][split] if limit is None else min(limit,cfg['splits'][split])
 with torch.inference_mode():
  for i in range(count):
   b=bank.batch(split,i,device);_,states=model(b['source'],b['operator_psf_indices'],True);loss,t=objective(states,b,model,cfg);values.append(float(loss));parts.append({k:float(v) for k,v in t.items()})
 return dict(split=split,parents=count,mean_loss=sum(values)/count,mean_terms={k:sum(x[k] for x in parts)/count for k in parts[0]},individual_loss=values)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run-name',required=True);p.add_argument('--init',choices=['scratch'],default='scratch');p.add_argument('--smoke',action='store_true');a=p.parse_args();cfg=train_config();mc=model_config();setup(cfg['model_seed']);device=cfg['device'];verify_bank_lock();bank=Bank(cfg)
 if MODEL_NAME_BASE!=mc['model_name']:raise RuntimeError('Artifact identity mismatch')
 run=ROOT/'runs'/a.run_name
 if run.exists() and not (run/'latest.json').exists():raise FileExistsError('Run exists without resume checkpoint')
 run.mkdir(parents=True,exist_ok=True);(run/'checkpoints').mkdir(exist_ok=True);model=Model(mc,ROOT).to(device);opt=optimizer(model,cfg['optimizer']['max_lr'],cfg['optimizer']['weight_decay'],mc['optical_lr_multiplier']);latest=run/'latest.json';log=run/'updates.jsonl';start=0
 if latest.exists():
  rec=load(latest);assert sha(rec['path'])==rec['sha256'];cp=torch.load(rec['path'],map_location='cpu',weights_only=False)
  if cp['model_config']!=mc or cp['data_manifest_sha256']!=sha(ROOT/'data/payload/manifest.json'):raise RuntimeError('Resume identity mismatch')
  model.load_state_dict(cp['model']);opt.load_state_dict(cp['optimizer']);torch.set_rng_state(cp['torch_rng']);torch.cuda.set_rng_state_all(cp['cuda_rng']);start=cp['step'];assert len(log.read_text().splitlines())==start
 save(run/'run_config.json',dict(model_config=mc,train_config=cfg,initialization='scratch',data_manifest_sha256=sha(ROOT/'data/payload/manifest.json'),psf_bank_sha256=sha(ROOT/mc['psf_bank']),started_utc=now()))
 total=64 if a.smoke else cfg['updates'];begin=time.perf_counter()
 if start==0:save(run/'dev_initial.json',assess(model,bank,'dev',device,4 if a.smoke else None))
 def checkpoint_file(step):
  path=run/'checkpoints'/f'step{step:05d}.pth';tmp=path.with_suffix('.tmp');torch.save(dict(model_name=mc['model_name'],initialization='scratch',model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),step=step,model_config=mc,train_config=cfg,data_manifest_sha256=sha(ROOT/'data/payload/manifest.json'),psf_bank_sha256=sha(ROOT/mc['psf_bank']),checkpoint_kind='trained_model' if step==cfg['updates'] and not a.smoke else 'incomplete_training',torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all()),tmp);os.replace(tmp,path);save(latest,dict(path=str(path),step=step,sha256=sha(path)))
 with log.open('a',encoding='utf-8',buffering=1) as h:
  for step in range(start+1,total+1):
   epoch=(step-1)//512;idx=int(bank.order(epoch)[(step-1)%512]);b=bank.batch('train',idx,device,epoch);model.train();opt.zero_grad(set_to_none=True);_,states=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(states,b,model,cfg)
   if not torch.isfinite(loss):raise FloatingPointError(step)
   loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);rate=lr_for(step,cfg)
   for group in opt.param_groups:group['lr']=rate*(mc['optical_lr_multiplier'] if group['name']=='optical_step' else 1)
   opt.step();row=dict(step=step,epoch=epoch,parent_id=b['parent_id'],category=b['category'],loss=float(loss),**{k:float(v) for k,v in terms.items()},eta=(mc['eta_max']*torch.sigmoid(model.step_logits)).detach().cpu().tolist(),physical_steps=(mc['optical_step_max']*torch.sigmoid(model.optical_step_logits)).detach().cpu().tolist(),learning_rate=rate,utc=now());h.write(json.dumps(row)+'\n')
   if step%32==0 or step==total:save(run/'status.json',dict(state='training',step=step,total=total,loss=float(loss),elapsed_seconds=time.perf_counter()-begin,updated_utc=now()));print('TRAIN',step,'/',total,'loss',float(loss),flush=True)
   if step%cfg['save_every']==0 or step==total:checkpoint_file(step)
   if step%cfg['dev_every']==0 and not a.smoke:save(run/f'dev_{step:05d}.json',assess(model,bank,'dev',device))
 if a.smoke:save(run/'smoke_complete.json',dict(updates=total,not_a_trained_model=True,completed_utc=now()))
 else:save(run/'test_final.json',assess(model,bank,'test',device));save(run/'training_complete.json',dict(updates=total,checkpoint=load(latest),real_validation_complete=False,completed_utc=now()))
 save(run/'status.json',dict(state='smoke_complete' if a.smoke else 'training_complete',step=total,total=total,updated_utc=now()));print('FINISHED',a.run_name,flush=True)
if __name__=='__main__':main()
