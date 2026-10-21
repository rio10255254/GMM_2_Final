"""R107 single-image fixed-center local edge operator.

The network predicts local parameters only.  It never emits a free image
residual and never predicts a global contour for rendering.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


class SeparableBinomialBlur(nn.Module):
    def __init__(self, channels: int, size: int):
        super().__init__()
        row = torch.tensor([math.comb(size - 1, index) for index in range(size)], dtype=torch.float32)
        row /= row.sum()
        self.channels = int(channels)
        self.size = int(size)
        self.register_buffer("horizontal", row.view(1, 1, 1, size).repeat(channels, 1, 1, 1))
        self.register_buffer("vertical", row.view(1, 1, size, 1).repeat(channels, 1, 1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        radius = self.size // 2
        mode = "reflect" if x.shape[-2] > radius and x.shape[-1] > radius else "replicate"
        value = F.conv2d(F.pad(x, (radius, radius, 0, 0), mode=mode), self.horizontal.to(dtype=x.dtype), groups=self.channels)
        return F.conv2d(F.pad(value, (0, 0, radius, radius), mode=mode), self.vertical.to(dtype=x.dtype), groups=self.channels)


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, dilation: int = 1, activate: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=dilation, dilation=dilation)
        self.act = nn.SiLU() if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.conv(x))


class ResBlock(nn.Module):
    def __init__(self, channels: int, dilation: int = 1):
        super().__init__()
        self.a = ConvBlock(channels, channels, dilation=dilation)
        self.b = ConvBlock(channels, channels, dilation=dilation, activate=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.b(self.a(x)))


class LocalEvidence(nn.Module):
    channels = 18

    def __init__(self):
        super().__init__()
        self.blur3 = SeparableBinomialBlur(1, 3)
        self.blur5 = SeparableBinomialBlur(1, 5)
        self.blur9 = SeparableBinomialBlur(1, 9)
        self.blur17 = SeparableBinomialBlur(1, 17)
        self.blur33 = SeparableBinomialBlur(1, 33)
        sobel = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32) / 8.0
        self.register_buffer("sobel_x", sobel.view(1, 1, 3, 3))
        self.register_buffer("sobel_y", sobel.t().contiguous().view(1, 1, 3, 3))

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        b3, b5, b9, b17, b33 = self.blur3(x), self.blur5(x), self.blur9(x), self.blur17(x), self.blur33(x)
        gx = F.conv2d(safe_pad(x, 1), self.sobel_x.to(dtype=x.dtype))
        gy = F.conv2d(safe_pad(x, 1), self.sobel_y.to(dtype=x.dtype))
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        local_centered = x - b17
        local_scale = torch.sqrt(self.blur17(local_centered.square()) + (2.0 / 255.0) ** 2)
        relative_gradient = (magnitude / (local_scale + 2.0 / 255.0)).clamp(0.0, 4.0)

        jxx = self.blur9(gx.square())
        jyy = self.blur9(gy.square())
        jxy = self.blur9(gx * gy)
        coherence = torch.sqrt((jxx - jyy).square() + 4.0 * jxy.square() + 1e-10) / (jxx + jyy + 1e-6)
        coherence = coherence.clamp(0.0, 1.0)
        nx, ny = gx / magnitude.clamp_min(1e-5), gy / magnitude.clamp_min(1e-5)

        normalized = (local_centered / (2.5 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        fine = ((b3 - b9) / (2.0 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        medium = ((b5 - b17) / (2.5 * local_scale + 2.0 / 255.0)).clamp(-1.0, 1.0)
        relative = (x / (b17 + 8.0 / 255.0) - 1.0).clamp(-1.0, 1.0)
        highpass = x - b3
        features = torch.cat([
            x, b3, b5, b9, b17, b33,
            x - b3, x - b5, x - b9,
            gx, gy, magnitude, nx, ny,
            normalized, fine, medium, relative,
        ], dim=1)
        gradient_support = ((relative_gradient - 0.28) / 1.25).clamp(0.0, 1.0)
        evidence = gradient_support * coherence
        evidence = torch.where(relative_gradient >= 0.28, evidence, torch.zeros_like(evidence))
        return {
            "features": features,
            "gx": gx,
            "gy": gy,
            "magnitude": magnitude,
            "nx": nx,
            "ny": ny,
            "coherence": coherence,
            "evidence": evidence,
            "local_scale": local_scale,
            "highpass": highpass,
        }


def sample_along_normal(x: torch.Tensor, nx: torch.Tensor, ny: torch.Tensor, distance: float) -> tuple[torch.Tensor, torch.Tensor]:
    n, _c, h, w = x.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, h, device=x.device, dtype=x.dtype),
        torch.linspace(-1.0, 1.0, w, device=x.device, dtype=x.dtype),
        indexing="ij",
    )
    base = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(n, -1, -1, -1)
    dx = 2.0 * float(distance) * nx[:, 0] / max(w - 1, 1)
    dy = 2.0 * float(distance) * ny[:, 0] / max(h - 1, 1)
    offset = torch.stack([dx, dy], dim=-1)
    plus = F.grid_sample(x, base + offset, mode="bilinear", padding_mode="reflection", align_corners=True)
    minus = F.grid_sample(x, base - offset, mode="bilinear", padding_mode="reflection", align_corners=True)
    return minus, plus


@dataclass
class R107Details:
    output: torch.Tensor
    width_scale: torch.Tensor
    reliability: torch.Tensor
    evidence: torch.Tensor
    coherence: torch.Tensor
    endpoint_mix: torch.Tensor
    endpoint_contrast: torch.Tensor
    rendered_edge: torch.Tensor
    edge_delta: torch.Tensor
    texture_gain: torch.Tensor
    texture_delta: torch.Tensor
    total_delta: torch.Tensor


class FixedCenterLocalEdgeMOSR(nn.Module):
    alignment_multiple = int(CONFIG["model"]["alignment_multiple"])
    minimum_halo_px = int(CONFIG["model"]["minimum_halo_px"])

    def __init__(self, base: int | None = None):
        super().__init__()
        base = int(base or CONFIG["model"]["base_channels"])
        self.base = base
        self.min_scale = float(CONFIG["model"]["minimum_width_scale"])
        self.max_scale = float(CONFIG["model"]["maximum_width_scale"])
        self.texture_bound = float(CONFIG["model"]["texture_gain_bound"])
        self.distances = tuple(float(value) for value in CONFIG["model"]["endpoint_distances_px"])
        self.cues = LocalEvidence()
        self.stem = nn.Sequential(ConvBlock(LocalEvidence.channels, base), ResBlock(base))
        dilations = [int(value) for value in CONFIG["model"]["body_dilations"]]
        self.body = nn.Sequential(*[ResBlock(base, dilation=value) for value in dilations])
        self.width_head = nn.Conv2d(base, 1, 1)
        self.reliability_head = nn.Conv2d(base, 1, 1)
        self.mix_head = nn.Conv2d(base, len(self.distances), 1)
        self.texture_head = nn.Conv2d(base, 1, 1)
        self._initialize_heads()

    def _initialize_heads(self) -> None:
        for head in (self.width_head, self.reliability_head, self.mix_head, self.texture_head):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)
        initial_scale = 0.90
        probability = (initial_scale - self.min_scale) / max(self.max_scale - self.min_scale, 1e-6)
        nn.init.constant_(self.width_head.bias, math.log(probability / max(1.0 - probability, 1e-6)))
        nn.init.constant_(self.reliability_head.bias, -2.2)

    def _forward_aligned(self, x: torch.Tensor) -> R107Details:
        raw = x.clamp(0.0, 1.0)
        cues = self.cues(raw)
        features = self.body(self.stem(cues["features"]))
        # Parameter heads are small and precision-sensitive.  Keep them in
        # FP32 under an otherwise AMP-enabled backbone; float16 1x1 outputs
        # overflowed after several optimizer steps in the first formal run.
        with torch.autocast(device_type=features.device.type, enabled=False):
            parameter_features = torch.tanh(features.float())
            width_logits = self.width_head(parameter_features)
            reliability_logits = self.reliability_head(parameter_features)
            mix_logits = self.mix_head(parameter_features)
            texture_logits = self.texture_head(parameter_features)
        width_scale = self.min_scale + (self.max_scale - self.min_scale) * torch.sigmoid(width_logits)
        learned_reliability = torch.sigmoid(reliability_logits)
        reliability = cues["evidence"] * learned_reliability
        endpoint_mix = torch.softmax(mix_logits, dim=1)

        rendered_rows = []
        contrast_rows = []
        for distance in self.distances:
            minus, plus = sample_along_normal(raw, cues["nx"], cues["ny"], distance)
            lower = torch.minimum(minus, plus)
            upper = torch.maximum(minus, plus)
            # Run the analytic logit transform in FP32 even under AMP.  In
            # float16, 1-1e-4 rounds to exactly 1 and log1p(-p) becomes -inf.
            lower32, upper32, raw32 = lower.float(), upper.float(), raw.float()
            contrast = (upper32 - lower32).clamp_min(1.0 / 255.0)
            probability = ((raw32 - lower32) / contrast).clamp(1e-4, 1.0 - 1e-4)
            logits = torch.logit(probability, eps=1e-4)
            sharpened = torch.sigmoid(logits / width_scale.float().clamp_min(self.min_scale))
            rendered_rows.append(lower32 + contrast * sharpened)
            contrast_rows.append(contrast)
        rendered_stack = torch.cat(rendered_rows, dim=1)
        contrast_stack = torch.cat(contrast_rows, dim=1)
        rendered_edge = (endpoint_mix.float() * rendered_stack).sum(dim=1, keepdim=True)
        endpoint_contrast = (endpoint_mix.float() * contrast_stack).sum(dim=1, keepdim=True)

        contrast_support = ((endpoint_contrast - 4.0 / 255.0) / (20.0 / 255.0)).clamp(0.0, 1.0)
        gate = reliability * contrast_support
        edge_delta = gate * (rendered_edge - raw)

        texture_gain = self.texture_bound * torch.tanh(texture_logits)
        texture_evidence = (cues["highpass"].abs() / (cues["local_scale"] + 2.0 / 255.0)).clamp(0.0, 1.0)
        texture_support = (1.0 - cues["evidence"]) * texture_evidence
        texture_delta = texture_support * texture_gain * cues["highpass"]

        total_delta = edge_delta + texture_delta
        output = (raw + total_delta).clamp(0.0, 1.0)
        return R107Details(
            output=output,
            width_scale=width_scale,
            reliability=gate,
            evidence=cues["evidence"],
            coherence=cues["coherence"],
            endpoint_mix=endpoint_mix,
            endpoint_contrast=endpoint_contrast,
            rendered_edge=rendered_edge,
            edge_delta=edge_delta,
            texture_gain=texture_gain,
            texture_delta=texture_delta,
            total_delta=total_delta,
        )

    def forward_details(self, x: torch.Tensor) -> R107Details:
        h, w = x.shape[-2:]
        pad_h, pad_w = (-h) % self.alignment_multiple, (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            details = self._forward_aligned(F.pad(x, (0, pad_w, 0, pad_h), mode=mode))
            values = [getattr(details, field)[..., :h, :w] for field in details.__dataclass_fields__]
            return R107Details(*values)
        return self._forward_aligned(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward_details(x).output


def build_model(base: int | None = None) -> FixedCenterLocalEdgeMOSR:
    return FixedCenterLocalEdgeMOSR(base=base)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
