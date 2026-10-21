"""Explicit-root adapter for the locked R116 ACM-inflection-LSC program."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
R116 = ROOT.parent / "R116_CoherentGeometryAnchorScratch/validation/run_lsc_e42.py"


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--method',required=True); parser.add_argument('--recon-root',required=True); parser.add_argument('--output',required=True); args=parser.parse_args()
    recon=Path(args.recon_root).resolve(); output=Path(args.output).resolve()
    if not recon.is_dir(): raise FileNotFoundError(recon)
    protected = {ROOT / name for name in ('config', 'model', 'training', 'inference', 'validation', 'scripts', 'data')}
    if output == ROOT or any(output == folder or folder in output.parents for folder in protected): raise ValueError('LSC output must be outside R119 source directories')
    cmd=[sys.executable,str(R116),'--method',args.method,'--recon-root',str(recon),'--output',str(output)]
    result=subprocess.run(cmd,cwd=ROOT,text=True)
    return result.returncode


if __name__=='__main__': raise SystemExit(main())
