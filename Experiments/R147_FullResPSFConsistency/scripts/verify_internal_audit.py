"""Verify diagnostic coverage and rederive stage PI arithmetic independently."""
from pathlib import Path
import sys,re
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from utils import load,save,sha
from verify_package import verify_source_lock
from evaluation_lock import verify as verify_evaluation
def main():
 out=ROOT/'results/internal_audit';verify_source_lock();verify_evaluation()
 manifest=load(ROOT/'data/manifest.json')
 for e in manifest['entries']:
  assert sha(ROOT/'data'/e['arrays'])==e['arrays_sha256'];assert sha(ROOT/'data'/e['metadata'])==e['metadata_sha256']
 d=pd.read_csv(out/'trace_circles.csv');u=pd.read_csv(out/'trace_updates.csv');assert len(d)==4320 and len(u)==120;assert len(d.frame.unique())==30
 assert load(out/'trace_complete.json')['max_saved_output_difference']==0
 for model in ('r147','r146','r140'):
  for kind,count in [('crops',270),('shifts',378),('nuisance',378)]:
   x=pd.read_csv(out/f'{kind}_{model}.csv');assert len(x)==count;assert len(x.frame.unique())==6;assert np.isfinite(x.select_dtypes('number')).all().all()
   rec=load(out/f'{kind}_{model}_complete.json')
   source='audit_nuisance.py' if kind=='nuisance' else 'audit_internal.py';assert rec.get('source_script_sha256',rec.get('script_sha256'))==sha(ROOT/'scripts'/source)
  assert load(out/f'nuisance_{model}_complete.json')['baseline_full_output_max_error']<1e-6
 full=d[(d['mode']=='full')&(d.iteration==4)];maxcenter=0
 for run,g in full.groupby('run'):
  old=pd.read_csv(ROOT/'results/centers'/f'{run}.csv')
  for idx,h in g.groupby('index'):
   source=old[old['index']==idx].sort_values('pillar_id')[['center_x_px','center_y_px','radius_px']].to_numpy();new=h.sort_values('pillar')[['cx','cy','radius']].to_numpy();maxcenter=max(maxcenter,float(np.abs(source-new).max()))
 assert maxcenter<1e-7
 plan=load(ROOT/'evaluation/capture_plan.json');axis=load(ROOT/'evaluation/calibration.json')['axis_unit_vector'];steps=pd.read_csv(out/'stage_displacements.csv');maxstep=0
 for v in steps.itertuples():
  x=d[(d['mode']==v.mode)&(d.iteration==v.iteration)&(d.run==v.run)];left=x[x['index']==v.i].sort_values('pillar');right=x[x['index']==v.j].sort_values('pillar');dx=np.median(right.cx.to_numpy()-left.cx.to_numpy());dy=np.median(right.cy.to_numpy()-left.cy.to_numpy());f0=plan['frames'][int(left.frame.iloc[0])];f1=plan['frames'][int(right.frame.iloc[0])];expect=(dx*axis[0]+dy*axis[1])*172.5-(f1['pi_y_um']-f0['pi_y_um'])*1000;maxstep=max(maxstep,abs(expect-v.error_nm))
 assert maxstep<1e-8
 assert len(pd.read_csv(out/'gradient_terms.csv'))==14;assert load(out/'data_contract_complete.json')['metadata_verified']==768
 assert len(pd.read_csv(out/'r137_grid.csv'))==108;assert load(out/'r137_grid_complete.json')['baseline_full_output_max_error']<1e-6
 assert len(pd.read_csv(out/'activation.csv'))==24;assert load(out/'activation_complete.json')['maximum_saturated_fraction']==0
 for name in ('R147_INTERNAL_AUDIT.md','R147_OPTIMIZATION_PLAN.md'):
  p=ROOT/'reports'/name
  for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
   if target.startswith('https://'):continue
   assert (p.parent/target).is_file(),(name,target)
 save(out/'verification.json',dict(passed=True,original_source_lock_unchanged=True,original_evaluation_lock_unchanged=True,all768_array_and_metadata_hashes_unchanged=True,trace_circle_rows=4320,trace_update_rows=120,shift_rows=1134,crop_rows=810,nuisance_rows=1134,final_stage_existing_center_max_difference_px=maxcenter,independent_stage_displacement_max_difference_nm=maxstep,no_retraining_or_new_candidate_selection=True))
 print('INTERNAL_AUDIT_VERIFIED',maxcenter,maxstep)
if __name__=='__main__':main()
