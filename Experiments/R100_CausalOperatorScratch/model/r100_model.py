"""R100 causal, source-supported, tile-safe reconstruction model.

R100 deliberately has no spatial transport and no unrestricted image residual
head.  The learned network may only control four local physical operations:
broad radiometry, flat-region denoising, symmetric edge-profile restoration,
and source-supported material-detail restoration away from structural edges.
"""
from __future__ import annotations

from typing import Any

import torch
from torch import nn
import torch.nn.functional as F


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
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedFilter(_binomial_kernel(5))
        self.conv = nn.Conv2d(c_in, c_out, 3, stride=2, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(self.blur(x))


class AntiAliasedUpsample(nn.Module):
    def __init__(self, c_in: int, c_out: int):
        super().__init__()
        self.blur = FixedFilter(_binomial_kernel(3))
        self.conv = nn.Conv2d(c_in, c_out, 3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        return self.conv(self.blur(x))


class LocalOpticalBank(nn.Module):
    """Procedural optical cues used only as evidence, never as output pixels."""

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

    def gradients(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        gx = self._filter(x, self.sobel_x, (1, 1, 1, 1))
        gy = self._filter(x, self.sobel_y, (1, 1, 1, 1))
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        return gx, gy, magnitude

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        g3, g5, g7 = self.g3(x), self.g5(x), self.g7(x)
        ax = self._filter(x, self.anisotropic_x, (3, 3, 0, 0))
        ay = self._filter(x, self.anisotropic_y, (0, 0, 3, 3))
        gx, gy, _magnitude = self.gradients(x)
        lap = self._filter(x, self.laplacian, (1, 1, 1, 1))
        bank = torch.cat([x, g3, g5, g7, ax, ay, gx, gy, lap], dim=1)
        cues = torch.cat([x, g5, gx.abs(), gy.abs()], dim=1)
        weights = torch.softmax(self.weight_logits(cues), dim=1)
        mixed = (weights * bank).sum(dim=1, keepdim=True)
        features = torch.cat([x, mixed, x - g5, gx.abs(), gy.abs(), lap], dim=1)
        return features, g7


class CausalOperatorNet(nn.Module):
    alignment_multiple = 8
    minimum_halo_px = 192

    def __init__(self, base: int = 24):
        super().__init__()
        self.base = int(base)
        self.optical = LocalOpticalBank()
        self.blur3 = FixedFilter(_binomial_kernel(3))
        self.blur5 = FixedFilter(_binomial_kernel(5))
        self.blur7 = FixedFilter(_binomial_kernel(7))
        self.blur15 = FixedFilter(_binomial_kernel(15))
        self.blur17 = FixedFilter(_binomial_kernel(17))

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

        # The shared backbone predicts operation strength, never output pixels.
        self.radiometry_head = nn.Sequential(ConvAct(base, base), nn.Conv2d(base, 2, 1))
        self.denoise_head = nn.Sequential(ConvAct(base + 6, base), ResidualBlock(base, scale=0.08), nn.Conv2d(base, 1, 1))
        self.texture_head = nn.Sequential(ConvAct(base + 7, base), ResidualBlock(base, scale=0.08), nn.Conv2d(base, 3, 1))

        # Edge strength sees only sign-free, symmetric optical evidence.  It
        # cannot inspect an arbitrary signed feature map and paint an edge.
        self.edge_head = nn.Sequential(ConvAct(6, 16), ConvAct(16, 16), nn.Conv2d(16, 1, 1))

        nn.init.zeros_(self.radiometry_head[-1].weight)
        nn.init.zeros_(self.radiometry_head[-1].bias)
        for head in (self.denoise_head[-1], self.texture_head[-1], self.edge_head[-1]):
            nn.init.zeros_(head.weight)
        nn.init.constant_(self.denoise_head[-1].bias, -4.2)
        nn.init.constant_(self.edge_head[-1].bias, -4.0)
        nn.init.constant_(self.texture_head[-1].bias, -3.5)

    def _aligned_features(self, raw: torch.Tensor) -> torch.Tensor:
        optical, _raw_low = self.optical(raw)
        e1 = self.e1(optical)
        e2 = self.e2(self.d1(e1))
        e3 = self.e3(self.d2(e2))
        mid = self.mid(self.d3(e3))
        y3 = self.f3(torch.cat([self.u3(mid), e3], dim=1))
        y2 = self.f2(torch.cat([self.u2(y3), e2], dim=1))
        return self.f1(torch.cat([self.u1(y2), e1], dim=1))

    def _forward_aligned(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = x.clamp(0.0, 1.0)
        features = self._aligned_features(raw)

        # 1) Broad radiometry.  The predicted maps are quarter-resolution and
        # filtered again, so this stage cannot draw a narrow contour.
        radiometry_small = self.radiometry_head(F.avg_pool2d(features, 4, stride=4))
        radiometry_params = F.interpolate(radiometry_small, size=raw.shape[-2:], mode="bilinear", align_corners=False)
        radiometry_params = self.blur17(radiometry_params)
        gain_delta = 0.22 * torch.tanh(radiometry_params[:, :1])
        bias_delta = 0.16 * torch.tanh(radiometry_params[:, 1:2])
        radiometry = torch.clamp(raw * (1.0 + gain_delta) + bias_delta, 0.0, 1.0)
        low_delta = radiometry - raw

        b3 = self.blur3(radiometry)
        b7 = self.blur7(radiometry)
        b15 = self.blur15(radiometry)
        _gx3, _gy3, mag3 = self.optical.gradients(b3)
        _gx15, _gy15, mag15 = self.optical.gradients(b15)
        edge_support = mag15.square() / (mag15.square() + 0.012 ** 2)
        edge_support = self.blur5(edge_support).clamp(0.0, 1.0)
        material_support = (1.0 - edge_support).square()
        even_cues = torch.cat([b3, b7, b15, mag3, mag15, torch.abs(b3 - b7)], dim=1)

        # 2) Noise removal is allowed only away from structural edges and only
        # by attenuating the finest symmetric source band.
        denoise_logits = self.blur7(self.denoise_head(torch.cat([features, even_cues], dim=1)))
        denoise_strength = 0.45 * torch.sigmoid(denoise_logits)
        denoise_delta = -material_support * denoise_strength * (radiometry - b3)
        denoised = torch.clamp(radiometry + denoise_delta, 0.0, 1.0)

        # 3) Structural edges use a zero-phase symmetric band.  The strength
        # predictor sees only even optical cues, preventing polarity-dependent
        # free edge painting.
        edge_strength = 1.10 * torch.sigmoid(self.blur7(self.edge_head(even_cues)))
        edge_candidate = denoised - self.blur7(denoised)
        edge_delta = torch.clamp(edge_support * edge_strength * edge_candidate, -0.12, 0.12)
        edge_base = torch.clamp(denoised + edge_delta, 0.0, 1.0)

        # 4) Material detail is source-supported and explicitly excluded from
        # structural edges.  Positive strengths prevent the texture stage from
        # becoming a second smoothing path.
        t3 = self.blur3(edge_base)
        t7 = self.blur7(edge_base)
        t15 = self.blur15(edge_base)
        texture_candidates = torch.cat([edge_base - t3, t3 - t7, t7 - t15], dim=1)
        texture_features = torch.cat(
            [features, edge_base, texture_candidates.abs(), material_support, denoise_strength, edge_support], dim=1,
        )
        texture_logits = self.blur15(self.texture_head(texture_features))
        texture_coefficients = 1.20 * torch.sigmoid(texture_logits)
        coefficient_sum = texture_coefficients.sum(dim=1, keepdim=True).clamp_min(1.20)
        texture_coefficients = texture_coefficients * (1.20 / coefficient_sum)
        texture_delta = torch.clamp(
            material_support * (texture_coefficients * texture_candidates).sum(dim=1, keepdim=True),
            -0.18,
            0.18,
        )
        detail_delta = denoise_delta + texture_delta
        output = torch.clamp(edge_base + texture_delta, 0.0, 1.0)
        correction = torch.clamp(output - raw, -0.35, 0.35)
        output = torch.clamp(raw + correction, 0.0, 1.0)

        zero = torch.zeros_like(raw)
        return {
            "output": output,
            "low_delta": low_delta,
            "denoise_delta": denoise_delta,
            "detail_delta": detail_delta,
            "texture_delta": texture_delta,
            "edge_delta": edge_delta,
            "correction": correction,
            "gain_delta": gain_delta,
            "bias_delta": bias_delta,
            "denoise_strength": denoise_strength,
            "edge_strength": edge_strength,
            "edge_support": edge_support,
            "material_support": material_support,
            "texture_coefficients": texture_coefficients,
            "texture_candidates": texture_candidates,
            # Compatibility diagnostics are explicit zeros: R100 has no
            # transport or auxiliary geometry output by construction.
            "transport_delta": zero,
            "transport_offset_px": zero,
            "transport_dx_px": zero,
            "transport_dy_px": zero,
            "geometry_logits": zero,
            "geometry_probability": zero,
            "geometry_boundary_support": edge_support,
            "raw_low": b15,
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


def build_model(base: int = 24) -> CausalOperatorNet:
    return CausalOperatorNet(base=base)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def architecture_contract(model: CausalOperatorNet) -> dict[str, Any]:
    return {
        "class_name": type(model).__name__,
        "parameter_count": count_parameters(model),
        "normalization_layers": 0,
        "global_pooling_layers": 0,
        "alignment_multiple": model.alignment_multiple,
        "minimum_halo_px": model.minimum_halo_px,
        "random_initialization_only": True,
        "spatial_transport_exists": False,
        "free_image_residual_exists": False,
        "stage_order": ["radiometry", "flat_denoise", "symmetric_edge", "material_texture"],
        "radiometry_is_broad": True,
        "edge_predictor_uses_even_cues_only": True,
        "edge_operation_is_zero_phase": True,
        "texture_excludes_structural_edges": True,
        "texture_is_source_supported": True,
        "texture_strength_is_nonnegative": True,
        "combined_correction_bound": 0.35,
        "edge_correction_bound": 0.12,
        "texture_correction_bound": 0.18,
        "detail_subbands": 3,
    }
