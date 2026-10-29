"""Combine R91 trajectory, real appearance, SEM ACM, precision, tile, and motion evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260811.json"
RESULTS = ROOT / "results" / "capability_diagnosis_20260811"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
RAW_ACM = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/results/tables/primary_contour_metrics.csv'))
R90_E45_ACM = Path(str(PROJECT_ROOT / 'Experiments/R90_ExposureCoherentScratch/results/early_stop_validation/sem_acm/E045/tables/primary_contour_metrics.csv'))
BASE_MASK = Path(str(PROJECT_ROOT / 'Experiments/R89_MeasurementNativeScratch/results/final_validation/sem_acm_epoch100/acm_validation/results/masks/acm_primary_masks.mat'))

METRICS = {
    "iou": "higher",
    "mean_boundary_distance_pitch_pct": "lower",
    "area_error_pct": "lower",
    "perimeter_error_pct": "lower",
    "centroid_alignment_shift_px": "lower",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def audit_inputs(protocol: dict[str, Any], stages: list[int]) -> dict[str, Any]:
    manifest = read_json(RESULTS / "fixed_source_manifest_fp32.json")
    if manifest["protocol_id"] != protocol["protocol_id"] or manifest["sealed_holdout_accessed"]:
        raise RuntimeError("Fixed source manifest is not eligible")
    source_rows = manifest["appearance"] + manifest["live_branch_probe"] + manifest["sem"] + manifest["motion"]
    for row in source_rows:
        if sha256_file(Path(row["source"])) != row["sha256"]:
            raise RuntimeError(f"Source changed: {row['source']}")
    inventory = pd.read_csv(TABLES / "reconstruction_inventory_fp32.csv")
    if len(inventory) != 418:
        raise RuntimeError(f"FP32 inventory is incomplete: {len(inventory)}")
    for row in inventory.itertuples(index=False):
        output = Path(row.output)
        if not output.is_file() or sha256_file(output) != row.output_sha256:
            raise RuntimeError(f"Output hash mismatch: {output}")
    expected_keys = {(exposure, pillar) for exposure in range(13, 25) for pillar in range(1, 37)}
    acm_counts: dict[str, int] = {}
    for precision in ("fp32", "bf16"):
        root = RESULTS / ("sem_acm_fp32" if precision == "fp32" else "sem_acm")
        for epoch in stages:
            path = root / f"E{epoch:03d}" / "tables" / "primary_contour_metrics.csv"
            table = pd.read_csv(path)
            observed = set(map(tuple, table[["exposure", "pillar_id"]].astype(int).to_numpy()))
            if len(table) != 432 or table.isna().any().any() or observed != expected_keys:
                raise RuntimeError(f"Incomplete ACM table: {path}")
            acm_counts[f"{precision}_E{epoch}"] = int(len(table))
    motion = read_json(RESULTS / "motion_analysis_fp32" / "summary.json")
    if motion["status"] != "complete" or int(motion["common_valid_locked_steps"]) != 30:
        raise RuntimeError("FP32 motion analysis is incomplete")
    return {
        "status": "pass",
        "source_records_verified": len(source_rows),
        "fp32_reconstruction_outputs_verified": int(len(inventory)),
        "acm_rows": acm_counts,
        "motion_locked_steps": 30,
        "sealed_holdout_accessed": False,
        "all_hashes_verified": True,
    }


def load_sem(stages: list[int], precision: str = "fp32") -> pd.DataFrame:
    raw = pd.read_csv(RAW_ACM)
    raw = raw.loc[raw["method"].isin(["Raw", "R61v16"])].copy()
    r90 = pd.read_csv(R90_E45_ACM)
    r90["method"] = "R90_E45"
    tables = [raw, r90]
    root = RESULTS / ("sem_acm_fp32" if precision == "fp32" else "sem_acm")
    for epoch in stages:
        table = pd.read_csv(root / f"E{epoch:03d}" / "tables" / "primary_contour_metrics.csv")
        table["method"] = f"R91_E{epoch}"
        tables.append(table)
    combined = pd.concat(tables, ignore_index=True)
    combined.to_csv(TABLES / f"sem_acm_all_records_{precision}.csv", index=False, encoding="utf-8-sig")
    return combined


def summarize_sem(combined: pd.DataFrame, stages: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_names = list(METRICS)
    physical = combined.groupby(["pillar_id", "method"], observed=True)[metric_names].median().unstack("method")
    methods = ["Raw", "R61v16", "R90_E45", *[f"R91_E{epoch}" for epoch in stages]]
    rows: list[dict[str, Any]] = []
    for method in methods:
        row: dict[str, Any] = {"method": method, "independent_pillars": 36, "repeated_exposures": 12}
        for metric in metric_names:
            values = physical[(metric, method)].to_numpy(float)
            row[f"median_{metric}"] = float(np.median(values))
            row[f"q1_{metric}"] = float(np.percentile(values, 25))
            row[f"q3_{metric}"] = float(np.percentile(values, 75))
        rows.append(row)
    method_summary = pd.DataFrame(rows)
    method_summary.to_csv(TABLES / "sem_method_summary_fp32.csv", index=False, encoding="utf-8-sig")

    comparisons: list[dict[str, Any]] = []
    for epoch in stages:
        candidate = f"R91_E{epoch}"
        for comparator in ("Raw", "R61v16", "R90_E45"):
            for metric, direction in METRICS.items():
                source = physical[(metric, comparator)].to_numpy(float)
                selected = physical[(metric, candidate)].to_numpy(float)
                improvement = selected - source if direction == "higher" else source - selected
                comparisons.append({
                    "epoch": epoch,
                    "candidate": candidate,
                    "comparator": comparator,
                    "metric": metric,
                    "direction": direction,
                    "median_improvement_positive_is_r91_better": float(np.median(improvement)),
                    "improved_pillars": int(np.count_nonzero(improvement > 1e-9)),
                    "tied_pillars": int(np.count_nonzero(np.abs(improvement) <= 1e-9)),
                    "worsened_pillars": int(np.count_nonzero(improvement < -1e-9)),
                })
    comparison_table = pd.DataFrame(comparisons)
    comparison_table.to_csv(TABLES / "sem_paired_comparisons_fp32.csv", index=False, encoding="utf-8-sig")
    by_exposure = combined.groupby(["exposure", "method"], observed=True)[metric_names].median().reset_index()
    by_exposure.to_csv(TABLES / "sem_by_exposure_fp32.csv", index=False, encoding="utf-8-sig")
    return method_summary, comparison_table, by_exposure


def signed_area_by_exposure(stages: list[int]) -> pd.DataFrame:
    base = loadmat(BASE_MASK, variable_names=["truth_masks", "exposures"])
    truth = np.asarray(base["truth_masks"], dtype=bool)
    truth_area = truth.sum(axis=(0, 1))
    exposures = np.asarray(base["exposures"]).ravel().astype(int)
    rows: list[dict[str, Any]] = []
    for epoch in stages:
        stage = loadmat(
            RESULTS / "sem_acm_fp32" / f"E{epoch:03d}" / "masks" / "stage_primary_masks.mat",
            variable_names=["aligned_masks"],
        )
        masks = np.asarray(stage["aligned_masks"], dtype=bool)
        for exposure_index, exposure in enumerate(exposures):
            areas = masks[:, :, :, exposure_index].sum(axis=(0, 1))
            signed = 100.0 * (areas - truth_area) / truth_area
            for pillar_id, value in enumerate(signed, start=1):
                rows.append({"epoch": epoch, "exposure": int(exposure), "pillar_id": pillar_id, "signed_area_error_pct": float(value)})
    table = pd.DataFrame(rows)
    table.to_csv(TABLES / "sem_signed_area_error_fp32.csv", index=False, encoding="utf-8-sig")
    summary = table.groupby(["epoch", "exposure"], observed=True)["signed_area_error_pct"].median().reset_index()
    summary.to_csv(TABLES / "sem_signed_area_by_exposure_fp32.csv", index=False, encoding="utf-8-sig")
    return summary


def precision_sensitivity(stages: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    image_rows: list[dict[str, Any]] = []
    acm_rows: list[dict[str, Any]] = []
    metric_names = list(METRICS)
    for epoch in stages:
        bf16_dir = RESULTS / "reconstructions" / "sem" / "stage_root" / f"E{epoch:03d}" / "reconstruction"
        fp32_dir = RESULTS / "reconstructions_fp32" / "sem" / "stage_root" / f"E{epoch:03d}" / "reconstruction"
        for exposure in range(13, 25):
            bf16 = read_gray(bf16_dir / f"{exposure}.bmp").astype(np.int16)
            fp32 = read_gray(fp32_dir / f"{exposure}.bmp").astype(np.int16)
            difference = np.abs(bf16 - fp32)
            image_rows.append({
                "epoch": epoch,
                "exposure": exposure,
                "mean_abs_gray": float(difference.mean()),
                "p95_abs_gray": float(np.percentile(difference, 95)),
                "max_abs_gray": int(difference.max()),
                "fraction_pixels_changed": float(np.mean(difference > 0)),
            })
        bf16_acm = pd.read_csv(RESULTS / "sem_acm" / f"E{epoch:03d}" / "tables" / "primary_contour_metrics.csv").sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
        fp32_acm = pd.read_csv(RESULTS / "sem_acm_fp32" / f"E{epoch:03d}" / "tables" / "primary_contour_metrics.csv").sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
        if not bf16_acm[["exposure", "pillar_id"]].equals(fp32_acm[["exposure", "pillar_id"]]):
            raise RuntimeError(f"Precision ACM keys differ at E{epoch}")
        for metric in metric_names:
            delta = bf16_acm[metric].to_numpy(float) - fp32_acm[metric].to_numpy(float)
            acm_rows.append({
                "epoch": epoch,
                "metric": metric,
                "median_bf16_minus_fp32": float(np.median(delta)),
                "median_absolute_difference": float(np.median(np.abs(delta))),
                "p95_absolute_difference": float(np.percentile(np.abs(delta), 95)),
                "maximum_absolute_difference": float(np.max(np.abs(delta))),
                "changed_records": int(np.count_nonzero(np.abs(delta) > 1e-9)),
            })
    images = pd.DataFrame(image_rows)
    acm = pd.DataFrame(acm_rows)
    images.to_csv(TABLES / "precision_image_sensitivity.csv", index=False, encoding="utf-8-sig")
    acm.to_csv(TABLES / "precision_acm_sensitivity.csv", index=False, encoding="utf-8-sig")
    return images, acm


def summarize_branches() -> pd.DataFrame:
    table = pd.read_csv(TABLES / "live_branch_probe_fp32.csv")
    fields = [
        "mean_abs_change_gray",
        "fine_detail_energy_ratio",
        "edge_gain_on_raw_support",
        "low_delta_mean_abs_gray",
        "detail_delta_mean_abs_gray",
        "edge_delta_mean_abs_gray",
        "correction_mean_abs_gray",
        "correction_flat_mean_abs_gray",
        "correction_edge_band_mean_abs_gray",
    ]
    summary = table.groupby("epoch", observed=True)[fields].median().reset_index()
    summary.to_csv(TABLES / "branch_summary_fp32.csv", index=False, encoding="utf-8-sig")
    return summary


def summarize_appearance() -> pd.DataFrame:
    table = pd.read_csv(TABLES / "real_appearance_per_frame_fp32.csv")
    fields = [
        "mean_abs_change_gray",
        "fine_detail_energy_ratio",
        "edge_gain_on_raw_support",
        "off_source_strong_edge_fraction",
        "dark_change_fraction_on_raw_edge_band",
        "mean_abs_change_flat_region_gray",
    ]
    summary = table.groupby(["epoch", "magnification"], observed=True)[fields].median().reset_index()
    summary.to_csv(TABLES / "appearance_by_magnification_fp32.csv", index=False, encoding="utf-8-sig")
    return summary


def save_figures(
    by_exposure: pd.DataFrame,
    area: pd.DataFrame,
    branches: pd.DataFrame,
    stages: list[int],
) -> list[str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), constrained_layout=True)
    methods = ["Raw", "R61v16", "R90_E45", *[f"R91_E{epoch}" for epoch in stages]]
    colors = {"Raw": "#111111", "R61v16": "#6c757d", "R90_E45": "#2a6fbb", "R91_E34": "#50a36d", "R91_E40": "#2f8f83", "R91_E52": "#e28d28", "R91_E60": "#c43d3d"}
    for method in methods:
        rows = by_exposure.loc[by_exposure["method"] == method]
        axes[0].plot(rows["exposure"], rows["iou"], marker="o", markersize=3, label=method, color=colors[method])
        axes[1].plot(rows["exposure"], rows["mean_boundary_distance_pitch_pct"], marker="o", markersize=3, label=method, color=colors[method])
    axes[0].set_title("Fixed SEM ACM overlap")
    axes[0].set_ylabel("IoU (higher is better)")
    axes[1].set_title("Fixed SEM ACM boundary distance")
    axes[1].set_ylabel("% of pitch (lower is better)")
    for axis in axes:
        axis.set_xlabel("Optical exposure")
        axis.set_xticks(range(13, 25))
        axis.axvspan(17.5, 19.5, color="#d62728", alpha=0.07)
        axis.grid(alpha=0.22)
    axes[0].legend(ncol=2, frameon=False, fontsize=8)
    path = FIGURES / "r91_sem_acm_by_exposure_fp32.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    outputs.append(str(path))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), constrained_layout=True)
    for epoch in stages:
        rows = area.loc[area["epoch"] == epoch]
        axes[0].plot(rows["exposure"], rows["signed_area_error_pct"], marker="o", label=f"E{epoch}")
    axes[0].axhline(0, color="black", linewidth=1)
    axes[0].axvspan(17.5, 19.5, color="#d62728", alpha=0.07)
    axes[0].set_title("Signed ACM area error versus SEM shape")
    axes[0].set_xlabel("Optical exposure")
    axes[0].set_ylabel("Median signed area error (%)")
    axes[0].grid(alpha=0.22)
    axes[0].legend(frameon=False)
    axes[1].plot(branches["epoch"], branches["low_delta_mean_abs_gray"], marker="o", label="Broad correction")
    axes[1].plot(branches["epoch"], branches["detail_delta_mean_abs_gray"], marker="o", label="Fine/medium detail")
    axes[1].plot(branches["epoch"], branches["edge_delta_mean_abs_gray"], marker="o", label="Edge correction")
    axes[1].set_title("What produces the visible change")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Median absolute change (gray)")
    axes[1].grid(alpha=0.22)
    axes[1].legend(frameon=False)
    path = FIGURES / "r91_area_and_branch_root_cause.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    outputs.append(str(path))
    return outputs


def main() -> int:
    protocol = read_json(PROTOCOL)
    stages = [int(value) for value in protocol["representative_stages"]["sem_contour"]]
    audit = audit_inputs(protocol, stages)
    combined = load_sem(stages, "fp32")
    method_summary, comparisons, by_exposure = summarize_sem(combined, stages)
    area = signed_area_by_exposure(stages)
    precision_images, precision_acm = precision_sensitivity(stages)
    branches = summarize_branches()
    appearance = summarize_appearance()
    figures = save_figures(by_exposure, area, branches, stages)

    methods = method_summary.set_index("method")
    exposure = by_exposure.set_index(["method", "exposure"])
    branch = branches.set_index("epoch")
    iso = pd.read_csv(RESULTS / "motion_analysis_fp32" / "tables" / "isocontour_summary.csv")
    phase = pd.read_csv(RESULTS / "motion_analysis_fp32" / "tables" / "gmf_like_phase_summary.csv")
    iso_locked = iso.loc[iso["population"] == "locked30_common_valid"].set_index("method")
    phase_locked = phase.loc[phase["population"] == "locked30"].set_index("method")
    best_sem_method = method_summary.loc[method_summary["method"].str.startswith("R91_")].sort_values("median_iou", ascending=False).iloc[0]
    findings = {
        "stored_metric_correction": "The old detail axis is dominated by the clear-input role's near-zero Raw denominator. Degraded textured-general error improves strongly instead of worsening.",
        "best_r91_sem_stage": str(best_sem_method["method"]),
        "best_r91_sem_median_iou": float(best_sem_method["median_iou"]),
        "raw_sem_median_iou": float(methods.loc["Raw", "median_iou"]),
        "r61_sem_median_iou": float(methods.loc["R61v16", "median_iou"]),
        "r90_e45_sem_median_iou": float(methods.loc["R90_E45", "median_iou"]),
        "e52_sem_boundary_pitch_pct": float(methods.loc["R91_E52", "median_mean_boundary_distance_pitch_pct"]),
        "e60_exposure18_iou": float(exposure.loc[("R91_E60", 18), "iou"]),
        "raw_exposure18_iou": float(exposure.loc[("Raw", 18), "iou"]),
        "e60_broad_correction_gray": float(branch.loc[60, "low_delta_mean_abs_gray"]),
        "e60_detail_correction_gray": float(branch.loc[60, "detail_delta_mean_abs_gray"]),
        "e60_edge_correction_gray": float(branch.loc[60, "edge_delta_mean_abs_gray"]),
        "e60_isocontour_step_sd_change_vs_raw_pct": float(iso_locked.loc["R91_E60", "step_sd_vs_raw_percent"]),
        "e60_isocontour_mae_change_vs_raw_pct": float(iso_locked.loc["R91_E60", "mae_vs_raw_percent"]),
        "e60_phase_step_sd_change_vs_raw_pct": float(phase_locked.loc["R91_E60", "step_sd_vs_raw_percent"]),
        "e60_phase_mae_change_vs_raw_pct": float(phase_locked.loc["R91_E60", "mae_vs_raw_percent"]),
        "bf16_vs_fp32_image_mean_abs_gray_max": float(precision_images["mean_abs_gray"].max()),
        "bf16_vs_fp32_acm_iou_p95_abs_max": float(precision_acm.loc[precision_acm["metric"] == "iou", "p95_absolute_difference"].max()),
    }
    payload = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "audit": audit,
        "findings": findings,
        "r92_decision": {
            "keep": [
                "scratch-only independent training",
                "same tile-safe architecture",
                "5000 procedural observations with 8x antialiased labels",
                "physical transition labels instead of a universal midpoint",
                "no source-to-target structural repair",
                "separate degraded-detail and clear-input metrics",
                "balanced exposure updates near 16 percent",
                "fixed detail multiplier instead of the contaminated adaptive controller"
            ],
            "add": [
                "continuous Raw-geometry preservation when an input contour is already accurate",
                "quality-weighted low-branch neutrality on geometry-adequate optical anchors",
                "per-exposure-position worst contour tracking instead of bundle averages alone",
                "FP32 as the primary validation and deployment reference; BF16 only as a sensitivity/speed mode",
                "tile tests across precision, core size, and tile batch while judging seam-level and distribution-level differences"
            ],
            "do_not_add": [
                "hard binary confidence gates",
                "real SEM pixels or real pillar structures in training",
                "a larger architecture or another inherited checkpoint"
            ]
        },
        "outputs": {
            "sem_method_summary": str(TABLES / "sem_method_summary_fp32.csv"),
            "sem_by_exposure": str(TABLES / "sem_by_exposure_fp32.csv"),
            "branch_summary": str(TABLES / "branch_summary_fp32.csv"),
            "appearance_summary": str(TABLES / "appearance_by_magnification_fp32.csv"),
            "precision_sensitivity": str(TABLES / "precision_acm_sensitivity.csv"),
            "figures": figures,
        },
        "claim_limit": protocol["decision_policy"]["claim_limits"],
    }
    (RESULTS / "capability_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
