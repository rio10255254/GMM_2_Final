"""Explicit device/thread continuation layer; original locked experiment sources remain unchanged."""
from pathlib import Path
import argparse,os,sys,json,time,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
a=argparse.ArgumentParser();a.add_argument('--device',choices=['cpu','cuda'],required=True);a.add_argument('--threads',type=int,required=True);args=a.parse_args()
if args.threads<1 or args.threads>24:raise ValueError('threads must be1..24')
if args.device=='cpu':os.environ['CUDA_VISIBLE_DEVICES']='-1'
else:os.environ.pop('CUDA_VISIBLE_DEVICES',None)
os.environ['PYTHONWARNINGS']='ignore::FutureWarning'
sys.path.insert(0,str(ROOT))
import torch
import utils
base_config=utils.config;cfg=base_config();cfg['device']=args.device;cfg['cpu_threads']=args.threads
utils.config=lambda:cfg
from train_r138_psf import create,update,learning_rate
from dataset_r138_psf import Bank
from losses_r138_psf import objective
from utils import load,save,sha,state_digest,verify_frozen,verify_protected,now
RUN=ROOT/'runs/formal_8192';REQUEST=HERE/'switch_request.json'
class Handoff(Exception):pass

def main():
 lock=load(ROOT/'config/source_lock.json');verify_frozen(lock);verify_protected()
 overlay=load(HERE/'runtime_source_lock.json')
 for name,digest in overlay.items():assert sha(HERE/name)==digest,name
 if args.device=='cuda' and not torch.cuda.is_available():raise RuntimeError('Requested GPU unavailable; no silent device fallback')
 model,opt=create(cfg);initial=state_digest(model);assert initial==load(ROOT/'results/preflight.json')['scratch_initial_parameter_sha256'];bank=Bank(cfg)
 RUN.mkdir(exist_ok=True);(RUN/'checkpoints').mkdir(exist_ok=True);(RUN/'evaluations').mkdir(exist_ok=True)
 latest=RUN/'latest_checkpoint.json';step=0
 if latest.exists():
  rec=load(latest);assert sha(rec['path'])==rec['sha256'];cp=torch.load(rec['path'],map_location='cpu',weights_only=False)
  assert cp['model_name']=='R138-V42PSF8' and cp['source_hashes']==lock and cp['runtime_source_hashes']==overlay
  model.load_state_dict(cp['model'],strict=True);opt.load_state_dict(cp['optimizer'])
  for state in opt.state.values():
   for key,value in state.items():
    if torch.is_tensor(value) and key!='step':state[key]=value.to(args.device)
  torch.set_rng_state(cp['torch_rng'])
  if args.device=='cuda' and cp.get('cuda_rng'):torch.cuda.set_rng_state_all(cp['cuda_rng'])
  step=cp['step'];logged=[json.loads(s) for s in (RUN/'updates.jsonl').read_text().splitlines()] if (RUN/'updates.jsonl').exists() else []
  assert [r['step'] for r in logged]==list(range(1,step+1)),'Uncheckpointed log tail: preserve and audit before recovery'
 elif (RUN/'updates.jsonl').exists() and (RUN/'updates.jsonl').stat().st_size:raise RuntimeError('Log without checkpoint')
 if not (RUN/'run_config.json').exists():save(RUN/'run_config.json',dict(**cfg,initial_parameter_sha256=initial,source_hashes=lock,runtime_source_hashes=overlay,source_config_sha256=sha(ROOT/'config_r138_psf.yaml'),parameter_count=sum(p.numel() for p in model.parameters()),started_utc=now(),runtime_device_override_explicit=True,old_initial_check='runs/initial_check_before_device_control,0updates,preserved'))
 with (RUN/'device_history.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(start_step=step,device=args.device,threads=args.threads,pid=os.getpid(),utc=now()))+'\n')
 save(HERE/'execution_device.json',dict(device=args.device,threads=args.threads))
 save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(state='training',device=args.device,threads=args.threads,pid=os.getpid(),run=str(RUN),step=step,total=8192))
 start=time.perf_counter()
 def checkpoint():
  p=RUN/'checkpoints'/f'step{step:05d}.pth'
  if not p.exists():
   tmp=p.with_suffix('.tmp');torch.save(dict(model_name='R138-V42PSF8',initialization='scratch',optical_mode='v42_select8',model={k:v.detach().cpu() for k,v in model.state_dict().items()},optimizer=opt.state_dict(),step=step,epoch=max(0,(step-1)//512),config=cfg,source_hashes=lock,runtime_source_hashes=overlay,initial_parameter_sha256=initial,torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if args.device=='cuda' else []),tmp);os.replace(tmp,p)
  save(latest,dict(step=step,path=str(p),sha256=sha(p)))
 def status(phase,**extra):save(RUN/'status.json',dict(state=phase,device=args.device,threads=args.threads,pid=os.getpid(),step=step,total=8192,segment_elapsed_seconds=time.perf_counter()-start,updated_utc=now(),**extra))
 def handoff_if_requested():
  if REQUEST.exists():
   request=load(REQUEST)
   if request['device'] not in ['cpu','cuda'] or not 1<=request['threads']<=24:raise ValueError('Invalid switch request')
   checkpoint();status('checkpoint_saved_for_device_switch',requested_device=request['device'],requested_threads=request['threads']);raise Handoff()
 def evaluate(split,path):
  model.eval();rows=[]
  for idx in range(cfg['splits'][split]):
   with torch.inference_mode():
    b=bank.batch(split,idx,args.device);pred=model(b['source']);loss,terms=objective(pred,b)
   if not torch.isfinite(loss):raise FloatingPointError('Nonfinite evaluation')
   rows.append(dict(index=idx,parent_id=b['parent_id'],total=float(loss),**{k:float(v) for k,v in terms.items()}))
   if (idx+1)%8==0:status('generated_evaluation',split=split,completed_parents=idx+1,total_parents=cfg['splits'][split])
   handoff_if_requested()
  result=dict(step=step,split=split,parents=len(rows),means={k:sum(r[k] for r in rows)/len(rows) for k in ['total','image','gradient','pair']},rows=rows);save(path,result);return result
 checkpoint()
 try:
  if step==0 or step%512==0:
   path=RUN/'evaluations'/f'dev_{step:05d}.json'
   if not path.exists():evaluate('dev',path)
  with (RUN/'updates.jsonl').open('a',encoding='utf-8',buffering=1) as out:
   for next_step in range(step+1,8193):
    ep=(next_step-1)//512;pos=(next_step-1)%512;idx=int(bank.order(ep)[pos]);tick=time.perf_counter();b=bank.batch('train',idx,args.device,ep);row=update(model,opt,b,learning_rate(next_step,cfg),cfg);step=next_step
    row.update(step=step,epoch=ep,position=pos,seconds=time.perf_counter()-tick,utc=now(),device=args.device,cpu_threads=args.threads);out.write(json.dumps(row)+'\n');out.flush()
    if step%4==0:status('training',latest_loss=row['loss']);print(f'{args.device} threads{args.threads} {step}/8192 loss{row["loss"]:.5f}',flush=True)
    if step%128==0:verify_frozen(lock);checkpoint()
    handoff_if_requested()
    if step%512==0:evaluate('dev',RUN/'evaluations'/f'dev_{step:05d}.json')
  path=RUN/'evaluations/test_08192.json';test=load(path) if path.exists() else evaluate('test',path)
  checkpoint();logs=[json.loads(x) for x in (RUN/'updates.jsonl').read_text().splitlines()];assert [x['step'] for x in logs]==list(range(1,8193));verify_frozen(lock);verify_protected()
  result=dict(state='training_and_generated_evaluation_complete',unique_updates=8192,final_checkpoint=load(latest),parameter_count=sum(p.numel() for p in model.parameters()),elapsed_seconds=sum(r['seconds'] for r in logs),elapsed_scope='sum of update wall times; evaluations and restart downtime excluded',dev_evaluations=len(list((RUN/'evaluations').glob('dev_*.json'))),test_summary=test['means'],initial_parameter_sha256=initial,real_evaluation_complete=False,device_history='device_history.jsonl',completed_utc=now())
  save(RUN/'training_complete.json',result);save(RUN/'status.json',result)
 except Handoff:
  print('Saved safe checkpoint at',step,'for device/thread switch',flush=True);return 75
 return 0
if __name__=='__main__':sys.exit(main())
