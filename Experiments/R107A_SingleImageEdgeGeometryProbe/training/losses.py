"""R107 losses keep center, width, reliability and texture explicit."""
from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def safe_pad(x: torch.Tensor, amount: int) -> torch.Tensor:
    mode = "reflect" if x.shape[-2] > amount and x.shape[-1] > amount else "replicate"
    return F.pad(x, (amount, amount, amount, amount), mode=mode)


def gaussian_blur(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    rows = {3: [1, 2, 1], 5: [1, 4, 6, 4, 1], 9: [1, 8, 28, 56, 70, 56, 28, 8, 1]}
    row = torch.tensor(rows[size], device=x.device, dtype=x.dtype); kernel = torch.outer(row, row); kernel = (kernel / kernel.sum()).view(1, 1, size, size).repeat(x.shape[1], 1, 1, 1)
    return F.conv2d(safe_pad(x, size // 2), kernel, groups=x.shape[1])


def highpass(x: torch.Tensor, size: int = 5) -> torch.Tensor:
    return x - gaussian_blur(x, size)


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    gx = F.pad(x[..., :, 1:] - x[..., :, :-1], (0, 1, 0, 0)); gy = F.pad(x[..., 1:, :] - x[..., :-1, :], (0, 0, 0, 1)); return gx, gy


def gradient_magnitude(x: torch.Tensor) -> torch.Tensor:
    gx, gy = gradients(x); return torch.sqrt(gx.square() + gy.square() + 1e-8)


def soft_logits(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    midpoint = midpoint.view(-1, 1, 1, 1); polarity = polarity.view(-1, 1, 1, 1)
    return polarity * (image - midpoint) / 0.035


def soft_probability(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(soft_logits(image, midpoint, polarity))


def soft_centroid(probability: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    h, w = probability.shape[-2:]; yy, xx = torch.meshgrid(torch.arange(h, device=probability.device, dtype=probability.dtype), torch.arange(w, device=probability.device, dtype=probability.dtype), indexing="ij")
    total = probability.sum(dim=(-2, -1)).clamp_min(1e-6); cx = (probability * xx).sum(dim=(-2, -1)) / total; cy = (probability * yy).sum(dim=(-2, -1)) / total; return cx, cy


def smooth_zero(x: torch.Tensor, epsilon: float = 1.0 / 255.0) -> torch.Tensor:
    return (torch.sqrt(x.square() + epsilon * epsilon) - epsilon).mean()


def loss_components(
    details: Any,
    source: torch.Tensor,
    target: torch.Tensor,
    mask: torch.Tensor,
    sdf: torch.Tensor,
    edge_target: torch.Tensor,
    reliability_target: torch.Tensor,
    width_scale_target: torch.Tensor,
    identity: torch.Tensor,
    midpoint: torch.Tensor,
    polarity: torch.Tensor,
) -> dict[str, torch.Tensor]:
    prediction = details.output.float(); source = source.float(); target = target.float(); edge_target = edge_target.float(); zero = prediction.new_zeros(())
    supervised = ~identity
    if bool(supervised.any()):
        pred, truth = prediction[supervised], target[supervised]
        reconstruction = F.smooth_l1_loss(pred, truth, beta=2.0 / 255.0)
        pgx, pgy = gradients(pred); tgx, tgy = gradients(truth)
        gradient = F.smooth_l1_loss(pgx, tgx, beta=1.0 / 255.0) + F.smooth_l1_loss(pgy, tgy, beta=1.0 / 255.0)
        high_frequency = F.smooth_l1_loss(highpass(pred, 3), highpass(truth, 3), beta=0.5 / 255.0)
        high_frequency += 0.65 * F.smooth_l1_loss(highpass(pred, 5), highpass(truth, 5), beta=0.75 / 255.0)
    else:
        reconstruction = gradient = high_frequency = zero

    contour_rows = supervised & (edge_target.amax(dim=(-3, -2, -1)) > 0.02)
    if bool(contour_rows.any()):
        pred_logits = soft_logits(prediction[contour_rows], midpoint[contour_rows], polarity[contour_rows])
        pred_prob = torch.sigmoid(pred_logits)
        target_prob = mask[contour_rows].clamp(0.0, 1.0)
        intersection = (pred_prob * target_prob).sum(dim=(-2, -1)); union = pred_prob.sum(dim=(-2, -1)) + target_prob.sum(dim=(-2, -1))
        dice = 1.0 - ((2.0 * intersection + 1.0) / (union + 1.0)).mean()
        contour = 0.50 * F.binary_cross_entropy_with_logits(pred_logits, target_prob) + 0.30 * dice + 0.20 * F.l1_loss(gradient_magnitude(pred_prob), gradient_magnitude(target_prob))
        pcx, pcy = soft_centroid(pred_prob); tcx, tcy = soft_centroid(target_prob)
        normalizer = float(max(prediction.shape[-2], prediction.shape[-1], 1))
        center = ((pcx - tcx).abs().mean() + (pcy - tcy).abs().mean()) / normalizer
    else:
        contour = center = zero

    edge_weight = edge_target.clamp(0.0, 1.0)
    width_map_target = width_scale_target.view(-1, 1, 1, 1).expand_as(details.width_scale)
    width_parameter = ((details.width_scale - width_map_target).abs() * edge_weight).sum() / edge_weight.sum().clamp_min(1.0)
    reliability = ((details.reliability - reliability_target.float()).abs()).mean()

    lower = target.amin(dim=(-2, -1), keepdim=True) - 2.0 / 255.0; upper = target.amax(dim=(-2, -1), keepdim=True) + 2.0 / 255.0
    halo = (F.relu(lower - prediction) + F.relu(prediction - upper)).mean()
    texture_support = (1.0 - edge_target.clamp(0.0, 1.0)) * supervised.view(-1, 1, 1, 1)
    texture = (F.smooth_l1_loss(highpass(prediction, 3), highpass(target, 3), beta=0.5 / 255.0, reduction="none") * texture_support).sum() / texture_support.sum().clamp_min(1.0)
    identity_loss = smooth_zero(prediction[identity] - source[identity]) if bool(identity.any()) else zero
    return {
        "reconstruction": reconstruction,
        "gradient": gradient,
        "high_frequency": high_frequency,
        "contour": contour,
        "center": center,
        "width_parameter": width_parameter,
        "reliability": reliability,
        "halo": halo,
        "texture": texture,
        "identity": identity_loss,
    }


def combine(components: dict[str, torch.Tensor], weights: dict[str, float]) -> torch.Tensor:
    return sum(float(weights.get(name, 0.0)) * value for name, value in components.items())
