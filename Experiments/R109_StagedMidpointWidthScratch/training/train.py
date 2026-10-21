"""Single formal entry point for staged R109 scratch training."""
from __future__ import annotations
import argparse,hashlib,json,math,os,random,sys,time
from pathlib import Path
from typing import Any
import cv2,numpy as np,torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
ROOT=Path(__file__).resolve().parents[1];CONFIG=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'));sys.path.insert(0,str(ROOT/'model'));sys.path.insert(0,str(ROOT/'training'))
from r109_model import build_model,count_parameters
from r109_dataset import R109Dataset
from losses import detector_components,renderer_components,combine
def atomic_json(path,payload):path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as handle:
  for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def seed_all(seed):random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);torch.backends.cudnn.benchmark=True;torch.set_float32_matmul_precision('high')
def worker_seed(worker_id):seed=torch.initial_seed()%2**32;np.random.seed(seed+worker_id);random.seed(seed+worker_id)
def flatten(batch,device):
 result={}
 for name in ('source','target','mask','sdf','edge'):result[name]=batch[name].reshape(-1,*batch[name].shape[2:]).to(device,non_blocking=True)
 for name in ('identity','midpoint','polarity','width_gain_target'):result[name]=batch[name].reshape(-1).to(device,non_blocking=True)
 return result
def loader(dataset,batch,workers,shuffle,seed):
 generator=torch.Generator();generator.manual_seed(seed);options=dict(dataset=dataset,batch_size=batch,shuffle=shuffle,num_workers=workers,pin_memory=True,drop_last=shuffle,worker_init_fn=worker_seed,generator=generator)
 if workers>0:options.update(persistent_workers=True,prefetch_factor=2)
 return DataLoader(**options)
def warp(x,dx,dy):
 n,_c,h,w=x.shape;theta=torch.zeros((n,2,3),device=x.device,dtype=x.dtype);theta[:,0,0]=1;theta[:,1,1]=1;theta[:,0,2]=-2*dx/max(w-1,1);theta[:,1,2]=-2*dy/max(h-1,1);grid=F.affine_grid(theta,x.shape,align_corners=True);return F.grid_sample(x,grid,mode='bilinear',padding_mode='reflection',align_corners=True)
def translation_loss(model,source,base,step):
 generator=torch.Generator(device=source.device).manual_seed(int(CONFIG['data']['seed'])+step*17);dx=torch.empty(source.shape[0],device=source.device).uniform_(-.9,.9,generator=generator);dy=torch.empty(source.shape[0],device=source.device).uniform_(-.9,.9,generator=generator);shifted=model(warp(source,dx,dy));expected=warp(base.detach(),dx,dy);margin=16;return F.smooth_l1_loss(shifted[...,margin:-margin,margin:-margin],expected[...,margin:-margin,margin:-margin],beta=.25/255)
def exposure_loss(model,source,base,step):
 scale=(.78,.90,1.12,1.24)[step%4];scaled=torch.clamp(.5+scale*(source-.5),0,1);prediction=model(scaled);expected=torch.clamp(.5+scale*(base.detach()-.5),0,1);return F.smooth_l1_loss(prediction,expected,beta=.5/255)
def tile_loss(model,source,full):
 halo,core=96,64
 if min(source.shape[-2:])<core+2*halo:return full.new_zeros(())
 top=(source.shape[-2]-core-2*halo)//2;left=(source.shape[-1]-core-2*halo)//2;tile=source[...,top:top+core+2*halo,left:left+core+2*halo];value=model(tile)[...,halo:halo+core,halo:halo+core];reference=full[...,top+halo:top+halo+core,left+halo:left+halo+core].detach();return F.smooth_l1_loss(value,reference,beta=.25/255)
def finite(name,value):
 if not bool(torch.isfinite(value).all()):raise FloatingPointError(name)
def save_preview(path,rows):
 if not rows:return
 tile=192;canvas=np.zeros((len(rows)*tile,3*tile),np.uint8)
 for r,triplet in enumerate(rows):
  for c,image in enumerate(triplet):canvas[r*tile:(r+1)*tile,c*tile:(c+1)*tile]=np.round(np.clip(cv2.resize(image,(tile,tile),interpolation=cv2.INTER_AREA),0,1)*255).astype(np.uint8)
 path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.png',canvas)[1].tofile(str(path))
