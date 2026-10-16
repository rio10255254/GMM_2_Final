"""Tile-native MOSR model for R87.

Every operation is local in space.  There is no FFT, image-wide pooling, or
normalization over height and width.  Tiles whose global origins share the
8-pixel encoder phase therefore agree once a sufficiently wide halo is kept.
"""
from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class PixelGroupNorm(nn.Module):
    """Group normalization over channels only, independently at every pixel."""

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
    def __init__(self, c_in: int, c_out: int, *, activate: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)
        self.norm = PixelGroupNorm(c_out)
        self.act = nn.SiLU() if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.norm(self.conv(x)))


class ResBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.a = ConvBlock(channels, channels)
        self.b = ConvBlock(channels, channels, activate=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.b(self.a(x)))


class ShiftSafeUpsample(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = nn.Conv2d(c_in, c_in, 3, groups=c_in, bias=False)
        kernel = torch.tensor([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=torch.float32) / 16.0
        with torch.no_grad():
            self.blur.weight.copy_(kernel.view(1, 1, 3, 3).repeat(c_in, 1, 1, 1))
        self.blur.weight.requires_grad_(False)
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        mode = "reflect" if x.shape[-2] > 1 and x.shape[-1] > 1 else "replicate"
        x = self.blur(F.pad(x, (1, 1, 1, 1), mode=mode))
        return self.conv(x)


class LocalOpticalFeatures(nn.Module):
    """Fixed local blur/high-pass/gradient cues; no measured PSF is used."""

    def __init__(self):
        super().__init__()
        blur = torch.tensor(
            [[1, 4, 6, 4, 1], [4, 16, 24, 16, 4], [6, 24, 36, 24, 6],
             [4, 16, 24, 16, 4], [1, 4, 6, 4, 1]], dtype=torch.float32
        ) / 256.0
        sobel_x = torch.tensor([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=torch.float32) / 8.0
        sobel_y = sobel_x.t().contiguous()
        self.register_buffer("blur_kernel", blur.view(1, 1, 5, 5))
        self.register_buffer("sobel_x", sobel_x.view(1, 1, 3, 3))
        self.register_buffer("sobel_y", sobel_y.view(1, 1, 3, 3))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mode = "reflect" if x.shape[-2] > 2 and x.shape[-1] > 2 else "replicate"
        blur = F.conv2d(F.pad(x, (2, 2, 2, 2), mode=mode), self.blur_kernel)
        gx = F.conv2d(F.pad(x, (1, 1, 1, 1), mode=mode), self.sobel_x)
        gy = F.conv2d(F.pad(x, (1, 1, 1, 1), mode=mode), self.sobel_y)
        grad = torch.sqrt(gx.square() + gy.square() + 1e-8)
        return torch.cat([x, blur, x - blur, grad], dim=1)


class TileNativeMOSR(nn.Module):
    alignment_multiple = 8

    def __init__(self, base: int = 32):
        super().__init__()
        self.base = int(base)
        self.optical = LocalOpticalFeatures()

        self.e1 = nn.Sequential(ConvBlock(4, base), ResBlock(base))
        self.d1 = nn.Conv2d(base, base, 3, stride=2, padding=1)
        self.e2 = nn.Sequential(ConvBlock(base, base * 2), ResBlock(base * 2))
        self.d2 = nn.Conv2d(base * 2, base * 2, 3, stride=2, padding=1)
        self.e3 = nn.Sequential(ConvBlock(base * 2, base * 4), ResBlock(base * 4))
        self.d3 = nn.Conv2d(base * 4, base * 4, 3, stride=2, padding=1)
        self.mid = nn.Sequential(ConvBlock(base * 4, base * 4), ResBlock(base * 4), ResBlock(base * 4))

        self.u3 = ShiftSafeUpsample(base * 4, base * 2)
        self.p3 = nn.Sequential(ConvBlock(base * 6, base * 2), ResBlock(base * 2))
        self.u2 = ShiftSafeUpsample(base * 2, base)
        self.p2 = nn.Sequential(ConvBlock(base * 3, base), ResBlock(base))
        self.u1 = ShiftSafeUpsample(base, base)
        self.p1 = nn.Sequential(ConvBlock(base * 2, base), ResBlock(base))

        self.residual_head = nn.Conv2d(base, 1, 1)
        self.boundary_head = nn.Sequential(
            nn.Conv2d(base + 1, 16, 3, padding=1),
            nn.SiLU(),
            nn.Conv2d(16, 1, 3, padding=1),
        )
        nn.init.zeros_(self.residual_head.weight)
        nn.init.zeros_(self.residual_head.bias)
        nn.init.zeros_(self.boundary_head[-1].weight)
        nn.init.zeros_(self.boundary_head[-1].bias)

    def _forward_aligned(self, x: torch.Tensor) -> torch.Tensor:
        raw = x.clamp(1e-4, 1.0 - 1e-4)
        f1 = self.e1(self.optical(raw))
        f2 = self.e2(self.d1(f1))
        f3 = self.e3(self.d2(f2))
        mid = self.mid(self.d3(f3))
        y3 = self.p3(torch.cat([self.u3(mid), f3], dim=1))
        y2 = self.p2(torch.cat([self.u2(y3), f2], dim=1))
        y1 = self.p1(torch.cat([self.u1(y2), f1], dim=1))

        base_residual = 3.0 * torch.tanh(self.residual_head(y1))
        local_grad = self.optical(raw)[:, 3:4]
        boundary_residual = 0.75 * torch.tanh(self.boundary_head(torch.cat([y1, local_grad], dim=1)))
        return torch.sigmoid(torch.logit(raw) + base_residual + boundary_residual)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, w = x.shape[-2:]
        pad_h = (-h) % self.alignment_multiple
        pad_w = (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            x = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
        out = self._forward_aligned(x)
        return out[..., :h, :w]


def build_model(base: int = 32) -> TileNativeMOSR:
    return TileNativeMOSR(base=base)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())

