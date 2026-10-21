"""R42 COMBO/R42 low-alpha sweep policy and parsing helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch


def validate_state_dicts_compatible(
    sd_a: Mapping[str, torch.Tensor],
    sd_b: Mapping[str, torch.Tensor],
) -> None:
    keys_a = set(sd_a.keys())
    keys_b = set(sd_b.keys())
    if keys_a != keys_b:
        raise ValueError(
            f"state_dict key mismatch: only_in_a={sorted(keys_a - keys_b)[:5]} "
            f"only_in_b={sorted(keys_b - keys_a)[:5]}"
        )
    mismatched = []
    for key in sorted(keys_a):
        if tuple(sd_a[key].shape) != tuple(sd_b[key].shape):
            mismatched.append((key, tuple(sd_a[key].shape), tuple(sd_b[key].shape)))
    if mismatched:
        raise ValueError(f"state_dict shape mismatch: {mismatched[:5]}")


def interpolate_state_dicts(
    sd_a: Mapping[str, torch.Tensor],
    sd_b: Mapping[str, torch.Tensor],
    alpha: float,
) -> dict[str, torch.Tensor]:
    if alpha < 0.0 or alpha > 1.0:
        raise ValueError(f"alpha must be in [0, 1]; got {alpha}")
    out: dict[str, torch.Tensor] = {}
    for key, ta in sd_a.items():
        tb = sd_b[key]
        if torch.is_floating_point(ta) and torch.is_floating_point(tb):
            val = (1.0 - alpha) * ta + alpha * tb
            out[key] = val.to(ta.dtype) if ta.dtype == tb.dtype else val
        else:
            out[key] = tb.clone()
    return out


def alpha_tag(alpha: float) -> str:
    return f"a{int(round(alpha * 100)):03d}"


def default_alpha_grid() -> list[float]:
    return [0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20]


def parse_boundary_summary(summary: dict) -> dict:
    per_stage = {}
    for entry in summary.get("stages", []):
        per_stage[entry["stage"]] = {
            "psnr": float(entry["avg_psnr"]),
            "high_frequency_retention": float(entry["avg_hf_retention"]),
            "boundary_distance_px": float(entry["avg_boundary_distance_px"]),
            "boundary_fscore_t1p0": float(entry["avg_boundary_fscore_t1p0"]),
            "centerline_distance_px": float(entry.get("avg_centerline_distance_px", 0.0)),
            "grid_pitch_error_px": float(entry.get("avg_grid_pitch_error_px", 0.0)),
            "count": int(entry.get("count", 0)),
        }
    return {
        "overall_psnr": float(summary["overall_avg_psnr"]),
        "overall_high_frequency_retention": float(summary["overall_hf_retention"]),
        "overall_boundary_distance_px": float(summary["overall_boundary_distance_px"]),
        "overall_boundary_fscore_t1p0": float(summary["overall_boundary_fscore_t1p0"]),
        "total_count": int(summary.get("total_count", 0)),
        "per_stage": per_stage,
    }


def _maybe_float(value):
    return None if value is None else float(value)


def parse_ring_guard_summary(summary: dict) -> dict:
    scales: dict[str, dict] = {}
    for entry in summary.get("datasets", []):
        scales[entry["short_name"]] = {
            "expected_step_px": float(entry["expected_step_px"]),
            "step_std": float(entry["r42_internal_step_std_y"]),
            "combo_step_std": _maybe_float(entry.get("combo_internal_step_std_y")),
            "delta_vs_combo": _maybe_float(entry.get("delta_internal_step_std_y")),
            "relative_delta_vs_combo_pct": _maybe_float(entry.get("relative_delta_vs_combo_pct")),
            "local_guard_pass": bool(entry.get("local_guard_pass", False)),
        }
    return {"scales": scales, "local_ring_guard_pass": bool(summary.get("local_ring_guard_pass", False))}


def combine_sweep_row(alpha: float, boundary_parsed: dict, ring_parsed: dict) -> dict:
    scales = ring_parsed["scales"]
    return {
        "alpha": float(alpha),
        "alpha_tag": alpha_tag(alpha),
        "boundary_overall_psnr": boundary_parsed["overall_psnr"],
        "boundary_high_frequency_retention": boundary_parsed["overall_high_frequency_retention"],
        "boundary_distance_px": boundary_parsed["overall_boundary_distance_px"],
        "boundary_fscore_t1p0": boundary_parsed["overall_boundary_fscore_t1p0"],
        "boundary_per_stage": boundary_parsed["per_stage"],
        "ring_8px_step_std": scales["pitch1um_y_100"]["step_std"],
        "ring_0p8px_step_std": scales["pitch0p1um_y_60"]["step_std"],
        "ring_0p08px_step_std": scales["pitch0p01um_y_40"]["step_std"],
        "ring_8px_delta_pct": scales["pitch1um_y_100"].get("relative_delta_vs_combo_pct"),
        "ring_0p8px_delta_pct": scales["pitch0p1um_y_60"].get("relative_delta_vs_combo_pct"),
        "ring_0p08px_delta_pct": scales["pitch0p01um_y_40"].get("relative_delta_vs_combo_pct"),
        "local_ring_guard_pass": ring_parsed["local_ring_guard_pass"],
    }


@dataclass(frozen=True)
class BoundaryTradeoffThresholds:
    min_boundary_psnr: float
    min_high_frequency_retention: float
    max_boundary_distance_px: float
    min_boundary_fscore_t1p0: float
    max_8px: float
    max_0p8px: float
    max_0p08px: float


DEFAULT_THRESHOLDS = BoundaryTradeoffThresholds(
    min_boundary_psnr=23.0,
    min_high_frequency_retention=0.30,
    max_boundary_distance_px=7.0,
    min_boundary_fscore_t1p0=0.70,
    max_8px=0.1431,
    max_0p8px=0.1615,
    max_0p08px=0.1268,
)


def _meets_boundary(row: dict, thresholds: BoundaryTradeoffThresholds) -> bool:
    return (
        row["boundary_overall_psnr"] >= thresholds.min_boundary_psnr
        and row["boundary_high_frequency_retention"] >= thresholds.min_high_frequency_retention
        and row["boundary_distance_px"] <= thresholds.max_boundary_distance_px
        and row["boundary_fscore_t1p0"] >= thresholds.min_boundary_fscore_t1p0
    )


def _meets_ring(row: dict, thresholds: BoundaryTradeoffThresholds) -> bool:
    return (
        row["ring_8px_step_std"] <= thresholds.max_8px
        and row["ring_0p8px_step_std"] <= thresholds.max_0p8px
        and row["ring_0p08px_step_std"] <= thresholds.max_0p08px
    )


def _capacity_key(row: dict) -> tuple[float, float, float]:
    return (
        float(row["boundary_overall_psnr"]),
        float(row["boundary_fscore_t1p0"]),
        -float(row["boundary_distance_px"]),
    )


def evaluate_boundary_tradeoff(rows: list[dict], thresholds: BoundaryTradeoffThresholds) -> dict:
    guarded = [r for r in rows if _meets_boundary(r, thresholds) and _meets_ring(r, thresholds)]
    if guarded:
        best = max(guarded, key=_capacity_key)
        return {
            "found": True,
            "best": best,
            "boundary_only_best": None,
            "reason": f"guarded boundary trade-off found at alpha={best['alpha']:.2f}",
        }
    boundary_rows = [r for r in rows if _meets_boundary(r, thresholds)] or list(rows)
    boundary_best = max(boundary_rows, key=_capacity_key) if boundary_rows else None
    return {
        "found": False,
        "best": None,
        "boundary_only_best": boundary_best,
        "reason": "no alpha satisfies both boundary-capacity and local ring-guard thresholds",
    }