@torch.inference_mode()
def validate(model,device,limit=128):
 data=R109Dataset('validation',epoch=0,limit=limit);totals={};count=0;previews=[];model.eval()
 for batch_data in loader(data,int(CONFIG['training']['batch_size']),0,False,int(CONFIG['data']['seed'])+99):
  batch=flatten(batch_data,device);details=model.forward_details(batch['source']);dc=detector_components(details,batch['source'],batch['target'],batch['edge'],batch['identity']);rc=renderer_components(details,batch['source'],batch['target'],batch['mask'],batch['edge'],batch['identity'],batch['midpoint'],batch['polarity'],batch['width_gain_target']);components={f'detector_{k}':v for k,v in dc.items()}|{f'renderer_{k}':v for k,v in rc.items()}
  for name,value in components.items():totals[name]=totals.get(name,0)+float(value.cpu())
  totals['width_gain_mean']=totals.get('width_gain_mean',0)+float(details.width_gain.mean().cpu());totals['normal_shift_abs_mean']=totals.get('normal_shift_abs_mean',0)+float(details.normal_shift.abs().mean().cpu());count+=1
  if len(previews)<8:
   for index in range(min(2,len(details.output))):previews.append(np.stack([batch['source'][index,0].cpu().numpy(),details.output[index,0].cpu().numpy(),batch['target'][index,0].cpu().numpy()]))
 return {name:value/max(count,1) for name,value in totals.items()},previews
