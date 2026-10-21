"""Quantify uncertainty and validate the deterministic current-top30 LSC comparison."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "lsc_current_top30"
PAIR_PATH = OUTPUT / "tables" / "four_method_lsc_per_pair_current_top30.csv"
SUMMARY_PATH = OUTPUT / "lsc_current_top30_summary.json"


def main() -> int:
    pairs = pd.read_csv(PAIR_PATH, encoding="utf-8-sig")
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    expected_methods = ["R109 E48", "Raw", "V42 E120", "Wiener"]
    if sorted(pairs["method"].unique().tolist()) != expected_methods:
        raise RuntimeError("Unexpected LSC method set")
    if len(pairs) != 480 or pairs.groupby(["sequence", "method"]).size().nunique() != 1:
        raise RuntimeError("LSC pair population is incomplete")
    keys = ["sequence", "start_frame_index", "end_frame_index"]
    paired = pairs.loc[pairs["method"] == "V42 E120"].merge(
        pairs.loc[pairs["method"] == "R109 E48"],
        on=keys,
        suffixes=("_v42", "_r109"),
        validate="one_to_one",
    )
    if len(paired) != 120:
        raise RuntimeError("V42/R109 LSC join is incomplete")

    rng = np.random.default_rng(111)
    repetitions = 10_000
    result = np.empty((repetitions, 4), dtype=float)
    groups = [group for _, group in paired.groupby("sequence", sort=False)]
    for index in range(repetitions):
        sampled = [group.iloc[rng.integers(0, len(group), len(group))] for group in groups]
        v42_sd = np.mean([group["measured_step_um_v42"].std(ddof=1) * 1000.0 for group in sampled])
        r109_sd = np.mean([group["measured_step_um_r109"].std(ddof=1) * 1000.0 for group in sampled])
        v42_mae = np.concatenate([group["nominal_abs_error_nm_v42"].to_numpy() for group in sampled])
        r109_mae = np.concatenate([group["nominal_abs_error_nm_r109"].to_numpy() for group in sampled])
        v42_within = np.concatenate([group["within_grid_sd_nm_v42"].to_numpy() for group in sampled])
        r109_within = np.concatenate([group["within_grid_sd_nm_r109"].to_numpy() for group in sampled])
        v42_cross = np.concatenate([group["cross_axis_abs_nm_v42"].to_numpy() for group in sampled])
        r109_cross = np.concatenate([group["cross_axis_abs_nm_r109"].to_numpy() for group in sampled])
        result[index] = [
            r109_sd - v42_sd,
            float(np.mean(r109_mae) - np.mean(v42_mae)),
            float(np.median(r109_within) - np.median(v42_within)),
            float(np.median(r109_cross) - np.median(v42_cross)),
        ]

    observed = {
        "step_sd_nm": summary["r109"]["step_sd_nm"] - summary["v42"]["step_sd_nm"],
        "nominal_mae_nm": summary["r109"]["mean_nominal_abs_error_nm"] - summary["v42"]["mean_nominal_abs_error_nm"],
        "within_grid_median_nm": summary["r109"]["median_within_grid_sd_nm"] - summary["v42"]["median_within_grid_sd_nm"],
        "cross_axis_median_nm": summary["r109"]["median_cross_axis_abs_nm"] - summary["v42"]["median_cross_axis_abs_nm"],
    }
    names = list(observed)
    uncertainty = {
        name: {
            "observed_r109_minus_v42": float(observed[name]),
            "ci95": np.percentile(result[:, column], [2.5, 97.5]).tolist(),
            "fraction_r109_worse": float(np.mean(result[:, column] > 0)),
        }
        for column, name in enumerate(names)
    }
    all_cross_zero = all(item["ci95"][0] <= 0.0 <= item["ci95"][1] for item in uncertainty.values())
    summary["uncertainty"] = {
        "method": "paired sequence-stratified bootstrap",
        "repetitions": repetitions,
        "seed": 111,
        "metrics": uncertainty,
    }
    summary["assessment"] = {
        "result": "V42 E120 and R109 E48 are equivalent under the current-top30 LSC readout",
        "all_primary_difference_intervals_include_zero": all_cross_zero,
        "reason": "The observed differences are small and every paired uncertainty interval crosses zero.",
    }
    summary["validated_local"] = datetime.now().astimezone().isoformat()
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    validation = {
        "status": "pass" if all_cross_zero and summary["determinism_spot_check_max_px"] == 0.0 else "fail",
        "rows": len(pairs),
        "paired_rows": len(paired),
        "methods": expected_methods,
        "determinism_spot_check_max_px": summary["determinism_spot_check_max_px"],
        "all_uncertainty_intervals_include_zero": all_cross_zero,
    }
    (OUTPUT / "lsc_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "validation": validation}, ensure_ascii=False, indent=2))
    return 0 if validation["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
