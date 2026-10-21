"""R109 tile-safe midpoint/width-factorized single-image model."""
from __future__ import annotations
from dataclasses import dataclass
import json,math
from pathlib import Path
import torch
from torch import nn
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[1];CONFIG=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'));MCFG=CONFIG['model']
def safe_pad(x,amount):return F.pad(x,(amount,amount,amount,amount),mode='reflect' if min(x.shape[-2:])>amount else 'replicate')
class Blur(nn.Module):
 def __init__(self,sigma):
  super().__init__();radius=max(1,int(math.ceil(3*float(sigma))));axis=torch.arange(-radius,radius+1,dtype=torch.float32);row=torch.exp(-.5*(axis/float(sigma))**2);row/=row.sum();self.register_buffer('horizontal',row.view(1,1,1,-1));self.register_buffer('vertical',row.view(1,1,-1,1));self.radius=radius
 def forward(self,x):
  mode='reflect' if min(x.shape[-2:])>self.radius else 'replicate';value=F.conv2d(F.pad(x,(self.radius,self.radius,0,0),mode=mode),self.horizontal.to(x.dtype));return F.conv2d(F.pad(value,(0,0,self.radius,self.radius),mode=mode),self.vertical.to(x.dtype))
class Residual(nn.Module):
 def __init__(self,channels,dilation):super().__init__();self.a=nn.Conv2d(channels,channels,3,padding=dilation,dilation=dilation);self.b=nn.Conv2d(channels,channels,3,padding=dilation,dilation=dilation)
 def forward(self,x):return F.silu(x+.15*self.b(F.silu(self.a(x))))
def gradients(x):return F.pad(x[...,1:]-x[...,:-1],(0,1,0,0)),F.pad(x[...,1:,:]-x[...,:-1,:],(0,0,0,1))
class LocalCues(nn.Module):
 channels=15
 def __init__(self):super().__init__();self.blurs=nn.ModuleList([Blur(value) for value in MCFG['blur_scales_px']]);self.context=Blur(max(MCFG['blur_scales_px']))
 def forward(self,x):
  blurred=[layer(x) for layer in self.blurs];highpasses=[x-value for value in blurred];gx,gy=gradients(x);magnitude=torch.sqrt(gx.square()+gy.square()+1e-8);local_mean=blurred[-1];local_scale=torch.sqrt(self.context((x-local_mean).square())+(2/255)**2);normalized=((x-local_mean)/(local_scale+2/255)).clamp(-4,4);features=torch.cat([x,*blurred,*highpasses,gx,gy,magnitude,local_mean,local_scale,normalized],1);return {'features':features,'blurred':blurred,'magnitude':magnitude,'local_scale':local_scale}
@dataclass
class Details:
 output:torch.Tensor
 delta:torch.Tensor
 boundary_logits:torch.Tensor
 boundary:torch.Tensor
 necessity:torch.Tensor
 support:torch.Tensor
 width_gain:torch.Tensor
 normal_shift:torch.Tensor
 flow:torch.Tensor
