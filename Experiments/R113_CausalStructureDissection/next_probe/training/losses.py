"""Matched physical losses; the only arm-specific values come from detail itself."""
from __future__ import annotations

import torch
import torch.nn.functional as F


def gradients(value):
    return (F.pad(value[..., 1:] - value[..., :-1], (0, 1, 0, 0)),
            F.pad(value[..., 1:, :] - value[..., :-1, :], (0, 0, 0, 1)))


def weighted(value, weight):
    return (value * weight).sum() / weight.sum().clamp_min(1e-8)


def dice(prediction, target):
    numerator = 2 * (prediction * target).sum((1, 2, 3)) + 1e-6
    denominator = prediction.sum((1, 2, 3)) + target.sum((1, 2, 3)) + 1e-6
    return 1 - (numerator / denominator).mean()


def centroid(prediction, target):
    h, w = prediction.shape[-2:]
    yy, xx = torch.meshgrid(torch.linspace(-1, 1, h, device=prediction.device),
                            torch.linspace(-1, 1, w, device=prediction.device), indexing="ij")
    xx = xx.view(1, 1, h, w); yy = yy.view(1, 1, h, w)
    pm = prediction.sum((2, 3)).clamp_min(1e-6); tm = target.sum((2, 3)).clamp_min(1e-6)
    return (torch.abs((prediction * xx).sum((2, 3)) / pm - (target * xx).sum((2, 3)) / tm)
            + torch.abs((prediction * yy).sum((2, 3)) / pm - (target * yy).sum((2, 3)) / tm)).mean()


def detector_components(details, edge):
    boundary = F.max_pool2d(edge, 5, 1, 2).clamp(0, 1)
    positive = (1 - boundary.mean()).detach() / boundary.mean().clamp_min(1e-4).detach()
    return {
        "boundary_bce": F.binary_cross_entropy_with_logits(details.boundary_logits, boundary, pos_weight=positive),
        "boundary_dice": dice(details.boundary, boundary),
    }


def parameter_tv(value):
    return (torch.abs(value[..., 1:] - value[..., :-1]).mean()
            + torch.abs(value[..., 1:, :] - value[..., :-1, :]).mean())


def renderer_components(details, source, target, mask, edge, identity, midpoint, polarity, width_gain_target):
    boundary = F.max_pool2d(edge, 5, 1, 2).clamp(0, 1)
    soft = torch.sigmoid(42 * polarity[:, None, None, None] * (details.output - midpoint[:, None, None, None]))
    contour = dice(soft, mask)
    contour_bce = F.binary_cross_entropy(soft.clamp(1e-5, 1 - 1e-5), mask)
    area = torch.abs(soft.mean((1, 2, 3)) - mask.mean((1, 2, 3))).mean()
    center = centroid(soft, mask)
    band = .06 + .94 * boundary
    direct = weighted(F.smooth_l1_loss(details.delta, target - source, beta=1 / 255, reduction="none"), band)
    reconstruction = weighted(torch.abs(details.output - target), band)
    ogx, ogy = gradients(details.output); tgx, tgy = gradients(target)
    gradient = weighted(torch.abs(ogx - tgx) + torch.abs(ogy - tgy), band)
    identity_loss = details.delta[identity].abs().mean()
    smoothness = parameter_tv(details.width_gain) + parameter_tv(details.normal_shift)
    width_target = width_gain_target[:, None, None, None].expand_as(details.width_gain)
    width_loss = weighted(torch.abs(details.width_gain - width_target), boundary + .01)
    detail_low_frequency = F.avg_pool2d(details.detail, 9, 1, 4).abs().mean()
    detail_energy = details.detail.abs().mean()
    detail_identity = details.detail[identity].abs().mean()
    return {
        "contour": contour, "contour_bce": contour_bce, "area": area, "centroid": center,
        "direct": direct, "reconstruction": reconstruction, "gradient": gradient,
        "identity": identity_loss, "parameter_smoothness": smoothness, "width_target": width_loss,
        "detail_low_frequency": detail_low_frequency, "detail_energy": detail_energy,
        "detail_identity": detail_identity,
    }


def combine(components, weights):
    return sum(float(weights.get(name, 0)) * value for name, value in components.items())
