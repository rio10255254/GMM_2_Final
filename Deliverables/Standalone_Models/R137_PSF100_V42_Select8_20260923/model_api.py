"""R137 trained core with the original V42 eight-candidate weak PSF module."""
from pathlib import Path
import json,hashlib,copy
import torch
from model_r137_psf import Model
ROOT=Path(__file__).resolve().parent
ORIGINAL_SHA='061194a038089435a95a1c2956fff12c6eb68d42ed65423e81ff8a42e5e11bc2'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_model(psf_bank=None,device='cpu'):
 cfg=copy.deepcopy(json.loads((ROOT/'config_r137_psf.yaml').read_text(encoding='utf-8-sig')))
 bank=Path(psf_bank).resolve() if psf_bank is not None else ROOT/cfg['model']['psf_bank']
 if cfg['model']['psf_count']!=100:raise ValueError('Expected100 PSFs')
 if not bank.is_file():raise FileNotFoundError('Supply calibration/psf_100.npz first')
 cfg['model']['psf_bank']=str(bank)
 # Reproducible fresh gating, without changing the caller RNG or importing V42 learned weights.
 with torch.random.fork_rng(devices=[]):
  torch.manual_seed(1378001);model=Model(cfg['model'])
  torch.nn.init.zeros_(model.optics.gating[-1].weight);torch.nn.init.zeros_(model.optics.gating[-1].bias)
 checkpoint=ROOT/'weights/R137_original_trained.pth'
 if sha(checkpoint)!=ORIGINAL_SHA:raise RuntimeError('Original R137 checkpoint changed')
 original=torch.load(checkpoint,map_location='cpu',weights_only=False)
 if original.get('model_name')!='R137-WeakPSF' or original.get('step')!=8192:raise ValueError('Wrong trained model')
 state=model.state_dict();copied=[]
 for key,value in original['model'].items():
  if key.startswith('backbone.') or key=='step_logits':
   if key not in state or state[key].shape!=value.shape:raise ValueError('Core mismatch: '+key)
   state[key]=value;copied.append(key)
 expected=[k for k in state if k.startswith('backbone.') or k=='step_logits']
 if set(copied)!=set(expected):raise ValueError('Incomplete trained core transfer')
 model.load_state_dict(state,strict=True)
 for key in copied:
  if not torch.equal(model.state_dict()[key],original['model'][key]):raise RuntimeError('Core changed')
 meta=dict(model_name='R137-PSF100-V42-Select8',PSF_count=100,candidates=8,automatic_candidate_indices=list(model.optics.psf_indices),candidate_selection='V42 evenly spaced automatic fallback; no spatial grid invented',mixing='V42 input-dependent softmax network',trained_core_unchanged=True,old_R137_optical_adapter_removed=True,new_gating_trained=False,initial_mix='uniform1/8',initial_effective_beta=.02,PSF_bank_sha256=sha(bank),original_checkpoint_sha256=ORIGINAL_SHA,retrained=False,validated_with_user_PSF100=False)
 return model.to(device).eval(),meta

def predict(model,x,mode='full',**kwargs):
 if mode!='full':raise ValueError('V42 global feature pooling/FFT requires full mode; independent tile inference is not equivalent')
 return model(x)
