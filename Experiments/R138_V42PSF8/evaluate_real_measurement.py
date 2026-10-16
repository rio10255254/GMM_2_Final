"""Same fixed930 observations, Raw tracking, ACM/edge/LSC and calibration."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import time,concurrent.futures
import numpy as np,pandas as pd,torch,cv2
from utils import ROOT,config,load,save,sha,now,verify_frozen,verify_protected,verify_evaluation_sources,setup
from infer_r138_psf import load_own_model,predict_tensor
from evaluation.measurement_interface import measure_image

def require_final():
 c=load(ROOT/'runs/formal_8192/training_complete.json');assert c['unique_updates']==8192 and c['final_checkpoint']['step']==8192
 p=c['final_checkpoint'];assert sha(p['path'])==p['sha256'];verify_frozen(load(ROOT/'config/source_lock.json'))
 verify_evaluation_sources()
 return c

def reconstruct_all():
 complete=require_final();cfg=config();setup(cfg['model_seed']);model,_=load_own_model(complete['final_checkpoint']['path']);plan=load(ROOT/'evaluation/capture_plan.json');rows=[];dest=ROOT/'results/reconstruction';start=time.perf_counter()
 weight_history=[]
 def capture(module,args,output):
  w=torch.softmax(output.reshape(output.shape[0],8)/model.optics.psf_temp,dim=1);weight_history.append(w.detach().cpu().tolist())
 handle=model.optics.gating.register_forward_hook(capture)
 for k,f in enumerate(plan['frames'],1):
  directory=dest/f['run'];directory.mkdir(exist_ok=True);stem=f"{f['index']+1:02d}";record=directory/(stem+'.json')
  if record.exists():
   r=load(record);assert r['checkpoint_sha256']==complete['final_checkpoint']['sha256'];assert sha(directory/(stem+'.npz'))==r['output_sha256'];rows.append(r);continue
  tick=time.perf_counter();p=f['source']['path'];assert sha(p)==f['source']['sha256'];raw=cv2.imread(p,0)
  if raw is None:raise ValueError('Missing input')
  if raw.shape!=(1544,2064):raise ValueError('Unexpected full native shape')
  x=torch.from_numpy(raw.astype('float32')[None,None]/np.float32(255));a=time.perf_counter();x=x.to(cfg['device']);transfer=time.perf_counter()-a
  a=time.perf_counter()
  weight_history.clear()
  with torch.inference_mode():y=predict_tensor(model,x,'full',cfg['inference']['tile_core'],cfg['inference']['halo'])
  inference=time.perf_counter()-a;peak=0;v=y.cpu().numpy()[0,0]
  if not np.isfinite(v).all():raise FloatingPointError('Nonfinite real output')
  output=directory/(stem+'.npz');np.savez_compressed(output,output=v)
  if not cv2.imwrite(str(directory/(stem+'.png')),np.rint(v*65535).clip(0,65535).astype('uint16')):raise OSError('Cannot save display image')
  assert len(weight_history)==4
  r=dict(PSF_weights_per_iteration=weight_history,PSF_indices=list(model.optics.psf_indices),PSF_effective_beta=model.optics.last_beta,model='R138-V42PSF8',run=f['run'],index=f['index'],shape=list(v.shape),source=f['source'],output_path=str(output),output_sha256=sha(output),checkpoint_sha256=complete['final_checkpoint']['sha256'],data_transfer_seconds=transfer,total_reconstruction_seconds=inference,peak_gpu_allocated_bytes=peak,end_to_end_load_infer_save_seconds=time.perf_counter()-tick,precision='FP32',device=cfg['device'],mode='full',completed_utc=now())
  save(record,r);rows.append(r)
  if k%10==0 or k==1:
   save(ROOT/'results/reconstruction_status.json',dict(state='running',completed=k,total=930,elapsed_seconds=time.perf_counter()-start,updated_utc=now()));print('Full-image inference',k,'/930',flush=True)
 assert len(rows)==930;pd.DataFrame(rows).to_csv(ROOT/'results/reconstruction_runtime.csv',index=False)
 save(ROOT/'results/reconstruction_complete.json',dict(images=930,shape=[1544,2064],checkpoint_sha256=complete['final_checkpoint']['sha256'],completed_utc=now(),no_measurement_feedback=True));handle.remove();del model

def measure_run(run):
 cv2.setNumThreads(1);plan=load(ROOT/'evaluation/capture_plan.json');cfg=load(ROOT/'evaluation/measurement_config.json');tracking=pd.read_csv(ROOT/'evaluation/tracking.csv');tracking=tracking[tracking.run==run]
 frames=[f for f in plan['frames'] if f['run']==run];rows=[];points=[];coarse=[];times=[]
 for f in frames:
  path=ROOT/'results/reconstruction'/run/f"{f['index']+1:02d}.npz"
  with np.load(path) as z:image=z['output'].astype(np.float64)
  centers=tracking[tracking['index']==f['index']].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy();assert centers.shape==(9,2)
  start=time.perf_counter();r,p=measure_image(image,centers,cfg);times.append(time.perf_counter()-start)
  rows.extend([dict(model='R138-V42PSF8',run=run,run_index=f['run_index'],index=f['index'],**v) for v in r]);points.append(p['points']);coarse.append(p['coarse'])
 out=ROOT/'results/centers';out.mkdir(exist_ok=True);pd.DataFrame(rows).to_csv(out/(run+'.csv'),index=False)
 np.savez_compressed(out/(run+'.npz'),points=np.stack(points),coarse=np.stack(coarse))
 result=dict(run=run,images=31,circles=279,ACM_measurement_seconds=times,completed_utc=now());save(out/(run+'.json'),result);return result

def baseline_reader_parity():
 cfg=load(ROOT/'evaluation/measurement_config.json');plan=load(ROOT/'evaluation/capture_plan.json');tracking=pd.read_csv(ROOT/'evaluation/tracking.csv');checks=[]
 # Frozen examples only check the unchanged reader after training is finished.
 for idx in [0,30,899,929]:
  f=plan['frames'][idx];seed=tracking[(tracking.run==f['run'])&(tracking['index']==f['index'])].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy()
  raw=cv2.imread(f['source']['path'],0).astype(float)/255
  rows,p=measure_image(raw,seed,cfg)
  with np.load(ROOT/f'evaluation/baseline_centers/Raw/{f["run"]}.npz') as z:expected=z['points'][f['index']]
  error=float(np.abs(p['points']-expected).max());assert error<1e-7,(idx,error)
  checks.append(dict(frame_index=idx,max_point_error_px=error))
 save(ROOT/'results/baseline_reader_parity.json',checks)

def main():
 require_final();baseline_reader_parity()
 if not (ROOT/'results/reconstruction_complete.json').exists():reconstruct_all()
 plan=load(ROOT/'evaluation/capture_plan.json');out=ROOT/'results/centers';out.mkdir(exist_ok=True)
 pending=[x['run'] for x in plan['runs'] if not (out/(x['run']+'.json')).exists()]
 with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
  for r in pool.map(measure_run,pending):print('Measured scan',r['run'],flush=True)
 assert len(list(out.glob('*_XY_0.csv')))==30
 save(ROOT/'results/measurement_complete.json',dict(scans=30,images=930,circles=8370,backend='unchanged frozen ACM maximum-gradient LSC',completed_utc=now()))
 verify_protected()
if __name__=='__main__':main()
