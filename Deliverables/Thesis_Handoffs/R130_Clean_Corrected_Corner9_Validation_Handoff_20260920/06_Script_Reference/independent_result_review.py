"""Post-run independent arithmetic and visual audit; never updates a model/source lock."""
from pathlib import Path
import json,hashlib,time
import numpy as np,pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def radial(p):
 a=np.mod(np.arctan2(p[:,1],p[:,0]),2*np.pi);v=np.linalg.norm(p,axis=1);i=np.argsort(a);a,v=a[i],v[i]
 return np.interp(np.linspace(0,2*np.pi,720,endpoint=False),np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[v[-1],v,v[0]])
def main():
 assert load(ROOT/'results/complete.json')['images']==930
 out=ROOT/'results/independent_review';out.mkdir(exist_ok=True);figs=ROOT/'reports/figures'
 plan=load(ROOT/'evaluation/capture_plan.json');final=load(ROOT/'runs/formal_8192/training_complete.json')['final_checkpoint'];sources=[]
 for k,f in enumerate(plan['frames'],1):
  p=ROOT/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.json";meta=load(p)
  assert meta['source']==f['source'] and meta['checkpoint_sha256']==final['sha256'] and meta['shape']==[1544,2064] and meta['mode']=='full'
  v=Path(meta['output_path']);assert sha(v)==meta['output_sha256'];assert v.with_suffix('.png').exists();sources.append(meta['output_sha256'])
  if k%150==0:print('Independent output hashes',k,'/930',flush=True)
 table=pd.read_csv(ROOT/'results/comparison/displacement_summary.csv');cal=load(ROOT/'evaluation/calibration.json');axis=np.array(cal['axis_unit_vector']);derived=[];errors=[]
 for model in ['Raw','R129','R130-Clean']:
  folder=ROOT/'results/centers' if model=='R130-Clean' else ROOT/'evaluation/baseline_centers'/model
  arr=[]
  for run in plan['runs']:
   df=pd.read_csv(folder/(run['run']+'.csv')).sort_values(['index','pillar_id']);arr.append(df[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2))
  c=np.stack(arr)
  for kind in ['adjacent','start']:
   delta=np.diff(c,axis=1) if kind=='adjacent' else c[:,1:]-c[:,:1]
   image=np.median(delta,axis=2)@axis*.1725;pi=[]
   for run in plan['runs']:
    pos=np.array([f['pi_y_um'] for f in plan['frames'] if f['run']==run['run']]);pi.append(np.diff(pos) if kind=='adjacent' else pos[1:]-pos[0])
   e=(image-np.array(pi))*1000;row=table[(table.model==model)&(table.kind==kind)].iloc[0]
   vals=dict(mae_nm=float(np.abs(e).mean()),bias_nm=float(e.mean()),repeatability_nm=float(e.std(axis=0,ddof=1).mean()),maximum_error_nm=float(np.abs(e).max()))
   for key,value in vals.items():errors.append(abs(value-row[key]));assert abs(value-row[key])<1e-7
   derived.append(dict(model=model,kind=kind,**vals))
 pd.DataFrame(derived).to_csv(out/'independently_recomputed_displacement.csv',index=False)
 # Registered audit method: circular blocks of3 separately within6/24 sessions,
 # never crossing the acquisition break. This is sensitivity, not a new model.
 scans=pd.read_csv(ROOT/'results/comparison/scan_statistics.csv');rng=np.random.default_rng(13013601)
 early=((rng.integers(0,6,size=(2000,2,1))+np.arange(3))%6).reshape(2000,6)
 late=6+((rng.integers(0,24,size=(2000,8,1))+np.arange(3))%24).reshape(2000,24)
 ix=np.concatenate([early,late],axis=1);intervals=[]
 for kind in ['adjacent','start']:
  for base in ['Raw','R129']:
   a=scans[(scans.model=='R130-Clean')&(scans.kind==kind)].set_index('run').mae_nm.sort_index().to_numpy();b=scans[(scans.model==base)&(scans.kind==kind)].set_index('run').mae_nm.sort_index().to_numpy();v=a-b;q=np.quantile(v[ix].mean(1),[.025,.975]);intervals.append(dict(kind=kind,reference=base,mean_difference_nm=v.mean(),block3_separate_6_24_low_nm=q[0],block3_separate_6_24_high_nm=q[1]))
 pd.DataFrame(intervals).to_csv(out/'time_block_sensitivity.csv',index=False)
 # All nine mean shapes and the fixed first SEM mapping; preserve both mappings in main tables.
 mapping=load(ROOT/'evaluation/sem_mapping_candidates.json')[0];scale=load(ROOT/'evaluation/sem_scale.json')['scale_nm_per_px'];references=[]
 with np.load(ROOT/'evaluation/sem_points.npz') as z:
  for pid in mapping['sem_ids_by_new_nine']:
   points=z[f'SEM_{pid}'];q=points-points.mean(0)
   def f(c):
    rr=np.linalg.norm(q-c,axis=1);return rr-rr.mean()
   center=least_squares(f,[0,0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x;q=(q-center)*scale
   if mapping['candidate']['flip']:q[:,0]*=-1
   for _ in range(mapping['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
   references.append(radial(q))
 means={'SEM':np.array(references)}
 for model in ['Raw','R129','R130-Clean']:
  with np.load(ROOT/f'results/comparison/{model}_radial_profiles.npz') as z:means[model]=z['radius_nm'].astype(float).mean(axis=(0,1))
 amplitude=[];colors={'SEM':'black','Raw':'#777777','R129':'#1e7898','R130-Clean':'#d16d20'}
 for model,p in means.items():
  for j,v in enumerate(p):amplitude.append(dict(model=model,pillar=j+1,de_mean_shape_rms_nm=np.std(v),radial_range_nm=np.ptp(v),scope='mean shape amplitude,not error or repeatability'))
 pd.DataFrame(amplitude).to_csv(out/'mean_shape_amplitudes.csv',index=False)
 fig,axes=plt.subplots(3,3,figsize=(11,9),layout='constrained');theta=np.arange(720)/2
 for j,ax in enumerate(axes.flat):
  for model,p in means.items():ax.plot(theta,p[j]-p[j].mean(),label=model,color=colors[model],lw=1)
  ax.set(title=f'Pillar {j+1}',xlabel='Angle (deg)',ylabel='De-mean radius (nm)');ax.grid(alpha=.15)
 axes[0,0].legend(fontsize=8);fig.suptitle('All nine mean shapes; SEM mapping1 remains inferred. Sizes reported separately.');fig.savefig(figs/'independent_mean_shapes.png',dpi=160);plt.close(fig)
 # Inspect the objectively largest new adjacent error, using the same raw tracking crop.
 disp=pd.read_csv(ROOT/'results/comparison/all_displacements.csv');q=disp[(disp.model=='R130-Clean')&(disp.kind=='adjacent')];worst=q.loc[q.error_nm.abs().idxmax()];frame=next(f for f in plan['frames'] if f['run']==worst.run and f['index']==int(worst.j));tracking=pd.read_csv(ROOT/'evaluation/tracking.csv');t=tracking[(tracking.run==worst.run)&(tracking['index']==int(worst.j))];left=int(t.seed_x_px.min())-20;right=int(t.seed_x_px.max())+21;top=int(t.seed_y_px.min())-20;bottom=int(t.seed_y_px.max())+21
 images={'Raw':cv2.imread(frame['source']['path'],0).astype(float)/255}
 for model in ['R129','R130-Clean']:
  p=(ROOT.parents[2]/'Experiments/R136_PIRepeatability/results/R129' if model=='R129' else ROOT/'results/reconstruction')/worst.run/f'{int(worst.j)+1:02d}.npz'
  with np.load(p) as z:images[model]=z['output']
 fig,axes=plt.subplots(1,3,figsize=(11,4),layout='constrained')
 for ax,(model,v) in zip(axes,images.items()):ax.imshow(v[top:bottom,left:right],cmap='gray',vmin=0,vmax=1,interpolation='nearest');ax.set_title(model);ax.axis('off')
 fig.suptitle(f'Largest R130 adjacent-error observation: {worst.run}, position{int(worst.j)}');fig.savefig(figs/'worst_adjacent_observation.png',dpi=170);plt.close(fig)
 result=dict(outputs_sha256_verified=930,unique_output_hashes=len(set(sources)),independent_displacement_summary_max_difference_nm=max(errors),final_checkpoint_sha256=final['sha256'],audit_script_sha256=sha(__file__),time_block_sensitivity='circular block3 sampled separately within first6 and late24;2000 draws,seed13013601',mean_shape_plot='SEM mapping1 explicitly inferred; other mapping retained in primary report',worst_case=dict(run=worst.run,position=int(worst.j),error_nm=float(worst.error_nm)),no_model_or_measurement_changes=True)
 (out/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
