"""Refresh R119 receipt hashes after verified implementation/output changes.

This is a bookkeeping tool only: it refuses missing artifacts and never changes
status, checks or scientific notes. It does not run inference or training.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT=Path(__file__).resolve().parents[1]
PLAN=Path(str(PROJECT_ROOT / 'Experiments/R118_PhysicalCoordinateRepairScratch/reports/next_design_plan.json'))
ASSETS=Path(str(PROJECT_ROOT / 'Experiments/R118_PhysicalCoordinateRepairScratch/reports/next_design_assets.json'))
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args();plan=json.loads(PLAN.read_text());snap=sha(ASSETS);receipts={}
 for i in range(1,13):
  path=ROOT/f'reports/handoff_receipts/P{i:02d}.json';data=json.loads(path.read_text(encoding='utf-8-sig'));data['plan_sha256']=sha(PLAN);data['input_snapshot_sha256']=snap
  if data['phase']=='P05' and not any(a['path']=='data/training_observations/manifest.json' for a in data['artifacts']):data['artifacts'].append({'path':'data/training_observations/manifest.json','sha256':''})
  if data['phase']=='P06' and not any(a['path']=='results/candidate_smoke.json' for a in data['artifacts']):data['artifacts'].append({'path':'results/candidate_smoke.json','sha256':''})
  if data['phase']=='P07' and not any(a['path']=='results/probe_matrix.json' for a in data['artifacts']):data['artifacts'].append({'path':'results/probe_matrix.json','sha256':''})
  if data['phase']=='P10' and not any(a['path']=='results/design_decision.json' for a in data['artifacts']):data['artifacts'].append({'path':'results/design_decision.json','sha256':''})
  if data['phase']=='P11' and not any(a['path']=='results/formal_sequence/representative_panels.png' for a in data['artifacts']):data['artifacts'].append({'path':'results/formal_sequence/representative_panels.png','sha256':''})
  for artifact in data['artifacts']:
   target=ROOT/artifact['path']
   if not target.is_file():raise FileNotFoundError(target)
   artifact['sha256']=sha(target)
  if i>1:
   previous=f'P{i-1:02d}';data['depends_on_receipts']={previous:receipts[previous]}
  receipts[data['phase']]=sha(path) if args.check_only else None
  if not args.check_only:
   tmp=path.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(path);receipts[data['phase']]=sha(path)
 print(json.dumps({'status':'checked' if args.check_only else 'refreshed','receipt_hashes':receipts,'plan_sha256':sha(PLAN),'input_snapshot_sha256':snap},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
