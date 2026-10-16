"""Register the completed research record without changing existing model roles."""
import copy
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
PROJECT=ROOT.parents[1]
policy=PROJECT/'ESTIMATOR_POLICY.json'
before=policy.read_bytes()
data=json.loads(before.decode('utf-8-sig'))
baseline=copy.deepcopy(data['formal_baseline'])
alternates=copy.deepcopy(data['approved_alternates'])
results=json.loads((OUT/'complete_results.json').read_text(encoding='utf-8'))
receipt=json.loads((OUT/'PACKAGE_RECEIPT.json').read_text(encoding='utf-8'))
assert receipt['status']=='passed' and receipt['all_archive_members_verified']
relative='Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_RAW_FULL_RECORD_20261002/REPORT.md'
assert (PROJECT/relative).is_file()
data['artifact_index']['R152_RAW_complete_research_record_20261002']={
    'date':'2026-10-02','status':'complete','role':'thesis research record',
    'methods':['RAW','R152'],'canonical_report':relative,
    'complete_archive':'Deliverables/R152_RAW_COMPLETE_RESEARCH_RECORD_20261002.zip',
    'paired_scans':30,'images_per_method':930,'circles_per_method':8370,
    'primary_definition':'sample SD of 30 observed adjacent steps within each scan; pooled after within-scan centering',
    'RAW_pooled_within_scan_sd_nm':results['within_scan'][0]['pooled_within_scan_sd_nm'],
    'R152_pooled_within_scan_sd_nm':results['within_scan'][1]['pooled_within_scan_sd_nm'],
    'improved_scans':30,'per_scan_improvement_range_percent':results['per_scan_improvement_range_percent'],
    'SEM_workbook_size_difference_worsens':True,'new_training_or_acquisition':False,
    'report_sha256':hashlib.sha256((PROJECT/relative).read_bytes()).hexdigest(),
    'archive_sha256':receipt['archive_sha256'],
}
note='2026-10-02 RAW/R152 complete research record: primary displacement fluctuation is within one 30-step scan. 30 paired scans are used for the empirical improvement range. Complete saved-readout recalculation and 930 RAW/930 native-output hashes passed; pooled SD 10.199758 to 4.864821 nm, all 30 scans improved. Size/contour repeatability improved, SEM size difference increased, endpoint bias and SD differences remain inconclusive. Canonical report and full data/figure/source reading archive are registered. This records the user-selected thesis model, without changing formal production roles.'
if note not in data['notes']:data['notes'].append(note)
assert data['formal_baseline']==baseline and data['approved_alternates']==alternates
assert policy.read_bytes()==before,'Policy changed concurrently; refresh before updating'
policy.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
saved=json.loads(policy.read_text(encoding='utf-8'))
assert saved['formal_baseline']==baseline and saved['approved_alternates']==alternates
entry=saved['artifact_index']['R152_RAW_complete_research_record_20261002']
assert (PROJECT/entry['canonical_report']).is_file() and (PROJECT/entry['complete_archive']).is_file()
for path,needle in [(PROJECT/'PROJECT_STATE.md','R152 RAW complete research record'),
                    (PROJECT/'Experiments/INDEX.md','R152_RAW_FULL_RECORD_20261002/REPORT.md'),
                    (ROOT/'reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md','R152_RAW_FULL_RECORD_20261002/REPORT.md')]:
    assert needle in path.read_text(encoding='utf-8-sig')
print('PASS: report/data archive registered; new documentation links valid; existing production roles preserved')
