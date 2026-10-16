import os,sys,json,time,hashlib,datetime,random
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8');sys.dont_write_bytecode=True
import numpy as np,torch
ROOT=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for v in iter(lambda:f.read(4*1024*1024),b''):h.update(v)
    return h.hexdigest()
def record(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def atomic(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    for i in range(30):
        try:t=p.with_suffix('.writing');t.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False),encoding='utf-8');os.replace(t,p);return
        except PermissionError:time.sleep(.1)
    raise RuntimeError('State IO retry exhausted')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(x):return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
def model_digest(m):
    h=hashlib.sha256()
    for k,v in m.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()
def setup(seed):
    torch.set_num_threads(4);torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)
    torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
def create(arm,seed,device='cuda'):
    from net.network import Network
    setup(seed);bank=np.load(ROOT/'calibration/measured_psf_bank.npz');m=Network(torch.from_numpy(bank['mean']),torch.from_numpy(bank['candidates']),arm)
    torch.nn.init.zeros_(m.prior.head.weight);torch.nn.init.zeros_(m.prior.head.bias)
    return m.to(device)
def verify():
    for r in load(ROOT/'config/source_protection.json')['sources']:assert sha(r['path'])==r['sha256']

