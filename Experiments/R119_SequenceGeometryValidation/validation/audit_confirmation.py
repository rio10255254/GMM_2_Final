"""Verify the one-time confirmation ledger and all 144 per-scene rows."""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1];SOURCE=Path(r'D:/GMM_2_Final/Experiments/R118_PhysicalCoordinateRepairScratch/data/confirmation/manifest.json')
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/confirmation/audit.json');args=parser.parse_args();errors=[];cons=json.loads((ROOT/'results/confirmation/consumption.json').read_text());summary=json.loads((ROOT/'results/confirmation/summary.json').read_text());rows=[json.loads(x) for x in (ROOT/'results/confirmation/per_scene.jsonl').read_text().splitlines() if x.strip()];seal=json.loads(SOURCE.read_text())
 if cons.get('status')!='consumed_once' or cons.get('scene_count')!=144 or cons.get('selection_or_tuning_after_read') is not False:errors.append('consumption ledger is not one-time/no-tuning')
 if cons.get('confirmation_manifest_sha256')!=sha(SOURCE) or cons.get('source_seal_modified') is not False:errors.append('source seal hash/immutability mismatch')
 if len(rows)!=144 or len({r.get('file') for r in rows})!=144:errors.append('per-scene confirmation rows incomplete/duplicated')
 if seal.get('status')!='sealed_not_evaluated' or seal.get('training_inclusion') is not False:errors.append('source seal declaration changed')
 numeric=[]
 for row in rows:
  for k,v in row.items():
   if isinstance(v,(int,float)):numeric.append(float(v))
   if k.endswith('_mae_gray') or k.endswith('_gradient_error'):
    if not np.isfinite(float(v)):errors.append(f'nonfinite metric {row.get("file")} {k}')
 if not np.isfinite(np.asarray(numeric)).all():errors.append('nonfinite confirmation numeric')
 if summary.get('status')!='complete' or summary.get('checkpoint_sha256')!=cons.get('checkpoint_sha256'):errors.append('confirmation summary identity mismatch')
 result={'schema_version':1,'status':'pass' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'errors':errors,'scene_count':len(rows),'candidate':cons.get('candidate'),'checkpoint_sha256':cons.get('checkpoint_sha256'),'confirmation_manifest_sha256':cons.get('confirmation_manifest_sha256'),'source_seal_still_declared_pristine':seal.get('status')=='sealed_not_evaluated' and seal.get('model_predictions_generated') is False,'summary':summary.get('summary'),'tuning_after_read':cons.get('selection_or_tuning_after_read'),'meaning':'Confirmation consumption integrity; it is no longer unseen and must not be reused for tuning.'}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2
if __name__=='__main__':raise SystemExit(main())
