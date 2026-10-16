"""Local building blocks retained from R117; no model weights are reused."""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
from typing import Iterable

import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]


def safe_pad(value: torch.Tensor, amount: int) -> torch.Tensor:
    if amount <= 0:
        return value
    mode = "reflect" if min(value.shape[-2:]) > amount else "replicate"
    return F.pad(value, (amount, amount, amount, amount), mode=mode)


class LocalConv2d(nn.Module):
    def __init__(self, inputs: int, outputs: int, kernel: int = 3, dilation: int = 1):
        super().__init__()
        self.pad = dilation * (kernel // 2)
        self.conv = nn.Conv2d(inputs, outputs, kernel, dilation=dilation)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.conv(safe_pad(value, self.pad))


class GaussianBlur(nn.Module):
    def __init__(self, sigma: float):
        super().__init__()
        self.radius = max(1, int(math.ceil(3 * sigma)))
        axis = torch.arange(-self.radius, self.radius + 1, dtype=torch.float32)
        row = torch.exp(-0.5 * (axis / sigma).square())
        row /= row.sum()
        self.register_buffer("h", row.view(1, 1, 1, -1))
        self.register_buffer("v", row.view(1, 1, -1, 1))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        channels = value.shape[1]
        h = self.h.to(value).expand(channels, 1, 1, -1)
        v = self.v.to(value).expand(channels, 1, -1, 1)
        mode = "reflect" if min(value.shape[-2:]) > self.radius else "replicate"
        value = F.conv2d(F.pad(value, (self.radius, self.radius, 0, 0), mode=mode), h, groups=channels)
        return F.conv2d(F.pad(value, (0, 0, self.radius, self.radius), mode=mode), v, groups=channels)


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, dilation: int):
        super().__init__()
        self.a, self.b = LocalConv2d(channels, channels, 3, dilation), LocalConv2d(channels, channels, 3, dilation)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return F.silu(value + 0.15 * self.b(F.silu(self.a(value))))


class LocalTower(nn.Module):
    def __init__(self, inputs: int, channels: int, dilations: Iterable[int]):
        super().__init__()
        self.stem = LocalConv2d(inputs, channels)
        self.blocks = nn.Sequential(*(ResidualBlock(channels, int(item)) for item in dilations))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.blocks(F.silu(self.stem(value)))


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0), mode="replicate")
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1), mode="replicate")
    return gx, gy


def warp_local(value: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=value.device, dtype=value.dtype),
        torch.linspace(-1, 1, width, device=value.device, dtype=value.dtype), indexing="ij",
    )
    grid = torch.stack((xx, yy), -1).unsqueeze(0).expand(batch, -1, -1, -1).clone()
    grid[..., 0] += flow[:, 0] * (2.0 / max(width - 1, 1))
    grid[..., 1] += flow[:, 1] * (2.0 / max(height - 1, 1))
    sampled = F.grid_sample(value, grid, mode="bilinear", padding_mode="reflection", align_corners=True)
    zero = flow.abs().amax(dim=1, keepdim=True) == 0
    return sampled + zero.to(sampled.dtype) * (value - sampled).detach()


def warp_many(value: torch.Tensor, flows: torch.Tensor) -> torch.Tensor:
    batch, samples, _two, height, width = flows.shape
    channels = value.shape[1]
    packed = value[:, None].expand(-1, samples, -1, -1, -1).reshape(batch * samples, channels, height, width)
    return warp_local(packed, flows.reshape(batch * samples, 2, height, width)).reshape(batch, samples, channels, height, width)


class LocalCues(nn.Module):
    def __init__(self, scales):
        super().__init__()
        self.blurs = nn.ModuleList(GaussianBlur(float(item)) for item in scales)
        self.context = GaussianBlur(float(max(scales)))
        self.channels = 1 + 2 * len(scales) + 6

    def forward(self, raw: torch.Tensor) -> dict:
        blurred = [layer(raw) for layer in self.blurs]
        highpasses = [raw - item for item in blurred]
        gx, gy = gradients(raw)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-8)
        mean = blurred[-1]
        scale = torch.sqrt(self.context((raw - mean).square()) + (2.0 / 255.0) ** 2)
        normalized = (raw - mean) / (scale + 2.0 / 255.0)
        normalized = normalized / torch.sqrt(1.0 + normalized.square() / 16.0)
        return {
            "features": torch.cat((raw, *blurred, *highpasses, gx, gy, magnitude, mean, scale, normalized), 1),
            "blurred": blurred, "highpasses": highpasses, "magnitude": magnitude,
            "local_mean": mean, "local_scale": scale,
        }
