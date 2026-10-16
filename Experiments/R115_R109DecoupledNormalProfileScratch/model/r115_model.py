"""R115: R109 geometry with a fully decoupled normal-profile evidence tower."""
from __future__ import annotations

from dataclasses import dataclass, fields
import json
import math
from pathlib import Path

import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
MCFG = CONFIG["model"]


def safe_pad(value: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if min(value.shape[-2:]) > amount else "replicate"
    return F.pad(value, (amount, amount, amount, amount), mode=mode)


class Blur(nn.Module):
    def __init__(self, sigma: float):
        super().__init__()
        radius = max(1, int(math.ceil(3 * float(sigma))))
        axis = torch.arange(-radius, radius + 1, dtype=torch.float32)
        row = torch.exp(-0.5 * (axis / float(sigma)) ** 2)
        row /= row.sum()
        self.register_buffer("horizontal", row.view(1, 1, 1, -1))
        self.register_buffer("vertical", row.view(1, 1, -1, 1))
        self.radius = radius

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        mode = "reflect" if min(value.shape[-2:]) > self.radius else "replicate"
        horizontal = F.conv2d(
            F.pad(value, (self.radius, self.radius, 0, 0), mode=mode),
            self.horizontal.to(dtype=value.dtype),
        )
        return F.conv2d(
            F.pad(horizontal, (0, 0, self.radius, self.radius), mode=mode),
            self.vertical.to(dtype=value.dtype),
        )


class Residual(nn.Module):
    def __init__(self, channels: int, dilation: int):
        super().__init__()
        # Keep R109's a/b names so the non-formal frozen-baseline probe can
        # load common geometry tensors without a translation table.
        self.a = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)
        self.b = nn.Conv2d(channels, channels, 3, padding=dilation, dilation=dilation)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return F.silu(value + 0.15 * self.b(F.silu(self.a(value))))


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0))
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1))
    return gx, gy


class LocalCues(nn.Module):
    channels = 15

    def __init__(self):
        super().__init__()
        self.blurs = nn.ModuleList([Blur(value) for value in MCFG["blur_scales_px"]])
        self.context = Blur(max(MCFG["blur_scales_px"]))

    def forward(self, value: torch.Tensor) -> dict[str, torch.Tensor | list[torch.Tensor]]:
        blurred = [layer(value) for layer in self.blurs]
        highpasses = [value - item for item in blurred]
        gx, gy = gradients(value)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-8)
        local_mean = blurred[-1]
        local_scale = torch.sqrt(self.context((value - local_mean).square()) + (2 / 255) ** 2)
        normalized = ((value - local_mean) / (local_scale + 2 / 255)).clamp(-4, 4)
        features = torch.cat(
            [value, *blurred, *highpasses, gx, gy, magnitude, local_mean, local_scale, normalized],
            dim=1,
        )
        return {
            "features": features,
            "blurred": blurred,
            "magnitude": magnitude,
            "local_scale": local_scale,
        }


@dataclass(frozen=True)
class R115Details:
    output: torch.Tensor
    baseline_output: torch.Tensor
    delta: torch.Tensor
    boundary_logits: torch.Tensor
    boundary: torch.Tensor
    support: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    shift_factor: torch.Tensor
    width_factor: torch.Tensor
    shift_adjustment: torch.Tensor
    width_adjustment: torch.Tensor
    effective_width_gain: torch.Tensor
    effective_normal_shift: torch.Tensor
    flow: torch.Tensor
    shifted_base: torch.Tensor
    width_proposal: torch.Tensor
    shift_candidate_delta: torch.Tensor
    width_candidate_delta: torch.Tensor
    selected_shift_delta: torch.Tensor
    selected_width_delta: torch.Tensor
    profile_features: torch.Tensor


