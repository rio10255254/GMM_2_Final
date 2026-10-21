"""Verify the single R119 formal run's process, markers, logs and E42 reload."""
from __future__ import annotations
import argparse, csv, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]; RUN=ROOT/'runs/formal_B_s1195001'
sys_path=str(ROOT)
import sys; sys.path.insert(0,sys_path)
from inference.run import load, read, tiled


def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/formal_completion.json');args=parser.parse_args();errors=[]
 state=json.loads((RUN/'state.json').read_text());summary=json.loads((RUN/'SUMMARY.json').read_text());marker=json.loads((ROOT/'runs/launcher_logs/active_formal_run.json').read_text());log=list(csv.DictReader((RUN/'training_log.csv').open(encoding='utf-8-sig')))
 if state.get('status')!='complete' or summary.get('status')!='complete' or marker.get('status')!='complete':errors.append('run/summary/marker not all complete')
 if state.get('checkpoint_loaded') is not False or summary.get('checkpoint_loaded') is not False:errors.append('formal run has warm-start provenance')
 if state.get('epochs_completed')!=42 or summary.get('epochs_completed')!=42 or len(log)!=42 or [int(r['epoch']) for r in log]!=list(range(1,43)):errors.append('formal epoch inventory mismatch')
 expected_weights=[RUN/'weights'/f'epoch_{e:03d}.pth' for e in list(range(3,43,3))]
 expected_preview=[RUN/'previews'/f'epoch_{e:03d}_real.png' for e in list(range(3,43,3))]
 expected_validation=[RUN/'validation'/f'epoch_{e:03d}.json' for e in range(1,43)]
 for label,paths in [('weights',expected_weights),('previews',expected_preview),('validation',expected_validation)]:
  if any(not p.is_file() for p in paths):errors.append(f'{label} inventory incomplete')
 numeric=[]
 for row in log:
  for key,value in row.items():
   if key in {'epoch','stage'} or value=='':continue
   try:numeric.append(float(value))
   except ValueError:pass
 if not np.isfinite(np.asarray(numeric)).all():errors.append('training log contains nonfinite numeric value')
 if state.get('steps')!=42*417 or summary.get('steps')!=42*417:errors.append('optimizer step count mismatch')
 # Confirm the exact E42 checkpoint is reloadable and finite on one Raw input.
 e42=RUN/'weights/epoch_042.pth'; reload_ok=False; output_max=None
 try:
  model=load(e42,'cuda' if torch.cuda.is_available() else 'cpu'); raw=read(ROOT/'validation/inputs/Raw/50x_array_raw.bmp'); tensor=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(next(model.parameters()).device)
  with torch.inference_mode(): value=tiled(model,tensor,core=192); reload_ok=bool(torch.isfinite(value).all()); output_max=float(value.max())
 except Exception as exc:errors.append(f'E42 reload/inference failed: {exc!r}')
 if not reload_ok:errors.append('E42 output is not finite')
 # Exact command-line scan; child data-loader workers are allowed to have exited.
 try:
  probe=subprocess.run(['powershell.exe','-NoProfile','-Command',"Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' -and $_.CommandLine -match 'training[\\\\/]+train\\.py' -and $_.CommandLine -match 'formal_B_s1195001' } | Select-Object -ExpandProperty ProcessId"],capture_output=True,text=True,timeout=20)
  active=[x.strip() for x in probe.stdout.splitlines() if x.strip().isdigit()]
  if active:errors.append(f'formal trainer process still active: {active}')
 except Exception as exc:errors.append(f'process exit check failed: {exc!r}')
 result={'schema_version':1,'status':'pass' if not errors else 'blocked','created_at_utc':datetime.now(timezone.utc).isoformat(),'run_id':'formal_B_s1195001','errors':errors,'epochs':len(log),'steps':summary.get('steps'),'weight_count':sum(p.is_file() for p in expected_weights),'preview_count':sum(p.is_file() for p in expected_preview),'validation_count':sum(p.is_file() for p in expected_validation),'e42_checkpoint_sha256':sha(e42) if e42.is_file() else None,'e42_reload_finite':reload_ok,'e42_output_max':output_max,'marker_status':marker.get('status'),'checkpoint_loaded':summary.get('checkpoint_loaded'),'meaning':'Formal run completion integrity only; no capability promotion.'}
 if args.output.exists():raise FileExistsError(args.output)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2
if __name__=='__main__':raise SystemExit(main())
