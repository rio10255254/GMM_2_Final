"""R118: geometric normals, continuous monotone rendering, trainable detail.

All modules are local. Geometry stays trainable after its warmup. Source
evidence is input, not an unconditional correction floor. There is no
reflection projection, forced zero-mean residual, or prescribed width target.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import torch
from torch import nn
import torch.nn.functional as F
from model.ops import LocalCues,LocalTower,warp_local,warp_many

ROOT=Path(__file__).resolve().parents[1]

def geometric_normals(sdf):
    gx=F.pad((sdf[...,2:]-sdf[...,:-2])*.5,(1,1,0,0),mode='replicate')
    gy=F.pad((sdf[...,2:,:]-sdf[...,:-2,:])*.5,(0,0,1,1),mode='replicate')
    magnitude=torch.sqrt(gx.square()+gy.square()+1e-8)
    return gx/magnitude,gy/magnitude

def continuous_width(anchor,gain,sdf,normals,window=21):
    """Neutral continuous at gain=1, including local plateaus.

    Compute the correction on a 2x grid; integrate its residual to native
    pixels so neutral gain preserves the original samples exactly.
    """
    radius=window//2
    # All pixels on a straight edge use the same geometric center/endpoints.
    # Sliding local min/max endpoints are not spatially monotone and failed
    # the clean-edge regression despite an individually monotone intensity map.
    center=-sdf*normals
    offsets=anchor.new_tensor([-radius,radius]).view(1,2,1,1,1)
    endpoints=warp_many(anchor,center[:,None]+offsets*normals[:,None])[:,:,0]
    lo=endpoints.amin(1,keepdim=True)
    hi=endpoints.amax(1,keepdim=True)
    dynamic=(hi-lo).clamp_min(1/255)
    size=(anchor.shape[-2]*2,anchor.shape[-1]*2)
    up=lambda t:F.interpolate(t,size=size,mode='bilinear',align_corners=False)
    a,l,r,g=up(anchor),up(lo),up(dynamic),up(gain)
    unit=((a-l)/r).clamp(1e-4,1-1e-4)
    logits=torch.log(unit)-torch.log1p(-unit)
    # Subtract the same neutral evaluation, not a gain==1 special branch.
    correction=r*(torch.sigmoid(g*logits)-torch.sigmoid(logits))
    return anchor+F.avg_pool2d(correction,2)

@dataclass
class Details:
    output:torch.Tensor
    sdf:torch.Tensor
    boundary_logits:torch.Tensor
    normals:torch.Tensor
    shift:torch.Tensor
    flow:torch.Tensor
    width_gain:torch.Tensor
    geometry_output:torch.Tensor
    detail:torch.Tensor

class Model(nn.Module):
    def __init__(self,config=None):
        super().__init__()
        self.config=config or json.loads((ROOT/'config/experiment.json').read_text())['model']
        c=self.config;self.minimum_halo_px=c['minimum_halo_px'];self.alignment_multiple=c['alignment_multiple']
        self.cues=LocalCues(c['blur_scales_px'])
        self.geometry=LocalTower(self.cues.channels,c['base_channels'],c['detector_dilations'])
        self.geometry_head=nn.Conv2d(c['base_channels'],2,1)
        self.action=LocalTower(self.cues.channels+2,c['action_channels'],c['action_dilations'])
        self.action_head=nn.Conv2d(c['action_channels'],2,1)
        self.detail_tower=LocalTower(self.cues.channels+2,c['detail_channels'],c['detail_dilations'])
        self.detail_head=nn.Conv2d(c['detail_channels'],1,1)
        for h in (self.geometry_head,self.action_head,self.detail_head):
            nn.init.zeros_(h.weight);nn.init.zeros_(h.bias)
        with torch.no_grad():self.geometry_head.weight[0].normal_(0,.01)
        nn.init.constant_(self.geometry_head.bias[1],-2)
        self.detail_enabled=True

    def groups(self):
        return {
            'geometry':[*self.geometry.parameters(),*self.geometry_head.parameters()],
            'action':[*self.action.parameters(),*self.action_head.parameters()],
            'detail':[*self.detail_tower.parameters(),*self.detail_head.parameters()]
        }

    def forward_details(self,x):
        raw=x.float().clamp(0,1)
        features=self.cues(raw)['features']
        geometry=self.geometry_head(self.geometry(features)).float()
        sdf=self.config['maximum_sdf_px']*torch.tanh(geometry[:,:1])
        boundary_logits=geometry[:,1:2]
        nx,ny=geometric_normals(sdf)
        normal=torch.cat((nx,ny),1)
        context=torch.cat((features,sdf/self.config['maximum_sdf_px'],torch.sigmoid(boundary_logits)),1)
        act=self.action_head(self.action(context)).float()
        shift=self.config['maximum_normal_shift_px']*torch.tanh(act[:,:1])
        flow=normal*shift
        anchor=warp_local(raw,flow)
        # Positive sharpening amount starts at neutral and stays continuous.
        amount=torch.tanh(act[:,1:2])
        bounded=amount.clamp(0,1)
        amount=amount+(bounded-amount).detach()
        gain=1+(self.config['maximum_width_gain']-1)*amount
        base=continuous_width(anchor,gain,sdf,normal,self.config['local_range_window'])
        detail_logits=self.detail_head(self.detail_tower(context)).float()
        detail=(self.config['maximum_detail_gray']/255)*torch.tanh(detail_logits)
        if not self.detail_enabled:detail=detail*0
        output=(base+detail).clamp(0,1)
        return Details(output,sdf,boundary_logits,normal,shift,flow,gain,base,detail)

    def forward(self,x):return self.forward_details(x).output

def build_model(config=None):return Model(config)
