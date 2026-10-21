from common import *
import subprocess,time

def main():
    while True:
        ready=all((ROOT/'results'/model/'complete.json').exists() for model in ['R61','R129']) and (ROOT/'results/measurements_complete.json').exists()
        if ready:break
        for name in ['R61','R129']:
            p=ROOT/f'results/status_{name}.json'
            if p.exists() and load(p).get('status')=='failed':raise RuntimeError('Reconstruction failed: '+name)
        if (ROOT/'results/measurement_failure.json').exists():raise RuntimeError('Measurement process reported failure')
        time.sleep(20)
    for script in ['analyze.py','figures.py','verify_results.py','publish.py']:
        save(ROOT/'results/status_delivery.json',dict(stage=script,status='running',updated_utc=now()))
        with (ROOT/'results'/('log_'+script+'.txt')).open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            save(ROOT/'results/status_delivery.json',dict(stage=script,status='failed',updated_utc=now()));raise RuntimeError(script+' failed')
        print('Finished',script,flush=True)
    save(ROOT/'results/status_delivery.json',dict(stage='visual_review',status='ready',updated_utc=now()))
if __name__=='__main__':main()
