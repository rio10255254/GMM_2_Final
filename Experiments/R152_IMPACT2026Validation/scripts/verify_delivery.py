"""Independently verify preserved sources, native outputs, counts, and reported statistics."""
from pathlib import Path
import hashlib, json, sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def main():
    full=ROOT/'results/full120/complete.json'
    if full.exists() and load(full).get('state')=='complete_objective_calibrated_full120':
        from verify_full120 import main as verify_current
        return verify_current()
    sources=load(ROOT/'results/source_manifest.json')
    for r in sources:
        assert r['exists'] and sha(r['path'])==r['sha256'],r['path']
        if 'snapshot' in r:assert sha(ROOT/r['snapshot'])==r['sha256']
    replay=load(ROOT/'results/submission_replay_check.json');assert replay['passed']
    manifest=load(ROOT/'results/20x/reconstruction_manifest.json');assert len(manifest)==80
    for r in manifest:
        assert sha(r['output'])==r['output_sha256'] and sha(r['source'])==r['source_sha256']
        a=np.load(r['output'])['output']
        assert a.dtype==np.float32 and list(a.shape)==r['shape'] and np.isfinite(a).all() and a.min()>=0 and a.max()<=1
    centers=pd.read_csv(ROOT/'results/20x/centers.csv');pairs=pd.read_csv(ROOT/'results/20x/per_pair.csv');summary=pd.read_csv(ROOT/'results/20x/summary.csv')
    assert len(centers)==2160 and len(pairs)==180
    idx=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index();maxerr=0.0
    for r in pairs.itertuples():
        a=idx.loc[(r.sequence,r.method,r.start_frame_index)].sort_index()
        b=idx.loc[(r.sequence,r.method,r.end_frame_index)].sort_index()
        assert len(a)==len(b)==9 and a.index.equals(b.index)
        dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*.1725
        vals=[abs(np.median(dx)),abs(abs(np.median(dx))-r.nominal_step_um)*1000,np.std(dx,ddof=1)*1000]
        err=max(abs(np.array(vals)-[r.measured_step_um,r.nominal_abs_error_nm,r.within_grid_sd_nm]));maxerr=max(maxerr,err)
    assert maxerr<1e-7
    for row in summary.itertuples():
        g=pairs[pairs.method==row.method]
        if row.sequence!='20x_only_two_conditions':g=g[g.sequence==row.sequence]
        expected=[np.mean([s.measured_step_um.std(ddof=1)*1000 for _,s in g.groupby('sequence')]),np.mean([s.nominal_abs_error_nm.mean() for _,s in g.groupby('sequence')]),g.within_grid_sd_nm.median()]
        assert np.max(abs(np.array(expected)-[row.step_sd_nm,row.nominal_mae_nm,row.median_within_grid_sd_nm]))<1e-9
    expected_files=['reports/R152_AUDIT.md','reports/R152_RESULTS.md','poster_assets/POSTER_TEXT.md','poster_assets/RESULTS_20X_TEXT.md','poster_assets/results_20x_only.png','poster_assets/results_20x_only.svg','poster_assets/representative_20x_only.png','poster_assets/representative_20x_only.svg','poster_assets/method_protocol_pending.png','poster_assets/method_protocol_pending.svg']
    for f in expected_files:assert (ROOT/f).is_file(),f
    status=load(ROOT/'results/preflight_status.json')
    assert status['status']=='PARTIAL_20X_COMPLETE_50X_BLOCKED' and status['full_r152_inference_started']==False
    result=dict(passed=True,source_files_rechecked=len(sources),source_files_unchanged=True,output_images_verified=80,partial_pairs_per_method=60,center_rows=2160,pair_rows=180,center_to_pair_max_numeric_difference=maxerr,historical_replay_passed=True,full_four_condition_result=False,blocked='R152 compatible 50x optical bank and verified installation',artifacts=[dict(path=f,sha256=sha(ROOT/f)) for f in expected_files])
    (ROOT/'results/delivery_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
