"""Spatial supervision derived from known synthetic source/target geometry."""
from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class SpatialTargets:
    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    boundary: torch.Tensor
    boundary_binary: torch.Tensor
    boundary_confidence: torch.Tensor
    need: torch.Tensor
    recoverability: torch.Tensor
    uncertainty: torch.Tensor
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    geometry_weight: torch.Tensor
    identity: torch.Tensor
    flat: torch.Tensor


def finite_differences(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0), mode="replicate")
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1), mode="replicate")
    return gx, gy


def _local_unit(value: torch.Tensor, window: int = 21) -> tuple[torch.Tensor, torch.Tensor]:
    radius = window // 2
    maximum = F.max_pool2d(value, window, stride=1, padding=radius)
    minimum = -F.max_pool2d(-value, window, stride=1, padding=radius)
    dynamic = (maximum - minimum).clamp_min(2.0 / 255.0)
    return ((value - minimum) / dynamic).clamp(0, 1), dynamic


def build_spatial_targets(
    source: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    sdf: torch.Tensor,
    identity: torch.Tensor,
    flat: torch.Tensor | None = None,
) -> SpatialTargets:
    """Build local targets without a scene-wide scalar width assumption.

    Source and target are paired synthetic images, so the targets use only
    known forward-process evidence.  Real microscopy never enters this path.
    """

    del mask  # Geometry comes from the supersampled SDF and image profiles.
    identity_map = identity.reshape(-1, 1, 1, 1).bool()
    flat_map = torch.zeros_like(identity_map) if flat is None else flat.reshape(-1, 1, 1, 1).bool()

    normalized_sdf = (sdf / 12.0).clamp(-1, 1)
    sdf_gx, sdf_gy = finite_differences(sdf)
    sdf_length = torch.sqrt(sdf_gx.square() + sdf_gy.square() + 1.0e-8)
    normal_x = sdf_gx / sdf_length
    normal_y = sdf_gy / sdf_length

    boundary = torch.exp(-sdf.abs() / 1.75)
    boundary = torch.where(flat_map, torch.zeros_like(boundary), boundary)
    boundary_binary = ((sdf.abs() <= 1.75) & ~flat_map).to(source.dtype)
    boundary_context = F.max_pool2d(boundary, 11, stride=1, padding=5)

    local_difference = F.avg_pool2d((target - source).abs(), 9, stride=1, padding=4)
    need = (1.0 - torch.exp(-local_difference / (2.5 / 255.0))) * boundary_context
    need = torch.where(identity_map | flat_map, torch.zeros_like(need), need).clamp(0, 1)

    source_unit, _source_dynamic = _local_unit(source)
    target_unit, _target_dynamic = _local_unit(target)
    sgx, sgy = finite_differences(source_unit)
    tgx, tgy = finite_differences(target_unit)
    source_normal_gradient = sgx * normal_x + sgy * normal_y
    target_normal_gradient = tgx * normal_x + tgy * normal_y
    source_magnitude = torch.sqrt(sgx.square() + sgy.square() + 1.0e-8)
    target_magnitude = torch.sqrt(tgx.square() + tgy.square() + 1.0e-8)
    alignment = ((sgx * tgx + sgy * tgy).abs() / (source_magnitude * target_magnitude + 1.0e-6)).clamp(0, 1)
    visibility = (source_normal_gradient.abs() / (target_normal_gradient.abs() + 1.0 / 255.0)).clamp(0, 1)
    source_smooth = F.avg_pool2d(source_unit, 5, stride=1, padding=2)
    noise_proxy = F.avg_pool2d((source_unit - source_smooth).abs(), 5, stride=1, padding=2)
    snr = (source_magnitude / (source_magnitude + noise_proxy + 1.0 / 255.0)).clamp(0, 1)
    nearby_boundary = (F.max_pool2d(boundary, 9, stride=1, padding=4) - boundary).clamp(0, 1)
    boundary_density = F.avg_pool2d(boundary_binary, 21, stride=1, padding=10)
    density_penalty = torch.sigmoid((0.48 - boundary_density) / 0.075)
    local_edge_peak = F.max_pool2d(source_magnitude, 11, stride=1, padding=5).clamp_min(1.0 / 255.0)
    localized_evidence = (source_magnitude / local_edge_peak).clamp(0, 1)
    recoverability = torch.sqrt((visibility * alignment * snr).clamp_min(0))
    recoverability = recoverability * (1.0 - 0.45 * nearby_boundary)
    recoverability = recoverability * density_penalty * (0.25 + 0.75 * torch.sqrt(localized_evidence))
    recoverability = torch.where(identity_map, torch.ones_like(recoverability), recoverability)
    recoverability = torch.where(flat_map, torch.zeros_like(recoverability), recoverability).clamp(0, 1)
    boundary_confidence = boundary * (0.08 + 0.92 * recoverability)
    boundary_confidence = torch.where(flat_map, torch.zeros_like(boundary_confidence), boundary_confidence)

    target_slope = F.avg_pool2d(target_normal_gradient.abs(), 5, stride=1, padding=2)
    source_slope = F.avg_pool2d(source_normal_gradient.abs(), 5, stride=1, padding=2)
    width_gain = (target_slope / (source_slope + 1.0 / 255.0)).clamp(1.0, 3.5)
    width_gain = torch.where(identity_map | flat_map, torch.ones_like(width_gain), width_gain)

    # A local optical-flow estimate along the known target normal.  Local-unit
    # profiles remove most exposure/contrast bias before estimating the shift.
    numerator = F.avg_pool2d((target_unit - source_unit) * source_normal_gradient, 5, stride=1, padding=2)
    denominator = F.avg_pool2d(source_normal_gradient.square(), 5, stride=1, padding=2) + (1.5 / 255.0) ** 2
    normal_shift = (numerator / denominator).clamp(-1.5, 1.5)
    normal_shift = torch.where(identity_map | flat_map, torch.zeros_like(normal_shift), normal_shift)

    geometry_weight = (0.05 * boundary_context + 0.95 * boundary_confidence).clamp_min(1.0e-4)
    return SpatialTargets(
        normalized_sdf=normalized_sdf,
        normal_x=normal_x,
        normal_y=normal_y,
        boundary=boundary,
        boundary_binary=boundary_binary,
        boundary_confidence=boundary_confidence,
        need=need,
        recoverability=recoverability,
        uncertainty=1.0 - recoverability,
        width_gain=width_gain,
        normal_shift=normal_shift,
        geometry_weight=geometry_weight,
        identity=identity.reshape(-1).bool(),
        flat=(torch.zeros_like(identity) if flat is None else flat).reshape(-1).bool(),
    )
