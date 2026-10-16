"""Post-hoc descriptive analysis of confirmation fixed-reference positions.

This reads the already-consumed ledger only; it cannot alter the candidate or
choose a checkpoint. The confirmation remains consumed and is not re-used for
tuning.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/confirmation/position_analysis.json');args=parser.parse_args();rows=[json.loads(x) for x in (ROOT/'results/confirmation/per_scene.jsonl').read_text().splitlines() if x.strip()];summary={};errors=[]
 for key in ('raw_a_position','model_a_position','raw_b_position','model_b_position'):
  values=[]
  for row in rows:
   position=row.get(key)
   if position is not None:values.append(float(np.linalg.norm(np.asarray(position,float)-np.asarray(row['true_shift_xy_px'],float))))
  summary[key]={'valid_count':len(values),'invalid_count':len(rows)-len(values),'median_error_px':float(np.median(values)) if values else None,'p95_error_px':float(np.percentile(values,95)) if values else None,'max_error_px':float(np.max(values)) if values else None}
 if any(v['max_error_px'] is not None and not np.isfinite(v['max_error_px']) for v in summary.values()):errors.append('nonfinite position error')
 result={'schema_version':1,'status':'complete' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'candidate':'R119_B_E42','summary':summary,'comparison_definition':'fixed-reference registration position minus confirmation manifest shift_xy; this is a diagnostic, not locked real LSC','tuning_after_read':False,'confirmation_consumed':True,'errors':errors,'meaning':'Descriptive post-hoc position diagnostic; no selection or tuning.'}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='complete' else 2
if __name__=='__main__':raise SystemExit(main())
