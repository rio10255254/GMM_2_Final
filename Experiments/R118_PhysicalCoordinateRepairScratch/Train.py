"""IDE Run entry point. Edit config/experiment.json to change the formal plan."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parent
PYTHON=Path(r'C:\Users\Rio\anaconda3\python.exe')
if __name__=='__main__':
    interpreter=str(PYTHON) if PYTHON.is_file() else sys.executable
    checked=subprocess.call([interpreter,str(ROOT/'validation/preflight.py')],cwd=ROOT)
    if checked or '--check-only' in sys.argv:raise SystemExit(checked)
    raise SystemExit(subprocess.call([interpreter,str(ROOT/'training/train.py'),'--mode','formal'],cwd=ROOT))
