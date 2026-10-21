"""Four optical cells per native axis; neural prior stays on the2x grid.

The four phase outputs are independent trainable corrections, so this does not
discard the within2x-cell variation exposed by the R125 data audit.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import math,sys
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint
BASE=Path(__file__).resolve().parents[2]/'R124_RealFirstPrototype';sys.path.insert(0,str(BASE))
from model.observation import LinearObservation
from model.network import LocalResidualBlock,ReconstructionDetails

@dataclass(frozen=True)
class PrototypeConfig:
    channels:int=64
    dilations:tuple[int,...]=(1,2,4,2)
    iterations:int=4
    sampling_factor:int=4
    prior_sampling_factor:int=2
    checkpoint_blocks:bool=False
    maximum_prior_step:float=.25
    initial_prior_fraction:float=.4
    initial_observation_fraction:float=.5
    maximum_sdf_native_px:float=16.
    observation_steps:bool=True
    def __post_init__(self):
        object.__setattr__(self,'dilations',tuple(self.dilations))
        if self.sampling_factor!=4 or self.prior_sampling_factor!=2:raise ValueError('Only optical4x/prior2x is implemented')
        if type(self.channels)is not int or self.channels<1 or type(self.iterations)is not int or self.iterations<1:raise ValueError('Invalid model dimensions')
        if not self.dilations or any(type(x)is not int or x<1 for x in self.dilations):raise ValueError('Invalid dilations')
        if not 0<self.initial_prior_fraction<1 or not 0<self.initial_observation_fraction<1:raise ValueError('Invalid fractions')
        if not math.isfinite(self.maximum_prior_step) or self.maximum_prior_step<=0:raise ValueError('Invalid prior bound')

class PhasePrior(nn.Module):
    def __init__(self,c):
        super().__init__();self.stem=nn.Conv2d(7,c.channels,3,padding=1)
        self.blocks=nn.ModuleList(LocalResidualBlock(c.channels,d) for d in c.dilations)
        self.head=nn.Conv2d(c.channels,4,3,padding=1)
        nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias);self.checkpoint_blocks=c.checkpoint_blocks
    def forward(self,x):
        h=F.silu(self.stem(x))
        for b in self.blocks:
            h=checkpoint(b,h,use_reentrant=False) if self.checkpoint_blocks and self.training and torch.is_grad_enabled() else b(h)
        return F.pixel_shuffle(torch.tanh(self.head(h)),2)

class PrototypeModel(nn.Module):
    def __init__(self,config=None,observation=None):
        super().__init__();self.config=config if isinstance(config,PrototypeConfig) else PrototypeConfig(**(config or {}));c=self.config
        self.observation=observation if observation is not None else LinearObservation(torch.ones(1,1),sampling_factor=4,qualification='unqualified_diagnostic',calibration_id='r125_identity_arithmetic')
        if self.observation.sampling_factor!=4 or self.observation.qualification!='unqualified_diagnostic':raise ValueError('Optical4x diagnostic observation required')
        self.prior=PhasePrior(c);self.geometry_head=nn.Sequential(nn.Conv2d(2,24,3,padding=1),nn.SiLU(),nn.Conv2d(24,3,3,padding=1))
        nn.init.normal_(self.geometry_head[-1].weight,0,.01);nn.init.zeros_(self.geometry_head[-1].bias)
        logit=lambda p:math.log(p/(1-p));self.prior_logits=nn.Parameter(torch.full((c.iterations,),logit(c.initial_prior_fraction)));self.observation_logits=nn.Parameter(torch.full((c.iterations,),logit(c.initial_observation_fraction)))
        self.research_status='untrained_repaired_representation'
    def config_dict(self):return asdict(self.config)
    @property
    def calibration_qualified(self):return False
    @property
    def required_halo(self):
        s=4;rf=self.observation.kernel_radius_internal+s-1
        # Prior radius20 on2x =40 on4x, plus average-pool support1.
        prior=2*(2+2*sum(self.config.dilations))+1
        radius=math.ceil(self.config.iterations*(3*rf+prior)/s)+3
        return math.ceil(radius/16)*16
    @property
    def minimum_halo_px(self):return self.required_halo
    @staticmethod
    def _validate_input(raw):
        if raw.ndim!=4 or raw.shape[1]!=1 or min(raw.shape)<1 or not raw.is_floating_point():raise ValueError('Expected normalized nonemptyN1HW')
        if not torch.isfinite(raw).all() or (raw<0).any() or (raw>1).any():raise ValueError('Invalid camera intensity')
    def forward_details(self,raw,trace=False):
        self._validate_input(raw);obs=self.observation
        if obs.sampling_factor!=4:raise ValueError('Wrong per-scene observation sampling')
        lift2=lambda x:x.repeat_interleave(2,-2).repeat_interleave(2,-1)
        original=obs.lift(raw);original2=lift2(raw);state=original
        gx=lift2(F.pad(raw[...,1:]-raw[...,:-1],(0,1,0,0)));gy=lift2(F.pad(raw[...,1:,:]-raw[...,:-1,:],(0,0,0,1)))
        noise=torch.ones_like(original2)*obs.noise_variance.sqrt();gain=torch.ones_like(original2)*obs.gain
        traces=[];curvature=obs.curvature_bound()
        for i in range(self.config.iterations):
            before=state;pred=obs(before);residual=raw-pred
            features=torch.cat((F.avg_pool2d(before,2),original2,lift2(residual),gx,gy,noise,gain),1)
            correction=self.config.maximum_prior_step*torch.sigmoid(self.prior_logits[i])*self.prior(features)
            proposal=before+correction;at_proposal=obs(proposal);eta=torch.sigmoid(self.observation_logits[i])/curvature
            dc=-eta*obs.adjoint((at_proposal-raw)/obs.noise_variance) if self.config.observation_steps else torch.zeros_like(proposal)
            unconstrained=proposal+dc;state=unconstrained.clamp(0,1)
            if trace:traces.append({'state_before':before,'observation_before':pred,'residual_before':residual,'prior_correction':correction,'proposal':proposal,'observation_at_proposal':at_proposal,'observation_correction':dc,'projection_correction':state-unconstrained,'state_after':state,'native_output':obs.integrate(state),'step_size':eta})
        output=obs.integrate(state);g=F.avg_pool2d(self.geometry_head(torch.cat((F.avg_pool2d(state,2),original2),1)),2)
        geometry={'boundary_logits':g[:,:1],'sdf':self.config.maximum_sdf_native_px*torch.tanh(g[:,1:2]),'log_scale':g[:,2:3].clamp(-5,5)}
        meta={'research_status':self.research_status,'observation_qualification':obs.qualification,'calibration_id':obs.calibration_id,'calibration_qualified':False,'uncertainty_calibrated':False,'geometry_is_independent_truth':False,'required_halo_native_px':self.required_halo,'sampling_factor':4,'prior_sampling_factor':2,'boundary_convention':'zero exterior finite convolutions, full context required','projection':'[0,1] intensity projection separately traced','representation_repair':'four independent subcell phase corrections per2xprior site'}
        return ReconstructionDetails(output,state,geometry,traces,meta)
    def forward(self,raw):return self.forward_details(raw).output
def build_model(config=None,observation=None):return PrototypeModel(config,observation)
