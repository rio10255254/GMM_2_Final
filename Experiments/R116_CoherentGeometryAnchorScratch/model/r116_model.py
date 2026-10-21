"""R116 single-image coherent geometry-anchor reconstruction model.

The model is intentionally local and scratch-only.  It does not load a
checkpoint, use patch-wide statistics, or expose a free image residual.  Four
independent trainable paths estimate boundary coordinates, width, normal shift,
and evidence-bound detail from shared fixed image cues.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
from typing import Iterable, Mapping

import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class R116Config:
    input_channels: int = 1
    base_channels: int = 48
    action_channels: int = 32
    detail_channels: int = 24
    detector_dilations: tuple[int, ...] = (1, 2, 4, 8, 8, 4, 2, 1)
    action_dilations: tuple[int, ...] = (1, 2, 4, 2, 1)
    detail_dilations: tuple[int, ...] = (1, 2, 4, 2, 1)
    blur_scales_px: tuple[float, ...] = (0.8, 1.6, 3.2, 6.4)
    profile_offsets_px: tuple[float, ...] = (-12, -9, -6, -3, 0, 3, 6, 9, 12)
    coherence_offsets_px: tuple[float, ...] = (-6, -3, 0, 3, 6)
    coherence_sigma_px: float = 4.0
    coherence_strength: float = 0.8
    maximum_predicted_sdf_px: float = 12.0
    minimum_predicted_band_support: float = 0.25
    maximum_normal_shift_px: float = 1.5
    minimum_width_gain: float = 1.0
    maximum_width_gain: float = 3.5
    local_range_window_px: int = 21
    low_frequency_anchor_sigma_px: float = 3.2
    maximum_detail_delta_gray: float = 18.0
    maximum_detail_basis_gain: float = 1.5
    initial_width_amount_bias: float = -1.5
    initial_action_confidence_bias: float = -1.5
    initial_detail_confidence_bias: float = -1.5
    minimum_halo_px: int = 224
    alignment_multiple: int = 8
    normalization: str = "none"

    def __post_init__(self) -> None:
        if self.input_channels != 1:
            raise ValueError("R116 accepts one grayscale channel")
        if min(self.base_channels, self.action_channels, self.detail_channels) < 4:
            raise ValueError("all channel counts must be at least four")
        for name in ("detector_dilations", "action_dilations", "detail_dilations"):
            values = getattr(self, name)
            if not values or any(int(value) < 1 for value in values):
                raise ValueError(f"{name} must contain positive integers")
        if len(self.blur_scales_px) < 3 or any(float(value) <= 0 for value in self.blur_scales_px):
            raise ValueError("at least three positive blur scales are required")
        if not self.profile_offsets_px or 0.0 not in self.profile_offsets_px:
            raise ValueError("profile offsets must include zero")
        if not self.coherence_offsets_px or 0.0 not in self.coherence_offsets_px:
            raise ValueError("coherence offsets must include zero")
        if not (0.0 <= self.coherence_strength <= 1.0):
            raise ValueError("coherence strength must be in [0, 1]")
        if self.coherence_sigma_px <= 0:
            raise ValueError("coherence sigma must be positive")
        if self.maximum_predicted_sdf_px <= 0 or self.maximum_normal_shift_px <= 0:
            raise ValueError("SDF and shift limits must be positive")
        if not (0.0 <= self.minimum_predicted_band_support <= 1.0):
            raise ValueError("minimum predicted-band support must be in [0, 1]")
        if not (0 < self.minimum_width_gain < self.maximum_width_gain):
            raise ValueError("width-gain bounds must be ordered and positive")
        if self.local_range_window_px < 3 or self.local_range_window_px % 2 != 1:
            raise ValueError("local range window must be an odd integer >= 3")
        if self.low_frequency_anchor_sigma_px <= 0:
            raise ValueError("low-frequency anchor sigma must be positive")
        if self.maximum_detail_delta_gray <= 0 or self.maximum_detail_basis_gain <= 0:
            raise ValueError("detail bounds must be positive")
        for name in (
            "initial_width_amount_bias",
            "initial_action_confidence_bias",
            "initial_detail_confidence_bias",
        ):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError(f"{name} must be finite")
        if self.minimum_halo_px < 16:
            raise ValueError("minimum halo is implausibly small")
        if self.alignment_multiple < 1:
            raise ValueError("alignment multiple must be positive")
        if self.normalization != "none":
            raise ValueError("R116 forbids learned or spatial normalization")

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "R116Config":
        tuple_fields = {
            "detector_dilations",
            "action_dilations",
            "detail_dilations",
            "blur_scales_px",
            "profile_offsets_px",
            "coherence_offsets_px",
        }
        kwargs = dict(values)
        for name in tuple_fields:
            if name in kwargs:
                kwargs[name] = tuple(kwargs[name])
        allowed = {item.name for item in fields(cls)}
        return cls(**{key: value for key, value in kwargs.items() if key in allowed})


def _safe_pad(value: torch.Tensor, amount: int) -> torch.Tensor:
    if amount <= 0:
        return value
    mode = "reflect" if min(value.shape[-2:]) > amount else "replicate"
    return F.pad(value, (amount, amount, amount, amount), mode=mode)


class LocalConv2d(nn.Module):
    """Explicit local padding; never uses a patch-wide statistic."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3,
                 dilation: int = 1, bias: bool = True):
        super().__init__()
        if kernel_size % 2 != 1:
            raise ValueError("kernel size must be odd")
        self.pad = dilation * (kernel_size // 2)
        self.conv = nn.Conv2d(
            in_channels, out_channels, kernel_size,
            padding=0, dilation=dilation, bias=bias,
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.conv(_safe_pad(value, self.pad))


class GaussianBlur(nn.Module):
    """Fixed separable blur that supports any channel count."""

    def __init__(self, sigma: float):
        super().__init__()
        self.sigma = float(sigma)
        self.radius = max(1, int(math.ceil(3 * self.sigma)))
        axis = torch.arange(-self.radius, self.radius + 1, dtype=torch.float32)
        row = torch.exp(-0.5 * (axis / self.sigma).square())
        row /= row.sum()
        self.register_buffer("horizontal", row.view(1, 1, 1, -1))
        self.register_buffer("vertical", row.view(1, 1, -1, 1))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        channels = value.shape[1]
        horizontal = self.horizontal.to(device=value.device, dtype=value.dtype).expand(channels, 1, 1, -1)
        vertical = self.vertical.to(device=value.device, dtype=value.dtype).expand(channels, 1, -1, 1)
        mode = "reflect" if min(value.shape[-2:]) > self.radius else "replicate"
        result = F.conv2d(
            F.pad(value, (self.radius, self.radius, 0, 0), mode=mode),
            horizontal,
            groups=channels,
        )
        return F.conv2d(
            F.pad(result, (0, 0, self.radius, self.radius), mode=mode),
            vertical,
            groups=channels,
        )


class ResidualBlock(nn.Module):
    def __init__(self, channels: int, dilation: int):
        super().__init__()
        self.a = LocalConv2d(channels, channels, 3, dilation=dilation)
        self.b = LocalConv2d(channels, channels, 3, dilation=dilation)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return F.silu(value + 0.15 * self.b(F.silu(self.a(value))))


class LocalTower(nn.Module):
    def __init__(self, in_channels: int, channels: int, dilations: Iterable[int]):
        super().__init__()
        self.stem = LocalConv2d(in_channels, channels, 3)
        self.blocks = nn.Sequential(*[ResidualBlock(channels, int(value)) for value in dilations])

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.blocks(F.silu(self.stem(value)))


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0), mode="replicate")
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1), mode="replicate")
    return gx, gy


