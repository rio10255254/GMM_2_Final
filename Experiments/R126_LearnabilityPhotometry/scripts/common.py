"""R126 utilities; previous experiment sources are import-only."""
from __future__ import annotations
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
R125=ROOT.parent/'R125_DataAlignedPilot'
R124=ROOT.parent/'R124_RealFirstPrototype'
sys.dont_write_bytecode=True
sys.path.insert(0,str(R124));sys.path.insert(0,str(R125))
from prototype.network import build_model
from prototype.factorized_observation import from_observation
from model.calibration import observation_from_profile,load_observation
from training.objectives import objective,robust_gray
CFG=json.loads((R125/'config/pilot.json').read_text())

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def thash(t):return hashlib.sha256(t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()

def save(path,value,exclusive=True):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x' if exclusive else 'w',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)

def setup():
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark=False
    torch.backends.cudnn.allow_tf32=False
    torch.backends.cuda.matmul.allow_tf32=False
    if not torch.cuda.is_available():raise RuntimeError('Bounded runtime protocol expects local CUDA')

def new_model(observation_on,seed,profile=None):
    torch.manual_seed(seed)
    obs=observation_from_profile(profile) if profile is not None else load_observation(R125/'config/real_observation_v2.json')
    m=build_model({**CFG['model'],'observation_steps':observation_on},from_observation(obs,checkpoint_ops=True)).cuda()
    m.observation_logits.requires_grad_(observation_on)
    for p in m.geometry_head.parameters():p.requires_grad_(False)
    return m

def pack(model,arm,seed,step,data_hash,initial_hash=None):
    return dict(kind='R126_bounded_exploratory_model',arm=arm,seed=seed,model_seed=seed,step=step,
                model_config=model.config_dict(),model_state={k:v.detach().cpu().clone() if isinstance(v,torch.Tensor) else v for k,v in model.state_dict().items()},
                training_source_manifest_sha256=data_hash,initial_checkpoint_sha256=initial_hash,
                calibration_qualified=False,uncertainty_calibrated=False,formal_promotion=False,
                model_source_sha256=sha(R125/'prototype/network.py'),
                checkpoint_note='Learned tensors only at evaluation; rebind frozen real observation. No calibrated real optics.')

def checkpoint(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:torch.save(payload,f)

def protect():
    out=ROOT/'config/protected_before.json'
    if out.exists():return
    old=R125.parent/'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/protected_inputs_v2.json'
    expected=json.loads(old.read_text());bad=[p for p,h in expected.items() if sha(p)!=h]
    if bad:raise ValueError(f'Original protected inputs already changed: {bad}')
    extra={str(p):sha(p) for p in R125.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    extra.update({str(p):sha(p) for sub in ['model','inference'] for p in (R124/sub).glob('*.py')})
    save(out,dict(original_R119_expectations=expected,R125_and_model_snapshot=extra,old_confirmation_payload_access=False))

def verify_protection():
    d=json.loads((ROOT/'config/protected_before.json').read_text())
    all_files={**d['original_R119_expectations'],**d['R125_and_model_snapshot']}
    bad=[p for p,h in all_files.items() if not Path(p).is_file() or sha(p)!=h]
    return dict(files=len(all_files),unchanged=not bad,failures=bad,original_R119=len(d['original_R119_expectations']))
