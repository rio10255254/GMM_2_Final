"""Explicit observation-profile loading; engineering kernels stay unqualified."""
from __future__ import annotations
import json, math
from pathlib import Path
import torch
from .observation import LinearObservation


def observation_from_profile(profile: dict, device='cpu'):
    required = {'calibration_id', 'qualification', 'kernel_convention', 'kernel',
                'sampling_factor', 'gain', 'bias', 'noise_variance'}
    if not required <= profile.keys():
        raise ValueError(f'Missing observation fields: {sorted(required-profile.keys())}')
    if profile['qualification'] == 'qualified_independent_calibration':
        # This prototype has no verified instrument-admission implementation.
        # A user-written qualification flag cannot turn a profile into a certified calibration.
        raise ValueError('Instrument qualification is not implemented; use explicit diagnostic profiles')
    if profile['qualification'] != 'unqualified_diagnostic':
        raise ValueError('Unknown observation qualification')
    k = profile['kernel']
    if k['type'] == 'identity':
        kernel = torch.ones(1, 1)
    elif k['type'] == 'gaussian':
        sigma = float(k['sigma_native_px']) * profile['sampling_factor']
        radius = int(k['radius_native_px']) * profile['sampling_factor']
        if not math.isfinite(sigma) or sigma <= 0 or radius < 1 or radius > 32:
            raise ValueError('Invalid diagnostic Gaussian parameters')
        axis = torch.arange(-radius, radius+1, dtype=torch.float64)
        v = torch.exp(-axis.square()/(2*sigma*sigma));v /= v.sum()
        kernel = (v[:, None]*v[None, :]).float()
    elif k['type'] == 'explicit':
        kernel = torch.tensor(k['values'], dtype=torch.float32)
    else:
        raise ValueError('Unknown kernel family')
    convention = profile['kernel_convention']
    if convention == 'physical_psf':
        # torch conv2d is correlation: flip once, retaining physical centroid.
        kernel = kernel.flip((-2, -1))
    elif convention != 'correlation':
        raise ValueError('Declare physical_psf or correlation kernel convention')
    obs = LinearObservation(kernel, sampling_factor=profile['sampling_factor'],
                            gain=profile['gain'], bias=profile['bias'],
                            noise_variance=profile['noise_variance'],
                            calibration_id=profile['calibration_id'],
                            qualification=profile['qualification']).to(device)
    obs.profile = profile
    return obs


def load_observation(profile_path, device='cpu'):
    return observation_from_profile(json.loads(Path(profile_path).read_text(encoding='utf-8-sig')), device)