def warp_local(value: torch.Tensor, flow_px: torch.Tensor) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=value.device, dtype=value.dtype),
        torch.linspace(-1, 1, width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    grid = torch.stack((xx, yy), dim=-1).unsqueeze(0).expand(batch, -1, -1, -1).clone()
    grid[..., 0] += flow_px[:, 0] * (2.0 / max(width - 1, 1))
    grid[..., 1] += flow_px[:, 1] * (2.0 / max(height - 1, 1))
    sampled = F.grid_sample(
        value, grid, mode="bilinear", padding_mode="reflection", align_corners=True,
    )
    zero_flow = flow_px.abs().amax(dim=1, keepdim=True) == 0
    # Keep exact identity in the forward pass at zero flow without selecting a
    # branch that disconnects the shift head from its gradient.  The detached
    # correction is numerically exact while the backward path follows sampled.
    return sampled + zero_flow.to(sampled.dtype) * (value - sampled).detach()


def warp_local_many(value: torch.Tensor, flows_px: torch.Tensor) -> torch.Tensor:
    """Sample several local flow fields in one grid-sample call.

    ``flows_px`` is ``[batch, samples, 2, height, width]`` and the result is
    ``[batch, samples, channels, height, width]``.  Keeping the sample axis in
    the batch dimension removes dozens of tiny grid-sample launches from each
    R116 forward pass while retaining the same local operation and gradient.
    """
    if flows_px.ndim != 5 or flows_px.shape[2] != 2:
        raise ValueError("flows_px must be [batch, samples, 2, height, width]")
    batch, samples, _two, height, width = flows_px.shape
    if value.shape[0] != batch or value.shape[-2:] != (height, width):
        raise ValueError("value and flows_px must have matching batch and spatial shapes")
    channels = value.shape[1]
    expanded_value = value[:, None].expand(-1, samples, -1, -1, -1).reshape(
        batch * samples, channels, height, width,
    )
    flat_flow = flows_px.reshape(batch * samples, 2, height, width)
    sampled = warp_local(expanded_value, flat_flow)
    return sampled.reshape(batch, samples, channels, height, width)


class LocalCues(nn.Module):
    def __init__(self, config: R116Config):
        super().__init__()
        self.blurs = nn.ModuleList(GaussianBlur(value) for value in config.blur_scales_px)
        self.context = GaussianBlur(max(config.blur_scales_px))
        self.channels = 1 + 2 * len(config.blur_scales_px) + 6

    def forward(self, raw: torch.Tensor) -> dict[str, object]:
        blurred = [layer(raw) for layer in self.blurs]
        highpasses = [raw - value for value in blurred]
        gx, gy = gradients(raw)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-8)
        local_mean = blurred[-1]
        local_scale = torch.sqrt(self.context((raw - local_mean).square()) + (2.0 / 255.0) ** 2)
        normalized = (raw - local_mean) / (local_scale + 2.0 / 255.0)
        normalized = normalized / torch.sqrt(1.0 + normalized.square() / 16.0)
        features = torch.cat(
            [raw, *blurred, *highpasses, gx, gy, magnitude, local_mean, local_scale, normalized],
            dim=1,
        )
        return {
            "features": features,
            "blurred": blurred,
            "highpasses": highpasses,
            "magnitude": magnitude,
            "local_mean": local_mean,
            "local_scale": local_scale,
        }


