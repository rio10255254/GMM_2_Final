"""Local experiment paths and immutable records; no legacy network weight loading."""
import os,sys,json,hashlib,datetime,random,math
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent.parent
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'model'),str(ROOT/'training')]
import torch,numpy as np
from types import SimpleNamespace
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def record(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def atomic(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix('.writing');t.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(t,p)
def setup(seed):
    torch.set_num_threads(4);random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
def digest(m):
    h=hashlib.sha256()
    for k,v in m.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()
class V42(torch.nn.Module):
    def __init__(self,original=False):
        super().__init__()
        if original:from model_original import GeoEdgeAlignSR_v1_v5_NoCoord as Network
        else:from model_v42 import GeoEdgeAlignSR_v1_v5_NoCoord as Network
        args=load(ROOT/'config/architecture.json');args['psf_fitted_path']=str(ROOT/'calibration/shared_psf.mat')
        self.network=Network(**args)
    def forward(self,x):
        from deterministic_ops import pad
        h,w=x.shape[-2:];ph=(-h)%8;pw=(-w)%8
        xp=pad(x,(0,pw,0,ph),'reflect') if ph or pw else x
        return self.network(xp)[...,:h,:w]
    def forward_details(self,x,trace=False):
        output=self(x);quality=self.network.last_quality_gate.flatten(1).mean(1)
        return SimpleNamespace(output=output,quality=quality)
def create(device='cuda',original=False):
    cfg=load(ROOT/'config/training.json');setup(cfg['seed']);m=V42(original).to(device)
    opt=torch.optim.AdamW(m.parameters(),lr=cfg['optimizer']['peak_lr'],weight_decay=cfg['optimizer']['weight_decay'])
    return m,opt
def verify_frozen():
    f=load(ROOT/'config/frozen.json')
    for item in f['sources']:
        if sha(item['path'])!=item['sha256']:raise RuntimeError('Frozen source changed: '+item['path'])
    return sha(ROOT/'config/frozen.json')
