"""Verify actual long-run start, cooperative pause and continuation, then leave it running."""
import sys,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import psutil
PROJECT_ROOT = Path(__file__).resolve().parents[6]
def main():
    pkg=Path(PROJECT_ROOT / load(ROOT/'config/standalone_build.json')['path']);run=pkg/'results/training/r129_long_01';deadline=time.monotonic()+1200
    def wait_for(predicate):
        while time.monotonic()<deadline:
            path=run/'status.json'
            if path.exists():
                state=load(path)
                if state['status']=='failed':raise RuntimeError(state.get('error','Training failed'))
                if predicate(state):return state
            time.sleep(2)
        raise TimeoutError('Long-run status did not reach the required state')
    started=wait_for(lambda s:s['status']=='training' and s['completed_updates']>=3)
    assert psutil.pid_exists(started['pid'])
    r=subprocess.run([sys.executable,'-B',str(pkg/'control.py'),'pause'],capture_output=True,text=True);assert r.returncode==0
    paused=wait_for(lambda s:s['status']=='paused')
    checkpoint=pkg/paused['latest_checkpoint']['path'];assert checkpoint.is_file() and sha(checkpoint)==paused['latest_checkpoint']['sha256']
    while (run/'active.lock').exists() and time.monotonic()<deadline:time.sleep(1)
    r=subprocess.run([sys.executable,'-B',str(pkg/'control.py'),'resume'],capture_output=True,text=True);assert r.returncode==0
    continued=wait_for(lambda s:s['status']=='training' and s['pid']!=started['pid'] and s['completed_updates']>=paused['completed_updates']+3)
    assert psutil.pid_exists(continued['pid'])
    save(pkg/'results/manual_training_cycle.json',dict(completed_utc=now(),passed=True,initial_pid=started['pid'],paused_updates=paused['completed_updates'],paused_checkpoint=paused['latest_checkpoint'],resumed_pid=continued['pid'],verified_continued_updates=continued['completed_updates'],final_state='running',model_promoted=False))
    save(ROOT/'results/standalone_launch_verified.json',dict(completed_utc=now(),source=record(__file__),package=str(pkg),cycle=record(pkg/'results/manual_training_cycle.json'),observed_status=continued))
    print('Actual pause/resume cycle passed; training remains active:',continued['completed_updates'],'/',continued['planned_updates'],'PID',continued['pid'],flush=True)
if __name__=='__main__':main()
