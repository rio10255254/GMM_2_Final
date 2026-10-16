"""Additional read-only probes: SEM mask area, sampling and motion null space."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import cv2
from scipy.io import loadmat
import torch

OUT=Path(__file__).resolve().parent
W=OUT.parents[1]
sys.path.insert(0,str(W))
from training.objectives import location_xy


def main():
    rows=[];raw_reference=None
    for name in ['shortlist_sem_B','formal_E024_sem','formal_E036_sem','formal_sem']:
        d=loadmat(W/'results'/name/'results/masks/acm_primary_masks.mat',
                  variable_names=['truth_masks','raw_masks','recon_masks','opt_pitch'])
        truth=d['truth_masks'].sum((0,1)).astype(float)[:,None]
        raw=d['raw_masks'].sum((0,1)).astype(float)
        output=d['recon_masks'].sum((0,1)).astype(float)
        raw_equal=True if raw_reference is None else bool(np.array_equal(raw,raw_reference))
        if raw_reference is None:raw_reference=raw.copy()
        rows.append({'run':name,'Raw_signed_area_error_pct':float(np.median(100*(raw-truth)/truth)),
            'output_signed_area_error_pct':float(np.median(100*(output-truth)/truth)),
            'output_minus_Raw_area_pct_of_truth':float(np.median(100*(output-raw)/truth)),
            'all_Raw_masks_identical_across_runs':raw_equal,
            'output_larger_than_Raw_observations':int((output>raw).sum()),'observations':int(output.size),
            'SEM_boundary_inference':'signed areas measure contour dilation/contraction, not circular CD'})
    # Analytic, spatially band-limited pattern. Physical resampling preserves its
    # amplitude; bilinear translation on an already-sampled image suppresses it.
    size=256;factor=8;frequency=.4
    high_x=(np.arange(size*factor,dtype=np.float64)+.5)/factor
    high=np.tile(.5+.2*np.sin(2*np.pi*frequency*high_x),(8,1))
    physical_shift=np.tile(.5+.2*np.sin(2*np.pi*frequency*(high_x-.5)),(8,1))
    native=high.reshape(1,8,size,8).mean((1,3)).astype(np.float32)
    physical=physical_shift.reshape(1,8,size,8).mean((1,3)).astype(np.float32)
    bilinear=cv2.warpAffine(native,np.float32([[1,0,.5],[0,1,0]]),(size,1),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    roi=slice(10,246)
    # Fit sine/cosine amplitude, avoiding phase-dependent finite-window std bias.
    x=np.arange(size)[roi]+.5
    design=np.stack([np.ones(len(x)),np.sin(2*np.pi*frequency*x),np.cos(2*np.pi*frequency*x)],1)
    amplitude=lambda a:float(np.linalg.norm(np.linalg.lstsq(design,a[0,roi],rcond=None)[0][1:]))
    sampled={'frequency_cycles_per_pixel':frequency,'translation_px':.5,
        'physical_shift_amplitude_ratio':amplitude(physical)/amplitude(native),
        'postsampling_bilinear_amplitude_ratio':amplitude(bilinear)/amplitude(native),
        'interpretation':'native-pixel shifting can make a motion test artificially easier by suppressing high frequency'}
    # A symmetric outward edge error is invisible to an x/y center-only loss.
    y,x=np.mgrid[:128,:128].astype(np.float32)
    radius=np.hypot(x-63.5,y-63.5)
    reference=.8-.5/(1+np.exp(np.clip((radius-28)/1.2,-40,40)))
    expanded=.8-.5/(1+np.exp(np.clip((radius-28.4)/1.2,-40,40)))
    displacement, confidence=location_xy(torch.from_numpy(expanded)[None,None],torch.from_numpy(reference)[None,None])
    null_test={'outward_boundary_shift_px':.4,'training_xy_readout_px':displacement[0].tolist(),
        'training_xy_confidence':float(confidence[0]),'area_change_from_known_geometry_pct':100*((28.4/28)**2-1),
        'interpretation':'center precision is insufficient to establish boundary precision; neither goal intrinsically forbids the other'}
    with (OUT/'boundary_sampling_results.json').open('x',encoding='utf-8') as stream:
        json.dump({'SEM_signed_area':rows,'physical_sampling_fixture':sampled,'center_only_null_space_fixture':null_test},stream,indent=2)
    print(json.dumps({'SEM_signed_area':rows,'physical_sampling_fixture':sampled,'center_only_null_space_fixture':null_test},indent=2))


if __name__=='__main__': main()
