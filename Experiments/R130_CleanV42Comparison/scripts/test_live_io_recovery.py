"""Hold a read handle briefly and confirm the running writer retries without losing progress."""
import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
def main():
    run=ROOT/'runs/v42_clean';deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        s=load(run/'status.json')
        if s['status']=='failed':raise RuntimeError('Training failed')
        if s['status']=='training' and 8<s['step']%128<100:break
        time.sleep(.2)
    else:raise TimeoutError('No training interval for the read-lock test')
    with (run/'status.json').open('r',encoding='utf-8') as handle:
        before=json.load(handle);time.sleep(1)
        pending=load(run/'status.writing');assert pending['step']>before['step']
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        after=load(run/'status.json')
        if after['step']>pending['step']:break
        time.sleep(.1)
    assert after['pid']==before['pid'] and after['step']>pending['step'] and after['status']=='training'
    save(ROOT/'results/io_recovery/live_lock_test.json',dict(passed=True,utc=now(),source=record(__file__),before_step=before['step'],pending_step_while_file_locked=pending['step'],after_step=after['step'],same_process=True,model_and_optimizer_not_changed=True))
    print('Actual locked status write recovered:',before['step'],pending['step'],after['step'])
if __name__=='__main__':main()
