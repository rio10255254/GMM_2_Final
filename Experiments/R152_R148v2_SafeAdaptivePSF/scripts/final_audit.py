"""Independent integrity and row-count audit of R152 full real validation."""
from __future__ import annotations
import json,sys
from pathlib import Path
import numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1];BASE=Path(r'D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF');sys.path.insert(0,str(ROOT))
from utils import load,save,sha,now

MODEL='R152-R148v2-SafeAdaptivePSF';PARENT='R148v2-HybridContextNativePSF'
def main():
 done=load(ROOT/'runs/formal_8192/training_complete.json');rec=done['deployed_checkpoint'];assert done['updates']==8192 and sha(rec['path'])==rec['sha256']
 cp=torch.load(rec['path'],map_location='cpu',weights_only=False);old=torch.load(BASE/'runs/formal_8192/checkpoints/step08192.pth',map_location='cpu',weights_only=False)
 assert all(torch.equal(value,cp['model']['base.'+key]) for key,value in old['model'].items())
 plan=load(ROOT/'evaluation/capture_plan.json');assert len(plan['frames'])==930 and len(plan['runs'])==30
 receipts=[]
 for frame in plan['frames']:
  stem=f"{frame['index']+1:02d}";path=ROOT/'results/reconstruction'/frame['run']/stem;receipt=load(path.with_suffix('.json'))
  assert receipt['checkpoint_sha256']==rec['sha256'] and receipt['source']['sha256']==frame['source']['sha256']
  assert sha(path.with_suffix('.npz'))==receipt['output_sha256']
  assert receipt['deployment_scale']==1.0 and receipt['tiled_inference'] is True
  receipts.append(receipt)
 assert len(receipts)==930
 for run in plan['runs']:
  name=run['run'];csv=ROOT/'results/centers'/(name+'.csv');npz=ROOT/'results/centers'/(name+'.npz');assert len(pd.read_csv(csv))==279
  with np.load(npz,allow_pickle=False) as z:assert z['points'].shape==(31,9,64,2)
 comp=ROOT/'results/comparison';disp=pd.read_csv(comp/'displacement_summary.csv');geo=pd.read_csv(comp/'shape_size_summary.csv');ci=pd.read_csv(comp/'paired_scan_intervals.csv');sem=pd.read_csv(comp/'SEM_comparison.csv');sem_size=pd.read_csv(comp/'SEM_corrected_size_summary.csv');parent_disp=pd.read_csv(BASE/'results/comparison/displacement_summary.csv');parent_geo=pd.read_csv(BASE/'results/comparison/shape_size_summary.csv')
 assert len(pd.read_csv(comp/'all_displacements.csv'))==13*1800
 assert len(pd.read_csv(comp/'all_circles.csv'))==13*8370
 assert len(ci)==60 and len(sem)==26 and len(sem_size)==13
 assert len(disp[disp.model==MODEL])==2 and len(geo[geo.model==MODEL])==1
 for kind in ('adjacent','start'):
  a=disp[(disp.model==PARENT)&(disp.kind==kind)].iloc[0];b=parent_disp[(parent_disp.model==PARENT)&(parent_disp.kind==kind)].iloc[0]
  for key in ('mae_nm','bias_nm','repeatability_nm','maximum_error_nm'):assert abs(a[key]-b[key])<1e-7
 a=geo[geo.model==PARENT].iloc[0];b=parent_geo[parent_geo.model==PARENT].iloc[0]
 for key in ('diameter_mean_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm','diameter_repeat_absmax_nm'):assert abs(a[key]-b[key])<1e-7
 result=dict(passed=True,model=MODEL,checkpoint_sha256=rec['sha256'],parent_checkpoint_sha256=done['base_checkpoint_sha256'],images=len(receipts),circles=8370,scans=30,comparison_models=13,paired_intervals=len(ci),baseline_parity=True,completed_utc=now());save(ROOT/'results/final_audit.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
