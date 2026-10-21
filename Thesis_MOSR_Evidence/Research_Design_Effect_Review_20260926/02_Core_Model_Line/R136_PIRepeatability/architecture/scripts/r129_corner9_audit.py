import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';OUT=B/'R129_revalidation_20260920';S=B/'shape_size'
plan=json.loads((R/'config/plan.json').read_text(encoding='utf-8-sig'));model=plan['models']['R129'];cp=Path(model['checkpoint']['path']);assert hashlib.sha256(cp.read_bytes()).hexdigest()==model['checkpoint']['sha256']
assert model['guard_width']==80 and model['guard_transition']==16
rng=np.random.default_rng(136);weights=rng.multinomial(30,np.ones(30)/30,2000)/30;boot={};actual={};max_difference=0.;count=0
for name in ['Raw','R129']:
 profile=np.load(S/f'{name}_radial_profiles.npz');saved=profile['radius_nm'];theta=profile['angle_rad'];rebuilt=[];radii=[]
 for run in plan['runs']:
  stem=B/'centers'/name/run['run'];df=pd.read_csv(stem.with_suffix('.csv')).sort_values(['index','pillar_id']);points=np.load(stem.with_suffix('.npz'))['points'];one=[]
  for p,row in zip(points.reshape(-1,64,2),df.itertuples()):
   q=p-[row.center_x_px,row.center_y_px];a=np.mod(np.arctan2(q[:,1],q[:,0]),2*np.pi);rad=np.linalg.norm(q,axis=1);ix=np.argsort(a);a,rad=a[ix],rad[ix];v=np.interp(theta,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[rad[-1],rad,rad[0]])*172.5;one.append(v);count+=1
  rebuilt.append(np.array(one).reshape(31,9,720));radii.append(df.radius_px.to_numpy().reshape(31,9)*345)
 rebuilt=np.array(rebuilt);delta=float(np.max(np.abs(saved-rebuilt)));assert delta<.0002;max_difference=max(max_difference,delta)
 data={'diameter_repeat_sd_nm':np.array(radii),'shape_repeat_sd_nm':rebuilt-rebuilt.mean(axis=-1,keepdims=True),'contour_repeat_sd_nm':rebuilt}
 boot[name]={};actual[name]={}
 for metric,v in data.items():
  x=v.reshape(30,-1);actual[name][metric]=float(np.sqrt(np.var(x,axis=0,ddof=1).mean()));x=x-x.mean(axis=0);gram=x@x.T/x.shape[1];boot[name][metric]=np.sqrt(np.maximum(0,(weights@np.diag(gram)-np.einsum('bi,ij,bj->b',weights,gram,weights))*30/29))
rows=[]
for metric in boot['Raw']:
 d=boot['R129'][metric]-boot['Raw'][metric];lo,hi=np.quantile(d,[.025,.975]);rows.append(dict(comparison='R129 - Raw',metric=metric,difference_nm=actual['R129'][metric]-actual['Raw'][metric],ci_low_nm=lo,ci_high_nm=hi))
pd.DataFrame(rows).to_csv(OUT/'paired_shape_size_intervals.csv',index=False)
(OUT/'shape_and_model_verification.json').write_text(json.dumps({'checkpoint_verified':model,'contours_recomputed':count,'angles_per_contour':720,'maximum_profile_difference_nm':max_difference,'nominal_nm_per_px':172.5,'actual_repeat_sd_nm':actual,'bootstrap_repetitions':2000,'bootstrap_unit':'complete scan, paired across methods','stored_float32_profiles_match':True,'no_retraining_or_reinference':True},indent=2),encoding='utf-8')
print(pd.DataFrame(rows).to_string(index=False));print('Profiles verified:',count,'max nm difference',max_difference)
