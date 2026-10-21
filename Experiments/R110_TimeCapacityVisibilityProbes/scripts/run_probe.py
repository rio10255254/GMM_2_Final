"""Run one R110 causal probe."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,random,sys,time
from pathlib import Path
import cv2,numpy as np,pandas as pd,torch
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[1];R109=Path(r'D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch');sys.path.insert(0,str(R109/'model'));sys.path.insert(0,str(R109/'training'));sys.path.insert(0,str(ROOT/'model'));import r109_model as base;import r109_dataset as data_module;import losses;import train as rtrain;from visibility_model import build_model as build_visibility
CONFIG=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'));HELPER=Path(r'D:\GMM_2_Final\Experiments\R96_LocalizedEvidenceProtectedScratch\scripts\evaluate_real_holdout.py');REAL=[Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\5x_dense_raw.bmp'),Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\20x_mixed_raw.bmp'),Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\50x_array_raw.bmp'),Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\pillar_center9_50x_raw.bmp')]
def load(name,path):spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
helper=load('r110_appearance_helper',HELPER)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def seed_all(seed):random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);torch.backends.cudnn.benchmark=True;torch.set_float32_matmul_precision('high')
class VisibilityDataset(torch.utils.data.Dataset):
 def __init__(self,split,epoch=0,limit=0):self.base=data_module.R109Dataset(split,epoch=epoch,limit=limit)
 def __len__(self):return len(self.base)
 def __getitem__(self,index):
  item=self.base[index];gains=[]
  for view in range(2):
   if bool(item['identity'][view]):gains.append(1.0);continue
   mask=item['mask'][view,0];source=item['source'][view,0];target=item['target'][view,0];inside=mask>.75;outside=mask<.25
   if not bool(inside.any()) or not bool(outside.any()):gains.append(1.0);continue
   target_contrast=torch.abs(torch.median(target[inside])-torch.median(target[outside]));source_contrast=torch.abs(torch.median(source[inside])-torch.median(source[outside]));gains.append(float(torch.clamp(target_contrast/(source_contrast+1/255),1,2)))
  item['visibility_gain_target']=torch.tensor(gains,dtype=torch.float32);return item
def flatten(batch,device,visibility=False):
 result=rtrain.flatten(batch,device)
 if visibility:result['visibility_gain_target']=batch['visibility_gain_target'].reshape(-1).to(device,non_blocking=True)
 return result
def parameter_tv(value):return torch.abs(value[...,1:]-value[...,:-1]).mean()+torch.abs(value[...,1:,:]-value[...,:-1,:]).mean()
def renderer_loss(details,batch,step,model,visibility=False):
 components=losses.renderer_components(details,batch['source'],batch['target'],batch['mask'],batch['edge'],batch['identity'],batch['midpoint'],batch['polarity'],batch['width_gain_target']);frequency=rtrain.CONFIG['training']['auxiliary_frequency'];components['translation']=rtrain.translation_loss(model,batch['source'],details.output,step) if step%int(frequency['translation_every_steps'])==0 else details.output.new_zeros(());components['exposure']=rtrain.exposure_loss(model,batch['source'],details.output,step) if step%int(frequency['exposure_every_steps'])==0 else details.output.new_zeros(());components['tile']=rtrain.tile_loss(model,batch['source'],details.output) if step%int(frequency['tile_every_steps'])==0 else details.output.new_zeros(());total=losses.combine(components,rtrain.CONFIG['training']['renderer_loss_weights'])
 if visibility:
  boundary=F.max_pool2d(batch['edge'],5,1,2).clamp(0,1);target=batch['visibility_gain_target'][:,None,None,None].expand_as(details.visibility_gain);components['visibility_target']=losses.weighted(torch.abs(details.visibility_gain-target),boundary+.01);components['visibility_smoothness']=parameter_tv(details.visibility_gain);total=total+.08*components['visibility_target']+.03*components['visibility_smoothness']
 return total,components
@torch.inference_mode()
def tiled(model,image,device,core=1024,halo=192):
 tensor=torch.from_numpy(image[None,None]).to(device);h,w=image.shape;padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect');output=torch.zeros_like(tensor)
 for y in range(0,h,core):
  for x in range(0,w,core):ch,cw=min(core,h-y),min(core,w-x);tile=padded[...,y:y+ch+2*halo,x:x+cw+2*halo];value=model(tile);output[...,y:y+ch,x:x+cw]=value[...,halo:halo+ch,halo:halo+cw]
 return output[0,0].cpu().numpy()
@torch.inference_mode()
def evaluate_real_and_tile(model,device,output):
 rows=[];previews=[]
 for path in REAL:
  raw=helper.read_gray(path);value=np.round(tiled(model,raw.astype(np.float32)/255,device)*255).astype(np.uint8);destination=output/'real'/path.name;helper.write_gray(destination,value);rows.append({'image':path.name,**helper.appearance_metrics(raw,value,1024)});small=[cv2.resize(image,(480,360),interpolation=cv2.INTER_AREA) for image in (raw,value,np.clip(np.abs(value.astype(np.int16)-raw.astype(np.int16))*8,0,255).astype(np.uint8))];previews.append(np.concatenate(small,1))
 frame=pd.DataFrame(rows);frame.to_csv(output/'real_appearance.csv',index=False);cv2.imencode('.png',np.concatenate(previews,0))[1].tofile(str(output/'real_raw_output_diff.png'))
 generator=torch.Generator(device=device).manual_seed(1100999);image=torch.rand((1,1,512,512),generator=generator,device=device);full=model(image);halo,core=192,128;padded=F.pad(image,(halo,halo,halo,halo),mode='reflect');canvas=torch.zeros_like(image)
 for y in range(0,512,core):
  for x in range(0,512,core):value=model(padded[...,y:y+core+2*halo,x:x+core+2*halo]);canvas[...,y:y+core,x:x+core]=value[...,halo:halo+core,halo:halo+core]
 delta=torch.abs(full-canvas)*255;interior=delta[...,halo:-halo,halo:-halo];return {'real_median':{key:float(frame[key].median()) for key in frame.columns if key!='image'},'tile':{'mean_gray':float(interior.mean()),'p99_gray':float(torch.quantile(interior,.99)),'max_gray':float(interior.max())}}
@torch.inference_mode()
def per_challenge(model,device,visibility=False):
 dataset=VisibilityDataset('validation',epoch=0,limit=512) if visibility else data_module.R109Dataset('validation',epoch=0,limit=512);rows=[];model.eval()
 for item in dataset:
  source=item['source'][0:1].to(device);output=model(source)[0,0].cpu().numpy();target=item['target'][0,0].numpy();mask=item['mask'][0,0].numpy()>.5;mid=float(item['midpoint'][0]);pol=float(item['polarity'][0]);prediction=output>mid if pol>0 else output<mid;intersection=np.logical_and(prediction,mask).sum();union=np.logical_or(prediction,mask).sum();rows.append({'challenge':item['challenge'],'mae_gray':float(np.mean(np.abs(output-target))*255),'change_gray':float(np.mean(np.abs(output-source[0,0].cpu().numpy()))*255),'iou':float(intersection/max(union,1))})
 frame=pd.DataFrame(rows);return frame.groupby('challenge')[['mae_gray','change_gray','iou']].median().reset_index().to_dict(orient='records')
def run(variant):
 cfg=CONFIG['probes'][variant];output=ROOT/'runs'/variant
 if output.exists():raise RuntimeError(f'Output exists: {output}')
 output.mkdir(parents=True);device=torch.device('cuda:0');visibility=variant=='visibility';continuation=variant=='continuation';seed_all(1101001 if continuation else 1102001 if variant=='capacity64' else 1103001)
 if variant=='capacity64':base.MCFG['base_channels']=64;model=base.build_model().to(device)
 elif visibility:model=build_visibility().to(device)
 else:model=base.build_model().to(device);checkpoint=Path(CONFIG['r109_selected_checkpoint']);
 if continuation:
  if sha(checkpoint)!=CONFIG['r109_selected_sha256']:raise RuntimeError('R109 selected hash mismatch')
  model.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=False)['model'])
 detector_parameters=model.detector_parameters();renderer_parameters=model.renderer_parameters();history=[];global_step=0;started=time.perf_counter()
 if continuation:
  for parameter in detector_parameters:parameter.requires_grad_(False)
  optimizer=torch.optim.AdamW(renderer_parameters,lr=float(cfg['learning_rate']),weight_decay=1e-5);schedule=[('renderer',epoch) for epoch in range(49,57)];limit=5000
 else:
  detector_optimizer=torch.optim.AdamW(detector_parameters,lr=3.5e-4,weight_decay=1e-5);renderer_optimizer=torch.optim.AdamW(renderer_parameters,lr=3e-4,weight_decay=1e-5);schedule=[('detector',1),*[('renderer',epoch) for epoch in range(2,6)]];limit=1000
 for position,(stage,data_epoch) in enumerate(schedule,1):
  for parameter in detector_parameters:parameter.requires_grad_(stage=='detector')
  for parameter in renderer_parameters:parameter.requires_grad_(stage=='renderer')
  if continuation:learning_rate=float(cfg['learning_rate'])
  elif stage=='detector':learning_rate=3.5e-4
  else:
   renderer_index=data_epoch-2;learning_rate=2.5e-5+.5*(3e-4-2.5e-5)*(1+math.cos(math.pi*renderer_index/3))
  optimizer=optimizer if continuation else detector_optimizer if stage=='detector' else renderer_optimizer
  for group in optimizer.param_groups:group['lr']=learning_rate
  dataset=VisibilityDataset('train',epoch=data_epoch,limit=limit) if visibility else data_module.R109Dataset('train',epoch=data_epoch,limit=limit);loader=rtrain.loader(dataset,int(cfg['batch_size']),4,True,1100000+data_epoch);model.train();totals={};batches=0;epoch_started=time.perf_counter();torch.cuda.reset_peak_memory_stats(device)
  for batch_data in loader:
   global_step+=1;batch=flatten(batch_data,device,visibility);optimizer.zero_grad(set_to_none=True);details=model.forward_details(batch['source'])
   if stage=='detector':components=losses.detector_components(details,batch['source'],batch['target'],batch['edge'],batch['identity']);total=.55*components['boundary_bce']+.45*components['boundary_dice']
   else:total,components=renderer_loss(details,batch,global_step,model,visibility)
   if not bool(torch.isfinite(total)):
    raise FloatingPointError('loss')
   total.backward();parameters=detector_parameters if stage=='detector' else renderer_parameters;norm=torch.nn.utils.clip_grad_norm_(parameters,5);optimizer.step();batches+=1;totals['total']=totals.get('total',0)+float(total.detach().cpu())
   for name,value in components.items():totals[name]=totals.get(name,0)+float(value.detach().cpu())
   if global_step==1 or global_step%100==0:print(json.dumps({'variant':variant,'stage':stage,'data_epoch':data_epoch,'global_step':global_step,'loss':float(total.detach().cpu()),'gradient':float(norm.detach().cpu())}),flush=True)
  validation,previews=rtrain.validate(model,device,limit=128);row={'probe_epoch':position,'data_epoch':data_epoch,'stage':stage,'global_step':global_step,'learning_rate':learning_rate,'duration_seconds':time.perf_counter()-epoch_started,'gpu_peak_reserved_gib':torch.cuda.max_memory_reserved(device)/2**30,**{f'train_{name}':value/max(batches,1) for name,value in totals.items()},**{f'validation_{name}':value for name,value in validation.items()}}
  if visibility:
   visibility_values=[]
   valdata=VisibilityDataset('validation',epoch=0,limit=128)
   with torch.inference_mode():
    for start in range(0,len(valdata),8):
     items=[valdata[i] for i in range(start,min(start+8,len(valdata)))];source=torch.cat([item['source'] for item in items],0).to(device);visibility_values.append(model.forward_details(source).visibility_gain.mean().cpu())
   row['validation_visibility_gain_mean']=float(torch.stack(visibility_values).mean())
  history.append(row);(output/'training_history.json').write_text(json.dumps(history,indent=2),encoding='utf-8');rtrain.save_preview(output/'previews'/f'probe_{position:02d}.png',previews);print(json.dumps(row),flush=True)
  if continuation and position in (4,8) or not continuation and position==len(schedule):
   path=output/'weights'/('E052.pth' if continuation and position==4 else 'E056.pth' if continuation else f'{variant}_final.pth');path.parent.mkdir(parents=True,exist_ok=True);torch.save({'model':model.state_dict(),'variant':variant,'probe_epoch':position,'source_checkpoint':str(CONFIG['r109_selected_checkpoint']) if continuation else None},path)
 final_checkpoint=output/'weights'/('E056.pth' if continuation else f'{variant}_final.pth');audit=evaluate_real_and_tile(model,device,output);challenge=per_challenge(model,device,visibility);summary={'status':'complete','variant':variant,'checkpoint':str(final_checkpoint),'checkpoint_sha256':sha(final_checkpoint),'elapsed_seconds':time.perf_counter()-started,'history':history,'audit':audit,'per_challenge':challenge,'training_pixels':'procedural only','inherited_weight':continuation,'formal_candidate':False};(output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps({'status':'complete','variant':variant,'checkpoint':str(final_checkpoint)}),flush=True);return 0
def main():parser=argparse.ArgumentParser();parser.add_argument('--variant',choices=['continuation','capacity64','visibility'],required=True);return run(parser.parse_args().variant)
if __name__=='__main__':raise SystemExit(main())
