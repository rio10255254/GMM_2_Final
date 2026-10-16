"""Independent scratch-only R114 split-reliability reconstruction model.

This module implements the renderer contract recorded by the E020 gate-design
diagnosis and the later oracle boundary-profile action probe.  Width correction
and normal shift have independent reliability heads and independent actuation
gates.  A third, bounded analytic normal-profile action is applied only after
that split geometry base has been completed.  The legacy ``geometry_gate`` is
returned for diagnostics only and is never used to actuate width or shift.

The implementation is deliberately single-image, fully local, and tile safe:
there is no inherited checkpoint, global pooling/FFT, spatial normalization,
or patch-wide statistic.  The new profile renderer has no free image residual
and receives no target image: it can only choose a local midpoint offset,
signed plateau contrast, transition width, and visibility inside a fixed
smooth boundary band.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
from typing import Mapping

import torch
from torch import nn
import torch.nn.functional as F

from .r114_model import LocalConv2d, LocalCues, ModelConfig, ResidualBlock


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SplitProfileConfig:
    """All architecture and bounded-action values for a fresh split model."""

    base_channels: int = 48
    dilations: tuple[int, ...] = (1, 2, 4, 8, 8, 4, 2, 1)
    blur_scales_px: tuple[float, ...] = (0.8, 1.6, 3.2, 6.4)
    normalization: str = "channel_only_rms"
    minimum_halo_px: int = 192
    residual_scale_init: float = 0.10
    head_weight_std: float = 0.02
    local_range_window_px: int = 21
    minimum_width_gain: float = 1.0
    maximum_width_gain: float = 3.5
    maximum_normal_shift_px: float = 1.5
    sdf_unit_scale_px: float = 12.0
    profile_full_strength_radius_px: float = 10.0
    profile_outer_band_radius_px: float = 14.0
    maximum_midpoint_offset_gray_levels: float = 24.0
    maximum_signed_contrast_gray_levels: float = 72.0
    minimum_profile_width_px: float = 0.8
    maximum_profile_width_px: float = 3.5
    initial_profile_width_px: float = 1.35
    maximum_profile_delta_gray_levels: float = 48.0

    def __post_init__(self) -> None:
        if self.base_channels < 4:
            raise ValueError("base_channels must be at least 4")
        if not self.dilations or any(int(value) < 1 for value in self.dilations):
            raise ValueError("dilations must contain positive integers")
        if not self.blur_scales_px or any(float(value) <= 0 for value in self.blur_scales_px):
            raise ValueError("blur_scales_px must contain positive values")
        if self.normalization not in {"channel_only_rms", "none"}:
            raise ValueError("normalization must be channel_only_rms or none")
        if self.local_range_window_px < 3 or self.local_range_window_px % 2 != 1:
            raise ValueError("local_range_window_px must be an odd integer >= 3")
        if not (0 < self.minimum_width_gain < self.maximum_width_gain):
            raise ValueError("width-gain bounds must be positive and ordered")
        if self.maximum_normal_shift_px <= 0:
            raise ValueError("maximum_normal_shift_px must be positive")
        if self.sdf_unit_scale_px <= 0:
            raise ValueError("sdf_unit_scale_px must be positive")
        if not (
            0 < self.profile_full_strength_radius_px
            < self.profile_outer_band_radius_px
        ):
            raise ValueError("profile band radii must be positive and ordered")
        if self.maximum_midpoint_offset_gray_levels <= 0:
            raise ValueError("maximum_midpoint_offset_gray_levels must be positive")
        if self.maximum_signed_contrast_gray_levels <= 0:
            raise ValueError("maximum_signed_contrast_gray_levels must be positive")
        if not (0 < self.minimum_profile_width_px < self.maximum_profile_width_px):
            raise ValueError("profile-width bounds must be positive and ordered")
        if not (
            self.minimum_profile_width_px
            <= self.initial_profile_width_px
            <= self.maximum_profile_width_px
        ):
            raise ValueError("initial_profile_width_px must lie inside its bounds")
        if self.maximum_profile_delta_gray_levels <= 0:
            raise ValueError("maximum_profile_delta_gray_levels must be positive")
        # Reuse the already audited local controller-radius calculation.
        self.controller_config()

    def controller_config(self) -> ModelConfig:
        return ModelConfig(
            base_channels=self.base_channels,
            dilations=self.dilations,
            blur_scales_px=self.blur_scales_px,
            normalization=self.normalization,
            minimum_halo_px=self.minimum_halo_px,
            residual_scale_init=self.residual_scale_init,
            head_weight_std=self.head_weight_std,
        )

    @classmethod
    def from_project_json(cls, path: str | Path | None = None) -> "SplitProfileConfig":
        source = Path(path) if path is not None else ROOT / "config" / "model.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        return cls(
            base_channels=int(payload["base_channels"]),
            dilations=tuple(int(value) for value in payload["dilations"]),
            blur_scales_px=tuple(float(value) for value in payload["blur_scales_px"]),
            normalization=str(payload["normalization"]),
            minimum_halo_px=int(payload["minimum_halo_px"]),
            local_range_window_px=int(payload["local_range_window_px"]),
            minimum_width_gain=float(payload["minimum_width_gain"]),
            maximum_width_gain=float(payload["maximum_width_gain"]),
            maximum_normal_shift_px=float(payload["maximum_normal_shift_px"]),
        )

    @classmethod
    def compact_test_config(cls) -> "SplitProfileConfig":
        return cls(
            base_channels=12,
            dilations=(1, 2, 2, 1),
            blur_scales_px=(0.8, 1.6),
            minimum_halo_px=32,
            local_range_window_px=7,
        )


@dataclass(frozen=True)
class SplitControllerOutput:
    """All learned controller maps, with separate geometry reliabilities."""

    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    boundary_confidence: torch.Tensor
    correction_need: torch.Tensor
    recoverability_uncertainty: torch.Tensor
    width_reliability: torch.Tensor
    shift_reliability: torch.Tensor

    @property
    def recoverability(self) -> torch.Tensor:
        return self.recoverability_uncertainty[:, 0:1]

    @property
    def uncertainty(self) -> torch.Tensor:
        return self.recoverability_uncertainty[:, 1:2]

    @property
    def geometry_gate(self) -> torch.Tensor:
        """Legacy diagnostic only; renderer code must not consume this map."""

        return self.boundary_confidence * self.correction_need

    @property
    def width_gate(self) -> torch.Tensor:
        return self.boundary_confidence * self.correction_need * self.width_reliability

    @property
    def shift_gate(self) -> torch.Tensor:
        return self.boundary_confidence * self.correction_need * self.shift_reliability

@dataclass(frozen=True)
class WidthProfileContext:
    """Stable interface for a local width/profile proposal.

    A future learned analytic normal-profile action may use the SDF, normals,
    and renderer features.  The current bounded local-logit proposal only uses
    ``shifted_base`` and ``width_gain`` but preserves the same interface.
    """

    shifted_base: torch.Tensor
    width_gain: torch.Tensor
    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    renderer_features: torch.Tensor


class WidthProfileAction(nn.Module):
    """Interface for a fully local, tile-safe width proposal."""

    action_radius_px: int

    def forward(self, context: WidthProfileContext) -> torch.Tensor:  # pragma: no cover - interface
        raise NotImplementedError


class LocalLogitWidthProfileAction(WidthProfileAction):
    """Current local width proposal; no smoothing or patch-wide statistic."""

    def __init__(self, window_px: int):
        super().__init__()
        if window_px < 3 or window_px % 2 != 1:
            raise ValueError("window_px must be an odd integer >= 3")
        self.window_px = int(window_px)
        self.action_radius_px = self.window_px // 2

    def forward(self, context: WidthProfileContext) -> torch.Tensor:
        shifted = context.shifted_base
        radius = self.action_radius_px
        local_max = F.max_pool2d(shifted, self.window_px, stride=1, padding=radius)
        local_min = -F.max_pool2d(-shifted, self.window_px, stride=1, padding=radius)
        dynamic = (local_max - local_min).clamp_min(2.0 / 255.0)
        unit = ((shifted - local_min) / dynamic).clamp(1.0e-4, 1.0 - 1.0e-4)
        sharpened = torch.sigmoid(
            context.width_gain * (torch.log(unit) - torch.log1p(-unit))
        )
        return local_min + dynamic * sharpened


@dataclass(frozen=True)
class SplitGeometryOutput:
    """Pure geometry-action result, useful for causal intervention tests."""

    base_output: torch.Tensor
    shifted_base: torch.Tensor
    width_proposal: torch.Tensor
    geometry_gate: torch.Tensor
    width_gate: torch.Tensor
    shift_gate: torch.Tensor
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    effective_width_gain: torch.Tensor
    effective_normal_shift: torch.Tensor
    flow: torch.Tensor


@dataclass(frozen=True)
class ProfileActionOutput:
    """Bounded analytic profile action applied after split geometry."""

    profile_output: torch.Tensor
    profile_midpoint_cue: torch.Tensor
    midpoint_offset: torch.Tensor
    profile_midpoint: torch.Tensor
    signed_plateau_contrast: torch.Tensor
    profile_width: torch.Tensor
    profile_visibility: torch.Tensor
    predicted_sdf_px: torch.Tensor
    profile_band: torch.Tensor
    profile_gate: torch.Tensor
    profile_proposal: torch.Tensor
    profile_proposal_delta: torch.Tensor
    profile_delta: torch.Tensor


@dataclass(frozen=True)
class SplitReconstructionOutput:
    """Complete inference and diagnostic output of the split model."""

    output: torch.Tensor
    base_output: torch.Tensor
    shifted_base: torch.Tensor
    width_proposal: torch.Tensor
    profile_output: torch.Tensor
    profile_midpoint_cue: torch.Tensor
    midpoint_offset: torch.Tensor
    profile_midpoint: torch.Tensor
    signed_plateau_contrast: torch.Tensor
    profile_width: torch.Tensor
    profile_visibility: torch.Tensor
    predicted_sdf_px: torch.Tensor
    profile_band: torch.Tensor
    profile_gate: torch.Tensor
    profile_proposal: torch.Tensor
    profile_proposal_delta: torch.Tensor
    profile_delta: torch.Tensor
    delta: torch.Tensor
    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    boundary_confidence: torch.Tensor
    correction_need: torch.Tensor
    recoverability: torch.Tensor
    uncertainty: torch.Tensor
    width_reliability: torch.Tensor
    shift_reliability: torch.Tensor
    geometry_gate: torch.Tensor
    width_gate: torch.Tensor
    shift_gate: torch.Tensor
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    effective_width_gain: torch.Tensor
    effective_normal_shift: torch.Tensor
    flow: torch.Tensor


def _warp_local(value: torch.Tensor, flow_px: torch.Tensor) -> torch.Tensor:
    """Bilinearly sample a local image using a flow measured in pixels."""

    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, height, device=value.device, dtype=value.dtype),
        torch.linspace(-1.0, 1.0, width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(batch, -1, -1, -1).clone()
    grid[..., 0] += flow_px[:, 0] * (2.0 / max(width - 1, 1))
    grid[..., 1] += flow_px[:, 1] * (2.0 / max(height - 1, 1))
    sampled = F.grid_sample(
        value,
        grid,
        mode="bilinear",
        padding_mode="reflection",
        align_corners=True,
    )
    # grid_sample's nominal identity grid can differ from the input by a few
    # floating-point ulps.  Preserve exact neutral semantics at pixels where
    # the split shift gate made the physical flow exactly zero.
    zero_flow = flow_px.abs().amax(dim=1, keepdim=True) == 0
    return torch.where(zero_flow, value, sampled)


class R114SplitProfileController(nn.Module):
    """Fresh local controller with independent width/shift reliability heads."""

    def __init__(self, config: SplitProfileConfig):
        super().__init__()
        self.config = config
        controller_config = config.controller_config()
        self.cues = LocalCues(config.blur_scales_px, 1.0e-6)
        self.stem = LocalConv2d(self.cues.channels, config.base_channels)
        self.tower = nn.Sequential(*[
            ResidualBlock(
                config.base_channels,
                int(dilation),
                config.residual_scale_init,
                config.normalization,
            )
            for dilation in config.dilations
        ])
        channels = config.base_channels
        self.sdf_head = nn.Conv2d(channels, 1, 1)
        self.normal_head = nn.Conv2d(channels, 2, 1)
        self.boundary_confidence_head = nn.Conv2d(channels, 1, 1)
        self.correction_need_head = nn.Conv2d(channels, 1, 1)
        self.recoverability_uncertainty_head = nn.Conv2d(channels, 2, 1)
        self.width_reliability_head = nn.Conv2d(channels, 1, 1)
        self.shift_reliability_head = nn.Conv2d(channels, 1, 1)
        self.minimum_halo_px = controller_config.minimum_halo_px
        self._initialize()

    def _initialize(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Conv2d):
                nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
        heads = (
            self.sdf_head,
            self.normal_head,
            self.boundary_confidence_head,
            self.correction_need_head,
            self.recoverability_uncertainty_head,
            self.width_reliability_head,
            self.shift_reliability_head,
        )
        for head in heads:
            nn.init.normal_(head.weight, mean=0.0, std=self.config.head_weight_std)
            nn.init.zeros_(head.bias)
        nn.init.constant_(self.boundary_confidence_head.bias, -1.5)
        nn.init.constant_(self.correction_need_head.bias, -1.5)

    def backbone(self, value: torch.Tensor) -> torch.Tensor:
        return self.tower(F.silu(self.stem(self.cues(value))))

    def forward(self, value: torch.Tensor) -> SplitControllerOutput:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("expected input shape [batch, 1, height, width]")
        if not value.is_floating_point():
            raise TypeError("R114 split-model input must be floating point")
        features = self.backbone(value)
        # Keep bounded physical maps in FP32 if the backbone later uses BF16.
        with torch.autocast(device_type=value.device.type, enabled=False):
            head_features = features.float()
            normalized_sdf = self.sdf_head(head_features)
            normal = F.normalize(self.normal_head(head_features), p=2.0, dim=1, eps=1.0e-6)
            boundary = torch.sigmoid(self.boundary_confidence_head(head_features))
            need = torch.sigmoid(self.correction_need_head(head_features))
            recoverability = torch.softmax(
                self.recoverability_uncertainty_head(head_features), dim=1
            )
            width_reliability = torch.sigmoid(self.width_reliability_head(head_features))
            shift_reliability = torch.sigmoid(self.shift_reliability_head(head_features))
        return SplitControllerOutput(
            normalized_sdf=normalized_sdf,
            normal_x=normal[:, 0:1],
            normal_y=normal[:, 1:2],
            boundary_confidence=boundary,
            correction_need=need,
            recoverability_uncertainty=recoverability,
            width_reliability=width_reliability,
            shift_reliability=shift_reliability,
        )


class R114SplitProfileModel(nn.Module):
    """Split-gated geometry renderer, initialized from scratch."""

    def __init__(
        self,
        config: SplitProfileConfig | None = None,
        width_profile_action: WidthProfileAction | None = None,
    ):
        super().__init__()
        self.config = config or SplitProfileConfig.from_project_json()
        self.controller = R114SplitProfileController(self.config)
        self.renderer_cues = LocalCues(self.config.blur_scales_px, 1.0e-6)
        self.renderer_stem = LocalConv2d(self.renderer_cues.channels, self.config.base_channels)
        self.renderer_tower = nn.Sequential(*[
            ResidualBlock(
                self.config.base_channels,
                int(dilation),
                self.config.residual_scale_init,
                self.config.normalization,
            )
            for dilation in self.config.dilations
        ])
        channels = self.config.base_channels
        self.width_head = nn.Conv2d(channels, 1, 1)
        self.shift_head = nn.Conv2d(channels, 1, 1)
        self.profile_midpoint_offset_head = nn.Conv2d(channels, 1, 1)
        self.profile_signed_contrast_head = nn.Conv2d(channels, 1, 1)
        self.profile_width_head = nn.Conv2d(channels, 1, 1)
        self.profile_visibility_head = nn.Conv2d(channels, 1, 1)
        self.width_profile_action = width_profile_action or LocalLogitWidthProfileAction(
            self.config.local_range_window_px
        )
        self._initialize_renderer()

    def _initialize_renderer(self) -> None:
        for root in (self.renderer_stem, self.renderer_tower):
            for module in root.modules():
                if isinstance(module, nn.Conv2d):
                    nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
        for head in (
            self.width_head,
            self.shift_head,
            self.profile_midpoint_offset_head,
            self.profile_signed_contrast_head,
            self.profile_width_head,
        ):
            nn.init.normal_(head.weight, mean=0.0, std=0.01)
            nn.init.zeros_(head.bias)
        # A zero profile-visibility logit maps to exact zero through
        # ``_bounded_profile_visibility`` while retaining a positive one-sided
        # gradient.  This makes every fresh model exactly neutral relative to
        # its already-computed split width+shift base.
        nn.init.zeros_(self.profile_visibility_head.weight)
        nn.init.zeros_(self.profile_visibility_head.bias)
        fraction = (1.03 - self.config.minimum_width_gain) / (
            self.config.maximum_width_gain - self.config.minimum_width_gain
        )
        fraction = max(min(fraction, 1.0 - 1.0e-5), 1.0e-5)
        nn.init.constant_(self.width_head.bias, math.log(fraction / (1.0 - fraction)))
        profile_width_fraction = (
            self.config.initial_profile_width_px - self.config.minimum_profile_width_px
        ) / (
            self.config.maximum_profile_width_px - self.config.minimum_profile_width_px
        )
        profile_width_fraction = max(
            min(profile_width_fraction, 1.0 - 1.0e-5), 1.0e-5
        )
        nn.init.constant_(
            self.profile_width_head.bias,
            math.log(profile_width_fraction / (1.0 - profile_width_fraction)),
        )

    @property
    def minimum_halo_px(self) -> int:
        renderer_radius = self.renderer_cues.maximum_radius + 1 + 2 * sum(
            block.first.conv.dilation[0] for block in self.renderer_tower
        )
        action_radius = int(self.width_profile_action.action_radius_px)
        shift_margin = math.ceil(self.config.maximum_normal_shift_px)
        profile_midpoint_radius = self.config.local_range_window_px // 2
        geometry_radius = renderer_radius + action_radius + shift_margin
        profile_radius = geometry_radius + profile_midpoint_radius
        exact_action_radius = profile_radius
        return max(self.controller.minimum_halo_px, exact_action_radius)

    def parameter_groups(self) -> Mapping[str, list[nn.Parameter]]:
        """Return disjoint atomic groups for staged/alternating optimization."""

        groups = {
            "controller_backbone": [
                *self.controller.stem.parameters(),
                *self.controller.tower.parameters(),
            ],
            "controller_geometry_heads": [
                *self.controller.sdf_head.parameters(),
                *self.controller.normal_head.parameters(),
                *self.controller.boundary_confidence_head.parameters(),
                *self.controller.correction_need_head.parameters(),
            ],
            "recoverability_head": list(
                self.controller.recoverability_uncertainty_head.parameters()
            ),
            "width_reliability_head": list(
                self.controller.width_reliability_head.parameters()
            ),
            "shift_reliability_head": list(
                self.controller.shift_reliability_head.parameters()
            ),
            "renderer_backbone": [
                *self.renderer_stem.parameters(),
                *self.renderer_tower.parameters(),
            ],
            "width_action_head": list(self.width_head.parameters()),
            "shift_action_head": list(self.shift_head.parameters()),
            "profile_midpoint_offset_head": list(
                self.profile_midpoint_offset_head.parameters()
            ),
            "profile_signed_contrast_head": list(
                self.profile_signed_contrast_head.parameters()
            ),
            "profile_width_head": list(self.profile_width_head.parameters()),
            "profile_visibility_head": list(
                self.profile_visibility_head.parameters()
            ),
        }
        return groups

    def reliability_parameters(self) -> list[nn.Parameter]:
        groups = self.parameter_groups()
        return [
            *groups["controller_backbone"],
            *groups["controller_geometry_heads"],
            *groups["width_reliability_head"],
            *groups["shift_reliability_head"],
        ]

    def width_parameters(self) -> list[nn.Parameter]:
        groups = self.parameter_groups()
        return [*groups["renderer_backbone"], *groups["width_action_head"]]

    def shift_parameters(self) -> list[nn.Parameter]:
        groups = self.parameter_groups()
        return [*groups["renderer_backbone"], *groups["shift_action_head"]]

    def profile_parameters(self) -> list[nn.Parameter]:
        """Parameters authorized for the learned bounded-profile probe."""

        groups = self.parameter_groups()
        return [
            *groups["renderer_backbone"],
            *groups["profile_midpoint_offset_head"],
            *groups["profile_signed_contrast_head"],
            *groups["profile_width_head"],
            *groups["profile_visibility_head"],
        ]

    def _renderer_features(self, raw: torch.Tensor) -> torch.Tensor:
        return self.renderer_tower(F.silu(self.renderer_stem(self.renderer_cues(raw))))

    @staticmethod
    def _bounded_profile_visibility(logits: torch.Tensor) -> torch.Tensor:
        """Map a fresh zero logit to exact zero without a dead initial slope.

        ``softplus(0) - log(2)`` is exactly zero to floating-point precision.
        PyTorch's clamp boundary keeps the positive one-sided gradient, so a
        positive visibility target can turn the action on from scratch while
        clear/identity targets can keep it exactly off.
        """

        return torch.clamp(F.softplus(logits) - math.log(2.0), min=0.0, max=1.0)

    def _profile_band(self, predicted_sdf_px: torch.Tensor) -> torch.Tensor:
        """C1 smooth band: one through 10 px, zero from 14 px onward."""

        inner = self.config.profile_full_strength_radius_px
        outer = self.config.profile_outer_band_radius_px
        phase = ((outer - predicted_sdf_px.abs()) / (outer - inner)).clamp(0.0, 1.0)
        return phase.square() * (3.0 - 2.0 * phase)

    def _profile_midpoint_cue(self, value: torch.Tensor) -> torch.Tensor:
        """Raw-derived local plateau midpoint with no patch-wide statistic."""

        window = self.config.local_range_window_px
        radius = window // 2
        # Replication keeps a physical image border neutral; zero padding would
        # invent a dark plateau that is absent from the captured image.
        padded = F.pad(value, (radius, radius, radius, radius), mode="replicate")
        local_max = F.max_pool2d(padded, window, stride=1)
        local_min = -F.max_pool2d(-padded, window, stride=1)
        return 0.5 * (local_max + local_min)

    def apply_profile_action(
        self,
        base_output: torch.Tensor,
        controller: SplitControllerOutput,
        midpoint_offset: torch.Tensor,
        signed_plateau_contrast: torch.Tensor,
        profile_width: torch.Tensor,
        profile_visibility: torch.Tensor,
        midpoint_source: torch.Tensor | None = None,
    ) -> ProfileActionOutput:
        """Apply the oracle-supported analytic action without a free residual.

        Every argument is an inference-time prediction or a local image cue.
        There is deliberately no target/label argument or target-copy path.
        """

        source = base_output if midpoint_source is None else midpoint_source
        midpoint_cue = self._profile_midpoint_cue(source)
        midpoint = (midpoint_cue + midpoint_offset).clamp(0.0, 1.0)
        predicted_sdf_px = controller.normalized_sdf * self.config.sdf_unit_scale_px
        band = self._profile_band(predicted_sdf_px)
        gate = (
            controller.boundary_confidence
            * profile_visibility
            * band
        )
        safe_width = profile_width.clamp(
            self.config.minimum_profile_width_px,
            self.config.maximum_profile_width_px,
        )
        proposal = (
            midpoint
            + 0.5
            * signed_plateau_contrast
            * torch.tanh(predicted_sdf_px / safe_width)
        ).clamp(0.0, 1.0)
        maximum_delta = self.config.maximum_profile_delta_gray_levels / 255.0
        proposal_delta = (proposal - base_output).clamp(-maximum_delta, maximum_delta)
        delta = gate * proposal_delta
        profile_output = (base_output + delta).clamp(0.0, 1.0)
        return ProfileActionOutput(
            profile_output=profile_output,
            profile_midpoint_cue=midpoint_cue,
            midpoint_offset=midpoint_offset,
            profile_midpoint=midpoint,
            signed_plateau_contrast=signed_plateau_contrast,
            profile_width=safe_width,
            profile_visibility=profile_visibility,
            predicted_sdf_px=predicted_sdf_px,
            profile_band=band,
            profile_gate=gate,
            profile_proposal=proposal,
            profile_proposal_delta=proposal_delta,
            profile_delta=delta,
        )

    def apply_geometry(
        self,
        raw: torch.Tensor,
        controller: SplitControllerOutput,
        width_gain: torch.Tensor,
        normal_shift: torch.Tensor,
        renderer_features: torch.Tensor,
    ) -> SplitGeometryOutput:
        """Apply split gates in the contractually required order.

        Shift is completed first.  The profile proposal is then constructed
        from that shifted base, and only ``width_gate`` mixes it into the base.
        ``geometry_gate`` is copied to the output solely for diagnostics.
        """

        width_gate = controller.width_gate
        shift_gate = controller.shift_gate
        effective_width_gain = 1.0 + width_gate * (width_gain - 1.0)
        effective_normal_shift = shift_gate * normal_shift
        flow = torch.cat(
            [
                effective_normal_shift * controller.normal_x,
                effective_normal_shift * controller.normal_y,
            ],
            dim=1,
        )
        shifted_base = _warp_local(raw, flow)
        width_proposal = self.width_profile_action(
            WidthProfileContext(
                shifted_base=shifted_base,
                width_gain=width_gain,
                normalized_sdf=controller.normalized_sdf,
                normal_x=controller.normal_x,
                normal_y=controller.normal_y,
                renderer_features=renderer_features,
            )
        )
        base_output = shifted_base + width_gate * (width_proposal - shifted_base)
        return SplitGeometryOutput(
            base_output=base_output,
            shifted_base=shifted_base,
            width_proposal=width_proposal,
            geometry_gate=controller.geometry_gate,
            width_gate=width_gate,
            shift_gate=shift_gate,
            width_gain=width_gain,
            normal_shift=normal_shift,
            effective_width_gain=effective_width_gain,
            effective_normal_shift=effective_normal_shift,
            flow=flow,
        )

    def forward_details(self, value: torch.Tensor) -> SplitReconstructionOutput:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("expected input shape [batch, 1, height, width]")
        if not value.is_floating_point():
            raise TypeError("R114 split-model input must be floating point")
        raw = value.clamp(0, 1)
        controller = self.controller(raw)
        renderer_features = self._renderer_features(raw)
        with torch.autocast(device_type=value.device.type, enabled=False):
            renderer_fp32 = renderer_features.float()
            width_fraction = torch.sigmoid(self.width_head(renderer_fp32))
            width_gain = self.config.minimum_width_gain + (
                self.config.maximum_width_gain - self.config.minimum_width_gain
            ) * width_fraction
            normal_shift = self.config.maximum_normal_shift_px * torch.tanh(
                self.shift_head(renderer_fp32)
            )
            midpoint_offset = (
                self.config.maximum_midpoint_offset_gray_levels
                / 255.0
                * torch.tanh(self.profile_midpoint_offset_head(renderer_fp32))
            )
            signed_plateau_contrast = (
                self.config.maximum_signed_contrast_gray_levels
                / 255.0
                * torch.tanh(self.profile_signed_contrast_head(renderer_fp32))
            )
            profile_width_fraction = torch.sigmoid(
                self.profile_width_head(renderer_fp32)
            )
            profile_width = self.config.minimum_profile_width_px + (
                self.config.maximum_profile_width_px
                - self.config.minimum_profile_width_px
            ) * profile_width_fraction
            profile_visibility = self._bounded_profile_visibility(
                self.profile_visibility_head(renderer_fp32)
            )
        geometry = self.apply_geometry(
            raw.float(), controller, width_gain, normal_shift, renderer_fp32
        )
        profile = self.apply_profile_action(
            base_output=geometry.base_output,
            controller=controller,
            midpoint_offset=midpoint_offset,
            signed_plateau_contrast=signed_plateau_contrast,
            profile_width=profile_width,
            profile_visibility=profile_visibility,
            midpoint_source=geometry.shifted_base,
        )
        output = profile.profile_output
        return SplitReconstructionOutput(
            output=output,
            base_output=geometry.base_output,
            shifted_base=geometry.shifted_base,
            width_proposal=geometry.width_proposal,
            profile_output=profile.profile_output,
            profile_midpoint_cue=profile.profile_midpoint_cue,
            midpoint_offset=profile.midpoint_offset,
            profile_midpoint=profile.profile_midpoint,
            signed_plateau_contrast=profile.signed_plateau_contrast,
            profile_width=profile.profile_width,
            profile_visibility=profile.profile_visibility,
            predicted_sdf_px=profile.predicted_sdf_px,
            profile_band=profile.profile_band,
            profile_gate=profile.profile_gate,
            profile_proposal=profile.profile_proposal,
            profile_proposal_delta=profile.profile_proposal_delta,
            profile_delta=profile.profile_delta,
            delta=output - raw.float(),
            normalized_sdf=controller.normalized_sdf,
            normal_x=controller.normal_x,
            normal_y=controller.normal_y,
            boundary_confidence=controller.boundary_confidence,
            correction_need=controller.correction_need,
            recoverability=controller.recoverability,
            uncertainty=controller.uncertainty,
            width_reliability=controller.width_reliability,
            shift_reliability=controller.shift_reliability,
            geometry_gate=geometry.geometry_gate,
            width_gate=geometry.width_gate,
            shift_gate=geometry.shift_gate,
            width_gain=geometry.width_gain,
            normal_shift=geometry.normal_shift,
            effective_width_gain=geometry.effective_width_gain,
            effective_normal_shift=geometry.effective_normal_shift,
            flow=geometry.flow,
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def build_split_profile_model(
    compact: bool = False,
    config: SplitProfileConfig | None = None,
) -> R114SplitProfileModel:
    """Construct a new random model; this function never reads a checkpoint."""

    if compact and config is not None:
        raise ValueError("compact and explicit config are mutually exclusive")
    selected = SplitProfileConfig.compact_test_config() if compact else config
    return R114SplitProfileModel(config=selected)


def forward_tiled_split(
    model: R114SplitProfileModel,
    value: torch.Tensor,
    core_size: int,
    halo: int | None = None,
) -> SplitReconstructionOutput:
    """Stitch local core predictions from overlapping tiles."""

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
            tile_output = model.forward_details(
                value[..., tile_y0:tile_y1, tile_x0:tile_x1]
            )
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
    return SplitReconstructionOutput(**canvases)


def output_field_names() -> tuple[str, ...]:
    return tuple(item.name for item in fields(SplitReconstructionOutput))


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
