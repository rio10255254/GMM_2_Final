"""Train per-specialist counterfactual adoption maps after freezing experts."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch import nn


ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results';WEIGHTS=ROOT/'weights';DEVICE=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
spec=importlib.util.spec_from_file_location('specialist_core',ROOT/'scripts/run_specialists.py')
if spec is None or spec.loader is None:raise RuntimeError('Cannot load specialist core')
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
ORDER=['denoise','radiometry','edge','texture']


class AdoptionNet(nn.Module):
 def __init__(self):
  super().__init__();self.blur=core.Blur(1.4);self.tower=core.LocalTower(6,30);self.head=nn.Conv2d(30,1,1);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
 def forward(self,source,proposal):
  delta=proposal-source;gx,gy=core.gradients(source);mag=torch.sqrt(gx.square()+gy.square()+1e-8);features=torch.cat([source,proposal,delta,source-self.blur(source),delta.abs(),mag],1);return torch.sigmoid(self.head(self.tower(features)))


def load_models():
 models={'edge':core.EdgeExpert(),'texture':core.TextureExpert(),'denoise':core.DenoiseExpert(),'radiometry':core.RadiometryExpert()}
 for name,model in models.items():
  payload=torch.load(WEIGHTS/f'{name}.pth',map_location=DEVICE,weights_only=False);model.load_state_dict(payload['model']);model.to(DEVICE).eval()
  for parameter in model.parameters():parameter.requires_grad_(False)
 return models


@torch.inference_mode()
def expert_proposal(name,model,x):
 return model(x)[0]


def oracle_alpha(source,target,proposal,kernel=9):
 delta=proposal-source;desired=target-source;num=F.avg_pool2d(delta*desired,kernel,1,kernel//2);den=F.avg_pool2d(delta.square(),kernel,1,kernel//2)+1e-8;return (num/den).clamp(0,1)


def balanced_alpha_loss(prediction,target):
 losses=[]
 for mask in (target<.10,(target>=.10)&(target<.90),target>=.90):
  if bool(mask.any()):losses.append(F.smooth_l1_loss(prediction[mask],target[mask],beta=.05))
 return torch.stack(losses).mean()


def train_one(name,expert,current,target,edge,role,steps=600,guarded=False):
 offset=100 if guarded else 0;core.seed_all(109000+ORDER.index(name)+offset);selector=AdoptionNet().to(DEVICE);optimizer=torch.optim.AdamW(selector.parameters(),lr=4e-4,weight_decay=1e-5);generator=torch.Generator(device=DEVICE).manual_seed(109010+ORDER.index(name)+offset);trace=[];batch=18
 for step in range(1,steps+1):
  index=torch.randint(0,len(current),(batch,),device=DEVICE,generator=generator);source=current[index];truth=target[index];edge_batch=edge[index]
  with torch.no_grad():proposal=expert_proposal(name,expert,source);alpha_target=oracle_alpha(source,truth,proposal)
  alpha=selector(source,proposal);output=(source+alpha*(proposal-source)).clamp(0,1);alpha_loss=balanced_alpha_loss(alpha,alpha_target);pixel=F.smooth_l1_loss(output,truth,beta=2/255);edge_loss=(torch.abs(output-truth)*(.15+.85*edge_batch)).sum()/(.15+.85*edge_batch).sum();clear_alpha=alpha.new_zeros(())
  if guarded:
   clear_index=torch.randint(0,len(target),(batch,),device=DEVICE,generator=generator);clear=target[clear_index]
   with torch.no_grad():clear_proposal=expert_proposal(name,expert,clear)
   clear_alpha=selector(clear,clear_proposal).mean()
  loss=alpha_loss+.18*pixel+.10*edge_loss+(.65*clear_alpha if guarded else 0)
  optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(selector.parameters(),5);optimizer.step()
  if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f'{name} adoption {step}')
  if step==1 or step%100==0:
   identity=role[index]==core.ROLES.index('identity');row={'step':step,'loss':float(loss.detach()),'alpha_mean':float(alpha.mean().detach()),'target_mean':float(alpha_target.mean().detach()),'identity_alpha':float(alpha[identity].mean().detach()) if bool(identity.any()) else 0.0,'clear_counterfactual_alpha':float(clear_alpha.detach())};trace.append(row);print(json.dumps({'adoption':name,'guarded':guarded,**row}),flush=True)
 tag='adoption_guarded' if guarded else 'adoption';torch.save({'model':selector.state_dict(),'expert':name,'steps':steps,'guarded':guarded},WEIGHTS/f'{tag}_{name}.pth');return selector.eval(),trace


@torch.inference_mode()
def apply_stage(name,expert,selector,current,batch=24):
 rows=[];alphas=[]
 for start in range(0,len(current),batch):
  source=current[start:start+batch];proposal=expert_proposal(name,expert,source);alpha=selector(source,proposal);rows.append((source+alpha*(proposal-source)).clamp(0,1).cpu());alphas.append(alpha.cpu())
 return torch.cat(rows).to(DEVICE),torch.cat(alphas).numpy()


def stage_metrics(before,after,target,alpha,role):
 before_np=before.cpu().numpy();after_np=after.cpu().numpy();truth=target.cpu().numpy();raw=np.abs(before_np-truth).reshape(len(before),-1).mean(1);err=np.abs(after_np-truth).reshape(len(before),-1).mean(1);scene_alpha=alpha.reshape(len(alpha),-1).mean(1);identity=role.cpu().numpy()==core.ROLES.index('identity');degraded=~identity
 return {'before_mae_gray':float(raw.mean()*255),'after_mae_gray':float(err.mean()*255),'improved_fraction':float(np.mean(err<raw)),'alpha_mean':float(alpha.mean()),'alpha_identity_mean':float(scene_alpha[identity].mean()),'alpha_degraded_mean':float(scene_alpha[degraded].mean()),'identity_vs_degraded_auc':float(roc_auc_score(degraded,scene_alpha))}


def final_metrics(source,output,target,edge,role):
 src=source.cpu().numpy();out=output.cpu().numpy();truth=target.cpu().numpy();edge_np=edge.cpu().numpy();raw=np.abs(src-truth);err=np.abs(out-truth);weight=.15+.85*edge_np;identity=role.cpu().numpy()==core.ROLES.index('identity')
 return {'images':len(src),'raw_mae_gray':float(raw.mean()*255),'model_mae_gray':float(err.mean()*255),'improved_fraction':float(np.mean(err.reshape(len(src),-1).mean(1)<raw.reshape(len(src),-1).mean(1))),'raw_edge_mae_gray':float((raw*weight).sum()/weight.sum()*255),'model_edge_mae_gray':float((err*weight).sum()/weight.sum()*255),'output_change_gray':float(np.abs(out-src).mean()*255),'identity_change_gray':float(np.abs(out[identity]-src[identity]).mean()*255)}


@torch.inference_mode()
def pipeline(models,selectors,x):
 for name in ORDER:
  proposal=expert_proposal(name,models[name],x);alpha=selectors[name](x,proposal);x=(x+alpha*(proposal-x)).clamp(0,1)
 return x


def read_real(path):
 image=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
 if image is None:raise RuntimeError(path)
 return image.astype(np.float32)/255


@torch.inference_mode()
def tiled_pipeline(models,selectors,image,core_size=256,halo=192):
 tensor=torch.from_numpy(image[None,None]).to(DEVICE);h,w=image.shape;padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect');output=torch.zeros_like(tensor)
 for y in range(0,h,core_size):
  for x in range(0,w,core_size):
   ch=min(core_size,h-y);cw=min(core_size,w-x);tile=padded[...,y:y+ch+2*halo,x:x+cw+2*halo];value=pipeline(models,selectors,tile);output[...,y:y+ch,x:x+cw]=value[...,halo:halo+ch,halo:halo+cw]
 return output[0,0].cpu().numpy()


def real_validation(models,selectors,suffix=''):
 rows=[];previews=[]
 for path in core.REAL_IMAGES:
  raw=read_real(path);value=tiled_pipeline(models,selectors,raw);gx=cv2.Sobel(raw,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(raw,cv2.CV_32F,0,1,ksize=3);gm=np.hypot(gx,gy);support=gm>=np.quantile(gm,.9);gx2=cv2.Sobel(value,cv2.CV_32F,1,0,ksize=3);gy2=cv2.Sobel(value,cv2.CV_32F,0,1,ksize=3);rows.append({'image':path.name,'change_gray':float(np.mean(np.abs(value-raw))*255),'edge_gain':float(np.hypot(gx2,gy2)[support].mean()/max(gm[support].mean(),1e-8)),'fine_detail_ratio':float(np.mean(np.abs(value-core.gaussian(value,1)))/max(np.mean(np.abs(raw-core.gaussian(raw,1))),1e-8))});previews.append(np.concatenate([cv2.resize(raw,(480,360),interpolation=cv2.INTER_AREA),cv2.resize(value,(480,360),interpolation=cv2.INTER_AREA)],1))
 frame=pd.DataFrame(rows);frame.to_csv(RESULT/f'real_adopted_pipeline{suffix}.csv',index=False,encoding='utf-8-sig');canvas=np.concatenate(previews,0);cv2.imencode('.png',np.round(np.clip(canvas,0,1)*255).astype(np.uint8))[1].tofile(str(RESULT/f'real_adopted_pipeline{suffix}.png'));return {key:float(frame[key].median()) for key in ('change_gray','edge_gain','fine_detail_ratio')}


@torch.inference_mode()
def tile_parity(models,selectors):
 rng=np.random.default_rng(109050);image=torch.from_numpy(rng.random((1,1,512,512),dtype=np.float32)).to(DEVICE);full=pipeline(models,selectors,image);halo=192;core_size=128;padded=F.pad(image,(halo,halo,halo,halo),mode='reflect');canvas=torch.zeros_like(image)
 for y in range(0,512,core_size):
  for x in range(0,512,core_size):canvas[...,y:y+core_size,x:x+core_size]=pipeline(models,selectors,padded[...,y:y+core_size+2*halo,x:x+core_size+2*halo])[...,halo:halo+core_size,halo:halo+core_size]
 delta=(full-canvas).abs()*255;interior=delta[...,halo:-halo,halo:-halo];mask=torch.zeros_like(delta,dtype=torch.bool)
 for c in (128,256,384):
  if halo<c<512-halo:mask[...,halo:-halo,c-3:c+4]=True;mask[...,c-3:c+4,halo:-halo]=True
 seam=delta[mask];return {'interior_mean_gray':float(interior.mean()),'interior_p99_gray':float(torch.quantile(interior,.99)),'interior_max_gray':float(interior.max()),'seam_mean_gray':float(seam.mean()),'seam_max_gray':float(seam.max())}


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--guarded',action='store_true');args=parser.parse_args();guarded=bool(args.guarded);suffix='_guarded' if guarded else ''
 core.seed_all(109000);splits=core.prepare_specialist_data();keys=['target','edge','mixed_input'];tensors={split:core.to_tensors(data,keys) for split,data in splits.items()};models=load_models();selectors={};traces={};current={split:tensors[split]['mixed_input'].clone() for split in splits};original={split:value.clone() for split,value in current.items()};stage_results={}
 for name in ORDER:
  selector,trace=train_one(name,models[name],current['train'],tensors['train']['target'],tensors['train']['edge'],tensors['train']['role'],600,guarded);selectors[name]=selector;traces[name]=trace;stage_results[name]={}
  for split in splits:
   before=current[split].clone();after,alpha=apply_stage(name,models[name],selector,before);current[split]=after;stage_results[name][split]=stage_metrics(before,after,tensors[split]['target'],alpha,tensors[split]['role'])
 summary={'status':'complete','device':str(DEVICE),'guarded_clear_counterfactual':guarded,'order':ORDER,'stage_results':stage_results,'final':{split:final_metrics(original[split],current[split],tensors[split]['target'],tensors[split]['edge'],tensors[split]['role']) for split in splits},'real':real_validation(models,selectors,suffix),'tile':tile_parity(models,selectors),'traces':traces};(RESULT/f'adoption{suffix}_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
