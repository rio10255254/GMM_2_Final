"""Check whether boundary contact in core-plus-halo PSFs hides a better fit."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import differential_evolution
from scipy.signal import fftconvolve

from screen_parametric_psfs import FOLDS, ROOT, RUN, TRUTH, XX, YY, kernel, fit_gain_and_error, grad_error


OPTIONS = {
    "gaussian_mixture_wide": ("gaussian_mixture", [(0.6,5.0),(.2,22.0),(.1,.95)]),
    "moffat_wide": ("moffat",[(.5,12.0),(.7,12.0)]),
}


def main():
    rows=[]
    rr=np.hypot(XX,YY)
    order=np.argsort(rr.ravel())
    for fold,(frames,train_path,hold_path,_) in FOLDS.items():
        train=cv2.imread(str(train_path),0)>0
        hold=cv2.imread(str(hold_path),0)>0
        for frame in frames:
            observed=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
            for name,(base_model,bounds) in OPTIONS.items():
                def objective(params):
                    psf=kernel(base_model,params)
                    prediction=fftconvolve(TRUTH,psf,mode='same')
                    return fit_gain_and_error(observed,prediction,train)[1]
                opt=differential_evolution(objective,bounds,seed=20260924+frame,maxiter=50,
                                           popsize=9,polish=True,tol=1e-5,workers=1)
                psf=kernel(base_model,opt.x)
                predicted=fftconvolve(TRUTH,psf,mode='same')
                gain,_=fit_gain_and_error(observed,predicted,train)
                y,p=observed[hold],gain*predicted[hold]
                cum=np.cumsum(psf.ravel()[order])
                rows.append(dict(fold=fold,frame=frame,model=name,params=json.dumps(opt.x.tolist()),
                                 optimizer_calls=int(opt.nfev),train_mse=float(opt.fun),
                                 heldout_mse=float(np.mean((y-p)**2)),
                                 heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                                 heldout_gradient_mae=grad_error(observed,gain*predicted,hold),
                                 psf_r50_px=float(rr.ravel()[order][np.searchsorted(cum,.5)]),
                                 psf_r90_px=float(rr.ravel()[order][np.searchsorted(cum,.9)]),
                                 outer_3px_energy=float(psf[:3].sum()+psf[-3:].sum()+psf[3:-3,:3].sum()+psf[3:-3,-3:].sum())))
            print(fold,frame,'done',flush=True)
    with (ROOT/'expanded_screen_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for fold,model in dict.fromkeys((r['fold'],r['model']) for r in rows):
        s=[r for r in rows if r['fold']==fold and r['model']==model]
        summary.append(dict(fold=fold,model=model,mean_heldout_mse=float(np.mean([r['heldout_mse'] for r in s])),
                            mean_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in s])),
                            max_outer_3px_energy=max(r['outer_3px_energy'] for r in s),
                            median_r90_px=float(np.median([r['psf_r90_px'] for r in s]))))
    (ROOT/'expanded_screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
