"""Verify deterministic replay of the rows preserved at the previous interruption."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/formal_8192';LOGS=ROOT/'runs/launcher_logs'
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 tail=LOGS/'uncheckpointed_steps_05889_05961.jsonl';active=RUN/'updates.jsonl';preserved=[json.loads(x) for x in tail.read_text().splitlines()];current=[json.loads(x) for x in active.read_text().splitlines()][5888:5961]
 if len(preserved)!=len(current)!=73:raise RuntimeError('Unexpected replay length')
 differences=[]
 for old,new in zip(preserved,current):
  old=dict(old);new=dict(new);old.pop('utc',None);new.pop('utc',None)
  if old!=new:differences.append(old['step'])
 if differences:raise RuntimeError(f'Replayed rows differ: {differences[:10]}')
 latest=json.loads((RUN/'latest.json').read_text(encoding='utf-8-sig'));receipt=dict(passed=True,checkpoint_step_used=5888,replayed_first_step=5889,replayed_last_step=5961,replayed_rows=73,exact_rows_excluding_runtime_timestamp=73,differing_steps=[],preserved_tail_sha256=sha(tail),active_log_sha256_at_verification=sha(active),current_step=json.loads(active.read_text().splitlines()[-1])['step'],latest_checkpoint_step=latest['step'],latest_checkpoint_sha256=latest['sha256'])
 path=LOGS/'RESUME_VERIFIED_05888.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,indent=2),encoding='utf-8');os.replace(tmp,path);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
