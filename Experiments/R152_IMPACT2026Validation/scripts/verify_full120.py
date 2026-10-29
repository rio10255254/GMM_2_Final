"""Independent output/source/protocol verification for the completed full120 extension."""
from pathlib import Path
import ast,hashlib,json,subprocess
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
    for script in (ROOT/'scripts').glob('*.py'):ast.parse(script.read_text(encoding='utf-8'))
    auth=load(ROOT/'config/objective_optics_authorization.json');assert auth['use_original_50x_calibration']
    adapter=load(ROOT/'results/objective_adapter_preflight.json');assert adapter['passed']
    assert sha(ROOT/'scripts/objective_optics.py')==adapter['installation']['adapter_sha256']
    assert adapter['native_25_psf_restore_max_difference']==0 and adapter['single_psf_reinstall_max_difference']==0
    assert adapter['saved_full_frame_parity_max_difference']==0
    initial=load(ROOT/'results/50x_calibrated/optical_installation.json')
    assert sha(ROOT/'sources/objective_optics_first50run.py')==initial['adapter_sha256']
    sources=load(ROOT/'results/source_manifest.json')
    for r in sources:
        assert r['exists'] and sha(str(PROJECT_ROOT / r['path']))==r['sha256'],str(PROJECT_ROOT / r['path'])
        if 'snapshot' in r:assert sha(ROOT/r['snapshot'])==r['sha256']
    frames=[]
    for folder in ['20x','50x_calibrated']:
        complete=load(ROOT/f'results/{folder}/complete.json');assert complete['weights_and_buffers_unchanged']
        frames+=load(ROOT/f'results/{folder}/reconstruction_manifest.json')
    assert len(frames)==166 and len({(r['sequence'],r['frame_index']) for r in frames})==166
    assert len({r['checkpoint_sha256'] for r in frames})==1 and len({r['bank_sha256'] for r in frames})==2
    expected_banks={'20x':load(ROOT/'results/20x/complete.json')['bank_sha256'],'50x':sha(ROOT/'config/50x_calibrated_psf.npz')}
    for r in frames:
        assert sha(r['source'])==r['source_sha256'] and sha(r['output'])==r['output_sha256']
        assert r['object_um_per_px']==(.069 if r['sequence'].startswith('50x') else .1725)
        assert r['bank_sha256']==expected_banks['50x' if r['sequence'].startswith('50x') else '20x']
        assert r['deployment_scale']==1 and r['precision']=='FP32' and r['tf32']==False
        a=np.load(r['output'])['output'];assert list(a.shape)==r['shape'] and a.dtype==np.float32 and np.isfinite(a).all() and a.min()>=0 and a.max()<=1
    p=pd.read_csv(ROOT/'results/full120/per_pair.csv');c=pd.read_csv(ROOT/'results/full120/centers.csv')
    assert len(p)==360 and len(c)==4482
    index=c.set_index(['sequence','method','frame_index','pillar_id']).sort_index();maxerr=0.0
    locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    for (seq,m),group in p.groupby(['sequence','method']):
        assert len(group)==30
        expected=locked[locked.sequence==seq][['start_frame_index','end_frame_index']].to_numpy()
        assert np.array_equal(group.sort_values('pair_rank_raw_locked')[['start_frame_index','end_frame_index']].to_numpy(),expected)
    for r in p.itertuples():
        a=index.loc[(r.sequence,r.method,r.start_frame_index)].sort_index();b=index.loc[(r.sequence,r.method,r.end_frame_index)].sort_index()
        assert a.index.equals(b.index) and len(a)==9
        scale=.069 if r.magnification=='50x' else .1725;assert (a.object_um_per_px==scale).all()
        dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*scale
        values=[abs(np.median(dx)),abs(abs(np.median(dx))-r.nominal_step_um)*1000,np.std(dx,ddof=1)*1000]
        maxerr=max(maxerr,float(np.max(abs(np.array(values)-[r.measured_step_um,r.nominal_abs_error_nm,r.within_grid_sd_nm]))))
    assert maxerr<1e-7
    for filename,key in [('condition_summary','sequence'),('aggregate_summary','scope')]:
        summary=pd.read_csv(ROOT/f'results/full120/{filename}.csv')
        for r in summary.itertuples():
            g=p[p.method==r.method];scope=getattr(r,key)
            if key=='sequence':g=g[g.sequence==scope]
            elif scope!='all120':g=g[g.magnification==scope]
            expected=[np.mean([x.measured_step_um.std(ddof=1)*1000 for _,x in g.groupby('sequence')]),np.mean([x.nominal_abs_error_nm.mean() for _,x in g.groupby('sequence')]),g.within_grid_sd_nm.median()]
            assert np.max(abs(np.array(expected)-[r.step_sd_nm,r.nominal_mae_nm,r.median_within_grid_sd_nm]))<1e-9
    old=pd.read_csv(ROOT/'sources/historical_per_pair.csv');keys=['sequence','method','pair_rank_raw_locked'];cols=['measured_step_um','nominal_abs_error_nm','within_grid_sd_nm']
    a=p[p.method.isin(['Raw','Wiener'])].set_index(keys).sort_index();b=old[old.method.isin(['Raw','Wiener'])].set_index(keys).sort_index();assert a.index.equals(b.index)
    delta=abs(a[cols]-b[cols]).max();assert delta.max()<1e-7
    work=ROOT.parents[1];policy=load(work/'ESTIMATOR_POLICY.json');before=json.loads(subprocess.check_output(['git','show','HEAD:ESTIMATOR_POLICY.json'],cwd=work,encoding='utf-8'))
    assert policy['formal_baseline']==before['formal_baseline'] and policy['approved_alternates']==before['approved_alternates']
    status=load(ROOT/'results/preflight_status.json');assert status['status']=='COMPLETE_OBJECTIVE_CALIBRATED_FULL120' and not status['blocking_items']
    required=[ROOT/'reports/R152_RESULTS.md',ROOT/'reports/R152_AUDIT.md',ROOT/'poster_assets/full120/START_HERE.md',ROOT/'poster_assets/full120/POSTER_TEXT.md']
    for stem in ['01_aggregate_results','02_condition_results','03_representative_outputs','04_measurement_protocol']:
        required.extend(ROOT/f'poster_assets/full120/{stem}.{ext}' for ext in ['png','svg'])
    for f in required:assert f.is_file(),f
    result=dict(passed=True,source_files_rechecked=len(sources),source_files_unchanged=True,images_verified=166,pairs_per_method=120,center_rows=4482,pair_rows=360,center_to_pair_max_numeric_difference=maxerr,raw_wiener_original_max_difference=delta.to_dict(),same_learned_checkpoint_across_magnifications=True,objective_specific_optics=True,single_psf_adapter_verified=True,full_four_condition_result=True,measurement_protocol_matches_paper=True,exact_submitted_model_implementation=False,user_authorized_optical_input_adapter=True,formal_baseline_unchanged=True,blocked=None,artifacts=[dict(path=str(f.relative_to(ROOT)),sha256=sha(f)) for f in required])
    (ROOT/'results/full120/delivery_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