class R109Model(nn.Module):
 alignment_multiple=int(MCFG['alignment_multiple']);minimum_halo_px=int(MCFG['minimum_halo_px'])
 def __init__(self):
  super().__init__();base=int(MCFG['base_channels']);self.cues=LocalCues();self.detector_stem=nn.Conv2d(LocalCues.channels,base,3,padding=1);self.detector_tower=nn.Sequential(*[Residual(base,int(d)) for d in MCFG['dilations']]);self.renderer_stem=nn.Conv2d(LocalCues.channels,base,3,padding=1);self.renderer_tower=nn.Sequential(*[Residual(base,int(d)) for d in MCFG['dilations']]);self.boundary_head=nn.Conv2d(base,1,1);self.width_head=nn.Conv2d(base,1,1);self.shift_head=nn.Conv2d(base,1,1);self._initialize()
 def _initialize(self):
  for head in (self.boundary_head,self.width_head,self.shift_head):nn.init.zeros_(head.weight);nn.init.zeros_(head.bias)
  nn.init.constant_(self.boundary_head.bias,-2);nn.init.constant_(self.width_head.bias,-4)
 def detector_parameters(self):return [*self.detector_stem.parameters(),*self.detector_tower.parameters(),*self.boundary_head.parameters()]
 def renderer_parameters(self):return [*self.renderer_stem.parameters(),*self.renderer_tower.parameters(),*self.width_head.parameters(),*self.shift_head.parameters()]
 @staticmethod
 def warp(x,flow):
  n,_c,h,w=x.shape;yy,xx=torch.meshgrid(torch.linspace(-1,1,h,device=x.device,dtype=x.dtype),torch.linspace(-1,1,w,device=x.device,dtype=x.dtype),indexing='ij');grid=torch.stack([xx,yy],-1).unsqueeze(0).expand(n,-1,-1,-1).clone();grid[...,0]+=flow[:,0]*(2/max(w-1,1));grid[...,1]+=flow[:,1]*(2/max(h-1,1));return F.grid_sample(x,grid,mode='bilinear',padding_mode='reflection',align_corners=True)
 def _forward_aligned(self,x):
  raw=x.clamp(0,1);cues=self.cues(raw);detector=self.detector_tower(F.silu(self.detector_stem(cues['features'])));renderer=self.renderer_tower(F.silu(self.renderer_stem(cues['features'])))
  with torch.autocast(device_type=x.device.type,enabled=False):
   detector32=torch.tanh(detector.float());renderer32=torch.tanh(renderer.float());boundary_logits=self.boundary_head(detector32);boundary=torch.sigmoid(boundary_logits);necessity=torch.ones_like(boundary);minimum=float(MCFG['minimum_width_gain']);maximum=float(MCFG['maximum_width_gain']);width_gain=minimum+(maximum-minimum)*torch.sigmoid(self.width_head(renderer32));normal_shift=float(MCFG['maximum_normal_shift_px'])*torch.tanh(self.shift_head(renderer32))
   magnitude=cues['magnitude'].float();local_scale=cues['local_scale'].float();source_support=((magnitude/(local_scale+2/255)-.05)/1.10).clamp(0,1);support=torch.maximum(source_support,.85*F.max_pool2d(boundary,9,1,4)).clamp(0,1);effective=support;smooth_gx,smooth_gy=gradients(cues['blurred'][1].float());smooth_magnitude=torch.sqrt(smooth_gx.square()+smooth_gy.square()+1e-8);normal_x,normal_y=smooth_gx/smooth_magnitude,smooth_gy/smooth_magnitude;flow=torch.cat([normal_shift*normal_x,normal_shift*normal_y],1);warped=self.warp(raw.float(),flow*effective);window=int(MCFG['local_range_window_px']);radius=window//2;local_max=F.max_pool2d(warped,window,1,radius);local_min=-F.max_pool2d(-warped,window,1,radius);dynamic=(local_max-local_min).clamp_min(2/255);unit=((warped-local_min)/dynamic).clamp(1e-3,1-1e-3);corrected=torch.sigmoid(width_gain*(torch.log(unit)-torch.log1p(-unit)));proposal=local_min+dynamic*corrected;output=(raw.float()+effective*(proposal-raw.float())).clamp(0,1);delta=output-raw.float()
  return Details(output,delta,boundary_logits,boundary,necessity,support,width_gain,normal_shift,flow)
 def forward_details(self,x):
  h,w=x.shape[-2:];pad_h,pad_w=(-h)%self.alignment_multiple,(-w)%self.alignment_multiple
  if pad_h or pad_w:
   padded=F.pad(x,(0,pad_w,0,pad_h),mode='reflect' if h>pad_h and w>pad_w else 'replicate');details=self._forward_aligned(padded);return Details(*[getattr(details,name)[...,:h,:w] for name in details.__dataclass_fields__])
  return self._forward_aligned(x)
 def forward(self,x):return self.forward_details(x).output
def build_model():return R109Model()
def count_parameters(model):return sum(parameter.numel() for parameter in model.parameters())
