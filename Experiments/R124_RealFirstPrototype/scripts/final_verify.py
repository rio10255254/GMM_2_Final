"""Verify completed prototype scope and preserve scientific limitations."""
import csv,hashlib,json,pathlib,re
import cv2,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    tests=(ROOT/'runs/launcher_logs/all_tests_v1.log').read_text(encoding='utf-8-sig')
    assert 'Ran 26 tests' in tests and tests.rstrip().endswith('OK')
    back=read(ROOT/'results/backward_v1/status.json');tiles=read(ROOT/'results/tiles_v1/status.json')
    assert back['status']==tiles['status']=='passed' and back['optimizer_updates']==0 and back['weights_unchanged']
    assert back['shape']==[2,1,640,640] and back['parameter_count']==301212
    assert all(r['maximum_abs_difference']<=2e-6 for r in tiles['cases'])
    assert tiles['max_kernel']['maximum_abs_difference']<=5e-6 and tiles['zero_context_difference']>1e-4
    a=np.load(next((ROOT/'results/cli_initial').glob('*.npz')))['output'];b=np.load(next((ROOT/'results/cli_reload').glob('*.npz')))['output'];assert np.array_equal(a,b)
    smoke=ROOT/'results/real_smoke_v1';s=read(smoke/'summary.json');assert s['output_count']==12 and not s['efficacy_evaluated']
    identity=[]
    for row in s['outputs']:
        data=np.load(smoke/row['source_name']/row['profile_name']/'output_float.npz')['output'];assert list(data.shape)==row['shape_hw'] and np.isfinite(data).all()
        if row['profile_name']=='identity_assumption':
            raw=cv2.imdecode(np.fromfile(row['source']['path'],dtype=np.uint8),0).astype(np.float32)/255
            assert np.array_equal(raw,data);identity.append(row['source_name'])
    traces=[]
    for profile in ['identity_assumption','gaussian_assumption']:
        with np.load(smoke/'center128_trace'/profile/'four_stages.npz') as d:
            for i in range(4):
                k=f'traces__{i:02d}__';expected=d[k+'state_before']+d[k+'prior_correction']+d[k+'observation_correction']+d[k+'projection_correction'];err=float(np.max(abs(expected-d[k+'state_after'])));assert err<2e-7;traces.append(err)
    semdir=ROOT/'results/sem_smoke_v1/followup_v2';sem=read(semdir/'summary.json');delivery=read(semdir/'delivery_verification.json')
    assert sem['measurements']==432 and sem['raw_parity_cases']==144 and sem['maximum_Raw_per_normal_parity_difference_px']==0
    assert sem['floor_active_crossings']==4 and sem['readout_limitation_detected'] and not sem['full_ACM_evaluated'] and not sem['physical_accuracy_qualified']
    assert delivery['checked_rows']==432 and delivery['checked_profile_populations']==144
    scoped={}
    for name,p in [('real_smoke',smoke/'protected_inputs_after.json'),('SEM_adapter',semdir/'protected_inputs_after.json')]:
        data=read(p);assert data['unchanged']
        for item in data['files']:assert sha(item['path'])==item['sha256'],item['path']
        scoped[name]=len(data['files'])
    historical=read(ROOT.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/protected_inputs_v2.json')
    for p,h in historical.items():assert sha(p)==h,p
    designs=ROOT.parent/'R123_RealFirstModelDesign';old=read(designs/'results/design_verification.json')['design_source_sha256']
    for p,h in old.items():assert sha(designs/p)==h,p
    initial_sampling=read(ROOT/'results/sampling_initial_failure_rows.json');sampling=read(ROOT/'results/sampling_checks.json');assert len(initial_sampling['rows'])==18 and len(sampling['cases'])==36
    preserved=[ROOT/'runs/launcher_logs/network_initial_failure.log',ROOT/'runs/launcher_logs/sampling_v1.log',ROOT/'results/sampling_initial_source.py',ROOT/'results/sem_smoke_v1/failure.json',ROOT/'results/sem_smoke_v1/adapter_source_failed_v1.py']
    assert all(p.exists() for p in preserved)
    total=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());assert total<2*2**30
    result={'status':'prototype_implemented_mechanically_verified_untrained','unit_tests_passed':26,'paired_native_backward_shape':back['shape'],'peak_allocated_gib':back['peak_allocated_gib'],'optimizer_updates':0,'default_parameter_count':301212,'maximum_default_tile_error':max(r['maximum_abs_difference'] for r in tiles['cases']),'max_kernel_test_channels':8,'identity_real_outputs_exact_in_model_FP32_units':len(identity),'real_outputs':12,'trace_stages_recomputed':len(traces),'maximum_trace_closure_error':max(traces),'CLI_float_reload_exact':True,'SEM_readout_rows':432,'SEM_Raw_parity_cases':144,'SEM_floor_sensitive_crossings_retained':4,'protected_sources_by_scope':scoped,'historical_R119_inputs_unchanged':len(historical),'R123_design_sources_unchanged':len(old),'new_model_efficacy_established':False,'instrument_qualified':False,'uncertainty_calibrated':False,'full_ACM_and_full_real_motion_evaluated':False,'confirmation_image_access':False,'preserved_failures':[str(p.relative_to(ROOT)) for p in preserved],'size_gib':total/2**30,'figures_visually_inspected':['results/real_smoke_v1/untrained_real_previews.png','results/sem_smoke_v1/followup_v2/untrained_sem_half_readout.png']}
    dest=ROOT/'results/final_verification.json';dest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    links=0
    for doc in (ROOT/'reports').glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if target.startswith(('https:','http:','#')):continue
            assert (doc.parent/target).resolve().exists(),(doc,target);links+=1
    result['local_report_links_checked']=links
    result['implementation_sha256']={str(p.relative_to(ROOT)):sha(p) for folder in ['model','inference','scripts','tests','config','reports'] for p in (ROOT/folder).glob('*') if p.is_file()}
    dest.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='implementation_sha256'},indent=2))
if __name__=='__main__':main()
