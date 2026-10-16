"""Refresh only the report hash after the previously requested documentation updates."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'config/SOURCE_LOCK.json'
lock=json.loads(path.read_text(encoding='utf-8'))
allowed='reports\\R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md'
changes=[]
for relative,expected in lock['files'].items():
    actual=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    if actual!=expected:
        assert relative==allowed,'Executable/configuration source changed: '+relative
        changes.append(dict(file=relative,previous_sha256=expected,current_sha256=actual,
                            reason='Authorized metric-definition and new report/figure navigation updates'))
        lock['files'][relative]=actual
assert len(changes)==1
lock['documentation_refresh_date']='2026-10-04'
path.write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(Path(__file__).resolve().parent/'documentation_lock_refresh.json').write_text(
    json.dumps(dict(changes=changes,all_other_locked_files_unchanged=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: only the previously updated report hash was refreshed; all 33 other locked files match')
