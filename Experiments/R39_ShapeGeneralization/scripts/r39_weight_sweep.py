"""R39 weight-averaging sweep between COMBO and an R39 candidate.

Pure logic only in this module: state_dict validation, linear interpolation,
JSON parsing, and sweet-spot thresholding. Orchestration (subprocess calls,
filesystem layout, CLI) lives in the companion runner module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch


# ----------------------------------------------------------------------------
# state_dict validation and interpolation
# ----------------------------------------------------------------------------

def validate_state_dicts_compatible(
    sd_a: Mapping[str, torch.Tensor],
    sd_b: Mapping[str, torch.Tensor],
) -> None:
    """Raise ValueError if the two state_dicts are not key/shape compatible."""
    keys_a = set(sd_a.keys())
    keys_b = set(sd_b.keys())
    if keys_a != keys_b:
        only_a = sorted(keys_a - keys_b)
        only_b = sorted(keys_b - keys_a)
        raise ValueError(
            f"state_dict key mismatch: only_in_a={only_a[:5]} only_in_b={only_b[:5]}"
        )

    mismatched_shapes = []
    for k in sorted(keys_a):
        sa = tuple(sd_a[k].shape)
        sb = tuple(sd_b[k].shape)
        if sa != sb:
            mismatched_shapes.append((k, sa, sb))
    if mismatched_shapes:
        first = mismatched_shapes[:5]
        raise ValueError(f"state_dict shape mismatch: {first}")


def interpolate_state_dicts(
    sd_a: Mapping[str, torch.Tensor],
    sd_b: Mapping[str, torch.Tensor],
    alpha: float,
) -> dict[str, torch.Tensor]:
    """Return W = (1 - alpha) * sd_a + alpha * sd_b for floating tensors.

    Non-floating tensors (e.g. BN num_batches_tracked) are taken from sd_b
    so the interpolated checkpoint reflects the more recently trained state.
    """
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError(f"alpha must be in [0, 1]; got {alpha}")
    out: dict[str, torch.Tensor] = {}
    for k, ta in sd_a.items():
        tb = sd_b[k]
        if torch.is_floating_point(ta) and torch.is_floating_point(tb):
            out[k] = (1.0 - alpha) * ta + alpha * tb
            if ta.dtype == tb.dtype:
                out[k] = out[k].to(ta.dtype)
        else:
            out[k] = tb.clone()
    return out


# ----------------------------------------------------------------------------
# alpha grid + tag
# ----------------------------------------------------------------------------

def alpha_tag(alpha: float) -> str:
    """Stable filesystem-safe tag, e.g. 0.5 -> 'a050'."""
    rounded = int(round(alpha * 100))
    return f"a{rounded:03d}"


def default_alpha_grid() -> list[float]:
    """Eleven evenly spaced alphas in [0.0, 1.0] inclusive."""
    return [round(i / 10.0, 2) for i in range(11)]


# ----------------------------------------------------------------------------
# JSON parsing helpers
# ----------------------------------------------------------------------------

def parse_shape_summary(summary: dict) -> dict:
    """Extract overall + per-stage PSNR / SSIM from a shape recon summary JSON."""
    per_stage = {}
    for entry in summary.get("stages", []):
        per_stage[entry["stage"]] = {
            "psnr": float(entry["avg_psnr"]),
            "ssim": float(entry["avg_ssim"]),
            "count": int(entry.get("count", 0)),
        }
    return {
        "overall_psnr": float(summary["overall_avg_psnr"]),
        "overall_ssim": float(summary["overall_avg_ssim"]),
        "total_count": int(summary.get("total_count", 0)),
        "per_stage": per_stage,
    }


def parse_ring_guard_summary(summary: dict) -> dict:
    """Extract three-scale step_std + residual stats from a ring guard summary."""
    scales: dict[str, dict] = {}
    for entry in summary.get("datasets", []):
        scales[entry["short_name"]] = {
            "expected_step_px": float(entry["expected_step_px"]),
            "step_std": float(entry["r39_internal_step_std_y"]),
            "combo_step_std": _maybe_float(entry.get("combo_internal_step_std_y")),
            "delta_vs_combo": _maybe_float(entry.get("delta_internal_step_std_y")),
            "outer_residual_mean": _maybe_float(entry.get("r39_outer_residual_mean")),
            "inner_residual_mean": _maybe_float(entry.get("r39_inner_residual_mean")),
        }
    return {"scales": scales}


def _maybe_float(value):
    return None if value is None else float(value)


# ----------------------------------------------------------------------------
# sweep row + sweet-spot evaluation
# ----------------------------------------------------------------------------

def combine_sweep_row(alpha: float, shape_parsed: dict, ring_parsed: dict) -> dict:
    scales = ring_parsed["scales"]
    return {
        "alpha": float(alpha),
        "alpha_tag": alpha_tag(alpha),
        "shape_overall_psnr": shape_parsed["overall_psnr"],
        "shape_overall_ssim": shape_parsed["overall_ssim"],
        "shape_per_stage": shape_parsed["per_stage"],
        "ring_8px_step_std": scales["pitch1um_y_100"]["step_std"],
        "ring_0p8px_step_std": scales["pitch0p1um_y_60"]["step_std"],
        "ring_0p08px_step_std": scales["pitch0p01um_y_40"]["step_std"],
        "ring_8px_outer_residual_mean": scales["pitch1um_y_100"]["outer_residual_mean"],
        "ring_0p8px_outer_residual_mean": scales["pitch0p1um_y_60"]["outer_residual_mean"],
        "ring_0p08px_outer_residual_mean": scales["pitch0p01um_y_40"]["outer_residual_mean"],
    }


@dataclass(frozen=True)
class SweetSpotThresholds:
    min_shape_psnr: float
    max_8px: float
    max_0p8px: float
    max_0p08px: float


def evaluate_sweet_spot(rows: list[dict], thresholds: SweetSpotThresholds) -> dict:
    """Pick the row with highest shape PSNR that satisfies all ring caps.

    Returns {"found": bool, "best": row_dict | None, "reason": str}.
    """
    qualifying = [
        r for r in rows
        if r["shape_overall_psnr"] >= thresholds.min_shape_psnr
        and r["ring_8px_step_std"] <= thresholds.max_8px
        and r["ring_0p8px_step_std"] <= thresholds.max_0p8px
        and r["ring_0p08px_step_std"] <= thresholds.max_0p08px
    ]
    if not qualifying:
        return {
            "found": False,
            "best": None,
            "reason": (
                "no alpha satisfies all four thresholds "
                f"(min_psnr={thresholds.min_shape_psnr}, "
                f"max_8px={thresholds.max_8px}, "
                f"max_0p8px={thresholds.max_0p8px}, "
                f"max_0p08px={thresholds.max_0p08px})"
            ),
        }
    best = max(qualifying, key=lambda r: r["shape_overall_psnr"])
    return {
        "found": True,
        "best": best,
        "reason": f"sweet spot found at alpha={best['alpha']:.2f}",
    }
