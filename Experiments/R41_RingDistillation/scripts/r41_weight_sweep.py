"""R41 weight-sweep policy and thresholds."""
from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
R40_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"
if str(R40_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(R40_SCRIPT_DIR))

from r40_weight_sweep import (  # noqa: E402,F401
    CapacityTradeoffThresholds,
    alpha_tag,
    combine_sweep_row,
    evaluate_capacity_tradeoff,
    interpolate_state_dicts,
    parse_micro_summary,
    validate_state_dicts_compatible,
)


DEFAULT_THRESHOLDS = CapacityTradeoffThresholds(
    min_micro_psnr=26.0,
    min_high_frequency_retention=0.30,
    max_8px=0.159,
    max_0p8px=0.141,
    max_0p08px=0.107,
)


def default_alpha_grid() -> list[float]:
    return [round(v, 2) for v in (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)]


def _maybe_float(value):
    return None if value is None else float(value)


def parse_ring_guard_summary(summary: dict) -> dict:
    scales: dict[str, dict] = {}
    for entry in summary.get("datasets", []):
        scales[entry["short_name"]] = {
            "expected_step_px": float(entry["expected_step_px"]),
            "step_std": float(entry.get("r41_internal_step_std_y", entry.get("r40_internal_step_std_y", entry.get("r39_internal_step_std_y")))),
            "combo_step_std": _maybe_float(entry.get("combo_internal_step_std_y")),
            "delta_vs_combo": _maybe_float(entry.get("delta_internal_step_std_y")),
            "outer_residual_mean": _maybe_float(entry.get("r41_outer_residual_mean", entry.get("r40_outer_residual_mean", entry.get("r39_outer_residual_mean")))),
            "inner_residual_mean": _maybe_float(entry.get("r41_inner_residual_mean", entry.get("r40_inner_residual_mean", entry.get("r39_inner_residual_mean")))),
        }
    return {"scales": scales}
