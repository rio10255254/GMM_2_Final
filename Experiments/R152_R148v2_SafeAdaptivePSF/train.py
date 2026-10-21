from __future__ import annotations
import argparse,json,math,os,time
from pathlib import Path
import torch
from dataset import Bank
from losses import objective
from model import Model
from utils import ROOT,data_config,load,model_config,now,save,setup,sha,train_config,verify_bank_lock
def lr_for(step,total,cfg):
 o=cfg['optimizer'];warm=min(cfg['warmup'],max(8,total//8))
 if step<=warm:return o['max_lr']*step/warm
 return o['min_lr']+.5*(o['max_lr']-o['min_lr'])*(1+math.cos(math.pi*(step-warm)/(total-warm)))
def assess(model,bank,split,device,cfg,limit=None):
 model.eval();n=cfg['splits'][split] if limit is None else min(limit,cfg['splits'][split]);rows=[]
 with torch.inference_mode():
  for i in range(n):
   b=bank.batch(split,i,device);out,parts=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(out,parts,b,model,cfg);task=sum(cfg['loss'][k]*terms[k] for k in ('image','gradient','pair_output','boundary'))+cfg['loss']['observation']*terms['observation'];rows.append(dict(total=float(loss),task=float(task),**{k:float(v) for k,v in terms.items()}))
 keys=rows[0].keys();return dict(split=split,parents=n,mean={k:sum(r[k] for r in rows)/n for k in keys})
def main():
 p=argparse.ArgumentParser();p.add_argument('--run-name',required=True);p.add_argument('--short-updates',type=int);p.add_argument('--seed',type=int);p.add_argument('--assessment-limit',type=int,default=16);a=p.parse_args();cfg=train_config();mc=model_config();reference=data_config();seed=cfg['model_seed'] if a.seed is None else a.seed;setup(seed);verify_bank_lock();checkpoint_path=Path(mc['base_checkpoint']);assert sha(checkpoint_path)==mc['base_checkpoint_sha256'];bank=Bank(cfg);device=cfg['device'];model=Model(mc,ROOT).to(device);trainable=[p for p in model.parameters() if p.requires_grad];opt=torch.optim.AdamW(trainable,lr=cfg['optimizer']['max_lr'],weight_decay=cfg['optimizer']['weight_decay']);run=ROOT/'runs'/a.run_name
 if run.exists() and not (run/'latest.json').exists():raise FileExistsError('Run exists without a resumable checkpoint')
 run.mkdir(parents=True,exist_ok=True);(run/'checkpoints').mkdir(exist_ok=True);latest=run/'latest.json';log=run/'updates.jsonl';start=0;total=cfg['updates'] if a.short_updates is None else a.short_updates;formal=a.short_updates is None
 if latest.exists():
  rec=load(latest);assert sha(rec['path'])==rec['sha256'];cp=torch.load(rec['path'],map_location='cpu',weights_only=False);assert cp['model_config']==mc and cp['seed']==seed;model.load_state_dict(cp['model'],strict=True);opt.load_state_dict(cp['optimizer']);torch.set_rng_state(cp['torch_rng']);torch.cuda.set_rng_state_all(cp['cuda_rng']);start=cp['step'];assert len(log.read_text(encoding='utf-8').splitlines())==start
 save(run/'run_config.json',dict(model=mc,train=cfg,seed=seed,total=total,formal=formal,base_checkpoint_sha256=mc['base_checkpoint_sha256'],payload_manifest_sha256=reference['payload_manifest_sha256'],geometry_manifest_sha256=reference['geometry_manifest_sha256'],started_utc=now()))
 limit=None if formal else a.assessment_limit
 if start==0:
  model.set_deployment_scale(0);save(run/'dev_base.json',assess(model,bank,'dev',device,cfg,limit));model.set_deployment_scale(1);save(run/'dev_initial.json',assess(model,bank,'dev',device,cfg,limit))
 begin=time.perf_counter()
 def save_checkpoint(step,name=None):
  path=run/'checkpoints'/(name or f'step{step:05d}.pth');tmp=path.with_suffix('.tmp');torch.save(dict(model_name=mc['model_name'],model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),step=step,seed=seed,model_config=mc,train_config=cfg,base_checkpoint_sha256=mc['base_checkpoint_sha256'],payload_manifest_sha256=reference['payload_manifest_sha256'],geometry_manifest_sha256=reference['geometry_manifest_sha256'],checkpoint_kind='trained_extension' if formal and step==8192 else 'short_test' if not formal and step==total else 'incomplete_training',torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all()),tmp);os.replace(tmp,path);record=dict(path=str(path),step=step,sha256=sha(path));save(latest,record);return record
 with log.open('a',encoding='utf-8',buffering=1) as h:
  for step in range(start+1,total+1):
   epoch=(step-1)//512;index=int(bank.order(epoch)[(step-1)%512]);b=bank.batch('train',index,device,epoch);model.train();model.set_deployment_scale(1);opt.zero_grad(set_to_none=True);out,parts=model(b['source'],b['operator_psf_indices'],True);loss,terms=objective(out,parts,b,model,cfg);loss.backward();grad=float(torch.nn.utils.clip_grad_norm_(trainable,cfg['optimizer']['gradient_clip'],error_if_nonfinite=True));rate=lr_for(step,total,cfg)
   for group in opt.param_groups:group['lr']=rate
   opt.step();weights=model.psf_fusion.last_weights;h.write(json.dumps(dict(step=step,epoch=epoch,parent_id=b['parent_id'],category=b['category'],loss=float(loss),**{k:float(v) for k,v in terms.items()},gradient_l2=grad,weight_min=float(weights.min()),weight_max=float(weights.max()),weight_entropy=float(model.psf_fusion.last_entropy),learning_rate=rate,utc=now()))+'\n')
   if step%32==0 or step==total:save(run/'status.json',dict(state='training',step=step,total=total,loss=float(loss),safe_scale=float(model.safe_scale()),elapsed_seconds=time.perf_counter()-begin,updated_utc=now()));print('TRAIN',a.run_name,step,'/',total,float(loss),'scale',float(model.safe_scale()),flush=True)
   if step%128==0 or step==total:save_checkpoint(step)
   if formal and step%cfg['dev_every']==0:save(run/f'dev_{step:05d}.json',assess(model,bank,'dev',device,cfg))
 if formal:
  raw_training_checkpoint=load(latest);model.set_deployment_scale(0);base=assess(model,bank,'dev',device,cfg);candidates=[];guard=cfg['deployment_guard_relative']
  for scale in cfg['deployment_scale_candidates']:
   model.set_deployment_scale(scale);result=assess(model,bank,'dev',device,cfg);accepted=all(result['mean'][k]<=base['mean'][k]*(1+guard) for k in ('image','gradient','pair_output','boundary','observation'));candidates.append(dict(scale=scale,accepted=accepted,result=result))
  allowed=[x for x in candidates if x['accepted']];chosen=min(allowed,key=lambda x:x['result']['mean']['task']);model.set_deployment_scale(chosen['scale']);save(run/'deployment_selection.json',dict(base=base,candidates=candidates,chosen_scale=chosen['scale'],guard_relative=guard,selected_before_real_validation=True,completed_utc=now()));deployed=save_checkpoint(total,'deployed_step08192.pth');test=assess(model,bank,'test',device,cfg);save(run/'test_final.json',test);save(run/'training_complete.json',dict(updates=total,training_checkpoint=raw_training_checkpoint,deployed_checkpoint=deployed,deployment_scale=chosen['scale'],base_checkpoint_sha256=mc['base_checkpoint_sha256'],real_validation_complete=False,completed_utc=now()))
 else:
  final=assess(model,bank,'dev',device,cfg,limit);save(run/'dev_final.json',final);save(run/'short_complete.json',dict(updates=total,checkpoint=load(latest),dev_base=load(run/'dev_base.json')['mean'],dev_initial=load(run/'dev_initial.json')['mean'],dev_final=final['mean'],not_a_formal_model=True,completed_utc=now()))
 save(run/'status.json',dict(state='training_complete' if formal else 'short_complete',step=total,total=total,updated_utc=now()));print('FINISHED',a.run_name,flush=True)
if __name__=='__main__':main()
