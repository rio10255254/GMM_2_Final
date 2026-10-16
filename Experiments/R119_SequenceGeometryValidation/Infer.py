"""IDE Run entry point; set the three paths below for a reconstruction job."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parent
PYTHON=Path(r'C:\Users\Rio\anaconda3\python.exe')
CHECKPOINT = ''
INPUT = ''
OUTPUT = ''
if __name__=='__main__':
    if not all((CHECKPOINT,INPUT,OUTPUT)):
        raise SystemExit('Set CHECKPOINT, INPUT and OUTPUT above, then run this file.')
    interpreter=str(PYTHON) if PYTHON.is_file() else sys.executable
    raise SystemExit(subprocess.call([interpreter,str(ROOT/'inference/run.py'),'--checkpoint',CHECKPOINT,'--input',INPUT,'--output',OUTPUT],cwd=ROOT))
