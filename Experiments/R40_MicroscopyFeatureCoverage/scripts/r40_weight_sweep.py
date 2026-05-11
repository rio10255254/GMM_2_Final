"""Pure logic for R40 COMBO/candidate weight averaging."""
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
    return [round(i / 10.0, 2) for i in range(11)]


def parse_micro_summary(summary: dict) -> dict:
    per_stage = {}
    for entry in summary.get("stages", []):
        per_stage[entry["stage"]] = {
            "feature_family": entry.get("feature_family", "unknown"),
            "psnr": float(entry["avg_psnr"]),
            "ssim": float(entry["avg_ssim"]),
            "high_frequency_retention": float(entry.get("avg_high_frequency_retention", 0.0)),
            "edge_retention": float(entry.get("avg_edge_retention", 0.0)),
            "count": int(entry.get("count", 0)),
        }
    return {
        "overall_psnr": float(summary["overall_avg_psnr"]),
        "overall_ssim": float(summary["overall_avg_ssim"]),
        "overall_high_frequency_retention": float(summary.get("overall_high_frequency_retention", 0.0)),
        "overall_edge_retention": float(summary.get("overall_edge_retention", 0.0)),
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
            "step_std": float(entry.get("r40_internal_step_std_y", entry.get("r39_internal_step_std_y"))),
            "combo_step_std": _maybe_float(entry.get("combo_internal_step_std_y")),
            "delta_vs_combo": _maybe_float(entry.get("delta_internal_step_std_y")),
            "outer_residual_mean": _maybe_float(entry.get("r40_outer_residual_mean", entry.get("r39_outer_residual_mean"))),
            "inner_residual_mean": _maybe_float(entry.get("r40_inner_residual_mean", entry.get("r39_inner_residual_mean"))),
        }
    return {"scales": scales}


def combine_sweep_row(alpha: float, micro_parsed: dict, ring_parsed: dict) -> dict:
    scales = ring_parsed["scales"]
    return {
        "alpha": float(alpha),
        "alpha_tag": alpha_tag(alpha),
        "micro_overall_psnr": micro_parsed["overall_psnr"],
        "micro_overall_ssim": micro_parsed["overall_ssim"],
        "micro_high_frequency_retention": micro_parsed["overall_high_frequency_retention"],
        "micro_edge_retention": micro_parsed["overall_edge_retention"],
        "micro_per_stage": micro_parsed["per_stage"],
        "ring_8px_step_std": scales["pitch1um_y_100"]["step_std"],
        "ring_0p8px_step_std": scales["pitch0p1um_y_60"]["step_std"],
        "ring_0p08px_step_std": scales["pitch0p01um_y_40"]["step_std"],
    }


@dataclass(frozen=True)
class CapacityTradeoffThresholds:
    min_micro_psnr: float
    min_high_frequency_retention: float
    max_8px: float
    max_0p8px: float
    max_0p08px: float


def _meets_micro(row: dict, thresholds: CapacityTradeoffThresholds) -> bool:
    return (
        row["micro_overall_psnr"] >= thresholds.min_micro_psnr
        and row["micro_high_frequency_retention"] >= thresholds.min_high_frequency_retention
    )


def _meets_ring(row: dict, thresholds: CapacityTradeoffThresholds) -> bool:
    return (
        row["ring_8px_step_std"] <= thresholds.max_8px
        and row["ring_0p8px_step_std"] <= thresholds.max_0p8px
        and row["ring_0p08px_step_std"] <= thresholds.max_0p08px
    )


def _capacity_key(row: dict) -> tuple[float, float]:
    return (float(row["micro_overall_psnr"]), float(row["micro_high_frequency_retention"]))


def evaluate_capacity_tradeoff(rows: list[dict], thresholds: CapacityTradeoffThresholds) -> dict:
    guarded = [r for r in rows if _meets_micro(r, thresholds) and _meets_ring(r, thresholds)]
    if guarded:
        best = max(guarded, key=_capacity_key)
        return {
            "found": True,
            "best": best,
            "capacity_only_best": None,
            "reason": f"guarded trade-off found at alpha={best['alpha']:.2f}",
        }
    capacity_rows = [r for r in rows if _meets_micro(r, thresholds)] or list(rows)
    capacity_best = max(capacity_rows, key=_capacity_key) if capacity_rows else None
    return {
        "found": False,
        "best": None,
        "capacity_only_best": capacity_best,
        "reason": "no alpha satisfies both microscopy-capacity and ring-guard thresholds",
    }
