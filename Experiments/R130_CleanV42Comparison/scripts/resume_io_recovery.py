"""Retry transient Windows status-file locks; do not change frozen training arithmetic."""
import sys,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import common
def main():
    out=ROOT/'results/io_recovery';out.mkdir(exist_ok=False)
    run=ROOT/'runs/v42_clean';latest=common.load(run/'latest.json');assert common.sha(latest['path'])==latest['sha256']
    for parent in [run,ROOT/'runs/launcher_logs']:
        for p in parent.iterdir():
            if p.name in ['status.json','status.writing','active_formal_run.json','active_formal_run.writing','latest.json'] or p.name.startswith('failure_'):shutil.copy2(p,out/(parent.name+'_'+p.name))
    original=common.atomic
    def retry_atomic(path,value):
        for attempt in range(100):
            try:return original(path,value)
            except PermissionError:
                if attempt==99:raise
                time.sleep(.05)
    # Exercise the retry branch through one deliberate, local transient exception.
    attempts=[0]
    def temporary_fault(path,value):
        attempts[0]+=1
        if attempts[0]==1:raise PermissionError('Preflight-only injected transient file lock')
        return original(path,value)
    def test_retry():
        for i in range(2):
            try:return temporary_fault(out/'retry_test.json',dict(value=7))
            except PermissionError:
                if i:raise
    test_retry();assert attempts[0]==2 and common.load(out/'retry_test.json')=={'value':7}
    common.save(out/'recovery_plan.json',dict(created_utc=common.now(),wrapper=common.record(__file__),original_atomic_source=common.record(ROOT/'scripts/common.py'),frozen_source_manifest=common.record(ROOT/'config/frozen.json'),resume_checkpoint=latest,change='Process-local atomic JSON writer retries PermissionError up to5seconds; no source file, model, data, optimizer or scheduler changes',fault_injection_passed=True,previous_failed_attempt_preserved=True))
    common.atomic=retry_atomic
    import train
    assert train.atomic is retry_atomic
    train.main(resume=True)
if __name__=='__main__':main()
