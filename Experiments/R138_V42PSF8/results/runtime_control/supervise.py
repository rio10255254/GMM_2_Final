from pathlib import Path
import sys,os,subprocess,json,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from utils import load,save,now,sha,verify_frozen,verify_protected

def main():
 if (ROOT/'results/complete.json').exists():print('Already complete');return
 if (HERE/'supervisor.json').exists():
  import psutil
  old=load(HERE/'supervisor.json')
  if psutil.pid_exists(old['pid']) and old['pid']!=os.getpid():
   proc=psutil.Process(old['pid'])
   if abs(proc.create_time()-old['create_time'])<1:raise RuntimeError('This supervisor already runs')
 import psutil
 save(HERE/'supervisor.json',dict(pid=os.getpid(),create_time=psutil.Process().create_time(),started_utc=now()))
 current=load(HERE/'execution_device.json')
 while not (ROOT/'runs/formal_8192/training_complete.json').exists():
  env=dict(os.environ);env['PYTHONWARNINGS']='ignore::FutureWarning'
  if current['device']=='cpu':env['CUDA_VISIBLE_DEVICES']='-1'
  else:env.pop('CUDA_VISIBLE_DEVICES',None)
  save(ROOT/'runs/pipeline_status.json',dict(state='running',phase='train_worker',device=current['device'],threads=current['threads'],pid=os.getpid(),updated_utc=now()))
  result=subprocess.run([sys.executable,'-u','-B',str(HERE/'train_worker.py'),'--device',current['device'],'--threads',str(current['threads'])],cwd=ROOT,env=env)
  if result.returncode==75:
   request=load(HERE/'switch_request.json');current={k:request[k] for k in ['device','threads']};save(HERE/'execution_device.json',current)
   name='applied_request_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json';(HERE/'switch_request.json').rename(HERE/name)
   continue
  if result.returncode:save(ROOT/'runs/pipeline_failure.json',dict(state='failed',stage='train_worker',exit_code=result.returncode,utc=now()));raise SystemExit(result.returncode)
 for stage in ['evaluate_real_measurement.py','compare_measurements.py','final_audit.py','write_report.py','closeout.py']:
  save(ROOT/'runs/pipeline_status.json',dict(state='running',phase=stage,device=current['device'],threads=current['threads'],updated_utc=now()))
  result=subprocess.run([sys.executable,'-u','-B',str(HERE/'stage_worker.py'),'--stage',stage,'--device',current['device'],'--threads',str(current['threads'])],cwd=ROOT)
  if result.returncode:save(ROOT/'runs/pipeline_failure.json',dict(state='failed',stage=stage,exit_code=result.returncode,utc=now()));raise SystemExit(result.returncode)
 save(ROOT/'runs/pipeline_status.json',dict(state='complete',proof='results/complete.json',completed_utc=now()))
 save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(state='complete',completed_updates=8192,images=930,device_history='runs/formal_8192/device_history.jsonl',completed_utc=now()))
if __name__=='__main__':main()
