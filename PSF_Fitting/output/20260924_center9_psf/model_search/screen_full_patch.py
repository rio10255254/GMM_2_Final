"""Fit centered PSF families against complete valid 25x25 optical pillar patches."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import differential_evolution, minimize_scalar
from scipy.signal import fftconvolve

from screen_parametric_psfs import ROOT,RUN,TRUTH,kernel,fit_gain_and_error,grad_error,XX,YY


BOUNDS={
 'elliptic_gaussian':[(1,7),(1,7),(-np.pi/2,np.pi/2)],
 'gaussian_mixture':[(.6,5),(.2,22),(.1,.95)],
 'moffat':[(.5,12),(.7,12)],
}


def main():
    fold_manifest=json.loads((ROOT/'full_patch_folds.json').read_text(encoding='utf-8'))
    assert fold_manifest['frozen_before_full_patch_model_search']
    rows=[]
    yy,xx=np.mgrid[-50:51,-50:51]
    for fold,info in fold_manifest['folds'].items():
        if fold=='E':continue
        train=cv2.imread(str(ROOT/f'full_train6_{fold}.bmp'),0)>0
        hold=cv2.imread(str(ROOT/f'full_hold3_{fold}.bmp'),0)>0
        for frame in info['frames']:
            observed=cv2.imread(str(RUN/'parameter_audit'/'wide_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
            for name in ['gaussian','elliptic_gaussian','gaussian_mixture','moffat']:
                def objective(params):
                    psf=kernel(name,params)
                    predicted=fftconvolve(TRUTH,psf,mode='same')
                    return fit_gain_and_error(observed,predicted,train)[1]
                if name=='gaussian':
                    opt=minimize_scalar(lambda x:objective([x]),bounds=(1,7),method='bounded',options={'xatol':1e-3})
                    params=[float(opt.x)];calls=opt.nfev
                else:
                    opt=differential_evolution(objective,BOUNDS[name],seed=20260924+frame,maxiter=40,
                                               popsize=7,polish=True,tol=1e-5,workers=1)
                    params=opt.x.tolist();calls=opt.nfev
                psf=kernel(name,params)
                pred=fftconvolve(TRUTH,psf,mode='same')
                gain,train_mse=fit_gain_and_error(observed,pred,train)
                y,p=observed[hold],gain*pred[hold]
                rows.append(dict(fold=fold,frame=frame,model=name,params=json.dumps(params),
                                 optimizer_calls=int(calls),train_mse=train_mse,
                                 heldout_mse=float(np.mean((y-p)**2)),heldout_mae=float(np.mean(np.abs(y-p))),
                                 heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                                 heldout_gradient_mae=grad_error(observed,gain*pred,hold),
                                 centroid_offset_px=float(np.hypot(np.sum(xx*psf),np.sum(yy*psf))),
                                 outer_3px_energy=float(psf[:3].sum()+psf[-3:].sum()+psf[3:-3,:3].sum()+psf[3:-3,-3:].sum())))
            print(fold,frame,'done',flush=True)
    with (ROOT/'full_patch_screen_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for fold,model in dict.fromkeys((r['fold'],r['model']) for r in rows):
        subset=[r for r in rows if r['fold']==fold and r['model']==model]
        summary.append(dict(fold=fold,model=model,frames=len(subset),
                            mean_heldout_mse=float(np.mean([r['heldout_mse'] for r in subset])),
                            mean_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in subset])),
                            mean_heldout_correlation=float(np.mean([r['heldout_correlation'] for r in subset])),
                            max_outer_3px_energy=max(r['outer_3px_energy'] for r in subset)))
    (ROOT/'full_patch_screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
