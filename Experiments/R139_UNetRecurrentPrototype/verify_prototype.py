"""Read-only verification of the R139 untrained architecture prototype."""
from pathlib import Path
import json,hashlib,ast
ROOT=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8388608),b''):h.update(b)
    return h.hexdigest()

lock=json.loads((ROOT/'config/SOURCE_LOCK.json').read_text(encoding='utf-8-sig'))
for rel,expected in lock.items():
    assert sha(ROOT/rel)==expected,rel
source=json.loads((ROOT/'config/SOURCE_MAP.json').read_text(encoding='utf-8-sig'))
for name,item in source.items():
    assert sha(item['path'])==item['sha256'],name
checks=[('preflight.json','status','untrained_prototype_preflight_only'),('generated_pair_preflight.json','status','discarded_real_pair_smoke')]
for name,key,value in checks:
    report=json.loads((ROOT/'results'/name).read_text(encoding='utf-8-sig'))
    assert report[key]==value
full=json.loads((ROOT/'results/full_size_preflight.json').read_text(encoding='utf-8-sig'))
assert full['full_shape']==[1544,2064] and full['untrained']
scope=json.loads((ROOT/'config/EXECUTION_SCOPE.json').read_text(encoding='utf-8-sig'))
assert scope['formal_updates']==0 and not scope['trained_weights_exist'] and not scope['full_real_validation']
print('PASS: source unchanged, V42/reference sources unchanged, prototype checks present, no training/effect claim')
