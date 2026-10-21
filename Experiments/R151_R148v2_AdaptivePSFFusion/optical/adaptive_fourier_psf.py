"""Paper-aligned adaptive Fourier PSF fusion with a bounded residual output.

The weighted sum is applied to frequency-domain candidate filters before the
inverse transform. Because the inverse transform is linear, this is equivalent
to inverse-transforming every candidate and then taking the same weighted sum,
while using much less memory.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def reflect_pad(x: torch.Tensor, width: int) -> torch.Tensor:
    if width == 0:
        return x
    if min(x.shape[-2:]) <= width:
        raise ValueError("Image is smaller than the PSF support")
    x = torch.cat((x[..., 1:width+1].flip(-1), x, x[..., -width-1:-1].flip(-1)), -1)
    return torch.cat((x[..., 1:width+1, :].flip(-2), x, x[..., -width-1:-1, :].flip(-2)), -2)


class WeightEstimator(nn.Module):
    def __init__(self, count: int, hidden: int, input_channels: int = 1, raw_input: bool = True):
        super().__init__()
        self.raw_input = bool(raw_input)
        feature_channels = 4 if self.raw_input else int(input_channels)
        self.features = nn.Sequential(
            nn.Conv2d(feature_channels, hidden, 5, padding=2),
            nn.SiLU(),
            nn.Conv2d(hidden, hidden, 3, padding=1, groups=hidden),
            nn.SiLU(),
            nn.Conv2d(hidden, hidden, 1),
            nn.SiLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.spectrum_bins = 16
        if self.raw_input:
            self.output = nn.Conv2d(hidden, count, 1)
        else:
            self.spectrum = nn.Sequential(
                nn.Linear(self.spectrum_bins, hidden), nn.SiLU(),
                nn.Linear(hidden, hidden), nn.SiLU(),
            )
            self.output = nn.Linear(2*hidden, count)
        nn.init.normal_(self.output.weight, mean=0.0, std=0.01)
        nn.init.zeros_(self.output.bias)

    @staticmethod
    def input_features(x: torch.Tensor) -> torch.Tensor:
        p = reflect_pad(x, 1)
        dx = (p[..., 1:-1, 2:] - p[..., 1:-1, :-2]) * 0.5
        dy = (p[..., 2:, 1:-1] - p[..., :-2, 1:-1]) * 0.5
        lap = p[..., 1:-1, 2:] + p[..., 1:-1, :-2] + p[..., 2:, 1:-1] + p[..., :-2, 1:-1] - 4 * x
        local = x - F.avg_pool2d(reflect_pad(x, 2), 5, stride=1)
        magnitude = torch.sqrt(dx.square() + dy.square() + 1e-8)
        return torch.cat((x, magnitude, lap, local), 1)

    def spectrum_features(self, image: torch.Tensor) -> torch.Tensor:
        centered = image.float() - image.float().mean((-2,-1), keepdim=True)
        power = torch.log1p(torch.fft.rfft2(centered).abs().square())[:,0]
        height, half_width = power.shape[-2:]
        fy = torch.fft.fftfreq(height, device=image.device).unsqueeze(1)
        fx = torch.fft.rfftfreq((half_width-1)*2, device=image.device).unsqueeze(0)
        radius = torch.sqrt(fy.square()+fx.square()).clamp_max(0.5)
        edges = torch.linspace(0.0, 0.5, self.spectrum_bins+1, device=image.device)
        values = []
        for i in range(self.spectrum_bins):
            high = edges[i+1] + (1e-6 if i+1 == self.spectrum_bins else 0.0)
            mask = (radius >= edges[i]) & (radius < high)
            values.append(power[:,mask].mean(1))
        value = torch.stack(values,1)
        return (value-value.mean(1,keepdim=True))/torch.sqrt(value.var(1,keepdim=True,unbiased=False)+1e-6)

    def forward(self, x: torch.Tensor, image: torch.Tensor | None = None) -> torch.Tensor:
        value = self.input_features(x) if self.raw_input else x
        if value.shape[1] != self.features[0].in_channels:
            raise ValueError("Unexpected selector feature channels")
        spatial = self.features(value).flatten(1)
        if self.raw_input:
            return self.output(spatial[...,None,None]).flatten(1)
        if image is None:
            raise ValueError("Context selector also requires the observed image")
        spectral = self.spectrum(self.spectrum_features(image))
        return self.output(torch.cat((spatial,spectral),1))


class AdaptiveFourierPSFFusion(nn.Module):
    def __init__(self, cfg: dict, bank_path: str | Path):
        super().__init__()
        path = Path(bank_path)
        with np.load(path, allow_pickle=False) as z:
            bank = z["all_kernels"].astype(np.float64)
        expected = (int(cfg["psf_count"]), 101, 101)
        if bank.shape != expected or not np.isfinite(bank).all() or (bank < 0).any():
            raise ValueError(f"Expected nonnegative finite PSF bank {expected}")
        bank /= bank.sum((1, 2), keepdims=True)
        self.register_buffer("bank", torch.from_numpy(bank.astype(np.float32))[:, None])
        yy, xx = np.mgrid[-50:51, -50:51]
        rr = xx*xx + yy*yy
        descriptors = np.stack([
            (bank*rr).sum((1,2)),
            (bank*rr*rr).sum((1,2)),
            bank[:,rr >= 15*15].sum(1),
        ], 1)
        descriptor_mean = descriptors.mean(0, keepdims=True)
        descriptor_std = descriptors.std(0, keepdims=True)
        descriptors = (descriptors-descriptor_mean)/np.maximum(descriptor_std, 1e-12)
        self.register_buffer("psf_descriptors", torch.from_numpy(descriptors.astype(np.float32)))
        self.count = expected[0]
        self.temperature = float(cfg["selector_temperature"])
        self.regularization = float(cfg["psf_regularization"])
        self.lowfreq_ratio = float(cfg["psf_lowfreq_ratio"])
        self.max_inverse_gain = float(cfg["psf_max_inverse_gain"])
        self.correction_clip = float(cfg["psf_correction_clip"])
        self.beta_min = float(cfg["psf_beta_min"])
        self.beta_max = float(cfg["psf_beta_max"])
        beta_initial = float(cfg["psf_beta_initial"])
        if not 0 <= self.beta_min < beta_initial < self.beta_max:
            raise ValueError("Require beta_min < beta_initial < beta_max")
        fraction = (beta_initial - self.beta_min) / (self.beta_max - self.beta_min)
        self.beta_logit = nn.Parameter(torch.tensor(math.log(fraction / (1 - fraction)), dtype=torch.float32))
        self.estimator = WeightEstimator(
            self.count,
            int(cfg["selector_hidden_channels"]),
            int(cfg["selector_input_channels"]),
            raw_input=False,
        )
        self._transfer_cache: dict[tuple[int, int, str], torch.Tensor] = {}
        self.last_logits: torch.Tensor | None = None
        self.last_weights: torch.Tensor | None = None
        self.last_entropy: torch.Tensor | None = None
        self.last_beta: torch.Tensor | None = None

    def _apply(self, fn):
        self._transfer_cache.clear()
        return super()._apply(fn)

    def beta_value(self) -> torch.Tensor:
        return self.beta_min + (self.beta_max - self.beta_min) * torch.sigmoid(self.beta_logit)

    def select(self, features: torch.Tensor, image: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        logits = self.estimator(features, image)
        weights = torch.softmax(logits / max(self.temperature, 1e-6), dim=1)
        self.last_logits = logits
        self.last_weights = weights.detach()
        self.last_entropy = -(weights * torch.log(weights.clamp_min(1e-8))).sum(1).mean().detach()
        return logits, weights

    def _transfer_bank(self, height: int, width: int, device: torch.device) -> torch.Tensor:
        key = (height, width, str(device))
        cached = self._transfer_cache.get(key)
        if cached is not None:
            return cached
        # Create an ordinary constant tensor even if the first call occurs
        # inside inference_mode; later training must backpropagate through the
        # mixture weights that multiply this cached bank.
        with torch.inference_mode(False), torch.no_grad():
            kernel = self.bank.to(device=device, dtype=torch.float32)
            top = (height - 101) // 2
            left = (width - 101) // 2
            placed = F.pad(kernel, (left, width-101-left, top, height-101-top))
            origin = torch.roll(placed, (-(top+50), -(left+50)), (-2, -1))
            transfer = torch.fft.rfft2(origin)[:, 0]
            inverse = transfer.conj() / (transfer.abs().square() + self.regularization)
            fy = torch.fft.fftfreq(height, device=device).unsqueeze(1)
            fx = torch.fft.rfftfreq(width, device=device).unsqueeze(0)
            radius = torch.sqrt(fy.square() + fx.square()) / 0.5
            mask = (radius <= self.lowfreq_ratio).to(torch.float32)
            filtered = 1.0 + mask[None] * (inverse - 1.0)
            gain = filtered.abs().clamp_min(1e-8)
            filtered = filtered * torch.clamp(self.max_inverse_gain / gain, max=1.0)
        self._transfer_cache[key] = filtered
        return filtered

    def forward(self, x: torch.Tensor, selector_features: torch.Tensor, forced_indices: torch.Tensor | None = None):
        if x.ndim != 4 or x.shape[1] != 1 or x.dtype != torch.float32:
            raise ValueError("Expected FP32 N1HW input")
        _, weights = self.select(selector_features, x)
        if forced_indices is not None:
            if forced_indices.shape != (x.shape[0],) or ((forced_indices < 0) | (forced_indices >= self.count)).any():
                raise ValueError("Invalid forced PSF indices")
            weights = F.one_hot(forced_indices.long(), self.count).to(dtype=x.dtype)
        padded = reflect_pad(x, 50)
        height, width = padded.shape[-2:]
        bank = self._transfer_bank(height, width, x.device)
        mixed = torch.einsum("bn,nhw->bhw", weights.to(bank.dtype), bank)
        restored = torch.fft.irfft2(torch.fft.rfft2(padded.float()) * mixed[:, None], s=(height, width))
        restored = restored[..., 50:-50, 50:-50]
        correction = (restored - x.float()).clamp(-self.correction_clip, self.correction_clip)
        beta = self.beta_value()
        anchor = (x.float() + beta * correction).clamp(0.0, 1.0)
        self.last_beta = beta.detach()
        return anchor.to(x.dtype), correction.to(x.dtype)

    def selector_loss(self, labels: torch.Tensor) -> torch.Tensor:
        if self.last_logits is None:
            raise RuntimeError("Run the fusion module before requesting selector loss")
        valid = (labels >= 0) & (labels < self.count)
        if not valid.any():
            return self.last_logits.sum() * 0.0
        return F.cross_entropy(self.last_logits[valid], labels[valid].long())

    def selector_accuracy(self, labels: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if self.last_logits is None:
            raise RuntimeError("Run the fusion module before requesting selector accuracy")
        valid = (labels >= 0) & (labels < self.count)
        if not valid.any():
            zero = self.last_logits.sum() * 0.0
            return zero, zero
        prediction = self.last_logits[valid].argmax(1)
        return (prediction == labels[valid]).float().mean(), valid.sum()

    def descriptor_loss(self, labels: torch.Tensor) -> torch.Tensor:
        if self.last_logits is None:
            raise RuntimeError("Run the fusion module before requesting descriptor loss")
        valid = (labels >= 0) & (labels < self.count)
        if not valid.any():
            return self.last_logits.sum() * 0.0
        weights = torch.softmax(self.last_logits[valid] / max(self.temperature, 1e-6), dim=1)
        descriptors = self.psf_descriptors.to(weights.device)
        predicted = weights @ descriptors
        target = descriptors[labels[valid].long()]
        return F.mse_loss(predicted, target)
