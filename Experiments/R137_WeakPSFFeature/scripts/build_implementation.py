from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
P=Path(str(PROJECT_ROOT / 'Experiments/R137_WeakPSFFeature'))
def edit(name,old,new):
 p=P/name;s=p.read_text(encoding='utf-8');assert old in s,(name,old);p.write_text(s.replace(old,new),encoding='utf-8')
(P/'optical/__init__.py').write_text('')
(P/'optical/feature.py').write_text('''"""Fixed legacy25 PSF cue; no neural checkpoint import or spatial mapping inference."""
import math
from pathlib import Path
import numpy as np,torch
from torch import nn
from torch.nn import functional as F
class OpticalCue(nn.Module):
 def __init__(self,path,reg):
  super().__init__()
  with np.load(path,allow_pickle=False) as z:k=z['all_kernels'].astype('float64')
  if k.shape!=(25,101,101) or not np.isfinite(k).all() or k.min()<0 or (k.sum((1,2))<=0).any():raise ValueError('Invalid 25-PSF bank')
  k=k/k.sum((1,2),keepdims=True);mean=k.mean(0);mean=mean/mean.sum()
  self.register_buffer('mean_psf',torch.tensor(mean,dtype=torch.float32));self.reg=float(reg);self.calls=0;self._cache={}
 def forward(self,x):
  from model_r137_psf import reflect_pad
  self.calls+=1;p=50
  if min(x.shape[-2:])<=p:raise ValueError('PSF requires image dimensions >50')
  xp=reflect_pad(x,p);h,w=xp.shape[-2:];key=(h,w,str(x.device))
  if key not in self._cache:
   k=self.mean_psf;yy,xx=torch.meshgrid(torch.arange(101,device=x.device),torch.arange(101,device=x.device),indexing='ij');cy=(k*yy).sum()/k.sum();cx=(k*xx).sum()/k.sum()
   H=torch.fft.rfft2(F.pad(k,(0,w-101,0,h-101)));fy=torch.fft.fftfreq(h,device=x.device)[:,None];fx=torch.fft.rfftfreq(w,device=x.device)[None,:]
   H=H*torch.exp(2j*math.pi*(fy*cy+fx*cx));G=(1+self.reg)*H.conj()/(H.abs().square()+self.reg)
   if len(self._cache)>4:self._cache.clear()
   self._cache[key]=G
  y=torch.fft.irfft2(torch.fft.rfft2(xp)*self._cache[key],s=(h,w))[...,p:-p,p:-p]
  return y-x
''',encoding='utf-8')
edit('model_r137_psf.py','from optical.interface import require_disabled','from optical.feature import OpticalCue\nfrom pathlib import Path')
edit('model_r137_psf.py','def forward(self,f):\n        h=F.silu(self.stem(f))','def forward(self,f,optical_feature=None):\n        h=self.stem(f)\n        if optical_feature is not None:h=h+optical_feature\n        h=F.silu(h)')
edit('model_r137_psf.py',"super().__init__();require_disabled(cfg['optical_mode']);self.cfg=dict(cfg)","super().__init__();self.cfg=dict(cfg)\n        if cfg['optical_mode']!='feature_single':raise ValueError('This experiment requires explicit feature_single mode')")
edit('model_r137_psf.py',"self.loaded_pretrained_parameters=0;self.optical_mode='off';self.optical_files_loaded=0","self.loaded_pretrained_parameters=0;self.optical_mode='feature_single';self.optical_files_loaded=1\n        self.optics=OpticalCue(Path(__file__).resolve().parent/cfg['psf_bank'],cfg['optical_reg'])\n        self.optical_adapter=LocalConv(1,cfg['channels'])\n        nn.init.zeros_(self.optical_adapter.weight);nn.init.zeros_(self.optical_adapter.bias)\n        self.optical_enabled=True;self.optical_gain=float(cfg['optical_gain'])")
edit('model_r137_psf.py','def forward(self,x,trace=False):','def forward(self,x,trace=False,optical_cue=None):')
edit('model_r137_psf.py','fixed=self.features(x);r=torch.zeros_like(x);z=x;states=[]',"fixed=self.features(x);r=torch.zeros_like(x);z=x;states=[]\n        optical_feature=None\n        if self.optical_enabled and self.optical_gain!=0:\n            if optical_cue is None:optical_cue=self.optics(x)\n            if optical_cue.shape!=x.shape:raise ValueError('Optical cue shape mismatch')\n            optical_feature=self.optical_gain*torch.tanh(self.optical_adapter(optical_cue))")
edit('model_r137_psf.py','self.backbone(f))','self.backbone(f,optical_feature))')
# Full native optical observation retained for training; no labels enter the PSF cue.
edit('dataset_r137_psf.py',"return dict(source=torch.from_numpy(x).to(device)","return dict(optical_source=torch.from_numpy(np.ascontiguousarray(source[:,None].astype(np.float32)/np.float32(255))).to(device),source=torch.from_numpy(x).to(device)")
(P/'batch_prediction.py').write_text('''def predict_batch(model,batch):
 cue=None
 if model.optical_enabled and model.optical_gain!=0:cue=model.optics(batch['optical_source'])[...,32:352,32:352]
 return model(batch['source'],optical_cue=cue)
''',encoding='utf-8')
edit('train_r137_psf.py','from evaluate_generated import evaluate','from evaluate_generated import evaluate\nfrom batch_prediction import predict_batch')
edit('train_r137_psf.py',"pred=model(batch['source'])","pred=predict_batch(model,batch)")
edit('train_r137_psf.py',"optical_mode='off'","optical_mode='feature_single'")
edit('evaluate_generated.py','from utils import save','from utils import save\nfrom batch_prediction import predict_batch')
edit('evaluate_generated.py',"pred=model(b['source'])","pred=predict_batch(model,b)")
edit('utils.py',"PSF_mode='OFF',PSF_files_loaded=0","PSF_mode='FEATURE_SINGLE_WEAK',PSF_files_loaded=1,PSF_legacy_SEM_independence_qualified=False")
edit('utils.py','PSF mode: OFF','PSF mode: FEATURE_SINGLE legacy25 weak gain0.02')
edit('utils.py',"files.append(ROOT/'data/manifest.json')","files.append(ROOT/'data/manifest.json')\n files.extend(p for p in (ROOT/'calibration').glob('*') if p.is_file())")
edit('infer_r137_psf.py',"if mode=='full':return model(x)","cue=model.optics(x) if model.optical_enabled and model.optical_gain!=0 else None\n    if mode=='full':return model(x,optical_cue=cue)")
edit('infer_r137_psf.py','v=model(patch)','v=model(patch,optical_cue=None if cue is None else cue[...,a:b,l:r])')
edit('infer_r137_psf.py',"p.get('optical_mode')!='off'","p.get('optical_mode')!='feature_single'")
# Four methods; baseline reader and SEM identity checks unchanged.
edit('compare_measurements.py',"MODELS=['Raw','R129','R137-WeakPSF']","MODELS=['Raw','R129','R130-Clean','R137-WeakPSF']")
edit('compare_measurements.py','assert len(d)==5400','assert len(d)==7200')
edit('compare_measurements.py',"for base in ['Raw','R129']:","for base in ['Raw','R129','R130-Clean']:")
# Explicitly label timer as including the optical cue, do not call it neural-only.
edit('evaluate_real_measurement.py','total_neural_inference_seconds=inference','total_reconstruction_seconds=inference')
(P/'START_R137.cmd').write_text('@echo off\r\ncd /d "%~dp0"\r\npython -B scripts\\launch_r137.py\r\npause\r\n',encoding='ascii')
print('R137 feature-level implementation prepared')
