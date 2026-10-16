"""Single-image, tile-local, center-locked R117 reconstruction network."""

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


@dataclass(frozen=True)
class R117Details:
    output: torch.Tensor
    boundary_logits: torch.Tensor
    boundary_confidence: torch.Tensor
    predicted_sdf_px: torch.Tensor
    high_boundary_logits: torch.Tensor
    high_boundary_confidence: torch.Tensor
    high_predicted_sdf_px: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    source_support: torch.Tensor
    shift_amount: torch.Tensor
    shift_confidence: torch.Tensor
    shift_gate: torch.Tensor
    normal_shift: torch.Tensor
    flow: torch.Tensor
    geometry_anchor: torch.Tensor
    width_gain: torch.Tensor
    width_confidence: torch.Tensor
    width_gate: torch.Tensor
    width_proposal: torch.Tensor
    width_zero_mean_detail: torch.Tensor
    detail_coefficients: torch.Tensor
    detail_confidence: torch.Tensor
    evidence_detail: torch.Tensor
    pre_projection_detail: torch.Tensor
    reflected_detail: torch.Tensor
    center_locked_detail: torch.Tensor
    bounded_detail: torch.Tensor
    low_frequency_leakage: torch.Tensor


@dataclass(frozen=True)
class R117Detection:
    boundary_logits: torch.Tensor
    boundary_confidence: torch.Tensor
    predicted_sdf_px: torch.Tensor
    high_boundary_logits: torch.Tensor
    high_boundary_confidence: torch.Tensor
    high_predicted_sdf_px: torch.Tensor


