"""Record intentional completion-state handoff document changes in the plan."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'reports/next_design_plan.json');args=parser.parse_args();data=json.loads(args.output.read_text(encoding='utf-8-sig'));changed=[]
 wanted={'AGENTS.md','NEXT_STEPS.md','results/README.md','reports/R118_EXECUTION_HANDOFF.md'}
 for entry in data.get('handoff_integrity',[]):
  if entry['path'] in wanted:
   p=ROOT/entry['path'];
   if not p.is_file():raise FileNotFoundError(p)
   old=entry['sha256'];entry['sha256']=sha(p)
   if old!=entry['sha256']:changed.append(entry['path'])
 if set(wanted)-{e['path'] for e in data.get('handoff_integrity',[])}:raise RuntimeError('plan lacks one or more handoff paths')
 if not changed:raise RuntimeError('no intentional handoff path changed; refusing no-op')
 data['status']='executed_verified';data['scope']='r119_p00_p12_complete';data['completed_experiment_root']=str(PROJECT_ROOT / 'Experiments/R119_SequenceGeometryValidation');data['completion_note']='R119 P00-P12 executed; final confirmation consumed once; no automatic promotion.'
 tmp=args.output.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(args.output);print(json.dumps({'status':'refreshed','changed_paths':changed,'plan_sha256':sha(args.output)},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
