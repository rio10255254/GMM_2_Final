"""Independent post-run accounting for the fixed R140 real comparison."""
import ast,time,json,hashlib
import numpy as np,pandas as pd,torch,cv2
from utils import ROOT,model_config,config,load,save,sha,now,setup,verify_frozen,verify_protected,verify_evaluation
from infer_model import load_own_model
from dataset import Bank
from losses import objective

def main():
 cfg=config();setup(cfg['model_seed']);run=ROOT/'runs/formal_8192';train=load(run/'training_complete.json');record=train['final_checkpoint']
 assert train['unique_updates']==8192 and record['step']==8192 and sha(record['path'])==record['sha256']
 logs=[json.loads(line) for line in (run/'updates.jsonl').read_text().splitlines()];assert len(logs)==8192 and [x['step'] for x in logs]==list(range(1,8193))
 old=[json.loads(line) for line in (ROOT.parent/'R139_UNetRecurrentPrototype/runs/formal_8192/updates.jsonl').read_text().splitlines()];assert len(old)==8192
 for a,b in zip(logs,old):
  for key in ['epoch','position','parent_id','parent_sha256','input_sha256','noise_seed']:
   if a[key]!=b[key]:raise AssertionError((a['step'],key))
 model,cp=load_own_model(record['path']);assert list(model.refiner.optics.psf_indices)==[0,3,7,10,14,17,21,24]
 assert all(torch.isfinite(p).all() for p in model.parameters())
 real=pd.read_csv(ROOT/'results/reconstruction_runtime.csv');assert len(real)==930 and not real.duplicated(['run','index']).any();weights=[]
 for row in real.itertuples():
  assert row.checkpoint_sha256==record['sha256'] and sha(row.output_path)==row.output_sha256
  w=np.array(ast.literal_eval(row.PSF_weights_final_iteration)).reshape(-1);assert w.shape==(8,) and np.isfinite(w).all() and np.isclose(w.sum(),1,atol=1e-6)
  weights.append(dict(run=row.run,index=row.index,**{f'w{k}':float(v) for k,v in zip(model.refiner.optics.psf_indices,w)}))
 pd.DataFrame(weights).to_csv(ROOT/'results/PSF_all930_weights.csv',index=False)
 comp=ROOT/'results/comparison';assert load(comp/'complete.json')['independent_new_circle_refits']==8370
 circles=pd.read_csv(comp/'all_circles.csv');disps=pd.read_csv(comp/'all_displacements.csv');assert len(circles)==58590 and len(disps)==12600
 axis=np.array(load(ROOT/'evaluation/calibration.json')['axis_unit_vector']);errs=[]
 for (name,runname),group in circles.groupby(['model','run']):
  centers=group.sort_values(['index','pillar_id'])[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2)
  for kind in ['adjacent','start']:
   table=disps[(disps.model==name)&(disps.run==runname)&(disps.kind==kind)].sort_values('j')
   delta=centers[1:]-(centers[:-1] if kind=='adjacent' else centers[:1]);pred=(np.median(delta,axis=1)@axis*.1725-table.pi_displacement_um.to_numpy())*1000
   errs.extend(abs(pred-table.error_nm.to_numpy()))
 assert max(errs)<1e-8
 plan=load(ROOT/'evaluation/capture_plan.json');examples=[]
 for global_index in [0,30,899,929]:
  frame=plan['frames'][global_index];raw=cv2.imread(frame['source']['path'],0);assert raw.shape==(1544,2064)
  x=torch.from_numpy(raw[None,None].astype('float32')/255).cuda()
  with torch.inference_mode():
   on=model(x);model.optical_enabled=False;off=model(x);model.optical_enabled=True
   with np.load(ROOT/'results/reconstruction'/frame['run']/f"{frame['index']+1:02d}.npz") as z:stored=z['output']
   replay=float(abs(stored-on.cpu().numpy()[0,0]).max());assert replay<=2e-6
   examples.append(dict(global_index=global_index,run=frame['run'],index=frame['index'],replay_max_abs=replay,PSF_on_off_rms_gray=float((on-off).square().mean().sqrt()*255),PSF_on_off_max_gray=float((on-off).abs().max()*255)))
  del x,on,off;torch.cuda.empty_cache()
 pd.DataFrame(examples).to_csv(ROOT/'results/PSF_activity_real_examples.csv',index=False)
 # Fixed small generated set probes activity; this is not another model selection step.
 bank=Bank(cfg);generated=[]
 with torch.inference_mode():
  for index in range(32):
   batch=bank.batch('test',index,'cuda');model.optical_enabled=True;on=model(batch['source']);onloss,_=objective(on,batch)
   model.optical_enabled=False;off=model(batch['source']);offloss,_=objective(off,batch);model.optical_enabled=True
   generated.append(dict(index=index,loss_on=float(onloss),loss_off=float(offloss),output_rms_gray=float((on-off).square().mean().sqrt()*255)))
 pd.DataFrame(generated).to_csv(ROOT/'results/PSF_on_off_generated32.csv',index=False)
 verify_frozen(load(ROOT/'config/FORMAL_SOURCE_LOCK.json'));verify_protected();verify_evaluation()
 result=dict(completed_utc=now(),updates=8192,matched_R139_inputs_order_noise=8192,output_sha256_verified=930,PSF_weight_records=930,PSF_candidate_indices=list(model.refiner.optics.psf_indices),PSF_beta_raw=float(model.refiner.optics.beta),PSF_beta_scale=float(model.refiner.optics.beta_scale),PSF_beta_effective=float(model.refiner.optics.last_beta),PSF_activity_observed=any(v['PSF_on_off_max_gray']>0 for v in examples),independent_aggregate_displacements=12600,displacement_max_difference_nm=max(errs),new_circle_refits=8370,real_examples=examples,original_sources_unchanged=True,independent_SEM_confirmation=False,speed_controlled=False)
 save(ROOT/'results/final_audit.json',result);print('INDEPENDENT_FINAL_AUDIT',json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
