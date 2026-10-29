"""Show actual saved endpoint images with shared display levels and source-defined crops."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import cv2,pandas as pd
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
PROJECT_ROOT = Path(__file__).resolve().parents[3]
plt.rcParams['font.sans-serif']=['Microsoft JhengHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False

def main():
    out=ROOT/'results/visual_review_20260914';out.mkdir(exist_ok=False)
    r129=REPO/'Experiments/R129_OpticalPriorHybrid';pkg=Path(load(r129/'config/standalone_build.json')['path'])
    old=load(pkg/'results/training/r129_long_01/evaluations/step08192/real/complete.json')
    new=load(ROOT/'runs/v42_clean/evaluations/epoch32/real/complete.json')
    r129_image=next(x['image'] for x in old['images'] if x['name']=='sem14');r129_image=dict(path=str(pkg/r129_image['path']),sha256=r129_image['sha256'])
    v42_image=next(x['image'] for x in new['images'] if x['name']=='sem14')
    raw_item=next(x for x in load(ROOT/'validation/panel.json')['images'] if x['name']=='sem14')
    raw_image=dict(path=str(ROOT/raw_item['path']),sha256=raw_item['sha256'])
    ref=loadmat(ROOT/'validation/sem_reference.mat',variable_names=['global_index','opt_centers'])
    gy,gx=np.argwhere(ref['global_index']==18)[0];center=np.rint(ref['opt_centers'][int(gy)*6+int(gx)]).astype(int)-1
    box=[int(center[0]-52),int(center[1]-52),int(center[0]+52),int(center[1]+52)]
    cases=[dict(name='normal_50x',title='正常拍攝的柱體影像｜同一顆柱子放大',inputs=[raw_image,r129_image,v42_image],box=box,selection='Existing fixed pillar18, exposure14; selected by source grid, not candidate output')]
    sequence='20x_1um';idx=30;plan=load(ROOT/'config/final_evaluation_plan.json');frame=next(f for f in plan['frames'] if f['sequence']==sequence and f['frame_index']==idx)
    rec129=load(r129/'results/continuous_lsc/images'/sequence/f'frame_{idx:04d}'/'record.json')
    rec42=load(ROOT/'results/continuous/images'/sequence/f'frame_{idx:04d}'/'record.json')
    centers=pd.read_csv(r129/'results/continuous_lsc/measurements/Raw/centers.csv');group=centers[(centers.sequence==sequence)&(centers.frame_index==idx)]
    cx=int(round(group.predicted_x_px.median()));cy=int(round(group.predicted_y_px.median()))
    cases.append(dict(name='real_20x',title='20倍連續拍攝，第30張｜同一組柱子放大',inputs=[frame['source'],rec129['image'],rec42['image']],box=[cx-64,cy-64,cx+64,cy+64],selection='Fixed frame30; crop centered on Raw-predicted nine-pillar group, away from outer field guard'))
    records=[]
    for case in cases:
        images=[]
        for item in case['inputs']:
            assert sha(str(PROJECT_ROOT / item['path']))==item['sha256']
            im=cv2.imread(str(PROJECT_ROOT / item['path']),cv2.IMREAD_UNCHANGED);assert im.ndim==2 and im.dtype==np.uint8;images.append(im)
        assert len({im.shape for im in images})==1
        x0,y0,x1,y1=case['box'];h,w=images[0].shape;assert 0<=x0<x1<=w and 0<=y0<y1<=h
        fig,axes=plt.subplots(2,3,figsize=(12,7.3),layout='constrained',gridspec_kw={'height_ratios':[1,.75]})
        labels=['原始光學影像','R129 長訓練後','V42 乾淨重訓後']
        for col,(label,im) in enumerate(zip(labels,images)):
            axes[0,col].imshow(im,cmap='gray',vmin=0,vmax=255,interpolation='nearest')
            axes[0,col].add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='#edb553',linewidth=1.3))
            axes[0,col].set_title(label,fontsize=14);axes[0,col].axis('off')
            axes[1,col].imshow(im[y0:y1,x0:x1],cmap='gray',vmin=0,vmax=255,interpolation='nearest');axes[1,col].set_title('黃色框內，同位置放大',fontsize=10);axes[1,col].axis('off')
        fig.suptitle(case['title']+'\n三欄使用相同亮度尺度；均來自實際保存的重建影像',fontsize=14)
        target=out/(case['name']+'.png');fig.savefig(target,dpi=150);plt.close(fig)
        records.append(dict(**case,output=record(target),source_shape=list(images[0].shape),display_range=[0,255],same_crop_for_all=True,no_per_method_contrast_normalization=True))
        print(case['name'],'crop',case['box'],flush=True)
    save(out/'manifest.json',dict(created_utc=now(),source=record(__file__),R129_checkpoint='Existing step08192',V42_checkpoint='R130 fresh training epoch32/step04096',cases=records,original_sources_unchanged=True,no_new_model_inference_or_training=True))

if __name__=='__main__':main()
