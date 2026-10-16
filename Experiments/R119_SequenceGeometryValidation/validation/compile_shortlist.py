"""Compile identical-population ACM/SEM/LSC results for the P09 decision."""
from __future__ import annotations
import argparse, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
 h=hashlib.sha256();
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/shortlist_validation.json');args=parser.parse_args(); methods=[]
 for label in ('A','B','D'):
  acm=read(ROOT/f'results/shortlist_acm_{label}/analysis_summary.json');sem=read(ROOT/f'results/shortlist_sem_{label}/summary.json');lsc=read(ROOT/f'results/shortlist_lsc_{label}/lsc/summary.json');methods.append({'candidate':label,'checkpoint':acm['checkpoint'],'checkpoint_sha256':acm['checkpoint_sha256'],'acm':{suite:{'boundary_change_pct':row['effect']['overall_boundary_change_pct'],'hd95_change_pct':row['effect']['overall_hd95_change_pct'],'iou_delta':row['effect']['overall_iou_delta'],'failure_counts':row['zero_failure_audit']['failure_counts']} for suite,row in ((x['suite'],x) for x in acm['results'])},'sem':sem,'lsc':lsc['headline'][f'R119 {label}'],'lsc_vs_R109_step_sd_nm':lsc['headline'][f'R119 {label}']['step_sd_nm']-lsc['headline']['R109 E48']['step_sd_nm'],'lsc_vs_raw_step_sd_nm':lsc['headline'][f'R119 {label}']['step_sd_nm']-lsc['headline']['Raw']['step_sd_nm'],'tile_parity':read(ROOT/f'results/shortlist_validation_tile_{label}.json') if (ROOT/f'results/shortlist_validation_tile_{label}.json').exists() else None})
 result={'schema_version':1,'status':'complete','created_at_utc':datetime.now(timezone.utc).isoformat(),'population':'same locked R73/R74 ACM, same 36-pillar/12-exposure SEM, same Raw-locked 120-pair LSC development protocol','shortlist':methods,'selection_scope':'P09 decision only; not sealed confirmation or automatic promotion','decision_dimensions':['ACM shape','SEM shape','real LSC stability','fixed bias versus fluctuation','tile parity','visual review']}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
