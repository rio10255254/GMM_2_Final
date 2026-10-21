"""Compile P11 formal E42 development validation and mechanical checks."""
from __future__ import annotations
import argparse, json, hashlib
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/posttraining/audit.json');args=parser.parse_args();errors=[]
 completion=read(ROOT/'results/formal_completion.json');acm=read(ROOT/'results/formal_acm/analysis_summary.json');sem=read(ROOT/'results/formal_sem/summary.json');lsc=read(ROOT/'results/formal_lsc/analysis/summary.json');seq=read(ROOT/'results/formal_sequence/audit.json');tile=read(ROOT/'results/formal_tile_parity.json')
 if completion.get('status')!='pass':errors.append('formal completion audit failed')
 if acm.get('status')!='complete' or len(acm.get('results',[]))!=2:errors.append('formal ACM incomplete')
 for row in acm.get('results',[]):
  if row.get('zero_failure_audit',{}).get('failure_counts') != {'primary':0,'sensitivity':0}:errors.append(f"ACM failure {row.get('suite')}")
 if sem.get('status')!='complete' or sem.get('independent_pillars')!=36 or sem.get('repeated_exposures')!=12:errors.append('formal SEM incomplete')
 if lsc.get('status')!='complete' or lsc.get('candidate_pair_rows')!=120 or lsc.get('combined_pair_rows')!=600:errors.append('formal LSC incomplete')
 if seq.get('status')!='complete' or seq.get('positions_rows')!=13104 or seq.get('steps_rows')!=6912:errors.append('formal synthetic sequence incomplete')
 if tile.get('status')!='pass':errors.append('formal tile parity failed')
 s=pd.read_csv(ROOT/'results/formal_sequence/sequence_summary.csv');q=pd.read_csv(ROOT/'results/formal_sequence/shape_detail.csv');metrics={}
 for method in ('Raw','R119_B_E42','R109_E48'):
  m=s[s.method==method];motion=m[m.protocol.str.startswith('motion_')];static=m[m.protocol=='static_repeat'];metrics[method]={'synthetic_motion_step_sd_median_px':float(np.nanmedian(np.r_[motion.step_sd_x_px,motion.step_sd_y_px])),'synthetic_static_repeat_sd_median_px':float(np.nanmedian(np.r_[static.repeat_sd_x_px,static.repeat_sd_y_px])),'synthetic_image_mae_gray_median':float(q[q.method==method].image_mae_gray.median()),'synthetic_gradient_error_median':float(q[q.method==method].gradient_error.median())}
 result={'schema_version':1,'status':'pass' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'errors':errors,'checkpoint':acm.get('checkpoint'),'checkpoint_sha256':acm.get('checkpoint_sha256'),'completion':completion,'metrics':metrics,'acm':{'R73':acm['results'][0]['effect'],'R74':acm['results'][1]['effect']},'sem':sem,'lsc_headline':lsc['headline'],'tile_parity':tile,'sequence_audit':seq,'population':'development only; no confirmation data','promotion':False,'meaning':'Formal E42 capability and validation audit; no automatic thesis/production promotion.'}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2
if __name__=='__main__':raise SystemExit(main())
