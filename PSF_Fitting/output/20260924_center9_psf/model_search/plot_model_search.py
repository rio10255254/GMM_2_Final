"""Create comparable scientific plots for full-patch PSF validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import loadmat

from screen_parametric_psfs import ROOT,kernel,XX,YY


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))


def main():
    dev=json.loads((ROOT/'full_BADS_development_summary.json').read_text(encoding='utf-8'))
    final=json.loads((ROOT/'E_full_patch_verdict.json').read_text(encoding='utf-8'))
    folds=['A','B','C','D','E']
    mix=[next(r for r in dev if r['fold']==f)['mean_BADs_heldout_mse'] for f in folds[:-1]]
    gauss=[next(r for r in dev if r['fold']==f)['mean_gaussian_heldout_mse'] for f in folds[:-1]]
    mix.append(final['summary']['selected_core_halo_BADs']['mean_heldout_mse'])
    gauss.append(final['summary']['gaussian']['mean_heldout_mse'])
    x=np.arange(5)
    fig,axes=plt.subplots(1,2,figsize=(11,4),constrained_layout=True)
    ax=axes[0]
    ax.bar(x-.18,mix,width=.35,color='#168a78',label='BADS core + halo')
    ax.bar(x+.18,gauss,width=.35,color='#885ead',label='Single Gaussian')
    ax.scatter([4],[final['summary']['original_disk_BADs']['mean_heldout_mse']],
               marker='x',s=90,color='#5c6975',label='Original BADS on E')
    ax.axvline(3.5,color='black',ls='--',lw=1,alpha=.7)
    ax.set_xticks(x,[f'{f}\n(final)' if f=='E' else f for f in folds])
    ax.set_ylabel('Complete 25×25 held-out pixel MSE (lower is better)')
    ax.set_ylim(0,.0035)
    ax.grid(axis='y',alpha=.2)
    ax.legend(fontsize=8)
    ax.set_title('P-SEM contour → PSF → new photo')

    frame=16;idx=[5,9,11,16,19,21].index(frame)
    mixture=loadmat(ROOT/'mixture_full_E'/'PSF_fitted_mixture.mat')['psf_grid'].reshape(101,101,6)[:,:,idx]
    original=loadmat(ROOT/'original_full_E'/'PSF_fitted_2D_FOVstack.mat')['psf_grid'].reshape(101,101,6)[:,:,idx]
    mix_rows=read_csv(ROOT/'E_full_patch_metrics.csv')
    sigma=float(next(r for r in mix_rows if r['frame']==str(frame) and r['model']=='gaussian')['gaussian_sigma_px'])
    gaussian=kernel('gaussian',[sigma])
    radius=np.hypot(XX,YY)
    for name,psf,color in [('Core + halo',mixture,'#168a78'),('Single Gaussian',gaussian,'#885ead'),('Original BADS',original,'#5c6975')]:
        psf=psf/psf.sum()
        xs=[];ys=[]
        for rr in range(21):
            mask=(radius>=rr-.5)&(radius<rr+.5)
            if np.any(mask):xs.append(rr);ys.append(float(psf[mask].mean()))
        axes[1].plot(xs,ys,marker='.',label=name,color=color)
    axes[1].set_yscale('log')
    axes[1].set_xlim(0,20)
    axes[1].set_xlabel('Distance from PSF center (pixels)')
    axes[1].set_ylabel('Mean PSF intensity (log scale)')
    axes[1].set_title('Frame 16: sharp center and faint halo')
    axes[1].grid(alpha=.2)
    axes[1].legend(fontsize=8)
    fig.savefig(ROOT/'full_patch_validation_summary.png',dpi=180)
    plt.close(fig)
    print(str(ROOT/'full_patch_validation_summary.png'))


if __name__=='__main__':main()
