from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,random,subprocess
ROOT=Path(__file__).resolve().parent
MODEL_NAME_BASE='R138-V42PSF8'
def now():return datetime.now(timezone.utc).isoformat()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
 tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(tmp,p)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def digest_array(a):return hashlib.sha256(a.tobytes(order='C')).hexdigest()
def config():return load(ROOT/'config_r138_psf.yaml')
def setup(seed):
 os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
 import numpy as np,torch
 random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
 torch.use_deterministic_algorithms(True);torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
 torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_num_threads(config()['cpu_threads'])
def state_digest(model):
 h=hashlib.sha256()
 for k,v in sorted(model.state_dict().items()):h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
 return h.hexdigest()
def source_records():
 files=[p for p in ROOT.rglob('*.py') if not any(x in p.parts for x in ['data','runs','results','__pycache__'])]
 files+=[ROOT/'config_r138_psf.yaml',ROOT/'config/USER_SPECIFICATION.md']
 files += [p for p in (ROOT/'config').glob('*.json') if p.name!='source_lock.json']
 files.append(ROOT/'data/manifest.json')
 files.extend(p for p in (ROOT/'calibration').glob('*') if p.is_file())
 return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(files)}
def verify_frozen(binding):
 for rel,h in binding.items():
  if sha(ROOT/rel)!=h:raise RuntimeError('Frozen source changed: '+rel)
def verify_protected():
 for item in load(ROOT/'config/protected_sources.json'):
  if sha(item['path'])!=item['sha256']:raise RuntimeError('Protected source changed: '+item['path'])
def verify_evaluation_sources():
 for rel,h in load(ROOT/'config/evaluation_manifest.json')['local_files'].items():
  if sha(ROOT/rel)!=h:raise RuntimeError('Frozen evaluation input changed: '+rel)
def scratch_declaration():
 return dict(training_mode='SCRATCH',loaded_pretrained_parameters=0,loaded_checkpoint=None,loaded_optimizer_state=None,loaded_ema_state=None,PSF_mode='V42_AUTO8_FROM25',PSF_files_loaded=1,PSF_legacy_SEM_independence_qualified=False,real_image_training_data=None,SEM_supervision=None,PI_supervision=None)
def announce():
 print('TRAINING MODE: SCRATCH\nLoaded pretrained parameters: 0\nLoaded checkpoint: NONE\nLoaded optimizer state: NONE\nPSF mode: V42 auto8from25 feature residual beta initial0.02\nReal-image training data: NONE\nSEM supervision: NONE\nPI supervision: NONE',flush=True)
