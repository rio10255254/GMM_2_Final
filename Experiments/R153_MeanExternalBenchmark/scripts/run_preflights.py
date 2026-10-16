"""Isolate CUDA memory and imports for each official comparator feasibility run."""
from pathlib import Path
import subprocess,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmark_models import SPECS


if __name__=='__main__':
    for method in SPECS:
        p=subprocess.run([sys.executable,'-B','-X','utf8',str(ROOT/'scripts/preflight_model.py'),method])
        print('PREFLIGHT_PROCESS',method,'return',p.returncode,flush=True)
