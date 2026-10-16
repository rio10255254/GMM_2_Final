"""Audit R119 executor source and two one-epoch smoke runs."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256();
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/candidate_smoke.json');args=parser.parse_args(); errors=[]; runs=[]
    for name,device in [('smoke_cpu_v2','cpu'),('smoke_gpu_v2','cuda')]:
        run=ROOT/'runs'/name;state_path=run/'state.json';summary=run/'SUMMARY.json';weight=run/'weights/epoch_001.pth';log=run/'training_log.csv';
        if not all(p.is_file() for p in (state_path,summary,weight,log)):errors.append(f'{name}: missing completion artifact')
        else:
            state=json.loads(state_path.read_text());summary_data=json.loads(summary.read_text());
            if state.get('status')!='complete' or summary_data.get('epochs_completed')!=1:errors.append(f'{name}: not complete')
            if state.get('checkpoint_loaded') is not False:errors.append(f'{name}: warm-start provenance')
            runs.append({'run_id':name,'requested_device':device,'state_sha256':sha(state_path),'summary_sha256':sha(summary),'weight_sha256':sha(weight),'log_sha256':sha(log)})
    source=ROOT/'training/train_r119.py'; wrapper=ROOT/'training/train.py';
    if not source.is_file() or not wrapper.is_file():errors.append('executor source missing')
    result={'schema_version':1,'status':'pass' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'errors':errors,'smoke_runs':runs,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in (source,wrapper) if p.is_file()},'candidate_matrix':['A','B','D'],'seeds':[1185001,1185002],'separate_data_seed':1196001,'separate_sampler_seed':1197001,'formal_launch_authorization':'P09 only','meaning':'Executor integrity and smoke evidence; no candidate capability claim.'}
    if args.output.exists():raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2


if __name__=='__main__':raise SystemExit(main())
