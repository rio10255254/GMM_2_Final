from r135_common import *
from publish import publish,ORDER
import subprocess,traceback
def state(phase,**kw):atomic(ROOT/'results/status.json',dict(phase=phase,utc=now(),pid=os.getpid(),training_updates=0,model_promoted=False,**kw));publish()
def main():
    state('running',current='R61',recovery='R61 native reader has no external anchor stage; original failed adapter and records preserved')
    for tag in ORDER:
        path=ROOT/f'results/{tag}/complete.json'
        if path.exists():
            c=load(path)
            for r in c['sources']:assert sha(r['path'])==r['sha256']
            continue
        for r in load(ROOT/'config/dependencies.json')['sources']:assert sha(r['path'])==r['sha256']
        state('running',current=tag)
        with (ROOT/f'results/{tag}_v3.log').open('xb') as log:r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_model_v3.py'),tag],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError(load(ROOT/f'results/{tag}/failure.json')['error'])
        c=load(path);assert c['frames']==201 and c['SEM_rows']==108 and c['independent_motion_refits']==1809
    verify();records=[]
    for tag in ORDER:
        c=load(ROOT/f'results/{tag}/complete.json')
        for r in c['sources']:assert sha(r['path'])==r['sha256']
        records.append(record(ROOT/f'results/{tag}/complete.json'))
    for r in load(ROOT/'config/dependencies.json')['sources']:assert sha(r['path'])==r['sha256']
    save(ROOT/'results/complete.json',dict(methods=7,models=6,motion_frames=1407,SEM_rows=756,records=records,originals_unchanged=True,model_promoted=False,adapter_recovery='R61 external anchor omitted exactly as its original run_one; first failure retained'));state('complete',completion=record(ROOT/'results/complete.json'))
if __name__=='__main__':
    try:main()
    except BaseException:state('failed',error=traceback.format_exc());raise
