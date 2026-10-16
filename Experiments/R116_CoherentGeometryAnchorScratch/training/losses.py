"""Stage-separated R116 objectives.

The functions deliberately return components rather than one permanent global
sum.  A future formal trainer must alternate detector, width, shift, and detail
parameter groups according to the experiment contract.
"""

from __future__ import annotations

from typing import Mapping

import torch
import torch.nn.functional as F


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0), mode="replicate")
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1), mode="replicate")
    return gx, gy


def weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    value = value.float()
    weight = weight.float()
    return (value * weight).sum() / weight.sum().clamp_min(1.0e-8)


def probability_bce(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Autocast-safe BCE for probabilities already bounded by the model."""
    # BF16 rounds 0.99999 to exactly one, so the clamp must happen after
    # promotion to FP32 or log1p(-prediction) can still become -infinity.
    prediction = prediction.float().clamp(1.0e-6, 1.0 - 1.0e-6)
    target = target.float().clamp(0.0, 1.0)
    return -(target * torch.log(prediction) + (1.0 - target) * torch.log1p(-prediction))


def soft_dice(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    prediction = prediction.float()
    target = target.float()
    numerator = 2.0 * (prediction * target).flatten(1).sum(1) + 1.0e-6
    denominator = prediction.flatten(1).sum(1) + target.flatten(1).sum(1) + 1.0e-6
    return 1.0 - (numerator / denominator).mean()


def centroid(value: torch.Tensor) -> torch.Tensor:
    value = value.float()
    height, width = value.shape[-2:]
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=value.device, dtype=value.dtype),
        torch.linspace(-1, 1, width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    mass = value.flatten(2).sum(2).clamp_min(1.0e-6)
    center_x = (value * xx.view(1, 1, height, width)).flatten(2).sum(2) / mass
    center_y = (value * yy.view(1, 1, height, width)).flatten(2).sum(2) / mass
    return torch.stack((center_x, center_y), dim=-1)


def detector_components(details, target_sdf_px: torch.Tensor,
                        target_boundary: torch.Tensor,
                        maximum_sdf_px: float = 12.0) -> dict[str, torch.Tensor]:
    target_boundary = target_boundary.float()
    boundary_logits = details.boundary_logits.float()
    boundary_confidence = details.boundary_confidence.float()
    predicted_sdf_px = details.predicted_sdf_px.float()
    positive = (1.0 - target_boundary.mean()).detach() / target_boundary.mean().clamp_min(1.0e-4).detach()
    boundary_bce = F.binary_cross_entropy_with_logits(
        boundary_logits,
        target_boundary,
        pos_weight=positive,
    )
    boundary_dice = soft_dice(boundary_confidence, target_boundary)
    target_sdf_px = target_sdf_px.float().clamp(-float(maximum_sdf_px), float(maximum_sdf_px))
    sdf_band = torch.exp(-target_sdf_px.abs() / 3.0)
    sdf_error = F.smooth_l1_loss(
        predicted_sdf_px, target_sdf_px, beta=0.25, reduction="none",
    )
    signed_losses = []
    for region in (target_sdf_px < 0.0, target_sdf_px >= 0.0):
        weight = sdf_band * region.to(sdf_band.dtype)
        if bool(weight.sum() > 0):
            signed_losses.append(weighted_mean(sdf_error, weight))
    sdf = torch.stack(signed_losses).mean()
    return {"boundary_bce": boundary_bce, "boundary_dice": boundary_dice, "sdf": sdf}


def geometry_components(details, target: torch.Tensor, target_mask: torch.Tensor,
                        midpoint: torch.Tensor, polarity: torch.Tensor,
                        identity: torch.Tensor) -> dict[str, torch.Tensor]:
    output = details.output.float()
    target = target.float()
    target_mask = target_mask.float()
    threshold = midpoint.float()[:, None, None, None]
    sign = polarity.float()[:, None, None, None]
    soft = torch.sigmoid(42.0 * sign * (output - threshold))
    contour = soft_dice(soft, target_mask)
    center = torch.abs(centroid(soft) - centroid(target_mask)).mean()
    edge = torch.exp(-details.predicted_sdf_px.detach().float().abs() / 3.0)
    reconstruction = weighted_mean(torch.abs(output - target), 0.05 + 0.95 * edge)
    anchor_low_frequency = details.low_frequency_leakage.float().abs().mean()
    identity_loss = (
        torch.abs(output[identity] - target[identity]).mean()
        if bool(identity.any())
        else output.sum() * 0.0
    )
    return {
        "contour": contour,
        "centroid": center,
        "reconstruction": reconstruction,
        "anchor_low_frequency": anchor_low_frequency,
        "identity": identity_loss,
    }


def width_action_components(details, target_width_gain: torch.Tensor,
                            reliability: torch.Tensor,
                            boundary_band: torch.Tensor) -> dict[str, torch.Tensor]:
    width_gain = details.width_gain.float()
    valid = boundary_band.float().clamp(0.0, 1.0)
    reliability = reliability.float().clamp(0.0, 1.0)
    reliable = (valid * reliability).clamp(0.0, 1.0)
    fit = weighted_mean(
        F.smooth_l1_loss(width_gain, target_width_gain.float(), beta=0.04, reduction="none"),
        0.05 * valid + 0.95 * reliable,
    )
    confidence = probability_bce(details.width_confidence, reliability)
    confidence = weighted_mean(confidence, valid + 1.0e-4)
    neutral = weighted_mean(
        torch.abs(width_gain - 1.0),
        (1.0 - valid).clamp(0.0, 1.0) + 0.01,
    )
    return {"fit": fit, "confidence": confidence, "neutral": neutral}


def shift_action_components(details, target_normal_shift: torch.Tensor,
                            reliability: torch.Tensor,
                            boundary_band: torch.Tensor) -> dict[str, torch.Tensor]:
    normal_shift = details.normal_shift.float()
    valid = boundary_band.float().clamp(0.0, 1.0)
    reliability = reliability.float().clamp(0.0, 1.0)
    reliable = (valid * reliability).clamp(0.0, 1.0)
    fit = weighted_mean(
        F.smooth_l1_loss(normal_shift, target_normal_shift.float(), beta=0.04, reduction="none"),
        0.05 * valid + 0.95 * reliable,
    )
    confidence = probability_bce(details.shift_confidence, reliability)
    confidence = weighted_mean(confidence, valid + 1.0e-4)
    neutral = weighted_mean(
        normal_shift.abs(),
        (1.0 - valid).clamp(0.0, 1.0) + 0.01,
    )
    return {"fit": fit, "confidence": confidence, "neutral": neutral}


def detail_components(details, target: torch.Tensor, identity: torch.Tensor) -> dict[str, torch.Tensor]:
    target = target.float()
    geometry_anchor = details.geometry_anchor.detach().float()
    output = details.output.float()
    bounded_detail = details.bounded_detail.float()
    target_residual = target - geometry_anchor
    output_residual = output - geometry_anchor
    target_gx, target_gy = gradients(target_residual)
    output_gx, output_gy = gradients(output_residual)
    high_frequency = (torch.abs(output_gx - target_gx) + torch.abs(output_gy - target_gy)).mean()
    reconstruction = torch.abs(output - target).mean()
    local_mean = details.low_frequency_leakage.float().abs().mean()
    identity_loss = (
        bounded_detail[identity].abs().mean()
        if bool(identity.any())
        else output.sum() * 0.0
    )
    bound = F.relu(bounded_detail.abs() - 18.0 / 255.0).mean()
    return {
        "high_frequency": high_frequency,
        "reconstruction": reconstruction,
        "local_mean": local_mean,
        "identity": identity_loss,
        "bound": bound,
    }


def warp_translation(value: torch.Tensor, dx_px: torch.Tensor,
                     dy_px: torch.Tensor) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    theta = torch.zeros((batch, 2, 3), device=value.device, dtype=value.dtype)
    theta[:, 0, 0] = 1.0
    theta[:, 1, 1] = 1.0
    theta[:, 0, 2] = -2.0 * dx_px / max(width - 1, 1)
    theta[:, 1, 2] = -2.0 * dy_px / max(height - 1, 1)
    grid = F.affine_grid(theta, value.shape, align_corners=True)
    return F.grid_sample(value, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def translation_consistency(details_a, details_b, dx_px: torch.Tensor,
                            dy_px: torch.Tensor, margin: int = 20) -> dict[str, torch.Tensor]:
    def crop(value: torch.Tensor) -> torch.Tensor:
        return value[..., margin:-margin, margin:-margin]

    output_a, output_b = details_a.output.float(), details_b.output.float()
    sdf_a, sdf_b = details_a.predicted_sdf_px.float(), details_b.predicted_sdf_px.float()
    width_a, width_b = details_a.width_gain.float(), details_b.width_gain.float()
    shift_a, shift_b = details_a.normal_shift.float(), details_b.normal_shift.float()
    expected_output = warp_translation(output_a, dx_px.float(), dy_px.float())
    expected_sdf = warp_translation(sdf_a, dx_px.float(), dy_px.float())
    expected_width = warp_translation(width_a, dx_px.float(), dy_px.float())
    expected_shift = warp_translation(shift_a, dx_px.float(), dy_px.float())
    return {
        "output": F.smooth_l1_loss(crop(output_b), crop(expected_output), beta=0.25 / 255.0),
        "sdf": F.smooth_l1_loss(crop(sdf_b), crop(expected_sdf), beta=0.05),
        "width": F.smooth_l1_loss(crop(width_b), crop(expected_width), beta=0.01),
        "shift": F.smooth_l1_loss(crop(shift_b), crop(expected_shift), beta=0.01),
    }


def combine(components: Mapping[str, torch.Tensor], weights: Mapping[str, float]) -> torch.Tensor:
    return sum(float(weights.get(name, 0.0)) * value for name, value in components.items())
