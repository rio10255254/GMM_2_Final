"""Run the frozen 930-frame R150 validation and its integrity audit."""
from __future__ import annotations
import subprocess,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils import load,save,sha,now

PHASES=(
 ('reconstruction_and_measurement','scripts/evaluate_real.py','results/measurement_complete.json'),
 ('historical_comparison','scripts/compare_measurements.py','results/comparison/complete.json'),
 ('final_audit','scripts/final_audit.py','results/final_audit.json'),
)

def main():
 complete=load(ROOT/'runs/formal_8192/training_complete.json');assert complete['updates']==8192 and sha(complete['checkpoint']['path'])==complete['checkpoint']['sha256']
 status=ROOT/'runs/real_validation_status.json'
 for phase,script,expected in PHASES:
  if (ROOT/expected).exists():print('EXISTING',phase,flush=True);continue
  save(status,dict(state='running',phase=phase,script=script,script_sha256=sha(ROOT/script),updated_utc=now()))
  print('PHASE',phase,flush=True)
  try:subprocess.run([sys.executable,'-u','-B',str(ROOT/script)],cwd=ROOT,check=True)
  except BaseException:
   save(status,dict(state='failed',phase=phase,error=traceback.format_exc(),updated_utc=now()));raise
  if not (ROOT/expected).exists():raise RuntimeError('Missing expected output: '+expected)
 audit=load(ROOT/'results/final_audit.json');assert audit['passed']
 save(status,dict(state='complete',phase='complete',images=930,circles=8370,checkpoint_sha256=complete['checkpoint']['sha256'],completed_utc=now()));print('REAL_VALIDATION_COMPLETE',flush=True)
if __name__=='__main__':main()
