"""Wait for resumable reconstruction/measurement, then publish comparisons."""
from __future__ import annotations
import subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from utils import load,save,sha,now

def main():
 status=ROOT/'runs/real_validation_status.json';measurement=ROOT/'results/measurement_complete.json';limit=time.time()+6*3600
 save(status,dict(state='running',phase='reconstruction_and_measurement',updated_utc=now()))
 try:
  while not measurement.is_file():
   if time.time()>limit:raise TimeoutError('930-frame measurement did not finish within six hours')
   if (ROOT/'runs/real_validation.stderr.log').is_file():
    error=(ROOT/'runs/real_validation.stderr.log').read_text(encoding='utf-8',errors='replace')
    if 'Traceback (most recent call last)' in error:raise RuntimeError('Reconstruction or measurement failed; see real_validation.stderr.log')
   time.sleep(20)
  record=load(measurement);assert record['images']==930 and record['circles']==8370
  for phase,script,expected in (
   ('matched_comparison','compare_measurements.py','results/comparison/complete.json'),
   ('integrity_audit','final_audit.py','results/final_audit.json'),
  ):
   save(status,dict(state='running',phase=phase,script_sha256=sha(ROOT/'scripts'/script),updated_utc=now()));print('PHASE',phase,flush=True)
   subprocess.run([sys.executable,'-u','-B',str(ROOT/'scripts'/script)],cwd=ROOT,check=True)
   if not (ROOT/expected).is_file():raise RuntimeError('Missing output '+expected)
  assert load(ROOT/'results/final_audit.json')['passed']
  save(status,dict(state='complete',images=930,circles=8370,completed_utc=now()));print('R152_REAL_VALIDATION_COMPLETE',flush=True)
 except BaseException:
  save(status,dict(state='failed',error=traceback.format_exc(),updated_utc=now()));raise
if __name__=='__main__':main()
