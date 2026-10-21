"""Locked six-sequence displacement and appearance audit for frozen R108G."""
from __future__ import annotations
import hashlib,importlib.util,json,math,sys,time
from pathlib import Path
import cv2,numpy as np,pandas as pd,torch
ROOT=Path(__file__).resolve().parents[1];OUTPUT=ROOT/'results/real_motion';OUTPUT.mkdir(parents=True,exist_ok=True)
CORE_PATH=ROOT/'scripts/run_probe.py';HELPER=Path(r'D:\GMM_2_Final\Experiments\R96_LocalizedEvidenceProtectedScratch\scripts\evaluate_real_holdout.py');CONFIG_PATH=Path(r'D:\GMM_2_Final\Experiments\R68_R61_RealFOVFeatureGeneralization\config\sequences.json');LOCKED=Path(r'D:\GMM_2_Final\Experiments\R68_R61_RealFOVFeatureGeneralization\results\tables\tile_motion_measurements.csv')
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
core=load('r108g_motion_core',CORE_PATH);helpers=load('r108g_motion_helpers',HELPER);CONFIG=json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def bools(series):return series if series.dtype==bool else series.astype(str).str.lower().isin({'true','1'})
def write_json(path,payload):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2),encoding='utf-8')
def read(path):return helpers.read_gray(path)
def main():
 model=core.MidpointWidthOperator().to(core.DEVICE);checkpoint=core.WEIGHTS/'midpoint_width_operator.pth';model.load_state_dict(torch.load(checkpoint,map_location=core.DEVICE,weights_only=False)['model']);model.eval();locked=pd.read_csv(LOCKED);reconstructed={};records=[];appearance=[];total=sum(int(item['frame_count']) for item in CONFIG['sequences'].values());done=0;started=time.perf_counter()
 for sequence,item in CONFIG['sequences'].items():
  paths=sorted(Path(item['raw_dir']).glob('frame_*.bmp'))
  if len(paths)!=int(item['frame_count']):raise RuntimeError(f'{sequence} inventory')
  for index,path in enumerate(paths):
   destination=OUTPUT/'reconstructions'/sequence/path.name
   value=np.round(core.fcore.tiled(model,read(path).astype(np.float32)/255,core=1024,halo=192)*255).astype(np.uint8);helpers.write_gray(destination,value)
   reconstructed[(sequence,index)]=destination;records.append({'sequence':sequence,'frame_index':index,'source':str(path),'source_sha256':sha(path),'output':str(destination),'output_sha256':sha(destination)});raw=read(path);appearance.append({'sequence':sequence,'frame_index':index,**helpers.appearance_metrics(raw,value,512)});done+=1
   if done%10==0 or done==total:print(json.dumps({'done':done,'total':total,'sequence':sequence,'frame':index}),flush=True)
 pd.DataFrame(records).to_csv(OUTPUT/'reconstruction_manifest.csv',index=False);app=pd.DataFrame(appearance);app.to_csv(OUTPUT/'appearance_per_frame.csv',index=False);app.groupby('sequence').median(numeric_only=True).reset_index().to_csv(OUTPUT/'appearance_sequence_summary.csv',index=False)
 motion=[]
 for _,row in locked.iterrows():
  sequence=str(row.sequence);step=int(row.step_index);first=read(reconstructed[(sequence,step)]);second=read(reconstructed[(sequence,step+1)]);tile_h,tile_w=first.shape[0]//6,first.shape[1]//8;y0,x0=int(row.tile_row)*tile_h,int(row.tile_column)*tile_w;a=first[y0:y0+tile_h,x0:x0+tile_w];b=second[y0:y0+tile_h,x0:x0+tile_w];phase_dx,phase_dy,response=helpers.phase_shift(a,b)
  try:dx,dy,ecc=helpers.bounded_ecc_shift(a,b,float(row.raw_dx_px),float(row.raw_dy_px));finite=all(math.isfinite(v) for v in (dx,dy,ecc))
  except cv2.error:dx=dy=ecc=math.nan;finite=False
  limit=max(12,abs(float(row.expected_dx_px))*2.5);evaluable=finite and ecc>=.75 and abs(dx)<=limit and abs(dy)<=limit;raw_valid=str(row.raw_reference_valid).lower() in {'true','1'};valid=bool(raw_valid and evaluable);motion.append({**row.to_dict(),'candidate_phase_dx_px':phase_dx,'candidate_phase_dy_px':phase_dy,'candidate_response':response,'candidate_dx_px':dx,'candidate_dy_px':dy,'candidate_ecc':ecc,'candidate_evaluable':evaluable,'candidate_valid':valid,'candidate_direction_agreement':bool(valid and np.sign(dx)==np.sign(float(row.raw_dx_px)))})
 frame=pd.DataFrame(motion);frame['common_valid']=bools(frame.raw_reference_valid)&bools(frame.candidate_valid);frame.to_csv(OUTPUT/'motion_measurements.csv',index=False);summaries=[];decisions=[];gates=CONFIG['gates']
 for sequence,group in frame.groupby('sequence',sort=False):
  common=group[group.common_valid];scale=float(group.object_um_per_px.iloc[0]);nominal=float(group.nominal_step_um.iloc[0]);dx=common.candidate_dx_px.astype(float);dy=common.candidate_dy_px.astype(float);raw_dx=common.raw_dx_px.astype(float);raw_dy=common.raw_dy_px.astype(float);step=dx.abs()*scale;raw_step=raw_dx.abs()*scale;vector=np.hypot(dx.to_numpy()-raw_dx.to_numpy(),dy.to_numpy()-raw_dy.to_numpy())*scale;ratio=step/raw_step.clip(lower=1e-9);response=common.candidate_response.astype(float)/common.raw_response.astype(float).clip(lower=1e-9);valid_fraction=len(common)/max(int(bools(group.raw_reference_valid).sum()),1);direction=float(bools(common.candidate_direction_agreement).mean()) if len(common) else 0
  summary={'sequence':sequence,'magnification':float(group.magnification.iloc[0]),'nominal_step_um':nominal,'common_measurements':len(common),'common_fraction_of_raw_reference':valid_fraction,'median_abs_dx_um':float(step.median()),'step_std_um':float(step.std(ddof=1)),'median_model_over_raw_abs_dx':float(ratio.median()),'median_scale_error_fraction':float(abs(ratio.median()-1)),'median_vector_difference_from_raw_um':float(np.median(vector)),'p95_vector_difference_from_raw_um':float(np.quantile(vector,.95)),'median_response_ratio':float(response.median()),'median_ecc':float(common.candidate_ecc.median()),'direction_agreement':direction};summaries.append(summary);checks={'valid_fraction':valid_fraction>=float(gates['minimum_valid_fraction']),'direction':direction>=float(gates['minimum_direction_agreement']),'scale':summary['median_scale_error_fraction']<=float(gates['maximum_median_scale_error_fraction']),'median_difference':summary['median_vector_difference_from_raw_um']/nominal<=float(gates['maximum_median_difference_of_step']),'p95_difference':summary['p95_vector_difference_from_raw_um']/nominal<=float(gates['maximum_p95_difference_of_step']),'response':summary['median_response_ratio']>=float(gates['minimum_median_response_ratio']),'ecc':summary['median_ecc']>=float(gates['minimum_median_ecc'])};decisions.append({'sequence':sequence,'pass':all(checks.values()),'checks':checks})
 pd.DataFrame(summaries).to_csv(OUTPUT/'motion_sequence_summary.csv',index=False);result={'status':'complete','frames':total,'measurements':len(frame),'all_sequences_pass':all(item['pass'] for item in decisions),'decisions':decisions,'elapsed_seconds':time.perf_counter()-started,'checkpoint':str(checkpoint),'checkpoint_sha256':sha(checkpoint)};write_json(OUTPUT/'summary.json',result);print(json.dumps(result),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
