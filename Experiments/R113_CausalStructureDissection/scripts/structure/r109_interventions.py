"""Reusable, non-destructive R109 renderer interventions.

Variant names contain only letters and underscores so the output directories
can also be used as MATLAB structure fields.
"""
from __future__ import annotations

import math
import sys
from typing import Iterable

import torch
import torch.nn.functional as F


SUPPORTED_VARIANTS = (
    "full",
    "identity",
    "width_only",
    "shift_only",
    "no_shift",
    "no_width",
    "learned_support_only",
    "source_support_only",
    "smoothed_controls",
)


def gaussian_map(value: torch.Tensor, sigma: float = 2.0) -> torch.Tensor:
    radius = max(1, int(math.ceil(3 * sigma)))
    axis = torch.arange(-radius, radius + 1, device=value.device, dtype=value.dtype)
    kernel = torch.exp(-0.5 * (axis / sigma) ** 2)
    kernel /= kernel.sum()
    horizontal = kernel.view(1, 1, 1, -1)
    vertical = kernel.view(1, 1, -1, 1)
    result = F.conv2d(F.pad(value, (radius, radius, 0, 0), mode="reflect"), horizontal)
    return F.conv2d(F.pad(result, (0, 0, radius, radius), mode="reflect"), vertical)


def render_variant_aligned(model, raw: torch.Tensor, details, variant: str, smoothing_sigma: float = 2.0):
    """Render one intervention when ``raw`` and ``details`` have identical aligned shapes."""
    if variant not in SUPPORTED_VARIANTS:
        raise ValueError(f"Unsupported variant {variant!r}; choose from {SUPPORTED_VARIANTS}")
    if raw.shape[-2:] != details.output.shape[-2:]:
        raise ValueError("render_variant_aligned requires raw/details with identical spatial shapes")
    if variant == "identity":
        zero = torch.zeros_like(details.support)
        one = torch.ones_like(details.width_gain)
        return raw, {"support": zero, "source_support": zero, "learned_support": zero, "width": one, "shift": zero, "flow": torch.cat([zero, zero], 1)}

    model_module = sys.modules[model.__class__.__module__]
    cues = model.cues(raw)
    magnitude = cues["magnitude"].float()
    local_scale = cues["local_scale"].float()
    source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0, 1)
    learned_support = (0.85 * F.max_pool2d(details.boundary.float(), 9, 1, 4)).clamp(0, 1)
    support = torch.maximum(source_support, learned_support).clamp(0, 1)
    if variant == "learned_support_only":
        support = learned_support
    elif variant == "source_support_only":
        support = source_support

    width = details.width_gain.float()
    shift = details.normal_shift.float()
    if variant in {"shift_only", "no_width"}:
        width = torch.ones_like(width)
    if variant in {"width_only", "no_shift"}:
        shift = torch.zeros_like(shift)
    if variant == "smoothed_controls":
        width = gaussian_map(width, smoothing_sigma)
        shift = gaussian_map(shift, smoothing_sigma)

    smooth_gx, smooth_gy = model_module.gradients(cues["blurred"][1].float())
    smooth_magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1e-8)
    normal_x, normal_y = smooth_gx / smooth_magnitude, smooth_gy / smooth_magnitude
    flow = torch.cat([shift * normal_x, shift * normal_y], 1)
    warped = model.warp(raw.float(), flow * support)
    window = int(model_module.MCFG["local_range_window_px"])
    radius = window // 2
    local_max = F.max_pool2d(warped, window, 1, radius)
    local_min = -F.max_pool2d(-warped, window, 1, radius)
    dynamic = (local_max - local_min).clamp_min(2 / 255)
    unit = ((warped - local_min) / dynamic).clamp(1e-3, 1 - 1e-3)
    corrected = torch.sigmoid(width * (torch.log(unit) - torch.log1p(-unit)))
    proposal = local_min + dynamic * corrected
    output = (raw.float() + support * (proposal - raw.float())).clamp(0, 1)
    return output, {
        "support": support,
        "source_support": source_support,
        "learned_support": learned_support,
        "width": width,
        "shift": shift,
        "flow": flow,
    }


@torch.inference_mode()
def render_variants(model, raw: torch.Tensor, variants: Iterable[str] = SUPPORTED_VARIANTS, smoothing_sigma: float = 2.0):
    """Pad once, run learned controls once, render variants, and crop back exactly."""
    requested = tuple(variants)
    invalid = sorted(set(requested) - set(SUPPORTED_VARIANTS))
    if invalid:
        raise ValueError(f"Unsupported variants: {invalid}")
    height, width = raw.shape[-2:]
    multiple = int(model.alignment_multiple)
    pad_h, pad_w = (-height) % multiple, (-width) % multiple
    if pad_h or pad_w:
        mode = "reflect" if height > pad_h and width > pad_w else "replicate"
        aligned = F.pad(raw, (0, pad_w, 0, pad_h), mode=mode)
    else:
        aligned = raw
    details = model._forward_aligned(aligned)
    outputs = {}
    maps = {}
    for variant in requested:
        output, control_maps = render_variant_aligned(model, aligned, details, variant, smoothing_sigma=smoothing_sigma)
        outputs[variant] = output[..., :height, :width]
        maps[variant] = {name: value[..., :height, :width] for name, value in control_maps.items()}
    max_error = float(torch.max(torch.abs(outputs.get("full", details.output[..., :height, :width]) - details.output[..., :height, :width])).cpu())
    return outputs, maps, {"pad_h": pad_h, "pad_w": pad_w, "full_reproduction_max_abs": max_error}
