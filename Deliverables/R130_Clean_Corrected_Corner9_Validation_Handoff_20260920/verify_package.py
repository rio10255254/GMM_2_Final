from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parent
items=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
errors=[]
for item in items:
 p=(root/item['path']).resolve()
 if not p.is_relative_to(root) or not p.is_file():errors.append(item['path']);continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8388608),b''):h.update(chunk)
 if h.hexdigest()!=item['sha256']:errors.append(item['path'])
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='MANIFEST.json'}
expected={x['path'] for x in items}
errors.extend(sorted(actual^expected))
if errors:print('FAIL:',errors);sys.exit(1)
print('PASS:',len(items),'payload files verified; no files modified')
