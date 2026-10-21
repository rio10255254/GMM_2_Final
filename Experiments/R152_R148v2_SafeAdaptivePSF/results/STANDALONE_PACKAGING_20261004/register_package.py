"""Register the tested delivery while preserving existing model decisions."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
receipt=json.loads((OUT/'package_receipt.json').read_text(encoding='utf-8'))
assert receipt['status']=='passed' and receipt['all_archive_files_sha256_verified']
report=ROOT/'reports/R152_STANDALONE_PACKAGE_20261004.md'
content=report.read_text(encoding='utf-8')
for old,new in [('第一轮','第一輪'),('噪声与','噪聲與'),('塞进','塞進'),('改变','改變'),('独立','獨立')]:content=content.replace(old,new)
report.write_text(content,encoding='utf-8')
state=PROJECT/'PROJECT_STATE.md';content=state.read_text(encoding='utf-8-sig')
for old,new in [('独立','獨立'),('文档锁','文件來源鎖'),('新包装','新包裝')]:content=content.replace(old,new)
state.write_text(content,encoding='utf-8')
path=PROJECT/'ESTIMATOR_POLICY.json';before=path.read_bytes();policy=json.loads(before.decode('utf-8-sig'))
baseline=copy.deepcopy(policy['formal_baseline']);alternates=copy.deepcopy(policy['approved_alternates'])
policy['artifact_index']['R152_python_standalone_20261004']={
    'date':'2026-10-04','status':'complete','role':'portable model training/inference delivery',
    'package':'Deliverables/R152_Standalone_20261004','archive':'Deliverables/R152_Standalone_20261004.zip',
    'report':'Experiments/R152_R148v2_SafeAdaptivePSF/reports/R152_STANDALONE_PACKAGE_20261004.md',
    'training_entry':'Deliverables/R152_Standalone_20261004/train.py',
    'inference_entry':'Deliverables/R152_Standalone_20261004/infer.py',
    'all_control_files_python':True,'training_parents':768,'training_views':3072,
    'published_weight_tensors_exact':209,'published_native_sample_inference_exact':True,
    'source_input_views_exact':True,'resume_and_relocated_runtime_verified':True,
    'bytes':receipt['bytes'],'archive_sha256':receipt['archive_sha256'],
    'packaging_not_new_formal_training':True,
}
note='2026-10-04 R152 independent Python-only control/configuration package completed with all 768 parents/3072 views and geometry, actual PSFs, frozen-base and deployed weights. All source inputs and 209 published tensors, first four loss rows and whole real-frame native output match exactly. Resume, two-stage short run, post-update assessment continuation, CPU/CUDA, 8/16-bit image loading and alternate-location execution with original experiment reads denied passed. No original trained tensors/data changed and no formal 8192-update retraining was run; only the previously authorized report documentation hash was refreshed in the old source lock. Package and archive are registered without changing production roles.'
if note not in policy['notes']:policy['notes'].append(note)
assert path.read_bytes()==before
path.write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
saved=json.loads(path.read_text(encoding='utf-8'))
assert saved['formal_baseline']==baseline and saved['approved_alternates']==alternates
entry=saved['artifact_index']['R152_python_standalone_20261004']
for key in ('package','archive','report','training_entry','inference_entry'):assert (PROJECT/entry[key]).exists()
for relative,expected in json.loads((ROOT/'config/SOURCE_LOCK.json').read_text(encoding='utf-8'))['files'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==expected,relative
print('PASS: independent package registered, required entry paths exist, original source lock is consistent')
