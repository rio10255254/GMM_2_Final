"""Staged R115 losses and online causal targets for the two R109 actions."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0))
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1))
    return gx, gy


def weighted(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    return (value * weight).sum() / weight.sum().clamp_min(1.0e-8)


def per_scene_weighted(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    numerator = (value * weight).flatten(1).sum(1)
    denominator = weight.flatten(1).sum(1).clamp_min(1.0e-8)
    return (numerator / denominator).mean()


def masked_mean(value: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weight = mask.to(dtype=value.dtype)
    return (value * weight).sum() / weight.sum().clamp_min(1.0)


def dice(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    numerator = 2 * (prediction * target).sum((1, 2, 3)) + 1.0e-6
    denominator = prediction.sum((1, 2, 3)) + target.sum((1, 2, 3)) + 1.0e-6
    return 1 - (numerator / denominator).mean()


def centroid(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    height, width = prediction.shape[-2:]
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=prediction.device),
        torch.linspace(-1, 1, width, device=prediction.device),
        indexing="ij",
    )
    xx = xx.view(1, 1, height, width)
    yy = yy.view(1, 1, height, width)
    prediction_mass = prediction.sum((2, 3)).clamp_min(1.0e-6)
    target_mass = target.sum((2, 3)).clamp_min(1.0e-6)
    return (
        torch.abs((prediction * xx).sum((2, 3)) / prediction_mass - (target * xx).sum((2, 3)) / target_mass)
        + torch.abs((prediction * yy).sum((2, 3)) / prediction_mass - (target * yy).sum((2, 3)) / target_mass)
    ).mean()


def detector_components(details, edge: torch.Tensor) -> dict[str, torch.Tensor]:
    boundary = F.max_pool2d(edge, 5, 1, 2).clamp(0, 1)
    positive = (1 - boundary.mean()).detach() / boundary.mean().clamp_min(1.0e-4).detach()
    return {
        "boundary_bce": F.binary_cross_entropy_with_logits(
            details.boundary_logits, boundary, pos_weight=positive
        ),
        "boundary_dice": dice(details.boundary, boundary),
    }


def parameter_tv(value: torch.Tensor) -> torch.Tensor:
    return (
        torch.abs(value[..., 1:] - value[..., :-1]).mean()
        + torch.abs(value[..., 1:, :] - value[..., :-1, :]).mean()
    )


def renderer_components(
    details,
    source: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    edge: torch.Tensor,
    identity: torch.Tensor,
    midpoint: torch.Tensor,
    polarity: torch.Tensor,
    width_gain_target: torch.Tensor,
) -> dict[str, torch.Tensor]:
    boundary = F.max_pool2d(edge, 5, 1, 2).clamp(0, 1)
    soft = torch.sigmoid(42 * polarity[:, None, None, None] * (details.output - midpoint[:, None, None, None]))
    contour = dice(soft, mask)
    contour_bce = F.binary_cross_entropy(soft.clamp(1.0e-5, 1 - 1.0e-5), mask)
    area = torch.abs(soft.mean((1, 2, 3)) - mask.mean((1, 2, 3))).mean()
    center = centroid(soft, mask)
    band = 0.06 + 0.94 * boundary
    direct = weighted(
        F.smooth_l1_loss(details.delta, target - source, beta=1 / 255, reduction="none"),
        band,
    )
    reconstruction = weighted(torch.abs(details.output - target), band)
    output_gx, output_gy = gradients(details.output)
    target_gx, target_gy = gradients(target)
    gradient = weighted(torch.abs(output_gx - target_gx) + torch.abs(output_gy - target_gy), band)
    identity_loss = details.delta[identity].abs().mean() if bool(identity.any()) else details.delta.sum() * 0
    smoothness = parameter_tv(details.width_gain) + parameter_tv(details.normal_shift)
    width_target = width_gain_target[:, None, None, None].expand_as(details.width_gain)
    width_loss = weighted(torch.abs(details.width_gain - width_target), boundary + 0.01)
    baseline_fidelity = weighted(torch.abs(details.output - details.baseline_output.detach()), band)
    return {
        "contour": contour,
        "contour_bce": contour_bce,
        "area": area,
        "centroid": center,
        "direct": direct,
        "reconstruction": reconstruction,
        "gradient": gradient,
        "identity": identity_loss,
        "parameter_smoothness": smoothness,
        "width_target": width_loss,
        "baseline_fidelity": baseline_fidelity,
    }


@dataclass(frozen=True)
class FactorTargets:
    factor: torch.Tensor
    support: torch.Tensor
    weight: torch.Tensor
    raw_alpha: torch.Tensor
    signed_gain: torch.Tensor


def factor_targets(
    candidate_delta: torch.Tensor,
    source: torch.Tensor,
    target: torch.Tensor,
    sdf: torch.Tensor,
    identity: torch.Tensor,
) -> FactorTargets:
    residual = target.detach() - source.detach()
    candidate = candidate_delta.detach()
    denominator = candidate.square().clamp_min((0.01 / 255) ** 2)
    raw_alpha = residual * candidate / denominator
    maximum_adjustment = float(CONFIG["model"]["maximum_action_factor_adjustment"])
    factor = raw_alpha.clamp(1.0 - maximum_adjustment, 1.0 + maximum_adjustment)
    identity_map = identity.reshape(-1, 1, 1, 1).bool()
    factor = torch.where(identity_map, torch.ones_like(factor), factor)
    best = (source.detach() + factor * candidate).clamp(0, 1)
    signed_gain = residual.square() - (target.detach() - best).square()
    band = sdf.detach().abs() <= 12.0
    actionable = candidate.abs() >= 0.25 / 255
    support = band & (actionable | identity_map)
    magnitude = (candidate.abs() * 255 / 4.0).clamp(0, 1)
    weight = support.to(source.dtype) * (0.2 + 0.8 * magnitude)
    return FactorTargets(
        factor=factor,
        support=support,
        weight=weight,
        raw_alpha=raw_alpha,
        signed_gain=signed_gain,
    )


def one_factor_components(
    prediction: torch.Tensor,
    targets: FactorTargets,
    prefix: str,
) -> dict[str, torch.Tensor]:
    element = F.smooth_l1_loss(prediction, targets.factor, beta=0.02, reduction="none")
    fit = per_scene_weighted(element, targets.weight)
    neutral = per_scene_weighted((prediction - 1.0).abs(), targets.weight * (targets.factor - 1.0).abs().lt(0.01))
    return {
        f"{prefix}_factor_fit": fit,
        f"{prefix}_neutral_guard": neutral,
        f"{prefix}_target_factor_mean": weighted(targets.factor, targets.weight),
    }


def profile_evidence_components(
    details,
    source: torch.Tensor,
    target: torch.Tensor,
    sdf: torch.Tensor,
    identity: torch.Tensor,
) -> tuple[dict[str, torch.Tensor], FactorTargets, FactorTargets]:
    shift_targets = factor_targets(details.shift_candidate_delta, source, target, sdf, identity)
    width_targets = factor_targets(details.width_candidate_delta, source, target, sdf, identity)
    components = {}
    components.update(one_factor_components(
        details.shift_factor, shift_targets, "shift"
    ))
    components.update(one_factor_components(
        details.width_factor, width_targets, "width"
    ))
    boundary = (sdf.abs() <= 12.0).to(dtype=source.dtype)
    base_error = (details.baseline_output.detach() - target).abs()
    final_error = (details.output - target).abs()
    components["final_gain_guard"] = per_scene_weighted(F.relu(final_error - base_error), boundary)
    components["final_reconstruction"] = per_scene_weighted(final_error, boundary)
    components["identity_selector_delta"] = (
        (details.output - details.baseline_output.detach())[identity].abs().mean()
        if bool(identity.any()) else details.output.sum() * 0
    )
    return components, shift_targets, width_targets


def profile_objective(components: dict[str, torch.Tensor]) -> torch.Tensor:
    factor_weight = float(CONFIG["short_probe"]["factor_fit_weight"])
    gain_weight = float(CONFIG["short_probe"]["final_gain_guard_weight"])
    total = components["final_gain_guard"] * gain_weight + components["identity_selector_delta"]
    for prefix in ("shift", "width"):
        total = (
            total
            + factor_weight * components[f"{prefix}_factor_fit"]
            + 0.15 * components[f"{prefix}_neutral_guard"]
        )
    return total


def combine_renderer(components: dict[str, torch.Tensor]) -> torch.Tensor:
    weights = {
        "contour": 0.60,
        "contour_bce": 0.12,
        "area": 0.22,
        "centroid": 0.16,
        "direct": 0.90,
        "reconstruction": 0.42,
        "gradient": 0.18,
        "identity": 1.50,
        "parameter_smoothness": 0.035,
        "width_target": 0.05,
        "baseline_fidelity": 0.12,
    }
    return sum(float(weights[name]) * value for name, value in components.items() if name in weights)
