"""Set the input/output/checkpoint then press Run; inputs are preserved."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent
PYTHON='python'
CHECKPOINT=''
INPUT=''
OUTPUT=''

if __name__=='__main__':
    if not all([CHECKPOINT,INPUT,OUTPUT]):raise SystemExit('Set CHECKPOINT, INPUT and OUTPUT before running.')
    raise SystemExit(subprocess.call([PYTHON,str(ROOT/'inference/run.py'),'--checkpoint',CHECKPOINT,'--input',INPUT,'--output',OUTPUT],cwd=ROOT))
