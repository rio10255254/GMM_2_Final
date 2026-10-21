"""R102 parallel radiometry/contour/texture-innovation reconstruction model.

The network is deliberately local and fully convolutional.  Every normalizer
operates across channels at one pixel only, so image size and tile content do
not alter feature statistics.  Output heads start at exactly zero: a freshly
constructed model is an exact identity transform.
"""
from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
import torch.nn.functional as F


def _safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


class PixelGroupNorm(nn.Module):
    """Group normalization across channels, independently at every pixel."""

    def __init__(self, channels: int, groups: int = 8, eps: float = 1e-5):
        super().__init__()
        groups = min(int(groups), int(channels))
        while channels % groups:
            groups -= 1
        self.channels = int(channels)
        self.groups = int(groups)
        self.eps = float(eps)
        self.weight = nn.Parameter(torch.ones(channels))
        self.bias = nn.Parameter(torch.zeros(channels))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        n, c, h, w = x.shape
        y = x.reshape(n, self.groups, c // self.groups, h, w)
        mean = y.mean(dim=2, keepdim=True)
        var = y.var(dim=2, unbiased=False, keepdim=True)
        y = (y - mean) * torch.rsqrt(var + self.eps)
        y = y.reshape(n, c, h, w)
        return y * self.weight.view(1, c, 1, 1) + self.bias.view(1, c, 1, 1)


class ConvBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, dilation: int = 1, activate: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=dilation, dilation=dilation)
        self.norm = PixelGroupNorm(c_out)
        self.act = nn.SiLU() if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.norm(self.conv(x)))


class ResBlock(nn.Module):
    def __init__(self, channels: int, dilation: int = 1):
        super().__init__()
        self.a = ConvBlock(channels, channels, dilation=dilation)
        self.b = ConvBlock(channels, channels, dilation=dilation, activate=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.b(self.a(x)))


