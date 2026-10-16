"""Run with Python3 from any location; requires no third-party packages."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent
manifest=json.loads((root/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8-sig'))
for item in manifest['files']:
    p=root/item['path'];assert p.is_file(),item['path']
    assert p.stat().st_size==item['bytes'],item['path']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],item['path']
print('Verified',len(manifest['files']),'files.')
