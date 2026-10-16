"""R109 plus a bounded monotonic visibility/contrast parameter."""
from __future__ import annotations
from dataclasses import dataclass
import sys
from pathlib import Path
import torch
import torch.nn.functional as F
from torch import nn
R109=Path(r'D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch');sys.path.insert(0,str(R109/'model'));import r109_model as base
@dataclass
class VisibilityDetails:
 output:torch.Tensor;delta:torch.Tensor;boundary_logits:torch.Tensor;boundary:torch.Tensor;necessity:torch.Tensor;support:torch.Tensor;width_gain:torch.Tensor;normal_shift:torch.Tensor;flow:torch.Tensor;visibility_gain:torch.Tensor
class VisibilityModel(base.R109Model):
 def __init__(self):
  super().__init__();channels=int(base.MCFG['base_channels']);self.visibility_head=nn.Conv2d(channels,1,1);nn.init.zeros_(self.visibility_head.weight);nn.init.constant_(self.visibility_head.bias,-4)
 def renderer_parameters(self):return [*super().renderer_parameters(),*self.visibility_head.parameters()]
 def _forward_aligned(self,x):
  raw=x.clamp(0,1);cues=self.cues(raw);detector=self.detector_tower(F.silu(self.detector_stem(cues['features'])));renderer=self.renderer_tower(F.silu(self.renderer_stem(cues['features'])))
  with torch.autocast(device_type=x.device.type,enabled=False):
   detector32=torch.tanh(detector.float());renderer32=torch.tanh(renderer.float());boundary_logits=self.boundary_head(detector32);boundary=torch.sigmoid(boundary_logits);necessity=torch.ones_like(boundary);minimum=float(base.MCFG['minimum_width_gain']);maximum=float(base.MCFG['maximum_width_gain']);width_gain=minimum+(maximum-minimum)*torch.sigmoid(self.width_head(renderer32));normal_shift=float(base.MCFG['maximum_normal_shift_px'])*torch.tanh(self.shift_head(renderer32));visibility_gain=1+torch.sigmoid(self.visibility_head(renderer32))
   magnitude=cues['magnitude'].float();local_scale=cues['local_scale'].float();source_support=((magnitude/(local_scale+2/255)-.05)/1.10).clamp(0,1);support=torch.maximum(source_support,.85*F.max_pool2d(boundary,9,1,4)).clamp(0,1);smooth_gx,smooth_gy=base.gradients(cues['blurred'][1].float());smooth_magnitude=torch.sqrt(smooth_gx.square()+smooth_gy.square()+1e-8);normal_x,normal_y=smooth_gx/smooth_magnitude,smooth_gy/smooth_magnitude;flow=torch.cat([normal_shift*normal_x,normal_shift*normal_y],1);warped=self.warp(raw.float(),flow*support);window=int(base.MCFG['local_range_window_px']);radius=window//2;local_max=F.max_pool2d(warped,window,1,radius);local_min=-F.max_pool2d(-warped,window,1,radius);dynamic=(local_max-local_min).clamp_min(2/255);unit=((warped-local_min)/dynamic).clamp(1e-3,1-1e-3);visible_unit=(.5+visibility_gain*(unit-.5)).clamp(1e-3,1-1e-3);corrected=torch.sigmoid(width_gain*(torch.log(visible_unit)-torch.log1p(-visible_unit)));proposal=local_min+dynamic*corrected;output=(raw.float()+support*(proposal-raw.float())).clamp(0,1);delta=output-raw.float()
  return VisibilityDetails(output,delta,boundary_logits,boundary,necessity,support,width_gain,normal_shift,flow,visibility_gain)
 def forward_details(self,x):
  h,w=x.shape[-2:];pad_h,pad_w=(-h)%self.alignment_multiple,(-w)%self.alignment_multiple
  if pad_h or pad_w:
   padded=F.pad(x,(0,pad_w,0,pad_h),mode='reflect' if h>pad_h and w>pad_w else 'replicate');details=self._forward_aligned(padded);return VisibilityDetails(*[getattr(details,name)[...,:h,:w] for name in details.__dataclass_fields__])
  return self._forward_aligned(x)
def build_model():return VisibilityModel()
