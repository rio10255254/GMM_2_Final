from r135_common import *
from publish import publish,ORDER
import psutil,subprocess,traceback
def state(phase,**kw):atomic(ROOT/'results/status.json',dict(phase=phase,utc=now(),pid=os.getpid(),training_updates=0,model_promoted=False,**kw));publish()
def main():
    state('running',current='V42_old')
    while not (ROOT/'results/V42_old/complete.json').exists():
        if (ROOT/'results/V42_old/failure.json').exists():raise RuntimeError(load(ROOT/'results/V42_old/failure.json')['error'])
        if not psutil.pid_exists(26180):raise RuntimeError('Initial V42 worker stopped without completion')
        time.sleep(3)
    # Wait for a fully written completion record, never accept partial output.
    for _ in range(40):
        try:load(ROOT/'results/V42_old/complete.json');break
        except json.JSONDecodeError:time.sleep(.25)
    for tag in ['Raw','V42_clean','R61','R128','R129_W16','R134_P1']:
        for r in load(ROOT/'config/dependencies.json')['sources']:assert sha(r['path'])==r['sha256']
        state('running',current=tag)
        with (ROOT/f'results/{tag}.log').open('xb') as log:r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_model.py'),tag],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError(load(ROOT/f'results/{tag}/failure.json')['error'])
        c=load(ROOT/f'results/{tag}/complete.json');assert c['frames']==201 and c['SEM_rows']==108 and c['independent_motion_refits']==1809
    verify();records=[]
    for tag in ORDER:
        c=load(ROOT/f'results/{tag}/complete.json')
        for r in c['sources']:assert sha(r['path'])==r['sha256']
        records.append(record(ROOT/f'results/{tag}/complete.json'))
    for r in load(ROOT/'config/dependencies.json')['sources']:assert sha(r['path'])==r['sha256']
    save(ROOT/'results/complete.json',dict(methods=7,models=6,motion_frames=1407,SEM_rows=756,records=records,originals_unchanged=True,model_promoted=False));state('complete',completion=record(ROOT/'results/complete.json'))
if __name__=='__main__':
    try:main()
    except BaseException:state('failed',error=traceback.format_exc());raise
