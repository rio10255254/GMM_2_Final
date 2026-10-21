"""Calibrate only the denoise adoption map with light clear-texture guards."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'results';WEIGHTS=ROOT/'weights';DEVICE=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
spec=importlib.util.spec_from_file_location('adoption_core',ROOT/'scripts/train_adoptions.py')
if spec is None or spec.loader is None:raise RuntimeError('Cannot load adoption core')
adopt=importlib.util.module_from_spec(spec);sys.modules[spec.name]=adopt;spec.loader.exec_module(adopt)
BASE_LAMBDAS=[.01,.03,.08]
EXTENDED_LAMBDAS=[.12,.18,.25]


def load_selector(name):
 model=adopt.AdoptionNet().to(DEVICE);model.load_state_dict(torch.load(WEIGHTS/f'adoption_{name}.pth',map_location=DEVICE,weights_only=False)['model']);return model.eval()


def calibrate(initial,expert,current,target,role,guard_weight,steps=300):
 model=copy.deepcopy(initial).train();reference=copy.deepcopy(initial).eval()
 for parameter in reference.parameters():parameter.requires_grad_(False)
 optimizer=torch.optim.AdamW(model.parameters(),lr=5e-5,weight_decay=1e-5);generator=torch.Generator(device=DEVICE).manual_seed(109100+int(guard_weight*1000));trace=[];batch=18
 for step in range(1,steps+1):
  index=torch.randint(0,len(current),(batch,),device=DEVICE,generator=generator);source=current[index];truth=target[index]
  with torch.no_grad():proposal=adopt.expert_proposal('denoise',expert,source);alpha_target=adopt.oracle_alpha(source,truth,proposal);reference_alpha=reference(source,proposal)
  alpha=model(source,proposal);mixed_loss=adopt.balanced_alpha_loss(alpha,alpha_target);preserve=F.smooth_l1_loss(alpha,reference_alpha,beta=.05)
  clear_index=torch.randint(0,len(target),(batch,),device=DEVICE,generator=generator);clear=target[clear_index]
  with torch.no_grad():clear_proposal=adopt.expert_proposal('denoise',expert,clear)
  clear_alpha=model(clear,clear_proposal);clear_loss=F.smooth_l1_loss(clear_alpha,torch.zeros_like(clear_alpha),beta=.05);loss=mixed_loss+guard_weight*clear_loss+.03*preserve
  optimizer.zero_grad(set_to_none=True);loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
  if not torch.isfinite(loss) or not torch.isfinite(norm):raise FloatingPointError(f'calibration {guard_weight} step {step}')
  if step==1 or step%100==0:
   identity=role[index]==adopt.core.ROLES.index('identity');row={'step':step,'loss':float(loss.detach()),'mixed_alpha':float(alpha.mean().detach()),'target_alpha':float(alpha_target.mean().detach()),'mixed_identity_alpha':float(alpha[identity].mean().detach()) if bool(identity.any()) else 0.0,'clear_alpha':float(clear_alpha.mean().detach())};trace.append(row);print(json.dumps({'guard_weight':guard_weight,**row}),flush=True)
 model.eval();torch.save({'model':model.state_dict(),'guard_weight':guard_weight,'steps':steps,'source':'adoption_denoise.pth'},WEIGHTS/f'adoption_denoise_calibrated_{guard_weight:.2f}.pth');return model,trace


def evaluate_pipeline(models,selectors,splits,tensors):
 current={split:tensors[split]['mixed_input'].clone() for split in splits};original={split:value.clone() for split,value in current.items()};stage={}
 for name in adopt.ORDER:
  stage[name]={}
  for split in splits:
   before=current[split].clone();after,alpha=adopt.apply_stage(name,models[name],selectors[name],before);current[split]=after;stage[name][split]=adopt.stage_metrics(before,after,tensors[split]['target'],alpha,tensors[split]['role'])
 final={split:adopt.final_metrics(original[split],current[split],tensors[split]['target'],tensors[split]['edge'],tensors[split]['role']) for split in splits}
 return stage,final


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--extended',action='store_true');args=parser.parse_args();lambdas=EXTENDED_LAMBDAS if args.extended else BASE_LAMBDAS;suffix='_extended' if args.extended else ''
 failure={'status':'stopped','experiment':'guarded_weight_0.65','last_completed_specialist':'denoise','radiometry_last_observed_step':100,'reason':'All adoption values collapsed near zero under an over-strong clear counterfactual penalty; run stopped before edge/texture stages.','weights_reusable':False};(RESULT/'guarded_overweight_failure.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
 splits=adopt.core.prepare_specialist_data();keys=['target','edge','mixed_input'];tensors={split:adopt.core.to_tensors(data,keys) for split,data in splits.items()};models=adopt.load_models();base_selectors={name:load_selector(name) for name in adopt.ORDER};rows={}
 for weight in lambdas:
  calibrated,trace=calibrate(base_selectors['denoise'],models['denoise'],tensors['train']['mixed_input'],tensors['train']['target'],tensors['train']['role'],weight,300);selectors={**base_selectors,'denoise':calibrated};stage,final=evaluate_pipeline(models,selectors,splits,tensors);real=adopt.real_validation(models,selectors,f'_calibrated_{weight:.2f}');tile=adopt.tile_parity(models,selectors);rows[f'{weight:.2f}']={'guard_weight':weight,'trace':trace,'stage_results':stage,'final':final,'real':real,'tile':tile}
 summary={'status':'complete','source_selector':'adoption_denoise.pth','frozen_other_selectors':True,'frozen_specialists':True,'extended':bool(args.extended),'arms':rows}
 (RESULT/f'denoise_calibration{suffix}_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
