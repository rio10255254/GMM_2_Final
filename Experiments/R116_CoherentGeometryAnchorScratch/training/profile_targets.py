"""Dense normal-profile width, shift, and coordinate-reliability targets."""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class ProfileTargets:
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    width_reliability: torch.Tensor
    shift_reliability: torch.Tensor
    boundary_band: torch.Tensor
    sample_validity: torch.Tensor


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad((value[..., 2:] - value[..., :-2]) * 0.5, (1, 1, 0, 0), mode="replicate")
    gy = F.pad((value[..., 2:, :] - value[..., :-2, :]) * 0.5, (0, 0, 1, 1), mode="replicate")
    return gx, gy


def sample_profiles(value: torch.Tensor, center_sdf: torch.Tensor,
                    normal_x: torch.Tensor, normal_y: torch.Tensor,
                    offsets: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.arange(height, device=value.device, dtype=value.dtype),
        torch.arange(width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    xx = xx.view(1, 1, height, width).expand(batch, -1, -1, -1)
    yy = yy.view(1, 1, height, width).expand(batch, -1, -1, -1)
    center_x = xx - center_sdf * normal_x
    center_y = yy - center_sdf * normal_y
    samples = []
    validity = torch.ones_like(value)
    for offset in offsets:
        sample_x = center_x + offset * normal_x
        sample_y = center_y + offset * normal_y
        valid = (
            (sample_x >= 0.0) & (sample_x <= float(width - 1))
            & (sample_y >= 0.0) & (sample_y <= float(height - 1))
        )
        grid_x = 2.0 * sample_x[:, 0] / max(width - 1, 1) - 1.0
        grid_y = 2.0 * sample_y[:, 0] / max(height - 1, 1) - 1.0
        grid = torch.stack((grid_x, grid_y), dim=-1)
        samples.append(F.grid_sample(value, grid, mode="bilinear", padding_mode="reflection", align_corners=True))
        validity = validity * valid.to(value.dtype)
    return torch.cat(samples, dim=1), validity


def profile_moments(profile: torch.Tensor, offsets: torch.Tensor) -> dict[str, torch.Tensor]:
    derivative = (profile[:, 1:] - profile[:, :-1]).abs()
    middle = 0.5 * (offsets[1:] + offsets[:-1])
    weight_sum = derivative.sum(dim=1, keepdim=True).clamp_min(1.0e-6)
    location = (derivative * middle.view(1, -1, 1, 1)).sum(dim=1, keepdim=True) / weight_sum
    variance = (
        derivative * (middle.view(1, -1, 1, 1) - location).square()
    ).sum(dim=1, keepdim=True) / weight_sum
    width = 2.563103 * torch.sqrt(variance.clamp_min(1.0e-4))
    contrast = (profile[:, -2:].mean(dim=1, keepdim=True) - profile[:, :2].mean(dim=1, keepdim=True)).abs()
    total_variation = derivative.sum(dim=1, keepdim=True)
    monotonicity = (contrast / total_variation.clamp_min(1.0e-6)).clamp(0.0, 1.0)
    edge_peak = derivative.amax(dim=1, keepdim=True)
    concentration = (edge_peak / weight_sum).clamp(0.0, 1.0)
    return {
        "location": location,
        "width": width,
        "contrast": contrast,
        "monotonicity": monotonicity,
        "concentration": concentration,
    }


def build_profile_targets(source: torch.Tensor, target: torch.Tensor,
                          target_sdf_px: torch.Tensor,
                          predicted_sdf_px: torch.Tensor | None = None,
                          normal_x: torch.Tensor | None = None,
                          normal_y: torch.Tensor | None = None,
                          identity: torch.Tensor | None = None,
                          flat: torch.Tensor | None = None,
                          offsets_px: tuple[float, ...] = (-12, -9, -6, -3, 0, 3, 6, 9, 12),
                          maximum_width_gain: float = 3.5,
                          maximum_shift_px: float = 1.5) -> ProfileTargets:
    if source.shape != target.shape or source.shape != target_sdf_px.shape:
        raise ValueError("source, target, and target_sdf_px must have matching shapes")
    source = source.float().clamp(0.0, 1.0)
    target = target.float().clamp(0.0, 1.0)
    target_sdf_px = target_sdf_px.float()
    center_sdf = target_sdf_px if predicted_sdf_px is None else predicted_sdf_px.detach().float()
    if normal_x is None or normal_y is None:
        gx, gy = gradients(target_sdf_px)
        magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-8)
        normal_x, normal_y = gx / magnitude, gy / magnitude
    else:
        normal_x, normal_y = normal_x.detach().float(), normal_y.detach().float()
    offsets = torch.tensor(offsets_px, device=source.device, dtype=source.dtype)
    source_profile, source_valid = sample_profiles(source, center_sdf, normal_x, normal_y, offsets)
    target_profile, target_valid = sample_profiles(target, center_sdf, normal_x, normal_y, offsets)
    validity = source_valid * target_valid
    source_moments = profile_moments(source_profile, offsets)
    target_moments = profile_moments(target_profile, offsets)
    width_ratio = (
        source_moments["width"] / target_moments["width"].clamp_min(0.35)
    ).clamp(1.0, float(maximum_width_gain))
    shift = (source_moments["location"] - target_moments["location"]).clamp(
        -float(maximum_shift_px), float(maximum_shift_px)
    )
    contrast_score = (
        source_moments["contrast"] / (target_moments["contrast"] + 2.0 / 255.0)
    ).clamp(0.0, 1.0)
    target_contrast_score = torch.sigmoid((target_moments["contrast"] * 255.0 - 8.0) / 3.0)
    common = torch.sqrt(
        (
            source_moments["monotonicity"]
            * target_moments["monotonicity"]
            * source_moments["concentration"]
            * target_moments["concentration"]
        ).clamp_min(0.0)
    )
    width_stability = torch.exp(
        -torch.abs(torch.log((source_moments["width"] + 0.2) / (target_moments["width"] + 0.2))) / 1.2
    )
    width_reliability = (common * torch.sqrt(contrast_score * target_contrast_score) * width_stability).clamp(0.0, 1.0)
    shift_reliability = (
        common * contrast_score * target_contrast_score
        * torch.exp(-(shift.abs() - float(maximum_shift_px) * 0.8).clamp_min(0.0) / 0.2)
    ).clamp(0.0, 1.0)
    boundary_band = torch.exp(-target_sdf_px.abs() / 2.5) * validity
    # Reliability is conditional on being in the boundary band.  The loss
    # applies boundary_band separately; multiplying it here as well would make
    # confidence targets vanish and close the action gates during warm-up.
    batch = source.shape[0]
    identity_vector = torch.zeros(batch, dtype=torch.bool, device=source.device) if identity is None else identity.bool()
    flat_vector = torch.zeros(batch, dtype=torch.bool, device=source.device) if flat is None else flat.bool()
    identity_map = identity_vector[:, None, None, None]
    flat_map = flat_vector[:, None, None, None]
    width_ratio = torch.where(identity_map | flat_map, torch.ones_like(width_ratio), width_ratio)
    shift = torch.where(identity_map | flat_map, torch.zeros_like(shift), shift)
    width_reliability = torch.where(flat_map, torch.zeros_like(width_reliability), width_reliability)
    shift_reliability = torch.where(flat_map, torch.zeros_like(shift_reliability), shift_reliability)
    boundary_band = torch.where(flat_map, torch.zeros_like(boundary_band), boundary_band)
    tensors = (width_ratio, shift, width_reliability, shift_reliability, boundary_band, validity)
    if not all(bool(torch.isfinite(value).all()) for value in tensors):
        raise FloatingPointError("non-finite profile target")
    return ProfileTargets(*tensors)
