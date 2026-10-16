"""Full R114 single-image reconstruction model.

The controller decides where a boundary exists, whether it needs correction,
and whether detail is recoverable.  The renderer can only act through those
learned local gates.  No checkpoint is loaded by this module.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F

from .r114_model import (
    GaussianBlur,
    LocalConv2d,
    LocalCues,
    ModelConfig,
    R114Controller,
    ResidualBlock,
)


ROOT = Path(__file__).resolve().parents[1]
MODEL_CONFIG = json.loads((ROOT / "config" / "model.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ReconstructionOutput:
    output: torch.Tensor
    base_output: torch.Tensor
    delta: torch.Tensor
    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    boundary_confidence: torch.Tensor
    correction_need: torch.Tensor
    recoverability: torch.Tensor
    uncertainty: torch.Tensor
    geometry_gate: torch.Tensor
    detail_gate: torch.Tensor
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    flow: torch.Tensor
    detail_carrier: torch.Tensor
    detail: torch.Tensor


def _warp(value: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=value.device, dtype=value.dtype),
        torch.linspace(-1, 1, width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(batch, -1, -1, -1).clone()
    grid[..., 0] += flow[:, 0] * (2.0 / max(width - 1, 1))
    grid[..., 1] += flow[:, 1] * (2.0 / max(height - 1, 1))
    return F.grid_sample(
        value,
        grid,
        mode="bilinear",
        padding_mode="reflection",
        align_corners=True,
    )


class R114Model(nn.Module):
    """Confidence-gated analytic geometry renderer with optional bounded detail."""

    def __init__(self, detail_enabled: bool = False, compact: bool = False):
        super().__init__()
        base = 16 if compact else int(MODEL_CONFIG["base_channels"])
        dilations = (1, 2, 2, 1) if compact else tuple(int(v) for v in MODEL_CONFIG["dilations"])
        scales = (0.8, 1.6) if compact else tuple(float(v) for v in MODEL_CONFIG["blur_scales_px"])
        controller_config = ModelConfig(
            base_channels=base,
            dilations=dilations,
            blur_scales_px=scales,
        )
        self.controller = R114Controller(controller_config)
        self.cues = LocalCues(scales, 1.0e-6)
        self.renderer_stem = LocalConv2d(self.cues.channels, base)
        self.renderer_tower = nn.Sequential(*[
            ResidualBlock(
                base,
                dilation,
                controller_config.residual_scale_init,
                controller_config.normalization,
            )
            for dilation in dilations
        ])
        self.width_head = nn.Conv2d(base, 1, 1)
        self.shift_head = nn.Conv2d(base, 1, 1)
        self.detail_head = nn.Conv2d(base, 1, 1)
        self.detail_projection = GaussianBlur(float(MODEL_CONFIG["detail"]["zero_local_mean_sigma_px"]))
        self.detail_enabled = bool(detail_enabled)
        self._initialize_renderer()

    def _initialize_renderer(self) -> None:
        modules = [self.renderer_stem, self.renderer_tower]
        for root in modules:
            for module in root.modules():
                if isinstance(module, nn.Conv2d):
                    nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
        for head in (self.width_head, self.shift_head, self.detail_head):
            nn.init.normal_(head.weight, mean=0.0, std=0.01)
            nn.init.zeros_(head.bias)
        # Start near identity without making either geometry head input-blind.
        minimum = float(MODEL_CONFIG["minimum_width_gain"])
        maximum = float(MODEL_CONFIG["maximum_width_gain"])
        fraction = max(min((1.03 - minimum) / (maximum - minimum), 1 - 1e-5), 1e-5)
        nn.init.constant_(self.width_head.bias, math.log(fraction / (1.0 - fraction)))

    @property
    def minimum_halo_px(self) -> int:
        renderer_radius = self.cues.maximum_radius + 1 + 2 * sum(
            block.first.conv.dilation[0] for block in self.renderer_tower
        )
        range_radius = int(MODEL_CONFIG["local_range_window_px"]) // 2
        detail_radius = self.detail_projection.radius
        shift_margin = math.ceil(float(MODEL_CONFIG["maximum_normal_shift_px"]))
        return max(self.controller.minimum_halo_px, renderer_radius) + range_radius + detail_radius + shift_margin

    def controller_parameters(self) -> list[nn.Parameter]:
        return list(self.controller.parameters())

    def geometry_parameters(self) -> list[nn.Parameter]:
        return [
            *self.renderer_stem.parameters(),
            *self.renderer_tower.parameters(),
            *self.width_head.parameters(),
            *self.shift_head.parameters(),
        ]

    def detail_parameters(self) -> list[nn.Parameter]:
        return list(self.detail_head.parameters())

    def set_detail_enabled(self, enabled: bool) -> None:
        self.detail_enabled = bool(enabled)

    def forward_details(self, value: torch.Tensor) -> ReconstructionOutput:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("expected input shape [batch, 1, height, width]")
        raw = value.clamp(0, 1)
        controller = self.controller(raw)
        renderer = self.renderer_tower(F.silu(self.renderer_stem(self.cues(raw))))

        minimum = float(MODEL_CONFIG["minimum_width_gain"])
        maximum = float(MODEL_CONFIG["maximum_width_gain"])
        width_gain = minimum + (maximum - minimum) * torch.sigmoid(self.width_head(renderer))
        max_shift = float(MODEL_CONFIG["maximum_normal_shift_px"])
        normal_shift = max_shift * torch.tanh(self.shift_head(renderer))

        geometry_gate = controller.geometry_gate
        flow = torch.cat(
            [normal_shift * controller.normal_x, normal_shift * controller.normal_y],
            dim=1,
        )
        warped = _warp(raw, flow * geometry_gate)
        window = int(MODEL_CONFIG["local_range_window_px"])
        radius = window // 2
        local_max = F.max_pool2d(warped, window, stride=1, padding=radius)
        local_min = -F.max_pool2d(-warped, window, stride=1, padding=radius)
        dynamic = (local_max - local_min).clamp_min(2.0 / 255.0)
        unit = ((warped - local_min) / dynamic).clamp(1.0e-4, 1.0 - 1.0e-4)
        sharpened = torch.sigmoid(width_gain * (torch.log(unit) - torch.log1p(-unit)))
        proposal = local_min + dynamic * sharpened
        base_output = raw + geometry_gate * (proposal - raw)

        detail_gate = controller.detail_gate
        bound = float(MODEL_CONFIG["detail"]["maximum_amplitude_gray_levels"]) / 255.0
        detail_carrier = 0.5 * bound * torch.tanh(self.detail_head(renderer)) * detail_gate
        projected_detail = detail_carrier - self.detail_projection(detail_carrier)
        detail = projected_detail if self.detail_enabled else torch.zeros_like(projected_detail)
        output = (base_output + detail).clamp(0, 1)

        return ReconstructionOutput(
            output=output,
            base_output=base_output,
            delta=output - raw,
            normalized_sdf=controller.normalized_sdf,
            normal_x=controller.normal_x,
            normal_y=controller.normal_y,
            boundary_confidence=controller.boundary_confidence,
            correction_need=controller.correction_need,
            recoverability=controller.recoverability,
            uncertainty=controller.uncertainty,
            geometry_gate=geometry_gate,
            detail_gate=detail_gate,
            width_gain=width_gain,
            normal_shift=normal_shift,
            flow=flow,
            detail_carrier=detail_carrier,
            detail=detail,
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def build_full_model(detail_enabled: bool = False, compact: bool = False) -> R114Model:
    return R114Model(detail_enabled=detail_enabled, compact=compact)


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def output_field_names() -> tuple[str, ...]:
    return tuple(item.name for item in fields(ReconstructionOutput))
