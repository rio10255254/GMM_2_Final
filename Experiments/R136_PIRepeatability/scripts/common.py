from pathlib import Path
import os,sys,json,hashlib,datetime,importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent.parent
SOURCE=Path(r'C:\Users\Rio\Downloads\20260902_100MF_uncertainty\20260902_100MF_uncertainty\20260903')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.writing');q.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(q,p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4194304),b''):h.update(b)
    return h.hexdigest()
def record(p): return dict(path=str(Path(p).resolve()),sha256=sha(p))
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
