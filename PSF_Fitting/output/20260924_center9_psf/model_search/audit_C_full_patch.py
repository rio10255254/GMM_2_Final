"""Preserve the post-confirmation finding that center-only success misses halo error."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve


ROOT=Path(__file__).resolve().parent
RUN=ROOT.parent
TRUTH=np.load(RUN/'sem_shape_forward_validation'/'gt_sem_contour_20x_float.npz')['image']
FRAMES=[3,8,14,20,22]
IDS=[36,35,34,30,29,28,24,23,22]
HELD=[35,28,24]
CENTERS=[69,150,231]


def main():
    initial=json.loads((ROOT/'C_verdict.json').read_text(encoding='utf-8'))
    assert initial['status']=='PASS_predictive_research_candidate'
    mixture=loadmat(ROOT/'mixture_bads_C'/'PSF_fitted_mixture.mat')['psf_grid'].reshape(101,101,5)
    with (ROOT/'C_metrics.csv').open(newline='',encoding='utf-8') as f:
        controls={(int(r['frame']),r['model']):r for r in csv.DictReader(f)}
    yy,xx=np.ogrid[-12:13,-12:13]
    rr=np.hypot(xx,yy)
    masks={name:np.zeros((301,301),bool) for name in ('center_r10','annulus_r10_to_r12','full_25x25')}
    for pillar in HELD:
        index=IDS.index(pillar);row,col=divmod(index,3);y,x=CENTERS[row],CENTERS[col]
        tile=np.s_[y-12:y+13,x-12:x+13]
        masks['center_r10'][tile] |= rr<=10
        masks['annulus_r10_to_r12'][tile] |= (rr>10)&(rr<=12)
        masks['full_25x25'][tile] |= True
    rows=[]
    for i,frame in enumerate(FRAMES):
        image=cv2.imread(str(RUN/'fit_input'/f'fit_input_{frame:02d}.bmp'),0).astype(float)/255
        mixture_psf=mixture[:,:,i]/mixture[:,:,i].sum()
        for model in ('selected_mixture_BADs','gaussian'):
            metadata=controls[(frame,model)]
            gain=float(metadata['gain_from_train6'])
            if model=='selected_mixture_BADs':
                pred=fftconvolve(TRUTH,mixture_psf,mode='same')
            else:
                pred=gaussian_filter(TRUTH,float(metadata['gaussian_sigma_px']),mode='constant')
            row=dict(frame=frame,model=model)
            for name,mask in masks.items():
                row[name+'_mse']=float(np.mean((image[mask]-gain*pred[mask])**2))
            rows.append(row)
    with (ROOT/'C_full_patch_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={}
    for model in ('selected_mixture_BADs','gaussian'):
        subset=[r for r in rows if r['model']==model]
        summary[model]={name:float(np.mean([r[name+'_mse'] for r in subset])) for name in masks}
    report={'status':'FAIL_full_patch_even_though_frozen_center_gates_passed',
            'center_gate_file':'C_verdict.json',
            'secondary_check_not_used_to_select_prior_model':True,
            'summary':summary,
            'interpretation':'Core-plus-halo model fits inner disk but overpredicts light in the valid outer optical patch; not suitable as an overall image-fidelity improvement.'}
    assert summary['selected_mixture_BADs']['center_r10'] < summary['gaussian']['center_r10']
    assert summary['selected_mixture_BADs']['full_25x25'] > summary['gaussian']['full_25x25']
    (ROOT/'C_full_patch_reassessment.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
