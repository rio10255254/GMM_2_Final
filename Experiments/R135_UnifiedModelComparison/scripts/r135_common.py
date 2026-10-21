from pathlib import Path
import os,sys,json,hashlib,time,datetime,importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8');sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent.parent;P134=REPO/'Experiments/R134_DirectStateRepair/precision_revision'
sys.path.insert(0,str(ROOT))
import numpy as np,torch
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def record(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def plain(x):
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,dict):return {k:plain(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [plain(v) for v in x]
    return x
def save(p,v):
    text=json.dumps(plain(v),ensure_ascii=False,indent=2,allow_nan=False);p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:f.write(text)
def atomic(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);text=json.dumps(plain(v),ensure_ascii=False,indent=2,allow_nan=False);q=p.with_name(p.name+'.writing')
    for _ in range(30):
        try:q.write_text(text,encoding='utf-8');os.replace(q,p);return
        except PermissionError:time.sleep(.1)
    raise RuntimeError('State remains locked')
def setup():
    torch.set_num_threads(4);torch.manual_seed(135001);np.random.seed(135001);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def verify():
    for r in load(ROOT/'config/plan.json')['protected']:
        if sha(r['path'])!=r['sha256']:raise RuntimeError('Protected source changed: '+r['path'])
def guard(x,v,width):
    h,w=x.shape[-2:];yy=torch.arange(h,device=x.device)[:,None];xx=torch.arange(w,device=x.device)[None,:];d=torch.minimum(torch.minimum(yy,h-1-yy),torch.minimum(xx,w-1-xx)).float();return x+(v-x)*((d-width)/16).clamp(0,1)
