from pathlib import Path
import hashlib,json,datetime,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];R128=ROOT.parent/'R128_SourceOnlyFullTraining';REPO=ROOT.parent.parent
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def record(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
