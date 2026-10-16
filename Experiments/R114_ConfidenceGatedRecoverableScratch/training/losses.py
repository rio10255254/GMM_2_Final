"""Per-scene normalized, stage-specific R114 objectives."""
from __future__ import annotations

from collections.abc import Mapping

import torch
import torch.nn.functional as F

from .targets import SpatialTargets, finite_differences


def per_scene_weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    if value.shape != weight.shape:
        weight = weight.expand_as(value)
    numerator = (value * weight).flatten(1).sum(1)
    denominator = weight.flatten(1).sum(1).clamp_min(1.0e-6)
    return (numerator / denominator).mean()


def per_scene_mean(value: torch.Tensor) -> torch.Tensor:
    return value.flatten(1).mean(1).mean()


def per_scene_weighted_values(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    if value.shape != weight.shape:
        weight = weight.expand_as(value)
    numerator = (value * weight).flatten(1).sum(1)
    denominator = weight.flatten(1).sum(1).clamp_min(1.0e-6)
    return numerator / denominator


def soft_dice(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    numerator = 2.0 * (prediction * target).flatten(1).sum(1) + 1.0e-6
    denominator = prediction.flatten(1).sum(1) + target.flatten(1).sum(1) + 1.0e-6
    return (1.0 - numerator / denominator).mean()


def balanced_boundary_bce(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    prediction = prediction.clamp(1.0e-5, 1.0 - 1.0e-5)
    losses = []
    for index in range(prediction.shape[0]):
        pred = prediction[index:index + 1]
        truth = target[index:index + 1]
        positive = truth
        negative = 1.0 - truth
        pos_loss = per_scene_weighted_mean(-torch.log(pred), positive)
        neg_loss = per_scene_weighted_mean(-torch.log1p(-pred), negative)
        losses.append(0.5 * (pos_loss + neg_loss))
    return torch.stack(losses).mean()


def controller_components(details, targets: SpatialTargets) -> dict[str, torch.Tensor]:
    sdf_weight = 0.05 + 0.95 * F.max_pool2d(targets.boundary_confidence, 9, stride=1, padding=4)
    sdf = per_scene_weighted_mean(
        F.smooth_l1_loss(details.normalized_sdf, targets.normalized_sdf, beta=0.08, reduction="none"),
        sdf_weight,
    )
    normal_dot = details.normal_x * targets.normal_x + details.normal_y * targets.normal_y
    # SDF sign is fixed (positive inside), so reversed normals are not
    # equivalent: they would invert the meaning of the learned shift.
    normal = per_scene_weighted_mean(0.5 * (1.0 - normal_dot.clamp(-1, 1)), targets.boundary_confidence + 1.0e-3)
    boundary_bce = balanced_boundary_bce(details.boundary_confidence, targets.boundary_confidence)
    boundary_dice = soft_dice(details.boundary_confidence, targets.boundary_confidence)
    need_error = F.smooth_l1_loss(details.correction_need, targets.need, beta=0.05, reduction="none")
    need_per_scene = per_scene_weighted_values(
        need_error,
        0.02 + F.max_pool2d(targets.boundary, 11, stride=1, padding=5),
    )
    degraded = ~(targets.identity | targets.flat)
    parts = []
    if bool(degraded.any()):
        parts.append(0.65 * need_per_scene[degraded].mean())
    if bool(targets.identity.any()):
        identity_need = per_scene_weighted_values(
            details.correction_need.square(), targets.boundary + 0.01
        )[targets.identity].mean()
        parts.append(0.25 * identity_need)
    if bool(targets.flat.any()):
        flat_need = details.correction_need[targets.flat].square().flatten(1).mean(1).mean()
        parts.append(0.10 * flat_need)
    need = sum(parts) / max(sum((0.65 if bool(degraded.any()) else 0.0, 0.25 if bool(targets.identity.any()) else 0.0, 0.10 if bool(targets.flat.any()) else 0.0)), 1.0e-6)
    recoverability = per_scene_weighted_mean(
        F.binary_cross_entropy(
            details.recoverability.clamp(1.0e-5, 1.0 - 1.0e-5),
            targets.recoverability,
            reduction="none",
        ),
        targets.boundary + 1.0e-3,
    )
    return {
        "sdf": sdf,
        "normal": normal,
        "boundary_bce": boundary_bce,
        "boundary_dice": boundary_dice,
        "need": need,
        "recoverability": recoverability,
    }


def controller_objective(components: Mapping[str, torch.Tensor], cycle: int) -> torch.Tensor:
    phase = cycle % 3
    if phase == 0:
        return components["sdf"] + 0.7 * components["normal"]
    if phase == 1:
        return components["boundary_bce"] + 0.7 * components["boundary_dice"]
    return components["need"] + 0.65 * components["recoverability"]


def geometry_parameter_components(details, targets: SpatialTargets) -> dict[str, torch.Tensor]:
    width = per_scene_weighted_mean(
        F.smooth_l1_loss(details.width_gain, targets.width_gain, beta=0.08, reduction="none"),
        targets.geometry_weight,
    )
    shift = per_scene_weighted_mean(
        F.smooth_l1_loss(details.normal_shift, targets.normal_shift, beta=0.10, reduction="none"),
        targets.geometry_weight,
    )
    width_gx, width_gy = finite_differences(details.width_gain)
    tangent_x, tangent_y = -targets.normal_y, targets.normal_x
    tangent_width = width_gx * tangent_x + width_gy * tangent_y
    shift_gx, shift_gy = finite_differences(details.normal_shift)
    tangent_shift = shift_gx * tangent_x + shift_gy * tangent_y
    coherence = per_scene_weighted_mean(
        tangent_width.abs() + 0.5 * tangent_shift.abs(),
        targets.boundary * targets.recoverability + 1.0e-3,
    )
    return {"width": width, "shift": shift, "tangent_coherence": coherence}


def render_components(details, batch, targets: SpatialTargets) -> dict[str, torch.Tensor]:
    target = batch["target"]
    mask = batch["mask"]
    midpoint = batch["midpoint"].reshape(-1, 1, 1, 1)
    polarity = batch["polarity"].reshape(-1, 1, 1, 1)
    soft_mask = torch.sigmoid(42.0 * polarity * (details.output - midpoint))
    contour_dice = soft_dice(soft_mask, mask)
    contour_bce = per_scene_mean(F.binary_cross_entropy(soft_mask.clamp(1e-5, 1 - 1e-5), mask, reduction="none"))
    reconstruction = per_scene_weighted_mean(
        F.smooth_l1_loss(details.output, target, beta=1.0 / 255.0, reduction="none"),
        0.10 + 0.90 * F.max_pool2d(targets.boundary, 9, stride=1, padding=4),
    )
    output_gx, output_gy = finite_differences(details.output)
    target_gx, target_gy = finite_differences(target)
    gradient = per_scene_weighted_mean(
        (output_gx - target_gx).abs() + (output_gy - target_gy).abs(),
        0.05 + targets.boundary,
    )
    identity_mask = batch["identity"].reshape(-1).bool()
    if bool(identity_mask.any()):
        identity = details.delta[identity_mask].abs().flatten(1).mean(1).mean()
    else:
        identity = details.delta.new_zeros(())
    return {
        "contour_dice": contour_dice,
        "contour_bce": contour_bce,
        "reconstruction": reconstruction,
        "gradient": gradient,
        "identity": identity,
    }


def detail_target(model, details, target: torch.Tensor, targets: SpatialTargets, identity: torch.Tensor) -> torch.Tensor:
    bound = 18.0 / 255.0
    residual = target.detach() - details.base_output.detach()
    carrier = 0.5 * bound * torch.tanh(residual / max(0.5 * bound, 1.0e-8))
    carrier = carrier * details.detail_gate.detach() * targets.recoverability
    projected = carrier - model.detail_projection(carrier)
    projected = projected.clone()
    projected[identity.reshape(-1).bool()] = 0
    return projected


def detail_components(model, details, target_detail: torch.Tensor, targets: SpatialTargets) -> dict[str, torch.Tensor]:
    detail = per_scene_weighted_mean(
        F.smooth_l1_loss(details.detail, target_detail, beta=1.0 / 255.0, reduction="none"),
        0.05 + targets.boundary * targets.recoverability,
    )
    zero_mean = per_scene_mean(F.avg_pool2d(details.detail, 17, stride=1, padding=8).abs())
    geometry_guard = per_scene_weighted_mean(
        (details.output - details.base_output.detach()).abs(),
        targets.boundary * (1.0 - targets.recoverability) + 1.0e-3,
    )
    return {"detail": detail, "detail_zero_mean": zero_mean, "detail_geometry_guard": geometry_guard}
