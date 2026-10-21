"""Evaluate fixed PSF candidates against P-SEM silhouettes on sealed folds."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent
TRUTH = np.load(RUN / "sem_shape_forward_validation" / "gt_sem_contour_20x_float.npz")["image"]
FOLDS = {
    "A": ([1,13,25], RUN / "fit_input" / "loss_mask_train6.bmp", RUN / "fit_input" / "loss_mask_hold3.bmp"),
    "B": ([4,7,12,18,23], RUN / "fit_input" / "loss_mask_train6_B.bmp", RUN / "fit_input" / "loss_mask_hold3_B.bmp"),
    "C": ([3,8,14,20,22], ROOT / "loss_mask_train6_C.bmp", ROOT / "loss_mask_hold3_C.bmp"),
}


def model_paths(fold):
    paths=[]
    for directory in sorted(ROOT.iterdir()):
        if directory.is_dir() and directory.name.endswith('_'+fold):
            if (directory / "PSF_fitted_2D_FOVstack.mat").is_file():
                paths.append((directory.name,directory / "PSF_fitted_2D_FOVstack.mat"))
    if fold == 'A':
        paths.extend([
            ('disk_original_A', RUN / 'cv_bounds_2' / 'PSF_fitted_2D_FOVstack.mat'),
            ('disk_profile_gain_A', RUN / 'parameter_audit' / 'profile_gain_0p1' / 'PSF_fitted_2D_FOVstack.mat'),
        ])
    if fold == 'B':
        paths.extend([
            ('disk_original_B', RUN / 'parameter_audit' / 'confirm_original' / 'PSF_fitted_2D_FOVstack.mat'),
            ('disk_profile_gain_B', RUN / 'parameter_audit' / 'confirm_profile_gain_0p1' / 'PSF_fitted_2D_FOVstack.mat'),
        ])
    return paths


def score(observed, prediction, train, held):
    gain=float(np.dot(observed[train],prediction[train])/np.dot(prediction[train],prediction[train]))
    y,p=observed[held],gain*prediction[held]
    return gain,float(np.mean((y-p)**2)),float(np.mean(np.abs(y-p))),float(np.corrcoef(y,p)[0,1])


def gradient_error(observed,prediction,held):
    def norm_grad(a):
        x=cv2.Sobel(a,cv2.CV_64F,1,0,ksize=3);y=cv2.Sobel(a,cv2.CV_64F,0,1,ksize=3)
        z=np.hypot(x,y);return (z-z.min())/max(z.max()-z.min(),1e-12)
    return float(np.mean(np.abs(norm_grad(observed)[held]-norm_grad(prediction)[held])))


def evaluate(folds=('A','B')):
    frozen=json.loads((ROOT/'frozen_folds.json').read_text(encoding='utf-8'))
    assert frozen['frozen_before_model_selection'] is True
    rows=[]
    for fold in folds:
        frames,train_path,hold_path=FOLDS[fold]
        train=cv2.imread(str(train_path),0)>0;held=cv2.imread(str(hold_path),0)>0
        assert train.sum()==6*317 and held.sum()==3*317
        paths=model_paths(fold)
        for name,path in paths:
            data=loadmat(path,variable_names=['psf_grid','subset_indices'])
            psfs=data['psf_grid'].reshape(101,101,len(frames))
            assert np.array_equal(data['subset_indices'].ravel(),frames)
            for idx,frame in enumerate(frames):
                observed=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
                psf=psfs[:,:,idx]/psfs[:,:,idx].sum()
                pred=fftconvolve(TRUTH,psf,mode='same')
                gain,mse,mae,corr=score(observed,pred,train,held)
                yy,xx=np.mgrid[:101,:101];py,px=np.unravel_index(np.argmax(psf),psf.shape)
                rows.append(dict(fold=fold,frame=frame,model=name,gain=gain,heldout_mse=mse,heldout_mae=mae,
                                 heldout_correlation=corr,heldout_gradient_mae=gradient_error(observed,gain*pred,held),
                                 peak_offset_px=float(np.hypot(px-50,py-50)),
                                 centroid_offset_px=float(np.hypot(np.sum((xx-50)*psf),np.sum((yy-50)*psf)))))
        # Gaussian control gets the same six-pillar training region.
        for frame in frames:
            observed=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
            choices=[]
            for sigma in np.arange(1,10.01,.1):
                pred=gaussian_filter(TRUTH,float(sigma),mode='constant')
                _,mse,_,_=score(observed,pred,train,train)
                choices.append((mse,float(sigma),pred))
            _,sigma,pred=min(choices,key=lambda r:r[0])
            gain,mse,mae,corr=score(observed,pred,train,held)
            rows.append(dict(fold=fold,frame=frame,model='gaussian_'+fold,gain=gain,heldout_mse=mse,
                             heldout_mae=mae,heldout_correlation=corr,
                             heldout_gradient_mae=gradient_error(observed,gain*pred,held),
                             peak_offset_px=0,centroid_offset_px=0,gaussian_sigma_px=sigma))
    return rows


def main():
    rows=evaluate()
    with (ROOT/'development_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));writer.writeheader();writer.writerows(rows)
    summary=[]
    for fold,model in dict.fromkeys((r['fold'],r['model']) for r in rows):
        subset=[r for r in rows if r['fold']==fold and r['model']==model]
        summary.append(dict(fold=fold,model=model,
                            mean_heldout_mse=float(np.mean([r['heldout_mse'] for r in subset])),
                            mean_heldout_correlation=float(np.mean([r['heldout_correlation'] for r in subset])),
                            mean_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in subset])),
                            max_peak_offset_px=max(r['peak_offset_px'] for r in subset),
                            max_centroid_offset_px=max(r['centroid_offset_px'] for r in subset)))
    (ROOT/'development_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
