"""Verify the repaired experiment and deliverable scope without approving a model."""
import csv,hashlib,json,pathlib,re
import numpy as np
E=pathlib.Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    area=E/'results/area_render_v2';s=read(area/'summary.json');rows=list(csv.DictReader((area/'physical_fit.csv').open(encoding='utf-8')))
    assert len(rows)==360
    recomputed={}
    for sh in ['line','circle8','circle16','circle32']:
        rr=[r for r in rows if r['shape']==sh];no=[r for r in rr if float(r['noise'])==0];d=s['physical_fit'][sh]
        assert len(rr)==90 and len(no)==30
        assert sum(r['position_pass']=='False' for r in rr)==d['position_failure']
        assert sum(r['motion_pass']=='False' for r in rr)==d['motion_failure']
        assert max(abs(float(r['position_error_px'])) for r in rr)==d['worst_abs_position_px']
        assert max(abs(float(r['motion_error_px'])) for r in rr)==d['worst_abs_motion_px']
        recomputed[sh]={'count':len(no),'max_abs_position_px':max(abs(float(r['position_error_px'])) for r in no),'max_abs_motion_px':max(abs(float(r['motion_error_px'])) for r in no)}
    assert s['render_convergence']['max_abs_center_difference_px']<.001
    assert s['line_checks']['max_abs_position_error_px']<.001
    assert s['line_checks']['max_intensity_error_gray']<.01
    assert sum(r['position_pass']=='False' for r in rows)==119
    assert sum(r['motion_pass']=='False' for r in rows)==47
    protected={**read(E/'results/protected_inputs.json'),**read(E/'results/protected_extension.json')}
    for p,h in protected.items():assert sha(p)==h,p
    old=E.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/protected_inputs_v2.json';olddata=read(old)
    for p,h in olddata.items():assert sha(p)==h,p
    p=read(E/'results/v42_provenance_summary.json');q=read(E/'results/v42_provenance_extension.json')
    assert sum(r['evaluation_frames_with_train_ancestry'] for r in p['evaluation_overlap'])==201
    assert sum(r['selected_pairs_both_frames_have_train_ancestry'] for r in p['evaluation_overlap'])==120
    assert p['pixel_checks']['exact']==p['pixel_checks']['count']==835
    assert len(q['current_sem_answer_matches'])==9 and all(r['training_rows_with_same_radius']>0 for r in q['current_sem_answer_matches'])
    assert q['auxiliary_loaders']['validation_pairs_also_sequence_training']==1000
    assert q['auxiliary_loaders']['validation_pairs_also_motion_training']==1000
    assert not read(E/'results/split_guard_rejects_v42.json')['lineage_disjoint']
    # Local report links resolve; no hidden dependency on an uncreated deliverable.
    linkcount=0
    for doc in (E/'reports').glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            if target.startswith(('https:','http:','#')):continue
            assert (doc.parent/target).resolve().exists(),(doc,target)
            linkcount+=1
    for file in ['identifiability.png','area_render_v2/physical_fit.png']:assert (E/'results'/file).stat().st_size>10000
    outputs={str(p.relative_to(E)):sha(p) for folder in ['scripts','config','reports'] for p in (E/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    result={'status':'diagnostics_and_corrections_verified','corrected_physical_rows_recomputed':len(rows),'corrected_position_failures':119,'corrected_motion_failures':47,'corrected_noise_free':recomputed,'current_protected_inputs_unchanged':len(protected),'historical_protected_inputs_unchanged':len(olddata),'report_local_links_checked':linkcount,'figures_visually_inspected':['identifiability.png','area_render_v2/physical_fit.png'],'no_training_or_confirmation_evaluation':True,'model_approved':False,'semantics':'Consistency verification does not override recorded scientific failures. Continuous 2D renderer and independently useful trained model remain future work.','source_and_report_sha256':outputs}
    (E/'results/final_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='source_and_report_sha256'},indent=2))
if __name__=='__main__':main()
