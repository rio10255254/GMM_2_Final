"""Package-local paths, deterministic execution and durable records."""
import os,json,hashlib,datetime,random,math
from pathlib import Path
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import numpy as np
import torch
ROOT=Path(__file__).resolve().parent
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def record(path):
    p=Path(path).resolve();return dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))
from serialization import save,atomic

def setup(seed):
    torch.set_num_threads(4);random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.use_deterministic_algorithms(True)
def digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def state_digest(model):
    h=hashlib.sha256()
    for k,v in model.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()
def create(device='cuda'):
    from model import Hybrid
    cfg=load(ROOT/'config/training.json');setup(cfg['seed']);bank=np.load(ROOT/'calibration/measured_psf_bank.npz')
    m=Hybrid(torch.from_numpy(bank['mean']),torch.from_numpy(bank['candidates'])).to(device)
    m.load_state_dict(torch.load(ROOT/'weights/initial_r134p.pth',map_location=device)['model'],strict=True)
    opt=torch.optim.AdamW(m.parameters(),lr=cfg['optimizer']['peak_lr'],weight_decay=cfg['optimizer']['weight_decay'])
    return m,opt
def binding(cfg):
    frozen=load(ROOT/'PACKAGE_MANIFEST.json')
    return dict(config_sha256=sha(ROOT/'config/training.json'),runtime_files={p:h for p,h in frozen['files'].items() if p.endswith(('.py','.m')) or p.startswith(('weights/','calibration/'))},data_manifest_sha256=sha(ROOT/'training_data/manifest.json'),validation_panel_sha256=sha(ROOT/'validation/panel.json'))
def verify_binding(value):
    if sha(ROOT/'config/training.json')!=value['config_sha256']:raise RuntimeError('Training configuration changed; start a distinct run')
    if sha(ROOT/'training_data/manifest.json')!=value['data_manifest_sha256']:raise RuntimeError('Data manifest changed')
    if sha(ROOT/'validation/panel.json')!=value['validation_panel_sha256']:raise RuntimeError('Validation panel changed')
    for p,h in value['runtime_files'].items():
        if sha(ROOT/p)!=h:raise RuntimeError('Frozen source changed: '+p)
def lr_at(step,cfg):
    o=cfg['optimizer'];warm=o['warmup_updates'];end=cfg['updates']
    if step<=warm:return o['peak_lr']*step/warm
    return o['minimum_lr']+.5*(o['peak_lr']-o['minimum_lr'])*(1+math.cos(math.pi*(step-warm)/(end-warm)))
