"""Differentiable R102 objectives, separated by physical responsibility."""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


def gaussian_blur(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    if size == 3:
        row = torch.tensor([1, 2, 1], device=x.device, dtype=x.dtype)
    elif size == 5:
        row = torch.tensor([1, 4, 6, 4, 1], device=x.device, dtype=x.dtype)
    elif size == 9:
        row = torch.tensor([1, 8, 28, 56, 70, 56, 28, 8, 1], device=x.device, dtype=x.dtype)
    else:
        raise ValueError("size must be 3, 5, or 9")
    kernel = torch.outer(row, row)
    kernel = kernel / kernel.sum()
    kernel = kernel.view(1, 1, size, size).repeat(x.shape[1], 1, 1, 1)
    return F.conv2d(safe_pad(x, size // 2), kernel, groups=x.shape[1])


def highpass(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    return x - gaussian_blur(x, size)


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = x[..., :, 1:] - x[..., :, :-1]
    gy = x[..., 1:, :] - x[..., :-1, :]
    return gx, gy


def gradient_magnitude(x: torch.Tensor) -> torch.Tensor:
    gx = F.pad(x[..., :, 1:] - x[..., :, :-1], (0, 1, 0, 0))
    gy = F.pad(x[..., 1:, :] - x[..., :-1, :], (0, 0, 0, 1))
    return torch.sqrt(gx.square() + gy.square() + 1e-8)


def charbonnier(x: torch.Tensor, epsilon: float = 1e-3) -> torch.Tensor:
    return torch.sqrt(x.square() + epsilon * epsilon).mean()


def correlation_loss(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    a = a.flatten(1)
    b = b.flatten(1)
    a = a - a.mean(dim=1, keepdim=True)
    b = b - b.mean(dim=1, keepdim=True)
    numerator = (a * b).sum(dim=1)
    denominator = torch.sqrt(a.square().sum(dim=1) * b.square().sum(dim=1) + 1e-8)
    return (1.0 - numerator / denominator.clamp_min(1e-8)).mean()


def soft_contour_loss(
    prediction: torch.Tensor,
    mask: torch.Tensor,
    midpoint: torch.Tensor,
    polarity: torch.Tensor,
) -> torch.Tensor:
    midpoint = midpoint.view(-1, 1, 1, 1)
    polarity = polarity.view(-1, 1, 1, 1)
    logits = polarity * (prediction - midpoint) / 0.035
    probability = torch.sigmoid(logits)
    target = mask.clamp(0.0, 1.0)
    bce = F.binary_cross_entropy_with_logits(logits, target)
    intersection = (probability * target).sum(dim=(-2, -1))
    union = probability.sum(dim=(-2, -1)) + target.sum(dim=(-2, -1))
    dice = 1.0 - ((2.0 * intersection + 1.0) / (union + 1.0)).mean()
    pred_boundary = gradient_magnitude(probability)
    target_boundary = gradient_magnitude(target)
    boundary = F.l1_loss(pred_boundary, target_boundary)
    return 0.40 * bce + 0.35 * dice + 0.25 * boundary


def boundary_support(mask: torch.Tensor) -> torch.Tensor:
    edge = gradient_magnitude(mask)
    edge = F.max_pool2d(edge, kernel_size=9, stride=1, padding=4)
    scale = edge.amax(dim=(-2, -1), keepdim=True).clamp_min(1e-5)
    return (edge / scale).clamp(0.0, 1.0)


def warp_tensor(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    """Translate like cv2.warpAffine using reflective sampling."""
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
    top = (h - core_size) // 2
    left = (w - core_size) // 2
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
    batch_views = prediction.shape[0]

    reconstruction = charbonnier(prediction - target)
    low_prediction = (source + low_delta).clamp(0.0, 1.0)
    contour_prediction = (source + low_delta.detach() + contour_delta + texture_delta.detach()).clamp(0.0, 1.0)
    texture_prediction = (source + low_delta.detach() + contour_delta.detach() + texture_delta).clamp(0.0, 1.0)
    low_frequency = F.l1_loss(gaussian_blur(low_prediction, 9), gaussian_blur(target, 9))
    pgx, pgy = gradients(contour_prediction)
    tgx, tgy = gradients(target)
    texture_gx, texture_gy = gradients(texture_prediction)
    gradient = 0.35 * (charbonnier(pgx - tgx) + charbonnier(pgy - tgy))
    gradient = gradient + 0.15 * (charbonnier(texture_gx - tgx) + charbonnier(texture_gy - tgy))
    pred_hf3, target_hf3 = highpass(texture_prediction, 3), highpass(target, 3)
    pred_hf5, target_hf5 = highpass(texture_prediction, 5), highpass(target, 5)
    high_frequency = 0.55 * F.l1_loss(pred_hf3, target_hf3) + 0.45 * F.l1_loss(pred_hf5, target_hf5)
    high_frequency_correlation = 0.5 * correlation_loss(pred_hf3, target_hf3) + 0.5 * correlation_loss(pred_hf5, target_hf5)
    contour = soft_contour_loss(contour_prediction, mask, midpoint, polarity)

    residual_target = target - source
    low_target = gaussian_blur(residual_target, 9)
    support = boundary_support(mask)
    high_target = highpass(target, 5) - highpass(source, 5)
    contour_target = support * high_target
    innovation_rows = (mode == 1).float().view(batch_views, 1, 1, 1)
    texture_weight = (1.0 - 0.75 * support) * (1.0 - innovation_rows) + innovation_rows
    texture_target = texture_weight * high_target
    branch_targets = (
        0.75 * F.l1_loss(low_delta, low_target)
        + 1.15 * F.l1_loss(contour_delta, contour_target)
        + 1.25 * F.l1_loss(texture_delta, texture_target)
        + 0.30 * highpass(low_delta, 5).abs().mean()
        + 0.20 * gaussian_blur(texture_delta, 9).abs().mean()
    )

    identity_rows = identity | (mode == 2)
    if bool(identity_rows.any()):
        identity_prediction = prediction[identity_rows]
        identity_source = source[identity_rows]
        identity_loss = F.l1_loss(identity_prediction, identity_source)
        identity_loss = identity_loss + 0.75 * F.l1_loss(highpass(identity_prediction, 3), highpass(identity_source, 3))
    else:
        identity_loss = prediction.new_zeros(())

    flat_rows = mode == 3
    if bool(flat_rows.any()):
        flat_prediction = prediction[flat_rows]
        flat_source = source[flat_rows]
        flat_negative = F.l1_loss(flat_prediction, target[flat_rows])
        flat_negative = flat_negative + 1.25 * highpass(flat_prediction, 3).abs().mean()
        flat_negative = flat_negative + 0.50 * (flat_prediction - flat_source).abs().mean()
    else:
        flat_negative = prediction.new_zeros(())

    # The flattened layout is [scene0_view0, scene0_view1, ...].
    if batch_views >= 2 and batch_views % 2 == 0:
        first = prediction[0::2]
        second = prediction[1::2]
        motion_first = motion[0::2]
        motion_second = motion[1::2]
        dx = motion_second[:, 0] - motion_first[:, 0]
        dy = motion_second[:, 1] - motion_first[:, 1]
        aligned_first = warp_tensor(first, dx, dy)
        margin = min(12, max(0, core_size // 8))
        if margin:
            aligned_first = aligned_first[..., margin:-margin, margin:-margin]
            second = second[..., margin:-margin, margin:-margin]
        paired = F.l1_loss(aligned_first, second)
    else:
        paired = prediction.new_zeros(())

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
