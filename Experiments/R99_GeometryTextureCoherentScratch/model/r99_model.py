"""R99 geometry/texture-coherent, tile-safe reconstruction model.

The proven normalization-free, anti-aliased local backbone is retained.  R99
adds one missing causal action: a bounded sub-pixel transport field that can
move an observed edge along the learned foreground normal.  Illumination,
geometry transport, edge-profile repair and source-supported texture are then
applied sequentially so later branches cannot silently cancel the geometry
correction.
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
        15: torch.tensor([1, 14, 91, 364, 1001, 2002, 3003, 3432, 3003, 2002, 1001, 364, 91, 14, 1], dtype=torch.float32),
        17: torch.tensor([1, 16, 120, 560, 1820, 4368, 8008, 11440, 12870, 11440, 8008, 4368, 1820, 560, 120, 16, 1], dtype=torch.float32),
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
        # Every fixed blur in R99 is binomial and therefore exactly separable.
        # Row/column sums recover the normalized 1-D vector.  Two short
        # depthwise passes replace a KxK pass (34 taps instead of 289 for K17)
        # without changing the mathematical filter or receptive field.
        vector = kernel.float().sum(dim=0)
        self.register_buffer("kernel_horizontal", vector.view(1, 1, 1, -1))
        self.register_buffer("kernel_vertical", vector.view(1, 1, -1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        channels = int(x.shape[1])
        horizontal = self.kernel_horizontal.to(dtype=x.dtype).repeat(channels, 1, 1, 1)
        vertical = self.kernel_vertical.to(dtype=x.dtype).repeat(channels, 1, 1, 1)
        mode = "reflect" if x.shape[-2] > self.radius and x.shape[-1] > self.radius else "replicate"
        x = F.conv2d(F.pad(x, (self.radius, self.radius, 0, 0), mode=mode), horizontal, groups=channels)
        return F.conv2d(F.pad(x, (0, 0, self.radius, self.radius), mode=mode), vertical, groups=channels)


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


class GeometryTextureCoherentNet(nn.Module):
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
        self.geometry_head = nn.Sequential(ConvAct(base + 4, base), ResidualBlock(base, scale=0.08), nn.Conv2d(base, 1, 1))
        self.transport_head = nn.Sequential(ConvAct(base + 5, base), ResidualBlock(base, scale=0.08), nn.Conv2d(base, 1, 1))
        self.edge_head = nn.Sequential(ConvAct(base + 5, base), nn.Conv2d(base, 1, 1))
        self.texture_head = nn.Sequential(
            ConvAct(base + 6, base),
            ResidualBlock(base, scale=0.08),
            ConvAct(base, base),
            nn.Conv2d(base, 6, 1),
        )
        self.low_head_blur = FixedFilter(_binomial_kernel(7))
        self.blur3 = FixedFilter(_binomial_kernel(3))
        self.blur5 = FixedFilter(_binomial_kernel(5))
        self.blur7 = FixedFilter(_binomial_kernel(7))
        self.blur15 = FixedFilter(_binomial_kernel(15))
        self.blur17 = FixedFilter(_binomial_kernel(17))
        for head in (
            self.low_head[-1], self.geometry_head[-1], self.transport_head[-1],
            self.edge_head[-1], self.texture_head[-1],
        ):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)

    @staticmethod
    def _sample_with_pixel_offsets(
        image: torch.Tensor,
        dx_px: torch.Tensor,
        dy_px: torch.Tensor,
    ) -> torch.Tensor:
        """Local ONNX-compatible bilinear sampling in physical pixel units."""
        n, _c, h, w = image.shape
        # Build the identity grid directly.  This is equivalent to affine_grid
        # but exports through ONNX opset 17, whereas PyTorch 2.3 has no legacy
        # exporter for aten::affine_grid_generator.
        x_coordinates = torch.arange(w, device=image.device, dtype=torch.float32).view(1, 1, w)
        y_coordinates = torch.arange(h, device=image.device, dtype=torch.float32).view(1, h, 1)
        grid_x = 2.0 * (x_coordinates + dx_px[:, 0].float()) / (w - 1) - 1.0
        grid_y = 2.0 * (y_coordinates + dy_px[:, 0].float()) / (h - 1) - 1.0
        grid = torch.stack([grid_x, grid_y], dim=-1)
        transported = F.grid_sample(
            image.float(), grid, mode="bilinear", padding_mode="border", align_corners=True,
        )
        return transported.to(dtype=image.dtype)

    def _geometry_transport(
        self,
        image: torch.Tensor,
        geometry_probability: torch.Tensor,
        offset_px: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        # The learned probability is always foreground-oriented, independent
        # of whether the actual object is bright or dark.  Its gradient is
        # therefore a stable inward normal for both polarities.
        smooth_probability = self.blur7(geometry_probability)
        gx = self.optical._filter(smooth_probability, self.optical.sobel_x, (1, 1, 1, 1))
        gy = self.optical._filter(smooth_probability, self.optical.sobel_y, (1, 1, 1, 1))
        magnitude_squared = gx.square() + gy.square()
        normalizer = torch.sqrt(magnitude_squared + 1e-8)
        # Squared soft support is exactly zero on flat geometry and has a
        # finite derivative there, avoiding the undefined sqrt gradient that
        # an otherwise equivalent magnitude formulation would introduce.
        support = magnitude_squared / (magnitude_squared + 0.015 ** 2)
        dx_px = offset_px * gx / normalizer * support
        dy_px = offset_px * gy / normalizer * support
        sampled = self._sample_with_pixel_offsets(image, dx_px, dy_px)
        # Blend only on the learned boundary.  Besides avoiding needless
        # resampling of flat texture, this makes the zero-initialized model an
        # exact identity rather than a numerically approximate grid sample.
        transported = image + support * (sampled - image)
        return transported, dx_px, dy_px, support

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
        low_small = 0.28 * torch.tanh(self.low_head(F.avg_pool2d(y1, 4, stride=4)))
        low_delta = F.interpolate(low_small, size=raw.shape[-2:], mode="bilinear", align_corners=False)
        low_delta = self.low_head_blur(low_delta)

        # 1) broad radiometry first
        radiometry_base = torch.clamp(raw + low_delta, 0.0, 1.0)

        # 2) actionable geometry.  Unlike R92/R98, this probability is part of
        # the reconstruction graph and its normal actually transports pixels.
        geometry_logits = self.geometry_head(torch.cat([y1, raw, local_edges], dim=1))
        geometry_probability = torch.sigmoid(geometry_logits)
        transport_features = torch.cat(
            [y1, radiometry_base, geometry_probability, local_edges], dim=1,
        )
        transport_offset_px = 1.50 * torch.tanh(self.blur7(self.transport_head(transport_features)))
        geometry_base, transport_dx_px, transport_dy_px, geometry_boundary_support = self._geometry_transport(
            radiometry_base, geometry_probability, transport_offset_px,
        )
        transport_delta = geometry_base - radiometry_base

        # 3) repair the edge transition after it has reached the right place.
        edge_features = torch.cat(
            [y1, geometry_base, geometry_probability, local_edges], dim=1,
        )
        edge_localizer = 0.20 + 0.80 * geometry_boundary_support
        edge_delta = 0.10 * torch.tanh(self.edge_head(edge_features)) * edge_localizer
        edge_base = torch.clamp(geometry_base + edge_delta, 0.0, 1.0)

        # 4) source-supported six-band texture.  Coefficients vary slowly and
        # all candidates are zero-DC, so texture cannot reintroduce broad
        # illumination drift or a second geometry transport.
        blur3 = self.blur3(edge_base)
        blur5 = self.blur5(edge_base)
        blur7 = self.blur7(edge_base)
        blur15 = self.blur15(edge_base)
        blur17 = self.blur17(edge_base)
        texture_candidates = torch.cat(
            [
                edge_base - blur3,
                edge_base - blur5,
                blur3 - blur7,
                blur5 - blur15,
                blur7 - blur17,
                blur15 - blur17,
            ],
            dim=1,
        )
        texture_features = torch.cat(
            [
                y1, edge_base, raw_low, raw_high, raw_high.abs(),
                geometry_probability, geometry_boundary_support,
            ],
            dim=1,
        )
        texture_coefficients = 2.10 * torch.tanh(self.blur5(self.texture_head(texture_features)))
        coefficient_norm = texture_coefficients.abs().sum(dim=1, keepdim=True).clamp_min(2.10)
        texture_coefficients = texture_coefficients * (2.10 / coefficient_norm)
        detail_delta = torch.clamp(
            (texture_coefficients * texture_candidates).sum(dim=1, keepdim=True),
            -0.20,
            0.20,
        )
        output = torch.clamp(edge_base + detail_delta, 0.0, 1.0)
        correction = torch.clamp(output - raw, -0.45, 0.45)
        output = torch.clamp(raw + correction, 0.0, 1.0)
        return {
            "output": output,
            "low_delta": low_delta,
            "detail_delta": detail_delta,
            "edge_delta": edge_delta,
            "transport_delta": transport_delta,
            "transport_offset_px": transport_offset_px,
            "transport_dx_px": transport_dx_px,
            "transport_dy_px": transport_dy_px,
            "correction": correction,
            "geometry_logits": geometry_logits,
            "geometry_probability": geometry_probability,
            "geometry_boundary_support": geometry_boundary_support,
            "texture_coefficients": texture_coefficients,
            "texture_candidates": texture_candidates,
            "raw_low": raw_low,
        }

    def forward(self, x: torch.Tensor, return_details: bool = False) -> torch.Tensor | dict[str, torch.Tensor]:
        h, w = x.shape[-2:]
        pad_h = (-h) % self.alignment_multiple
        pad_w = (-w) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if h > pad_h and w > pad_w else "replicate"
            x = F.pad(x, (0, pad_w, 0, pad_h), mode=mode)
        details = self._forward_aligned(x)
        details = {key: value[..., :h, :w] for key, value in details.items()}
        return details if return_details else details["output"]


def build_model(base: int = 24) -> GeometryTextureCoherentNet:
    return GeometryTextureCoherentNet(base=base)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def architecture_contract(model: GeometryTextureCoherentNet) -> dict[str, Any]:
    return {
        "class_name": type(model).__name__,
        "parameter_count": count_parameters(model),
        "normalization_layers": 0,
        "global_pooling_layers": 0,
        "alignment_multiple": model.alignment_multiple,
        "minimum_halo_px": model.minimum_halo_px,
        "r90_backbone_preserved": True,
        "binary_confidence_gate": False,
        "raw_identity_at_initialization": True,
        "low_correction_bound": 0.28,
        "low_branch_quarter_resolution_lowpass": True,
        "transport_bound_px": 1.50,
        "geometry_is_actionable": True,
        "geometry_detached_from_reconstruction": False,
        "sequential_branch_composition": True,
        "detail_correction_bound": 0.20,
        "detail_branch_multiscale_zero_dc": True,
        "detail_subbands": 6,
        "edge_correction_bound": 0.10,
        "combined_correction_bound": 0.45,
        "auxiliary_geometry_head": False,
    }