class FixedBlur(nn.Module):
    def __init__(self, channels: int, size: int = 5):
        super().__init__()
        if size == 3:
            kernel = torch.tensor([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=torch.float32) / 16.0
        elif size == 5:
            row = torch.tensor([1, 4, 6, 4, 1], dtype=torch.float32)
            kernel = torch.outer(row, row) / 256.0
        elif size == 9:
            row = torch.tensor([1, 8, 28, 56, 70, 56, 28, 8, 1], dtype=torch.float32)
            kernel = torch.outer(row, row) / 16384.0
        else:
            raise ValueError("FixedBlur supports sizes 3, 5, and 9")
        self.size = int(size)
        self.channels = int(channels)
        self.register_buffer("kernel", kernel.view(1, 1, size, size).repeat(channels, 1, 1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        radius = self.size // 2
        return F.conv2d(_safe_pad(x, radius), self.kernel.to(dtype=x.dtype), groups=self.channels)


class LocalOpticalCues(nn.Module):
    """Fixed, local cues. No measured PSF and no image-wide Wiener operation."""

    def __init__(self):
        super().__init__()
        self.blur3 = FixedBlur(1, 3)
        self.blur5 = FixedBlur(1, 5)
        self.blur9 = FixedBlur(1, 9)
        sx = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32) / 8.0
        sy = sx.t().contiguous()
        self.register_buffer("sobel_x", sx.view(1, 1, 3, 3))
        self.register_buffer("sobel_y", sy.view(1, 1, 3, 3))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b3, b5, b9 = self.blur3(x), self.blur5(x), self.blur9(x)
        gx = F.conv2d(_safe_pad(x, 1), self.sobel_x.to(dtype=x.dtype))
        gy = F.conv2d(_safe_pad(x, 1), self.sobel_y.to(dtype=x.dtype))
        grad = torch.sqrt(gx.square() + gy.square() + 1e-8)
        # A restrained local inverse cue supplies recoverability evidence but
        # never directly constrains or replaces the learned output.
        inverse_cue = (x + 0.7 * (x - b5)).clamp(0.0, 1.0)
        return torch.cat([x, b3, b9, x - b3, x - b9, gx, gy, grad, inverse_cue], dim=1)


class AntiAliasDown(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedBlur(c_in, 3)
        self.conv = nn.Conv2d(c_in, c_out, 3, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(x))


class ShiftSafeUp(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedBlur(c_in, 3)
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        return self.conv(self.blur(x))


class ParallelDilatedBody(nn.Module):
    """A local multi-scale body without serial denoise-then-sharpen ordering."""

    def __init__(self, channels: int):
        super().__init__()
        branch = max(8, channels // 2)
        self.a = ConvBlock(channels, branch, dilation=1)
        self.b = ConvBlock(channels, branch, dilation=2)
        self.c = ConvBlock(channels, branch, dilation=3)
        self.merge = nn.Sequential(ConvBlock(branch * 3, channels), ResBlock(channels))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.merge(torch.cat([self.a(x), self.b(x), self.c(x)], dim=1))


@dataclass
class R102Details:
    output: torch.Tensor
    low_delta: torch.Tensor
    contour_delta: torch.Tensor
    texture_delta: torch.Tensor
    total_delta: torch.Tensor
    contour_confidence: torch.Tensor
    texture_confidence: torch.Tensor


class ParallelInnovationMOSR(nn.Module):
    alignment_multiple = 8
    minimum_halo_px = 128

    def __init__(
        self,
        base: int = 32,
        low_bound: float = 0.18,
        contour_bound: float = 0.16,
        texture_bound: float = 0.14,
        combined_bound: float = 0.36,
    ):
        super().__init__()
        self.base = int(base)
        self.low_bound = float(low_bound)
        self.contour_bound = float(contour_bound)
        self.texture_bound = float(texture_bound)
        self.combined_bound = float(combined_bound)
        self.cues = LocalOpticalCues()

        self.e1 = nn.Sequential(ConvBlock(9, base), ResBlock(base))
        self.d1 = AntiAliasDown(base, base * 2)
        self.e2 = nn.Sequential(ConvBlock(base * 2, base * 2), ResBlock(base * 2))
        self.d2 = AntiAliasDown(base * 2, base * 4)
        self.e3 = nn.Sequential(ConvBlock(base * 4, base * 4), ResBlock(base * 4))
        self.d3 = AntiAliasDown(base * 4, base * 4)
        self.mid = nn.Sequential(ResBlock(base * 4, dilation=1), ResBlock(base * 4, dilation=2), ResBlock(base * 4, dilation=3))

        self.u3 = ShiftSafeUp(base * 4, base * 2)
        self.p3 = nn.Sequential(ConvBlock(base * 6, base * 2), ResBlock(base * 2))
        self.u2 = ShiftSafeUp(base * 2, base)
        self.p2 = nn.Sequential(ConvBlock(base * 3, base), ResBlock(base))
        self.u1 = ShiftSafeUp(base, base)
        self.p1 = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))

        self.low_body = nn.Sequential(ConvBlock(base, base), ResBlock(base))
        self.low_head = nn.Conv2d(base, 1, 1)

        self.contour_body = ParallelDilatedBody(base)
        self.contour_head = nn.Conv2d(base, 1, 1)
        self.contour_gate = nn.Conv2d(base, 1, 1)

        self.texture_body = ParallelDilatedBody(base)
        self.texture_head = nn.Conv2d(base, 1, 1)
        self.texture_gate = nn.Conv2d(base, 1, 1)

        self.low_project = FixedBlur(1, 9)
        self.contour_project = FixedBlur(1, 3)
        self.texture_project = FixedBlur(1, 5)
        self._initialize_identity_heads()

    def _initialize_identity_heads(self) -> None:
        for head in (self.low_head, self.contour_head, self.texture_head):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)
        for gate in (self.contour_gate, self.texture_gate):
            nn.init.zeros_(gate.weight)
            nn.init.zeros_(gate.bias)

    def _features(self, raw: torch.Tensor) -> torch.Tensor:
        f1 = self.e1(self.cues(raw))
        f2 = self.e2(self.d1(f1))
        f3 = self.e3(self.d2(f2))
        mid = self.mid(self.d3(f3))
        y3 = self.p3(torch.cat([self.u3(mid), f3], dim=1))
        y2 = self.p2(torch.cat([self.u2(y3), f2], dim=1))
        return self.p1(torch.cat([self.u1(y2), f1], dim=1))

    def _forward_aligned(self, x: torch.Tensor) -> R102Details:
        raw = x.clamp(0.0, 1.0)
        features = self._features(raw)

        # Radiometry is projected to a broad local band so it cannot draw a
        # dark outline. Contour and texture innovations are both zero-DC.
        low_logits = self.low_head(self.low_body(features))
        low_delta = self.low_bound * torch.tanh(self.low_project(low_logits))

        contour_features = self.contour_body(features)
        contour_confidence = torch.sigmoid(self.contour_gate(contour_features))
        contour_scale = 0.75 + 0.50 * contour_confidence
        contour_logits = torch.tanh(self.contour_head(contour_features))
        contour_high = contour_logits - self.contour_project(contour_logits)
        contour_delta = self.contour_bound * contour_scale * contour_high

        texture_features = self.texture_body(features)
        texture_confidence = torch.sigmoid(self.texture_gate(texture_features))
        texture_scale = 0.75 + 0.50 * texture_confidence
        texture_logits = torch.tanh(self.texture_head(texture_features))
        texture_high = texture_logits - self.texture_project(texture_logits)
        texture_delta = self.texture_bound * texture_scale * texture_high

        total = low_delta + contour_delta + texture_delta
        total = self.combined_bound * torch.tanh(total / max(self.combined_bound, 1e-6))
        output = (raw + total).clamp(0.0, 1.0)
        return R102Details(output, low_delta, contour_delta, texture_delta, total, contour_confidence, texture_confidence)

    def forward_details(self, x: torch.Tensor) -> R102Details:
        h, w = x.shape[-2:]
        pad_h = (-h) % self.alignment_multiple
        pad_w = (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            padded = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
            details = self._forward_aligned(padded)
            values = [getattr(details, field)[:, :, :h, :w] for field in details.__dataclass_fields__]
            return R102Details(*values)
        return self._forward_aligned(x)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.forward_details(x).output


def build_model(base: int = 32, **bounds: float) -> ParallelInnovationMOSR:
    return ParallelInnovationMOSR(base=base, **bounds)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
