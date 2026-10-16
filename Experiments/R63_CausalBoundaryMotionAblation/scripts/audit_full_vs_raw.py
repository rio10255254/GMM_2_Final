"""Provide absolute Raw-versus-full context for the matched R63 control."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
METRIC_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "metrics"
OUTPUT_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "aggregate"
SEEDS = (1261200, 1261217)


def add_record(
    records: list[dict[str, object]],
    *,
    seed: int,
    metric: str,
    stratum: str,
    raw: float,
    full: float,
) -> None:
    improvement = 100.0 * (raw - full) / raw if abs(raw) > 1e-12 else float("nan")
    records.append(
        {
            "seed": seed,
            "metric": metric,
            "stratum": stratum,
            "raw_value": raw,
            "full_value": full,
            "improvement_vs_raw_pct": improvement,
            "not_worse_than_raw_by_15pct": bool(full <= raw * 1.15),
            "improves_raw_by_10pct": bool(improvement >= 10.0),
        }
    )


def static_records(seed: int, records: list[dict[str, object]]) -> None:
    root = METRIC_ROOT / "full_control" / f"seed{seed}" / "static_cd"
    measurements = pd.read_csv(root / "static_cd_per_measurement.csv")
    edges = pd.read_csv(root / "static_edge_guardrails.csv")
    for magnification in ("50x", "20x"):
        values: dict[str, dict[str, float]] = {}
        for method in ("Raw", "Method"):
            subset = measurements.loc[
                measurements["magnification"].eq(magnification)
                & measurements["method"].eq(method)
            ]
            per_pillar_error = subset.groupby("pillar_id")["abs_error_nm"].median()
            per_pillar_bound = subset.groupby("pillar_id")["diameter_um"].agg(
                lambda group: float(group.max() - group.min()) * 1000.0
            )
            edge_subset = edges.loc[
                edges["magnification"].eq(magnification) & edges["method"].eq(method)
            ]
            values[method] = {
                "cd_median_abs_error_nm": float(per_pillar_error.median()),
                "cd_bound_width_nm": float(per_pillar_bound.median()),
                "edge_width_10_90_nm": float(edge_subset["edge_width_10_90_nm"].median()),
                "outer_ringing_energy": float(edge_subset["outer_ringing_energy"].median()),
            }
        for metric in values["Raw"]:
            add_record(
                records,
                seed=seed,
                metric=metric,
                stratum=magnification,
                raw=values["Raw"][metric],
                full=values["Method"][metric],
            )


def displacement_records(seed: int, records: list[dict[str, object]]) -> None:
    path = (
        METRIC_ROOT
        / "full_control"
        / f"seed{seed}"
        / "displacement"
        / "displacement_per_step_top30.csv"
    )
    data = pd.read_csv(path)
    if not data["method_valid"].astype(str).str.lower().isin({"true", "1"}).all():
        raise RuntimeError(f"full_control/seed{seed}: invalid locked displacement step")
    data["raw_step_nm"] = data["raw_boundary_dx_um"].abs() * 1000.0
    data["full_step_nm"] = data["method_boundary_dx_um"].abs() * 1000.0
    data["raw_step_residual_nm"] = data["raw_step_nm"] - data.groupby("sequence")[
        "raw_step_nm"
    ].transform("mean")
    data["full_step_residual_nm"] = data["full_step_nm"] - data.groupby("sequence")[
        "full_step_nm"
    ].transform("mean")
    data["raw_command_error_nm"] = (
        data["raw_step_nm"] - data["nominal_step_um"] * 1000.0
    ).abs()
    data["full_command_error_nm"] = (
        data["full_step_nm"] - data["nominal_step_um"] * 1000.0
    ).abs()

    strata: dict[str, pd.Series] = {
        sequence: data["sequence"].eq(sequence)
        for sequence in data["sequence"].drop_duplicates()
    }
    strata["50x_all"] = data["sequence"].str.startswith("50x")
    strata["20x_all"] = data["sequence"].str.startswith("20x")
    strata["all_sequences"] = pd.Series(True, index=data.index)
    for stratum, mask in strata.items():
        subset = data.loc[mask]
        metrics = {
            "displacement_step_magnitude_nm": (
                float(subset["raw_step_residual_nm"].std(ddof=1)),
                float(subset["full_step_residual_nm"].std(ddof=1)),
            ),
            "displacement_within_grid_nm": (
                float(subset["raw_within_grid_nm"].mean()),
                float(subset["method_within_grid_nm"].mean()),
            ),
            "displacement_command_abs_error_nm": (
                float(subset["raw_command_error_nm"].mean()),
                float(subset["full_command_error_nm"].mean()),
            ),
        }
        for metric, (raw, full) in metrics.items():
            add_record(
                records,
                seed=seed,
                metric=metric,
                stratum=stratum,
                raw=raw,
                full=full,
            )


def main() -> None:
    records: list[dict[str, object]] = []
    for seed in SEEDS:
        static_records(seed, records)
        displacement_records(seed, records)
    table = pd.DataFrame(records)
    if not np.isfinite(
        table[["raw_value", "full_value", "improvement_vs_raw_pct"]].to_numpy(float)
    ).all():
        raise RuntimeError("Raw-versus-full audit contains non-finite values")
    grouped = []
    for (metric, stratum), group in table.groupby(["metric", "stratum"], sort=False):
        grouped.append(
            {
                "metric": metric,
                "stratum": stratum,
                "mean_improvement_vs_raw_pct": float(group["improvement_vs_raw_pct"].mean()),
                "both_seeds_not_worse_than_raw_by_15pct": bool(
                    group["not_worse_than_raw_by_15pct"].all()
                ),
                "both_seeds_improve_raw_by_10pct": bool(group["improves_raw_by_10pct"].all()),
            }
        )
    summary = pd.DataFrame(grouped)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT_ROOT / "full_vs_raw_context.csv", index=False, float_format="%.12g")
    summary.to_csv(
        OUTPUT_ROOT / "full_vs_raw_context_summary.csv", index=False, float_format="%.12g"
    )
    payload = {
        "all_primary_values_finite": True,
        "comparison": "full_control versus the identical locked Raw evaluation units",
        "step_stability_definition": "within-sequence mean-centered absolute step SD",
        "records": summary.to_dict("records"),
    }
    (OUTPUT_ROOT / "full_vs_raw_context.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
