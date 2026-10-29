"""Combine R92 hard-microscopy ACM output with the frozen Raw/R61 comparison."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"
R74_TABLES = Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/results/tables'))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, repetitions: int = 10000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    indices = rng.integers(0, len(values), size=(repetitions, len(values)))
    medians = np.median(values[indices], axis=1)
    return float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))


def paired_summary(method_rows: pd.DataFrame, reference_rows: pd.DataFrame, method: str, reference: str, family: str, alignment: str, rng: np.random.Generator) -> dict[str, Any]:
    keys = ["image_id", "family", "alignment"]
    merged = method_rows.merge(reference_rows, on=keys, suffixes=("_method", "_reference"), validate="one_to_one")
    iou_delta = merged["iou_method"].to_numpy(float) - merged["iou_reference"].to_numpy(float)
    boundary_delta = merged["mean_boundary_distance_px_reference"].to_numpy(float) - merged["mean_boundary_distance_px_method"].to_numpy(float)
    iou_ci = bootstrap_ci(iou_delta, rng)
    boundary_ci = bootstrap_ci(boundary_delta, rng)

    def safe_wilcoxon(values: np.ndarray) -> float:
        if np.allclose(values, 0):
            return 1.0
        return float(wilcoxon(values, alternative="two-sided", zero_method="pratt").pvalue)

    return {
        "method": method,
        "reference": reference,
        "alignment": alignment,
        "family": family,
        "images": int(len(merged)),
        "method_median_iou": float(merged["iou_method"].median()),
        "reference_median_iou": float(merged["iou_reference"].median()),
        "median_iou_change": float(np.median(iou_delta)),
        "iou_change_ci95_low": iou_ci[0],
        "iou_change_ci95_high": iou_ci[1],
        "iou_improvement_fraction": float(np.mean(iou_delta > 0)),
        "iou_wilcoxon_p": safe_wilcoxon(iou_delta),
        "method_median_boundary_distance_px": float(merged["mean_boundary_distance_px_method"].median()),
        "reference_median_boundary_distance_px": float(merged["mean_boundary_distance_px_reference"].median()),
        "median_boundary_improvement_px": float(np.median(boundary_delta)),
        "boundary_improvement_ci95_low": boundary_ci[0],
        "boundary_improvement_ci95_high": boundary_ci[1],
        "boundary_improvement_fraction": float(np.mean(boundary_delta > 0)),
        "boundary_wilcoxon_p": safe_wilcoxon(boundary_delta),
    }


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    root = Path(PROJECT_ROOT / protocol["output_root"]) / "hard_microscopy"
    runner_tables = root / "matlab_runner" / "results" / "tables"
    output_tables = root / "tables"
    output_tables.mkdir(parents=True, exist_ok=True)
    new_primary = pd.read_csv(runner_tables / "primary_contour_metrics.csv")
    new_primary["method"] = new_primary["method"].replace({"R61v16": "R92_E80"})
    new_sensitivity = pd.read_csv(runner_tables / "acm_sensitivity_metrics.csv")
    new_sensitivity["method"] = new_sensitivity["method"].replace({"R61v16": "R92_E80"})
    truth_qa = pd.read_csv(runner_tables / "truth_acm_geometry_qa.csv")
    old_primary = pd.read_csv(R74_TABLES / "primary_contour_metrics.csv")

    metric_columns = ["iou", "dice", "mean_boundary_distance_px", "hd95_px", "area_error_pct", "perimeter_error_pct"]
    raw_new = new_primary.loc[new_primary["method"] == "Raw", ["image_id", "alignment", *metric_columns]]
    raw_old = old_primary.loc[old_primary["method"] == "Raw", ["image_id", "alignment", *metric_columns]]
    raw_check = raw_new.merge(raw_old, on=["image_id", "alignment"], suffixes=("_new", "_old"), validate="one_to_one")
    maximum_raw_difference = max(
        float(np.max(np.abs(raw_check[f"{metric}_new"] - raw_check[f"{metric}_old"])))
        for metric in metric_columns
    )
    if maximum_raw_difference > 1e-9:
        raise RuntimeError(f"Frozen Raw ACM rerun does not match R74: {maximum_raw_difference}")

    combined = pd.concat([
        old_primary,
        new_primary.loc[new_primary["method"] == "R92_E80"],
    ], ignore_index=True)
    if len(combined) != 600:
        raise RuntimeError(f"Combined hard-microscopy record count mismatch: {len(combined)}")
    combined.to_csv(output_tables / "primary_contour_metrics_combined.csv", index=False, encoding="utf-8-sig")
    new_sensitivity.to_csv(output_tables / "r92_acm_sensitivity_metrics.csv", index=False, encoding="utf-8-sig")
    truth_qa.to_csv(output_tables / "truth_acm_geometry_qa.csv", index=False, encoding="utf-8-sig")

    rng = np.random.default_rng(920041)
    summaries: list[dict[str, Any]] = []
    for alignment in sorted(combined["alignment"].unique()):
        aligned = combined.loc[combined["alignment"] == alignment]
        for family in ["overall", *sorted(aligned["family"].unique())]:
            group = aligned if family == "overall" else aligned.loc[aligned["family"] == family]
            for method, reference in (("R92_E80", "Raw"), ("R92_E80", "R61v16")):
                summaries.append(paired_summary(
                    group.loc[group["method"] == method],
                    group.loc[group["method"] == reference],
                    method,
                    reference,
                    family,
                    alignment,
                    rng,
                ))
    summary = pd.DataFrame(summaries)
    summary.to_csv(output_tables / "paired_contour_summary.csv", index=False, encoding="utf-8-sig")

    sensitivity_rows: list[dict[str, Any]] = []
    for (preset, method, alignment), group in new_sensitivity.groupby(["preset", "method", "alignment"], sort=True):
        sensitivity_rows.append({
            "sensitivity_preset": preset,
            "method": method,
            "alignment": alignment,
            "images": len(group),
            "median_iou": float(group["iou"].median()),
            "median_boundary_distance_px": float(group["mean_boundary_distance_px"].median()),
        })
    pd.DataFrame(sensitivity_rows).to_csv(output_tables / "sensitivity_summary.csv", index=False, encoding="utf-8-sig")

    primary = summary.loc[(summary["alignment"] == "translation_only") & (summary["family"] == "overall")]
    payload = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "images": 100,
        "challenge_families": 5,
        "combined_primary_records": len(combined),
        "frozen_raw_rerun_maximum_metric_difference": maximum_raw_difference,
        "primary_translation_only_overall": primary.to_dict(orient="records"),
        "truth_acm_minimum_iou": float(truth_qa["iou"].min()),
        "interpretation": "Exact procedural geometry truth; same frozen MATLAB ACM rule as R74. No model-specific sample selection.",
    }
    write_json(root / "summary.json", payload)
    print(primary.to_string(index=False))
    print(json.dumps({"status": "complete", "output": str(root)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
