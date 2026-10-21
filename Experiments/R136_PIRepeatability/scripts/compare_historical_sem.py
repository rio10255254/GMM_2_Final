import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,json
sys.dont_write_bytecode=True
import numpy as np,pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/sem_reference_followup';OLD=R.parent/'R135_UnifiedModelComparison'
sys.path.insert(0,str(OLD));sys.path.insert(0,str(OLD/'scripts'))
from sem_metrics import score
out=O/'R129_original80'
table,points,info=score(out/'sem_masks.mat',OLD/'validation/sem_reference.mat')
table.to_csv(out/'measurements.csv',index=False);np.savez_compressed(out/'points.npz',**points);(out/'complete.json').write_text(json.dumps(info,indent=2))
models=['Raw','R61','R129','R128'];colors=['#777777','#df8636','#2088aa','#9356ad'];data={};tables=[];summary=[]
for model in models:
 p=out if model=='R129' else OLD/f'results/{model}/sem'
 df=pd.read_csv(p/'measurements.csv');df['model']=model;tables.append(df)
 meta=json.loads((p/'complete.json').read_text());sc=meta['scale_nm_per_px'];assert abs(sc-info['scale_nm_per_px'])<1e-9
 summary.append({'model':model,**df.groupby('pillar')[['diameter_error_nm','centered_shape_nm','radial_nm']].median().median().to_dict()})
 data[model]=np.load(p/'points.npz')
pd.concat(tables).to_csv(O/'historical_sem_per_pillar.csv',index=False);pd.DataFrame(summary).to_csv(O/'historical_sem_summary.csv',index=False)
def center(p):
 o=p.mean(0);z=p-o
 def f(c):
  d=np.linalg.norm(z-c,axis=1);return d-d.mean()
 c=least_squares(f,[0,0],xtol=1e-12,ftol=1e-12,gtol=1e-12).x
 return (z-c)*sc
fig,axes=plt.subplots(6,6,figsize=(15,15))
for pid,ax in enumerate(axes.flat,1):
 for model,color in zip(models,colors):
  for exp in [13,14,15]:
   p=center(data[model][f'{exp}_{pid}']);p=np.vstack([p,p[0]]);ax.plot(p[:,0],p[:,1],color=color,alpha=.5,lw=.8)
 p=center(data['Raw'][f'SEM_{pid}']);p=np.vstack([p,p[0]]);ax.plot(p[:,0],p[:,1],color='black',lw=1.4)
 ax.set_aspect('equal');ax.set_xlim(-1550,1550);ax.set_ylim(-1550,1550);ax.set_title(f'SEM ID {pid}',fontsize=9);ax.tick_params(labelsize=6)
from matplotlib.lines import Line2D
fig.legend([Line2D([0],[0],color=c) for c in ['black']+colors],['SEM']+models,loc='upper center',ncol=5)
fig.suptitle('Historical paired sample: 36 pillars, 3 exposures; coordinates in nm',y=.975)
fig.tight_layout(rect=[0,0,1,.955]);fig.savefig(O/'historical_sem_36_overlays.png',dpi=180)
print(pd.DataFrame(summary).to_string(index=False),flush=True)
