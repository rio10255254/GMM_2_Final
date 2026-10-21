"""Native method outputs, with a predeclared memory-only inference fallback."""
from pathlib import Path
import gc,sys
import numpy as np
import torch
from torch import nn
from study import ROOT,PACK,read,sha
from benchmark_models import make_model
if str(PACK) not in sys.path:sys.path.insert(0,str(PACK))
from models.fullres_psf import FullResPSF,reflect_pad

RUNTIME_FRAME_NUMBERS=[0,465,929]
FALLBACK={'core':512,'halo':192,'trigger':'CUDA out of memory only','stitching':'core only; no overlap averaging'}


class Wiener(nn.Module):
    def __init__(self,regularization):
        super().__init__();self.regularization=float(regularization)
    def forward(self,x,operators=None,optics=None,noise_sigma=None):
        if optics is None:raise ValueError('Wiener requires the fixed mean PSF')
        padded=reflect_pad(x,50);h,w=padded.shape[-2:]
        transfer=optics._transfer(h,w,-1,x.device)
        inverse=transfer.conj()/(transfer.abs().square()+self.regularization).clamp_min(1e-20)
        value=torch.fft.irfft2(torch.fft.rfft2(padded)*inverse,s=(h,w))
        return value[...,50:-50,50:-50]


def load_method(method,device='cuda'):
    optics=FullResPSF(PACK/'calibration/psf25_bank.npz').to(device) if method in ('Wiener','USRNet-x1') else None
    if method=='RAW':return nn.Identity().to(device),optics,None
    if method=='MOSR':
        from settings import model_config
        from models import Model
        path=PACK/'weights/r152_deployed.pth'
        cp=torch.load(path,map_location='cpu',weights_only=False)
        model=Model(model_config(),PACK).to(device).eval();model.load_state_dict(cp['model'],strict=True)
        optics=model.base.optics
    elif method=='Wiener':
        path=ROOT/'config/wiener_selected.json'
        model=Wiener(read(path)['regularization']).to(device).eval()
    else:
        complete=read(ROOT/'runs'/method/'training_complete.json')
        if complete['state']!='complete':raise RuntimeError('External model has not completed ordinary training')
        path=ROOT/'runs'/method/'selected.pth'
        assert sha(path)==complete['checkpoint_sha256']
        cp=torch.load(path,map_location='cpu',weights_only=False)
        model=make_model(method,checkpoint_training=False).to(device).eval();model.load_state_dict(cp['model'],strict=True)
    return model,optics,sha(path)


def native_forward(method,model,optics,x):
    if method=='RAW':return x
    if method=='MOSR':return model.forward_tiled(x)
    return model(x,None,optics)


def tiled_forward(method,model,optics,x,core=512,halo=192):
    n,c,h,w=x.shape
    if n!=1:raise ValueError('Real inference uses batch=1')
    output=torch.empty_like(x)
    for y in range(0,h,core):
        for xx in range(0,w,core):
            y1=min(h,y+core);x1=min(w,xx+core)
            a=max(0,y-halo);b=min(h,y1+halo);l=max(0,xx-halo);r=min(w,x1+halo)
            value=native_forward(method,model,optics,x[...,a:b,l:r])
            output[...,y:y1,xx:x1]=value[...,y-a:y1-a,xx-l:x1-l]
    return output


def forward_with_mode(method,model,optics,x,mode):
    return tiled_forward(method,model,optics,x,FALLBACK['core'],FALLBACK['halo']) if mode=='memory_fallback_tiles' else native_forward(method,model,optics,x)


def choose_mode(method,model,optics,x):
    if method=='MOSR':return model.forward_tiled(x),'native_MOSR_stage_tiles',None
    try:
        return native_forward(method,model,optics,x),'native_full_frame',None
    except torch.cuda.OutOfMemoryError:
        pass
    gc.collect();torch.cuda.empty_cache()
    return tiled_forward(method,model,optics,x,FALLBACK['core'],FALLBACK['halo']),'memory_fallback_tiles',dict(FALLBACK)