class R117Model(nn.Module):
    def __init__(self):
        super().__init__()
        cfg = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))["model"]
        self.config = cfg
        self.minimum_halo_px = int(cfg["minimum_halo_px"])
        self.alignment_multiple = int(cfg["alignment_multiple"])
        self.cues = LocalCues(cfg["blur_scales_px"])
        self.detector = LocalTower(self.cues.channels, int(cfg["base_channels"]), cfg["detector_dilations"])
        self.boundary_head = nn.Conv2d(int(cfg["base_channels"]), 1, 1)
        self.sdf_head = nn.Conv2d(int(cfg["base_channels"]), 1, 1)
        self.subpixel_refiner = nn.Sequential(LocalConv2d(3, 12), nn.SiLU(), LocalConv2d(12, 2))
        profile_channels = 2 * len(cfg["profile_offsets_px"]) + len(cfg["profile_offsets_px"]) - 1 + 5
        self.width_tower = LocalTower(profile_channels, int(cfg["action_channels"]), cfg["action_dilations"])
        self.width_head = nn.Conv2d(int(cfg["action_channels"]), 2, 1)
        self.shift_tower = LocalTower(profile_channels, int(cfg["action_channels"]), cfg["action_dilations"])
        self.shift_head = nn.Conv2d(int(cfg["action_channels"]), 2, 1)
        self.detail_tower = LocalTower(profile_channels, int(cfg["detail_channels"]), cfg["detail_dilations"])
        self.detail_head = nn.Conv2d(int(cfg["detail_channels"]), 4, 1)
        self.lowpass = GaussianBlur(float(cfg["low_frequency_anchor_sigma_px"]))
        self._initialize()

    def _initialize(self) -> None:
        for head in (self.boundary_head, self.sdf_head, self.width_head, self.shift_head, self.detail_head):
            nn.init.zeros_(head.weight); nn.init.zeros_(head.bias)
        nn.init.constant_(self.boundary_head.bias, -2.0)
        nn.init.zeros_(self.subpixel_refiner[-1].conv.weight)
        nn.init.zeros_(self.subpixel_refiner[-1].conv.bias)
        with torch.no_grad():
            self.width_head.bias[:] = torch.tensor((-1.5, -1.5))
            self.shift_head.bias[:] = torch.tensor((0.0, -1.5))
            self.detail_head.bias[:] = torch.tensor((0.0, 0.0, 0.0, -1.5))

    def parameter_groups(self) -> dict[str, list[nn.Parameter]]:
        return {
            "detector": [*self.detector.parameters(), *self.boundary_head.parameters(), *self.sdf_head.parameters(), *self.subpixel_refiner.parameters()],
            "width": [*self.width_tower.parameters(), *self.width_head.parameters()],
            "shift": [*self.shift_tower.parameters(), *self.shift_head.parameters()],
            "detail": [*self.detail_tower.parameters(), *self.detail_head.parameters()],
        }

    @staticmethod
    def zero_fraction(logits: torch.Tensor, bias: float = -1.5) -> torch.Tensor:
        baseline = torch.sigmoid(logits.new_tensor(bias))
        raw = (torch.sigmoid(logits) - baseline) / (1.0 - baseline)
        bounded = raw.clamp(0.0, 1.0)
        return raw + (bounded - raw).detach()

    def detect(self, raw: torch.Tensor, detector_features: torch.Tensor) -> tuple[torch.Tensor, ...]:
        maximum = float(self.config["maximum_predicted_sdf_px"])
        boundary_logits = self.boundary_head(detector_features)
        sdf = maximum * torch.tanh(self.sdf_head(detector_features))
        scale = int(self.config["subpixel_scale"])
        # Half-pixel interpolation is translation equivariant and therefore
        # independent of the enclosing tile size.  align_corners=True would
        # subtly change coordinates between a full frame and a cropped tile.
        high_raw = F.interpolate(raw, scale_factor=scale, mode="bilinear", align_corners=False)
        packed = F.interpolate(torch.cat((boundary_logits, sdf / maximum, raw), 1), scale_factor=scale, mode="bilinear", align_corners=False)
        correction = self.subpixel_refiner(packed)
        high_logits = packed[:, :1] + correction[:, :1]
        high_sdf = (maximum * packed[:, 1:2] + 2.0 * torch.tanh(correction[:, 1:2])).clamp(-maximum, maximum)
        boundary_logits = F.avg_pool2d(high_logits, scale)
        sdf = F.avg_pool2d(high_sdf, scale)
        return boundary_logits, sdf, high_logits, high_sdf, high_raw

    def profile(self, raw, sdf, nx, ny, boundary, cues) -> torch.Tensor:
        center_flow = torch.cat((-sdf.clamp(-12, 12) * nx, -sdf.clamp(-12, 12) * ny), 1)
        centered = warp_local(torch.cat((cues["local_mean"], cues["local_scale"]), 1), center_flow)
        mean, scale = centered[:, :1], centered[:, 1:].clamp_min(2.0 / 255.0)
        offsets = raw.new_tensor(self.config["profile_offsets_px"]).view(1, -1, 1, 1, 1)
        normal = torch.cat((nx, ny), 1)
        sampled = warp_many(raw, center_flow[:, None] + offsets * normal[:, None])[:, :, 0]
        normalized = (sampled - mean) / (scale + 2.0 / 255.0)
        normalized = normalized / torch.sqrt(1.0 + normalized.square() / 16.0)
        differences = sampled[:, 1:] - sampled[:, :-1]
        ratio = cues["magnitude"] / (cues["local_scale"] + 2.0 / 255.0)
        return torch.cat((sampled, normalized, differences, boundary, ratio.clamp(0, 8), sdf / 12.0, scale, raw), 1)

    def bounded_highpass(self, value: torch.Tensor) -> torch.Tensor:
        cap = float(self.config["maximum_detail_delta_gray"]) / 255.0
        value = value - self.lowpass(value)
        value = cap * torch.tanh(value / cap)
        value = value - self.lowpass(value)
        return value.clamp(-cap, cap)

    def _forward_aligned(self, value: torch.Tensor) -> R117Details:
        raw = value.float().clamp(0, 1)
        cues = self.cues(raw)
        features = self.detector(cues["features"])
        logits, sdf, high_logits, high_sdf, _high_raw = self.detect(raw, features)
        boundary = torch.sigmoid(logits)
        smooth_gx, smooth_gy = gradients(cues["blurred"][1])
        magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1.0e-8)
        nx, ny = smooth_gx / magnitude, smooth_gy / magnitude
        source_support = ((cues["magnitude"] / (cues["local_scale"] + 2.0 / 255.0) - 0.05) / 1.10).clamp(0, 1)
        source_support = torch.maximum(source_support, 0.85 * F.max_pool2d(boundary, 9, 1, 4)).clamp(0, 1)
        band = torch.exp(-sdf.abs() / 3.0)
        support = (source_support * boundary * (0.25 + 0.75 * band)).clamp(0, 1)
        profile = self.profile(raw, sdf, nx, ny, boundary, cues)

        shift_logits = self.shift_head(self.shift_tower(profile))
        shift_amount = float(self.config["maximum_normal_shift_px"]) * torch.tanh(shift_logits[:, :1])
        shift_confidence = torch.sigmoid(shift_logits[:, 1:2])
        shift_gate = (support * shift_confidence).clamp(0, 1)
        normal_shift = shift_gate * shift_amount
        flow = torch.cat((normal_shift * nx, normal_shift * ny), 1)
        geometry_anchor = warp_local(raw, flow)

        width_logits = self.width_head(self.width_tower(profile))
        amount = (float(self.config["maximum_width_gain"]) - 1.0) * self.zero_fraction(width_logits[:, :1])
        width_confidence = torch.sigmoid(width_logits[:, 1:2])
        width_gate = (support * width_confidence).clamp(0, 1)
        width_gain = (1.0 + width_gate * amount).clamp(float(self.config["minimum_width_gain"]), float(self.config["maximum_width_gain"]))
        center_flow = torch.cat((-sdf * nx, -sdf * ny), 1)
        endpoint_offsets = raw.new_tensor((-8.0, 8.0)).view(1, 2, 1, 1, 1)
        endpoints = warp_many(geometry_anchor, center_flow[:, None] + endpoint_offsets * torch.cat((nx, ny), 1)[:, None])[:, :, 0]
        midpoint = 0.5 * (endpoints[:, :1] + endpoints[:, 1:2])
        half = 0.5 * (endpoints[:, 1:2] - endpoints[:, :1]).abs().clamp_min(2.0 / 255.0)
        unit = ((geometry_anchor - midpoint) / half).clamp(-0.995, 0.995)
        transformed = midpoint + half * torch.tanh(width_gain * torch.atanh(unit))
        identity_width = width_gain == 1.0
        transformed = transformed + identity_width.to(transformed.dtype) * (geometry_anchor - transformed).detach()
        width_proposal = geometry_anchor + width_gate * (transformed - geometry_anchor)
        width_zero_mean = width_proposal - geometry_anchor
        width_zero_mean = width_zero_mean - self.lowpass(width_zero_mean)

        detail_logits = self.detail_head(self.detail_tower(profile))
        coefficients = float(self.config["maximum_detail_basis_gain"]) * torch.tanh(detail_logits[:, :3])
        detail_confidence = torch.sigmoid(detail_logits[:, 3:4])
        blurred = [self.cues.blurs[index](geometry_anchor) for index in range(3)]
        basis = torch.cat((geometry_anchor - blurred[0], blurred[0] - blurred[1], blurred[1] - blurred[2]), 1)
        evidence = (coefficients * basis).sum(1, keepdim=True)
        pre = width_zero_mean + (support * detail_confidence).clamp(0, 1) * evidence
        reflected = warp_local(pre, torch.cat((-2.0 * sdf.clamp(-6, 6) * nx, -2.0 * sdf.clamp(-6, 6) * ny), 1))
        odd = 0.5 * (pre - reflected)
        lock = torch.sigmoid((float(self.config["contour_lock_radius_px"]) - sdf.abs()) / 0.75)
        center_locked = lock * odd + (1.0 - lock) * pre
        bounded = self.bounded_highpass(center_locked)
        output = (geometry_anchor + bounded).clamp(0, 1)
        return R117Details(
            output, logits, boundary, sdf, high_logits, torch.sigmoid(high_logits), high_sdf,
            nx, ny, source_support, shift_amount, shift_confidence, shift_gate, normal_shift,
            flow, geometry_anchor, width_gain, width_confidence, width_gate, width_proposal,
            width_zero_mean, coefficients, detail_confidence, evidence, pre, reflected,
            center_locked, bounded, self.lowpass(output - geometry_anchor),
        )

    def _detect_aligned(self, value: torch.Tensor) -> R117Detection:
        raw = value.float().clamp(0, 1)
        features = self.detector(self.cues(raw)["features"])
        logits, sdf, high_logits, high_sdf, _ = self.detect(raw, features)
        return R117Detection(logits, torch.sigmoid(logits), sdf, high_logits, torch.sigmoid(high_logits), high_sdf)

    def forward_detection(self, value: torch.Tensor) -> R117Detection:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("R117 expects [batch,1,height,width]")
        height, width = value.shape[-2:]
        ph, pw = (-height) % self.alignment_multiple, (-width) % self.alignment_multiple
        if ph or pw:
            result = self._detect_aligned(F.pad(value, (0, pw, 0, ph), mode="reflect"))
            scale = int(self.config["subpixel_scale"])
            return R117Detection(
                result.boundary_logits[..., :height, :width],
                result.boundary_confidence[..., :height, :width],
                result.predicted_sdf_px[..., :height, :width],
                result.high_boundary_logits[..., :height * scale, :width * scale],
                result.high_boundary_confidence[..., :height * scale, :width * scale],
                result.high_predicted_sdf_px[..., :height * scale, :width * scale],
            )
        return self._detect_aligned(value)

    def forward_details(self, value: torch.Tensor) -> R117Details:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("R117 expects [batch,1,height,width]")
        height, width = value.shape[-2:]
        ph, pw = (-height) % self.alignment_multiple, (-width) % self.alignment_multiple
        if ph or pw:
            result = self._forward_aligned(F.pad(value, (0, pw, 0, ph), mode="reflect"))
            full_fields = {"high_boundary_logits", "high_boundary_confidence", "high_predicted_sdf_px"}
            values = []
            scale = int(self.config["subpixel_scale"])
            for item in fields(result):
                tensor = getattr(result, item.name)
                values.append(tensor[..., :height * scale, :width * scale] if item.name in full_fields else tensor[..., :height, :width])
            return R117Details(*values)
        return self._forward_aligned(value)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def build_model() -> R117Model:
    return R117Model()


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
