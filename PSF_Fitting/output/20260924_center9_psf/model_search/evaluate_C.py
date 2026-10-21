"""One-time sealed confirmation for the chosen core-plus-halo PSF family."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter
from scipy.optimize import minimize_scalar
from scipy.signal import fftconvolve


ROOT=Path(__file__).resolve().parent
RUN=ROOT.parent
TRUTH=np.load(RUN/'sem_shape_forward_validation'/'gt_sem_contour_20x_float.npz')['image']
FRAMES=[3,8,14,20,22]
IDS=[36,35,34,30,29,28,24,23,22]
HELD=[35,28,24]
TILE=[69,150,231]


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def grad_mae(observed,prediction,mask):
    def normalized(a):
        gx=cv2.Sobel(a,cv2.CV_64F,1,0,ksize=3);gy=cv2.Sobel(a,cv2.CV_64F,0,1,ksize=3)
        z=np.hypot(gx,gy);return (z-z.min())/max(z.max()-z.min(),1e-12)
    return float(np.mean(np.abs(normalized(observed)[mask]-normalized(prediction)[mask])))


def main():
    frozen=json.loads((ROOT/'frozen_folds.json').read_text(encoding='utf-8'))
    selected=json.loads((ROOT/'selected_model_before_C.json').read_text(encoding='utf-8'))
    assert selected['selection_frozen_before_C'] and frozen['frozen_before_model_selection']
    assert selected['frozen_confirmation']['frames']==FRAMES
    assert selected['frozen_confirmation']['heldout_sem_ids']==HELD
    train=cv2.imread(str(ROOT/'loss_mask_train6_C.bmp'),0)>0
    hold=cv2.imread(str(ROOT/'loss_mask_hold3_C.bmp'),0)>0
    mixture=loadmat(ROOT/'mixture_bads_C'/'PSF_fitted_mixture.mat')['psf_grid'].reshape(101,101,5)
    original=loadmat(RUN/'parameter_audit'/'confirm_C_original'/'PSF_fitted_2D_FOVstack.mat')['psf_grid'].reshape(101,101,5)
    profiled=loadmat(RUN/'parameter_audit'/'confirm_C_profile_gain_0p1'/'PSF_fitted_2D_FOVstack.mat')['psf_grid'].reshape(101,101,5)
    july=loadmat(RUN.parent/'pillar_via_junction_psf_20260713'/'20x'/'fit_result'/'PSF_fitted_2D_FOVstack.mat')['psf_grid']
    july=july/july.sum()
    rows=[];per_pillar=[];display=None
    for index,frame in enumerate(FRAMES):
        observed=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
        kernels={'selected_mixture_BADs':mixture[:,:,index], 'original_disk_BADs':original[:,:,index],
                 'profiled_disk_BADs':profiled[:,:,index], 'july_psf':july}
        candidates={}
        for name,raw in kernels.items():
            psf=raw/raw.sum();candidates[name]=(fftconvolve(TRUTH,psf,mode='same'),psf)
        options=[]
        for sigma in np.arange(1,10.01,.1):
            p=gaussian_filter(TRUTH,float(sigma),mode='constant')
            gain=np.dot(observed[train],p[train])/np.dot(p[train],p[train])
            options.append((np.mean((observed[train]-gain*p[train])**2),float(sigma),p))
        _,sigma,gp=min(options,key=lambda r:r[0]);candidates['gaussian']=(gp,None)
        display_models={}
        for name,(pred,psf) in candidates.items():
            gain=float(np.dot(observed[train],pred[train])/np.dot(pred[train],pred[train]))
            scaled=gain*pred
            y,p=observed[hold],scaled[hold]
            if psf is None:
                peak=centroid=0.
            else:
                py,px=np.unravel_index(np.argmax(psf),psf.shape);yy,xx=np.mgrid[:101,:101]
                peak=float(np.hypot(px-50,py-50));centroid=float(np.hypot(np.sum((xx-50)*psf),np.sum((yy-50)*psf)))
            rows.append(dict(frame=frame,model=name,heldout_mse=float(np.mean((y-p)**2)),
                             heldout_mae=float(np.mean(np.abs(y-p))),heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                             heldout_gradient_mae=grad_mae(observed,scaled,hold),gain_from_train6=gain,
                             peak_offset_px=peak,centroid_offset_px=centroid,
                             gaussian_sigma_px=sigma if name=='gaussian' else ''))
            display_models[name]=scaled
            for pillar in HELD:
                k=IDS.index(pillar);row,col=divmod(k,3);x,y0=TILE[col],TILE[row];roi=np.s_[y0-10:y0+11,x-10:x+11]
                per_pillar.append(dict(frame=frame,sem_id=pillar,model=name,
                                       mse=float(np.mean((observed[roi]-scaled[roi])**2))))
        if frame==14:display=(observed,display_models)
    with (ROOT/'C_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (ROOT/'C_per_pillar.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(per_pillar[0]));writer.writeheader();writer.writerows(per_pillar)
    summary={}
    for name in dict.fromkeys(r['model'] for r in rows):
        subset=[r for r in rows if r['model']==name]
        summary[name]=dict(mean_heldout_mse=float(np.mean([r['heldout_mse'] for r in subset])),
                           mean_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in subset])),
                           mean_heldout_correlation=float(np.mean([r['heldout_correlation'] for r in subset])),
                           max_peak_offset_px=max(r['peak_offset_px'] for r in subset),
                           max_centroid_offset_px=max(r['centroid_offset_px'] for r in subset))
    pivot={(r['frame'],r['model']):r['heldout_mse'] for r in rows}
    selected_result=summary['selected_mixture_BADs'];gaussian=summary['gaussian'];original=summary['original_disk_BADs']
    gates={
       'mean_20_percent_better_than_gaussian':selected_result['mean_heldout_mse']<.8*gaussian['mean_heldout_mse'],
       'mean_20_percent_better_than_original_BADs':selected_result['mean_heldout_mse']<.8*original['mean_heldout_mse'],
       'better_than_gaussian_all_five_frames':all(pivot[(f,'selected_mixture_BADs')]<pivot[(f,'gaussian')] for f in FRAMES),
       'gradient_error_lower_than_gaussian':selected_result['mean_heldout_gradient_mae']<gaussian['mean_heldout_gradient_mae'],
       'zero_peak_offset':selected_result['max_peak_offset_px']==0,
       'max_centroid_under_point_one_px':selected_result['max_centroid_offset_px']<.1,
    }
    verdict={'status':'PASS_predictive_research_candidate' if all(gates.values()) else 'FAIL_frozen_gates',
             'frames':FRAMES,'heldout_sem_ids':HELD,'summary':summary,'gates':gates,
             'scope':'Different camera views of one physical nine-pillar set, not independent specimen accuracy'}
    (ROOT/'C_verdict.json').write_text(json.dumps(verdict,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(verdict,indent=2))

    observed,models=display
    fig,axes=plt.subplots(3,5,figsize=(12,7),constrained_layout=True)
    for row,pillar in enumerate(HELD):
        k=IDS.index(pillar);gr,gc=divmod(k,3);x,y=TILE[gc],TILE[gr];roi=np.s_[y-12:y+13,x-12:x+13]
        panels=[observed[roi],models['selected_mixture_BADs'][roi],models['gaussian'][roi],
                models['original_disk_BADs'][roi],np.abs(observed[roi]-models['selected_mixture_BADs'][roi])]
        titles=['New photo','Selected core+halo','One Gaussian','Original BADS','Absolute difference']
        for col,(panel,title) in enumerate(zip(panels,titles)):
            ax=axes[row,col];ax.imshow(panel,cmap='magma' if col==4 else 'gray',vmin=0,vmax=.35 if col==4 else 1)
            if row==0:ax.set_title(title,fontsize=10)
            if col==0:ax.set_ylabel(f'SEM {pillar}')
            ax.set_xticks([]);ax.set_yticks([])
    fig.suptitle('Frozen C check, frame 14: P-SEM outline convolved to predict excluded pillars')
    fig.savefig(ROOT/'C_frame14_comparison.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':main()
