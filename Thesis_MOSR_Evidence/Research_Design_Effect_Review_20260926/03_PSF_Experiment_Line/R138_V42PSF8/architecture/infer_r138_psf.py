import torch
from utils import config
from model_r138_psf import Model

def predict_tensor(model,x,mode='full',core=512,halo=96):
 if mode!='full':raise ValueError('V42 global module: full-image mode required')
 return model(x)

def load_own_model(path,device='cpu'):
 p=torch.load(path,map_location='cpu',weights_only=False)
 if p.get('model_name')!='R138-V42PSF8' or p.get('initialization')!='scratch' or p.get('optical_mode')!='v42_select8':raise ValueError('Not the expected R138 checkpoint')
 m=Model(config()['model']);m.load_state_dict(p['model'],strict=True);return m.to(device).eval(),p
