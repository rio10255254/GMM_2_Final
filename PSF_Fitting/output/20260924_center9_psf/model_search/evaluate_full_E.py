"""One-time frozen-E verdict on complete 25x25 measured pillar patches."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat
from scipy.optimize import minimize_scalar
from scipy.signal import fftconvolve

from screen_parametric_psfs import ROOT,RUN,TRUTH,kernel,grad_error,XX,YY


FRAMES=[5,9,11,16,19,21]
IDS=[36,35,34,30,29,28,24,23,22]
HELD=[34,29,24]
TILE=[69,150,231]


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def main():
    frozen=json.loads((ROOT/'full_patch_folds.json').read_text(encoding='utf-8'))
    selected=json.loads((ROOT/'selected_full_patch_before_E.json').read_text(encoding='utf-8'))
    assert selected['selection_frozen_before_E'] and frozen['frozen_before_full_patch_model_search']
    assert selected['frozen_final_fold']['frames']==FRAMES
    assert selected['frozen_final_fold']['heldout_sem_ids']==HELD
    train=cv2.imread(str(ROOT/'full_train6_E.bmp'),0)>0
    hold=cv2.imread(str(ROOT/'full_hold3_E.bmp'),0)>0
    assert train.sum()==6*625 and hold.sum()==3*625
    mixture_data=loadmat(ROOT/'mixture_full_E'/'PSF_fitted_mixture.mat')
    mixture=mixture_data['psf_grid'].reshape(101,101,6)
    assert np.array_equal(mixture_data['frames'].ravel(),FRAMES)
    original=loadmat(ROOT/'original_full_E'/'PSF_fitted_2D_FOVstack.mat')['psf_grid'].reshape(101,101,6)
    profiled=loadmat(ROOT/'profile_full_E'/'PSF_fitted_2D_FOVstack.mat')['psf_grid'].reshape(101,101,6)
    mix_rows=read_csv(ROOT/'mixture_full_E'/'batch_results.csv')
    assert len(mix_rows)==6 and all(int(r['exitflag'])>0 for r in mix_rows)
    results=[];per_pillar=[];display=None
    for index,frame in enumerate(FRAMES):
        observed=cv2.imread(str(RUN/'parameter_audit'/'wide_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
        psfs={'selected_core_halo_BADs':mixture[:,:,index],
              'original_disk_BADs':original[:,:,index],
              'profiled_disk_BADs':profiled[:,:,index]}
        def gaussian_training_loss(sigma):
            pred=fftconvolve(TRUTH,kernel('gaussian',[sigma]),mode='same')
            g=np.dot(observed[train],pred[train])/np.dot(pred[train],pred[train])
            return float(np.mean((observed[train]-g*pred[train])**2))
        opt=minimize_scalar(gaussian_training_loss,bounds=(1,7),method='bounded',options={'xatol':1e-3})
        psfs['gaussian']=kernel('gaussian',[float(opt.x)])
        scaled={}
        for name,raw in psfs.items():
            psf=raw/raw.sum()
            pred=fftconvolve(TRUTH,psf,mode='same')
            gain=float(np.dot(observed[train],pred[train])/np.dot(pred[train],pred[train]))
            prediction=gain*pred
            y,p=observed[hold],prediction[hold]
            py,px=np.unravel_index(np.argmax(psf),psf.shape)
            cent=float(np.hypot(np.sum(XX*psf),np.sum(YY*psf)))
            edge=float(psf[:3].sum()+psf[-3:].sum()+psf[3:-3,:3].sum()+psf[3:-3,-3:].sum())
            results.append(dict(frame=frame,model=name,heldout_mse=float(np.mean((y-p)**2)),
                                heldout_mae=float(np.mean(np.abs(y-p))),
                                heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                                heldout_gradient_mae=grad_error(observed,prediction,hold),
                                gain_from_train6=gain,peak_offset_px=float(np.hypot(px-50,py-50)),
                                centroid_offset_px=cent,outer_3px_energy_fraction=edge,
                                gaussian_sigma_px=float(opt.x) if name=='gaussian' else ''))
            scaled[name]=prediction
            for pillar in HELD:
                n=IDS.index(pillar);row,col=divmod(n,3);x,y0=TILE[col],TILE[row]
                roi=np.s_[y0-12:y0+13,x-12:x+13]
                per_pillar.append(dict(frame=frame,sem_id=pillar,model=name,
                                       full_patch_mse=float(np.mean((observed[roi]-prediction[roi])**2))))
        if frame==16:display=(observed,scaled)
    with (ROOT/'E_full_patch_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]));writer.writeheader();writer.writerows(results)
    with (ROOT/'E_full_patch_per_pillar.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(per_pillar[0]));writer.writeheader();writer.writerows(per_pillar)
    summary={}
    for name in dict.fromkeys(r['model'] for r in results):
        s=[r for r in results if r['model']==name]
        summary[name]=dict(mean_heldout_mse=float(np.mean([r['heldout_mse'] for r in s])),
                           mean_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in s])),
                           mean_heldout_correlation=float(np.mean([r['heldout_correlation'] for r in s])),
                           max_peak_offset_px=max(r['peak_offset_px'] for r in s),
                           max_centroid_offset_px=max(r['centroid_offset_px'] for r in s),
                           max_outer_3px_energy_fraction=max(r['outer_3px_energy_fraction'] for r in s))
    pick=summary['selected_core_halo_BADs'];gauss=summary['gaussian'];old=summary['original_disk_BADs']
    by_key={(r['frame'],r['model']):r['heldout_mse'] for r in results}
    gates={
      'mean_10_percent_better_than_gaussian':pick['mean_heldout_mse']<.9*gauss['mean_heldout_mse'],
      'mean_10_percent_better_than_original_BADs':pick['mean_heldout_mse']<.9*old['mean_heldout_mse'],
      'better_than_gaussian_all_six_frames':all(by_key[(f,'selected_core_halo_BADs')]<by_key[(f,'gaussian')] for f in FRAMES),
      'gradient_error_lower_than_gaussian':pick['mean_heldout_gradient_mae']<gauss['mean_heldout_gradient_mae'],
      'zero_peak_offsets':pick['max_peak_offset_px']==0,
      'centroid_below_point_one_px':pick['max_centroid_offset_px']<.1,
      'outer_energy_below_point_zero_zero_one':pick['max_outer_3px_energy_fraction']<.001,
      'all_BADS_exitflags_positive':all(int(r['exitflag'])>0 for r in mix_rows),
    }
    verdict={'status':'PASS_predictive_research_PSF' if all(gates.values()) else 'FAIL_frozen_full_patch_gates',
             'frames':FRAMES,'heldout_sem_ids':HELD,'summary':summary,'gates':gates,
             'scope':'Six new camera views of the same nine physical pillars; no independent specimen PSF-trueness claim'}
    (ROOT/'E_full_patch_verdict.json').write_text(json.dumps(verdict,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(verdict,indent=2))

    image,models=display
    fig,axes=plt.subplots(3,5,figsize=(12,7),constrained_layout=True)
    for row,pillar in enumerate(HELD):
        n=IDS.index(pillar);r,c=divmod(n,3);x,y=TILE[c],TILE[r];region=np.s_[y-12:y+13,x-12:x+13]
        panels=[image[region],models['selected_core_halo_BADs'][region],models['gaussian'][region],
                models['original_disk_BADs'][region],np.abs(image[region]-models['selected_core_halo_BADs'][region])]
        titles=['Photo','Core + halo PSF','Single Gaussian','Original BADS','Absolute difference']
        for col,(panel,title) in enumerate(zip(panels,titles)):
            ax=axes[row,col];ax.imshow(panel,cmap='magma' if col==4 else 'gray',vmin=0,vmax=.3 if col==4 else 1)
            if row==0:ax.set_title(title,fontsize=10)
            if col==0:ax.set_ylabel(f'SEM {pillar}')
            ax.set_xticks([]);ax.set_yticks([])
    fig.suptitle('Frozen E, frame 16: full measured 25x25 P-SEM pillar patches')
    fig.savefig(ROOT/'E_frame16_full_patch.png',dpi=170)
    plt.close(fig)


if __name__=='__main__':main()
