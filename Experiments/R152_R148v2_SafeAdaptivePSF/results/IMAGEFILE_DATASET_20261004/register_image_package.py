"""Record the user's TIFF-only formal training delivery."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
receipt=json.loads((OUT/'package_receipt.json').read_text(encoding='utf-8'))
assert receipt['status']=='passed' and receipt['all_archive_files_verified']
report=ROOT/'reports/R152_TIFF_TRAINING_PACKAGE_20261004.md'
text=report.read_text(encoding='utf-8')
for old,new in [('標记','標記'),('连续','連續'),('没有','沒有')]:text=text.replace(old,new)
report.write_text(text,encoding='utf-8')
policy_path=PROJECT/'ESTIMATOR_POLICY.json';before=policy_path.read_bytes();policy=json.loads(before.decode('utf-8-sig'))
baseline=copy.deepcopy(policy['formal_baseline']);alternates=copy.deepcopy(policy['approved_alternates'])
policy['artifact_index']['R152_TIFF_training_standalone_20261004']={
    'date':'2026-10-04','status':'complete','role':'latest formal-training image-file delivery',
    'package':'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004',
    'archive':'Deliverables/R152_Standalone_ImageFiles_20261004.zip',
    'report':'Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_TIFF_TRAINING_PACKAGE_20261004.md',
    'entry':'Deliverables/Standalone_Models/R152_Standalone_ImageFiles_20261004/train.py',
    'all_controls_python':True,'formal_data_format':'TIFF float32','clear_images':3072,'blur_images':3072,
    'geometry_images':3072,'training_NPZ_files':0,'training_PNG_files':0,
    'all_original_training_inputs_exact':True,'first_four_update_losses_exact':True,
    'resume_exact':True,'model_and_weights_unchanged':True,'archive_sha256':receipt['archive_sha256'],
}
note='2026-10-04 user-selected TIFF-only R152 training delivery completed: the formal reader opens 3072 clear, 3072 blur and 3072 geometry TIFF images directly, with fixed labels/metadata in Python. No training NPZ containers or PNG previews remain. All original training float32 values and 3072 inputs, original first-four losses and 2+2 resume match exactly. The existing model/PSF/weights are unchanged; this converts data storage rather than creating a new trained model. Previous NPZ delivery is preserved as provenance.'
if note not in policy['notes']:policy['notes'].append(note)
assert policy_path.read_bytes()==before
policy_path.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
saved=json.loads(policy_path.read_text(encoding='utf-8'))
assert saved['formal_baseline']==baseline and saved['approved_alternates']==alternates
for key in ('package','archive','report','entry'):
    assert (PROJECT/saved['artifact_index']['R152_TIFF_training_standalone_20261004'][key]).exists()
for path in ('PROJECT_STATE.md','Experiments/INDEX.md'):
    assert 'R152_Standalone_ImageFiles_20261004' in (PROJECT/path).read_text(encoding='utf-8-sig')
print('PASS: TIFF-only image-training delivery registered and current entry paths verified')
