"""Package the validated centered core-plus-halo PSFs as research outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat, savemat
from scipy.optimize import minimize_scalar
from scipy.signal import fftconvolve

from screen_parametric_psfs import ROOT,RUN,TRUTH,kernel,grad_error,XX,YY


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def mse_with_gain(observed,predicted,mask):
    gain=float(np.dot(observed[mask],predicted[mask])/np.dot(predicted[mask],predicted[mask]))
    y,p=observed[mask],gain*predicted[mask]
    return gain,float(np.mean((y-p)**2)),float(np.corrcoef(y,p)[0,1])


def main():
    verdict=json.loads((ROOT/'E_full_patch_verdict.json').read_text(encoding='utf-8'))
    assert verdict['status']=='PASS_predictive_research_PSF'
    fit=loadmat(ROOT/'mixture_full_ALL'/'PSF_fitted_mixture.mat')
    raw=fit['psf_grid'].reshape(101,101,25)
    assert np.array_equal(fit['frames'].ravel(),np.arange(1,26))
    candidate=raw/raw.sum(axis=(0,1),keepdims=True)
    original=loadmat(RUN/'PSF_20260924_center9_25_normalized.mat')['psf_grid'].reshape(101,101,25)
    batch=read_csv(ROOT/'mixture_full_ALL'/'batch_results.csv')
    sources=read_csv(RUN/'center9_locations.csv')[::9]
    assert len(batch)==len(sources)==25
    mask=cv2.imread(str(ROOT/'full_all9.bmp'),0)>0
    assert mask.sum()==9*625
    grid=np.empty((101,101,5,5));params=np.empty((5,5,3));gains=np.empty((5,5))
    rows=[]
    for i in range(25):
        frame=i+1
        observed=cv2.imread(str(RUN/'parameter_audit'/'wide_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
        current=candidate[:,:,i]
        pred=fftconvolve(TRUTH,current,mode='same')
        gain,mse,corr=mse_with_gain(observed,pred,mask)
        orig_pred=fftconvolve(TRUTH,original[:,:,i],mode='same')
        _,orig_mse,_=mse_with_gain(observed,orig_pred,mask)
        def gaussian_loss(sigma):
            p=fftconvolve(TRUTH,kernel('gaussian',[sigma]),mode='same')
            return mse_with_gain(observed,p,mask)[1]
        gaussian=minimize_scalar(gaussian_loss,bounds=(1,7),method='bounded',options={'xatol':1e-3})
        gaussian_mse=float(gaussian.fun)
        yy,xx=np.unravel_index(np.argmax(current),current.shape)
        centroid=float(np.hypot(np.sum(XX*current),np.sum(YY*current)))
        edge=float(current[:3].sum()+current[-3:].sum()+current[3:-3,:3].sum()+current[3:-3,-3:].sum())
        assert (xx,yy)==(50,50) and centroid<1e-10 and edge<.001
        assert int(batch[i]['frame'])==frame and int(batch[i]['exitflag'])>0
        core=float(batch[i]['sigma_core_px']);halo=float(batch[i]['sigma_halo_px']);weight=float(batch[i]['core_energy_weight'])
        grid[:,:,i//5,i%5]=current
        params[i//5,i%5]=[core,halo,weight]
        gains[i//5,i%5]=gain
        rows.append(dict(frame=frame,source_image=sources[i]['image'],sigma_core_px=core,sigma_halo_px=halo,
                         core_energy_weight=weight,brightness_gain=gain,fit_seconds=float(batch[i]['seconds']),
                         fit_loss=float(batch[i]['train_mse']),fit_exitflag=int(batch[i]['exitflag']),
                         in_sample_full_patch_mse_core_halo=mse,
                         in_sample_full_patch_mse_original_BADs=orig_mse,
                         in_sample_full_patch_mse_tuned_gaussian=gaussian_mse,
                         correlation_core_halo=corr,
                         gradient_mae_core_halo=grad_error(observed,gain*pred,mask),
                         max_PSF_peak_offset_px=0,PSF_centroid_offset_px=centroid,
                         PSF_outer_3px_energy=edge))
    with (ROOT/'full25_core_halo_qa.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    savemat(ROOT/'PSF_20260924_SEM_core_halo_25_RESEARCH.mat',dict(
        psf_grid=grid,
        source_image_names_row_major=np.asarray([r['image'] for r in sources],dtype=object).reshape(5,5),
        sem_ids_image_rows=np.array([[36,35,34],[30,29,28],[24,23,22]],dtype=np.int32),
        sigma_core_px=params[:,:,0],sigma_halo_px=params[:,:,1],core_energy_weight=params[:,:,2],
        brightness_gain_row_major=gains,object_pixel_um=np.array([[.1725]]),
        research_only=np.array([[1]],dtype=np.uint8),
        model_description=np.array(['centered unit-sum two-Gaussian core plus halo, BADS fit to actual P-SEM silhouettes'],dtype=object),
    ),do_compression=True)
    summary={
       'status':'research_candidate_not_formal_baseline',
       'source_acquisition_frames':25,
       'frozen_E_verdict':'PASS_predictive_research_PSF',
       'all_25_BADs_exitflags_positive':all(r['fit_exitflag']>0 for r in rows),
       'all_25_peaks_centered':True,
       'max_centroid_offset_px':max(r['PSF_centroid_offset_px'] for r in rows),
       'max_outer_3px_energy_fraction':max(r['PSF_outer_3px_energy'] for r in rows),
       'sigma_core_px_range':[float(params[:,:,0].min()),float(params[:,:,0].max())],
       'sigma_halo_px_range':[float(params[:,:,1].min()),float(params[:,:,1].max())],
       'core_energy_weight_range':[float(params[:,:,2].min()),float(params[:,:,2].max())],
       'median_in_sample_mse_core_halo':float(np.median([r['in_sample_full_patch_mse_core_halo'] for r in rows])),
       'median_in_sample_mse_original_BADs':float(np.median([r['in_sample_full_patch_mse_original_BADs'] for r in rows])),
       'median_in_sample_mse_tuned_gaussian':float(np.median([r['in_sample_full_patch_mse_tuned_gaussian'] for r in rows])),
       'core_halo_better_than_original_in_sample':sum(r['in_sample_full_patch_mse_core_halo']<r['in_sample_full_patch_mse_original_BADs'] for r in rows),
       'core_halo_better_than_gaussian_in_sample':sum(r['in_sample_full_patch_mse_core_halo']<r['in_sample_full_patch_mse_tuned_gaussian'] for r in rows),
       'median_fit_seconds_per_frame':float(np.median([r['fit_seconds'] for r in rows])),
    }
    (ROOT/'full25_core_halo_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    fig,axes=plt.subplots(5,5,figsize=(9,9),constrained_layout=True)
    vmax=float(np.percentile(grid[35:66,35:66,:,:],99.5))
    for i,ax in enumerate(axes.flat):
        ax.imshow(grid[35:66,35:66,i//5,i%5],cmap='magma',vmin=0,vmax=vmax)
        ax.set_title(f'{i+1:02d} {sources[i]["image"].removesuffix(".bmp")}',fontsize=8)
        ax.set_xticks([]);ax.set_yticks([])
    fig.savefig(ROOT/'PSF_core_halo_25_grid.png',dpi=170)
    plt.close(fig)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
