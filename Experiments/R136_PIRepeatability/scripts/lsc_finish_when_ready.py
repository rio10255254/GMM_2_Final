from common import *
import time,subprocess
def main():
    while not (ROOT/'results/lsc/complete.json').exists():
        if (ROOT/'results/lsc/failure.json').exists():raise RuntimeError('LSC measurement failed; inspect saved error')
        if load(ROOT/'results/status_R129.json').get('status')=='failed':raise RuntimeError('R129 reconstruction failed')
        time.sleep(20)
    steps=[['analyze.py','--input','results/lsc/readouts','--primary-roi','center9','--primary-reader','LSC','--out','results/lsc/analysis/tables'],['lsc_details.py'],['lsc_publish.py']]
    for argv in steps:
        save(ROOT/'results/lsc/delivery_status.json',dict(stage=argv[0],status='running',updated_utc=now()))
        with (ROOT/'results/lsc'/('log_'+argv[0]+'.txt')).open('w',encoding='utf-8') as log:process=subprocess.run([sys.executable,str(ROOT/'scripts'/argv[0]),*argv[1:]],stdout=log,stderr=subprocess.STDOUT)
        if process.returncode:
            save(ROOT/'results/lsc/delivery_status.json',dict(stage=argv[0],status='failed',updated_utc=now()));raise RuntimeError(argv[0]+' failed')
    save(ROOT/'results/lsc/delivery_status.json',dict(stage='visual_review_and_registration',status='ready',updated_utc=now()))
if __name__=='__main__':main()
