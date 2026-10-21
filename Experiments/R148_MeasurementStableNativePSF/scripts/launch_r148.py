"""R148 formal launcher with artifact identity and completion receipt."""
from __future__ import annotations
import os,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import train as trainer
from utils import load,save,sha,now
from verify_package import verify_source_lock
def main():
 pre=load(ROOT/'results/preflight.json');verify_source_lock()
 if not pre['passed'] or not load(ROOT/'results/data_generation_complete.json')['state']=='complete':raise RuntimeError('R148 preflight/data incomplete')
 trainer.MODEL_NAME_BASE=trainer.CFG.MODEL_NAME
 if trainer.MODEL_NAME_BASE!='R148-MeasurementStableNativePSF':raise RuntimeError('Wrong artifact identity')
 marker=ROOT/'runs/launcher_logs/active_formal_run.json';base=dict(experiment_id='R148_MeasurementStableNativePSF',model=trainer.MODEL_NAME_BASE,run='formal_8192',updates_expected=8192,data_manifest_sha256=sha(ROOT/'data/payload/manifest.json'),process_id=os.getpid(),started_utc=now());save(marker,dict(base,status='active_training'))
 old=sys.argv
 try:
  sys.argv=[str(ROOT/'train.py'),'--run-name','formal_8192','--init','scratch'];trainer.main();done=load(ROOT/'runs/formal_8192/training_complete.json');assert done['updates']==8192 and sha(done['checkpoint']['path'])==done['checkpoint']['sha256'];save(marker,dict(base,status='training_complete',checkpoint=done['checkpoint'],completed_utc=now()))
 except BaseException:
  save(marker,dict(base,status='failed',error=traceback.format_exc(),failed_utc=now()));raise
 finally:sys.argv=old
if __name__=='__main__':main()
