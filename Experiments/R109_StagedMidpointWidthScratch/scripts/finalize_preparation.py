"""Seal R109 preparation evidence and source hashes before the formal run."""
from __future__ import annotations
import csv,hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];EXP=ROOT.parent;R108G=EXP/'R108G_MidpointWidthFactorizedProfileMicroprobe'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def external(suite):
 data=pd.read_csv(R108G/f'results/acm/{suite}/results/tables/primary_contour_metrics.csv');group=data.groupby('method');raw=group.get_group('Raw');model=data[data.method!='Raw'];return {'raw_boundary_px':float(raw.mean_boundary_distance_px.median()),'model_boundary_px':float(model.mean_boundary_distance_px.median()),'raw_iou':float(raw.iou.median()),'model_iou':float(model.iou.median()),'families_improved':int(sum(model.groupby('family').mean_boundary_distance_px.median()<raw.groupby('family').mean_boundary_distance_px.median()))}
def main():
 if (ROOT/'runs/active_run.lock').exists():raise RuntimeError('Cannot finalize while a run is active')
 data_state=json.loads((ROOT/'data/PREPARED_STATE.json').read_text(encoding='utf-8'));smoke=json.loads((ROOT/'runs/r109_smoke_detector_renderer/run_state.json').read_text(encoding='utf-8'));peak_history=json.loads((ROOT/'runs/r109_throughput_batch16_peak/training_history.json').read_text(encoding='utf-8'));motion=json.loads((R108G/'results/real_motion/summary.json').read_text(encoding='utf-8'))
 if data_state['status']!='complete' or smoke['status']!='complete' or not motion['all_sequences_pass']:raise RuntimeError('Required evidence incomplete')
 sem=pd.read_csv(R108G/'results/acm/SEM/results/tables/primary_contour_metrics.csv');pillar=sem.groupby(['method','pillar_id'])[['iou','mean_boundary_distance_pitch_pct','area_error_pct','perimeter_error_pct']].median().groupby('method').median();raw_p=pillar.loc['Raw'];model_p=pillar.loc['R108G_midpoint_width']
 state={'status':'ready_for_single_formal_scratch_run','experiment':'R109_StagedMidpointWidthScratch','formal_training_authorized':True,'formal_training_started':False,'scratch_only':True,'weights_inherited':False,'data':data_state,'causal_basis':{'R73':external('R73'),'R74':external('R74'),'SEM_per_pillar':{'raw_boundary_pitch_pct':float(raw_p.mean_boundary_distance_pitch_pct),'model_boundary_pitch_pct':float(model_p.mean_boundary_distance_pitch_pct),'raw_iou':float(raw_p.iou),'model_iou':float(model_p.iou)},'real_motion_all_six_pass':True,'real_motion_frames':301,'real_motion_measurements':6672,'visual_dark_ring':False,'tile_safe':True},'smoke':{'run_id':'r109_smoke_detector_renderer','detector_and_renderer_exercised':True,'checkpoint':'runs/r109_smoke_detector_renderer/weights/epoch_002.pth','checkpoint_sha256':sha(ROOT/'runs/r109_smoke_detector_renderer/weights/epoch_002.pth'),'finite':True},'throughput_selection':{'batch_size':16,'detector_peak_reserved_gib':float(peak_history[0]['gpu_peak_reserved_gib']),'renderer_peak_reserved_gib':float(peak_history[1]['gpu_peak_reserved_gib']),'gpu_total_gib':47.99,'batch24_rejected_reason':'renderer memory oversubscription and 28x slowdown','amp':False},'formal_plan':{'run_id':'r109_formal_scratch_20260826','epochs':48,'detector_epochs':12,'renderer_epochs':36,'batch_size':16,'workers':4,'command':'scripts/train.ps1','estimated_hours':'approximately 4 to 6 after first full epoch calibration'},'not_yet_claimed':['formal model quality','replacement of R61 or R79','ONNX readiness','enterprise delivery readiness']}
 (ROOT/'PREPARED_STATE.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
 selected=[]
 for path in ROOT.rglob('*'):
  if not path.is_file():continue
  relative=path.relative_to(ROOT)
  if relative.parts[0]=='data' and relative.parts[1:2]==('package',) and relative.name!='manifest.json':continue
  if relative.parts[0]=='runs' and relative.parts[1] not in {'r109_smoke_detector_renderer','r109_throughput_batch16_peak'}:continue
  if path.name=='FILE_MANIFEST_SHA256.csv':continue
  if path.suffix.lower() in {'.py','.ps1','.json','.md','.txt','.pth','.png'}:selected.append(path)
 with (ROOT/'FILE_MANIFEST_SHA256.csv').open('w',newline='',encoding='utf-8-sig') as handle:
  writer=csv.DictWriter(handle,fieldnames=['relative_path','bytes','sha256']);writer.writeheader()
  for path in sorted(selected):writer.writerow({'relative_path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
 print(json.dumps({'status':state['status'],'manifest_files':len(selected),'formal_training_authorized':True}),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
