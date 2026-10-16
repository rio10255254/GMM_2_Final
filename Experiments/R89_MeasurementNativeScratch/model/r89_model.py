"""R89 measurement-native, tile-safe reconstruction model.

R89 preserves the R88 local optical bank and encoder-decoder.  The small but
important change is at the output: low-frequency, detail and edge corrections
are learned directly instead of being attenuated by a confidence gate.  The
model remains local, normalization-free and fully convolutional.
"""
from __future__ import annotations

from typing import Any

import torch
from torch import nn
import torch.nn.functional as F


def _pad_local(x: torch.Tensor, amount: int) -> torch.Tensor:
    if amount <= 0:
        return x
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


def _binomial_kernel(size: int) -> torch.Tensor:
    rows = {
        3: torch.tensor([1.0, 2.0, 1.0]),
        5: torch.tensor([1.0, 4.0, 6.0, 4.0, 1.0]),
        7: torch.tensor([1.0, 6.0, 15.0, 20.0, 15.0, 6.0, 1.0]),
    }
    vector = rows[int(size)]
    kernel = torch.outer(vector, vector)
    return kernel / kernel.sum()


class FixedFilter(nn.Module):
    def __init__(self, kernel: torch.Tensor):
        super().__init__()
        if kernel.ndim != 2 or kernel.shape[0] != kernel.shape[1] or kernel.shape[0] % 2 != 1:
            raise ValueError("FixedFilter requires a square odd kernel")
        self.radius = int(kernel.shape[0] // 2)
        self.register_buffer("kernel", kernel.float().view(1, 1, *kernel.shape))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        channels = int(x.shape[1])
        kernel = self.kernel.to(dtype=x.dtype).repeat(channels, 1, 1, 1)
        return F.conv2d(_pad_local(x, self.radius), kernel, groups=channels)


class ConvAct(nn.Module):
    def __init__(self, c_in: int, c_out: int, *, activate: bool = True):
        super().__init__()
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)
        self.act = nn.SiLU(inplace=True) if activate else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.conv(x))


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, scale: float = 0.1):
        super().__init__()
        self.a = ConvAct(channels, channels)
        self.b = ConvAct(channels, channels, activate=False)
        self.scale = float(scale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.silu(x + self.scale * self.b(self.a(x)))


class AntiAliasedDownsample(nn.Module):
    """Fixed low-pass filtering before every learned stride-2 operation."""

    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedFilter(_binomial_kernel(5))
        self.conv = nn.Conv2d(c_in, c_out, 3, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(x))


class AntiAliasedUpsample(nn.Module):
    """Bilinear upsample followed by a fixed depthwise low-pass."""

    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedFilter(_binomial_kernel(3))
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        return self.conv(self.blur(x))


class LocalOpticalBank(nn.Module):
    """Fixed procedural optical cues with learned local convex mixing."""

    def __init__(self):
        super().__init__()
        self.g3 = FixedFilter(_binomial_kernel(3))
        self.g5 = FixedFilter(_binomial_kernel(5))
        self.g7 = FixedFilter(_binomial_kernel(7))
        one_d = torch.tensor([1.0, 6.0, 15.0, 20.0, 15.0, 6.0, 1.0]) / 64.0
        self.register_buffer("anisotropic_x", one_d.view(1, 1, 1, 7))
        self.register_buffer("anisotropic_y", one_d.view(1, 1, 7, 1))
        sobel = torch.tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]]) / 8.0
        self.register_buffer("sobel_x", sobel.view(1, 1, 3, 3))
        self.register_buffer("sobel_y", sobel.t().contiguous().view(1, 1, 3, 3))
        lap = torch.tensor([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]])
        self.register_buffer("laplacian", lap.view(1, 1, 3, 3))
        self.weight_logits = nn.Sequential(
            nn.Conv2d(4, 16, 3, padding=1),
            nn.SiLU(inplace=True),
            nn.Conv2d(16, 9, 1),
        )
        nn.init.zeros_(self.weight_logits[-1].weight)
        nn.init.zeros_(self.weight_logits[-1].bias)

    @staticmethod
    def _filter(x: torch.Tensor, kernel: torch.Tensor, pad: tuple[int, int, int, int]) -> torch.Tensor:
        amount = max(pad)
        mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
        return F.conv2d(F.pad(x, pad, mode=mode), kernel.to(dtype=x.dtype))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        g3, g5, g7 = self.g3(x), self.g5(x), self.g7(x)
        ax = self._filter(x, self.anisotropic_x, (3, 3, 0, 0))
        ay = self._filter(x, self.anisotropic_y, (0, 0, 3, 3))
        gx = self._filter(x, self.sobel_x, (1, 1, 1, 1))
        gy = self._filter(x, self.sobel_y, (1, 1, 1, 1))
        lap = self._filter(x, self.laplacian, (1, 1, 1, 1))
        bank = torch.cat([x, g3, g5, g7, ax, ay, gx, gy, lap], dim=1)
        cues = torch.cat([x, g5, gx.abs(), gy.abs()], dim=1)
        weights = torch.softmax(self.weight_logits(cues), dim=1)
        mixed = (weights * bank).sum(dim=1, keepdim=True)
        features = torch.cat([x, mixed, x - g5, gx.abs(), gy.abs(), lap], dim=1)
        return features, g7


