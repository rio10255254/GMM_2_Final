"""Explicit bounded-probe entry; no automatic long training."""
from pathlib import Path
import argparse,subprocess,sys
ROOT=Path(__file__).resolve().parent
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--execute-probes',action='store_true');args=p.parse_args()
    if not args.execute_probes:
        print('R121 is a bounded factorial study. Read config/protocol_v2.json and reports/R121_RESULTS.md. No training started.')
    elif (ROOT/'config/source_freeze_v2.json').exists():
        raise SystemExit('This exact probe matrix has already been started. Preserve its evidence; inspect existing run state instead of launching a duplicate.')
    else:raise SystemExit(subprocess.call([sys.executable,'-B',str(ROOT/'scripts/run_matrix_v2.py')],cwd=ROOT))
