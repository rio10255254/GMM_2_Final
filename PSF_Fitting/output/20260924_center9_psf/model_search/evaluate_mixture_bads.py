"""Confirm that bundled BADS reproduces the screened centered two-Gaussian PSF."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.signal import fftconvolve

from screen_parametric_psfs import FOLDS, ROOT, RUN, TRUTH, grad_error


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    screened=read_csv(ROOT/'expanded_screen_metrics.csv')
    initial_screen=read_csv(ROOT/'parametric_screen_metrics.csv')
    rows=[]
    for fold,(frames,train_path,hold_path,_) in FOLDS.items():
        d=ROOT/f'mixture_bads_{fold}'
        mat=loadmat(d/'PSF_fitted_mixture.mat')
        psfs=mat['psf_grid'].reshape(101,101,len(frames))
        assert np.array_equal(mat['frames'].ravel(),frames)
        fit_rows=read_csv(d/'batch_results.csv')
        train=cv2.imread(str(train_path),0)>0
        hold=cv2.imread(str(hold_path),0)>0
        for index,frame in enumerate(frames):
            observed=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
            psf=psfs[:,:,index]/psfs[:,:,index].sum()
            predicted=fftconvolve(TRUTH,psf,mode='same')
            gain=float(np.dot(observed[train],predicted[train])/np.dot(predicted[train],predicted[train]))
            y,p=observed[hold],gain*predicted[hold]
            de=next(r for r in screened if r['fold']==fold and r['frame']==str(frame) and r['model']=='gaussian_mixture_wide')
            rows.append(dict(fold=fold,frame=frame,model='BADS_core_halo',
                             sigma_core_px=float(fit_rows[index]['sigma_core_px']),
                             sigma_halo_px=float(fit_rows[index]['sigma_halo_px']),
                             core_energy_weight=float(fit_rows[index]['core_energy_weight']),
                             train_mse=float(fit_rows[index]['train_mse']),
                             heldout_mse=float(np.mean((y-p)**2)),
                             heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                             heldout_gradient_mae=grad_error(observed,gain*predicted,hold),
                             peak_offset_px=float(fit_rows[index]['peak_offset_px']),
                             centroid_offset_px=float(fit_rows[index]['centroid_offset_px']),
                             BADS_seconds=float(fit_rows[index]['seconds']),
                             BADS_exitflag=int(fit_rows[index]['exitflag']),
                             DE_screen_heldout_mse=float(de['heldout_mse'])))
    with (ROOT/'mixture_bads_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for fold in FOLDS:
        s=[r for r in rows if r['fold']==fold]
        gaussian=[r for r in initial_screen if r['fold']==fold and r['model']=='gaussian']
        summary.append(dict(fold=fold,frames=len(s),
                            mean_BADS_heldout_mse=float(np.mean([r['heldout_mse'] for r in s])),
                            mean_DE_heldout_mse=float(np.mean([r['DE_screen_heldout_mse'] for r in s])),
                            mean_gaussian_heldout_mse=float(np.mean([float(r['heldout_mse']) for r in gaussian])),
                            mean_BADS_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in s])),
                            max_peak_offset_px=max(r['peak_offset_px'] for r in s),
                            max_centroid_offset_px=max(r['centroid_offset_px'] for r in s),
                            mean_BADS_seconds=float(np.mean([r['BADS_seconds'] for r in s]))))
    (ROOT/'mixture_bads_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
