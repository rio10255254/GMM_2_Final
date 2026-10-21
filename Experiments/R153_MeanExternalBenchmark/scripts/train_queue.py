"""Run each eligible ordinary model training sequentially on the one study GPU."""
from pathlib import Path
import os,subprocess,sys,time,datetime
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import save,read
from normal_protocol import COMMON,NORMAL


def main():
    order=['EDSR-x1','NAFNet','RDN-x1','RCAN-x1','Restormer','USRNet-x1','SwinIR']
    log_dir=ROOT/'runs/launcher_logs';log_dir.mkdir(exist_ok=True)
    status={'state':'training_queue','pid':os.getpid(),'formal_training_started':True,
            'training_protocol':'ordinary author loss/optimizer; shared image data and synthetic-validation stopping',
            'common':COMMON,'queue':order,'completed':[],'failed':[],'current_method':None}
    if (ROOT/'config/TIME_BUDGET_OVERRIDE.json').exists():
        status['duration_revision']=read(ROOT/'config/TIME_BUDGET_OVERRIDE.json')
    save(log_dir/'active_formal_run.json',status)
    for method in order:
        complete=ROOT/'runs'/method/'training_complete.json'
        if complete.exists():
            status['completed'].append(method);continue
        status.update(current_method=method,updated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(log_dir/'active_formal_run.json',status)
        with (log_dir/(method+'.log')).open('a',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-B','-X','utf8',str(ROOT/'scripts/train_external.py'),method],
                                     cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT)
            status['child_pid']=process.pid;save(log_dir/'active_formal_run.json',status)
            code=process.wait()
        if code==0 and complete.exists() and read(complete)['state']=='complete':
            status['completed'].append(method)
        else:
            status['failed'].append({'method':method,'returncode':code,'completion_receipt':complete.exists()})
        save(log_dir/'active_formal_run.json',status)
    status.update(state='training_finished_pending_real_validation',current_method=None,child_pid=None,
                  completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save(log_dir/'active_formal_run.json',status)
    print('TRAINING QUEUE FINISHED; real-data benchmark is a separate completion gate.',flush=True)


if __name__=='__main__':main()
