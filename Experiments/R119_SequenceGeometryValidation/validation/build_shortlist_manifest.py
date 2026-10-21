"""Freeze the shortlist identities before the P09 scientific decision."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/shortlist_manifest.json');args=parser.parse_args();rows=[]
 for c in ('A','B','D'):
  checkpoint=ROOT/f'runs/probe_{c}_s1185001/weights/epoch_012.pth';
  rows.append({'candidate':c,'run_id':f'probe_{c}_s1185001','checkpoint':str(checkpoint.resolve()),'checkpoint_sha256':sha(checkpoint),'acm_summary':str((ROOT/f'results/shortlist_acm_{c}/analysis_summary.json').resolve()),'sem_summary':str((ROOT/f'results/shortlist_sem_{c}/summary.json').resolve()),'lsc_summary':str((ROOT/f'results/shortlist_lsc_{c}/lsc/summary.json').resolve()),'tile_parity':str((ROOT/f'results/shortlist_validation_tile_{c}.json').resolve())})
 result={'schema_version':1,'status':'complete','created_at_utc':datetime.now(timezone.utc).isoformat(),'selection_predeclared_before_outcomes':True,'methods':rows,'references':['Raw','R109 E48','V42 E120'],'population':'development only; R73/R74, SEM 36 pillars x 12 exposures, Raw-locked 120 pairs','confirmation_opened':False,'method_choice':'one model seed per candidate for P08 as predeclared; second probe seed retained in P07 uncertainty'}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
