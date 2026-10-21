"""R139 fixed-budget scratch training, with conservative checkpoint recovery."""
import os,time,math,json,shutil
from pathlib import Path
import torch
from utils import ROOT,config,model_config,setup,load,save,now,sha,state_digest,verify_frozen,verify_protected
from model import Model
from training_policy import optimizer,apply_epoch_policy,project_beta_after_step
from dataset import Bank
from losses import objective

CFG_MODEL_NAME='R139-UNetRecurrent'
MODEL_NAME_BASE=CFG_MODEL_NAME

def learning_rate(step,cfg):
 o=cfg['optimizer'];warm=cfg['warmup']
 if step<=warm:return o['max_lr']*step/warm
 return o['min_lr']+.5*(o['max_lr']-o['min_lr'])*(1+math.cos(math.pi*(step-warm)/(cfg['updates']-warm)))

def require_inputs():
 cfg=config();mc=model_config();assert cfg['device']=='cuda' and cfg['updates']==8192 and cfg['epochs']==16
 assert cfg['splits']==dict(train=512,dev=128,test=128)
 assert sha(ROOT/'data/manifest.json')==load(ROOT/'config/DATA_REFERENCE.json')['manifest_sha256']
 verify_protected();verify_frozen(load(ROOT/'config/FORMAL_SOURCE_LOCK.json'))
 pre=load(ROOT/'results/formal_preflight.json');assert pre['ready_for_formal_training']
 return cfg,mc

def evaluate(model,bank,split,device,path,step,status_path):
 model.eval();rows=[]
 with torch.inference_mode():
  for index in range(bank.cfg['splits'][split]):
   b=bank.batch(split,index,device);pred=model(b['source']);loss,terms=objective(pred,b)
   if not torch.isfinite(loss):raise FloatingPointError('Nonfinite generated evaluation')
   rows.append(dict(index=index,parent_id=b['parent_id'],total=float(loss),**{k:float(v) for k,v in terms.items()}))
   if (index+1)%16==0:save(status_path,dict(state='generated_evaluation',split=split,completed_parents=index+1,total_parents=bank.cfg['splits'][split],step=step,updated_utc=now()))
 result=dict(step=step,split=split,parents=len(rows),means={k:sum(r[k] for r in rows)/len(rows) for k in ['total','image','gradient','pair']},rows=rows)
 save(path,result);return result

