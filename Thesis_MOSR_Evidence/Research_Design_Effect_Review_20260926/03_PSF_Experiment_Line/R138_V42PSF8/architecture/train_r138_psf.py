import argparse,math,time,os
from types import SimpleNamespace
import torch
from utils import ROOT,config,setup,load,save,now,sha,state_digest,source_records,verify_frozen,announce,scratch_declaration
from model_r138_psf import Model
from dataset_r138_psf import Bank
from losses_r138_psf import objective
from evaluate_generated import evaluate
from batch_prediction import predict_batch
CFG=SimpleNamespace(MODEL_NAME='R138-V42PSF8');MODEL_NAME_BASE=CFG.MODEL_NAME
def learning_rate(step,cfg):
 o=cfg['optimizer'];warm=cfg['warmup']
 if step<=warm:return o['max_lr']*step/warm
 return o['min_lr']+.5*(o['max_lr']-o['min_lr'])*(1+math.cos(math.pi*(step-warm)/(cfg['updates']-warm)))
def create(cfg):
 setup(cfg['model_seed']);m=Model(cfg['model']).to(cfg['device']);o=cfg['optimizer'];opt=torch.optim.AdamW(m.parameters(),lr=o['max_lr'],weight_decay=o['weight_decay']);return m,opt
def update(model,opt,batch,lr,cfg):
 for g in opt.param_groups:g['lr']=lr
 model.train();opt.zero_grad(set_to_none=True);pred=predict_batch(model,batch);loss,terms=objective(pred,batch)
 if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
 loss.backward();gn=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True);opt.step()
 return dict(loss=float(loss),gradient_norm=float(gn),learning_rate=lr,terms={k:float(v) for k,v in terms.items()},parent_id=batch['parent_id'],parent_sha256=batch['parent_sha256'],input_sha256=batch['input_sha256'],noise_seed=batch['noise_seed'])
def train_formal():
 cfg=config();assert cfg['checkpoint'] is None and not cfg['pretrained'] and not cfg['resume'] and cfg['teacher'] is None
 pre=load(ROOT/'results/preflight.json');assert pre['all_required_checks_passed']
 binding=load(ROOT/'config/source_lock.json');verify_frozen(binding)
 run=ROOT/'runs/formal_8192'
 if run.exists():raise FileExistsError('Formal run exists; do not silently resume or overwrite it')
 run.mkdir();(run/'checkpoints').mkdir();(run/'evaluations').mkdir()
 model,opt=create(cfg);bank=Bank(cfg);initial=state_digest(model);assert initial==pre['scratch_initial_parameter_sha256']
 announce();config_record=dict(**cfg,**scratch_declaration(),source_hashes=binding,config_sha256=sha(ROOT/'config_r138_psf.yaml'),dataset_manifest_sha256=sha(ROOT/'data/manifest.json'),initial_parameter_sha256=initial,parameter_count=sum(p.numel() for p in model.parameters()),actual_git_head=load(ROOT/'config/execution_context.json')['git_head'],started_utc=now())
 save(run/'run_config.json',config_record)
 marker=ROOT/'runs/launcher_logs/active_formal_run.json';save(marker,dict(state='training',pid=os.getpid(),run=str(run),model='R138-V42PSF8',scratch=True,started_utc=now()))
 start=time.perf_counter();evaluations=[]
 # Generated development only; never open any real evaluation image here.
 evaluations.append(evaluate(model,bank,'dev',cfg['device'],run/'evaluations/dev_00000.json',0))
 log=(run/'updates.jsonl').open('x',encoding='utf-8',buffering=1)
 for epoch in range(cfg['epochs']):
  for pos,index in enumerate(bank.order(epoch)):
   step=epoch*512+pos+1;tick=time.perf_counter();b=bank.batch('train',int(index),cfg['device'],epoch)
   row=update(model,opt,b,learning_rate(step,cfg),cfg);row.update(step=step,epoch=epoch,position=pos,seconds=time.perf_counter()-tick,utc=now());log.write(__import__('json').dumps(row)+'\n')
   if step%32==0:
    status=dict(state='training',pid=os.getpid(),step=step,total=8192,epoch=epoch,elapsed_seconds=time.perf_counter()-start,latest_loss=row['loss'],updated_utc=now());save(run/'status.json',status);print(f"Training {step}/8192 loss={row['loss']:.5f} elapsed={status['elapsed_seconds']:.1f}s",flush=True)
   if step%cfg['save_every']==0:
    verify_frozen(binding)
    p=run/'checkpoints'/f'step{step:05d}.pth';tmp=p.with_suffix('.tmp')
    torch.save(dict(model_name='R138-V42PSF8',initialization='scratch',optical_mode='v42_select8',model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),step=step,epoch=epoch,config=cfg,source_hashes=binding,initial_parameter_sha256=initial,torch_rng=torch.get_rng_state(),cuda_rng=[]),tmp);os.replace(tmp,p)
    save(run/'latest_checkpoint.json',dict(step=step,path=str(p),sha256=sha(p)))
   if step%cfg['dev_every']==0:evaluations.append(evaluate(model,bank,'dev',cfg['device'],run/'evaluations'/f'dev_{step:05d}.json',step))
 log.close();test=evaluate(model,bank,'test',cfg['device'],run/'evaluations/test_08192.json',8192)
 verify_frozen(binding);cp=load(run/'latest_checkpoint.json');assert cp['step']==8192
 rows=[__import__('json').loads(x) for x in (run/'updates.jsonl').read_text().splitlines()];assert len(rows)==8192 and [x['step'] for x in rows]==list(range(1,8193))
 for ep in range(16):assert len({x['parent_id'] for x in rows if x['epoch']==ep})==512
 result=dict(state='training_and_generated_evaluation_complete',unique_updates=8192,final_checkpoint=cp,parameter_count=config_record['parameter_count'],peak_training_allocated_bytes=0,peak_training_reserved_bytes=0,elapsed_seconds=time.perf_counter()-start,dev_evaluations=len(evaluations),test_summary=test['means'],real_evaluation_complete=False,initial_parameter_sha256=initial,completed_utc=now())
 save(run/'training_complete.json',result);save(run/'status.json',result);save(marker,dict(state='generated_complete_real_pending',pid=os.getpid(),run=str(run),completed_training_updates=8192))
 return result
if __name__=='__main__':train_formal()
