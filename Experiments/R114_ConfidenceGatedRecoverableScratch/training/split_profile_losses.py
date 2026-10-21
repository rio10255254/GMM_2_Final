"""Stage-specific losses for R114 split geometry and bounded profiles.

This module is intentionally independent from ``training.losses``.  It does
not define a permanent weighted sum.  Reliability, width, shift, and profile
heads are optimized through separate entry points so the next scratch probe
cannot silently recreate the E020 width/shift conflict.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import torch
import torch.nn.functional as F

from .split_profile_targets import (
    MAXIMUM_ACTION_GRAY,
    MAXIMUM_CONTRAST_GRAY,
    MAXIMUM_MIDPOINT_OFFSET_GRAY,
    MAXIMUM_NORMAL_SHIFT_PX,
    MAXIMUM_PROFILE_WIDTH_PX,
    MAXIMUM_WIDTH_GAIN,
    MINIMUM_PROFILE_WIDTH_PX,
    MINIMUM_WIDTH_GAIN,
    SplitProfileTargets,
)


def _field(value: Any, *names: str) -> torch.Tensor:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    raise KeyError(f"none of {names!r} are present")


def per_scene_weighted_values(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    if value.shape != weight.shape:
        weight = weight.expand_as(value)
    numerator = (value * weight).flatten(1).sum(1)
    denominator = weight.flatten(1).sum(1).clamp_min(1.0e-6)
    return numerator / denominator


def per_scene_weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return per_scene_weighted_values(value, weight).mean()


def per_scene_mean(value: torch.Tensor) -> torch.Tensor:
    return value.flatten(1).mean(1).mean()


def _finite_differences(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    padded = F.pad(value, (1, 1, 1, 1), mode="replicate")
    gx = 0.5 * (padded[..., 1:-1, 2:] - padded[..., 1:-1, :-2])
    gy = 0.5 * (padded[..., 2:, 1:-1] - padded[..., :-2, 1:-1])
    return gx, gy


def balanced_soft_bce(
    prediction: torch.Tensor,
    target: torch.Tensor,
    support: torch.Tensor,
) -> torch.Tensor:
    """Per-scene balanced BCE that keeps all-negative flat scenes.

    Soft positives and negatives are normalized independently for each image.
    If a scene has no positive support, its negative term remains active rather
    than dropping that scene from the batch.
    """

    prediction = prediction.clamp(1.0e-5, 1.0 - 1.0e-5)
    target = target.clamp(0, 1)
    support = support.clamp(0, 1)
    positive_weight = support * target
    negative_weight = support * (1.0 - target)
    positive_loss = per_scene_weighted_values(-torch.log(prediction), positive_weight)
    negative_loss = per_scene_weighted_values(-torch.log1p(-prediction), negative_weight)
    positive_mass = positive_weight.flatten(1).sum(1)
    negative_mass = negative_weight.flatten(1).sum(1)
    positive_valid = (positive_mass > 1.0e-6).to(prediction.dtype)
    negative_valid = (negative_mass > 1.0e-6).to(prediction.dtype)
    denominator = (positive_valid + negative_valid).clamp_min(1.0)
    return ((positive_valid * positive_loss + negative_valid * negative_loss) / denominator).mean()


def _mean_calibration(
    prediction: torch.Tensor,
    target: torch.Tensor,
    support: torch.Tensor,
) -> torch.Tensor:
    predicted_mean = per_scene_weighted_values(prediction, support)
    target_mean = per_scene_weighted_values(target, support)
    return (predicted_mean - target_mean).abs().mean()


def _within_scene_rank(
    prediction: torch.Tensor,
    target: torch.Tensor,
    support: torch.Tensor,
    margin: float = 0.20,
) -> torch.Tensor:
    """Require high-reliability regions to outrank low regions per image."""

    high_weight = support * ((target - 0.55) / 0.45).clamp(0, 1)
    low_weight = support * ((0.25 - target) / 0.25).clamp(0, 1)
    high_mean = per_scene_weighted_values(prediction, high_weight)
    low_mean = per_scene_weighted_values(prediction, low_weight)
    valid = (high_weight.flatten(1).sum(1) > 1.0e-6) & (low_weight.flatten(1).sum(1) > 1.0e-6)
    if not bool(valid.any()):
        return prediction.sum() * 0.0
    return F.relu(margin - (high_mean[valid] - low_mean[valid])).mean()


def reliability_components(
    predictions: Any,
    targets: SplitProfileTargets,
) -> dict[str, torch.Tensor]:
    """Independent width and shift reliability supervision."""

    width_prediction = _field(predictions, "width_reliability")
    shift_prediction = _field(predictions, "shift_reliability")
    # Boundary support retains the flat negative scene by explicitly using a
    # full-image support there.  Non-flat scenes remain confined to the 14 px
    # action band.
    support = targets.boundary_band.clone()
    if bool(targets.flat.any()):
        support[targets.flat] = 1.0
    return {
        "width_balanced_bce": balanced_soft_bce(width_prediction, targets.width_reliability, support),
        "width_mean_calibration": _mean_calibration(width_prediction, targets.width_reliability, support),
        "width_rank": _within_scene_rank(width_prediction, targets.width_reliability, support),
        "shift_balanced_bce": balanced_soft_bce(shift_prediction, targets.shift_reliability, support),
        "shift_mean_calibration": _mean_calibration(shift_prediction, targets.shift_reliability, support),
        "shift_rank": _within_scene_rank(shift_prediction, targets.shift_reliability, support),
    }


def width_reliability_objective(components: Mapping[str, torch.Tensor]) -> torch.Tensor:
    return (
        components["width_balanced_bce"]
        + 0.35 * components["width_mean_calibration"]
        + 0.25 * components["width_rank"]
    )


def shift_reliability_objective(components: Mapping[str, torch.Tensor]) -> torch.Tensor:
    return (
        components["shift_balanced_bce"]
        + 0.35 * components["shift_mean_calibration"]
        + 0.25 * components["shift_rank"]
    )


def width_action_components(
    predictions: Any,
    targets: SplitProfileTargets,
) -> dict[str, torch.Tensor]:
    """Width fit/neutral/coherence losses for a width-only optimizer step."""

    width = _field(predictions, "width_gain")
    # width_gain is already attenuated toward one by oracle reliability;
    # width_weight is valid spatial support only.  Do not multiply by
    # width_reliability again: that would be the diagnosed double suppression.
    fit = per_scene_weighted_mean(
        F.smooth_l1_loss(width, targets.width_gain, beta=0.08, reduction="none"),
        targets.width_weight,
    )
    neutral_weight = targets.boundary_band * (1.0 - targets.width_reliability)
    neutral = per_scene_weighted_mean(
        F.smooth_l1_loss(width, torch.ones_like(width), beta=0.05, reduction="none"),
        neutral_weight,
    )
    gx, gy = _finite_differences(width)
    tangent = gx * (-targets.normal_y) + gy * targets.normal_x
    coherence = per_scene_weighted_mean(tangent.abs(), targets.width_weight)
    range_guard = per_scene_mean(
        F.relu(MINIMUM_WIDTH_GAIN - width) + F.relu(width - MAXIMUM_WIDTH_GAIN)
    )
    return {
        "width_fit": fit,
        "width_neutral": neutral,
        "width_tangent_coherence": coherence,
        "width_range_guard": range_guard,
    }


def width_action_objective(components: Mapping[str, torch.Tensor]) -> torch.Tensor:
    return (
        components["width_fit"]
        + 0.35 * components["width_neutral"]
        + 0.08 * components["width_tangent_coherence"]
        + components["width_range_guard"]
    )


def shift_action_components(
    predictions: Any,
    targets: SplitProfileTargets,
) -> dict[str, torch.Tensor]:
    """Shift fit/neutral/coherence losses for a shift-only optimizer step."""

    shift = _field(predictions, "normal_shift")
    fit = per_scene_weighted_mean(
        F.smooth_l1_loss(shift, targets.normal_shift, beta=0.10, reduction="none"),
        targets.shift_weight,
    )
    neutral_weight = targets.boundary_band * (1.0 - targets.shift_reliability)
    neutral = per_scene_weighted_mean(
        F.smooth_l1_loss(shift, torch.zeros_like(shift), beta=0.06, reduction="none"),
        neutral_weight,
    )
    gx, gy = _finite_differences(shift)
    tangent = gx * (-targets.normal_y) + gy * targets.normal_x
    coherence = per_scene_weighted_mean(tangent.abs(), targets.shift_weight)
    range_guard = per_scene_mean(F.relu(shift.abs() - MAXIMUM_NORMAL_SHIFT_PX))
    return {
        "shift_fit": fit,
        "shift_neutral": neutral,
        "shift_tangent_coherence": coherence,
        "shift_range_guard": range_guard,
    }


def shift_action_objective(components: Mapping[str, torch.Tensor]) -> torch.Tensor:
    return (
        components["shift_fit"]
        + 0.45 * components["shift_neutral"]
        + 0.08 * components["shift_tangent_coherence"]
        + components["shift_range_guard"]
    )


def _focal_soft_bce(
    prediction: torch.Tensor,
    target: torch.Tensor,
    weight: torch.Tensor,
    gamma: float = 2.0,
) -> torch.Tensor:
    prediction = prediction.clamp(1.0e-5, 1.0 - 1.0e-5)
    target = target.clamp(0, 1)
    bce = -(target * torch.log(prediction) + (1.0 - target) * torch.log1p(-prediction))
    probability_true = target * prediction + (1.0 - target) * (1.0 - prediction)
    return per_scene_weighted_mean((1.0 - probability_true).pow(gamma) * bce, weight)


def _weighted_soft_dice(
    prediction: torch.Tensor,
    target: torch.Tensor,
    weight: torch.Tensor,
) -> torch.Tensor:
    intersection = (weight * prediction * target).flatten(1).sum(1)
    denominator = (weight * (prediction + target)).flatten(1).sum(1)
    return (1.0 - (2.0 * intersection + 1.0e-6) / (denominator + 1.0e-6)).mean()


def analytic_profile_image(
    predictions: Any,
    targets: SplitProfileTargets,
) -> torch.Tensor:
    # During real training, use the exact proposal produced by the deployable
    # model.  The fallback keeps small target-only unit tests readable while
    # still using the deployment coordinate when it is available.
    if hasattr(predictions, "profile_proposal"):
        return _field(predictions, "profile_proposal")
    midpoint_offset = _field(predictions, "midpoint_offset", "midpoint_offset_gray")
    signed_contrast = _field(
        predictions,
        "signed_plateau_contrast",
        "signed_contrast",
        "signed_contrast_gray",
    )
    width = _field(predictions, "profile_width", "profile_width_px").clamp_min(1.0e-4)
    midpoint = targets.raw_midpoint_cue + midpoint_offset
    coordinate = getattr(targets, "deployment_sdf", targets.sdf)
    return midpoint + 0.5 * signed_contrast * torch.tanh(coordinate / width)


def profile_parameter_components(
    predictions: Any,
    targets: SplitProfileTargets,
) -> dict[str, torch.Tensor]:
    """Parameter, visibility, profile-fit, and physical guard losses."""

    midpoint_offset = _field(predictions, "midpoint_offset", "midpoint_offset_gray")
    signed_contrast = _field(
        predictions,
        "signed_plateau_contrast",
        "signed_contrast",
        "signed_contrast_gray",
    )
    width = _field(predictions, "profile_width", "profile_width_px")
    visibility = _field(predictions, "profile_visibility", "visibility")
    parameter_weight = targets.profile_weight * targets.profile_visibility.clamp_min(0.05)

    midpoint = per_scene_weighted_mean(
        F.smooth_l1_loss(midpoint_offset, targets.midpoint_offset, beta=2.0 / 255.0, reduction="none"),
        parameter_weight,
    )
    contrast = per_scene_weighted_mean(
        F.smooth_l1_loss(
            signed_contrast,
            targets.signed_plateau_contrast,
            beta=2.0 / 255.0,
            reduction="none",
        ),
        parameter_weight,
    )
    profile_width = per_scene_weighted_mean(
        F.smooth_l1_loss(width, targets.profile_width, beta=0.08, reduction="none"),
        parameter_weight,
    )
    visibility_weight = getattr(
        targets,
        "profile_visibility_weight",
        targets.boundary_band + targets.flat.reshape(-1, 1, 1, 1).to(visibility.dtype),
    )
    visibility_focal = _focal_soft_bce(
        visibility,
        targets.profile_visibility,
        visibility_weight,
    )
    visibility_dice = _weighted_soft_dice(
        visibility,
        targets.profile_visibility,
        visibility_weight,
    )

    proposal = analytic_profile_image(predictions, targets)
    profile_output = _field(predictions, "profile_output", "output")
    base_image = getattr(targets, "base_image", targets.source_image)
    target_contrast = targets.signed_plateau_contrast.abs().clamp_min(4.0 / 255.0)
    normalized_profile_error = (profile_output - targets.target_image).abs() / target_contrast
    deployment_sdf = getattr(targets, "deployment_sdf", targets.sdf)
    deployment_band = getattr(targets, "deployment_band", targets.boundary_band)
    # Supervise the exact final output over the same predicted coordinate and
    # gate support used at inference.  True SDF contributes paired truth
    # support, but never replaces the deployment coordinate.
    transition_weight = (deployment_band + targets.boundary_band).clamp(0, 1) * (
        0.45
        + 0.55
        * torch.exp(-deployment_sdf.abs() / targets.profile_width.clamp_min(0.8))
    )
    profile_fit = per_scene_weighted_mean(
        F.smooth_l1_loss(
            normalized_profile_error,
            torch.zeros_like(normalized_profile_error),
            beta=0.04,
            reduction="none",
        ),
        transition_weight * targets.profile_reliability.clamp_min(0.05),
    )
    base_error = (base_image - targets.target_image).abs()
    final_error = (profile_output - targets.target_image).abs()
    gain_guard = per_scene_weighted_mean(
        F.relu(final_error - base_error),
        transition_weight,
    )
    final_reconstruction = per_scene_weighted_mean(
        F.smooth_l1_loss(
            profile_output,
            targets.target_image,
            beta=2.0 / 255.0,
            reduction="none",
        ),
        transition_weight,
    )

    target_sign = torch.sign(targets.signed_plateau_contrast)
    polarity_guard = per_scene_weighted_mean(
        F.relu(-signed_contrast * target_sign), targets.profile_weight
    )
    # For the analytic tanh renderer the derivative sign is exactly the signed
    # contrast sign.  This is therefore an explicit monotonicity guard rather
    # than a second free-form image-gradient loss.
    monotonicity_guard = polarity_guard
    predicted_midpoint = targets.raw_midpoint_cue + midpoint_offset
    plateau_a = predicted_midpoint - 0.5 * signed_contrast
    plateau_b = predicted_midpoint + 0.5 * signed_contrast
    overshoot_guard = per_scene_weighted_mean(
        F.relu(-plateau_a)
        + F.relu(plateau_a - 1.0)
        + F.relu(-plateau_b)
        + F.relu(plateau_b - 1.0),
        targets.profile_weight,
    )
    parameter_range_guard = per_scene_mean(
        F.relu(midpoint_offset.abs() - MAXIMUM_MIDPOINT_OFFSET_GRAY / 255.0)
        + F.relu(signed_contrast.abs() - MAXIMUM_CONTRAST_GRAY / 255.0)
        + F.relu(MINIMUM_PROFILE_WIDTH_PX - width)
        + F.relu(width - MAXIMUM_PROFILE_WIDTH_PX)
    )

    action_delta = profile_output - base_image
    action_bound_guard = per_scene_mean(
        F.relu(action_delta.abs() - MAXIMUM_ACTION_GRAY / 255.0)
    )
    outside_band_guard = per_scene_weighted_mean(
        action_delta.abs(), 1.0 - deployment_band
    )
    local_mean_guard = per_scene_mean(
        F.avg_pool2d(action_delta, 29, stride=1, padding=14).abs()
    )
    identity_or_flat = targets.identity | targets.flat
    if bool(identity_or_flat.any()):
        identity_guard = action_delta[identity_or_flat].abs().flatten(1).mean(1).mean()
    else:
        identity_guard = action_delta.sum() * 0.0

    return {
        "profile_midpoint_fit": midpoint,
        "profile_contrast_fit": contrast,
        "profile_width_fit": profile_width,
        "profile_visibility_focal": visibility_focal,
        "profile_visibility_dice": visibility_dice,
        "profile_normal_fit": profile_fit,
        "profile_final_reconstruction": final_reconstruction,
        "profile_gain_guard": gain_guard,
        "profile_polarity_guard": polarity_guard,
        "profile_monotonicity_guard": monotonicity_guard,
        "profile_overshoot_guard": overshoot_guard,
        "profile_parameter_range_guard": parameter_range_guard,
        "profile_action_bound_guard": action_bound_guard,
        "profile_outside_band_guard": outside_band_guard,
        "profile_local_mean_guard": local_mean_guard,
        "profile_identity_guard": identity_guard,
    }


def profile_parameter_objective(components: Mapping[str, torch.Tensor]) -> torch.Tensor:
    """Profile-only objective; never combine with width/shift in one step."""

    return (
        components["profile_midpoint_fit"]
        + components["profile_contrast_fit"]
        + components["profile_width_fit"]
        + components["profile_visibility_focal"]
        + 0.50 * components["profile_visibility_dice"]
        + 0.65 * components["profile_normal_fit"]
        + 0.65 * components["profile_final_reconstruction"]
        + 1.50 * components["profile_gain_guard"]
        + 0.35 * components["profile_polarity_guard"]
        + 0.15 * components["profile_monotonicity_guard"]
        + 0.35 * components["profile_overshoot_guard"]
        + components["profile_parameter_range_guard"]
        + components["profile_action_bound_guard"]
        + 0.50 * components["profile_outside_band_guard"]
        + 0.15 * components["profile_local_mean_guard"]
        + components["profile_identity_guard"]
    )


__all__ = [
    "balanced_soft_bce",
    "reliability_components",
    "width_reliability_objective",
    "shift_reliability_objective",
    "width_action_components",
    "width_action_objective",
    "shift_action_components",
    "shift_action_objective",
    "analytic_profile_image",
    "profile_parameter_components",
    "profile_parameter_objective",
    "per_scene_weighted_mean",
    "per_scene_weighted_values",
]
