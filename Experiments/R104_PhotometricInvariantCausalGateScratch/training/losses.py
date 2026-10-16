"""R104 losses: explicit shape, proposal, gate, illumination, motion, and tile roles."""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


def gaussian_blur(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    rows = {
        3: [1, 2, 1], 5: [1, 4, 6, 4, 1],
        9: [1, 8, 28, 56, 70, 56, 28, 8, 1],
    }
    row = torch.tensor(rows[size], device=x.device, dtype=x.dtype)
    kernel = torch.outer(row, row)
    kernel = (kernel / kernel.sum()).view(1, 1, size, size).repeat(x.shape[1], 1, 1, 1)
    return F.conv2d(safe_pad(x, size // 2), kernel, groups=x.shape[1])


def highpass(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    return x - gaussian_blur(x, size)


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(x[..., :, 1:] - x[..., :, :-1], (0, 1, 0, 0))
    gy = F.pad(x[..., 1:, :] - x[..., :-1, :], (0, 0, 0, 1))
    return gx, gy


def central_crop(x: torch.Tensor, core_size: int) -> torch.Tensor:
    height, width = x.shape[-2:]
    top, left = (height - core_size) // 2, (width - core_size) // 2
    return x[..., top:top + core_size, left:left + core_size]


def warp_tensor(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    n, _c, h, w = x.shape
    theta = torch.zeros((n, 2, 3), device=x.device, dtype=x.dtype)
    theta[:, 0, 0] = theta[:, 1, 1] = 1.0
    theta[:, 0, 2] = -2.0 * dx.to(x.dtype) / max(w - 1, 1)
    theta[:, 1, 2] = -2.0 * dy.to(x.dtype) / max(h - 1, 1)
    grid = F.affine_grid(theta, x.shape, align_corners=True)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def smooth_zero(x: torch.Tensor, epsilon: float) -> torch.Tensor:
    return (torch.sqrt(x.square() + epsilon * epsilon) - epsilon).clamp_min(0.0).mean()


def correlation_loss(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    a, b = a.flatten(1), b.flatten(1)
    a, b = a - a.mean(1, keepdim=True), b - b.mean(1, keepdim=True)
    numerator = (a * b).sum(1)
    denominator = torch.sqrt(a.square().sum(1) * b.square().sum(1) + 1e-8)
    return (1.0 - numerator / denominator.clamp_min(1e-8)).mean()


def weighted_smooth_l1(a: torch.Tensor, b: torch.Tensor, weight: torch.Tensor, beta: float) -> torch.Tensor:
    value = F.smooth_l1_loss(a, b, beta=beta, reduction="none")
    return (value * weight).sum() / weight.sum().clamp_min(1.0)


def local_coherence(a: torch.Tensor, b: torch.Tensor, size: int = 9) -> torch.Tensor:
    """Continuous phase/evidence score used only to supervise restoration need."""
    cross = gaussian_blur(a * b, size)
    power = torch.sqrt(gaussian_blur(a.square(), size) * gaussian_blur(b.square(), size) + 1e-8)
    return (cross / power.clamp_min(1e-6)).clamp(0.0, 1.0)


def balanced_soft_bce(
    probability: torch.Tensor, target: torch.Tensor, positive_fraction: float = 0.62,
) -> torch.Tensor:
    """Balance continuous positive and negative mass without a hard threshold."""
    probability = probability.clamp(1e-5, 1.0 - 1e-5)
    positive_mass = target.sum()
    negative = 1.0 - target
    negative_mass = negative.sum()
    positive_loss = (
        -(target * probability.log()).sum() / positive_mass.clamp_min(1.0)
        if bool(positive_mass > 0) else probability.new_zeros(())
    )
    negative_loss = -(
        negative * torch.log1p(-probability)
    ).sum() / negative_mass.clamp_min(1.0)
    return positive_fraction * positive_loss + (1.0 - positive_fraction) * negative_loss


def loss_components(
    details: Any,
    source: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    sdf: torch.Tensor,
    illumination_target: torch.Tensor,
    identity: torch.Tensor,
    mode: torch.Tensor,
    pair_type: torch.Tensor,
    motion: torch.Tensor,
    core_size: int,
) -> dict[str, torch.Tensor]:
    prediction = central_crop(details.output.float(), core_size)
    source = central_crop(source.float(), core_size)
    target = central_crop(target.float(), core_size)
    mask = central_crop(mask.float(), core_size)
    sdf = central_crop(sdf.float(), core_size).clamp(-24.0, 24.0)
    illumination_target = central_crop(illumination_target.float(), core_size)
    predicted_sdf = central_crop(details.signed_distance.float(), core_size)
    low_proposal = central_crop(details.low_proposal.float(), core_size)
    low_gate = central_crop(details.low_gate.float(), core_size)
    low_delta = central_crop(details.low_delta.float(), core_size)
    illumination_proposal = central_crop(details.illumination_proposal.float(), core_size)
    illumination_gate = central_crop(details.illumination_gate.float(), core_size)
    illumination_delta = central_crop(details.illumination_delta.float(), core_size)
    contour_proposal = central_crop(details.contour_proposal.float(), core_size)
    texture_proposal = central_crop(details.texture_proposal.float(), core_size)
    contour_gate = central_crop(details.contour_gate.float(), core_size)
    texture_gate = central_crop(details.texture_gate.float(), core_size)
    zero = prediction.new_zeros(())

    reconstruction = F.smooth_l1_loss(prediction, target, beta=2.0 / 255.0)
    low_frequency = F.smooth_l1_loss(
        gaussian_blur(prediction, 9), gaussian_blur(target, 9), beta=2.0 / 255.0
    )
    pgx, pgy = gradients(prediction)
    tgx, tgy = gradients(target)
    gradient = F.smooth_l1_loss(pgx, tgx, beta=1.0 / 255.0)
    gradient += F.smooth_l1_loss(pgy, tgy, beta=1.0 / 255.0)
    pred_h3, target_h3 = highpass(prediction, 3), highpass(target, 3)
    pred_h5, target_h5 = highpass(prediction, 5), highpass(target, 5)
    high_frequency = F.smooth_l1_loss(pred_h3, target_h3, beta=0.5 / 255.0)
    high_frequency += 0.65 * F.smooth_l1_loss(pred_h5, target_h5, beta=0.75 / 255.0)
    high_frequency += 0.08 * (correlation_loss(pred_h3, target_h3) + correlation_loss(pred_h5, target_h5))

    boundary_weight = torch.exp(-sdf.abs() / 5.0)
    boundary_band_reconstruction = weighted_smooth_l1(
        prediction, target, 0.15 + 0.85 * boundary_weight, beta=0.75 / 255.0
    )
    sdf_weight = 0.20 + 0.80 * torch.exp(-sdf.abs() / 10.0)
    # Compare a dimensionless signed-distance field so this auxiliary shape task
    # cannot dominate restoration merely because its unit is pixels.  Keep the
    # public prediction in pixels for boundary bands and later diagnostics.
    signed_distance_shape = weighted_smooth_l1(
        predicted_sdf / 24.0, sdf / 24.0, sdf_weight, beta=0.75 / 24.0
    )
    probability = torch.sigmoid(predicted_sdf / 1.5)
    intersection = (probability * mask).sum(dim=(-2, -1))
    union = probability.sum(dim=(-2, -1)) + mask.sum(dim=(-2, -1))
    signed_distance_shape += 0.25 * (1.0 - ((2.0 * intersection + 1.0) / (union + 1.0)).mean())

    psx, psy = gradients(predicted_sdf)
    tsx, tsy = gradients(sdf)
    pnorm = torch.sqrt(psx.square() + psy.square() + 1e-6)
    tnorm = torch.sqrt(tsx.square() + tsy.square() + 1e-6)
    normal_difference = 1.0 - (psx * tsx + psy * tsy) / (pnorm * tnorm).clamp_min(1e-6)
    shape_normal = (normal_difference * boundary_weight).sum() / boundary_weight.sum().clamp_min(1.0)

    residual = target - source
    remaining = residual - illumination_target
    low_target = gaussian_blur(remaining, 9)
    detail_target = remaining - low_target
    contour_support = torch.exp(-sdf.abs() / 4.0)
    contour_target = contour_support * detail_target
    texture_target = detail_target - contour_target
    proposal_supervision = F.smooth_l1_loss(low_proposal, low_target, beta=1.0 / 255.0)
    proposal_supervision += F.smooth_l1_loss(
        illumination_proposal, illumination_target, beta=1.0 / 255.0
    )
    proposal_supervision += 1.35 * F.smooth_l1_loss(contour_proposal, contour_target, beta=0.5 / 255.0)
    proposal_supervision += 1.20 * F.smooth_l1_loss(texture_proposal, texture_target, beta=0.5 / 255.0)

    source_h3, target_h3 = highpass(source, 3), highpass(target, 3)
    texture_recoverability = local_coherence(source_h3, target_h3, 9)
    sgx, sgy = gradients(source)
    contour_cross = gaussian_blur(sgx * tgx + sgy * tgy, 9)
    contour_power = torch.sqrt(
        gaussian_blur(sgx.square() + sgy.square(), 9)
        * gaussian_blur(tgx.square() + tgy.square(), 9) + 1e-8
    )
    contour_recoverability = (contour_cross / contour_power.clamp_min(1e-6)).clamp(0.0, 1.0)
    low_need = 1.0 - torch.exp(-low_target.abs() / (2.0 / 255.0))
    illumination_need = 1.0 - torch.exp(-illumination_target.abs() / (2.0 / 255.0))
    contour_need = (1.0 - torch.exp(-contour_target.abs() / (1.5 / 255.0)))
    texture_need = (1.0 - torch.exp(-texture_target.abs() / (1.5 / 255.0)))
    contour_need *= 0.10 + 0.90 * contour_recoverability
    texture_need *= 0.08 + 0.92 * texture_recoverability
    low_need = gaussian_blur(low_need, 9).clamp(0.0, 1.0)
    illumination_need = gaussian_blur(illumination_need, 9).clamp(0.0, 1.0)
    contour_need = gaussian_blur(contour_need, 3).clamp(0.0, 1.0)
    texture_need = gaussian_blur(texture_need, 3).clamp(0.0, 1.0)
    low_probability = (low_gate / 1.15).clamp(1e-5, 1.0 - 1e-5)
    illumination_probability = (illumination_gate / 1.15).clamp(1e-5, 1.0 - 1e-5)
    contour_probability = (contour_gate / 1.15).clamp(1e-5, 1.0 - 1e-5)
    texture_probability = (texture_gate / 1.15).clamp(1e-5, 1.0 - 1e-5)
    gate_supervision = 0.25 * (
        balanced_soft_bce(low_probability, low_need)
        + balanced_soft_bce(illumination_probability, illumination_need)
        + balanced_soft_bce(contour_probability, contour_need)
        + balanced_soft_bce(texture_probability, texture_need)
    )
    spatial_illumination = F.smooth_l1_loss(
        illumination_delta, illumination_target, beta=1.0 / 255.0
    )

    identity_output = smooth_zero(prediction[identity] - source[identity], 1.0 / 255.0) if bool(identity.any()) else zero
    identity_gate = (
        0.25 * (
            low_probability[identity].square().mean()
            + illumination_probability[identity].square().mean()
            + contour_probability[identity].square().mean()
            + texture_probability[identity].square().mean()
        )
    ) if bool(identity.any()) else zero
    flat = mode == 5
    flat_negative = (
        F.smooth_l1_loss(prediction[flat], target[flat], beta=1.0 / 255.0)
        + F.smooth_l1_loss(highpass(prediction[flat], 3), highpass(target[flat], 3), beta=0.5 / 255.0)
    ) if bool(flat.any()) else zero

    first, second = prediction[0::2], prediction[1::2]
    sdf_first, sdf_second = predicted_sdf[0::2], predicted_sdf[1::2]
    cg_first, cg_second = contour_probability[0::2], contour_probability[1::2]
    tg_first, tg_second = texture_probability[0::2], texture_probability[1::2]
    lg_first, lg_second = low_probability[0::2], low_probability[1::2]
    ig_first, ig_second = illumination_probability[0::2], illumination_probability[1::2]
    m0, m1 = motion[0::2], motion[1::2]
    dx, dy = m1[:, 0] - m0[:, 0], m1[:, 1] - m0[:, 1]
    aligned_first = warp_tensor(first, dx, dy)
    aligned_sdf = warp_tensor(sdf_first, dx, dy)
    aligned_cg = warp_tensor(cg_first, dx, dy)
    aligned_tg = warp_tensor(tg_first, dx, dy)
    margin = min(16, max(0, core_size // 8))
    if margin:
        aligned_first, second = aligned_first[..., margin:-margin, margin:-margin], second[..., margin:-margin, margin:-margin]
        aligned_sdf, sdf_second = aligned_sdf[..., margin:-margin, margin:-margin], sdf_second[..., margin:-margin, margin:-margin]
        aligned_cg, cg_second = aligned_cg[..., margin:-margin, margin:-margin], cg_second[..., margin:-margin, margin:-margin]
        aligned_tg, tg_second = aligned_tg[..., margin:-margin, margin:-margin], tg_second[..., margin:-margin, margin:-margin]
        lg_first, lg_second = lg_first[..., margin:-margin, margin:-margin], lg_second[..., margin:-margin, margin:-margin]
        ig_first, ig_second = ig_first[..., margin:-margin, margin:-margin], ig_second[..., margin:-margin, margin:-margin]
    scene_pair = pair_type[0::2]
    photometric_pair = scene_pair == 1
    clear_counterfactual_pair = scene_pair == 0
    motion_pair = scene_pair == 2
    tile_pair = scene_pair == 3
    paired_observation = F.smooth_l1_loss(
        aligned_first[clear_counterfactual_pair], second[clear_counterfactual_pair], beta=1.0 / 255.0
    ) if bool(clear_counterfactual_pair.any()) else zero
    translation = F.smooth_l1_loss(
        aligned_first[motion_pair], second[motion_pair], beta=1.0 / 255.0
    ) if bool(motion_pair.any()) else zero
    tile = F.smooth_l1_loss(
        aligned_first[tile_pair], second[tile_pair], beta=1.0 / 255.0
    ) if bool(tile_pair.any()) else zero
    exposure_shape_consistency = F.smooth_l1_loss(
        aligned_sdf[photometric_pair], sdf_second[photometric_pair], beta=0.75
    ) if bool(photometric_pair.any()) else zero
    if bool(photometric_pair.any()):
        def centered(value: torch.Tensor) -> torch.Tensor:
            return value - value.mean(dim=(-2, -1), keepdim=True)
        exposure_gate_consistency = 0.25 * (
            F.smooth_l1_loss(centered(lg_first[photometric_pair]), centered(lg_second[photometric_pair]), beta=0.02)
            + F.smooth_l1_loss(centered(ig_first[photometric_pair]), centered(ig_second[photometric_pair]), beta=0.02)
            + F.smooth_l1_loss(centered(aligned_cg[photometric_pair]), centered(cg_second[photometric_pair]), beta=0.02)
            + F.smooth_l1_loss(centered(aligned_tg[photometric_pair]), centered(tg_second[photometric_pair]), beta=0.02)
        )
    else:
        exposure_gate_consistency = zero

    return {
        "reconstruction": reconstruction,
        "low_frequency": low_frequency,
        "gradient": gradient,
        "high_frequency": high_frequency,
        "signed_distance_shape": signed_distance_shape,
        "shape_normal": shape_normal,
        "boundary_band_reconstruction": boundary_band_reconstruction,
        "proposal_supervision": proposal_supervision,
        "gate_supervision": gate_supervision,
        "spatial_illumination": spatial_illumination,
        "exposure_shape_consistency": exposure_shape_consistency,
        "exposure_gate_consistency": exposure_gate_consistency,
        "identity_output": identity_output,
        "identity_gate": identity_gate,
        "flat_negative": flat_negative,
        "paired_observation": paired_observation,
        "translation": translation,
        "tile": tile,
    }
