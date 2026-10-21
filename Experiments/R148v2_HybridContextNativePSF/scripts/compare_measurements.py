"""Fixed readout arithmetic, all30 scans, no model-dependent selection."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,pandas as pd
from scipy.optimize import least_squares
from utils import ROOT,load,save,now
from evaluation_lock import verify as verify_evaluation_lock
MODEL='R148v2-HybridContextNativePSF';MODELS=['Raw','R129','R130-Clean','R137-WeakPSF','R138-V42PSF8','R139-UNetRecurrent','R140v2-StableUNet','R143-PSF25-MatchedPairs','R145-Center9PSF25-CorrectedPairs','R146-SEMCoreHaloPSF25-MatchedPairs','R147-FullResPSFConsistency',MODEL];NM=172.5;TH=np.linspace(0,2*np.pi,720,endpoint=False)
def signature(points,center):
 d=points-center;a=np.mod(np.arctan2(d[:,1],d[:,0]),2*np.pi);r=np.linalg.norm(d,axis=1);ix=np.argsort(a);a,r=a[ix],r[ix]
 return np.interp(TH,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])
def boot_sd(x,w):
 x=x.reshape(30,-1);x=x-x.mean(axis=0);gram=x@x.T/x.shape[1]
 return np.sqrt(np.maximum(0,(w@np.diag(gram)-np.einsum('bi,ij,bj->b',w,gram,w))*30/29))
def main():
 verify_evaluation_lock()
 assert load(ROOT/'results/measurement_complete.json')['circles']==8370
 plan=load(ROOT/'evaluation/capture_plan.json');cal=load(ROOT/'evaluation/calibration.json');u=np.array(cal['axis_unit_vector']);trans=np.array(cal['transverse_unit_vector']);assert abs(cal['nominal_um_per_px']-.1725)<1e-14
 out=ROOT/'results/comparison';out.mkdir(exist_ok=True);displacements=[];circles=[];diameters={};profiles={};allpoints={};readout_times=[]
 for model in MODELS:
  base=ROOT/'results/centers' if model==MODEL else ROOT/'evaluation/baseline_centers'/model
  ds=[];ps=[];ptsall=[]
  for run in plan['runs']:
   name=run['run'];df=pd.read_csv(base/(name+'.csv')).sort_values(['index','pillar_id']);assert len(df)==279 and not df.duplicated(['index','pillar_id']).any()
   with np.load(base/(name+'.npz'),allow_pickle=False) as z:pts=z['points']
   assert pts.shape==(31,9,64,2);center=df[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2);radius=df.radius_px.to_numpy().reshape(31,9)
   sig=np.array([signature(p,c) for p,c in zip(pts.reshape(-1,64,2),center.reshape(-1,2))]).reshape(31,9,720)*NM
   ds.append(2*radius*NM);ps.append(sig);ptsall.append(pts);df['diameter_nm']=2*df.radius_px*NM;circles.append(df)
   frames=[f for f in plan['frames'] if f['run']==name]
   for kind,i,j in [('adjacent',j-1,j) for j in range(1,31)]+[('start',0,j) for j in range(1,31)]:
    delta=center[j]-center[i];med=np.median(delta,axis=0);pi=frames[j]['pi_y_um']-frames[i]['pi_y_um'];along=np.dot(med,u)*.1725
    displacements.append(dict(model=model,run=name,run_index=run['run_index'],kind=kind,i=i,j=j,pi_displacement_um=pi,image_displacement_um=along,error_nm=(along-pi)*1000,dx_px=med[0],dy_px=med[1],transverse_nm=np.dot(med,trans)*172.5))
   if model==MODEL:readout_times.extend(load(base/(name+'.json'))['ACM_measurement_seconds'])
  diameters[model]=np.array(ds);profiles[model]=np.array(ps);allpoints[model]=ptsall
  assert diameters[model].shape==(30,31,9) and profiles[model].shape==(30,31,9,720)
 d=pd.DataFrame(displacements);assert len(d)==len(MODELS)*1800;d.to_csv(out/'all_displacements.csv',index=False);pd.concat(circles,ignore_index=True).to_csv(out/'all_circles.csv',index=False)
 summary=[];positions=[];scans=[]
 for (model,kind),g in d.groupby(['model','kind']):
  s=g.groupby('j').error_nm.std(ddof=1)
  summary.append(dict(model=model,kind=kind,mae_nm=g.error_nm.abs().mean(),bias_nm=g.error_nm.mean(),repeatability_nm=s.mean(),maximum_error_nm=g.error_nm.abs().max()))
  for j,p in g.groupby('j'):positions.append(dict(model=model,kind=kind,position=int(j),n=len(p),mean_error_nm=p.error_nm.mean(),repeat_sd_nm=p.error_nm.std(ddof=1),mean_PI_um=p.pi_displacement_um.mean()))
  for name,p in g.groupby('run'):scans.append(dict(model=model,kind=kind,run=name,mae_nm=p.error_nm.abs().mean(),bias_nm=p.error_nm.mean()))
 s=pd.DataFrame(summary);s.to_csv(out/'displacement_summary.csv',index=False);pd.DataFrame(positions).to_csv(out/'position_statistics.csv',index=False);sc=pd.DataFrame(scans);sc.to_csv(out/'scan_statistics.csv',index=False)
 geom=[]
 for model in MODELS:
  p=profiles[model];shape=p-p.mean(axis=-1,keepdims=True);di=diameters[model]
  geom.append(dict(model=model,diameter_mean_nm=di.mean(),diameter_repeat_sd_nm=np.sqrt(di.var(axis=0,ddof=1).mean()),contour_repeat_sd_nm=np.sqrt(p.var(axis=0,ddof=1).mean()),shape_repeat_sd_nm=np.sqrt(shape.var(axis=0,ddof=1).mean()),diameter_repeat_absmax_nm=np.abs(di-di.mean(axis=0)).max()))
  np.savez_compressed(out/(model+'_radial_profiles.npz'),radius_nm=p.astype('float32'),angle_rad=TH)
 geometry=pd.DataFrame(geom);geometry.to_csv(out/'shape_size_summary.csv',index=False)
 # Baseline arithmetic must reproduce the supplied current-nine table.
 expected=pd.read_csv(ROOT/'evaluation/baseline_reference/main_comparison.csv');parity=[]
 for model in ['Raw','R129']:
  for kind in ['adjacent','start']:
   row=s[(s.model==model)&(s.kind==kind)].iloc[0]
   for key in ['mae_nm','repeatability_nm','maximum_error_nm']:
    ref=expected[(expected.scope==kind)&(expected.metric==key)].iloc[0][model+'_nm'];err=abs(row[key]-ref);assert err<1e-4,(model,kind,key,err);parity.append(err)
  row=geometry[geometry.model==model].iloc[0]
  for key in ['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm']:
   ref=expected[(expected.scope=='contour')&(expected.metric==key)].iloc[0][model+'_nm'];err=abs(row[key]-ref);assert err<1e-4;parity.append(err)
 # SEM uses the unchanged original definition, scale and both mapping candidates.
 mapping=load(ROOT/'evaluation/sem_mapping_candidates.json');ids=sorted(mapping[0]['sem_ids_by_new_nine']);scale=load(ROOT/'evaluation/sem_scale.json')['scale_nm_per_px'];truth={};reference_diam={}
 with np.load(ROOT/'evaluation/sem_points.npz') as z:
  for pid in ids:
   p=z[f'SEM_{pid}'];q=p-p.mean(0)
   def fun(c):
    r=np.linalg.norm(q-c,axis=1);return r-r.mean()
   c=least_squares(fun,[0,0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x;truth[pid]=(q-c)*scale;reference_diam[pid]=2*np.linalg.norm(truth[pid],axis=1).mean()
 sem=[]
 for mi,m in enumerate(mapping,1):
  ref=[]
  for pid in m['sem_ids_by_new_nine']:
   q=truth[pid].copy()
   if m['candidate']['flip']:q[:,0]*=-1
   for _ in range(m['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
   ref.append(signature(q,np.zeros(2)))
  ref=np.array(ref)
  for model in MODELS:
   p=profiles[model]
   sem.append(dict(model=model,mapping_candidate=mi,SEM_mean_diameter_nm=np.mean(list(reference_diam.values())),mean_diameter_difference_nm=diameters[model].mean()-np.mean(list(reference_diam.values())),full_radial_difference_nm=np.abs(p-ref).mean(),de_size_shape_difference_nm=np.abs((p-p.mean(-1,keepdims=True))-(ref-ref.mean(-1,keepdims=True))).mean()))
 sem=pd.DataFrame(sem);sem.to_csv(out/'SEM_comparison.csv',index=False)
 # Keep the previously verified image-row identity. The Excel disk values are
 # The Excel disks are a secondary size reference; the source bank was fitted
 # to actual P-SEM silhouettes, as in the unchanged R146 data.
 current_map=pd.read_csv(ROOT/'evaluation/sem_current_center9_mapping.csv').sort_values(['image_row','image_col'])
 assert current_map.sem_id_working.tolist()==[36,35,34,30,29,28,24,23,22]
 assert current_map.sem_id_working.is_unique and len(current_map)==9
 current_truth=current_map.sem_diameter_nm.to_numpy(dtype=float)
 current_rows=[];current_summary=[]
 for model in MODELS:
  observed=diameters[model].mean(axis=(0,1));difference=observed-current_truth
  for k,(row,value,diff) in enumerate(zip(current_map.itertuples(),observed,difference),1):
   current_rows.append(dict(model=model,pillar_id=k,sem_id=int(row.sem_id_working),
                            workbook_cell=row.workbook_cell,SEM_diameter_nm=float(row.sem_diameter_nm),
                            measured_mean_diameter_nm=float(value),signed_difference_nm=float(diff)))
  current_summary.append(dict(model=model,SEM_mean_diameter_nm=float(current_truth.mean()),
                              measured_mean_diameter_nm=float(observed.mean()),
                              mean_diameter_difference_nm=float(difference.mean()),
                              mean_absolute_pillar_difference_nm=float(np.abs(difference).mean()),
                              max_absolute_pillar_difference_nm=float(np.abs(difference).max())))
 pd.DataFrame(current_rows).to_csv(out/'SEM_corrected_size_by_pillar.csv',index=False)
 pd.DataFrame(current_summary).to_csv(out/'SEM_corrected_size_summary.csv',index=False)
 # The fixed PSF source used actual SEM silhouettes. Preserve their independently
 # extracted contour-diameter reference with the verified image-row IDs.
 contour_truth=np.array([reference_diam[int(pid)] for pid in current_map.sem_id_working],dtype=float)
 contour_rows=[];contour_summary=[]
 for model in MODELS:
  observed=diameters[model].mean(axis=(0,1));difference=observed-contour_truth
  for pillar,(row,value,diff) in enumerate(zip(current_map.itertuples(),observed,difference),1):
   contour_rows.append(dict(model=model,pillar_id=pillar,sem_id=int(row.sem_id_working),
                            SEM_contour_diameter_nm=float(contour_truth[pillar-1]),
                            measured_mean_diameter_nm=float(value),signed_difference_nm=float(diff)))
  contour_summary.append(dict(model=model,SEM_contour_mean_diameter_nm=float(contour_truth.mean()),
                              measured_mean_diameter_nm=float(observed.mean()),
                              mean_diameter_difference_nm=float(difference.mean()),
                              mean_absolute_pillar_difference_nm=float(np.abs(difference).mean()),
                              max_absolute_pillar_difference_nm=float(np.abs(difference).max())))
 pd.DataFrame(contour_rows).to_csv(out/'SEM_contour_size_by_pillar.csv',index=False)
 pd.DataFrame(contour_summary).to_csv(out/'SEM_contour_size_summary.csv',index=False)
 refsem=pd.read_csv(ROOT/'evaluation/baseline_reference/SEM_direction_sensitivity.csv')
 for model in ['Raw','R129']:
  for mi in [1,2]:
   row=sem[(sem.model==model)&(sem.mapping_candidate==mi)].iloc[0];ref=refsem[(refsem.model==model)&(refsem.mapping_candidate==mi)].iloc[0]
   assert abs(row.full_radial_difference_nm-ref.radial_mae_nm)<1e-4
   assert abs(row.de_size_shape_difference_nm-ref.shape_mae_nm)<1e-4
 # Entire-scan paired intervals; no angle/target pseudo-replication.
 rng=np.random.default_rng(130136);draw=rng.integers(0,30,size=(2000,30));weights=np.array([np.bincount(x,minlength=30)/30 for x in draw]);pairs=[]
 for base in ['Raw','R129','R130-Clean','R137-WeakPSF','R138-V42PSF8','R139-UNetRecurrent','R140v2-StableUNet','R143-PSF25-MatchedPairs','R145-Center9PSF25-CorrectedPairs','R146-SEMCoreHaloPSF25-MatchedPairs','R147-FullResPSFConsistency']:
  for kind in ['adjacent','start']:
   a=sc[(sc.model==MODEL)&(sc.kind==kind)].set_index('run').mae_nm.sort_index();b=sc[(sc.model==base)&(sc.kind==kind)].set_index('run').mae_nm.sort_index();delta=(a-b).to_numpy();interval=np.quantile(delta[draw].mean(1),[.025,.975]);pairs.append(dict(reference=base,metric=kind+'_mae_nm',difference_nm=delta.mean(),ci95_low=interval[0],ci95_high=interval[1],improved_scans=int((delta<0).sum())))
  for key in ['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm']:
   arrays={}
   for m in [base,MODEL]:
    a=diameters[m] if key=='diameter_repeat_sd_nm' else profiles[m]
    if key=='shape_repeat_sd_nm':a=a-a.mean(-1,keepdims=True)
    arrays[m]=boot_sd(a,weights)
   interval=np.quantile(arrays[MODEL]-arrays[base],[.025,.975]);delta=float(geometry[geometry.model==MODEL][key].iloc[0]-geometry[geometry.model==base][key].iloc[0]);pairs.append(dict(reference=base,metric=key,difference_nm=delta,ci95_low=interval[0],ci95_high=interval[1],improved_scans=None))
 pd.DataFrame(pairs).to_csv(out/'paired_scan_intervals.csv',index=False)
 endpoints=d[(d.kind=='start')&(d.j==30)].groupby('model').error_nm.agg(['mean','std','min','max']);endpoints.to_csv(out/'endpoint_30um.csv')
 save(out/'measurement_timing.json',dict(images=930,mean_seconds=float(np.mean(readout_times)),median_seconds=float(np.median(readout_times)),total_worker_seconds=float(np.sum(readout_times)),scope='ACM/maximum-gradient/LSC only; excludes reconstruction and image loading'))
 # Independent three-parameter refits for every newly measured boundary.
 maxfit=0;count=0
 for run,points in zip(plan['runs'],allpoints[MODEL]):
  rows=pd.read_csv(ROOT/f'results/centers/{run["run"]}.csv').sort_values(['index','pillar_id'])
  for p,row in zip(points.reshape(-1,64,2),rows.itertuples()):
   origin=p.mean(0);q=p-origin;r0=np.linalg.norm(q,axis=1).mean()
   def f(v):return np.linalg.norm(q-v[:2],axis=1)-v[2]
   fit=least_squares(f,[0,0,r0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x;actual=np.r_[fit[:2]+origin,fit[2]];old=np.array([row.center_x_px,row.center_y_px,row.radius_px]);maxfit=max(maxfit,float(np.abs(actual-old).max()));count+=1
 assert maxfit<1e-3,(maxfit,count)
 save(out/'complete.json',dict(models=MODELS,images_per_model=930,circles_per_model=8370,independent_new_circle_refits=count,max_refit_difference_px=maxfit,baseline_summary_max_difference_nm=max(parity),SEM_mapping='verified image-row IDs for contour and Excel sizes; two historical shape-direction candidates retained without new fit',completed_utc=now()))
 print(s.to_string(index=False),flush=True);print(geometry.to_string(index=False),flush=True)
if __name__=='__main__':main()