class MeasurementNativeTileNet(nn.Module):
    alignment_multiple = 8
    minimum_halo_px = 192

    def __init__(self, base: int = 24):
        super().__init__()
        self.base = int(base)
        self.optical = LocalOpticalBank()

        self.e1 = nn.Sequential(ConvAct(6, base), ResidualBlock(base), ResidualBlock(base))
        self.d1 = AntiAliasedDownsample(base, base * 2)
        self.e2 = nn.Sequential(ResidualBlock(base * 2), ResidualBlock(base * 2))
        self.d2 = AntiAliasedDownsample(base * 2, base * 4)
        self.e3 = nn.Sequential(ResidualBlock(base * 4), ResidualBlock(base * 4))
        self.d3 = AntiAliasedDownsample(base * 4, base * 6)
        self.mid = nn.Sequential(ResidualBlock(base * 6), ResidualBlock(base * 6), ResidualBlock(base * 6))

        self.u3 = AntiAliasedUpsample(base * 6, base * 4)
        self.f3 = nn.Sequential(ConvAct(base * 8, base * 4), ResidualBlock(base * 4))
        self.u2 = AntiAliasedUpsample(base * 4, base * 2)
        self.f2 = nn.Sequential(ConvAct(base * 4, base * 2), ResidualBlock(base * 2))
        self.u1 = AntiAliasedUpsample(base * 2, base)
        self.f1 = nn.Sequential(ConvAct(base * 2, base), ResidualBlock(base))

        self.low_head = nn.Sequential(ConvAct(base, base), nn.Conv2d(base, 1, 1))
        self.detail_head = nn.Sequential(ConvAct(base + 2, base), nn.Conv2d(base, 1, 1))
        self.edge_head = nn.Sequential(ConvAct(base + 3, base), nn.Conv2d(base, 1, 1))
        self.geometry_head = nn.Sequential(ConvAct(base + 4, base), nn.Conv2d(base, 1, 1))
        self.detail_blur = FixedFilter(_binomial_kernel(3))
        for head in (self.low_head[-1], self.detail_head[-1], self.edge_head[-1], self.geometry_head[-1]):
            nn.init.normal_(head.weight, mean=0.0, std=1e-3)
            nn.init.zeros_(head.bias)

    def _forward_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = x.clamp(0.0, 1.0)
        optical, raw_low = self.optical(raw)
        raw_high = raw - raw_low
        e1 = self.e1(optical)
        e2 = self.e2(self.d1(e1))
        e3 = self.e3(self.d2(e2))
        mid = self.mid(self.d3(e3))
        y3 = self.f3(torch.cat([self.u3(mid), e3], dim=1))
        y2 = self.f2(torch.cat([self.u2(y3), e2], dim=1))
        y1 = self.f1(torch.cat([self.u1(y2), e1], dim=1))

        local_edges = optical[:, 3:6]
        low_delta = 0.28 * torch.tanh(self.low_head(y1))
        detail_raw = 0.12 * torch.tanh(self.detail_head(torch.cat([y1, raw_high, raw_high.abs()], dim=1)))
        detail_delta = torch.clamp(detail_raw - self.detail_blur(detail_raw), -0.12, 0.12)
        edge_delta = 0.08 * torch.tanh(self.edge_head(torch.cat([y1, local_edges], dim=1)))
        geometry_logits = self.geometry_head(torch.cat([y1, raw, local_edges], dim=1))
        correction = torch.clamp(low_delta + detail_delta + edge_delta, -0.35, 0.35)
        output = torch.clamp(raw + correction, 0.0, 1.0)
        return {
            "output": output,
            "low_delta": low_delta,
            "detail_delta": detail_delta,
            "edge_delta": edge_delta,
            "correction": correction,
            "geometry_logits": geometry_logits,
            "raw_low": raw_low,
        }

    def forward(self, x: torch.Tensor, *, return_details: bool = False) -> torch.Tensor | dict[str, torch.Tensor]:
        h, w = x.shape[-2:]
        pad_h = (-h) % self.alignment_multiple
        pad_w = (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            x = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
        details = self._forward_aligned(x)
        details = {key: value[..., :h, :w] for key, value in details.items()}
        return details if return_details else details["output"]


def build_model(base: int = 24) -> MeasurementNativeTileNet:
    return MeasurementNativeTileNet(base=base)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def architecture_contract(model: MeasurementNativeTileNet) -> dict[str, Any]:
    return {
        "class_name": type(model).__name__,
        "parameter_count": count_parameters(model),
        "normalization_layers": 0,
        "global_pooling_layers": 0,
        "alignment_multiple": model.alignment_multiple,
        "minimum_halo_px": model.minimum_halo_px,
        "r88_backbone_preserved": True,
        "confidence_gate": False,
        "raw_identity_at_initialization": False,
        "low_correction_bound": 0.28,
        "detail_correction_bound": 0.12,
        "edge_correction_bound": 0.08,
        "combined_correction_bound": 0.35,
        "auxiliary_geometry_head": True,
    }
