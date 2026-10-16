"""Check the consolidated Markdown against the saved experiment outputs."""
from __future__ import annotations
import json,re,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];REPORT=ROOT/'reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md';text=REPORT.read_text(encoding='utf-8');errors=[]
def require(condition,message):
 if not condition:errors.append(message)
def has(value,precision=6):return f'{value:.{precision}f}' in text
audit=json.loads((ROOT/'results/final_audit.json').read_text(encoding='utf-8'));require(audit['passed'] and (audit['images'],audit['circles'],audit['scans'])==(930,8370,30),'final audit or counts')
model=json.loads((ROOT/'config/model.json').read_text(encoding='utf-8'));require(model['psf_count']==25 and model['inference_core']==512 and model['inference_halo']==24,'model configuration')
pre=json.loads((ROOT/'results/preflight.json').read_text(encoding='utf-8'));require(pre['frozen_parameters']==1194406 and pre['trainable_parameters']==12699,'parameter counts')
parent='R148v2-HybridContextNativePSF';current='R152-R148v2-SafeAdaptivePSF';comp=ROOT/'results/comparison'
for filename,columns in (
 ('displacement_summary.csv',('mae_nm','bias_nm','repeatability_nm','maximum_error_nm')),
 ('shape_size_summary.csv',('diameter_mean_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm','diameter_repeat_absmax_nm')),
 ('SEM_corrected_size_summary.csv',('mean_absolute_pillar_difference_nm',)),
):
 table=pd.read_csv(comp/filename)
 for name in (parent,current):
  for _,row in table[table.model==name].iterrows():
   for column in columns:require(has(float(row[column])) or has(float(row[column]),3),f'{filename}:{name}:{column}')
done=json.loads((ROOT/'runs/formal_8192/training_complete.json').read_text(encoding='utf-8'));require(done['updates']==8192 and done['deployment_scale']==1.0,'training/deployment')
require(done['deployed_checkpoint']['sha256'] in text,'deployed checkpoint hash')
require(model['base_checkpoint_sha256'] in text,'base checkpoint hash')
runtime=json.loads((ROOT/'results/matched_runtime.json').read_text(encoding='utf-8'));require(has(runtime['median_of_frame_medians']['R148v2'],4) and has(runtime['median_of_frame_medians']['R152'],4),'matched timing')
parity=json.loads((ROOT/'results/final_tile_parity.json').read_text(encoding='utf-8'));require(max(x['max_gray'] for x in parity['frames'])<0.000076,'tile parity')
links=re.findall(r'\]\(([^)]+)\)',text);missing=[]
for link in links:
 if link.startswith(('http:','https:','#')):continue
 target=(REPORT.parent/link).resolve()
 if not target.exists():missing.append(link)
require(not missing,'missing links '+repr(missing))
result=dict(status='passed' if not errors else 'failed',checked_links=len(links),errors=errors,report=str(REPORT));print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(1 if errors else 0)
