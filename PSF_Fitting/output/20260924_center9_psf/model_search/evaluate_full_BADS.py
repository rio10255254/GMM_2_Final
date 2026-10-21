"""Check BADS core-plus-halo fit on complete SEM/optical pillar patches."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.signal import fftconvolve

from screen_parametric_psfs import ROOT,RUN,TRUTH,grad_error


def records(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def main():
    folds=json.loads((ROOT/'full_patch_folds.json').read_text(encoding='utf-8'))['folds']
    screened=records(ROOT/'full_patch_screen_metrics.csv')
    rows=[]
    for fold,info in folds.items():
        if fold=='E':continue
        frames=info['frames']
        fit=loadmat(ROOT/f'mixture_full_{fold}'/'PSF_fitted_mixture.mat')
        psfs=fit['psf_grid'].reshape(101,101,len(frames))
        assert np.array_equal(fit['frames'].ravel(),frames)
        batch=records(ROOT/f'mixture_full_{fold}'/'batch_results.csv')
        train=cv2.imread(str(ROOT/f'full_train6_{fold}.bmp'),0)>0
        hold=cv2.imread(str(ROOT/f'full_hold3_{fold}.bmp'),0)>0
        for index,frame in enumerate(frames):
            observed=cv2.imread(str(RUN/'parameter_audit'/'wide_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
            psf=psfs[:,:,index]/psfs[:,:,index].sum()
            pred=fftconvolve(TRUTH,psf,mode='same')
            gain=float(np.dot(observed[train],pred[train])/np.dot(pred[train],pred[train]))
            y,p=observed[hold],gain*pred[hold]
            gauss=next(r for r in screened if r['fold']==fold and r['frame']==str(frame) and r['model']=='gaussian')
            de=next(r for r in screened if r['fold']==fold and r['frame']==str(frame) and r['model']=='gaussian_mixture')
            rows.append(dict(fold=fold,frame=frame,model='BADS_core_halo_full',
                             heldout_mse=float(np.mean((y-p)**2)),
                             heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                             heldout_gradient_mae=grad_error(observed,gain*pred,hold),
                             gaussian_heldout_mse=float(gauss['heldout_mse']),
                             differential_evolution_heldout_mse=float(de['heldout_mse']),
                             peak_offset_px=float(batch[index]['peak_offset_px']),
                             centroid_offset_px=float(batch[index]['centroid_offset_px']),
                             exitflag=int(batch[index]['exitflag']),
                             sigma_core_px=float(batch[index]['sigma_core_px']),
                             sigma_halo_px=float(batch[index]['sigma_halo_px']),
                             core_energy_weight=float(batch[index]['core_energy_weight'])))
    with (ROOT/'full_BADS_development_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for fold in ('A','B','C','D'):
        s=[r for r in rows if r['fold']==fold]
        summary.append(dict(fold=fold,frames=len(s),
                            mean_BADs_heldout_mse=float(np.mean([r['heldout_mse'] for r in s])),
                            mean_gaussian_heldout_mse=float(np.mean([r['gaussian_heldout_mse'] for r in s])),
                            mean_DE_heldout_mse=float(np.mean([r['differential_evolution_heldout_mse'] for r in s])),
                            mean_BADs_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in s])),
                            BADs_better_than_gaussian_frames=sum(r['heldout_mse']<r['gaussian_heldout_mse'] for r in s),
                            max_centroid_offset_px=max(r['centroid_offset_px'] for r in s)))
    (ROOT/'full_BADS_development_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
