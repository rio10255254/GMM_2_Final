"""Screen small centered PSF families using only six training SEM pillars."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.optimize import differential_evolution, minimize_scalar
from scipy.signal import fftconvolve


ROOT=Path(__file__).resolve().parent
RUN=ROOT.parent
TRUTH=np.load(RUN/'sem_shape_forward_validation'/'gt_sem_contour_20x_float.npz')['image']
YY,XX=np.mgrid[-50:51,-50:51]
RR=XX*XX+YY*YY
FOLDS={
 'A':([1,13,25],RUN/'fit_input'/'loss_mask_train6.bmp',RUN/'fit_input'/'loss_mask_hold3.bmp',RUN/'cv_bounds_2'/'PSF_fitted_2D_FOVstack.mat'),
 'B':([4,7,12,18,23],RUN/'fit_input'/'loss_mask_train6_B.bmp',RUN/'fit_input'/'loss_mask_hold3_B.bmp',RUN/'parameter_audit'/'confirm_original'/'PSF_fitted_2D_FOVstack.mat'),
}


def kernel(name,params,reference=None):
    if name=='gaussian':
        (sigma,)=params
        image=np.exp(-RR/(2*sigma*sigma))
    elif name=='elliptic_gaussian':
        sx,sy,theta=params
        ct,st=np.cos(theta),np.sin(theta)
        xr=ct*XX+st*YY
        yr=-st*XX+ct*YY
        image=np.exp(-.5*((xr/sx)**2+(yr/sy)**2))
    elif name=='moffat':
        alpha,beta=params
        image=(1+RR/(alpha*alpha))**(-beta)
    elif name=='gaussian_mixture':
        core,extra,core_weight=params
        halo=core+extra
        image=core_weight*np.exp(-RR/(2*core*core))/(2*np.pi*core*core)
        image+=(1-core_weight)*np.exp(-RR/(2*halo*halo))/(2*np.pi*halo*halo)
    elif name=='bads_gaussian_mixture':
        gaussian_weight,sigma=params
        image=(1-gaussian_weight)*reference + gaussian_weight*np.exp(-RR/(2*sigma*sigma))/(2*np.pi*sigma*sigma)
    else:
        raise ValueError(name)
    image=np.maximum(image,0)
    return image/image.sum()


def fit_gain_and_error(observed,prediction,mask):
    y,p=observed[mask],prediction[mask]
    gain=float(np.dot(y,p)/np.dot(p,p))
    return gain,float(np.mean((y-gain*p)**2))


def grad_error(observed,prediction,mask):
    def norm_grad(image):
        gx=cv2.Sobel(image,cv2.CV_64F,1,0,ksize=3);gy=cv2.Sobel(image,cv2.CV_64F,0,1,ksize=3)
        value=np.hypot(gx,gy);return (value-value.min())/max(value.max()-value.min(),1e-12)
    return float(np.mean(np.abs(norm_grad(observed)[mask]-norm_grad(prediction)[mask])))


def main():
    rows=[]
    bounds={
      'elliptic_gaussian':[(1.0,7.0),(1.0,7.0),(-np.pi/2,np.pi/2)],
      'moffat':[(1.0,12.0),(1.1,12.0)],
      'gaussian_mixture':[(1.0,6.0),(.3,15.0),(.5,1.0)],
      'bads_gaussian_mixture':[(0,1),(1.0,7.0)],
    }
    for fold,(frames,train_path,hold_path,reference_path) in FOLDS.items():
        train=cv2.imread(str(train_path),0)>0
        hold=cv2.imread(str(hold_path),0)>0
        references=loadmat(reference_path)['psf_grid'].reshape(101,101,len(frames))
        for index,frame in enumerate(frames):
            observed=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
            reference=references[:,:,index]/references[:,:,index].sum()
            for name in ['gaussian','elliptic_gaussian','moffat','gaussian_mixture','bads_gaussian_mixture']:
                def objective(param):
                    k=kernel(name,param,reference)
                    pred=fftconvolve(TRUTH,k,mode='same')
                    return fit_gain_and_error(observed,pred,train)[1]
                if name=='gaussian':
                    opt=minimize_scalar(lambda s:objective([s]),bounds=(1,7),method='bounded',options={'xatol':1e-3})
                    params=[float(opt.x)];calls=int(opt.nfev)
                else:
                    opt=differential_evolution(objective,bounds[name],seed=20260924+frame,maxiter=30,
                                               popsize=7,polish=True,tol=1e-5,workers=1)
                    params=opt.x.tolist();calls=int(opt.nfev)
                psf=kernel(name,params,reference)
                pred=fftconvolve(TRUTH,psf,mode='same')
                gain,train_mse=fit_gain_and_error(observed,pred,train)
                y,p=observed[hold],gain*pred[hold]
                rows.append(dict(fold=fold,frame=frame,model=name,params=json.dumps(params),optimizer_calls=calls,
                                 gain=gain,train_mse=train_mse,heldout_mse=float(np.mean((y-p)**2)),
                                 heldout_mae=float(np.mean(np.abs(y-p))),
                                 heldout_correlation=float(np.corrcoef(y,p)[0,1]),
                                 heldout_gradient_mae=grad_error(observed,gain*pred,hold),
                                 centroid_offset_px=float(np.hypot(np.sum(XX*psf),np.sum(YY*psf))),
                                 peak_offset_px=float(np.hypot(np.unravel_index(np.argmax(psf),psf.shape)[1]-50,
                                                               np.unravel_index(np.argmax(psf),psf.shape)[0]-50))))
            print(fold,frame,'done',flush=True)
    with (ROOT/'parametric_screen_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for fold,model in dict.fromkeys((r['fold'],r['model']) for r in rows):
        subset=[r for r in rows if r['fold']==fold and r['model']==model]
        summary.append(dict(fold=fold,model=model,mean_heldout_mse=float(np.mean([r['heldout_mse'] for r in subset])),
                            mean_heldout_correlation=float(np.mean([r['heldout_correlation'] for r in subset])),
                            mean_heldout_gradient_mae=float(np.mean([r['heldout_gradient_mae'] for r in subset])),
                            mean_optimizer_calls=float(np.mean([r['optimizer_calls'] for r in subset]))))
    (ROOT/'parametric_screen_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
