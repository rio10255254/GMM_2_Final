import os
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ.setdefault('PYTHONWARNINGS','ignore::FutureWarning')
from pathlib import Path
import sys,subprocess,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,source_records,verify_frozen,verify_protected,now

def call(file):
 save(ROOT/'runs/pipeline_status.json',dict(state='running',device='cpu',phase=file,pid=os.getpid(),updated_utc=now()))
 print('PHASE',file,flush=True);subprocess.run([sys.executable,'-u','-B',str(ROOT/file)],cwd=ROOT,check=True)
def main():
 if (ROOT/'results/complete.json').exists():print('Already complete: reports/R138_RESULTS.md');return
 try:
  assert load(ROOT/'config_r138_psf.yaml')['device']=='cpu'
  if not (ROOT/'results/preflight.json').exists():call('preflight_check.py')
  assert load(ROOT/'results/preflight.json')['all_required_checks_passed']
  lock=ROOT/'config/source_lock.json'
  if not lock.exists():save(lock,source_records())
  verify_frozen(load(lock));verify_protected()
  import train_r138_psf as trainer
  trainer.MODEL_NAME_BASE=trainer.CFG.MODEL_NAME
  save(ROOT/'runs/pipeline_status.json',dict(state='running',device='cpu',phase='train_r138_psf.py',pid=os.getpid(),updated_utc=now()))
  if not (ROOT/'runs/formal_8192/training_complete.json').exists():trainer.train_formal()
  call('evaluate_real_measurement.py');call('compare_measurements.py');call('final_audit.py');call('write_report.py');call('closeout.py')
  save(ROOT/'runs/pipeline_status.json',dict(state='complete',device='cpu',proof='results/complete.json',completed_utc=now()))
  save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(state='complete',device='cpu',completed_updates=8192,images=930,completed_utc=now()))
 except BaseException:
  save(ROOT/'runs/pipeline_failure.json',dict(state='failed',device='cpu',error=traceback.format_exc(),updated_utc=now()));raise
if __name__=='__main__':main()
