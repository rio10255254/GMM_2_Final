from __future__ import annotations
import hashlib,json,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];EXPS=ROOT.parent;REPO=EXPS.parent
R127=EXPS/'R127_MeasurementPreservationRepair';R126=EXPS/'R126_LearnabilityPhotometry';R125=EXPS/'R125_DataAlignedPilot';R124=EXPS/'R124_RealFirstPrototype'
sys.dont_write_bytecode=True
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(path,value,exclusive=True):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x' if exclusive else 'w',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
def atomic(path,value):
    p=Path(path);tmp=p.with_suffix(p.suffix+'.tmp')
    save(tmp,value,False);tmp.replace(p)
def record(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def protect():
    expected=load(R127/'config/protected_before.json')
    for rel,h in load(R127/'results/final_verification.json')['source_and_report_sha256'].items():expected[str(R127/rel)]=h
    bad=[p for p,h in expected.items() if not Path(p).is_file() or sha(p)!=h]
    if bad:raise RuntimeError(f'Historical identity mismatch; never accept new hashes: {bad}')
    expected.update({str(p):sha(p) for p in R127.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    save(ROOT/'config/protected_before.json',expected)
    out=ROOT/'reports/project_context_before';out.mkdir(parents=True,exist_ok=False)
    for name in ['PROJECT_STATE.md','ESTIMATOR_POLICY.json','Experiments/INDEX.md','RECON_GALLERY.md']:
        with (out/Path(name).name).open('xb') as f:f.write((REPO/name).read_bytes())
    print(json.dumps({'protected_files':len(expected),'utc':now()}),flush=True)
if __name__=='__main__':protect()
