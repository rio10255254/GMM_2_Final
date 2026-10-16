"""Analytic periodic scenes and differentiable wrong-period rejection for R98.

The shapes are deliberately generic (bars, dots, rings and rectangles).  No
real microscopy pixels or specimen geometry are used.  Every pattern contains
weak, spatially distributed anchors so the correct translation is observable
instead of being mathematically indistinguishable from a one-period slip.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np
import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class PeriodicBatch:
    source: torch.Tensor
    target: torch.Tensor
    shift_xy: torch.Tensor
    period_xy: torch.Tensor


def _render_clean(size: int, rng: np.random.Generator) -> tuple[np.ndarray, int, int]:
    yy, xx = np.mgrid[:size, :size].astype(np.float32)
    period_x = int(rng.integers(max(24, size // 8), max(32, size // 3)))
    period_y = int(rng.integers(max(24, size // 8), max(32, size // 3)))
    angle = float(rng.uniform(-math.pi, math.pi))
    ca, sa = math.cos(angle), math.sin(angle)
    xr = ca * xx - sa * yy
    yr = sa * xx + ca * yy
    family = int(rng.integers(0, 4))
    if family == 0:
        lattice = 0.5 * (np.cos(2.0 * math.pi * xr / period_x) + np.cos(2.0 * math.pi * yr / period_y))
    elif family == 1:
        lattice = np.cos(2.0 * math.pi * xr / period_x) * np.cos(2.0 * math.pi * yr / period_y)
    elif family == 2:
        dx = np.minimum(np.mod(xr, period_x), period_x - np.mod(xr, period_x))
        dy = np.minimum(np.mod(yr, period_y), period_y - np.mod(yr, period_y))
        radius = 0.15 * min(period_x, period_y)
        lattice = np.exp(-(dx * dx + dy * dy) / (2.0 * radius * radius)) * 2.0 - 1.0
    else:
        bars_x = (np.mod(xr, period_x) < 0.34 * period_x).astype(np.float32)
        bars_y = (np.mod(yr, period_y) < 0.28 * period_y).astype(np.float32)
        lattice = 2.0 * (0.65 * bars_x + 0.35 * bars_y) - 1.0

    # Low-frequency context and several weak unique anchors disambiguate a
    # true shift from a neighbouring pitch without copying any real sample.
    context = 0.12 * np.sin(2.0 * math.pi * xx / (size * rng.uniform(0.7, 1.4)) + rng.uniform(-math.pi, math.pi))
    context += 0.10 * np.cos(2.0 * math.pi * yy / (size * rng.uniform(0.8, 1.6)) + rng.uniform(-math.pi, math.pi))
    anchor = np.zeros((size, size), np.float32)
    for _ in range(5):
        cx = float(rng.uniform(0.12, 0.88) * size)
        cy = float(rng.uniform(0.12, 0.88) * size)
        sx = float(rng.uniform(0.025, 0.075) * size)
        sy = float(rng.uniform(0.025, 0.075) * size)
        sign = float(rng.choice([-1.0, 1.0]))
        anchor += sign * np.exp(-0.5 * (((xx - cx) / sx) ** 2 + ((yy - cy) / sy) ** 2))
    clean = 0.50 + float(rng.uniform(0.20, 0.34)) * lattice + context + 0.10 * anchor
    clean = np.clip(clean, 0.03, 0.97).astype(np.float32)
    return clean, period_x, period_y


def _degrade(clean: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    sigma_x = float(rng.uniform(0.45, 1.9))
    sigma_y = float(rng.uniform(0.45, 1.9))
    blurred = cv2.GaussianBlur(clean, (0, 0), sigmaX=sigma_x, sigmaY=sigma_y)
    gamma = float(rng.uniform(0.78, 1.28))
    gain = float(rng.uniform(0.82, 1.18))
    bias = float(rng.uniform(-0.055, 0.055))
    source = gain * np.power(np.clip(blurred, 1e-5, 1.0), gamma) + bias
    noise = rng.normal(0.0, rng.uniform(0.002, 0.018), clean.shape).astype(np.float32)
    yy, xx = np.mgrid[:clean.shape[0], :clean.shape[1]].astype(np.float32)
    fixed = float(rng.uniform(0.0, 0.010)) * np.sin(2.0 * math.pi * xx / rng.uniform(19.0, 61.0))
    return np.clip(source + noise + fixed, 0.0, 1.0).astype(np.float32)


def make_periodic_batch(
    batch_size: int,
    size: int,
    seed: int,
    *,
    device: torch.device | str = "cpu",
) -> PeriodicBatch:
    if size < 96 or size % 8:
        raise ValueError("periodic scene size must be an eight-pixel multiple >= 96")
    sources: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    shifts: list[tuple[float, float]] = []
    periods: list[tuple[float, float]] = []
    for index in range(int(batch_size)):
        rng = np.random.default_rng(int(seed) * 1000003 + index * 10007)
        clean, period_x, period_y = _render_clean(size, rng)
        dx = float(rng.uniform(-2.5, 2.5))
        dy = float(rng.uniform(-2.5, 2.5))
        matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], np.float32)
        moved = cv2.warpAffine(
            clean, matrix, (size, size), flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        sources.extend([_degrade(clean, rng), _degrade(moved, rng)])
        targets.extend([clean, moved])
        shifts.append((dx, dy))
        periods.append((float(period_x), float(period_y)))
    to_tensor = lambda rows: torch.from_numpy(np.stack(rows))[:, None].to(device=device, dtype=torch.float32)
    return PeriodicBatch(
        source=to_tensor(sources),
        target=to_tensor(targets),
        shift_xy=torch.tensor(shifts, device=device, dtype=torch.float32),
        period_xy=torch.tensor(periods, device=device, dtype=torch.float32),
    )


def _gradient_features(x: torch.Tensor) -> torch.Tensor:
    low = F.avg_pool2d(F.pad(x, (4, 4, 4, 4), mode="reflect"), 9, stride=1)
    fine = x - F.avg_pool2d(F.pad(x, (1, 1, 1, 1), mode="reflect"), 3, stride=1)
    gx = fine[..., :, 2:] - fine[..., :, :-2]
    gy = fine[..., 2:, :] - fine[..., :-2, :]
    gx = F.pad(gx, (1, 1, 0, 0), mode="replicate")
    gy = F.pad(gy, (0, 0, 1, 1), mode="replicate")
    return torch.cat([0.65 * low, gx, gy], dim=1)


def _normalized_similarity(reference: torch.Tensor, moved: torch.Tensor) -> torch.Tensor:
    margin = max(12, min(reference.shape[-2:]) // 12)
    reference = reference[..., margin:-margin, margin:-margin]
    moved = moved[..., margin:-margin, margin:-margin]
    reference = reference - reference.mean(dim=(-2, -1), keepdim=True)
    moved = moved - moved.mean(dim=(-2, -1), keepdim=True)
    numerator = (reference * moved).mean(dim=(1, 2, 3))
    # Add the floor before sqrt.  Clamping sqrt(0) afterwards leaves an
    # infinite derivative in autograd (0 * inf becomes NaN on flat regions).
    reference_energy = reference.float().square().mean(dim=(1, 2, 3))
    moved_energy = moved.float().square().mean(dim=(1, 2, 3))
    denominator = torch.sqrt(reference_energy * moved_energy + 1e-12)
    return numerator / denominator


def _translate(x: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor) -> torch.Tensor:
    batch, _channels, height, width = x.shape
    theta = torch.zeros((batch, 2, 3), device=x.device, dtype=x.dtype)
    theta[:, 0, 0] = 1.0
    theta[:, 1, 1] = 1.0
    theta[:, 0, 2] = -2.0 * dx / max(width - 1, 1)
    theta[:, 1, 2] = -2.0 * dy / max(height - 1, 1)
    grid = F.affine_grid(theta, x.shape, align_corners=True)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="reflection", align_corners=True)


def wrong_period_margin_loss(
    reconstructed: torch.Tensor,
    shift_xy: torch.Tensor,
    period_xy: torch.Tensor,
    *,
    margin: float = 0.025,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    if reconstructed.shape[0] % 2:
        raise ValueError("periodic reconstructions must contain reference/moved pairs")
    reference = _gradient_features(reconstructed[0::2])
    moved = _gradient_features(reconstructed[1::2])
    aligned = _translate(moved, -shift_xy[:, 0], -shift_xy[:, 1])
    true_score = _normalized_similarity(reference, aligned)
    wrong_scores = []
    for axis, sign in ((0, -1.0), (0, 1.0), (1, -1.0), (1, 1.0)):
        wrong_dx = -shift_xy[:, 0].clone()
        wrong_dy = -shift_xy[:, 1].clone()
        if axis == 0:
            wrong_dx = wrong_dx + sign * period_xy[:, 0]
        else:
            wrong_dy = wrong_dy + sign * period_xy[:, 1]
        wrong = _translate(moved, wrong_dx, wrong_dy)
        wrong_scores.append(_normalized_similarity(reference, wrong))
    hardest_wrong = torch.stack(wrong_scores, dim=1).max(dim=1).values
    loss = F.softplus((hardest_wrong + float(margin) - true_score) * 24.0).mean() / 24.0
    return loss, {
        "true_score": true_score.mean(),
        "hardest_wrong_score": hardest_wrong.mean(),
        "match_margin": (true_score - hardest_wrong).mean(),
        "wrong_pitch_rate": (hardest_wrong >= true_score).float().mean(),
    }


def phase_anchor_loss(source: torch.Tensor, output: torch.Tensor) -> torch.Tensor:
    """Penalize a change in local edge phase without penalizing edge strength."""
    source_features = _gradient_features(source)[:, 1:]
    output_features = _gradient_features(output)[:, 1:]
    # The epsilon belongs inside sqrt.  Putting clamp_min after sqrt creates
    # NaN gradients at every exactly-flat pixel even though the forward loss
    # itself is finite.
    source_norm = torch.sqrt(source_features.float().square().sum(dim=1, keepdim=True) + 1e-8)
    output_norm = torch.sqrt(output_features.float().square().sum(dim=1, keepdim=True) + 1e-8)
    source_direction = source_features / source_norm
    output_direction = output_features / output_norm
    edge_weight = source_norm.detach()
    edge_weight = edge_weight / edge_weight.mean(dim=(-2, -1), keepdim=True).clamp_min(1e-4)
    direction_error = 1.0 - (source_direction * output_direction).sum(dim=1, keepdim=True).clamp(-1.0, 1.0)
    return (direction_error * edge_weight.clamp_max(4.0)).mean()
