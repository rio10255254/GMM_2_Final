"""Materialize the verified 5,000-scene package inside R109 using NTFS hard links."""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];CONFIG=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'));SOURCE=Path(PROJECT_ROOT / CONFIG['data']['source_package']);DESTINATION=ROOT/CONFIG['data']['package_root'];EXPECTED=CONFIG['data']['source_manifest_sha256']
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as handle:
  for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def main():
 manifest=SOURCE/'manifest.json'
 if not manifest.is_file() or sha(manifest)!=EXPECTED:raise RuntimeError('Verified R107 source manifest mismatch')
 files=sorted(path for path in SOURCE.rglob('*') if path.is_file());linked=0;verified=0
 for source in files:
  destination=DESTINATION/source.relative_to(SOURCE);destination.parent.mkdir(parents=True,exist_ok=True)
  if destination.exists():
   if destination.stat().st_size!=source.stat().st_size:raise RuntimeError(f'Existing size mismatch: {destination}')
   verified+=1;continue
  os.link(source,destination);linked+=1
 local_manifest=DESTINATION/'manifest.json'
 if sha(local_manifest)!=EXPECTED:raise RuntimeError('Local hard-linked manifest mismatch')
 payload=json.loads(local_manifest.read_text(encoding='utf-8'));counts={split:sum(row['split']==split for row in payload['records']) for split in ('train','validation')}
 if counts!={'train':5000,'validation':512}:raise RuntimeError(f'Unexpected counts: {counts}')
 state={'status':'complete','source':str(SOURCE),'destination':str(DESTINATION),'files':len(files),'linked_now':linked,'verified_existing':verified,'manifest_sha256':EXPECTED,'counts':counts,'hard_linked':True,'real_training_pixels':False}
 (ROOT/'data/PREPARED_STATE.json').write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
