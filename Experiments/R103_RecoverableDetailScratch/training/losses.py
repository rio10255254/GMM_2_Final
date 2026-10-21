"""R103 losses with recoverable supervision and non-overlapping branches."""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


def gaussian_blur(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    rows = {
        3: [1, 2, 1],
        5: [1, 4, 6, 4, 1],
        9: [1, 8, 28, 56, 70, 56, 28, 8, 1],
    }
    if size not in rows:
        raise ValueError("size must be 3, 5, or 9")
    row = torch.tensor(rows[size], device=x.device, dtype=x.dtype)
    kernel = torch.outer(row, row)
    kernel = (kernel / kernel.sum()).view(1, 1, size, size).repeat(x.shape[1], 1, 1, 1)
    return F.conv2d(safe_pad(x, size // 2), kernel, groups=x.shape[1])


def highpass(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    return x - gaussian_blur(x, size)


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    return x[..., :, 1:] - x[..., :, :-1], x[..., 1:, :] - x[..., :-1, :]


def gradient_magnitude(x: torch.Tensor) -> torch.Tensor:
    gx = F.pad(x[..., :, 1:] - x[..., :, :-1], (0, 1, 0, 0))
    gy = F.pad(x[..., 1:, :] - x[..., :-1, :], (0, 0, 0, 1))
    return torch.sqrt(gx.square() + gy.square() + 1e-8)


def correlation_loss(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    a, b = a.flatten(1), b.flatten(1)
    a, b = a - a.mean(1, keepdim=True), b - b.mean(1, keepdim=True)
    numerator = (a * b).sum(1)
    denominator = torch.sqrt(a.square().sum(1) * b.square().sum(1) + 1e-8)
    return (1.0 - numerator / denominator.clamp_min(1e-8)).mean()


def smooth_zero(x: torch.Tensor, epsilon: float) -> torch.Tensor:
    return (torch.sqrt(x.square() + epsilon * epsilon) - epsilon).mean()


def soft_contour_loss(prediction: torch.Tensor, mask: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    midpoint = midpoint.view(-1, 1, 1, 1)
    polarity = polarity.view(-1, 1, 1, 1)
    logits = polarity * (prediction - midpoint) / 0.035
    probability = torch.sigmoid(logits)
    target = mask.clamp(0.0, 1.0)
    bce = F.binary_cross_entropy_with_logits(logits, target)
    intersection = (probability * target).sum(dim=(-2, -1))
    union = probability.sum(dim=(-2, -1)) + target.sum(dim=(-2, -1))
    dice = 1.0 - ((2.0 * intersection + 1.0) / (union + 1.0)).mean()
    boundary = F.l1_loss(gradient_magnitude(probability), gradient_magnitude(target))
    return 0.40 * bce + 0.35 * dice + 0.25 * boundary


def boundary_support(mask: torch.Tensor) -> torch.Tensor:
    edge = F.max_pool2d(gradient_magnitude(mask), kernel_size=9, stride=1, padding=4)
    scale = edge.amax(dim=(-2, -1), keepdim=True).clamp_min(1e-5)
    return (edge / scale).clamp(0.0, 1.0)


def warp_tensor(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    n, _c, h, w = x.shape
    theta = torch.zeros((n, 2, 3), device=x.device, dtype=x.dtype)
    theta[:, 0, 0] = 1.0
    theta[:, 1, 1] = 1.0
    theta[:, 0, 2] = -2.0 * dx.to(dtype=x.dtype) / max(w - 1, 1)
    theta[:, 1, 2] = -2.0 * dy.to(dtype=x.dtype) / max(h - 1, 1)
    grid = F.affine_grid(theta, x.shape, align_corners=True)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def central_crop(x: torch.Tensor, core_size: int) -> torch.Tensor:
    h, w = x.shape[-2:]
    if core_size > h or core_size > w:
        raise ValueError("core exceeds input")
    top, left = (h - core_size) // 2, (w - core_size) // 2
    return x[..., top:top + core_size, left:left + core_size]


def loss_components(
    details: Any,
    source: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    midpoint: torch.Tensor,
    polarity: torch.Tensor,
    mode: torch.Tensor,
    identity: torch.Tensor,
    motion: torch.Tensor,
    core_size: int,
) -> dict[str, torch.Tensor]:
    prediction = central_crop(details.output.float(), core_size)
    source = central_crop(source.float(), core_size)
    target = central_crop(target.float(), core_size)
    mask = central_crop(mask.float(), core_size)
    low_delta = central_crop(details.low_delta.float(), core_size)
    contour_delta = central_crop(details.contour_delta.float(), core_size)
    texture_delta = central_crop(details.texture_delta.float(), core_size)
    zero = prediction.new_zeros(())
    supervised = ~identity

    if bool(supervised.any()):
        pred, truth = prediction[supervised], target[supervised]
        reconstruction = F.smooth_l1_loss(pred, truth, beta=2.0 / 255.0)
        low_frequency = F.smooth_l1_loss(gaussian_blur(pred, 9), gaussian_blur(truth, 9), beta=2.0 / 255.0)
        pgx, pgy = gradients(pred)
        tgx, tgy = gradients(truth)
        gradient = F.smooth_l1_loss(pgx, tgx, beta=1.0 / 255.0)
        gradient = gradient + F.smooth_l1_loss(pgy, tgy, beta=1.0 / 255.0)
        pred_hf3, truth_hf3 = highpass(pred, 3), highpass(truth, 3)
        pred_hf5, truth_hf5 = highpass(pred, 5), highpass(truth, 5)
        high_frequency = F.smooth_l1_loss(pred_hf3, truth_hf3, beta=0.5 / 255.0)
        high_frequency = high_frequency + 0.65 * F.smooth_l1_loss(pred_hf5, truth_hf5, beta=0.75 / 255.0)
        high_frequency_correlation = 0.5 * correlation_loss(pred_hf3, truth_hf3)
        high_frequency_correlation = high_frequency_correlation + 0.5 * correlation_loss(pred_hf5, truth_hf5)

        residual = target - source
        low_target = gaussian_blur(residual, 9)
        detail_target = residual - low_target
        support = boundary_support(mask)
        contour_target = support * detail_target
        texture_target = detail_target - contour_target
        branch_targets = F.smooth_l1_loss(low_delta[supervised], low_target[supervised], beta=1.0 / 255.0)
        branch_targets = branch_targets + 1.5 * F.smooth_l1_loss(
            contour_delta[supervised], contour_target[supervised], beta=0.5 / 255.0
        )
        branch_targets = branch_targets + 1.5 * F.smooth_l1_loss(
            texture_delta[supervised], texture_target[supervised], beta=0.5 / 255.0
        )
    else:
        reconstruction = low_frequency = gradient = high_frequency = high_frequency_correlation = branch_targets = zero

    contour_rows = supervised & (mode != 3)
    contour = soft_contour_loss(
        prediction[contour_rows], mask[contour_rows], midpoint[contour_rows], polarity[contour_rows]
    ) if bool(contour_rows.any()) else zero

    identity_loss = smooth_zero(prediction[identity] - source[identity], 1.5 / 255.0) if bool(identity.any()) else zero

    flat_rows = supervised & (mode == 3)
    if bool(flat_rows.any()):
        flat_negative = F.smooth_l1_loss(prediction[flat_rows], target[flat_rows], beta=1.0 / 255.0)
        flat_negative = flat_negative + F.smooth_l1_loss(
            highpass(prediction[flat_rows], 3), highpass(target[flat_rows], 3), beta=0.5 / 255.0
        )
    else:
        flat_negative = zero

    # Layout is [degraded, same-content-clear] for every scene.
    if prediction.shape[0] >= 2 and prediction.shape[0] % 2 == 0:
        degraded, clear = prediction[0::2], prediction[1::2]
        m0, m1 = motion[0::2], motion[1::2]
        aligned = warp_tensor(degraded, m1[:, 0] - m0[:, 0], m1[:, 1] - m0[:, 1])
        margin = min(12, max(0, core_size // 8))
        if margin:
            aligned = aligned[..., margin:-margin, margin:-margin]
            clear = clear[..., margin:-margin, margin:-margin]
        paired = F.smooth_l1_loss(aligned, clear, beta=1.0 / 255.0)
    else:
        paired = zero

    return {
        "reconstruction": reconstruction,
        "low_frequency": low_frequency,
        "gradient": gradient,
        "high_frequency": high_frequency,
        "high_frequency_correlation": high_frequency_correlation,
        "contour": contour,
        "branch_targets": branch_targets,
        "paired_observation": paired,
        "identity": identity_loss,
        "flat_negative": flat_negative,
    }