class R115Model(nn.Module):
    alignment_multiple = int(MCFG["alignment_multiple"])
    minimum_halo_px = int(MCFG["minimum_halo_px"])

    def __init__(self):
        super().__init__()
        base = int(MCFG["base_channels"])
        profile_channels = int(MCFG["profile_channels"])
        self.offsets = tuple(float(value) for value in MCFG["profile_offsets_px"])
        self.cues = LocalCues()
        self.detector_stem = nn.Conv2d(LocalCues.channels, base, 3, padding=1)
        self.detector_tower = nn.Sequential(
            *[Residual(base, int(value)) for value in MCFG["geometry_dilations"]]
        )
        self.renderer_stem = nn.Conv2d(LocalCues.channels, base, 3, padding=1)
        self.renderer_tower = nn.Sequential(
            *[Residual(base, int(value)) for value in MCFG["geometry_dilations"]]
        )
        self.boundary_head = nn.Conv2d(base, 1, 1)
        self.width_head = nn.Conv2d(base, 1, 1)
        self.shift_head = nn.Conv2d(base, 1, 1)

        profile_inputs = len(self.offsets) + 7
        self.profile_stem = nn.Conv2d(profile_inputs, profile_channels, 3, padding=1)
        self.profile_tower = nn.Sequential(
            *[Residual(profile_channels, int(value)) for value in MCFG["profile_dilations"]]
        )
        self.shift_adjust_head = nn.Conv2d(profile_channels, 1, 1)
        self.width_adjust_head = nn.Conv2d(profile_channels, 1, 1)
        self._initialize()

    def _initialize(self) -> None:
        for head in (self.boundary_head, self.width_head, self.shift_head):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)
        nn.init.constant_(self.boundary_head.bias, -2.0)
        nn.init.constant_(self.width_head.bias, -4.0)
        for head in (
            self.shift_adjust_head,
            self.width_adjust_head,
        ):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)

    def detector_parameters(self) -> list[nn.Parameter]:
        return [
            *self.detector_stem.parameters(),
            *self.detector_tower.parameters(),
            *self.boundary_head.parameters(),
        ]

    def geometry_parameters(self) -> list[nn.Parameter]:
        return [
            *self.renderer_stem.parameters(),
            *self.renderer_tower.parameters(),
            *self.width_head.parameters(),
            *self.shift_head.parameters(),
        ]

    def profile_parameters(self) -> list[nn.Parameter]:
        return [
            *self.profile_stem.parameters(),
            *self.profile_tower.parameters(),
            *self.shift_adjust_head.parameters(),
            *self.width_adjust_head.parameters(),
        ]

    @staticmethod
    def warp(value: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        batch, _channels, height, width = value.shape
        yy, xx = torch.meshgrid(
            torch.linspace(-1, 1, height, device=value.device, dtype=value.dtype),
            torch.linspace(-1, 1, width, device=value.device, dtype=value.dtype),
            indexing="ij",
        )
        grid = torch.stack([xx, yy], dim=-1).unsqueeze(0).expand(batch, -1, -1, -1).clone()
        grid[..., 0] += flow[:, 0] * (2 / max(width - 1, 1))
        grid[..., 1] += flow[:, 1] * (2 / max(height - 1, 1))
        return F.grid_sample(
            value,
            grid,
            mode="bilinear",
            padding_mode="reflection",
            align_corners=True,
        )

    @staticmethod
    def bounded_positive(logit: torch.Tensor) -> torch.Tensor:
        return torch.clamp(F.softplus(logit) - math.log(2.0), min=0.0, max=1.0)

    @staticmethod
    def width_transform(value: torch.Tensor, width_gain: torch.Tensor) -> torch.Tensor:
        window = int(MCFG["local_range_window_px"])
        radius = window // 2
        local_max = F.max_pool2d(value, window, stride=1, padding=radius)
        local_min = -F.max_pool2d(-value, window, stride=1, padding=radius)
        dynamic = (local_max - local_min).clamp_min(2 / 255)
        unit = ((value - local_min) / dynamic).clamp(1.0e-3, 1.0 - 1.0e-3)
        corrected = torch.sigmoid(width_gain * (torch.log(unit) - torch.log1p(-unit)))
        return local_min + dynamic * corrected

    def _profile_features(
        self,
        raw: torch.Tensor,
        normal_x: torch.Tensor,
        normal_y: torch.Tensor,
        boundary: torch.Tensor,
        support: torch.Tensor,
        width_gain: torch.Tensor,
        normal_shift: torch.Tensor,
        magnitude: torch.Tensor,
        local_scale: torch.Tensor,
    ) -> torch.Tensor:
        nx = normal_x.detach()
        ny = normal_y.detach()
        samples = [
            self.warp(raw, torch.cat([offset * nx, offset * ny], dim=1))
            for offset in self.offsets
        ]
        evidence = torch.cat(
            [
                *samples,
                boundary.detach(),
                support.detach(),
                width_gain.detach(),
                normal_shift.detach(),
                magnitude.detach(),
                local_scale.detach(),
                raw,
            ],
            dim=1,
        )
        return self.profile_tower(F.silu(self.profile_stem(evidence)))

    def _forward_aligned(self, value: torch.Tensor) -> R115Details:
        raw = value.clamp(0, 1)
        cues = self.cues(raw)
        detector = self.detector_tower(F.silu(self.detector_stem(cues["features"])))
        renderer = self.renderer_tower(F.silu(self.renderer_stem(cues["features"])))
        with torch.autocast(device_type=value.device.type, enabled=False):
            detector32 = torch.tanh(detector.float())
            renderer32 = torch.tanh(renderer.float())
            boundary_logits = self.boundary_head(detector32)
            boundary = torch.sigmoid(boundary_logits)
            minimum = float(MCFG["minimum_width_gain"])
            maximum = float(MCFG["maximum_width_gain"])
            width_gain = minimum + (maximum - minimum) * torch.sigmoid(self.width_head(renderer32))
            normal_shift = float(MCFG["maximum_normal_shift_px"]) * torch.tanh(
                self.shift_head(renderer32)
            )
            magnitude = cues["magnitude"].float()
            local_scale = cues["local_scale"].float()
            source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0, 1)
            support = torch.maximum(source_support, 0.85 * F.max_pool2d(boundary, 9, 1, 4)).clamp(0, 1)
            smooth_gx, smooth_gy = gradients(cues["blurred"][1].float())
            smooth_magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1.0e-8)
            normal_x = smooth_gx / smooth_magnitude
            normal_y = smooth_gy / smooth_magnitude

            profile_features = self._profile_features(
                raw.float(), normal_x, normal_y, boundary, support,
                width_gain, normal_shift, magnitude, local_scale,
            ).float()
            maximum_adjustment = float(MCFG["maximum_action_factor_adjustment"])
            shift_adjustment = maximum_adjustment * torch.tanh(self.shift_adjust_head(profile_features))
            width_adjustment = maximum_adjustment * torch.tanh(self.width_adjust_head(profile_features))
            shift_factor = 1.0 + shift_adjustment
            width_factor = 1.0 + width_adjustment
            effective_shift = normal_shift * shift_factor
            effective_width = (
                1.0 + (width_gain - 1.0) * width_factor
            ).clamp(float(MCFG["minimum_width_gain"]), float(MCFG["maximum_width_gain"]))

            full_flow = torch.cat([normal_shift * normal_x, normal_shift * normal_y], dim=1)
            full_shifted = self.warp(raw.float(), full_flow * support)
            baseline_width = self.width_transform(full_shifted, width_gain)
            baseline_output = (raw.float() + support * (baseline_width - raw.float())).clamp(0, 1)

            flow = torch.cat([effective_shift * normal_x, effective_shift * normal_y], dim=1)
            shifted_base = self.warp(raw.float(), flow * support)
            width_proposal = self.width_transform(shifted_base, effective_width)
            output = (raw.float() + support * (width_proposal - raw.float())).clamp(0, 1)
            shift_candidate_delta = full_shifted - raw.float()
            width_only = raw.float() + support * (self.width_transform(raw.float(), width_gain) - raw.float())
            width_candidate_delta = width_only - raw.float()

        return R115Details(
            output=output,
            baseline_output=baseline_output,
            delta=output - raw.float(),
            boundary_logits=boundary_logits,
            boundary=boundary,
            support=support,
            normal_x=normal_x,
            normal_y=normal_y,
            width_gain=width_gain,
            normal_shift=normal_shift,
            shift_factor=shift_factor,
            width_factor=width_factor,
            shift_adjustment=shift_adjustment,
            width_adjustment=width_adjustment,
            effective_width_gain=effective_width,
            effective_normal_shift=effective_shift,
            flow=flow,
            shifted_base=shifted_base,
            width_proposal=width_proposal,
            shift_candidate_delta=shift_candidate_delta,
            width_candidate_delta=width_candidate_delta,
            selected_shift_delta=shifted_base - raw.float(),
            selected_width_delta=output - shifted_base,
            profile_features=profile_features,
        )

    def forward_details(self, value: torch.Tensor) -> R115Details:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("R115 expects [batch, 1, height, width]")
        height, width = value.shape[-2:]
        pad_h = (-height) % self.alignment_multiple
        pad_w = (-width) % self.alignment_multiple
        if pad_h or pad_w:
            mode = "reflect" if height > pad_h and width > pad_w else "replicate"
            padded = F.pad(value, (0, pad_w, 0, pad_h), mode=mode)
            details = self._forward_aligned(padded)
            return R115Details(
                *[getattr(details, item.name)[..., :height, :width] for item in fields(details)]
            )
        return self._forward_aligned(value)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def build_model() -> R115Model:
    return R115Model()


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def load_r109_for_probe(model: R115Model, checkpoint: str | Path) -> dict:
    """Load only common R109 geometry parameters for the non-formal A/B probe."""
    saved = torch.load(Path(checkpoint), map_location="cpu", weights_only=False)
    state = saved["model"]
    current = model.state_dict()
    common = {name: tensor for name, tensor in state.items() if name in current and current[name].shape == tensor.shape}
    incompatible = model.load_state_dict(common, strict=False)
    expected_missing = {name for name in current if name.startswith("profile_") or "adjust_head" in name}
    actual_missing = set(incompatible.missing_keys)
    if actual_missing != expected_missing or incompatible.unexpected_keys:
        raise RuntimeError(
            f"unexpected R109 probe load: missing={sorted(actual_missing ^ expected_missing)}, "
            f"unexpected={incompatible.unexpected_keys}"
        )
    return {
        "checkpoint": str(Path(checkpoint).resolve()),
        "epoch": int(saved.get("epoch", -1)),
        "common_tensors": len(common),
        "profile_tensors_random": len(expected_missing),
    }
