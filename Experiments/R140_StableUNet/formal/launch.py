"""Final R140 launch: synthetic scratch train, then fixed real evaluation."""
from pathlib import Path
import sys,subprocess,os,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,sha,source_records,verify_frozen,verify_protected,verify_evaluation,now

def call(file):
 save(ROOT/'runs/pipeline_status.json',dict(state='running',phase=file,device='cuda',pid=os.getpid(),updated_utc=now()))
 print('PHASE',file,flush=True)
 subprocess.run([sys.executable,'-u','-B',str(ROOT/file)],cwd=ROOT,check=True)

def main():
 if (ROOT/'results/complete.json').exists():
  print('R140 already complete; see reports/R140_RESULTS.md',flush=True);return
 try:
  lock=ROOT/'config/FORMAL_SOURCE_LOCK.json'
  if not lock.exists():save(lock,source_records())
  verify_frozen(load(lock));verify_protected();verify_evaluation()
  if not (ROOT/'results/formal_preflight.json').exists():call('formal/preflight.py')
  assert load(ROOT/'results/formal_preflight.json')['ready_for_formal_training']
  if not (ROOT/'runs/formal_8192/training_complete.json').exists():call('formal/train.py')
  for file in ['evaluate_real_measurement.py','compare_measurements.py','final_audit.py','write_report.py','formal/closeout.py']:
   call(file)
  save(ROOT/'runs/pipeline_status.json',dict(state='complete',proof='results/complete.json',completed_utc=now()))
  save(ROOT/'runs/launcher_logs/active_formal_run.json',dict(state='complete',updates=8192,images=930,circles=8370,completed_utc=now()))
 except BaseException:
  save(ROOT/'runs/pipeline_failure.json',dict(state='failed',error=traceback.format_exc(),updated_utc=now()));raise
if __name__=='__main__':main()
