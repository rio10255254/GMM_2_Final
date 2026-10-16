"""CPU-only frozen-checkpoint audit of stages, context and PSF-conditioning choices."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1]
import sys;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from dataset import Bank
from losses import stage_terms,robust_gray
from model import Model
from utils import load,save,sha,model_config,train_config
from verify_package import verify_source_lock
OUT=ROOT/'results/training_deep_dive';OUT.mkdir(parents=True,exist_ok=True)
def rms_gray(x,lo=144,hi=240):return float(x[...,lo:hi,lo:hi].double().square().mean().sqrt()*255)
def term_score(t,cfg):return float(t['image']+cfg['loss']['gradient']*t['gradient']+cfg['loss']['pair_output']*t['pair_output']+cfg['loss']['boundary']*t['boundary'])
def forward_mode(model,b,mode,original_gain):
 model.context_enabled=mode!='context_off';model.cfg['optical_feature_gain']=0 if mode=='cue_off' else original_gain;indices=b['actual_psf_indices'] if mode=='actual_psf' else b['operator_psf_indices']
 with torch.inference_mode():out,states=model(b['source'],indices,True)
 return out,states
def main():
 verify_source_lock();torch.set_num_threads(4);cfg=train_config();mc=model_config();latest=load(ROOT/'runs/formal_8192/latest.json');path=Path(latest['path']);assert sha(path)==latest['sha256'];cp=torch.load(path,map_location='cpu',weights_only=False);model=Model(mc,ROOT).eval();model.load_state_dict(cp['model'],strict=True);bank=Bank(cfg);categories={}
 for e in bank.manifest['entries']:
  if e['split']=='dev':categories.setdefault(e['category'],[]).append(e['index'])
 selected=[i for c in sorted(categories) for i in categories[c][:2]];stage_rows=[];ablation_rows=[];original_gain=mc['optical_feature_gain']
 for index in selected:
  b=bank.batch('dev',index,'cpu');category=b['category'];model.context_enabled=True;model.cfg['optical_feature_gain']=original_gain
  with torch.inference_mode():
   fixed,cue,context=model.prepare(b['source'],b['operator_psf_indices']);original,states=model(b['source'],b['operator_psf_indices'],True)
  previous=b['source'];base=stage_terms(b['source'],b)
  stage_rows.append(dict(index=index,category=category,stage=0,image=float(base['image']),gradient=float(base['gradient']),pair_output=float(base['pair_output']),boundary=float(base['boundary']),combined_score=term_score(base,cfg),increment_RMS_gray=0,total_residual_RMS_gray=0,zero_fraction=float((b['source']<=0).float().mean()),one_fraction=float((b['source']>=1).float().mean())))
  for stage,state in enumerate(states,1):
   t=stage_terms(state,b);stage_rows.append(dict(index=index,category=category,stage=stage,image=float(t['image']),gradient=float(t['gradient']),pair_output=float(t['pair_output']),boundary=float(t['boundary']),combined_score=term_score(t,cfg),increment_RMS_gray=rms_gray(state-previous),total_residual_RMS_gray=rms_gray(state-b['source']),zero_fraction=float((state<=1e-7).float().mean()),one_fraction=float((state>=1-1e-7).float().mean())));previous=state
  original_terms=stage_terms(original,b);base_score=term_score(original_terms,cfg)
  for mode in ('context_off','cue_off','actual_psf'):
   alt,_=forward_mode(model,b,mode,original_gain);t=stage_terms(alt,b);ablation_rows.append(dict(index=index,category=category,mode=mode,baseline_score=base_score,mode_score=term_score(t,cfg),score_change=float(term_score(t,cfg)-base_score),output_RMS_difference_gray=rms_gray(alt-original),image_change=float(t['image']-original_terms['image']),gradient_change=float(t['gradient']-original_terms['gradient']),pair_change=float(t['pair_output']-original_terms['pair_output']),boundary_change=float(t['boundary']-original_terms['boundary'])))
  ablation_rows.append(dict(index=index,category=category,mode='signals',baseline_score=base_score,mode_score=base_score,score_change=0,output_RMS_difference_gray=0,image_change=0,gradient_change=0,pair_change=0,boundary_change=0,cue_RMS_gray=rms_gray(original_gain*cue),context_RMS=float((mc['context_gain']*context[...,144:240,144:240]).double().square().mean().sqrt())))
  print('AUDIT',index,category,flush=True)
 model.context_enabled=True;model.cfg['optical_feature_gain']=original_gain
 stages=pd.DataFrame(stage_rows);abl=pd.DataFrame(ablation_rows);stages.to_csv(OUT/'frozen_stage_audit.csv',index=False);abl.to_csv(OUT/'frozen_ablation_audit.csv',index=False)
 params=[]
 for group,module in [('context',model.context),*[(f'stage_{i+1}',m) for i,m in enumerate(model.stages)]]:
  values=torch.cat([p.detach().flatten().double() for p in module.parameters()]);heads=torch.cat([p.detach().flatten().double() for n,p in module.named_parameters() if n.startswith('head.')]);params.append(dict(group=group,parameters=values.numel(),L2=float(values.norm()),mean_abs=float(values.abs().mean()),head_L2=float(heads.norm()),head_mean_abs=float(heads.abs().mean())))
 pd.DataFrame(params).to_csv(OUT/'parameter_norms.csv',index=False)
 summary=[]
 for stage,g in stages.groupby('stage'):
  g=g.sort_values('index');previous=None if stage==0 else stages[stages.stage==stage-1].sort_values('index')
  summary.append(dict(stage=int(stage),samples=len(g),combined_score=float(g.combined_score.mean()),image=float(g.image.mean()),gradient=float(g.gradient.mean()),pair_output=float(g.pair_output.mean()),boundary=float(g.boundary.mean()),increment_RMS_gray=float(g.increment_RMS_gray.mean()),total_residual_RMS_gray=float(g.total_residual_RMS_gray.mean()),improved_vs_previous=None if stage==0 else int(sum(g.combined_score.to_numpy()<previous.combined_score.to_numpy()))))
 ab_summary=[]
 for mode,g in abl[abl['mode']!='signals'].groupby('mode'):ab_summary.append(dict(mode=mode,samples=len(g),mean_score_change=float(g.score_change.mean()),median_score_change=float(g.score_change.median()),improved_samples=int((g.score_change<0).sum()),worsened_samples=int((g.score_change>0).sum()),mean_output_RMS_difference_gray=float(g.output_RMS_difference_gray.mean()),max_output_RMS_difference_gray=float(g.output_RMS_difference_gray.max())))
 signals=abl[abl['mode']=='signals'];etas=(mc['eta_max']*torch.sigmoid(model.step_logits)).detach().tolist();result=dict(snapshot_utc=datetime.now(timezone.utc).isoformat(),checkpoint_step=latest['step'],checkpoint_sha256=latest['sha256'],selected_dev_indices=selected,selected_categories={c:sum(stages[(stages.category==c)&(stages.stage==0)].shape[0] for _ in [0]) for c in sorted(categories)},stage_summary=summary,ablation_summary=ab_summary,mean_cue_RMS_gray=float(signals.cue_RMS_gray.mean()),mean_context_scaled_RMS=float(signals.context_RMS.mean()),step_strengths=etas,parameter_groups=params,scope='Frozen CPU audit on two deterministic dev parents per category; ablations are post-training switches, not matched retraining.')
 save(OUT/'frozen_checkpoint_audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
