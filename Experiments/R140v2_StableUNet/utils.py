"""Utilities shared by the isolated R140v2 formal execution."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,random
ROOT=Path(__file__).resolve().parent

def now():return datetime.now(timezone.utc).isoformat()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
 tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(tmp,p)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(8388608),b''):h.update(chunk)
 return h.hexdigest()
def digest_array(a):return hashlib.sha256(a.tobytes(order='C')).hexdigest()
def model_config():return load(ROOT/'config/model.json')
def config():return load(ROOT/'config/TRAIN.json')
def setup(seed):
 os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
 import numpy as np,torch
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_num_threads(4)
def state_digest(model):
 h=hashlib.sha256()
 for name,value in sorted(model.state_dict().items()):
  h.update(name.encode());h.update(value.detach().cpu().contiguous().numpy().tobytes())
 return h.hexdigest()
def source_records():
 paths=[ROOT/n for n in ['model.py','training_policy.py','dataset.py','losses.py','utils.py','infer_model.py','evaluate_real_measurement.py','compare_measurements.py','final_audit.py','write_report.py','formal/train.py','formal/launch.py','formal/preflight.py','formal/closeout.py','formal/monitor.py','scripts/pilot.py','scripts/full_size_preflight.py','optical/feature.py','config/model.json','config/TRAIN.json','config/DATA_REFERENCE.json','config/EVALUATION_REFERENCE.json','FORMAL_RUN.md','config/PROTECTED_SOURCES.json','config/measured_psf_bank.npz','data/manifest.json']]
 return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in paths}
def verify_frozen(lock):
 for rel,expected in lock.items():
  if sha(ROOT/rel)!=expected:raise RuntimeError('Frozen R140v2 execution source changed: '+rel)
def verify_protected():
 for item in load(ROOT/'config/PROTECTED_SOURCES.json'):
  if sha(item['path'])!=item['sha256']:raise RuntimeError('Protected historical artifact changed: '+item['path'])
def verify_evaluation():
 for rel,expected in load(ROOT/'config/EVALUATION_REFERENCE.json')['local_files'].items():
  if sha(ROOT/rel)!=expected:raise RuntimeError('R140v2 evaluation input changed: '+rel)