def run(args):
 if not torch.cuda.is_available():raise RuntimeError('CUDA is required')
 manifest=ROOT/CONFIG['data']['package_root']/'manifest.json'
 if not manifest.exists():raise FileNotFoundError('Run scripts/prepare_data.ps1 first')
 if sha(manifest)!=CONFIG['data']['source_manifest_sha256']:raise RuntimeError('Dataset manifest hash mismatch')
 if args.resume:raise RuntimeError('R109 is scratch-only; checkpoint resume is disabled')
 run_id=args.run_id or f"r109_{time.strftime('%Y%m%d_%H%M%S')}";run_dir=ROOT/'runs'/run_id;run_dir.mkdir(parents=True,exist_ok=False);lock=ROOT/'runs/active_run.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 try:descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(descriptor,run_id.encode());os.close(descriptor)
 except FileExistsError as error:raise RuntimeError(f"Another R109 run is active: {lock.read_text(encoding='utf-8')}") from error
 seed_all(int(CONFIG['data']['seed']));device=torch.device('cuda:0');model=build_model().to(device);detector_parameters=model.detector_parameters();renderer_parameters=model.renderer_parameters();detector_optimizer=torch.optim.AdamW(detector_parameters,lr=float(CONFIG['training']['detector_learning_rate']),weight_decay=float(CONFIG['training']['weight_decay']));renderer_optimizer=torch.optim.AdamW(renderer_parameters,lr=float(CONFIG['training']['renderer_learning_rate']),weight_decay=float(CONFIG['training']['weight_decay']));epochs=int(args.epochs);detector_epochs=int(args.detector_epochs);history=[];global_step=0;started=time.perf_counter();weights=CONFIG['training']['renderer_loss_weights'];amp=bool(args.amp)
 atomic_json(run_dir/'run_state.json',{'status':'running','run_id':run_id,'device':torch.cuda.get_device_name(0),'parameters':count_parameters(model),'scratch':True,'epochs':epochs,'detector_epochs':detector_epochs,'dataset_manifest_sha256':sha(manifest),'config_sha256':sha(ROOT/'config/experiment.json')})
 try:
  for epoch in range(1,epochs+1):
   stage='detector' if epoch<=detector_epochs else 'renderer';model.train();
   for parameter in detector_parameters:parameter.requires_grad_(stage=='detector')
   for parameter in renderer_parameters:parameter.requires_grad_(stage=='renderer')
   optimizer=detector_optimizer if stage=='detector' else renderer_optimizer;stage_start=1 if stage=='detector' else detector_epochs+1;stage_total=detector_epochs if stage=='detector' else epochs-detector_epochs;stage_epoch=epoch-stage_start+1;base_lr=float(CONFIG['training']['detector_learning_rate'] if stage=='detector' else CONFIG['training']['renderer_learning_rate']);minimum=float(CONFIG['training']['minimum_learning_rate']);learning_rate=minimum+.5*(base_lr-minimum)*(1+math.cos(math.pi*(stage_epoch-1)/max(stage_total-1,1)))
   for group in optimizer.param_groups:group['lr']=learning_rate
   dataset=R109Dataset('train',epoch=epoch,limit=int(args.data_limit));epoch_totals={};batches=0;epoch_started=time.perf_counter();torch.cuda.reset_peak_memory_stats(device)
   for batch_data in loader(dataset,int(args.batch_size),int(args.workers),True,int(CONFIG['data']['seed'])+epoch):
    global_step+=1;batch=flatten(batch_data,device);optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type='cuda',dtype=torch.float16,enabled=amp):details=model.forward_details(batch['source']);[finite(f'details.{name}',getattr(details,name)) for name in details.__dataclass_fields__]
    if stage=='detector':
     components=detector_components(details,batch['source'],batch['target'],batch['edge'],batch['identity']);total=.55*components['boundary_bce']+.45*components['boundary_dice']
    else:
     components=renderer_components(details,batch['source'],batch['target'],batch['mask'],batch['edge'],batch['identity'],batch['midpoint'],batch['polarity'],batch['width_gain_target']);frequency=CONFIG['training']['auxiliary_frequency'];components['translation']=translation_loss(model,batch['source'],details.output,global_step) if global_step%int(frequency['translation_every_steps'])==0 else details.output.new_zeros(());components['exposure']=exposure_loss(model,batch['source'],details.output,global_step) if global_step%int(frequency['exposure_every_steps'])==0 else details.output.new_zeros(());components['tile']=tile_loss(model,batch['source'],details.output) if global_step%int(frequency['tile_every_steps'])==0 else details.output.new_zeros(());total=combine(components,weights)
    finite('loss',total);total.backward();norm=torch.nn.utils.clip_grad_norm_((detector_parameters if stage=='detector' else renderer_parameters),float(CONFIG['training']['gradient_clip']));finite('gradient',norm);optimizer.step();[finite(f'parameter.{name}',parameter) for name,parameter in model.named_parameters()]
    batches+=1;epoch_totals['total']=epoch_totals.get('total',0)+float(total.detach().cpu())
    for name,value in components.items():epoch_totals[name]=epoch_totals.get(name,0)+float(value.detach().cpu())
    if global_step==1 or global_step%100==0:
     progress={'epoch':epoch,'stage':stage,'global_step':global_step,'learning_rate':learning_rate,'total':float(total.detach().cpu()),'gradient_norm':float(norm.detach().cpu()),**{name:float(value.detach().cpu()) for name,value in components.items()}};print(json.dumps({'step_progress':progress}),flush=True)
    if args.smoke_steps and batches>=int(args.smoke_steps):break
   validation,previews=validate(model,device,limit=int(args.validation_limit));duration=time.perf_counter()-epoch_started;row={'epoch':epoch,'stage':stage,'global_step':global_step,'learning_rate':learning_rate,'duration_seconds':duration,'gpu_peak_allocated_gib':torch.cuda.max_memory_allocated(device)/2**30,'gpu_peak_reserved_gib':torch.cuda.max_memory_reserved(device)/2**30,**{f'train_{name}':value/max(batches,1) for name,value in epoch_totals.items()},**{f'validation_{name}':value for name,value in validation.items()}};history.append(row);atomic_json(run_dir/'training_history.json',history);print(json.dumps(row),flush=True)
   if epoch%int(CONFIG['training']['preview_every_epochs'])==0 or args.smoke_steps:save_preview(run_dir/'previews'/f'epoch_{epoch:03d}.png',previews)
   if epoch%int(CONFIG['training']['save_every_epochs'])==0 or epoch==epochs or args.smoke_steps:
    path=run_dir/'weights'/f'epoch_{epoch:03d}.pth';path.parent.mkdir(parents=True,exist_ok=True);torch.save({'model':model.state_dict(),'epoch':epoch,'stage':stage,'global_step':global_step,'run_id':run_id,'scratch':True,'validation':validation,'config':CONFIG},path)
  atomic_json(run_dir/'run_state.json',{'status':'complete','run_id':run_id,'epochs_completed':epochs,'global_step':global_step,'elapsed_seconds':time.perf_counter()-started,'scratch':True,'formal':not bool(args.smoke_steps)})
 except BaseException as error:atomic_json(run_dir/'failure.json',{'status':'failed','run_id':run_id,'global_step':global_step,'error_type':type(error).__name__,'error':repr(error)});atomic_json(run_dir/'run_state.json',{'status':'failed','run_id':run_id,'global_step':global_step,'error_type':type(error).__name__});raise
 finally:
  if lock.exists() and lock.read_text(encoding='utf-8')==run_id:lock.unlink()
 return 0
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='');parser.add_argument('--epochs',type=int,default=int(CONFIG['training']['epochs']));parser.add_argument('--detector-epochs',type=int,default=int(CONFIG['training']['detector_epochs']));parser.add_argument('--batch-size',type=int,default=int(CONFIG['training']['batch_size']));parser.add_argument('--workers',type=int,default=int(CONFIG['training']['workers']));parser.add_argument('--amp',action=argparse.BooleanOptionalAction,default=bool(CONFIG['training']['amp']));parser.add_argument('--smoke-steps',type=int,default=0);parser.add_argument('--data-limit',type=int,default=0);parser.add_argument('--validation-limit',type=int,default=128);parser.add_argument('--resume',default='');return run(parser.parse_args())
if __name__=='__main__':raise SystemExit(main())
