"""Stream only new R128 LSC measurements, then compare all four frozen methods."""
from common import *
import time,subprocess
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from lsc_measure import measure_run
OUT=ROOT/'results/lsc/r128_extension'

def main():
    OUT.mkdir(parents=True,exist_ok=True);plan=load(ROOT/'config/plan.json');jobs=[r['run'] for r in plan['runs'] if not (ROOT/'results/lsc/centers/R128'/(r['run']+'.json')).exists()];done_count=30-len(jobs);running={}
    with ProcessPoolExecutor(max_workers=2) as pool:
        while jobs or running:
            for run in list(jobs):
                if len(running)<2 and (ROOT/'results/R128'/run/'31.json').exists():running[pool.submit(measure_run,'R128',run)]=run;jobs.remove(run)
            done,_=wait(running,timeout=10,return_when=FIRST_COMPLETED) if running else (set(),set())
            for future in done:
                run=running.pop(future)
                try:future.result()
                except BaseException:
                    import traceback
                    save(OUT/'status.json',dict(status='failed',stage='LSC',run=run,error=traceback.format_exc()));raise
                done_count+=1;print('R128 LSC',done_count,'/30',flush=True)
            status=ROOT/'results/status_R128.json'
            if status.exists() and load(status).get('status')=='failed':save(OUT/'status.json',dict(status='failed',stage='reconstruction'));raise RuntimeError('R128 reconstruction failed')
            save(OUT/'status.json',dict(status='running',stage='LSC',finished_scans=done_count,total_scans=30,pid=os.getpid(),updated_utc=now()))
            if not running and jobs:time.sleep(10)
    save(ROOT/'results/lsc/centers/R128/complete.json',dict(model='R128',scans=30,frames=930,centers=8370,completed_utc=now()))
    while not (ROOT/'results/R128/complete.json').exists():time.sleep(2)
    methods=['Raw','R61','R129','R128']
    steps=[['analyze.py','--models',*methods,'--input','results/lsc/readouts','--primary-roi','center9','--primary-reader','LSC','--out','results/lsc/four_model_analysis/tables'],['lsc_details.py','--models',*methods,'--output','results/lsc/four_model_analysis'],['lsc_publish.py','--models',*methods,'--output','results/lsc/four_model_analysis','--report','reports/R136_LSC_FOUR_MODEL_RESULTS.md','--figures','reports/lsc_four_model_figures']]
    for argv in steps:
        save(OUT/'status.json',dict(status='running',stage=argv[0],updated_utc=now()))
        with (OUT/(argv[0]+'.log')).open('w',encoding='utf-8') as f:result=subprocess.run([sys.executable,str(ROOT/'scripts'/argv[0]),*argv[1:]],stdout=f,stderr=subprocess.STDOUT)
        if result.returncode:save(OUT/'status.json',dict(status='failed',stage=argv[0]));raise RuntimeError(argv[0]+' failed; inspect log')
    save(OUT/'status.json',dict(status='ready',stage='visual_review_and_registration',updated_utc=now()))
if __name__=='__main__':main()
