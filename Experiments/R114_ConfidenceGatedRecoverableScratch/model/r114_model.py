"""Tile-safe, single-image R114 geometry/confidence controller.

This module implements Controller Viability Probe only.  It intentionally has
no renderer, free image residual, raw-gradient support floor, inherited
checkpoint, global pooling/FFT, or normalization over spatial dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
from typing import Iterable

import torch
from torch import nn
import torch.nn.functional as F


@dataclass(frozen=True)
class ModelConfig:
    """Architecture values that are safe to override in small probes/tests."""

    in_channels: int = 1
    base_channels: int = 48
    dilations: tuple[int, ...] = (1, 2, 4, 8, 8, 4, 2, 1)
    blur_scales_px: tuple[float, ...] = (0.8, 1.6, 3.2, 6.4)
    normalization: str = "channel_only_rms"
    minimum_halo_px: int = 192
    residual_scale_init: float = 0.10
    head_weight_std: float = 0.02
    probability_epsilon: float = 1.0e-6

    def __post_init__(self) -> None:
        if self.in_channels != 1:
            raise ValueError("R114 currently accepts one grayscale image channel")
        if self.base_channels < 4:
            raise ValueError("base_channels must be at least 4")
        if not self.dilations or any(int(value) < 1 for value in self.dilations):
            raise ValueError("dilations must contain positive integers")
        if not self.blur_scales_px or any(float(value) <= 0 for value in self.blur_scales_px):
            raise ValueError("blur_scales_px must contain positive values")
        if not (0 < self.residual_scale_init <= 1):
            raise ValueError("residual_scale_init must be in (0, 1]")
        if self.head_weight_std <= 0:
            raise ValueError("head_weight_std must be positive")
        if self.normalization not in {"channel_only_rms", "none"}:
            raise ValueError("normalization must be channel_only_rms or none")
        if self.minimum_halo_px < self.exact_receptive_field_radius_px:
            raise ValueError(
                "minimum_halo_px is smaller than the exact receptive-field radius "
                f"{self.exact_receptive_field_radius_px}"
            )

    @property
    def exact_receptive_field_radius_px(self) -> int:
        blur_radius = max(1, int(math.ceil(3 * max(self.blur_scales_px))))
        return 2 * blur_radius + 1 + 2 * sum(self.dilations)

    @classmethod
    def from_json(cls, path: str | Path) -> "ModelConfig":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            in_channels=int(payload["input_channels"]),
            base_channels=int(payload["base_channels"]),
            dilations=tuple(int(value) for value in payload["dilations"]),
            blur_scales_px=tuple(float(value) for value in payload["blur_scales_px"]),
            normalization=str(payload["normalization"]),
            minimum_halo_px=int(payload["minimum_halo_px"]),
        )


def _safe_pad(value: torch.Tensor, pad: int) -> torch.Tensor:
    if pad <= 0:
        return value
    mode = "reflect" if min(value.shape[-2:]) > pad else "replicate"
    return F.pad(value, (pad, pad, pad, pad), mode=mode)


class LocalConv2d(nn.Module):
    """Convolution with explicit local padding and no patch-wide statistics."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3,
                 dilation: int = 1, bias: bool = True):
        super().__init__()
        if kernel_size % 2 != 1:
            raise ValueError("LocalConv2d requires an odd kernel size")
        self.pad = dilation * (kernel_size // 2)
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size,
            padding=0,
            dilation=dilation,
            bias=bias,
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.conv(_safe_pad(value, self.pad))


class GaussianBlur(nn.Module):
    """Fixed separable local Gaussian cue; not a learned smoothing output."""

    def __init__(self, sigma: float):
        super().__init__()
        self.sigma = float(sigma)
        self.radius = max(1, int(math.ceil(3 * self.sigma)))
        axis = torch.arange(-self.radius, self.radius + 1, dtype=torch.float32)
        kernel = torch.exp(-0.5 * (axis / self.sigma).square())
        kernel = kernel / kernel.sum()
        self.register_buffer("horizontal", kernel.view(1, 1, 1, -1))
        self.register_buffer("vertical", kernel.view(1, 1, -1, 1))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        mode = "reflect" if min(value.shape[-2:]) > self.radius else "replicate"
        horizontal = F.pad(value, (self.radius, self.radius, 0, 0), mode=mode)
        horizontal = F.conv2d(horizontal, self.horizontal.to(dtype=value.dtype))
        vertical = F.pad(horizontal, (0, 0, self.radius, self.radius), mode=mode)
        return F.conv2d(vertical, self.vertical.to(dtype=value.dtype))


def finite_differences(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Forward local differences with output size preserved."""

    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0), mode="replicate")
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1), mode="replicate")
    return gx, gy


class LocalCues(nn.Module):
    """R109-derived local cues without any forced gate or global statistic."""

    def __init__(self, blur_scales_px: Iterable[float], epsilon: float):
        super().__init__()
        scales = tuple(float(value) for value in blur_scales_px)
        self.blurs = nn.ModuleList(GaussianBlur(value) for value in scales)
        self.context = GaussianBlur(max(scales))
        self.epsilon = float(epsilon)
        # raw + blurs + high passes + gx/gy/magnitude + local mean/scale/normalized
        self.channels = 1 + 2 * len(scales) + 6
        # local_scale applies the largest context blur to a residual that
        # already contains the largest blur, so its conservative radius is 2R.
        self.maximum_radius = 2 * max(layer.radius for layer in self.blurs)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        blurred = [layer(value) for layer in self.blurs]
        high_passes = [value - item for item in blurred]
        gx, gy = finite_differences(value)
        magnitude = torch.sqrt(gx.square() + gy.square() + self.epsilon)
        local_mean = blurred[-1]
        local_scale = torch.sqrt(
            self.context((value - local_mean).square()) + (2.0 / 255.0) ** 2
        )
        normalized = (value - local_mean) / (local_scale + 2.0 / 255.0)
        # Smoothly limit exceptional noise without a terminal feature tanh.
        normalized = normalized / torch.sqrt(1.0 + normalized.square() / 16.0)
        return torch.cat(
            [value, *blurred, *high_passes, gx, gy, magnitude,
             local_mean, local_scale, normalized],
            dim=1,
        )


class ChannelRMSNorm(nn.Module):
    """Normalize channels independently at each pixel, never over H/W."""

    def __init__(self, channels: int, epsilon: float = 1.0e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(1, channels, 1, 1))
        self.epsilon = float(epsilon)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        inverse_rms = torch.rsqrt(value.square().mean(dim=1, keepdim=True) + self.epsilon)
        return value * inverse_rms * self.weight


class ResidualBlock(nn.Module):
    """Normalization-free residual block with a learned, bounded layer scale."""

    def __init__(self, channels: int, dilation: int, scale_init: float,
                 normalization: str):
        super().__init__()
        self.first_norm = ChannelRMSNorm(channels) if normalization == "channel_only_rms" else nn.Identity()
        self.second_norm = ChannelRMSNorm(channels) if normalization == "channel_only_rms" else nn.Identity()
        self.first = LocalConv2d(channels, channels, dilation=dilation)
        self.second = LocalConv2d(channels, channels, dilation=dilation)
        initial = math.log(scale_init / (1.0 - scale_init))
        self.scale_logit = nn.Parameter(torch.full((1, channels, 1, 1), initial))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        residual = self.first(F.silu(self.first_norm(value)))
        residual = self.second(F.silu(self.second_norm(residual)))
        return F.silu(value + torch.sigmoid(self.scale_logit) * residual)


@dataclass(frozen=True)
class ControllerOutput:
    """R114 controller maps.

    ``recoverability_uncertainty`` has two channels: channel 0 is recoverable
    probability and channel 1 is uncertainty.  They are a softmax pair and
    therefore sum to one at every pixel.
    """

    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    boundary_confidence: torch.Tensor
    correction_need: torch.Tensor
    recoverability_uncertainty: torch.Tensor

    @property
    def recoverability(self) -> torch.Tensor:
        return self.recoverability_uncertainty[:, 0:1]

    @property
    def uncertainty(self) -> torch.Tensor:
        return self.recoverability_uncertainty[:, 1:2]

    @property
    def geometry_gate(self) -> torch.Tensor:
        return self.boundary_confidence * self.correction_need

    @property
    def detail_gate(self) -> torch.Tensor:
        return self.geometry_gate * self.recoverability


class R114Controller(nn.Module):
    """Single-image, fully local geometry/confidence estimator."""

    def __init__(self, config: ModelConfig | None = None):
        super().__init__()
        self.config = config or ModelConfig()
        self.cues = LocalCues(self.config.blur_scales_px, self.config.probability_epsilon)
        self.stem = LocalConv2d(self.cues.channels, self.config.base_channels)
        self.tower = nn.Sequential(*[
            ResidualBlock(
                self.config.base_channels,
                int(dilation),
                self.config.residual_scale_init,
                self.config.normalization,
            )
            for dilation in self.config.dilations
        ])
        channels = self.config.base_channels
        self.sdf_head = nn.Conv2d(channels, 1, 1)
        self.normal_head = nn.Conv2d(channels, 2, 1)
        self.boundary_confidence_head = nn.Conv2d(channels, 1, 1)
        self.correction_need_head = nn.Conv2d(channels, 1, 1)
        self.recoverability_uncertainty_head = nn.Conv2d(channels, 2, 1)
        self._initialize()

    @property
    def minimum_halo_px(self) -> int:
        return self.config.minimum_halo_px

    @property
    def exact_receptive_field_radius_px(self) -> int:
        return self.config.exact_receptive_field_radius_px

    def _initialize(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

        # Heads deliberately receive small non-zero weights.  Zero heads made
        # the previous controller input-insensitive at initialization.
        heads = (
            self.sdf_head,
            self.normal_head,
            self.boundary_confidence_head,
            self.correction_need_head,
            self.recoverability_uncertainty_head,
        )
        for head in heads:
            nn.init.normal_(head.weight, mean=0.0, std=self.config.head_weight_std)
            nn.init.zeros_(head.bias)
        nn.init.constant_(self.boundary_confidence_head.bias, -1.5)
        nn.init.constant_(self.correction_need_head.bias, -1.5)

    def forward(self, value: torch.Tensor) -> ControllerOutput:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("expected input shape [batch, 1, height, width]")
        if not value.is_floating_point():
            raise TypeError("R114 input must be floating point")

        features = self.tower(F.silu(self.stem(self.cues(value))))
        # Keep the small physical heads in FP32 even when the local backbone
        # later runs under BF16.  In particular, normalizing two nearly-zero
        # BF16 normal components can rotate the unit vector appreciably at
        # initialization even though all scalar maps remain close.
        with torch.autocast(device_type=value.device.type, enabled=False):
            head_features = features.float()
            normalized_sdf = self.sdf_head(head_features)
            normal_raw = self.normal_head(head_features)
            normal = F.normalize(normal_raw, p=2.0, dim=1, eps=1.0e-6)
            boundary_confidence = torch.sigmoid(self.boundary_confidence_head(head_features))
            correction_need = torch.sigmoid(self.correction_need_head(head_features))
            recoverability_uncertainty = torch.softmax(
                self.recoverability_uncertainty_head(head_features),
                dim=1,
            )
        return ControllerOutput(
            normalized_sdf=normalized_sdf,
            normal_x=normal[:, 0:1],
            normal_y=normal[:, 1:2],
            boundary_confidence=boundary_confidence,
            correction_need=correction_need,
            recoverability_uncertainty=recoverability_uncertainty,
        )


def build_model(config: ModelConfig | None = None) -> R114Controller:
    """Construct a new randomly initialized controller; no checkpoint is read."""

    if config is None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "model.json"
        config = ModelConfig.from_json(config_path) if config_path.exists() else ModelConfig()
    return R114Controller(config)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def forward_tiled(model: R114Controller, value: torch.Tensor, core_size: int,
                  halo: int | None = None) -> ControllerOutput:
    """Run the local controller on overlapping tiles and stitch core regions.

    This helper is intentionally simple and differentiable.  ``halo`` may be
    larger than the exact receptive-field radius but never smaller.
    """

    if value.ndim != 4 or value.shape[1] != 1:
        raise ValueError("expected input shape [batch, 1, height, width]")
    if core_size < 1:
        raise ValueError("core_size must be positive")
    required = model.minimum_halo_px
    actual_halo = required if halo is None else int(halo)
    if actual_halo < required:
        raise ValueError(f"halo {actual_halo} is smaller than required {required}")

    height, width = value.shape[-2:]
    canvases: dict[str, torch.Tensor] = {}
    for y0 in range(0, height, core_size):
        y1 = min(y0 + core_size, height)
        tile_y0 = max(0, y0 - actual_halo)
        tile_y1 = min(height, y1 + actual_halo)
        for x0 in range(0, width, core_size):
            x1 = min(x0 + core_size, width)
            tile_x0 = max(0, x0 - actual_halo)
            tile_x1 = min(width, x1 + actual_halo)
            tile_output = model(value[..., tile_y0:tile_y1, tile_x0:tile_x1])
            for item in fields(tile_output):
                name = item.name
                tensor = getattr(tile_output, name)
                if name not in canvases:
                    canvases[name] = tensor.new_empty(
                        tensor.shape[0], tensor.shape[1], height, width
                    )
                crop_y0, crop_y1 = y0 - tile_y0, y1 - tile_y0
                crop_x0, crop_x1 = x0 - tile_x0, x1 - tile_x0
                canvases[name][..., y0:y1, x0:x1] = tensor[
                    ..., crop_y0:crop_y1, crop_x0:crop_x1
                ]
    return ControllerOutput(**canvases)
