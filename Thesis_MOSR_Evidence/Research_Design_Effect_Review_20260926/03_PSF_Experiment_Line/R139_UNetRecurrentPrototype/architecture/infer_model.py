"""The final R139 model is always the fixed last training update."""
from pathlib import Path
import torch
from model import Model
from utils import ROOT,model_config,sha

def load_own_model(path,device='cuda'):
    checkpoint=torch.load(path,map_location='cpu',weights_only=False)
    if checkpoint.get('model_name')!='R139-UNetRecurrent' or checkpoint.get('initialization')!='scratch' or checkpoint.get('step')!=8192:
        raise ValueError('Expected the fixed scratch R139 final checkpoint')
    model=Model(model_config(),ROOT)
    model.load_state_dict(checkpoint['model'],strict=True)
    return model.to(device).eval(),checkpoint

def predict_tensor(model,x,mode='full'):
    if mode!='full':raise ValueError('This U-Net PSF model has no validated tile equivalent')
    return model(x)
