"""Paired sequence-stratified uncertainty for R109 LSC interventions."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "physical_validation" / "lsc_interventions"
PAIRS = OUTPUT / "tables" / "combined_lsc_per_pair.csv"
CANDIDATES = ("no_shift", "smoothed_controls")


def bootstrap(pairs: pd.DataFrame, candidate: str, repetitions: int = 10_000) -> dict[str, object]:
    keys = ["sequence", "start_frame_index", "end_frame_index"]
    paired = pairs.loc[pairs["method"].eq("R109 E48")].merge(
        pairs.loc[pairs["method"].eq(candidate)], on=keys, suffixes=("_full", "_candidate"), validate="one_to_one"
    )
    rng = np.random.default_rng(113503 + sum(ord(value) for value in candidate))
    values = np.empty((repetitions, 4), float)
    groups = [group for _, group in paired.groupby("sequence", sort=False)]
    for index in range(repetitions):
        sampled = [group.iloc[rng.integers(0, len(group), len(group))] for group in groups]
        full_sd = np.mean([group["measured_step_um_full"].std(ddof=1) * 1000 for group in sampled])
        candidate_sd = np.mean([group["measured_step_um_candidate"].std(ddof=1) * 1000 for group in sampled])
        values[index] = [
            candidate_sd - full_sd,
            np.mean(np.concatenate([group["nominal_abs_error_nm_candidate"].to_numpy() for group in sampled])) - np.mean(np.concatenate([group["nominal_abs_error_nm_full"].to_numpy() for group in sampled])),
            np.median(np.concatenate([group["within_grid_sd_nm_candidate"].to_numpy() for group in sampled])) - np.median(np.concatenate([group["within_grid_sd_nm_full"].to_numpy() for group in sampled])),
            np.median(np.concatenate([group["cross_axis_abs_nm_candidate"].to_numpy() for group in sampled])) - np.median(np.concatenate([group["cross_axis_abs_nm_full"].to_numpy() for group in sampled])),
        ]
    names = ("step_sd_nm", "nominal_mae_nm", "within_grid_median_nm", "cross_axis_median_nm")
    observed = [
        np.mean([group["measured_step_um_candidate"].std(ddof=1) * 1000 for group in groups]) - np.mean([group["measured_step_um_full"].std(ddof=1) * 1000 for group in groups]),
        paired["nominal_abs_error_nm_candidate"].mean() - paired["nominal_abs_error_nm_full"].mean(),
        paired["within_grid_sd_nm_candidate"].median() - paired["within_grid_sd_nm_full"].median(),
        paired["cross_axis_abs_nm_candidate"].median() - paired["cross_axis_abs_nm_full"].median(),
    ]
    metrics = {}
    for column, name in enumerate(names):
        low, high = np.percentile(values[:, column], [2.5, 97.5])
        metrics[name] = {
            "observed_candidate_minus_full": float(observed[column]),
            "ci95": [float(low), float(high)],
            "fraction_candidate_worse": float(np.mean(values[:, column] > 0)),
            "interval_includes_zero": bool(low <= 0 <= high),
        }
    return {"candidate": candidate, "paired_rows": len(paired), "metrics": metrics}


def main() -> int:
    pairs = pd.read_csv(PAIRS)
    results = [bootstrap(pairs, candidate) for candidate in CANDIDATES]
    payload = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "method": "paired sequence-stratified bootstrap",
        "repetitions": 10_000,
        "comparisons": results,
        "interpretation_boundary": "Intervals quantify repeatability differences on Raw-locked pairs; commanded motion is not independent stage truth.",
    }
    (OUTPUT / "uncertainty.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
