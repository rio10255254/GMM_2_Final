"""Frozen R148v2 with a small, trainable adaptive Fourier PSF residual."""
from __future__ import annotations
import json,math
from pathlib import Path
import torch
from torch import nn
from base_model import Model as BaseModel
from optical.adaptive_fourier_psf import AdaptiveFourierPSFFusion
PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Model(nn.Module):
 def __init__(self,cfg,root:Path|None=None):
  super().__init__();self.cfg=dict(cfg);root=Path(root) if root else Path(__file__).resolve().parent
  base_cfg=json.loads(Path(PROJECT_ROOT / cfg['base_model_config']).read_text(encoding='utf-8'));self.base=BaseModel(base_cfg,root)
  checkpoint_path=Path(PROJECT_ROOT / cfg['base_checkpoint']);checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=False);self.base.load_state_dict(checkpoint['model'],strict=True)
  for parameter in self.base.parameters():parameter.requires_grad_(False)
  self.base.eval();self.psf_fusion=AdaptiveFourierPSFFusion(cfg,root/cfg['psf_bank'])
  maximum=float(cfg['safe_scale_max']);initial=float(cfg['safe_scale_initial']);fraction=initial/maximum
  self.safe_scale_logit=nn.Parameter(torch.tensor(math.log(fraction/(1-fraction)),dtype=torch.float32));self.register_buffer('deployment_scale',torch.tensor(1.0))
 def train(self,mode=True):
  super().train(mode);self.base.eval();return self
 def safe_scale(self):return float(self.cfg['safe_scale_max'])*torch.sigmoid(self.safe_scale_logit)
 def set_deployment_scale(self,value):
  if not 0<=float(value)<=1:raise ValueError('deployment scale outside [0,1]')
  self.deployment_scale.fill_(float(value))
 def _base_from_prepared(self,x,fixed,cue,context,tiled):
  z=x;r=torch.zeros_like(x)
  for i,stage in enumerate(self.base.stages):
   features=torch.cat((z,x,z-x,self.base.cfg['optical_feature_gain']*cue,*fixed,self.base.cfg['context_gain']*context),1)
   delta=self.base._stage_tiled(stage,features) if tiled else stage(features);eta=self.base.cfg['eta_max']*torch.sigmoid(self.base.step_logits[i]);r=(r+eta*torch.tanh(self.base.cfg['output_logit_gain']*delta)).clamp(-self.base.cfg['r_max'],self.base.cfg['r_max']);z=(x+r).clamp(0,1)
  return z
 def forward(self,x,psf_indices=None,return_parts=False,tiled=False):
  if x.ndim!=4 or x.shape[1]!=1 or x.dtype!=torch.float32 or min(x.shape[-2:])<202:raise ValueError('Expected FP32 N1HW input')
  with torch.no_grad():
   fixed,cue,context=self.base.prepare(x,None if tiled else psf_indices);base_output=self._base_from_prepared(x,fixed,cue,context,tiled)
  anchor,raw_correction=self.psf_fusion(x,context.detach());branch_delta=anchor-x;scale=self.safe_scale()*self.deployment_scale;output=(base_output+scale*branch_delta).clamp(0,1)
  if return_parts:return output,dict(base=base_output,branch_delta=branch_delta,raw_correction=raw_correction,context=context,scale=scale)
  return output
 def forward_tiled(self,x,return_parts=False):return self.forward(x,None,return_parts,tiled=True)
