"""R129 composition: optics -> four shared updates -> original-image output."""
from dataclasses import dataclass
import torch
from torch import nn
from .optics import MeasuredOptics
from .reconstruction import SharedDecoder, refine
from .output_policy import anchored_output

@dataclass
class Details:
    output: torch.Tensor
    latent: torch.Tensor
    optical: dict
    neural: torch.Tensor
    quality: torch.Tensor

class Hybrid(nn.Module):

    def __init__(self, mean_psf, candidates, optical=True, aa=True):
        super().__init__()
        self.optical_enabled = optical
        self.optics = MeasuredOptics(mean_psf, candidates)
        self.prior = SharedDecoder(64, aa)
        self.step_logits = nn.Parameter(torch.zeros(4))
        self.required_halo = 80
        a = torch.arange(-6, 7, dtype=torch.float32)
        k = torch.exp(-0.5 * (a / 2).square())
        k /= k.sum()
        self.register_buffer('anchor_kernel', k)

    def initialize_from_r128(self, state):
        own = self.state_dict()
        for key, value in state.items():
            if key in own and own[key].shape == value.shape:
                own[key] = value.detach().clone()
        own['prior.head.weight'] = state['prior.head.weight'].mean(0, keepdim=True)
        own['prior.head.bias'] = state['prior.head.bias'].mean().reshape(1)
        self.load_state_dict(own)

    def backbone(self, raw, step_observer=None):
        return refine(raw, self.prior, self.step_logits, step_observer)

    def anchor(self, raw, neural):
        return anchored_output(raw, neural, self.anchor_kernel)

    def forward_details(self, raw, trace=False, step_observer=None):
        conditioned, info = self.optics(raw, self.optical_enabled, trace)
        neural, latent = self.backbone(conditioned, step_observer)
        out, q = self.anchor(raw, neural)
        return Details(out, latent, info, neural, q)

    def forward(self, raw):
        return self.forward_details(raw).output
