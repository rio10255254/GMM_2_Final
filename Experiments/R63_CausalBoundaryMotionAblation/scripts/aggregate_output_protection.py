"""Aggregate inference-only output-protection ablations against the full path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "output_protection"
OUTPUT = ROOT / "aggregate"
MODES = ("full", "no_boundary", "no_anchor", "no_gate", "no_all")


def aggregate(values: np.ndarray, method: str) -> float:
    if method == "mean":
        return float(np.mean(values))
    if method == "median":
        return float(np.median(values))
    if method == "std":
        return float(np.std(values, ddof=1))
    raise ValueError(method)


def load_units() -> pd.DataFrame:
    records = []
    for mode in MODES:
        root = ROOT / mode / "metrics"
        static_path = root / "static_cd" / "static_cd_per_measurement.csv"
        edge_path = root / "static_cd" / "static_edge_guardrails.csv"
        if static_path.is_file() and edge_path.is_file():
            static = pd.read_csv(static_path)
            static = static.loc[static["method"].eq("Method")]
            for (magnification, pillar), group in static.groupby(["magnification", "pillar_id"]):
                records.append({"metric": "cd_median_abs_error_nm", "stratum": magnification, "mode": mode, "unit": f"P{pillar}", "value": float(group["abs_error_nm"].median()), "aggregate": "median"})
            edge = pd.read_csv(edge_path)
            edge = edge.loc[edge["method"].eq("Method")]
            for row in edge.itertuples(index=False):
                records.append({"metric": "edge_width_10_90_nm", "stratum": row.magnification, "mode": mode, "unit": f"P{row.pillar_id}", "value": float(row.edge_width_10_90_nm), "aggregate": "median"})
                records.append({"metric": "outer_ringing_energy", "stratum": row.magnification, "mode": mode, "unit": f"P{row.pillar_id}", "value": float(row.outer_ringing_energy), "aggregate": "median"})
        synth_path = root / "synthetic_shift" / "synthetic_shift_per_case.csv"
        if synth_path.is_file():
            synth = pd.read_csv(synth_path)
            synth = synth.loc[synth["method"].eq(mode)]
            for (magnitude, pillar), group in synth.groupby(["magnitude_px", "pillar_id"]):
                records.append({"metric": "synthetic_vector_error_px", "stratum": f"{magnitude:g}px", "mode": mode, "unit": f"P{pillar}", "value": float(group["vector_error_px"].median()), "aggregate": "median"})
        displacement_path = root / "displacement" / "displacement_per_step_top30.csv"
        if displacement_path.is_file():
            displacement = pd.read_csv(displacement_path)
            valid = displacement["method_valid"].astype(str).str.lower().isin({"true", "1"})
            if not valid.all():
                raise RuntimeError(f"{mode}: output-protection audit has {(~valid).sum()} invalid locked steps")
            for row in displacement.itertuples(index=False):
                unit = f"F{int(row.end_frame_index):03d}"
                command_error = abs(abs(float(row.method_boundary_dx_um)) - float(row.nominal_step_um)) * 1000.0
                records.append({"metric": "displacement_command_abs_error_nm", "stratum": row.sequence, "mode": mode, "unit": unit, "value": command_error, "aggregate": "mean"})
                records.append({"metric": "displacement_within_grid_nm", "stratum": row.sequence, "mode": mode, "unit": unit, "value": float(row.method_within_grid_nm), "aggregate": "mean"})
                records.append({"metric": "displacement_step_magnitude_nm", "stratum": row.sequence, "mode": mode, "unit": unit, "value": abs(float(row.method_boundary_dx_um)) * 1000.0, "aggregate": "std"})
    return pd.DataFrame(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", type=int, default=4000)
    args = parser.parse_args()
    units = load_units()
    rng = np.random.default_rng(630017)
    summary_rows = []
    effect_rows = []
    for (metric, stratum), group in units.groupby(["metric", "stratum"], sort=False):
        rule = str(group["aggregate"].iloc[0])
        pivot = group.pivot(index="unit", columns="mode", values="value")
        available_modes = [mode for mode in MODES if mode in pivot.columns]
        if "full" not in available_modes:
            continue
        pivot = pivot[available_modes].dropna()
        values = {mode: aggregate(pivot[mode].to_numpy(float), rule) for mode in available_modes}
        for mode, value in values.items():
            summary_rows.append({"metric": metric, "stratum": stratum, "mode": mode, "value": value, "unit_count": len(pivot), "aggregate": rule})
        full = values["full"]
        for mode in [item for item in MODES[1:] if item in values]:
            boots = []
            for _ in range(args.bootstrap):
                sampled = pivot.iloc[rng.integers(0, len(pivot), size=len(pivot))]
                boots.append(aggregate(sampled[mode].to_numpy(float), rule) - aggregate(sampled["full"].to_numpy(float), rule))
            effect = values[mode] - full
            low, high = np.percentile(boots, [2.5, 97.5])
            percent = 100.0 * effect / full if abs(full) > 1e-12 else float("nan")
            effect_rows.append({
                "metric": metric,
                "stratum": stratum,
                "ablation": mode,
                "full_value": full,
                "ablated_value": values[mode],
                "ablation_minus_full": effect,
                "effect_vs_full_pct": percent,
                "bootstrap_ci_low": float(low),
                "bootstrap_ci_high": float(high),
                "material_change": bool(abs(percent) >= 10.0 and (low > 0.0 or high < 0.0)),
            })
    OUTPUT.mkdir(parents=True, exist_ok=True)
    units.to_csv(OUTPUT / "output_protection_units.csv", index=False, float_format="%.12g")
    pd.DataFrame(summary_rows).to_csv(OUTPUT / "output_protection_summary.csv", index=False, float_format="%.12g")
    effects = pd.DataFrame(effect_rows)
    effects.to_csv(OUTPUT / "output_protection_effects.csv", index=False, float_format="%.12g")
    inventory_path = ROOT / "inventory.json"
    invalid_rows = []
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        for record in inventory.get("records", []):
            for metric_name, status in record.get("metric_status", {}).items():
                if status.get("status") != "complete":
                    invalid_rows.append({
                        "mode": record.get("mode"),
                        "metric_group": metric_name,
                        "status": status.get("status"),
                        "reason": status.get("reason", ""),
                        "exit_code": status.get("exit_code"),
                    })
    pd.DataFrame(invalid_rows, columns=["mode", "metric_group", "status", "reason", "exit_code"]).to_csv(
        OUTPUT / "output_protection_invalid.csv", index=False
    )
    print(effects.loc[effects["material_change"]].to_string(index=False))


if __name__ == "__main__":
    main()
