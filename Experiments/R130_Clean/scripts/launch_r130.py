"""One local pipeline: clean preparation -> scratch -> final-only real evaluation."""
from pathlib import Path
import sys,subprocess,os,traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,sha,source_records,verify_frozen,verify_protected,now

def call(file):
 print('PHASE:',file,flush=True)
 save(ROOT/'runs/pipeline_status.json',dict(state='running',phase=file,pid=os.getpid(),updated_utc=now()))
 subprocess.run([sys.executable,'-B',str(ROOT/file)],cwd=ROOT,check=True)
def main():
 try:
  if not (ROOT/'data/manifest.json').exists():call('scripts/prepare_data.py')
  if not (ROOT/'config/evaluation_manifest.json').exists():call('scripts/prepare_evaluation.py')
  if not (ROOT/'results/preflight.json').exists():call('preflight_check.py')
  assert load(ROOT/'results/preflight.json')['all_required_checks_passed']
  lock=ROOT/'config/source_lock.json'
  if not lock.exists():save(lock,source_records())
  verify_frozen(load(lock));verify_protected()
  import train_r130_clean as trainer
  trainer.MODEL_NAME_BASE=trainer.CFG.MODEL_NAME
  if not (ROOT/'runs/formal_8192/training_complete.json').exists():trainer.train_formal()
  call('evaluate_real_measurement.py');call('compare_measurements.py');call('profile_r130_clean.py');call('write_report.py')
  save(ROOT/'runs/pipeline_status.json',dict(state='complete',proof='results/complete.json',completed_utc=now()))
 except BaseException:
  save(ROOT/'runs/pipeline_failure.json',dict(state='failed',error=traceback.format_exc(),updated_utc=now()));raise
if __name__=='__main__':main()
