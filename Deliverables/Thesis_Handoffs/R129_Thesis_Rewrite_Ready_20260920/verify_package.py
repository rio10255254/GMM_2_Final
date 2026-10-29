"""Verify the sealed writing-material package without changing any files."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
items=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'))
for item in items:
    p=(ROOT/item['path']).resolve()
    assert ROOT==p.parent or ROOT in p.parents,item['path']
    assert p.is_file() and p.stat().st_size==item['bytes'],item['path']
    assert sha(p)==item['sha256'],item['path']
checks=json.loads((ROOT/'07_Checks/preparation_checks.json').read_text(encoding='utf-8'))
assert sha(ROOT/'01_Original_Thesis/thesis_v34_original_unchanged.docx')==checks['original_word_sha256']
assert checks['parents_verified']==768 and checks['unique_training_updates']==8192
assert not checks['word_edited'] and not checks['new_model_training']
print(f'PASS: {len(items)} material files; original thesis copy unchanged. This does not certify a rewritten thesis or new scientific result.')
