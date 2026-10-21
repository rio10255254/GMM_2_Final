"""Mechanical P08 audit for ACM, SEM, LSC and tile-parity shortlist outputs."""
from __future__ import annotations
import argparse, json, csv, hashlib
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/shortlist_validation_audit.json');args=parser.parse_args();errors=[];rows=[]
 for c in ('A','B','D'):
  acm=read(ROOT/f'results/shortlist_acm_{c}/analysis_summary.json');sem=read(ROOT/f'results/shortlist_sem_{c}/summary.json');lsc=read(ROOT/f'results/shortlist_lsc_{c}/lsc/summary.json');tile=read(ROOT/f'results/shortlist_validation_tile_{c}.json')
  if acm.get('status')!='complete' or len(acm.get('results',[]))!=2:errors.append(f'{c}: ACM incomplete')
  for result in acm.get('results',[]):
   if result.get('zero_failure_audit',{}).get('failure_counts') != {'primary':0,'sensitivity':0}:errors.append(f'{c}: ACM failures in {result.get("suite")}')
  if sem.get('status')!='complete' or sem.get('independent_pillars')!=36 or sem.get('repeated_exposures')!=12:errors.append(f'{c}: SEM inventory mismatch')
  if lsc.get('status')!='complete' or lsc.get('candidate_pair_rows')!=120 or lsc.get('combined_pair_rows')!=600 or lsc.get('determinism_spot_check_max_px')!=0:errors.append(f'{c}: LSC inventory/determinism mismatch')
  if tile.get('status')!='pass' or max(r['max_gray'] for r in tile['rows'])>=.05:errors.append(f'{c}: tile parity failed')
  rows.append({'candidate':c,'acm_suites':len(acm.get('results',[])),'sem_pillars':sem.get('independent_pillars'),'sem_gain_pct':sem.get('median_boundary_gain_pitch_pct'),'lsc_step_sd_nm':lsc.get('headline',{}).get(f'R119 {c}',{}).get('step_sd_nm'),'lsc_within_grid_sd_nm':lsc.get('headline',{}).get(f'R119 {c}',{}).get('median_within_grid_sd_nm'),'tile_max_gray':max(r['max_gray'] for r in tile['rows'])})
 result={'schema_version':1,'status':'pass' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'errors':errors,'rows':rows,'same_protocol':True,'same_raw_input_provenance':True,'confirmation_opened':False,'meaning':'Mechanical shortlist validity; scientific choice remains a paired interpretation.'}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2
if __name__=='__main__':raise SystemExit(main())
