"""Scratch training for matched hybrid/native controls and one formal R148v2 run."""
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
def lr_for(step,total,cfg):
 o=cfg['optimizer'];warm=min(cfg['warmup'],max(8,total//8))
 if step<=warm:return o['max_lr']*step/warm
 return o['min_lr']+.5*(o['max_lr']-o['min_lr'])*(1+math.cos(math.pi*(step-warm)/(total-warm)))
def assess(model,bank,split,device,cfg,limit=None):
 model.eval();n=cfg['splits'][split] if limit is None else min(limit,cfg['splits'][split]);values=[];parts=[]
 with torch.inference_mode():
  for i in range(n):
   b=bank.batch(split,i,device);_,states=model(b['source'],b['operator_psf_indices'],True);loss,t=objective(states,b,model,cfg);values.append(float(loss));parts.append({k:float(v) for k,v in t.items()})
 return dict(split=split,parents=n,mean_loss=sum(values)/n,mean_terms={k:sum(x[k] for x in parts)/n for k in parts[0]},individual_loss=values)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run-name',required=True);p.add_argument('--init',choices=['scratch'],default='scratch');p.add_argument('--short-updates',type=int);p.add_argument('--seed',type=int);p.add_argument('--context-mode',choices=('hybrid','native_only'),default='hybrid');a=p.parse_args();cfg=train_config();mc=model_config();seed=cfg['model_seed'] if a.seed is None else a.seed;setup(seed);verify_bank_lock();bank=Bank(cfg);device=cfg['device'];model=Model(mc,ROOT).to(device);model.context_enabled=a.context_mode=='hybrid';opt=optimizer(model,cfg['optimizer']['max_lr'],cfg['optimizer']['weight_decay']);run=ROOT/'runs'/a.run_name
 if run.exists() and not (run/'latest.json').exists():raise FileExistsError('Run exists without checkpoint')
 run.mkdir(parents=True,exist_ok=True);(run/'checkpoints').mkdir(exist_ok=True);latest=run/'latest.json';log=run/'updates.jsonl';start=0;total=cfg['updates'] if a.short_updates is None else a.short_updates;formal=a.short_updates is None
 if latest.exists():
  rec=load(latest);assert sha(rec['path'])==rec['sha256'];cp=torch.load(rec['path'],map_location='cpu',weights_only=False);assert cp['model_config']==mc and cp['data_manifest_sha256']==sha(ROOT/'data/payload/manifest.json') and cp['context_mode']==a.context_mode and cp['seed']==seed;model.load_state_dict(cp['model']);opt.load_state_dict(cp['optimizer']);torch.set_rng_state(cp['torch_rng']);torch.cuda.set_rng_state_all(cp['cuda_rng']);start=cp['step'];assert len(log.read_text().splitlines())==start
 save(run/'run_config.json',dict(model=mc,train=cfg,seed=seed,context_mode=a.context_mode,total=total,formal=formal,data_manifest_sha256=sha(ROOT/'data/payload/manifest.json'),geometry_manifest_sha256=sha(ROOT/'data/geometry/manifest.json'),started_utc=now()))
 limit=None if formal else 16
 if start==0:save(run/'dev_initial.json',assess(model,bank,'dev',device,cfg,limit))
 begin=time.perf_counter()
 def checkpoint_file(step):
  path=run/'checkpoints'/f'step{step:05d}.pth';tmp=path.with_suffix('.tmp');torch.save(dict(model_name=mc['model_name'],model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),step=step,seed=seed,context_mode=a.context_mode,model_config=mc,train_config=cfg,data_manifest_sha256=sha(ROOT/'data/payload/manifest.json'),geometry_manifest_sha256=sha(ROOT/'data/geometry/manifest.json'),psf_bank_sha256=sha(ROOT/mc['psf_bank']),checkpoint_kind='trained_model' if formal and step==8192 else 'short_test' if not formal and step==total else 'incomplete_training',torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all()),tmp);os.replace(tmp,path);save(latest,dict(path=str(path),step=step,sha256=sha(path)))
 with log.open('a',encoding='utf-8',buffering=1) as h:
  for step in range(start+1,total+1):
   epoch=(step-1)//512;idx=int(bank.order(epoch)[(step-1)%512]);b=bank.batch('train',idx,device,epoch);model.train();opt.zero_grad(set_to_none=True);_,states=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(states,b,model,cfg);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);rate=lr_for(step,total,cfg)
   for group in opt.param_groups:group['lr']=rate
   opt.step();h.write(json.dumps(dict(step=step,epoch=epoch,parent_id=b['parent_id'],category=b['category'],context_mode=a.context_mode,loss=float(loss),**{k:float(v) for k,v in terms.items()},eta=(mc['eta_max']*torch.sigmoid(model.step_logits)).detach().cpu().tolist(),learning_rate=rate,utc=now()))+'\n')
   if step%32==0 or step==total:save(run/'status.json',dict(state='training',step=step,total=total,loss=float(loss),elapsed_seconds=time.perf_counter()-begin,updated_utc=now()));print('TRAIN',a.run_name,step,'/',total,float(loss),flush=True)
   if step%128==0 or step==total:checkpoint_file(step)
   if formal and step%cfg['dev_every']==0:save(run/f'dev_{step:05d}.json',assess(model,bank,'dev',device,cfg))
 final=assess(model,bank,'test' if formal else 'dev',device,cfg,limit);save(run/'test_final.json' if formal else 'dev_final.json',final)
 if formal:save(run/'training_complete.json',dict(updates=total,checkpoint=load(latest),context_mode=a.context_mode,real_validation_complete=False,completed_utc=now()))
 else:save(run/'short_complete.json',dict(updates=total,checkpoint=load(latest),seed=seed,context_mode=a.context_mode,dev_initial=load(run/'dev_initial.json')['mean_loss'],dev_final=final['mean_loss'],not_a_formal_model=True,completed_utc=now()))
 save(run/'status.json',dict(state='training_complete' if formal else 'short_complete',step=total,total=total,updated_utc=now()));print('FINISHED',a.run_name,flush=True)
if __name__=='__main__':main()
