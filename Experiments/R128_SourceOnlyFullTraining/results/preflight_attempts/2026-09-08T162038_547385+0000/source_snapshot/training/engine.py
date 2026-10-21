"""Shared arithmetic, deterministic optimization, and explicit checkpoint state."""
import os,sys,math,random,hashlib
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
import numpy as np
import torch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import load
from model.network import Model
from training.objectives import objective
from training.data import digest

def setup(seed):
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.use_deterministic_algorithms(True)
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)

def lr_at(update,cfg):
    o=cfg['optimizer'];warm=o['warmup_updates'];end=cfg['updates_per_run']
    if update<=warm:return o['peak_lr']*update/warm
    return o['minimum_lr']+.5*(o['peak_lr']-o['minimum_lr'])*(1+math.cos(math.pi*(update-warm)/(end-warm)))

def create(seed,device,cfg):
    setup(seed);model=Model(cfg['model']).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=cfg['optimizer']['peak_lr'],weight_decay=cfg['optimizer']['weight_decay'])
    return model,opt

def state_digest(model):
    h=hashlib.sha256()
    for k,v in model.state_dict().items():h.update(k.encode());h.update(v.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def update(model,opt,batch,step,arm,cfg):
    model.train();opt.zero_grad(set_to_none=True)
    learning_rate=lr_at(step,cfg)
    for group in opt.param_groups:group['lr']=learning_rate
    actual_hash=digest(batch['source'].detach().cpu().numpy())
    if actual_hash!=batch['cpu_input_sha256']:raise RuntimeError('Consumed input differs from prepared source')
    details=model.forward_details(batch['source'])
    loss,terms=objective(details,batch,cfg['loss_weights'],cfg['arms'][arm]['observation_loss_weight'])
    if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
    loss.backward()
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),cfg['optimizer']['gradient_clip'],error_if_nonfinite=True)
    opt.step()
    if any(not torch.isfinite(p).all() for p in model.parameters()):raise FloatingPointError('Nonfinite learned parameter')
    return dict(update=step,arm=arm,learning_rate=learning_rate,loss=float(loss.detach()),terms={k:float(v.detach()) for k,v in terms.items()},gradient_norm=float(norm),actual_input_sha256=actual_hash,source_uint8_sha256=batch['source_uint8_sha256'],parent_id=batch['metadata']['parent_id'],parent_arrays_sha256=batch['parent']['arrays_sha256'],noise_seed=batch['noise_seed'],noise_sigma_gray=batch['metadata']['noise_sigma_gray'],kernel_sha256=digest(batch['kernel'].detach().cpu().numpy()))

def payload(model,opt,step,arm,seed,binding):
    return dict(model=model.state_dict(),optimizer=opt.state_dict(),step=step,arm=arm,seed=seed,binding=binding,model_config=model.config_dict(),python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],parameter_sha256=state_digest(model))

def checkpoint(path,model,opt,step,arm,seed,binding):
    path=Path(path)
    if path.exists():raise FileExistsError('Immutable checkpoint exists')
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.writing')
    if temp.exists():raise FileExistsError('Incomplete write requires inspection')
    torch.save(payload(model,opt,step,arm,seed,binding),temp);temp.replace(path)

def restore(path,model,opt,binding,arm,seed):
    p=torch.load(path,map_location='cpu')
    if p['binding']!=binding or p['arm']!=arm or p['seed']!=seed:raise RuntimeError('Checkpoint study mismatch')
    model.load_state_dict(p['model']);opt.load_state_dict(p['optimizer'])
    if state_digest(model)!=p['parameter_sha256']:raise RuntimeError('Corrupt model state')
    random.setstate(p['python_rng']);np.random.set_state(p['numpy_rng']);torch.set_rng_state(p['torch_rng'])
    if p['cuda_rng']:torch.cuda.set_rng_state_all(p['cuda_rng'])
    return p['step']
