from pathlib import Path
import json,numpy as np,pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];B=R/'results/sem_corner9';S=B/'shape_size';OLD=R.parent/'R135_UnifiedModelComparison'
mapping=json.loads((B/'sem_mapping_candidates.json').read_text());ids=sorted(mapping[0]['sem_ids_by_new_nine']);assert ids==sorted(mapping[1]['sem_ids_by_new_nine'])
points=np.load(OLD/'results/Raw/sem/points.npz');scale=json.loads((OLD/'results/Raw/sem/complete.json').read_text())['scale_nm_per_px'];truth={};diam={};theta=np.linspace(0,2*np.pi,720,endpoint=False)
for pid in ids:
 p=points[f'SEM_{pid}'];z=p-p.mean(0)
 def fun(c):
  d=np.linalg.norm(z-c,axis=1);return d-d.mean()
 c=least_squares(fun,[0,0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x
 truth[pid]=(z-c)*scale;diam[pid]=float(2*np.linalg.norm(truth[pid],axis=1).mean())
def radial(p):
 a=np.mod(np.arctan2(p[:,1],p[:,0]),2*np.pi);r=np.linalg.norm(p,axis=1);ix=np.argsort(a);a,r=a[ix],r[ix]
 return np.interp(theta,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])
pd.DataFrame([dict(sem_id=i,diameter_nm=diam[i]) for i in ids]).to_csv(B/'sem_nine_reference_sizes.csv',index=False)
rows=[];per=[];summary=pd.read_csv(S/'summary.csv');allc=pd.read_csv(S/'per_contour.csv');models=['Raw','R61','R129','R128'];colors=['#777777','#df8636','#2088aa','#9356ad'];means={}
for model in models:
 p=np.load(S/f'{model}_radial_profiles.npz')['radius_nm'].astype(float);means[model]=p.mean(axis=(0,1));d=allc[allc.model==model].sort_values(['run_index','index','pillar_id']).diameter_nm.to_numpy().reshape(30,31,9)
 group=d.mean(axis=(1,2))-np.mean(list(diam.values()));r=summary.loc[summary.model==model].iloc[0]
 rows.append(dict(model=model,mean_diameter_nm=d.mean(),SEM_group_mean_diameter_nm=np.mean(list(diam.values())),group_signed_diameter_difference_nm=group.mean(),group_difference_between_scan_sd_nm=group.std(ddof=1)))
 for mi,m in enumerate(mapping):
  refs=[]
  for pid in m['sem_ids_by_new_nine']:
   q=truth[pid].copy()
   if m['candidate']['flip']:q[:,0]*=-1
   for k in range(m['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
   refs.append(radial(q))
  refs=np.array(refs);ds=np.array([diam[pid] for pid in m['sem_ids_by_new_nine']]);full=np.abs(p-refs).mean(axis=-1);sh=np.abs((p-p.mean(axis=-1,keepdims=True))-(refs-refs.mean(axis=-1,keepdims=True))).mean(axis=-1);de=np.abs(d-ds)
  for run in range(30):per.append(dict(model=model,mapping_candidate=mi+1,run_index=run+1,diameter_mae_nm=de[run].mean(),radial_mae_nm=full[run].mean(),shape_mae_nm=sh[run].mean()))
pd.DataFrame(rows).to_csv(B/'sem_group_size_comparison.csv',index=False);pd.DataFrame(per).to_csv(B/'sem_mapping_sensitivity_per_scan.csv',index=False);pd.DataFrame(per).groupby(['model','mapping_candidate']).mean(numeric_only=True).drop(columns='run_index').to_csv(B/'sem_mapping_sensitivity_summary.csv')
for mi,m in enumerate(mapping):
 fig,axes=plt.subplots(3,4,figsize=(12,9))
 for row,local in enumerate([0,4,8]):
  pid=m['sem_ids_by_new_nine'][local];q=truth[pid].copy()
  if m['candidate']['flip']:q[:,0]*=-1
  for k in range(m['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
  for col,(model,color) in enumerate(zip(models,colors)):
   ax=axes[row,col];p=np.load(S/f'{model}_radial_profiles.npz')['radius_nm'][:,0,local]
   for sig in p:ax.plot(sig*np.cos(theta),sig*np.sin(theta),color=color,alpha=.15,lw=.8)
   qq=np.vstack([q,q[0]]);ax.plot(qq[:,0],qq[:,1],color='black',lw=1.2);ax.set_aspect('equal');ax.set_xlim(-1650,1650);ax.set_ylim(-1650,1650);ax.set_title(f'{model}: new {local+1} / SEM {pid}');ax.set_xlabel('x (nm)');ax.set_ylabel('y (nm)')
 fig.suptitle(f'Corner9: 30 repeats at position1; SEM mapping candidate {mi+1} (orientation unresolved)');fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(B/f'sem_contours_candidate{mi+1}.png',dpi=170);plt.close(fig)
print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(per).groupby(['model','mapping_candidate']).mean().to_string())
