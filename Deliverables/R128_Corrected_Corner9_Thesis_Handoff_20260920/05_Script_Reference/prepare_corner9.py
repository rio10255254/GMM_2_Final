from common import *
import cv2,numpy as np,pandas as pd,time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=ROOT/'results/sem_corner9';OUT.mkdir(exist_ok=True)
plan=load(ROOT/'config/plan.json');old=pd.read_csv(ROOT/'results/lsc/tracking.csv');cfg=load(ROOT/'config/lsc_plan.json')
first=cv2.imread(plan['frames'][0]['source']['path'],0)
# Current image lower-right corner of the pillar array. Fixed before reading model results.
roi=first[670:810,1510:1670];_,mask=cv2.threshold(roi,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
_,_,stats,centers=cv2.connectedComponentsWithStats(mask)
use=(stats[:,4]>100)&(stats[:,4]<350)&(stats[:,2]>10)&(stats[:,2]<25)&(stats[:,3]>10)&(stats[:,3]<25)
c=centers[use]+[1510,670]
# Last three complete rows and columns next to the cross junction.
c=c[(c[:,0]>1570)&(c[:,1]>710)];c=c[np.argsort(c[:,1])]
rows=[]
for block in [c[i:i+3] for i in range(0,len(c),3)]:rows.extend(block[np.argsort(block[:,0])])
base=np.array(rows);assert base.shape==(9,2),base
cfg.update(base_centers=base.tolist(),selection='nine pillars nearest the lower-right cross junction within the historical SEM field; fixed 3x3; individual legacy IDs unresolved orientation',reference_status='SEM field candidate confirmed by topology; orientation/individual ID bridge pending',previous_center9_preserved=True)
save(ROOT/'config/sem_corner9_lsc_plan.json',cfg)
oldbase=old[(old.run==plan['frames'][0]['run'])&(old['index']==0)][['seed_x_px','seed_y_px']].to_numpy();group=old.groupby(['run','index']);tracking=[];maxoffset=0
for f in plan['frames']:
 im=cv2.imread(f['source']['path'],0);g=group.get_group((f['run'],f['index'])).sort_values('pillar_id');delta=np.median(g[['seed_x_px','seed_y_px']].to_numpy()-oldbase,axis=0)
 for pid,p in enumerate(base+delta,1):
  x,y=np.rint(p).astype(int);patch=im[y-13:y+14,x-13:x+14];_,m=cv2.threshold(patch,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU);_,_,st,cc=cv2.connectedComponentsWithStats(m);valid=(st[:,4]>80)&(st[:,4]<400);cc=cc[valid]+[x-13,y-13];assert len(cc)>0
  dist=np.linalg.norm(cc-p,axis=1);q=cc[np.argmin(dist)];assert dist.min()<5;maxoffset=max(maxoffset,float(dist.min()))
  tracking.append(dict(run=f['run'],run_index=f['run_index'],index=f['index'],pillar_id=pid,seed_x_px=q[0],seed_y_px=q[1]))
pd.DataFrame(tracking).to_csv(OUT/'tracking.csv',index=False)
fig,ax=plt.subplots(figsize=(11,8));ax.imshow(first,cmap='gray');ax.scatter(oldbase[:,0],oldbase[:,1],facecolors='none',edgecolors='orange',s=50,label='Previous center9');ax.scatter(base[:,0],base[:,1],facecolors='none',edgecolors='cyan',s=60,label='New cross-corner9')
for i,(x,y) in enumerate(base,1):ax.text(x+5,y-5,str(i),color='red',fontsize=9)
ax.legend();fig.tight_layout();fig.savefig(OUT/'selected_nine.png',dpi=180)
source=(ROOT/'scripts/lsc_measure.py').read_text(encoding='utf-8-sig').replace("config/lsc_plan.json","config/sem_corner9_lsc_plan.json").replace('results/lsc/','results/sem_corner9/')
(ROOT/'scripts/lsc_measure_corner9.py').write_text(source,encoding='utf-8')
save(OUT/'selection_verification.json',dict(frames=930,tracked_centers=len(tracking),maximum_local_reassociation_distance_px=maxoffset,base=base.tolist(),source='Raw only; prior Raw tracking supplies translation, local Raw components supply all new seeds',individual_sem_ids='not assigned'))
print(base);print('Tracked',len(tracking),'max offset',maxoffset)
