"""Geometry-first losses for R117's center-locked output contract."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def weighted_mean(value: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    value, weight = value.float(), weight.float()
    return (value * weight).sum() / weight.sum().clamp_min(1.0e-8)


def soft_dice_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    prediction, target = prediction.float(), target.float()
    numerator = 2 * (prediction * target).flatten(1).sum(1) + 1.0e-6
    denominator = prediction.flatten(1).sum(1) + target.flatten(1).sum(1) + 1.0e-6
    return 1.0 - (numerator / denominator).mean()


def gradients(value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0), mode="replicate")
    gy = F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1), mode="replicate")
    return gx, gy


def centroid(value: torch.Tensor) -> torch.Tensor:
    height, width = value.shape[-2:]
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=value.device),
        torch.linspace(-1, 1, width, device=value.device), indexing="ij",
    )
    mass = value.float().flatten(2).sum(2).clamp_min(1.0e-6)
    x = (value.float() * xx.view(1, 1, height, width)).flatten(2).sum(2) / mass
    y = (value.float() * yy.view(1, 1, height, width)).flatten(2).sum(2) / mass
    return torch.stack((x, y), -1)


def detector_loss(detection, target_sdf_2x: torch.Tensor, weights: dict) -> tuple[torch.Tensor, dict]:
    sdf = target_sdf_2x.float().clamp(-12, 12)
    edge = torch.exp(-sdf.abs() / 2.5)
    logits = detection.high_boundary_logits.float()
    positive = (1.0 - edge.mean()).detach() / edge.mean().clamp_min(1.0e-4).detach()
    bce = F.binary_cross_entropy_with_logits(logits, edge, pos_weight=positive)
    dice = soft_dice_loss(torch.sigmoid(logits), edge)
    band = torch.exp(-sdf.abs() / 3.0)
    distance = weighted_mean(F.smooth_l1_loss(detection.high_predicted_sdf_px.float(), sdf, beta=0.125, reduction="none"), band)
    total = weights["detector_boundary"] * bce + weights["detector_dice"] * dice + weights["detector_sdf"] * distance
    return total, {"boundary_bce": bce, "boundary_dice": dice, "sdf": distance}


def soft_object(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(42.0 * polarity[:, None, None, None].float() * (image.float() - midpoint[:, None, None, None].float()))


def edge_center_coordinate(image: torch.Tensor, target_sdf: torch.Tensor) -> torch.Tensor:
    gx, gy = gradients(image.float())
    magnitude = torch.sqrt(gx.square() + gy.square() + 1.0e-8)
    band = torch.exp(-target_sdf.float().abs() / 4.0)
    weight = magnitude * band
    return (weight * target_sdf.float()).flatten(1).sum(1) / weight.flatten(1).sum(1).clamp_min(1.0e-6)


def geometry_terms(details, batch: dict) -> dict:
    output, target = details.output.float(), batch["target"].float()
    soft = soft_object(output, batch["midpoint"], batch["polarity"])
    raw_soft = soft_object(batch["source"], batch["midpoint"], batch["polarity"])
    target_mask = batch["mask"].float()
    contour = soft_dice_loss(soft, target_mask)
    center = torch.abs(centroid(soft) - centroid(target_mask)).mean()
    reconstruction = weighted_mean(torch.abs(output - target), 0.08 + 0.92 * torch.exp(-batch["sdf"].float().abs() / 4.0))
    output_coordinate = edge_center_coordinate(output, batch["sdf"])
    target_coordinate = edge_center_coordinate(target, batch["sdf"])
    center_lock = torch.abs(output_coordinate - target_coordinate).mean()
    identity = torch.abs(output[batch["identity"]] - target[batch["identity"]]).mean() if bool(batch["identity"].any()) else output.sum() * 0
    return {"contour": contour, "center": center, "reconstruction": reconstruction, "center_lock": center_lock, "identity": identity, "raw_contour": soft_dice_loss(raw_soft, target_mask)}


def width_loss(details, batch: dict, weights: dict) -> tuple[torch.Tensor, dict]:
    band = torch.exp(-batch["sdf"].float().abs() / 3.0)
    reliable = band * batch["known_width_reliability"].float()
    known = weighted_mean(F.smooth_l1_loss(details.width_gain.float(), batch["known_width_gain"].float(), beta=0.05, reduction="none"), reliable + 0.02 * band)
    geometry = geometry_terms(details, batch)
    total = (
        weights["width_known_fit"] * known + weights["width_reconstruction"] * geometry["reconstruction"]
        + weights["width_contour"] * geometry["contour"] + weights["width_center"] * geometry["center_lock"]
        + weights["width_identity"] * geometry["identity"]
    )
    return total, {"known_fit": known, **geometry}


def shift_loss(details, batch: dict, weights: dict) -> tuple[torch.Tensor, dict]:
    band = torch.exp(-batch["sdf"].float().abs() / 2.5)
    predicted = (details.normal_shift.float() * band).flatten(1).sum(1) / band.flatten(1).sum(1).clamp_min(1.0e-6)
    source_center = edge_center_coordinate(batch["source"], batch["sdf"])
    target_center = edge_center_coordinate(batch["target"], batch["sdf"])
    direct_target = (source_center - target_center).clamp(-1.25, 1.25)
    direct_fit = F.smooth_l1_loss(predicted, direct_target, beta=0.04)
    geometry = geometry_terms(details, batch)
    total = (
        weights["shift_direct_fit"] * direct_fit + weights["shift_reconstruction"] * geometry["reconstruction"]
        + weights["shift_contour"] * geometry["contour"] + weights["shift_center"] * geometry["center_lock"]
        + weights["shift_identity"] * geometry["identity"]
    )
    return total, {"direct_fit": direct_fit, "target_shift_abs": direct_target.abs().mean(), **geometry}


def detail_loss(details, batch: dict, weights: dict) -> tuple[torch.Tensor, dict]:
    output, target = details.output.float(), batch["target"].float()
    ogx, ogy = gradients(output)
    tgx, tgy = gradients(target)
    gradient = (torch.abs(ogx - tgx) + torch.abs(ogy - tgy)).mean()
    geometry = geometry_terms(details, batch)
    local_mean = details.low_frequency_leakage.float().abs().mean()
    odd_violation = weighted_mean(
        torch.abs(details.pre_projection_detail.float() + details.reflected_detail.float()),
        torch.exp(-batch["sdf"].float().abs() / 2.5),
    )
    total = (
        weights["detail_gradient"] * gradient + weights["detail_reconstruction"] * geometry["reconstruction"]
        + weights["detail_center_lock"] * (geometry["center_lock"] + 0.25 * odd_violation)
        + weights["detail_local_mean"] * local_mean + weights["detail_identity"] * geometry["identity"]
    )
    return total, {"gradient": gradient, "local_mean": local_mean, "odd_violation": odd_violation, **geometry}


def warp_translation(value: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    theta = torch.zeros((batch, 2, 3), device=value.device, dtype=value.dtype)
    theta[:, 0, 0] = theta[:, 1, 1] = 1
    theta[:, 0, 2] = -2 * dx / max(width - 1, 1)
    theta[:, 1, 2] = -2 * dy / max(height - 1, 1)
    return F.grid_sample(value, F.affine_grid(theta, value.shape, align_corners=True), mode="bilinear", padding_mode="reflection", align_corners=True)


def paired_loss(details, batch: dict, scenes: int, weights: dict) -> tuple[torch.Tensor, dict]:
    a, b = slice(0, scenes * 3, 3), slice(1, scenes * 3, 3)
    dx, dy = batch["pair_shift_px"][:, 0].float(), batch["pair_shift_px"][:, 1].float()
    margin = 20
    crop = lambda value: value[..., margin:-margin, margin:-margin]
    output = F.smooth_l1_loss(crop(details.output[b].float()), crop(warp_translation(details.output[a].float(), dx, dy)), beta=0.25 / 255.0)
    sdf = F.smooth_l1_loss(crop(details.predicted_sdf_px[b].float()), crop(warp_translation(details.predicted_sdf_px[a].float(), dx, dy)), beta=0.05)
    width = F.smooth_l1_loss(crop(details.width_gain[b].float()), crop(warp_translation(details.width_gain[a].float(), dx, dy)), beta=0.01)
    shift = F.smooth_l1_loss(crop(details.normal_shift[b].float()), crop(warp_translation(details.normal_shift[a].float(), dx, dy)), beta=0.01)
    coordinate_a = edge_center_coordinate(details.output[a], batch["sdf"][a])
    coordinate_b = edge_center_coordinate(details.output[b], batch["sdf"][b])
    target_a = edge_center_coordinate(batch["target"][a], batch["sdf"][a])
    target_b = edge_center_coordinate(batch["target"][b], batch["sdf"][b])
    center = torch.abs((coordinate_b - target_b) - (coordinate_a - target_a)).mean()
    total = weights["pair_output"] * output + weights["pair_sdf"] * sdf + weights["pair_width"] * width + weights["pair_shift"] * shift + weights["pair_center"] * center
    return total, {"pair_output": output, "pair_sdf": sdf, "pair_width": width, "pair_shift": shift, "pair_center": center}
