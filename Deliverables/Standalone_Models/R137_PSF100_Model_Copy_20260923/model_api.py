"""Inference-only copy. Explicitly replaces the checkpoint's old optical buffer."""
from pathlib import Path
import json,hashlib,copy
import numpy as np,torch
from model_r137_psf import Model
ROOT=Path(__file__).resolve().parent
ORIGINAL_SHA='061194a038089435a95a1c2956fff12c6eb68d42ed65423e81ff8a42e5e11bc2'
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def load_model(psf_bank=None,device='cpu'):
 cfg=json.loads((ROOT/'config_r137_psf.yaml').read_text(encoding='utf-8-sig'))
 if cfg['model']['psf_count']!=100 or cfg['model']['optical_gain']!=.02:raise ValueError('This copy is fixed to 100 PSFs and gain0.02')
 bank=Path(psf_bank).resolve() if psf_bank is not None else ROOT/cfg['model']['psf_bank']
 # Validate/construct from the new bank before opening any neural checkpoint.
 cfg=copy.deepcopy(cfg);cfg['model']['psf_bank']=str(bank)
 model=Model(cfg['model']);new_mean=model.optics.mean_psf.detach().clone()
 checkpoint=ROOT/'weights/R137_original_trained.pth'
 if sha(checkpoint)!=ORIGINAL_SHA:raise RuntimeError('Original R137 checkpoint identity changed')
 original=torch.load(checkpoint,map_location='cpu',weights_only=False)
 if original.get('model_name')!='R137-WeakPSF' or original.get('step')!=8192:raise ValueError('Unexpected original checkpoint')
 state=dict(original['model'])
 # Critical: load_state_dict would otherwise silently restore the old 25-PSF mean.
 state['optics.mean_psf']=new_mean
 model.load_state_dict(state,strict=True)
 for key,value in model.state_dict().items():
  if key!='optics.mean_psf' and not torch.equal(value,original['model'][key]):raise RuntimeError('A trained parameter changed: '+key)
 if not torch.equal(model.optics.mean_psf,new_mean):raise RuntimeError('New PSF mean was not retained')
 metadata=dict(model_name='R137-PSF100-InferenceCopy',source_model='R137-WeakPSF',trained_with_PSF_count=25,inference_PSF_count=100,PSF_gain=.02,PSF_bank_path=str(bank),PSF_bank_sha256=sha(bank),original_checkpoint_sha256=ORIGINAL_SHA,neural_parameters_unchanged=True,retrained_with100=False,validated_on_real_images_with100=False,config=cfg)
 return model.to(device).eval(),metadata

def predict(model,x,mode='full',core=512,halo=96):
 if mode=='full':return model(x)
 if mode!='tiled' or halo<model.dependency_radius:raise ValueError('Invalid tile mode or halo')
 # One global optical cue; never recompute a different PSF cue per tile.
 cue=model.optics(x);out=torch.empty_like(x);h,w=x.shape[-2:]
 for y in range(0,h,core):
  for xx in range(0,w,core):
   y1=min(h,y+core);x1=min(w,xx+core);a=max(0,y-halo);b=min(h,y1+halo);l=max(0,xx-halo);r=min(w,x1+halo)
   value=model(x[...,a:b,l:r],optical_cue=cue[...,a:b,l:r]);out[...,y:y1,xx:x1]=value[...,y-a:y1-a,xx-l:x1-l]
 return out
