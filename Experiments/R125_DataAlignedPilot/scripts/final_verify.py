"""Final consistency checks. A passed audit is not model/data real-use qualification."""
import csv,hashlib,json,pathlib,sqlite3
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def rows(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def main():
    v1=load(ROOT/'results/data_audit_v1.json');v2=load(ROOT/'results/data_audit_v2.json');assert v1['pilot_admitted'] is False and v2['pilot_admitted'] is True
    assert len(v2['scenes'])==64 and not any(s['failures'] for s in v2['scenes'])
    assert sha(ROOT/'data/package_v2/manifest.json')==v2['manifest_sha256']
    execution=load(ROOT/'results/execution_audit_independent_v2.json');assert execution['execution_integrity_passed'] and execution['completed_optimizer_updates_verified']==384 and execution['all_runs_complete'] and len(execution['runs'])==6 and not execution['failures']
    for p,h in execution['implementation_source_sha256'].items():assert sha(p)==h,p
    matrix=load(ROOT/'runs/matrix_state.json');assert matrix['status']=='bounded_matrix_completed_not_promoted' and matrix['completed_updates']==384
    assert matrix['initial_evaluations_complete_before_optimizer_updates']
    assert all(e['returncode']==0 for e in matrix['events'])
    real=load(ROOT/'results/real_comparison/summary.json');assert real['checkpoint_evaluations']==12 and real['sem_rows']==1728 and real['motion_rows']==72
    assert real['empty_common_cases']==real['below90pct_common_cases']==0
    per=rows(ROOT/'results/real_comparison/all12_common_sem_per_pillar.csv');exp=rows(ROOT/'results/real_comparison/sem_exposure_comparison.csv');assert len(per)==1728
    for e in exp:
        r=[x for x in per if all(x[k]==e[k] for k in ['arm','seed','step','reference','exposure'])];assert len(r)==36
        value=float(np.median([float(x['common_mae_change_vs_Raw_px']) for x in r]));assert abs(value-float(e['median_pillar_change_vs_Raw_px']))<1e-12
        if int(e['step'])==64:
            if e['arm']=='A' and e['exposure']=='13':assert value<0
            else:assert value>0
    for x in per:
        assert abs((float(x['common_mae_px'])-float(x['raw_common_mae_px']))-float(x['common_mae_change_vs_Raw_px']))<1e-12
    motion=rows(ROOT/'results/real_comparison/motion_comparison.csv');assert len(motion)==72
    ref=load(ROOT/'results/training_reference_diagnostic/verification.json');assert ref['protected_sources_unchanged'] and ref['model_forward_calls']==72 and ref['all_shared_core_references_exact_across_checkpoints']
    photo=load(ROOT/'results/real_photometry_scope.json');assert photo['training_or_model_changed'] is False and len(photo['real_rows'])==72
    assert all(x['outside_training_level_envelope']==36 for x in photo['real_summary'])
    old=load(ROOT.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/protected_inputs_v2.json')
    for p,h in old.items():assert sha(p)==h,p
    base=ROOT.parent/'R124_RealFirstPrototype';oldmodel=load(base/'results/final_verification.json')['implementation_sha256']
    for p,h in oldmodel.items():assert sha(base/p)==h,p
    notebook=load(ROOT/'reports/R125_DATA_FIT.ipynb');code=[c for c in notebook['cells'] if c['cell_type']=='code'];assert len(code)==10 and all(c['execution_count'] is not None for c in code)
    assert not any(o.get('output_type')=='error' for c in code for o in c.get('outputs',[]))
    receipt=load(ROOT/'results/report_delivery_receipt.json');assert receipt['ok'] and receipt['stages']['verification']=='passed' and receipt['viewports']==[1440,390]
    artifact=load(ROOT/'reports/R125_REPORT.artifact.json');con=sqlite3.connect(ROOT/'results/report_snapshot.sqlite');con.row_factory=sqlite3.Row
    for source in artifact['manifest']['sources']:
        if source['id'].startswith('render_'):
            name=source['id'][7:];actual=[dict(x) for x in con.execute(source['query']['sql'])];assert actual==artifact['snapshot']['datasets'][name]
    con.close()
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());assert size<12*2**30
    tests=(ROOT/'runs/launcher_logs/all_tests_frozen.log').read_text(encoding='utf-8-sig');assert 'Ran 31 tests' in tests and tests.rstrip().endswith('OK')
    out={'status':'bounded_data_repair_and_pilot_complete_not_adopted','source_and_model_fit_admitted':True,'complete_real_training_dataset_claimed':False,'real_calibration_qualified':False,'new_model_promoted':False,'data_scenes':64,'views':128,'trained_runs':6,'optimizer_updates':384,'real_checkpoint_evaluations':12,'real_outputs':216,'SEM_rows_recomputed':1728,'motion_rows':72,'training_reference_forwards':72,'all31_pretraining_tests_passed':True,'executed_notebook_code_cells':len(code),'R119_protected_files_unchanged':len(old),'R124_implementation_files_unchanged':len(oldmodel),'report_browser_verified':True,'report_viewports':receipt['viewports'],'report_mode':'single_portable_HTML_official_reader_with_scoped_classic_scrollbar_fix','report_SQL_is_executed_formatting_adapter_not_original_scientific_analysis':True,'size_gib':size/2**30,'remaining':['source-disjointlearnabilitytest','realphotometry/contrastcoverage','independentrealoptics/readoutcalibration','fullACM/fullmotion/independentrealconfirmation'],'source_sha256':{str(p.relative_to(ROOT)):sha(p) for folder in ['prototype','training','scripts','config','reports'] for p in (ROOT/folder).glob('*') if p.is_file() and p.suffix in ['.py','.json','.md','.ipynb','.html','.mjs']}}
    (ROOT/'results/final_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in out.items() if k!='source_sha256'},indent=2))
if __name__=='__main__':main()
