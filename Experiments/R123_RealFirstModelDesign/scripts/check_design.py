"""Check design arithmetic, reference integrity and honest completion scope.

This is not a scientific-success or model-release checker.
"""
import csv,hashlib,json,math,pathlib,re
import numpy as np
E=pathlib.Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    a=read(E/'config/architecture.json');t=read(E/'config/training_design.json');v=read(E/'config/validation_contract.json')
    s=a['image_state']['internal_sampling_factor'];rF=s*a['forward_model']['max_kernel_radius_native_px']+s-1
    n=a['learned_prior'];rprior=n['stem_radius_internal_px']+n['head_radius_internal_px']+n['convolutions_per_block']*sum(n['residual_block_dilations'])
    radius=math.ceil(a['iterations']['outer_steps']*(3*rF+rprior)/s)+a['tiling']['maximum_local_conditioner_radius_native_px']+math.ceil(a['geometry']['head_radius_internal_px']/s)+1
    halo=a['tiling']['initial_conservative_halo_native_px'];assert radius==248 and halo>=radius
    b=t['first_bounded_comparison'];assert b['input_patch_native_px']==b['supervised_center_native_px']+2*b['context_per_side_native_px'];assert b['context_per_side_native_px']>=halo
    assert b['training_scenes']*b['passes_over_scenes']//b['scene_batch_size']==b['updates_per_model_seed']==1024
    assert b['primary_comparison_checkpoint_updates']==v['fixed_comparison']['primary_checkpoint_updates']==1024
    assert v['every_short_candidate_runs_real_panel'] and not v['synthetic_performance_gates_access_to_real_panel']
    assert not v['application_thresholds']['unset_allows_long_training_promotion']
    assert not t['existing_real_development_sources_allowed_as_training'] and t['teacher_models']==[]
    assert not v['fixed_comparison']['V42_as_teacher'] and not v['fixed_comparison']['V42_required_to_beat']
    catalog=read(E/'config/real_sources.json');assert all(not r['training_allowed'] for r in catalog['sources'])
    inventory=list(csv.DictReader((E/'results/real_source_inventory.csv').open(encoding='utf-8')));assert len(inventory)==438
    rois=read(E/'config/frozen_real_rois.json');assert rois['count']==len(rois['rois'])==144
    assert len({(r['sequence'],r['tile_id']) for r in rois['rois']})==144
    panel=read(E/'results/real_panel_audit.json');paired=list(csv.DictReader((E/'results/historical_real_paired_pillars.csv').open(encoding='utf-8')));assert len(paired)==144
    for r in panel['historical_real_results']:
        rows=[x for x in paired if x['reference']==r['reference'] and x['method']==r['method']];assert len(rows)==36
        assert abs(float(np.median([float(x['acm_change_pp']) for x in rows]))-r['median_pillar_acm_change_pp'])<1e-14
        assert abs(float(np.median([float(x['half_change_px']) for x in rows]))-r['median_pillar_half_change_px'])<1e-14
        if r['method']=='R109_full':assert r['decision']=='readout_correspondence_unresolved_no_physical_success_claim'
        if r['method']=='R119_full':assert r['decision']=='observed_real_geometry_regression'
    protected={**read(E/'results/protected_inputs.json'),**read(E/'results/protected_roi_inputs.json')}
    for p,h in protected.items():assert sha(p)==h,p
    historical=read(E.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/protected_inputs_v2.json')
    for p,h in historical.items():assert sha(p)==h,p
    r122=E.parent/'R122_OperatorPrinciples';old=read(r122/'results/final_verification.json')['source_and_report_sha256']
    for p,h in old.items():assert sha(r122/p)==h,p
    maths=read(E/'results/operator_math_checks.json');assert maths['adjoint_inner_product_error']<1e-12 and maths['finite_difference_gradient_error']<1e-9
    result={'status':'design_consistent_and_inputs_verified_not_model_success','conservative_native_dependency_bound':radius,'allocated_design_halo':halo,'full_model_runtime_bound_verified':False,'updates_per_candidate_seed':1024,'proposed_candidate_runs':len(b['models'])*len(b['shared_initialization_seeds']),'real_files_read':438,'primary_real_development_files':364,'fixed_legacy_Raw_ROIs':144,'paired_pillar_rows_recomputed':144,'current_input_files_unchanged':len(protected),'old_R119_protected_files_unchanged':len(historical),'R122_source_report_files_unchanged':len(old),'figures_visually_inspected':['real_input_panel.png','real_baseline_replay.png'],'model_implemented':False,'training_executed':False,'real_new_model_performance_verified':False,'application_calibration_complete':False,'new_confirmation_access':False,'remaining_before_decision_bearing_training':['qualified forward calibration and readout correspondence','frozen application benefit and guards','actual model backward/memory/tiling checks','specialized Raw-only corner/gap/defect eligibility annotations']}
    dest=E/'results/design_verification.json';dest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    links=0
    for p in (E/'reports').glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if link.startswith(('https:','http:','#')):continue
            assert (p.parent/link).resolve().exists(),(p,link);links+=1
    result['local_report_links_verified']=links;result['design_source_sha256']={str(p.relative_to(E)):sha(p) for folder in ['config','scripts','reports'] for p in (E/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts};dest.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:w for k,w in result.items() if k!='design_source_sha256'},indent=2))
if __name__=='__main__':main()
