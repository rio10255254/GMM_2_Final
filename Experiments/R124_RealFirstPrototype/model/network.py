"""Local four-step 2D reconstruction with explicit observation corrections.

Only the image prior updates the latent image. Geometry cannot overwrite it.
All calibration and uncertainty metadata remain independent of loss values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

from .observation import LinearObservation


@dataclass(frozen=True)
class PrototypeConfig:
    channels: int = 64
    dilations: tuple[int, ...] = (1, 2, 4, 2)
    iterations: int = 4
    sampling_factor: int = 2
    checkpoint_blocks: bool = False
    maximum_prior_step: float = 0.25
    initial_prior_fraction: float = 0.4
    initial_observation_fraction: float = 0.5
    maximum_sdf_native_px: float = 16.0
    observation_steps: bool = True

    def __post_init__(self):
        object.__setattr__(self, 'dilations', tuple(self.dilations))
        if self.channels < 1 or self.iterations < 1 or self.sampling_factor != 2:
            raise ValueError('Positive model dimensions and the tested 2x sampling contract are required')
        if not self.dilations or any(type(d) is not int or d < 1 for d in self.dilations):
            raise ValueError('Dilations must be positive integers')
        for value in (self.initial_prior_fraction, self.initial_observation_fraction):
            if not 0 < value < 1:
                raise ValueError('Initial step fractions must be strictly between zero and one')
        if not math.isfinite(self.maximum_prior_step) or self.maximum_prior_step <= 0:
            raise ValueError('Invalid prior step bound')
        if not math.isfinite(self.maximum_sdf_native_px) or self.maximum_sdf_native_px <= 0:
            raise ValueError('Invalid distance bound')


class LocalResidualBlock(nn.Module):
    def __init__(self, channels: int, dilation: int):
        super().__init__()
        self.a = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)
        self.b = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)

    def forward(self, x):
        return F.silu(x + 0.15 * self.b(F.silu(self.a(x))))


class SharedPrior(nn.Module):
    def __init__(self, config: PrototypeConfig):
        super().__init__()
        # Current state, original image, current observation residual,
        # fixed raw x/y gradients, calibrated noise and gain.
        self.stem = nn.Conv2d(7, config.channels, 3, padding=1)
        self.blocks = nn.ModuleList(LocalResidualBlock(config.channels, d) for d in config.dilations)
        self.head = nn.Conv2d(config.channels, 1, 3, padding=1)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        self.checkpoint_blocks = config.checkpoint_blocks

    def forward(self, features):
        h = F.silu(self.stem(features))
        for block in self.blocks:
            if self.checkpoint_blocks and self.training and torch.is_grad_enabled():
                h = checkpoint(block, h, use_reentrant=False)
            else:
                h = block(h)
        return torch.tanh(self.head(h))


@dataclass
class ReconstructionDetails:
    output: torch.Tensor
    latent: torch.Tensor
    geometry: dict[str, torch.Tensor]
    traces: list[dict[str, torch.Tensor]]
    metadata: dict[str, Any]


class PrototypeModel(nn.Module):
    def __init__(self, config: PrototypeConfig | dict | None = None,
                 observation: LinearObservation | None = None):
        super().__init__()
        self.config = config if isinstance(config, PrototypeConfig) else PrototypeConfig(**(config or {}))
        c = self.config
        self.observation = observation if observation is not None else LinearObservation(
            torch.ones(1, 1), sampling_factor=2, calibration_id='identity_arithmetic_only',
            qualification='unqualified_diagnostic')
        if self.observation.sampling_factor != c.sampling_factor:
            raise ValueError('Observation and latent sampling factors differ')
        if self.observation.qualification != 'unqualified_diagnostic':
            raise ValueError('R124 has no instrument admission; only explicit unqualified diagnostic observations are supported')
        self.prior = SharedPrior(c)
        self.geometry_head = nn.Sequential(nn.Conv2d(2, 24, 3, padding=1), nn.SiLU(),
                                           nn.Conv2d(24, 3, 3, padding=1))
        nn.init.normal_(self.geometry_head[-1].weight, 0, .01)
        nn.init.zeros_(self.geometry_head[-1].bias)
        logit = lambda p: math.log(p / (1-p))
        self.prior_logits = nn.Parameter(torch.full((c.iterations,), logit(c.initial_prior_fraction)))
        self.observation_logits = nn.Parameter(torch.full((c.iterations,), logit(c.initial_observation_fraction)))
        self.research_status = 'untrained_prototype'

    @property
    def required_halo(self) -> int:
        s = self.config.sampling_factor
        r_f = self.observation.kernel_radius_internal + s - 1
        r_prior = 2 + 2 * sum(self.config.dilations)
        # Residual input expands by F; subsequent F*F correction adds 2F.
        # One raw-gradient pixel, one geometry pixel, one integration margin.
        radius = math.ceil(self.config.iterations * (3*r_f+r_prior) / s) + 3
        return int(math.ceil(radius / 16) * 16)

    @property
    def minimum_halo_px(self):
        return self.required_halo

    @property
    def calibration_qualified(self):
        # A string or small observation residual cannot establish instrument qualification.
        return False

    def config_dict(self):
        return asdict(self.config)

    @staticmethod
    def _validate_input(raw):
        if raw.ndim != 4 or raw.shape[1] != 1 or min(raw.shape) <= 0:
            raise ValueError('Input must be nonempty N x 1 x H x W')
        if not raw.is_floating_point():
            raise ValueError('Input must be normalized floating point')
        if not torch.isfinite(raw).all():
            raise ValueError('Input contains nonfinite values')
        if bool((raw < 0).any()) or bool((raw > 1).any()):
            raise ValueError('Input range must be [0,1]; normalize using camera units, not per-image min/max')

    def forward_details(self, raw: torch.Tensor, trace: bool = False) -> ReconstructionDetails:
        self._validate_input(raw)
        # No AMP is enabled in this prototype. Float64 is retained for numerical tests.
        obs = self.observation
        original = obs.lift(raw)
        state = original
        gx = F.pad(raw[..., 1:] - raw[..., :-1], (0, 1, 0, 0))
        gy = F.pad(raw[..., 1:, :] - raw[..., :-1, :], (0, 0, 0, 1))
        raw_gx, raw_gy = obs.lift(gx), obs.lift(gy)
        noise = torch.ones_like(original) * torch.sqrt(obs.noise_variance.to(raw))
        gain = torch.ones_like(original) * obs.gain.to(raw)
        traces = []
        curvature = obs.curvature_bound()
        curvature = torch.as_tensor(curvature, dtype=raw.dtype, device=raw.device)
        for i in range(self.config.iterations):
            before = state
            predicted = obs(before)
            residual = raw - predicted
            features = torch.cat((before, original, obs.lift(residual), raw_gx, raw_gy, noise, gain), 1)
            prior_step = self.config.maximum_prior_step * torch.sigmoid(self.prior_logits[i])
            correction = prior_step * self.prior(features)
            proposal = before + correction
            at_proposal = obs(proposal)
            step = torch.sigmoid(self.observation_logits[i]) / curvature
            if self.config.observation_steps:
                dc = -step * obs.adjoint((at_proposal-raw) / obs.noise_variance.to(raw))
            else:
                dc = torch.zeros_like(proposal)
            unconstrained = proposal + dc
            state = unconstrained.clamp(0, 1)
            if trace:
                # Preserve graph: callers choose whether to detach/export.
                traces.append({'state_before': before, 'observation_before': predicted,
                               'residual_before': residual, 'prior_correction': correction,
                               'proposal': proposal, 'observation_at_proposal': at_proposal,
                               'observation_correction': dc, 'projection_correction': state-unconstrained,
                               'state_after': state, 'native_output': obs.integrate(state),
                               'step_size': step})
        output = obs.integrate(state)
        g = obs.integrate(self.geometry_head(torch.cat((state, original), 1)))
        geometry = {'boundary_logits': g[:, :1],
                    'sdf': self.config.maximum_sdf_native_px * torch.tanh(g[:, 1:2]),
                    'log_scale': g[:, 2:3].clamp(-5, 5)}
        metadata = {'research_status': self.research_status,
                    'observation_qualification': obs.qualification,
                    'calibration_id': obs.calibration_id,
                    'calibration_qualified': self.calibration_qualified,
                    'uncertainty_calibrated': False,
                    'geometry_is_independent_truth': False,
                    'required_halo_native_px': self.required_halo,
                    'sampling_factor': self.config.sampling_factor,
                    'boundary_convention': 'zero exterior on each finite-domain convolution; retain enough context for tiles',
                    'projection': 'each latent update clamped to normalized optical intensity [0,1], separately traced'}
        return ReconstructionDetails(output, state, geometry, traces, metadata)

    def forward(self, raw):
        return self.forward_details(raw, trace=False).output


def build_model(config=None, observation=None):
    return PrototypeModel(config, observation)
