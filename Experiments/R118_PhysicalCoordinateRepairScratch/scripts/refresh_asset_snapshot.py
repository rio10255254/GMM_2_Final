"""Refresh the intentional handoff-document hashes in next_design_assets.json.

This records current bytes; it never accepts a changed protected runtime/data
file without an explicit path-role review.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'reports/next_design_assets.json');args=parser.parse_args();data=json.loads(args.output.read_text(encoding='utf-8-sig'));changed=[]
 allowed={'R118 handoff documentation': {'AGENTS.md','NEXT_STEPS.md','results/README.md','reports/R118_EXECUTION_HANDOFF.md'}}
 for entry in data['protected_files']:
  p=Path(entry['path']);
  if p.is_file() and p.name in set().union(*allowed.values()) and str(ROOT).replace('\\','/') in str(p).replace('\\','/'):
   old=entry['sha256'];entry['sha256']=sha(p);entry['bytes']=p.stat().st_size
   if old!=entry['sha256']:changed.append(entry['path'])
 if not changed: raise RuntimeError('no intentional handoff files were changed; refusing a no-op refresh')
 data['captured_date']='2026-09-05';data['refresh_reason']='Intentional completion-state update to R118 handoff documents after R119 P00-P12 execution.';tmp=args.output.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(args.output);print(json.dumps({'status':'refreshed','changed_paths':changed,'snapshot_sha256':sha(args.output)},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
