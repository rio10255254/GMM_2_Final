"""Train and falsify four independently supervised optical specialists."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn


ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';RESULT=ROOT/'results';WEIGHTS=ROOT/'weights';REPORT=ROOT/'reports/R108C_RESULTS_ZH.md'
for folder in (DATA,RESULT,WEIGHTS,REPORT.parent):folder.mkdir(parents=True,exist_ok=True)
BASE_ROOT=Path(r'D:\GMM_2_Final\Experiments\R108B_StagedParallelOpticalExpertsMicroprobe')
BASE_DATA=BASE_ROOT/'data/microprobe_data.npz'
EXPECTED_BASE_SHA='e01a97bc2b361195d550a6f3c5262e354b2424f8676ae9045c6abed765d39185'
DEVICE=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
ROLES=['edge','texture','denoise','illumination','identity','mixed']
REAL_IMAGES=[
 Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\5x_dense_raw.bmp'),
 Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\20x_mixed_raw.bmp'),
 Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\50x_array_raw.bmp'),
 Path(r'D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\pillar_center9_50x_raw.bmp')]


def seed_all(seed:int):random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
def sha256(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as handle:
  for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
 return h.hexdigest()


spec=importlib.util.spec_from_file_location('r108b_data',BASE_ROOT/'scripts/run_microprobe.py')
if spec is None or spec.loader is None:raise RuntimeError('Cannot load verified R108B data helpers')
base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;spec.loader.exec_module(base)


def read_base()->dict[str,dict[str,np.ndarray]]:
 if not BASE_DATA.exists() or sha256(BASE_DATA)!=EXPECTED_BASE_SHA:raise RuntimeError('R108B base data hash mismatch')
 loaded=np.load(BASE_DATA,allow_pickle=False);splits={}
 for split in ('train','validation','holdout'):
  splits[split]={key:loaded[f'{split}_{key}'] for key in ('source1','target','mask','edge','midpoint','polarity','role','family')}
 return splits


def low_field(rng:np.random.Generator,side:int)->np.ndarray:return base.low_field(rng,side).astype(np.float32)
def gaussian(image:np.ndarray,sigma:float)->np.ndarray:return cv2.GaussianBlur(image,(0,0),sigma,borderType=cv2.BORDER_REFLECT_101) if sigma>0 else image.copy()


def prepare_specialist_data()->dict[str,dict[str,np.ndarray]]:
 path=DATA/'specialist_data.npz'
 expected_keys=('target','mask','edge','role','family','mixed_input','edge_input','texture_input','denoise_base','denoise_input1','denoise_input2','radiometry_base','radiometry_input')
 if path.exists():
  loaded=np.load(path,allow_pickle=False)
  if all(f'{split}_{key}' in loaded.files for split in ('train','validation','holdout') for key in expected_keys):return {split:{key:loaded[f'{split}_{key}'] for key in expected_keys} for split in ('train','validation','holdout')}
  loaded.close()
 base_splits=read_base();result={};payload={}
 for split_index,(split,data) in enumerate(base_splits.items()):
  rng=np.random.default_rng(108900+split_index);severe=split=='holdout';rows={key:[] for key in ('edge_input','texture_input','denoise_base','denoise_input1','denoise_input2','radiometry_base','radiometry_input')}
  targets=data['target'].astype(np.float32)/255
  for target in targets:
   # Edge isolation: blur/asymmetry only, no random sensor noise or illumination.
   sigma=float(rng.uniform(.7,3.0 if not severe else 4.0));edge_input=gaussian(target,sigma)
   if severe and rng.random()<.55:
    shifted=cv2.warpAffine(edge_input,np.asarray([[1,0,float(rng.uniform(-1.5,1.5))],[0,1,float(rng.uniform(-1.5,1.5))]],np.float32),(target.shape[1],target.shape[0]),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT_101);mix=float(rng.uniform(.03,.14));edge_input=(1-mix)*edge_input+mix*shifted
   # Texture isolation uses the same latent phase and only optical blur.
   texture_input=gaussian(target,float(rng.uniform(.7,2.3 if not severe else 3.2)))
   # Denoising target is the noise-free optical observation, not the sharp target.
   denoise_base=gaussian(target,float(rng.uniform(0,.8)));noise=float(rng.uniform(.006,.028 if not severe else .045));row1=rng.normal(0,noise*.18,(target.shape[0],1));row2=rng.normal(0,noise*.18,(target.shape[0],1));denoise1=np.clip(denoise_base+rng.normal(0,noise,target.shape)+row1,0,1);denoise2=np.clip(denoise_base+rng.normal(0,noise,target.shape)+row2,0,1)
   # Radiometry isolation adds only a zero-centered broad field.
   radiometry_base=gaussian(target,float(rng.uniform(0,.45)));amplitude=float(rng.uniform(.035,.15 if not severe else .24));radiometry_input=np.clip(radiometry_base+amplitude*low_field(rng,target.shape[0]),0,1)
   for key,value in [('edge_input',edge_input),('texture_input',texture_input),('denoise_base',denoise_base),('denoise_input1',denoise1),('denoise_input2',denoise2),('radiometry_base',radiometry_base),('radiometry_input',radiometry_input)]:rows[key].append(np.round(np.clip(value,0,1)*255).astype(np.uint8))
  output={key:data[key] for key in ('target','mask','edge','role','family')};output['mixed_input']=data['source1'];output.update({key:np.stack(value) for key,value in rows.items()});result[split]=output
  for key,value in output.items():payload[f'{split}_{key}']=value
 np.savez_compressed(path,**payload);manifest={'status':'complete','source':str(BASE_DATA),'source_sha256':EXPECTED_BASE_SHA,'counts':{k:len(v['target']) for k,v in result.items()},'specialists':['edge','texture','denoise','radiometry'],'real_training_pixels':False,'old_weights_or_teacher':False,'sha256':sha256(path)};(DATA/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');return result


class Blur(nn.Module):
 def __init__(self,sigma:float):
  super().__init__();radius=max(1,int(math.ceil(3*sigma)));axis=torch.arange(-radius,radius+1,dtype=torch.float32);row=torch.exp(-.5*(axis/sigma)**2);row/=row.sum();self.register_buffer('h',row.view(1,1,1,-1));self.register_buffer('v',row.view(1,1,-1,1));self.radius=radius
 def forward(self,x):
  mode='reflect' if min(x.shape[-2:])>self.radius else 'replicate';value=F.conv2d(F.pad(x,(self.radius,self.radius,0,0),mode=mode),self.h.to(x.dtype));return F.conv2d(F.pad(value,(0,0,self.radius,self.radius),mode=mode),self.v.to(x.dtype))


class Res(nn.Module):
 def __init__(self,c,d=1):super().__init__();self.a=nn.Conv2d(c,c,3,padding=d,dilation=d);self.b=nn.Conv2d(c,c,3,padding=d,dilation=d)
 def forward(self,x):return F.silu(x+.15*self.b(F.silu(self.a(x))))


class LocalTower(nn.Module):
 def __init__(self,cues:int,channels:int=32):super().__init__();self.net=nn.Sequential(nn.Conv2d(cues,channels,3,padding=1),nn.SiLU(),Res(channels),Res(channels,2),Res(channels,4),Res(channels,2),Res(channels))
 def forward(self,x):return self.net(x)


def gradients(x):return F.pad(x[:,:,:,1:]-x[:,:,:,:-1],(0,1,0,0)),F.pad(x[:,:,1:,:]-x[:,:,:-1,:],(0,0,0,1))


class EdgeExpert(nn.Module):
 def __init__(self):
  super().__init__();self.b08=Blur(.8);self.b16=Blur(1.6);self.b32=Blur(3.2);self.tower=LocalTower(7);self.head=nn.Conv2d(32,1,1);nn.init.zeros_(self.head.weight);nn.init.constant_(self.head.bias,math.log(.8/(4-.8)))
 def basis(self,x):
  b08,b16,b32=self.b08(x),self.b16(x),self.b32(x);gx,gy=gradients(x);mag=torch.sqrt(gx.square()+gy.square()+1e-8);scale=torch.sqrt(self.b32((x-b32).square())+(2/255)**2);support=((mag/(scale+2/255)-.20)/1.1).clamp(0,1);basis=support*(x-b16);cues=torch.cat([x,b08,b16,b32,x-b16,mag,support],1);return basis,support,cues
 def forward(self,x):
  basis,support,cues=self.basis(x);coefficient=4*torch.sigmoid(self.head(self.tower(cues)));delta=coefficient*basis;return (x+delta).clamp(0,1),coefficient,delta,support,basis


class TextureExpert(nn.Module):
 def __init__(self):
  super().__init__();self.b06=Blur(.6);self.b14=Blur(1.4);self.b28=Blur(2.8);self.tower=LocalTower(7);self.head=nn.Conv2d(32,1,1);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
 def support(self,x):
  b06,b14,b28=self.b06(x),self.b14(x),self.b28(x);gx,gy=gradients(x);mag=torch.sqrt(gx.square()+gy.square()+1e-8);scale=torch.sqrt(self.b28((x-b28).square())+(2/255)**2);edge=((mag/(scale+2/255)-.20)/1.1).clamp(0,1);support=(1-.85*edge).clamp(0,1);cues=torch.cat([x,b06,b14,b28,b06-b14,b14-b28,support],1);return support,cues
 def highpass(self,x):return x-self.b14(x)
 def forward(self,x):
  support,cues=self.support(x);raw=.12*torch.tanh(self.head(self.tower(cues)));delta=support*(raw-self.b14(raw));return (x+delta).clamp(0,1),delta,support


class DenoiseExpert(nn.Module):
 def __init__(self):super().__init__();self.b14=Blur(1.4);self.b28=Blur(2.8);self.tower=LocalTower(5);self.head=nn.Conv2d(32,1,1);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
 def forward(self,x):
  b14,b28=self.b14(x),self.b28(x);features=torch.cat([x,b14,b28,x-b14,b14-b28],1);raw=.15*torch.tanh(self.head(self.tower(features)));delta=raw-self.b28(raw);return (x+delta).clamp(0,1),delta


class RadiometryExpert(nn.Module):
 def __init__(self):super().__init__();self.b4=Blur(4);self.b8=Blur(8);self.tower=LocalTower(4,28);self.head=nn.Conv2d(28,1,1);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
 def forward(self,x):
  b4,b8=self.b4(x),self.b8(x);features=torch.cat([x,b4,b8,x-b8],1);raw=.28*torch.tanh(self.head(self.tower(features)));delta=self.b8(raw);return (x+delta).clamp(0,1),delta


def to_tensors(data:dict[str,np.ndarray],keys:list[str])->dict[str,torch.Tensor]:
 out={}
 for key in keys:out[key]=torch.from_numpy(data[key].astype(np.float32)/255).unsqueeze(1).to(DEVICE)
 out['role']=torch.from_numpy(data['role']).to(DEVICE);return out


def local_oracle_coefficient(basis,desired,edge):
 num=F.avg_pool2d(basis*desired,9,1,4);den=F.avg_pool2d(basis.square(),9,1,4)+1e-8;return (num/den).clamp(0,4)*edge


def train_edge(data,steps=800):
 seed_all(108910);model=EdgeExpert().to(DEVICE);opt=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=1e-5);gen=torch.Generator(device=DEVICE).manual_seed(108911);trace=[];batch=18
 for step in range(1,steps+1):
  idx=torch.randint(0,len(data['edge_input']),(batch,),device=DEVICE,generator=gen);source,target,edge=data['edge_input'][idx],data['target'][idx],data['edge'][idx];output,coeff,delta,support,basis=model(source)
  with torch.no_grad():target_coeff=local_oracle_coefficient(basis,target-source,edge)
  positive=edge>.03;coeff_pos=torch.abs(coeff[positive]-target_coeff[positive]).mean();coeff_neg=torch.abs(coeff[~positive]).mean();image=(torch.abs(output-target)*(.15+.85*edge)).sum()/(.15+.85*edge).sum();loss=coeff_pos+.20*coeff_neg+.12*image
  opt.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
  if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f'edge {step}')
  if step==1 or step%100==0:
   row={'step':step,'loss':float(loss.detach()),'pred_coeff':float(coeff[positive].mean().detach()),'target_coeff':float(target_coeff[positive].mean().detach()),'delta_gray':float(delta.abs().mean().detach()*255)};trace.append(row);print(json.dumps({'specialist':'edge',**row}),flush=True)
 torch.save({'model':model.state_dict(),'steps':steps},WEIGHTS/'edge.pth');return model.eval(),trace


def train_texture(data,steps=800):
 seed_all(108920);model=TextureExpert().to(DEVICE);opt=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=1e-5);gen=torch.Generator(device=DEVICE).manual_seed(108921);trace=[];batch=18;texture_role=torch.tensor([ROLES.index('texture'),ROLES.index('mixed')],device=DEVICE)
 for step in range(1,steps+1):
  idx=torch.randint(0,len(data['texture_input']),(batch,),device=DEVICE,generator=gen);source,target,edge,role=data['texture_input'][idx],data['target'][idx],data['edge'][idx],data['role'][idx];output,delta,support=model(source);active=(role[:,None,None,None]==texture_role[0])|(role[:,None,None,None]==texture_role[1]);truth_support=(1-.9*edge).clamp(0,1)*active;target_delta=truth_support*(model.highpass(target)-model.highpass(source));positive=truth_support>.05;direct=torch.abs(delta[positive]-target_delta[positive]).mean() if bool(positive.any()) else delta.abs().mean();negative=torch.abs(delta[~positive]).mean();image=(torch.abs(output-target)*(.1+.9*truth_support)).sum()/(.1+.9*truth_support).sum();loss=direct+.25*negative+.12*image
  opt.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
  if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f'texture {step}')
  if step==1 or step%100==0:
   row={'step':step,'loss':float(loss.detach()),'delta_gray':float(delta.abs().mean().detach()*255),'target_delta_gray':float(target_delta.abs().mean().detach()*255)};trace.append(row);print(json.dumps({'specialist':'texture',**row}),flush=True)
 torch.save({'model':model.state_dict(),'steps':steps},WEIGHTS/'texture.pth');return model.eval(),trace


def train_denoise(data,steps=700):
 seed_all(108930);model=DenoiseExpert().to(DEVICE);opt=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=1e-5);gen=torch.Generator(device=DEVICE).manual_seed(108931);trace=[];batch=18
 for step in range(1,steps+1):
  idx=torch.randint(0,len(data['denoise_input1']),(batch,),device=DEVICE,generator=gen);source,source2,target=data['denoise_input1'][idx],data['denoise_input2'][idx],data['denoise_base'][idx];output,delta=model(source);target_delta=target-source;output2,_=model(source2);direct=F.smooth_l1_loss(delta,target_delta,beta=1/255);image=F.smooth_l1_loss(output,target,beta=1/255);pair=torch.abs(output-output2).mean();low=torch.abs(model.b28(delta)).mean();loss=direct+.35*image+.08*pair+.15*low
  opt.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
  if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f'denoise {step}')
  if step==1 or step%100==0:
   row={'step':step,'loss':float(loss.detach()),'delta_gray':float(delta.abs().mean().detach()*255),'target_delta_gray':float(target_delta.abs().mean().detach()*255)};trace.append(row);print(json.dumps({'specialist':'denoise',**row}),flush=True)
 torch.save({'model':model.state_dict(),'steps':steps},WEIGHTS/'denoise.pth');return model.eval(),trace


def train_radiometry(data,steps=700):
 seed_all(108940);model=RadiometryExpert().to(DEVICE);opt=torch.optim.AdamW(model.parameters(),lr=4e-4,weight_decay=1e-5);gen=torch.Generator(device=DEVICE).manual_seed(108941);trace=[];batch=18
 for step in range(1,steps+1):
  idx=torch.randint(0,len(data['radiometry_input']),(batch,),device=DEVICE,generator=gen);source,target=data['radiometry_input'][idx],data['radiometry_base'][idx];output,delta=model(source);target_delta=target-source;direct=F.smooth_l1_loss(delta,target_delta,beta=1/255);image=F.smooth_l1_loss(output,target,beta=1/255);gx,gy=gradients(output);tx,ty=gradients(target);geometry=F.smooth_l1_loss(gx,tx,beta=1/255)+F.smooth_l1_loss(gy,ty,beta=1/255);loss=direct+.35*image+.08*geometry
  opt.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
  if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f'radiometry {step}')
  if step==1 or step%100==0:
   row={'step':step,'loss':float(loss.detach()),'delta_gray':float(delta.abs().mean().detach()*255),'target_delta_gray':float(target_delta.abs().mean().detach()*255)};trace.append(row);print(json.dumps({'specialist':'radiometry',**row}),flush=True)
 torch.save({'model':model.state_dict(),'steps':steps},WEIGHTS/'radiometry.pth');return model.eval(),trace


@torch.inference_mode()
def evaluate_specialist(name,model,data_np,data_t):
 inputs={'edge':'edge_input','texture':'texture_input','denoise':'denoise_input1','radiometry':'radiometry_input'};targets={'edge':'target','texture':'target','denoise':'denoise_base','radiometry':'radiometry_base'};source=data_t[inputs[name]];target=data_t[targets[name]];outputs=[];actions=[];extras=[]
 for start in range(0,len(source),24):
  if name=='edge':out,coeff,delta,support,basis=model(source[start:start+24]);extras.append(float(coeff.mean().cpu()))
  elif name=='texture':out,delta,support=model(source[start:start+24])
  else:out,delta=model(source[start:start+24])
  outputs.append(out.cpu());actions.append(delta.abs().mean(dim=(1,2,3)).cpu()*255)
 output=torch.cat(outputs).numpy();action=torch.cat(actions).numpy();src=source.cpu().numpy();truth=target.cpu().numpy();raw=np.abs(src-truth);err=np.abs(output-truth);edge=data_np['edge'].astype(np.float32)/255;edge_weight=.15+.85*edge[:,None]
 result={'images':len(src),'raw_mae_gray':float(raw.mean()*255),'model_mae_gray':float(err.mean()*255),'improved_fraction':float(np.mean(err.reshape(len(src),-1).mean(1)<raw.reshape(len(src),-1).mean(1))),'action_mean_gray':float(action.mean()),'action_p10_gray':float(np.quantile(action,.1)),'edge_weighted_raw_mae_gray':float((raw*edge_weight).sum()/edge_weight.sum()*255),'edge_weighted_model_mae_gray':float((err*edge_weight).sum()/edge_weight.sum()*255)}
 if name=='edge':result['coefficient_mean']=float(np.mean(extras))
 if name=='texture':
  roles=data_np['role'];active=np.isin(roles,[ROLES.index('texture'),ROLES.index('mixed')]);result['active_role_action_gray']=float(action[active].mean());result['negative_role_action_gray']=float(action[~active].mean())
  source_image=src[:,0];target_image=truth[:,0];output_image=output[:,0]
  def hp(values):return values-np.stack([gaussian(image,1.4) for image in values])
  source_hp,target_hp,output_hp=hp(source_image),hp(target_image),hp(output_image);band_support=(1-.9*edge)*active[:,None,None];mass=max(float(band_support.sum()),1e-8)
  result['active_band_raw_mae_gray']=float((np.abs(source_hp-target_hp)*band_support).sum()/mass*255);result['active_band_model_mae_gray']=float((np.abs(output_hp-target_hp)*band_support).sum()/mass*255)
  desired=((target_hp-source_hp)*band_support).reshape(len(src),-1);actual=((output_hp-source_hp)*band_support).reshape(len(src),-1);correlations=[]
  for actual_row,desired_row,is_active in zip(actual,desired,active):
   if not is_active:continue
   denominator=float(np.linalg.norm(actual_row)*np.linalg.norm(desired_row));correlations.append(float(np.dot(actual_row,desired_row)/denominator) if denominator>1e-9 else 0.0)
  result['active_band_delta_correlation']=float(np.median(correlations)) if correlations else 0.0
 return result,output[:,0]


def qualified(name:str,result:dict)->tuple[bool,list[str]]:
 reasons=[]
 if name!='texture' and not result['model_mae_gray']<result['raw_mae_gray']:reasons.append('overall_error_not_improved')
 if result['action_mean_gray']<.02:reasons.append('action_collapsed')
 if name=='edge' and not result['edge_weighted_model_mae_gray']<result['edge_weighted_raw_mae_gray']:reasons.append('edge_error_not_improved')
 if name=='texture':
  if result.get('active_role_action_gray',0)<=result.get('negative_role_action_gray',0):reasons.append('texture_role_not_separated')
  if not result.get('active_band_model_mae_gray',float('inf'))<result.get('active_band_raw_mae_gray',0):reasons.append('texture_band_error_not_improved')
  if result.get('active_band_delta_correlation',0)<=0:reasons.append('texture_delta_wrong_phase')
 return not reasons,reasons


@torch.inference_mode()
def compose(models:dict,x):
 x=models['denoise'](x)[0];x=models['radiometry'](x)[0];x=models['edge'](x)[0];x=models['texture'](x)[0];return x


@torch.inference_mode()
def composition_metrics(models,data_np,data_t):
 source=data_t['mixed_input'];target=data_t['target'];rows=[]
 for start in range(0,len(source),16):rows.append(compose(models,source[start:start+16]).cpu())
 output=torch.cat(rows).numpy();src=source.cpu().numpy();truth=target.cpu().numpy();edge=data_np['edge'].astype(np.float32)/255;weight=.15+.85*edge[:,None];raw=np.abs(src-truth);err=np.abs(output-truth);identity=data_np['role']==ROLES.index('identity')
 return {'images':len(src),'raw_mae_gray':float(raw.mean()*255),'model_mae_gray':float(err.mean()*255),'improved_fraction':float(np.mean(err.reshape(len(src),-1).mean(1)<raw.reshape(len(src),-1).mean(1))),'raw_edge_mae_gray':float((raw*weight).sum()/weight.sum()*255),'model_edge_mae_gray':float((err*weight).sum()/weight.sum()*255),'output_change_gray':float(np.abs(output-src).mean()*255),'identity_change_gray':float(np.abs(output[identity]-src[identity]).mean()*255)}


def read_real(path):
 image=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
 if image is None:raise RuntimeError(path)
 return image.astype(np.float32)/255


@torch.inference_mode()
def real_specialist_validation(models):
 rows=[];previews=[]
 for path in REAL_IMAGES:
  raw=read_real(path);tensor=torch.from_numpy(raw[None,None]).to(DEVICE);outputs={}
  for name,model in models.items():
   if name=='edge':outputs[name]=model(tensor)[0][0,0].cpu().numpy()
   elif name=='texture':outputs[name]=model(tensor)[0][0,0].cpu().numpy()
   else:outputs[name]=model(tensor)[0][0,0].cpu().numpy()
  small=[cv2.resize(raw,(320,240),interpolation=cv2.INTER_AREA)]
  gx=cv2.Sobel(raw,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(raw,cv2.CV_32F,0,1,ksize=3);gm=np.hypot(gx,gy);support=gm>=np.quantile(gm,.9);rawfine=np.mean(np.abs(raw-gaussian(raw,1)))
  for name,value in outputs.items():
   gx2=cv2.Sobel(value,cv2.CV_32F,1,0,ksize=3);gy2=cv2.Sobel(value,cv2.CV_32F,0,1,ksize=3);rows.append({'image':path.name,'specialist':name,'change_gray':float(np.mean(np.abs(value-raw))*255),'edge_gain':float(np.hypot(gx2,gy2)[support].mean()/max(gm[support].mean(),1e-8)),'fine_detail_ratio':float(np.mean(np.abs(value-gaussian(value,1)))/max(rawfine,1e-8))});small.append(cv2.resize(value,(320,240),interpolation=cv2.INTER_AREA))
  previews.append(np.concatenate(small,axis=1))
 frame=pd.DataFrame(rows);frame.to_csv(RESULT/'real_specialists.csv',index=False,encoding='utf-8-sig');canvas=np.concatenate(previews,axis=0);cv2.imencode('.png',np.round(np.clip(canvas,0,1)*255).astype(np.uint8))[1].tofile(str(RESULT/'real_specialists.png'));return {name:{'change_gray':float(g.change_gray.median()),'edge_gain':float(g.edge_gain.median()),'fine_detail_ratio':float(g.fine_detail_ratio.median())} for name,g in frame.groupby('specialist')}


@torch.inference_mode()
def real_composition(models):
 rows=[]
 for path in REAL_IMAGES:
  raw=read_real(path);tensor=torch.from_numpy(raw[None,None]).to(DEVICE);value=compose(models,tensor)[0,0].cpu().numpy();gx=cv2.Sobel(raw,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(raw,cv2.CV_32F,0,1,ksize=3);gm=np.hypot(gx,gy);support=gm>=np.quantile(gm,.9);gx2=cv2.Sobel(value,cv2.CV_32F,1,0,ksize=3);gy2=cv2.Sobel(value,cv2.CV_32F,0,1,ksize=3);rows.append({'change_gray':float(np.mean(np.abs(value-raw))*255),'edge_gain':float(np.hypot(gx2,gy2)[support].mean()/max(gm[support].mean(),1e-8)),'fine_detail_ratio':float(np.mean(np.abs(value-gaussian(value,1)))/max(np.mean(np.abs(raw-gaussian(raw,1))),1e-8))})
 return {key:float(np.median([row[key] for row in rows])) for key in ('change_gray','edge_gain','fine_detail_ratio')}


def main():
 seed_all(108900);splits=prepare_specialist_data();keys=['target','edge','mixed_input','edge_input','texture_input','denoise_base','denoise_input1','denoise_input2','radiometry_base','radiometry_input'];train=to_tensors(splits['train'],keys);val=to_tensors(splits['validation'],keys);held=to_tensors(splits['holdout'],keys)
 previous=json.loads((RESULT/'summary.json').read_text(encoding='utf-8')) if (RESULT/'summary.json').exists() else None;completed=all((WEIGHTS/f'{name}.pth').exists() for name in ('edge','texture','denoise','radiometry'))
 if completed:
  edge=EdgeExpert().to(DEVICE);edge.load_state_dict(torch.load(WEIGHTS/'edge.pth',map_location=DEVICE,weights_only=False)['model']);edge.eval();texture=TextureExpert().to(DEVICE);texture.load_state_dict(torch.load(WEIGHTS/'texture.pth',map_location=DEVICE,weights_only=False)['model']);texture.eval();denoise=DenoiseExpert().to(DEVICE);denoise.load_state_dict(torch.load(WEIGHTS/'denoise.pth',map_location=DEVICE,weights_only=False)['model']);denoise.eval();radiometry=RadiometryExpert().to(DEVICE);radiometry.load_state_dict(torch.load(WEIGHTS/'radiometry.pth',map_location=DEVICE,weights_only=False)['model']);radiometry.eval();traces=previous.get('traces',{}) if previous else {}
 else:
  edge,te=train_edge(train);texture,tt=train_texture(train);denoise,td=train_denoise(train);radiometry,tr=train_radiometry(train);traces={'edge':te,'texture':tt,'denoise':td,'radiometry':tr}
 models={'edge':edge,'texture':texture,'denoise':denoise,'radiometry':radiometry};summary={'status':'complete','device':str(DEVICE),'data_manifest':json.loads((DATA/'manifest.json').read_text()),'specialist_checkpoints_reused_for_metric_refinement':completed,'specialists':{},'real':{},'composition':{},'traces':traces}
 for name,model in models.items():
  v,_=evaluate_specialist(name,model,splits['validation'],val);h,_=evaluate_specialist(name,model,splits['holdout'],held);ok,reasons=qualified(name,h);summary['specialists'][name]={'validation':v,'holdout':h,'qualified':ok,'reasons':reasons}
 summary['real']=real_specialist_validation(models);all_ok=all(item['qualified'] for item in summary['specialists'].values());summary['composition']['authorized']=all_ok
 if all_ok:
  summary['composition'].update({'validation':composition_metrics(models,splits['validation'],val),'holdout':composition_metrics(models,splits['holdout'],held),'real':real_composition(models)})
 else:summary['composition']['skipped_reason']='At least one independently supervised specialist failed its isolated held-out test.'
 (RESULT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