@dataclass(frozen=True)
class R116Details:
    output: torch.Tensor
    boundary_logits: torch.Tensor
    boundary_confidence: torch.Tensor
    predicted_sdf_px: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    source_support: torch.Tensor
    width_amount: torch.Tensor
    width_confidence: torch.Tensor
    width_gate: torch.Tensor
    width_gain: torch.Tensor
    shift_amount: torch.Tensor
    shift_confidence: torch.Tensor
    shift_gate: torch.Tensor
    normal_shift: torch.Tensor
    flow: torch.Tensor
    geometry_anchor: torch.Tensor
    width_proposal: torch.Tensor
    width_zero_mean_detail: torch.Tensor
    detail_coefficients: torch.Tensor
    detail_confidence: torch.Tensor
    evidence_detail: torch.Tensor
    bounded_detail: torch.Tensor
    low_frequency_leakage: torch.Tensor
    profile_evidence: torch.Tensor


@dataclass(frozen=True)
class R116Detection:
    boundary_logits: torch.Tensor
    boundary_confidence: torch.Tensor
    predicted_sdf_px: torch.Tensor


class R116Model(nn.Module):
    def __init__(self, config: R116Config | None = None):
        super().__init__()
        self.config = config or load_config()
        self.minimum_halo_px = int(self.config.minimum_halo_px)
        self.alignment_multiple = int(self.config.alignment_multiple)
        self.cues = LocalCues(self.config)
        self.detector = LocalTower(
            self.cues.channels, self.config.base_channels, self.config.detector_dilations,
        )
        self.boundary_head = nn.Conv2d(self.config.base_channels, 1, 1)
        self.sdf_head = nn.Conv2d(self.config.base_channels, 1, 1)

        profile_channels = 2 * len(self.config.profile_offsets_px) + (len(self.config.profile_offsets_px) - 1) + 5
        self.width_tower = LocalTower(profile_channels, self.config.action_channels, self.config.action_dilations)
        self.shift_tower = LocalTower(profile_channels, self.config.action_channels, self.config.action_dilations)
        self.detail_tower = LocalTower(profile_channels, self.config.detail_channels, self.config.detail_dilations)
        self.width_head = nn.Conv2d(self.config.action_channels, 2, 1)
        self.shift_head = nn.Conv2d(self.config.action_channels, 2, 1)
        self.detail_head = nn.Conv2d(self.config.detail_channels, 4, 1)
        self.lowpass = GaussianBlur(self.config.low_frequency_anchor_sigma_px)
        self._initialize_heads()

    def _initialize_heads(self) -> None:
        for head in (self.boundary_head, self.sdf_head, self.width_head, self.shift_head, self.detail_head):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)
        nn.init.constant_(self.boundary_head.bias, -2.0)
        with torch.no_grad():
            self.width_head.bias[0] = float(self.config.initial_width_amount_bias)
            self.width_head.bias[1] = float(self.config.initial_action_confidence_bias)
            self.shift_head.bias[0] = 0.0
            self.shift_head.bias[1] = float(self.config.initial_action_confidence_bias)
            self.detail_head.bias[:3] = 0.0
            self.detail_head.bias[3] = float(self.config.initial_detail_confidence_bias)

    @staticmethod
    def _zero_initialized_fraction(logits: torch.Tensor, initial_bias: float) -> torch.Tensor:
        """Bound to [0, 1], equal zero at initialization, retain a live gradient."""
        baseline = torch.sigmoid(logits.new_tensor(float(initial_bias)))
        raw = (torch.sigmoid(logits) - baseline) / (1.0 - baseline).clamp_min(1.0e-6)
        bounded = raw.clamp(0.0, 1.0)
        return raw + (bounded - raw).detach()

    def parameter_groups(self) -> dict[str, list[nn.Parameter]]:
        return {
            "detector": [*self.detector.parameters(), *self.boundary_head.parameters(), *self.sdf_head.parameters()],
            "width": [*self.width_tower.parameters(), *self.width_head.parameters()],
            "shift": [*self.shift_tower.parameters(), *self.shift_head.parameters()],
            "detail": [*self.detail_tower.parameters(), *self.detail_head.parameters()],
        }

    def detector_parameters(self) -> list[nn.Parameter]:
        return self.parameter_groups()["detector"]

    def width_parameters(self) -> list[nn.Parameter]:
        return self.parameter_groups()["width"]

    def shift_parameters(self) -> list[nn.Parameter]:
        return self.parameter_groups()["shift"]

    def detail_parameters(self) -> list[nn.Parameter]:
        return self.parameter_groups()["detail"]

    def _normal_profile_evidence(
        self,
        raw: torch.Tensor,
        predicted_sdf_px: torch.Tensor,
        normal_x: torch.Tensor,
        normal_y: torch.Tensor,
        boundary: torch.Tensor,
        magnitude: torch.Tensor,
        local_mean: torch.Tensor,
        local_scale: torch.Tensor,
    ) -> torch.Tensor:
        center = -predicted_sdf_px.clamp(
            -self.config.maximum_predicted_sdf_px,
            self.config.maximum_predicted_sdf_px,
        )
        center_flow = torch.cat((center * normal_x, center * normal_y), dim=1)
        centered = warp_local(torch.cat((local_mean, local_scale), dim=1), center_flow)
        centered_mean = centered[:, 0:1]
        centered_scale = centered[:, 1:2].clamp_min(2.0 / 255.0)
        offsets = raw.new_tensor(self.config.profile_offsets_px).view(1, -1, 1, 1, 1)
        normal = torch.cat((normal_x, normal_y), dim=1)
        flows = center_flow[:, None] + offsets * normal[:, None]
        sampled = warp_local_many(raw, flows)[:, :, 0]
        normalized = (sampled - centered_mean) / (centered_scale + 2.0 / 255.0)
        normalized = normalized / torch.sqrt(1.0 + normalized.square() / 16.0)
        differences = sampled[:, 1:] - sampled[:, :-1]
        magnitude_ratio = magnitude / (local_scale + 2.0 / 255.0)
        return torch.cat(
            [
                sampled,
                normalized,
                differences,
                boundary,
                magnitude_ratio.clamp(0.0, 8.0),
                predicted_sdf_px / self.config.maximum_predicted_sdf_px,
                centered_scale,
                raw,
            ],
            dim=1,
        )

    def _tangent_coherence(
        self,
        value: torch.Tensor,
        normal_x: torch.Tensor,
        normal_y: torch.Tensor,
        support: torch.Tensor,
    ) -> torch.Tensor:
        tangent_x, tangent_y = -normal_y, normal_x
        sigma = float(self.config.coherence_sigma_px)
        offsets = value.new_tensor(self.config.coherence_offsets_px).view(1, -1, 1, 1, 1)
        tangent = torch.cat((tangent_x, tangent_y), dim=1)
        flows = offsets * tangent[:, None]
        packed = torch.cat((value, support, normal_x, normal_y), dim=1)
        sampled = warp_local_many(packed, flows)
        sampled_value = sampled[:, :, 0:1]
        sampled_support = sampled[:, :, 1:2]
        sampled_nx = sampled[:, :, 2:3]
        sampled_ny = sampled[:, :, 3:4]
        orientation = (
            sampled_nx * normal_x[:, None] + sampled_ny * normal_y[:, None]
        ).abs().clamp(0.0, 1.0).pow(4)
        spatial = torch.exp(-0.5 * (offsets / sigma).square())
        weight = sampled_support * orientation * spatial
        numerator = (weight * sampled_value).sum(dim=1)
        denominator = weight.sum(dim=1)
        coherent = numerator / denominator.clamp_min(1.0e-6)
        valid = denominator > 1.0e-5
        coherent = torch.where(valid, coherent, value)
        blend = (float(self.config.coherence_strength) * support).clamp(0.0, 1.0)
        return value + blend * (coherent - value)

    def _width_transform(self, value: torch.Tensor, gain: torch.Tensor) -> torch.Tensor:
        radius = self.config.local_range_window_px // 2
        local_max = F.max_pool2d(value, self.config.local_range_window_px, 1, radius)
        local_min = -F.max_pool2d(-value, self.config.local_range_window_px, 1, radius)
        dynamic = (local_max - local_min).clamp_min(2.0 / 255.0)
        unit = ((value - local_min) / dynamic).clamp(1.0e-3, 1.0 - 1.0e-3)
        corrected = torch.sigmoid(gain * (torch.log(unit) - torch.log1p(-unit)))
        transformed = local_min + dynamic * corrected
        identity = gain == 1.0
        return transformed + identity.to(transformed.dtype) * (value - transformed).detach()

    def _forward_aligned(self, value: torch.Tensor) -> R116Details:
        raw = value.float().clamp(0.0, 1.0)
        cues = self.cues(raw)
        detector_features = self.detector(cues["features"])
        boundary_logits = self.boundary_head(detector_features)
        boundary = torch.sigmoid(boundary_logits)
        predicted_sdf_px = float(self.config.maximum_predicted_sdf_px) * torch.tanh(
            self.sdf_head(detector_features)
        )

        smooth_gx, smooth_gy = gradients(cues["blurred"][1])
        smooth_magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1.0e-8)
        normal_x = smooth_gx / smooth_magnitude
        normal_y = smooth_gy / smooth_magnitude
        magnitude = cues["magnitude"]
        local_scale = cues["local_scale"]
        source_support = ((magnitude / (local_scale + 2.0 / 255.0) - 0.05) / 1.10).clamp(0.0, 1.0)
        source_support = torch.maximum(
            source_support,
            0.85 * F.max_pool2d(boundary, 9, stride=1, padding=4),
        ).clamp(0.0, 1.0)
        predicted_band = torch.exp(-predicted_sdf_px.abs() / 3.0)
        predicted_support = (
            float(self.config.minimum_predicted_band_support)
            + (1.0 - float(self.config.minimum_predicted_band_support)) * predicted_band
        )
        boundary_support = (source_support * boundary * predicted_support).clamp(0.0, 1.0)

        profile = self._normal_profile_evidence(
            raw,
            predicted_sdf_px,
            normal_x,
            normal_y,
            boundary,
            magnitude,
            cues["local_mean"],
            local_scale,
        )

        width_logits = self.width_head(self.width_tower(profile))
        width_fraction = self._zero_initialized_fraction(
            width_logits[:, 0:1], self.config.initial_width_amount_bias,
        )
        width_amount = (float(self.config.maximum_width_gain) - 1.0) * width_fraction
        width_confidence = torch.sigmoid(width_logits[:, 1:2])
        width_gate = (boundary_support * width_confidence).clamp(0.0, 1.0)
        coherent_width_amount = self._tangent_coherence(
            width_amount, normal_x, normal_y, width_gate,
        )
        width_gain = (
            1.0 + width_gate * coherent_width_amount
        ).clamp(float(self.config.minimum_width_gain), float(self.config.maximum_width_gain))

        shift_logits = self.shift_head(self.shift_tower(profile))
        shift_amount = float(self.config.maximum_normal_shift_px) * torch.tanh(shift_logits[:, 0:1])
        shift_confidence = torch.sigmoid(shift_logits[:, 1:2])
        shift_gate = (boundary_support * shift_confidence).clamp(0.0, 1.0)
        coherent_shift_amount = self._tangent_coherence(
            shift_amount, normal_x, normal_y, shift_gate,
        )
        normal_shift = shift_gate * coherent_shift_amount
        flow = torch.cat((normal_shift * normal_x, normal_shift * normal_y), dim=1)
        geometry_anchor = warp_local(raw, flow)

        width_proposal = self._width_transform(geometry_anchor, width_gain)
        width_residual = width_proposal - geometry_anchor
        width_zero_mean = width_residual - self.lowpass(width_residual)

        detail_logits = self.detail_head(self.detail_tower(profile))
        detail_coefficients = float(self.config.maximum_detail_basis_gain) * torch.tanh(
            detail_logits[:, :3]
        )
        detail_confidence = torch.sigmoid(detail_logits[:, 3:4])
        anchor_blurs = [self.cues.blurs[index](geometry_anchor) for index in range(3)]
        basis = torch.cat(
            [
                geometry_anchor - anchor_blurs[0],
                anchor_blurs[0] - anchor_blurs[1],
                anchor_blurs[1] - anchor_blurs[2],
            ],
            dim=1,
        )
        evidence_detail = (detail_coefficients * basis).sum(dim=1, keepdim=True)
        detail_gate = (boundary_support * detail_confidence).clamp(0.0, 1.0)
        combined_detail = width_zero_mean + detail_gate * evidence_detail
        combined_detail = combined_detail - self.lowpass(combined_detail)
        cap = float(self.config.maximum_detail_delta_gray) / 255.0
        bounded_detail = cap * torch.tanh(combined_detail / cap)
        # Saturation can re-introduce a small local DC component.  Project the
        # bounded result once more so the final image keeps the geometry
        # anchor's low-frequency appearance rather than merely regularizing it.
        bounded_detail = bounded_detail - self.lowpass(bounded_detail)
        bounded_detail = bounded_detail.clamp(-cap, cap)
        output = (geometry_anchor + bounded_detail).clamp(0.0, 1.0)
        low_frequency_leakage = self.lowpass(output - geometry_anchor)

        return R116Details(
            output=output,
            boundary_logits=boundary_logits,
            boundary_confidence=boundary,
            predicted_sdf_px=predicted_sdf_px,
            normal_x=normal_x,
            normal_y=normal_y,
            source_support=source_support,
            width_amount=width_amount,
            width_confidence=width_confidence,
            width_gate=width_gate,
            width_gain=width_gain,
            shift_amount=shift_amount,
            shift_confidence=shift_confidence,
            shift_gate=shift_gate,
            normal_shift=normal_shift,
            flow=flow,
            geometry_anchor=geometry_anchor,
            width_proposal=width_proposal,
            width_zero_mean_detail=width_zero_mean,
            detail_coefficients=detail_coefficients,
            detail_confidence=detail_confidence,
            evidence_detail=evidence_detail,
            bounded_detail=bounded_detail,
            low_frequency_leakage=low_frequency_leakage,
            profile_evidence=profile,
        )

    def _detect_aligned(self, value: torch.Tensor) -> R116Detection:
        raw = value.float().clamp(0.0, 1.0)
        cues = self.cues(raw)
        features = self.detector(cues["features"])
        boundary_logits = self.boundary_head(features)
        return R116Detection(
            boundary_logits=boundary_logits,
            boundary_confidence=torch.sigmoid(boundary_logits),
            predicted_sdf_px=float(self.config.maximum_predicted_sdf_px) * torch.tanh(
                self.sdf_head(features)
            ),
        )

    def forward_detection(self, value: torch.Tensor) -> R116Detection:
        """Run only the boundary-coordinate path for its isolated stages."""
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("R116 expects [batch, 1, height, width]")
        height, width = value.shape[-2:]
        pad_h = (-height) % self.alignment_multiple
        pad_w = (-width) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if height > pad_h and width > pad_w else "replicate"
            result = self._detect_aligned(F.pad(value, (0, pad_w, 0, pad_h), mode=mode))
            return R116Detection(
                result.boundary_logits[..., :height, :width],
                result.boundary_confidence[..., :height, :width],
                result.predicted_sdf_px[..., :height, :width],
            )
        return self._detect_aligned(value)

    def forward_details(self, value: torch.Tensor) -> R116Details:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("R116 expects [batch, 1, height, width]")
        height, width = value.shape[-2:]
        pad_h = (-height) % self.alignment_multiple
        pad_w = (-width) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if height > pad_h and width > pad_w else "replicate"
            padded = F.pad(value, (0, pad_w, 0, pad_h), mode=mode)
            result = self._forward_aligned(padded)
            return R116Details(
                *[getattr(result, item.name)[..., :height, :width] for item in fields(result)]
            )
        return self._forward_aligned(value)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def load_config() -> R116Config:
    payload = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
    return R116Config.from_mapping(payload["model"])


def build_model(config: R116Config | None = None) -> R116Model:
    return R116Model(config)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
