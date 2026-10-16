"""Freeze a matched complete-contour test; preserve all historical masks."""
import sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
from common import *
import numpy as np,cv2
from scipy.io import savemat
from train import verify_binding

def main():
    out=ROOT/'results/full_contour';out.mkdir(parents=True,exist_ok=True)
    assert not (out/'plan.json').exists() and not (out/'inputs.mat').exists(),'Refuse to replace an existing preparation'
    verify_binding(load(ROOT/'config/frozen_training.json'))
    old=EXPS/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat'
    alt=EXPS/'R121_BoundaryAnchorFactorial/results/pitch_matched_reference.mat'
    helper=EXPS/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/measure_acm.m'
    protected=load(ROOT/'config/protected_before.json')
    for p in [old,alt]:assert str(p) in protected and sha(p)==protected[str(p)]
    # The helper is a newly reused source for this supplemental analysis.
    # Pin its current content below, without changing historical expectations;
    # exact Raw-mask reproduction remains the independent comparability check.
    sources=[];raws=[];floats=[];pngs=[]
    nearby=load(ROOT/'results/nearby_brightness/summary.json')
    for exp in [13,14,15]:
        previous=next(x for x in nearby['summaries'] if x['exposure']==exp)
        src=previous['source'];pred=previous['output'];assert sha(src['path'])==src['sha256'] and sha(pred['path'])==pred['sha256']
        raw=cv2.imread(src['path'],0)
        with np.load(pred['path']) as f:a=f['output']
        assert raw.shape==a.shape==(821,821)
        raws.append(raw);floats.append(a.astype(np.float64));pngs.append(np.rint(a*255).clip(0,255).astype(np.uint8));sources.append(dict(exposure=exp,Raw=src,reconstruction=pred))
    savemat(out/'inputs.mat',dict(raw_images=np.stack(raws,2),candidate_u8_images=np.stack(pngs,2),candidate_float_images=np.stack(floats,2),exposures=np.array([13,14,15],np.float64)),do_compression=True)
    text=helper.read_text(encoding='utf-8');tail=text[text.index('\nfunction centers = sort_grid_centers'):]
    head=(ROOT/'analysis/full_contour/worker_head.txt').read_text(encoding='utf-8')
    path=ROOT/'analysis/full_contour/run_contour_check.m'
    with path.open('x',encoding='utf-8') as f:f.write(head+tail)
    plan=dict(created_utc=now(),question='Does the entire extracted optical contour approach the matched SEM contour after R128reconstruction?',candidate=record(ROOT/'runs/P_s1285002/checkpoints/step8192.pth'),exposures=[13,14,15],objects_per_exposure=36,physical_specimens=1,methods=['Raw','R128_PNG','R128_float'],primary_output='R128_PNG standard8bit trial output',primary_preset=dict(iterations=200,smooth_factor=1.),sensitivity_presets=[dict(iterations=150,smooth_factor=.5),dict(iterations=250,smooth_factor=2.)],references=[dict(name='historical',record=record(old)),dict(name='global_pitch_matched',record=record(alt))],reference_scope='Existing independently fixed SEM masks, not recalibrated material truth; report both without choosing favorable reference',alignment='Same Raw-derived integer translation applied to Raw and model for each object/exposure/reference, fixed across presets; no per-model scale/rotation/translation fit',full_contour_metrics=['mean_symmetric_boundary_distance_px','HD95_px','IoU','area_error_pct','perimeter_error_pct','circularity_error'],failure_policy='Retain all36objects and every segmentation failure; record support contact',Raw_primary_expected='Bitwise equal to original R119Raw masks before accepting historical comparability',sources=sources,input_mat=record(out/'inputs.mat'),original_helper_source=record(helper),copied_helper_sha256=hashlib.sha256(tail.encode()).hexdigest(),new_matlab_source=record(path),training_updates=0,no_new_confirmation_claim=True,normal_operating_range_not_fully_qualified=True)
    save(out/'plan.json',plan);print(json.dumps(dict(prepared=True,segmentation_cells=972,metric_rows=1944,helpers_copied_unchanged=True)),flush=True)

if __name__=='__main__':main()
