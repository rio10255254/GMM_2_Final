import cv2,numpy as np,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import loadmat
R=Path(__file__).resolve().parents[1];O=R/'results/sem_reference_followup'
old=cv2.imread('H:/From_2TB_D_disk/13_thesis/matlab/ch4/SEMdataset/image_B2D/13.bmp',0)
crop=cv2.imread('H:/From_2TB_D_disk/13_thesis/matlab/ch4/SEMdataset/image_cropped/13.bmp',0)
new=cv2.imread('C:/Users/Rio/Downloads/20260902_100MF_uncertainty/20260902_100MF_uncertainty/20260903/001804_XY_0/1.bmp',0)
res=cv2.matchTemplate(old,crop,cv2.TM_CCOEFF_NORMED);_,corr,_,loc=cv2.minMaxLoc(res)
print('Legacy crop location',loc,'correlation',corr,flush=True)
ref=loadmat(R.parent/'R135_UnifiedModelComparison/validation/sem_reference.mat');cent=ref['opt_centers']+loc
scale=28.9330637762/float(ref['opt_pitch'].item()); candidates=[]
for flip in [False,True]:
 for k in range(4):
  im=old[:,::-1] if flip else old
  im=np.rot90(im,k);small=cv2.resize(im,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
  # Blur to avoid high-frequency SEM-independent edge emphasis.
  mat=cv2.matchTemplate(cv2.GaussianBlur(new,(5,5),1),cv2.GaussianBlur(small,(5,5),1),cv2.TM_CCOEFF_NORMED)
  _,score,_,xy=cv2.minMaxLoc(mat);candidates.append(dict(flip=flip,k=k,correlation=score,xy=xy))
best=max(candidates,key=lambda x:x['correlation']);print(json.dumps(candidates,indent=2),flush=True)
points=cent.copy();h,w=old.shape
if best['flip']:points[:,0]=w-1-points[:,0]
for k in range(best['k']):points=np.c_[points[:,1],w-1-points[:,0]];h,w=w,h
points=points*scale+best['xy']
cfg=json.loads((R/'config/lsc_plan.json').read_text(encoding='utf-8-sig'))
import pandas as pd
targets=pd.read_csv(R/'results/lsc/centers/Raw/001804_XY_0.csv').query('index==0')[['center_x_px','center_y_px']].to_numpy()
fig,ax=plt.subplots(figsize=(12,9));ax.imshow(new,cmap='gray');ax.scatter(points[:,0],points[:,1],s=50,facecolors='none',edgecolors='cyan',label='Historical SEM 36 (provisional image match)');ax.scatter(targets[:,0],targets[:,1],s=80,facecolors='none',edgecolors='orange',label='Current 9 targets');ax.legend();ax.set_title(f'Whole-field match: correlation {best["correlation"]:.3f}; not yet accepted as identity proof');fig.tight_layout();fig.savefig(O/'field_match_provisional.png',dpi=170)
(O/'field_match_provisional.json').write_text(json.dumps(dict(legacy_crop_xy=loc,legacy_crop_correlation=corr,scale=scale,candidates=candidates,predicted_sem_centers=points.tolist(),current_targets=targets.tolist()),indent=2),encoding='utf-8')
