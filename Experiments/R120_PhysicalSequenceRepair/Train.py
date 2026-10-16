"""Editable IDE entry for a bounded independent scratch probe."""
from pathlib import Path
import subprocess
import datetime
ROOT=Path(__file__).resolve().parent
PYTHON='C:/Users/Rio/anaconda3/python.exe'
ARM='B'
MODEL_SEED=1205001
EPOCHS=12
TRAIN_SCENES=512
BATCH_SIZE=8
WORKERS=2

if __name__=='__main__':
    run_id='manual_'+ARM+'_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    raise SystemExit(subprocess.call([PYTHON,str(ROOT/'training/train.py'),'--arm',ARM,'--seed',str(MODEL_SEED),
        '--run-id',run_id,'--epochs',str(EPOCHS),'--scenes',str(TRAIN_SCENES),'--batch',str(BATCH_SIZE),'--workers',str(WORKERS)],cwd=ROOT))
