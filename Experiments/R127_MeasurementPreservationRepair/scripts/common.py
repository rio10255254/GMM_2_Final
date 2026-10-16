from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1];EXPS=ROOT.parent
R126=EXPS/'R126_LearnabilityPhotometry';R125=EXPS/'R125_DataAlignedPilot';R124=EXPS/'R124_RealFirstPrototype'
sys.dont_write_bytecode=True
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(path,value,exclusive=True):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x' if exclusive else 'w',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
def record(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def protect():
    old=json.loads((R126/'config/protected_before.json').read_text(encoding='utf-8'))
    expected={**old['original_R119_expectations'],**old['R125_and_model_snapshot']}
    assert all(sha(p)==h for p,h in expected.items()),'Older source mismatch; never accept new hashes automatically'
    expected.update({str(p):sha(p) for p in R126.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    save(ROOT/'config/protected_before.json',expected)
    context=ROOT/'reports/project_context_before';context.mkdir(parents=True,exist_ok=False)
    for name in ['PROJECT_STATE.md','ESTIMATOR_POLICY.json','Experiments/INDEX.md','RECON_GALLERY.md']:
        p=REPO/name
        with (context/Path(name).name).open('xb') as f:f.write(p.read_bytes())
def verify_old():
    expected=json.loads((ROOT/'config/protected_before.json').read_text(encoding='utf-8'));bad=[p for p,h in expected.items() if not Path(p).is_file() or sha(p)!=h]
    return {'count':len(expected),'unchanged':not bad,'failures':bad}
if __name__=='__main__':protect()
