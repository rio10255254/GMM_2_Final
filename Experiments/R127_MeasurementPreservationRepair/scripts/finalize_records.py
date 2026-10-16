"""Finalize the bounded software scope; preserve open physical requirements."""
from datetime import datetime,timezone
import re
from common import *

def main():
    audit=json.loads((ROOT/'results/repair_verification.json').read_text())
    assert audit['verification_passed'] and not audit['failures']
    prospective=json.loads((ROOT/'results/motion_hierarchy_prospective_v4.json').read_text())
    cli=json.loads((ROOT/'results/cli_checks/verification.json').read_text())
    assert prospective['engineering_checks_passed'] and cli['passed']
    for p in (ROOT/'reports').glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if not link.startswith(('http:','https:','#')):
                assert (p.parent/link).resolve().is_file(),(p,link)
    state=(REPO/'PROJECT_STATE.md').read_text(encoding='utf-8')
    quick=state.split('<!-- QUICK_HANDOFF_START -->')[1].split('<!-- QUICK_HANDOFF_END -->')[0]
    lines=len(quick.strip('\n').splitlines())
    assert lines<=60,lines
    gallery=(REPO/'RECON_GALLERY.md').read_text(encoding='utf-8')
    assert not re.search(r'<(?:table|p|details|img|div|a)\b',gallery,re.I)
    policy_path=REPO/'ESTIMATOR_POLICY.json'
    policy=json.loads(policy_path.read_text(encoding='utf-8-sig'))
    before=json.loads((ROOT/'reports/project_context_before/ESTIMATOR_POLICY.json').read_text(encoding='utf-8-sig'))
    protected=['formal_baseline','approved_alternates','research_state','closed_lines','measurement_policy']
    assert all(policy[k]==before[k] for k in protected)
    assert not any(x['candidate_id']=='R127_measurement_preservation' for x in policy['open_side_tracks'])
    entry={
        'candidate_id':'R127_measurement_preservation',
        'round':'R127 measurement and conditional preservation repair',
        'experiment':'Experiments/R127_MeasurementPreservationRepair',
        'status':'completed_software_repairs_physical_qualification_open',
        'mainline_status':'research_tools_no_model_promotion',
        'reports':{
            'results':'Experiments/R127_MeasurementPreservationRepair/reports/R127_RESULTS.md',
            'methodology':'Experiments/R127_MeasurementPreservationRepair/reports/R127_METHODOLOGY.md',
            'usage':'Experiments/R127_MeasurementPreservationRepair/reports/R127_USAGE.md',
            'physical_requirements':'Experiments/R127_MeasurementPreservationRepair/reports/R127_ACQUISITION_PLAN.md'
        },
        'optimizer_updates':0,
        'fullfield_outputs':48,
        'fullfield_model_pairs':24,
        'maximum_change_from_fullfield_Raw_px':audit['maximum_fullfield_Raw_difference'],
        'old_core_parity':'all48bitwise_equal',
        'physical_accuracy_qualified':False,
        'universal_real_clean_detection':False,
        'model_promoted':False,
        'notes':'Native SEM size/pitch and explicit rim definitions separate scaling from segmentation. A third prospectively frozen72case image/continuous control check passes at0.015998px maximum error; earlier failures remain. All4R126models are rerun on12full source frames, yielding24valid dominant-translation comparisons within0.000511px of full-fieldRaw and exact old-core parity. R126local phase jumps are not evidence of comparable whole-image displacement. Conditional exact preservation covers6known identity parents plus100arbitrary inputs, with ordinary noisy/blurred restoration retained; unknown real inputs never certified clean.5242older files unchanged. Material-edge correspondence, actual-position evidence and qualified model usefulness remain open.'
    }
    policy['open_side_tracks'].insert(0,entry)
    for track in policy['open_side_tracks']:
        if track['candidate_id']=='R126_learnability_photometry':
            track['interpretation_followup']='R127 full-field same-weight evaluation resolves the old local-readout jumps as insufficient evidence of whole-image displacement; size/physical-target issues still prevent adoption. See R127 canonical results.'
    policy['notes'].append('2026-09-08 R127: completed bounded measurement and conditional preservation repairs,0newoptimizer updates. Native SEM reference definitions are explicit, full-fieldsame-weight R126motion is consistent withRaw, and exactknown-noiselessidentity preservation is verified. No physical-stage accuracy, universal real clean detection, new unseen confirmation or model promotion is claimed.')
    assert all(policy[k]==before[k] for k in protected)
    storage_path=REPO/'docs/operations/PROJECT_STORAGE_REGISTRY.json'
    storage=json.loads(storage_path.read_text(encoding='utf-8'))
    item=next(x for x in storage['entries'] if x['id']=='r127_measurement_preservation')
    size=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())/2**30
    assert size<3
    item.update(state='completed_software_repairs_physical_qualification_open',size_gib_snapshot=round(size,6),keep='Retain native SEM sources/definition results, all failed reader versions and checks, prospective verification, conditional preservation controls,30local/context and24fullfield comparisons,48full outputs and exactold-core parity.0new training. Budget3GiB; old sources referenced in place, no archive/deletion or oldevidence rebaseline.')
    old=verify_old()
    assert old['unchanged']
    # Mutations occur only after read-only checks succeed.
    policy_path.write_text(json.dumps(policy,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    storage_path.write_text(json.dumps(storage,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    verify_policy=json.loads(policy_path.read_text(encoding='utf-8'))
    assert all(verify_policy[k]==before[k] for k in protected)
    final={
        'status':'bounded_software_repairs_verified_physical_validation_open',
        'finished_utc':datetime.now(timezone.utc).isoformat(),
        'old_sources':old,'new_optimizer_updates':0,
        'native_SEM_images':9,'physical_pillars':36,'native_size_records':360,
        'prospective_parameter_cases':72,'prospective_maximum_error_px':prospective['maximum_admitted_error'],
        'fullfield_outputs':48,'fullfield_model_pairs':24,'old_core_bitwise_parities':48,
        'maximum_fullfield_Raw_difference_px':audit['maximum_fullfield_Raw_difference'],
        'known_identity_parents':6,'arbitrary_identity_inputs':100,
        'CLI_tests_passed':True,'plots_visually_checked':3,
        'formal_policy_roles_unchanged':True,'quick_handoff_lines':lines,
        'size_gib_snapshot':size,'model_promoted':False,
        'physical_stage_truth_available':False,'physical_edge_equivalence_qualified':False,
        'universal_real_clean_detection_claimed':False,
        'old_confirmation_access':False,'new_real_holdout_claimed':False,
        'remaining_physical_requirements':['Independent actual-position records corresponding to images','Same physical SEM/optical edge correspondence','Qualified model benefit beyond these reused development images'],
        'source_and_report_sha256':{str(p.relative_to(ROOT)):sha(p) for folder in ['scripts','config','reports'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts},
        'repair_audit_sha256':sha(ROOT/'results/repair_verification.json'),
        'CLI_check_sha256':sha(ROOT/'results/cli_checks/verification.json')
    }
    save(ROOT/'results/final_verification.json',final)
    marker=json.loads((ROOT/'runs/launcher_logs/active_formal_run.json').read_text())
    marker.update(status='completed_bounded_software_repairs',active=False,optimizer_updates=0,fullfield_outputs=48,fullfield_model_pairs=24,final_verification='results/final_verification.json',physical_requirements_still_open=True,model_promoted=False,finished_utc=final['finished_utc'])
    save(ROOT/'runs/launcher_logs/active_formal_run.json',marker,False)
    save(ROOT/'runs/closeout.json',marker)
    print(json.dumps({k:v for k,v in final.items() if k!='source_and_report_sha256'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
