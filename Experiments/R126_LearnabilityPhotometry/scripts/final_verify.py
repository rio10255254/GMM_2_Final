"""Final arithmetic and completeness validation; scientific outcomes stay distinct."""
import csv,ast
from common import *

def main():
    audit=json.loads((ROOT/'results/execution_audit.json').read_text());assert audit['execution_integrity_passed'] and audit['verified_optimizer_updates']==1280 and not audit['failures']
    comparison=json.loads((ROOT/'results/real_comparison/summary.json').read_text());assert comparison['checkpoint_evaluations']==8
    def rows(path):
        with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    pillar=rows(ROOT/'results/real_comparison/all8_common_sem_per_pillar.csv');expo=rows(ROOT/'results/real_comparison/sem_exposure_comparison.csv')
    assert len(pillar)==1152
    for r in expo:
        selected=[x for x in pillar if all(x[k]==r[k] for k in ['arm','seed','step','reference','exposure'])];assert len(selected)==36
        for metric in ['common_mae_change_vs_Raw_px','common_mae_change_vs_own_step0_px']:
            expected=np.median([float(x[metric]) for x in selected]);key='median_pillar_change_vs_Raw_px' if 'Raw' in metric else 'median_pillar_change_vs_own_step0_px'
            assert abs(expected-float(r[key]))<1e-12
    ref=json.loads((ROOT/'results/reference_diagnostic/verification.json').read_text());assert ref['rows']==216 and ref['common_actual_inputs_verified']
    tile=json.loads((ROOT/'results/learned_tile_verification.json').read_text());assert tile['passed']
    trace=json.loads((ROOT/'results/learned_real_trace_matched/summary.json').read_text());assert trace['passed']
    original_trace=json.loads((ROOT/'results/learned_real_trace/summary.json').read_text());assert original_trace['passed'] is False
    phase=json.loads((ROOT/'results/phase_anatomy_initial/summary.json').read_text());assert phase['maximum_numerical_replay_error_px']<1e-6
    assert json.loads((ROOT/'results/derivative_precision.json').read_text())['passed']
    for p in (ROOT/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
    mandatory=[ROOT/'README.md',ROOT/'MANIFEST.md',ROOT/'reports/R126_RESULTS.md',ROOT/'reports/R126_METHODOLOGY.md',ROOT/'results/README.md']
    assert all(p.is_file() and p.stat().st_size>0 for p in mandatory)
    source=verify_protection();assert source['unchanged']
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file());assert size<4*2**30
    d=dict(status='bounded_learning_and_data_comparison_complete_not_adopted',optimizer_updates=1280,fixed_diagnostic_updates=768,photometry_updates=512,trained_photometry_runs=4,real_evaluations=8,real_float_outputs=144,SEM_common_population_rows=1152,motion_rows=48,reference_diagnostic_view_rows=216,independent_inputs_replayed=256,source_protection=source,learned_tile_max_error=max(r['maximum_absolute_difference'] for r in tile['rows']),original_failed_diagnostics_retained=True,model_promoted=False,real_calibration_qualified=False,uncertainty_calibrated=False,old_confirmation_payload_access=False,size_gib=size/2**30,arithmetic_and_execution_passed=True,scientific_usefulness_not_inferred=True,verified_sources={str(p.relative_to(ROOT)):sha(p) for folder in ['scripts','config','reports'] for p in (ROOT/folder).glob('*') if p.is_file()})
    save(ROOT/'results/final_verification.json',d)
    print(json.dumps({k:v for k,v in d.items() if k!='verified_sources'}),flush=True)

if __name__=='__main__':main()
