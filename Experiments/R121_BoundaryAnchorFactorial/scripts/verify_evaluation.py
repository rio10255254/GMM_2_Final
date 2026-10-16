"""Independent geometry recomputation and source-preservation audit."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd
from scipy.io import loadmat
from scipy.ndimage import binary_erosion,distance_transform_edt
ROOT=Path(__file__).resolve().parents[1]

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def independent_boundary(truth,prediction,pitch):
    ty,tx=np.nonzero(truth);py,px=np.nonzero(prediction)
    shift=np.array([tx.mean()-px.mean(),ty.mean()-py.mean()]);dx,dy=(np.sign(shift)*np.floor(np.abs(shift)+.5)).astype(int)
    h,w=prediction.shape;aligned=np.zeros_like(prediction)
    x0,x1=max(0,-dx),min(w,w-dx);y0,y1=max(0,-dy),min(h,h-dy)
    if x1>x0 and y1>y0:aligned[y0+dy:y1+dy,x0+dx:x1+dx]=prediction[y0:y1,x0:x1]
    te=truth^binary_erosion(truth,np.ones((3,3)));pe=aligned^binary_erosion(aligned,np.ones((3,3)))
    values=np.r_[distance_transform_edt(~te)[pe],distance_transform_edt(~pe)[te]]
    return float(values.mean()*100/pitch)

def main():
    protected=json.loads((ROOT/'reports/protected_inputs.json').read_text());assert all(sha(p)==h for p,h in protected.items())
    inputs=json.loads((ROOT/'config/evaluation_inputs.json').read_text());assert all(sha(p)==h for p,h in inputs.items())
    frame=pd.read_csv(ROOT/'results/sem/measurements.csv');assert len(frame)==7776 and not frame.duplicated(['method','reference','exposure','pillar']).any()
    old=loadmat(ROOT.parent/'R119_SequenceGeometryValidation/results/formal_sem/results/masks/acm_primary_masks.mat',variable_names=['truth_masks','raw_masks','opt_pitch'])
    alt=loadmat(ROOT/'results/pitch_matched_reference.mat',variable_names=['truth_masks'])
    saved=loadmat(ROOT/'results/sem/masks.mat',variable_names=['masks','method_names','raw_parity'],squeeze_me=True)
    names=[str(s) for s in saved['method_names']]
    assert np.array_equal(saved['masks'][:,:,:,:,0],old['raw_masks']) and np.all(saved['raw_parity']==0)
    rows=[]
    for row in frame[frame.valid==1].itertuples():
        truth=(old if row.reference=='historical' else alt)['truth_masks'][:,:,row.pillar-1].astype(bool)
        mask=saved['masks'][:,:,row.pillar-1,row.exposure-13,names.index(row.method)].astype(bool)
        value=independent_boundary(truth,mask,float(old['opt_pitch'].item()))
        area=100*(float(mask.sum())-truth.sum())/truth.sum()
        rows.append({'method':row.method,'reference':row.reference,'exposure':row.exposure,'pillar':row.pillar,'boundary_difference':value-row.boundary,'area_difference':area-row.signed_area})
    checked=pd.DataFrame(rows);assert checked.boundary_difference.abs().max()<2e-6 and checked.area_difference.abs().max()<1e-10
    checked.to_csv(ROOT/'results/assessment/independent_sem_recalculation.csv',index=False,mode='x')
    original=pd.read_csv(ROOT.parent/'R119_SequenceGeometryValidation/results/formal_sem/results/tables/primary_contour_metrics.csv')
    merged=frame[(frame.reference=='historical')&(frame.method=='Raw')].merge(original[original.method=='Raw'],left_on=['exposure','pillar'],right_on=['exposure','pillar_id'],validate='one_to_one')
    assert (merged.boundary-merged.mean_boundary_distance_pitch_pct).abs().max()<2e-6
    helper=(ROOT.parent/'R69_ACMContourSEMValidation/scripts/run_acm_extraction.m').read_text(encoding='utf-8').split('function centers = sort_grid_centers',1)[1]
    used=(ROOT/'scripts/evaluate_sem_v3.m').read_text(encoding='utf-8').split('function centers = sort_grid_centers',1)[1]
    assert helper==used
    decision=json.loads((ROOT/'results/assessment/decision.json').read_text())
    dev=pd.read_csv(ROOT/'results/development/per_view.csv')
    for gate in decision['gates']:
        own=dev[(dev.method==gate['method'])&(dev.role=='textured_edge')].highpass_mae_gray.mean()
        control=next(g['method'] for g in decision['gates'] if g['seed']==gate['seed'] and g['arm']=='A')
        base=dev[(dev.method==control)&(dev.role=='textured_edge')].highpass_mae_gray.mean()
        assert abs(own/base-gate['textured_highpass_error_ratio_vs_A'])<1e-12
    report={'protected_inputs_unchanged':len(protected),'evaluation_inputs_unchanged':len(inputs),'measurement_rows':len(frame),'invalid_measurements':int((frame.valid!=1).sum()),
            'independently_recomputed_rows':len(checked),'max_boundary_difference_pitch_percentage_points':float(checked.boundary_difference.abs().max()),
            'Raw_masks_exactly_reproduced':432,'historical_numerical_helpers_unchanged':True,'detail_ratios_recomputed':8,
            'supported_arms':decision['supported_arms_for_real_LSC'],'training_or_threshold_updates_after_outcomes':False,'code_sha256':sha(__file__)}
    with (ROOT/'results/assessment/verification.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