def main():
 cfg,mc=require_inputs();setup(cfg['model_seed']);device=cfg['device'];run=ROOT/'runs/formal_8192'
 if (run/'training_complete.json').exists():return
 run.mkdir(parents=True,exist_ok=True);(run/'checkpoints').mkdir(exist_ok=True);(run/'evaluations').mkdir(exist_ok=True)
 model=Model(mc,ROOT).to(device);opt=optimizer(model,base_lr=cfg['optimizer']['max_lr'],weight_decay=cfg['optimizer']['weight_decay'],optical_lr_multiplier=mc['psf_lr_multiplier']);bank=Bank(cfg)
 initial=state_digest(model);initial_record=run/'run_config.json';latest=run/'latest_checkpoint.json';logpath=run/'updates.jsonl';step=0
 if latest.exists():
  rec=load(latest);assert sha(rec['path'])==rec['sha256'];cp=torch.load(rec['path'],map_location='cpu',weights_only=False)
  assert cp['model_name']==CFG_MODEL_NAME and cp['source_hashes']==load(ROOT/'config/FORMAL_SOURCE_LOCK.json') and cp['data_manifest_sha256']==sha(ROOT/'data/manifest.json')
  model.load_state_dict(cp['model'],strict=True);opt.load_state_dict(cp['optimizer']);torch.set_rng_state(cp['torch_rng']);torch.cuda.set_rng_state_all(cp['cuda_rng']);step=cp['step'];initial=cp['initial_parameter_sha256']
  lines=logpath.read_text().splitlines() if logpath.exists() else []
  assert len(lines)>=step and [json.loads(v)['step'] for v in lines[:step]]==list(range(1,step+1))
  if len(lines)>step:
   recovery=run/'recovery'/('tail_after_step'+str(step)+'_'+now().replace(':','-'));recovery.mkdir(parents=True)
   shutil.copy2(logpath,recovery/'full_original_updates.jsonl')
   save(recovery/'RECOVERY.json',dict(last_logged_step=len(lines),restored_checkpoint_step=step,original_log_sha256=sha(logpath),source_log_preserved=True,utc=now()))
   logpath.write_text('\n'.join(lines[:step])+'\n',encoding='utf-8')
 elif logpath.exists() and logpath.stat().st_size:raise RuntimeError('Training log exists without checkpoint')
 if not initial_record.exists():
  save(initial_record,dict(model_name=CFG_MODEL_NAME,**cfg,model=mc,initial_parameter_sha256=initial,parameter_count=sum(p.numel() for p in model.parameters()),source_hashes=load(ROOT/'config/FORMAL_SOURCE_LOCK.json'),data_manifest_sha256=sha(ROOT/'data/manifest.json'),started_utc=now()))
 marker=ROOT/'runs/launcher_logs/active_formal_run.json';save(marker,dict(state='training',device=device,pid=os.getpid(),step=step,total=8192,updated_utc=now()))
 start=time.perf_counter();status=run/'status.json';lock=load(ROOT/'config/FORMAL_SOURCE_LOCK.json');last_epoch=None
 def checkpoint():
  path=run/'checkpoints'/f'step{step:05d}.pth'
  if not path.exists():
   tmp=path.with_suffix('.tmp');torch.save(dict(model_name=CFG_MODEL_NAME,initialization='scratch',model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),step=step,source_hashes=lock,data_manifest_sha256=sha(ROOT/'data/manifest.json'),initial_parameter_sha256=initial,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all(),config=cfg,model_config=mc),tmp);os.replace(tmp,path)
  save(latest,dict(step=step,path=str(path),sha256=sha(path)))
 checkpoint()
 if step==0 and not (run/'evaluations/dev_00000.json').exists():
  apply_epoch_policy(model,0)
  evaluate(model,bank,'dev',device,run/'evaluations/dev_00000.json',0,status)
 with logpath.open('a',encoding='utf-8',buffering=1) as logfile:
  for next_step in range(step+1,8193):
   epoch=(next_step-1)//512;position=(next_step-1)%512;idx=int(bank.order(epoch)[position])
   if epoch!=last_epoch:policy=apply_epoch_policy(model,epoch);last_epoch=epoch
   lr=learning_rate(next_step,cfg)
   for group in opt.param_groups:group['lr']=lr*(mc['psf_lr_multiplier'] if group['name']=='optical' else 1.)
   batch=bank.batch('train',idx,device,epoch);model.train();opt.zero_grad(set_to_none=True);tick=time.perf_counter();prediction=model(batch['source']);loss,terms=objective(prediction,batch)
   if not torch.isfinite(loss):raise FloatingPointError('Nonfinite training loss at '+str(next_step))
   loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);opt.step();project_beta_after_step(model);step=next_step
   block=model.refiner.optics
   row=dict(step=step,epoch=epoch,position=position,parent_id=batch['parent_id'],parent_sha256=batch['parent_sha256'],input_sha256=batch['input_sha256'],noise_seed=batch['noise_seed'],loss=float(loss),terms={k:float(v) for k,v in terms.items()},gradient_norm=float(norm),learning_rate=lr,optical_learning_rate=lr*mc['psf_lr_multiplier'],beta_raw=float(block.beta),beta_scale=float(block.beta_scale),beta_effective=float(block.last_beta),psf_active=policy['optical_active'],seconds=time.perf_counter()-tick,utc=now())
   logfile.write(json.dumps(row)+'\n')
   if step%32==0:
    snapshot=dict(state='training',step=step,total=8192,epoch=epoch,latest_loss=float(loss),beta_raw=float(block.beta),beta_scale=float(block.beta_scale),elapsed_seconds=time.perf_counter()-start,updated_utc=now())
    save(status,snapshot);save(marker,dict(state='training',device=device,pid=os.getpid(),step=step,total=8192,updated_utc=now()))
    print('Training',step,'/8192','loss',f'{float(loss):.5f}','beta',f'{float(block.beta):.5f}','scale',f'{float(block.beta_scale):.3f}',flush=True)
   if step%128==0:verify_frozen(lock);checkpoint()
   if step%512==0:
    evaluate(model,bank,'dev',device,run/'evaluations'/f'dev_{step:05d}.json',step,status)
 if not (run/'evaluations/test_08192.json').exists():test=evaluate(model,bank,'test',device,run/'evaluations/test_08192.json',8192,status)
 else:test=load(run/'evaluations/test_08192.json')
 checkpoint();verify_frozen(lock);verify_protected();records=[json.loads(v) for v in logpath.read_text().splitlines()]
 assert len(records)==8192 and [v['step'] for v in records]==list(range(1,8193))
 for epoch in range(16):assert len({v['parent_id'] for v in records if v['epoch']==epoch})==512
 result=dict(state='training_and_generated_evaluation_complete',unique_updates=8192,final_checkpoint=load(latest),parameter_count=sum(p.numel() for p in model.parameters()),elapsed_seconds=time.perf_counter()-start,elapsed_scope='wall clock including generated evaluations in this uninterrupted process',dev_evaluations=len(list((run/'evaluations').glob('dev_*.json'))),test_summary=test['means'],initial_parameter_sha256=initial,real_evaluation_complete=False,completed_utc=now())
 save(run/'training_complete.json',result);save(status,result);save(marker,dict(state='generated_complete_real_pending',completed_training_updates=8192,completed_utc=now()));print('TRAINING_COMPLETE step8192 checkpoint',result['final_checkpoint']['sha256'],flush=True)
if __name__=='__main__':main()
