"""Audit all bounded probe runs and their fixed checkpoint endpoints."""
from __future__ import annotations
import argparse, csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/probe_matrix_audit.json');args=parser.parse_args(); errors=[]; rows=[]
    for candidate in ('A','B','D'):
        for seed in (1185001,1185002):
            run_id=f'probe_{candidate}_s{seed}';run=ROOT/'runs'/run_id;state_path=run/'state.json';summary_path=run/'SUMMARY.json';log_path=run/'training_log.csv'
            required=[state_path,summary_path,log_path,*[run/'weights'/f'epoch_{e:03d}.pth' for e in (4,8,12)]]
            if any(not p.is_file() for p in required): errors.append(f'{run_id}: missing required endpoint')
            else:
                state=json.loads(state_path.read_text());summary=json.loads(summary_path.read_text());log=list(csv.DictReader(log_path.open(encoding='utf-8-sig')))
                if state.get('status')!='complete' or state.get('epochs_completed')!=12 or summary.get('epochs_completed')!=12:errors.append(f'{run_id}: completion mismatch')
                if len(log)!=12 or [int(r['epoch']) for r in log]!=list(range(1,13)):errors.append(f'{run_id}: epoch log mismatch')
                if state.get('checkpoint_loaded') is not False:errors.append(f'{run_id}: warm-start provenance')
                for record in log:
                    for key in ('total','val_output_mae_gray','duration_seconds'):
                        try:
                            if not np.isfinite(float(record[key])):errors.append(f'{run_id}: nonfinite {key}')
                        except (KeyError,ValueError):errors.append(f'{run_id}: missing {key}')
                rows.append({'run_id':run_id,'candidate':candidate,'model_seed':seed,'epochs':len(log),'final_loss':float(log[-1]['total']),'final_val_output_mae_gray':float(log[-1]['val_output_mae_gray']),'checkpoint_sha256':{str(e):sha(run/'weights'/f'epoch_{e:03d}.pth') for e in (4,8,12)},'state_sha256':sha(state_path),'summary_sha256':sha(summary_path)})
    if len({r['run_id'] for r in rows}) != 6:errors.append('matrix run identity is not unique')
    result={'schema_version':1,'status':'pass' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'expected_runs':6,'runs':rows,'errors':errors,'endpoints':[4,8,12],'same_probe_population':True,'fresh_initialization':True,'confirmation_used':False,'meaning':'Mechanical probe-completion audit; not a scientific winner decision.'}
    if args.output.exists():raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2


if __name__=='__main__':raise SystemExit(main())
