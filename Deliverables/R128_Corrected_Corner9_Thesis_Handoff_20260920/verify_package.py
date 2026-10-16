from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
for item in manifest:
 p=root/item['path']
 assert p.is_file(),str(p)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],str(p)
print('PASS:',len(manifest),'files verified')
