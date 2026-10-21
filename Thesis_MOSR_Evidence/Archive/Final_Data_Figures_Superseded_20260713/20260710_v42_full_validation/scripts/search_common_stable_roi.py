from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _axis_positions(start: int, stop: int, stride: int) -> list[int]:
    if stop < start:
        return []
    values = list(range(start, stop + 1, stride))
    if values[-1] != stop:
        values.append(stop)
    return values


def build_candidate_grid(
    image_width: int,
    image_height: int,
    roi_width: int,
    roi_height: int,
    stride_x: int,
    stride_y: int,
    margin: int = 24,
) -> list[tuple[int, int, int, int]]:
    max_x = image_width - margin - roi_width
    max_y = image_height - margin - roi_height
    xs = _axis_positions(margin, max_x, stride_x)
    ys = _axis_positions(margin, max_y, stride_y)
    return [(x, y, roi_width, roi_height) for y in ys for x in xs]


def roi_inside_bounds(
    roi: tuple[int, int, int, int],
    bounds: tuple[int, int, int, int],
) -> bool:
    x, y, width, height = roi
    bound_x, bound_y, bound_width, bound_height = bounds
    return bool(
        x >= bound_x
        and y >= bound_y
        and x + width <= bound_x + bound_width
        and y + height <= bound_y + bound_height
    )


def candidate_id_for_roi(family: str, roi: tuple[int, int, int, int]) -> str:
    x, y, width, height = roi
    return f"{family}_x{x:04d}_y{y:04d}_w{width:04d}_h{height:04d}"


def classify_final_roi_status(
    search_pass: bool,
    heldout_improvements: list[float],
    all_step_improvements: list[float],
    heldout_valid_counts: list[int],
    min_heldout_valid: int = 15,
) -> str:
    heldout_ok = (
        len(heldout_improvements) == 2
        and all(np.isfinite(value) and value > 0 for value in heldout_improvements)
        and len(heldout_valid_counts) == 2
        and all(value >= min_heldout_valid for value in heldout_valid_counts)
    )
    all_steps_ok = len(all_step_improvements) == 2 and all(
        np.isfinite(value) and value > 0 for value in all_step_improvements
    )
    return "robust_common" if search_pass and heldout_ok and all_steps_ok else "not_common"


def candidate_fold_summary(
    measurements: pd.DataFrame,
    min_valid_per_fold: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    keys = ["candidate_id", "group", "fold"]
    for key, part in measurements.groupby(keys, sort=False):
        valid = part[part.common_valid.astype(bool)]
        by_case = {
            case: case_rows.x_step_um.to_numpy(dtype=np.float64)
            for case, case_rows in valid.groupby("case", sort=False)
        }
        raw = by_case.get("raw", np.array([], dtype=np.float64))
        v42 = by_case.get("v42_e120", np.array([], dtype=np.float64))
        n_common = min(len(raw), len(v42))
        raw_sd = float(np.std(raw, ddof=1) * 1000.0) if len(raw) >= 2 else np.nan
        v42_sd = float(np.std(v42, ddof=1) * 1000.0) if len(v42) >= 2 else np.nan
        improvement = (
            float((raw_sd - v42_sd) / raw_sd * 100.0)
            if np.isfinite(raw_sd) and raw_sd > 0 and np.isfinite(v42_sd)
            else np.nan
        )
        passes = bool(
            n_common >= min_valid_per_fold
            and np.isfinite(improvement)
            and improvement > 0.0
        )
        rows.append(
            {
                "candidate_id": key[0],
                "group": key[1],
                "fold": int(key[2]),
                "raw_sd_nm": raw_sd,
                "v42_sd_nm": v42_sd,
                "improvement_pct": improvement,
                "n_common_valid": int(n_common),
                "passes_fold": passes,
            }
        )
    return pd.DataFrame(rows)


def candidate_group_summary(
    measurements: pd.DataFrame,
    min_valid_per_group: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for key, part in measurements.groupby(["candidate_id", "group"], sort=False):
        valid = part[part.common_valid.astype(bool)]
        by_case = {
            case: case_rows.x_step_um.to_numpy(dtype=np.float64)
            for case, case_rows in valid.groupby("case", sort=False)
        }
        raw = by_case.get("raw", np.array([], dtype=np.float64))
        v42 = by_case.get("v42_e120", np.array([], dtype=np.float64))
        n_common = min(len(raw), len(v42))
        raw_sd = float(np.std(raw, ddof=1) * 1000.0) if len(raw) >= 2 else np.nan
        v42_sd = float(np.std(v42, ddof=1) * 1000.0) if len(v42) >= 2 else np.nan
        improvement = (
            float((raw_sd - v42_sd) / raw_sd * 100.0)
            if np.isfinite(raw_sd) and raw_sd > 0 and np.isfinite(v42_sd)
            else np.nan
        )
        rows.append(
            {
                "candidate_id": key[0],
                "group": key[1],
                "raw_sd_nm": raw_sd,
                "v42_sd_nm": v42_sd,
                "improvement_pct": improvement,
                "n_common_valid": int(n_common),
                "passes_group": bool(
                    n_common >= min_valid_per_group
                    and np.isfinite(improvement)
                    and improvement > 0.0
                ),
            }
        )
    return pd.DataFrame(rows)


def choose_common_candidate(
    group_summary: pd.DataFrame,
    expected_groups: int,
) -> tuple[str | None, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for candidate_id, part in group_summary.groupby("candidate_id", sort=False):
        complete = len(part) == expected_groups
        common_pass = bool(complete and part.passes_group.astype(bool).all())
        rows.append(
            {
                "candidate_id": candidate_id,
                "groups_present": int(len(part)),
                "common_pass": common_pass,
                "min_improvement_pct": float(part.improvement_pct.min()),
                "median_improvement_pct": float(part.improvement_pct.median()),
                "mean_improvement_pct": float(part.improvement_pct.mean()),
            }
        )
    ranking = pd.DataFrame(rows).sort_values(
        ["common_pass", "min_improvement_pct", "median_improvement_pct"],
        ascending=[False, False, False],
    )
    passing = ranking[ranking.common_pass]
    selected = None if passing.empty else str(passing.iloc[0].candidate_id)
    return selected, ranking.reset_index(drop=True)


def choose_strict_common_candidate(
    fold_summary: pd.DataFrame,
    expected_cells: int,
) -> tuple[str | None, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    for candidate_id, part in fold_summary.groupby("candidate_id", sort=False):
        complete = len(part) == expected_cells
        strict_pass = bool(complete and part.passes_fold.astype(bool).all())
        rows.append(
            {
                "candidate_id": candidate_id,
                "cells_present": int(len(part)),
                "strict_pass": strict_pass,
                "min_improvement_pct": float(part.improvement_pct.min()),
                "median_improvement_pct": float(part.improvement_pct.median()),
                "mean_improvement_pct": float(part.improvement_pct.mean()),
            }
        )
    ranking = pd.DataFrame(rows).sort_values(
        ["strict_pass", "min_improvement_pct", "median_improvement_pct"],
        ascending=[False, False, False],
    )
    passing = ranking[ranking.strict_pass]
    selected = None if passing.empty else str(passing.iloc[0].candidate_id)
    return selected, ranking.reset_index(drop=True)


if __name__ == "__main__":
    raise SystemExit(
        "The tested ROI scoring helpers are ready; the experiment runner is added next."
    )
