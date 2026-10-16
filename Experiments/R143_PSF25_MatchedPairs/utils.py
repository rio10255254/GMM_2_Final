"""Package-local I/O and reproducibility utilities."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,random

ROOT=Path(__file__).resolve().parent

def now():return datetime.now(timezone.utc).isoformat()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(tmp,p)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def digest_array(value):return hashlib.sha256(value.tobytes(order='C')).hexdigest()
def model_config():return load(ROOT/'config/model.json')
def train_config():return load(ROOT/'config/train.json')
def verify_bank_lock():
    cfg=model_config();bank=ROOT/cfg['psf_bank'];lock_path=ROOT/'calibration/BANK_LOCK.json'
    if not bank.is_file() or not lock_path.is_file():
        raise FileNotFoundError('Measured PSF bank or its provenance lock is missing')
    lock=load(lock_path)
    if lock['bank_sha256']!=sha(bank) or lock['count']!=cfg['psf_count']:
        raise RuntimeError('Measured PSF bank changed since installation')
    if lock.get('test_only',False) and os.environ.get('MOSR_ALLOW_SYNTHETIC_TEST_BANK')!='1':
        raise RuntimeError('Test-only synthetic bank is not permitted for normal package use')
    return lock
def setup(seed):
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
    import numpy as np,torch
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False
