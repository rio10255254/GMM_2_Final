"""Preserve uncheckpointed rows and atomically align the formal log to latest checkpoint."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/formal_8192';LOGS=ROOT/'runs/launcher_logs'
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def save(path,value):
 p=Path(path);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def main():
 latest=json.loads((RUN/'latest.json').read_text(encoding='utf-8-sig'));checkpoint=Path(latest['path']);step=int(latest['step'])
 if sha(checkpoint)!=latest['sha256']:raise RuntimeError('Checkpoint hash mismatch')
 log=RUN/'updates.jsonl';raw=log.read_bytes();lines=raw.splitlines(keepends=True)
 if len(lines)<=step:raise RuntimeError(f'Expected uncheckpointed tail after step {step}; got {len(lines)} rows')
 parsed=[json.loads(x) for x in lines]
 if [x['step'] for x in parsed] != list(range(1,len(lines)+1)):raise RuntimeError('Update steps are not contiguous')
 first,last=step+1,len(lines);tail=LOGS/f'uncheckpointed_steps_{first:05d}_{last:05d}.jsonl'
 if tail.exists():raise FileExistsError(tail)
 tail.write_bytes(b''.join(lines[step:]));tail_rows=tail.read_bytes().splitlines()
 if len(tail_rows)!=last-step or [json.loads(x)['step'] for x in tail_rows]!=list(range(first,last+1)):raise RuntimeError('Tail preservation failed')
 tmp=log.with_suffix('.resume.tmp');tmp.write_bytes(b''.join(lines[:step]));os.replace(tmp,log)
 if len(log.read_bytes().splitlines())!=step:raise RuntimeError('Active log truncation failed')
 receipt=dict(state='resume_prepared',checkpoint_step=step,checkpoint_path=str(checkpoint),checkpoint_sha256=latest['sha256'],original_update_rows=last,active_update_rows=step,preserved_tail_path=str(tail),preserved_tail_rows=last-step,original_updates_sha256=hashlib.sha256(raw).hexdigest(),active_updates_sha256=sha(log),preserved_tail_sha256=sha(tail),replayed_steps=[first,last],reason='The process ended without stderr after the last checkpoint; uncheckpointed rows are preserved and will be deterministically replayed from the verified checkpoint.')
 save(LOGS/f'RESUME_FROM_{step:05d}.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
