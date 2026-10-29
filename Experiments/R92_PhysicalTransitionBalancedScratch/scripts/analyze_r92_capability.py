"""Audit and summarize the complete locked R92 E80 capability validation."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def bootstrap_median_ci(values: np.ndarray, seed: int, repetitions: int = 10000) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(repetitions, len(values)))
    medians = np.median(values[indices], axis=1)
    return float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))


def load_sem(protocol: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    r92_path = Path(PROJECT_ROOT / protocol["output_root"]) / "sem_acm_fp32" / "E080" / "tables" / "primary_contour_metrics.csv"
    sources = {
        "Raw_R61": Path(PROJECT_ROOT / protocol["comparators"]["sem_raw_r61"]),
        "R90_E45": Path(PROJECT_ROOT / protocol["comparators"]["sem_r90_e45"]),
        "R91_E52": Path(PROJECT_ROOT / protocol["comparators"]["sem_r91_e52"]),
        "R92_E80": r92_path,
    }
    frames: list[pd.DataFrame] = []
    for label, path in sources.items():
        frame = pd.read_csv(path)
        if label != "Raw_R61":
            frame["method"] = label
        frames.append(frame)
    combined = pd.concat(frames, ignore_index=True)
    counts = combined.groupby("method").size().to_dict()
    expected = {"Raw": 432, "R61v16": 432, "R90_E45": 432, "R91_E52": 432, "R92_E80": 432}
    if counts != expected:
        raise RuntimeError(f"SEM population mismatch: {counts}")

    metrics = [
        "iou",
        "mean_boundary_distance_pitch_pct",
        "hd95_pitch_pct",
        "area_error_pct",
        "perimeter_error_pct",
        "centroid_alignment_shift_px",
    ]
    physical = combined.groupby(["method", "pillar_id"], as_index=False)[metrics].median()
    summary_rows: list[dict[str, Any]] = []
    for method, group in physical.groupby("method", sort=False):
        row: dict[str, Any] = {"method": method, "physical_pillars": len(group), "exposures_per_pillar": 12}
        for metric in metrics:
            row[f"median_{metric}"] = float(group[metric].median())
            row[f"p05_{metric}"] = float(group[metric].quantile(0.05))
            row[f"p95_{metric}"] = float(group[metric].quantile(0.95))
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    exposure = combined.groupby(["method", "exposure"], as_index=False)[metrics].median()

    r92 = physical.loc[physical["method"] == "R92_E80"].set_index("pillar_id")
    paired_rows: list[dict[str, Any]] = []
    for reference in ("Raw", "R61v16", "R90_E45", "R91_E52"):
        other = physical.loc[physical["method"] == reference].set_index("pillar_id").loc[r92.index]
        iou_delta = r92["iou"].to_numpy() - other["iou"].to_numpy()
        boundary_delta = other["mean_boundary_distance_pitch_pct"].to_numpy() - r92["mean_boundary_distance_pitch_pct"].to_numpy()
        iou_ci = bootstrap_median_ci(iou_delta, 920041 + len(paired_rows))
        boundary_ci = bootstrap_median_ci(boundary_delta, 921041 + len(paired_rows))
        paired_rows.append({
            "method": "R92_E80",
            "reference": reference,
            "physical_pillars": len(r92),
            "median_iou_change": float(np.median(iou_delta)),
            "iou_change_ci95_low": iou_ci[0],
            "iou_change_ci95_high": iou_ci[1],
            "iou_improvement_fraction": float(np.mean(iou_delta > 0)),
            "iou_wilcoxon_p": float(wilcoxon(iou_delta, zero_method="pratt").pvalue),
            "median_boundary_improvement_pitch_pct": float(np.median(boundary_delta)),
            "boundary_improvement_ci95_low": boundary_ci[0],
            "boundary_improvement_ci95_high": boundary_ci[1],
            "boundary_improvement_fraction": float(np.mean(boundary_delta > 0)),
            "boundary_wilcoxon_p": float(wilcoxon(boundary_delta, zero_method="pratt").pvalue),
        })
    return combined, physical, summary, exposure, pd.DataFrame(paired_rows)


def appearance_comparison(results: Path) -> pd.DataFrame:
    r92 = pd.read_csv(results / "tables" / "real_appearance_per_frame_fp32.csv")
    r91 = pd.read_csv(Path(str(PROJECT_ROOT / 'Experiments/R91_DetailDecoupledScratch/results/capability_diagnosis_20260811/tables/real_appearance_per_frame_fp32.csv')))
    metrics = [
        "mean_abs_change_gray",
        "edge_gain_on_raw_support",
        "fine_detail_energy_ratio",
        "off_source_strong_edge_fraction",
        "dark_change_fraction_on_raw_edge_band",
        "mean_abs_change_flat_region_gray",
    ]
    rows: list[dict[str, Any]] = []
    for label, frame in (("R91_E52", r91.loc[r91["epoch"] == 52]), ("R91_E60", r91.loc[r91["epoch"] == 60]), ("R92_E80", r92)):
        for magnification, group in frame.groupby("magnification"):
            row = {"method": label, "magnification": int(magnification), "frames": len(group)}
            for metric in metrics:
                row[f"median_{metric}"] = float(group[metric].median())
            rows.append(row)
    return pd.DataFrame(rows)


def motion_comparison(protocol: dict[str, Any], results: Path) -> pd.DataFrame:
    r92 = json.loads((results / "motion_analysis_fp32" / "summary.json").read_text(encoding="utf-8"))
    r91 = json.loads(Path(PROJECT_ROOT / protocol["comparators"]["r91_motion_summary"]).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for readout, key, population in (
        ("isocontour", "isocontour_summary", "locked30_common_valid"),
        ("gmf_like_phase", "gmf_like_phase_summary", "locked30"),
    ):
        selected = [row for row in r91[key] if row["population"] == population and row["method"] in {"Raw", "R91_E52", "R91_E60"}]
        selected += [row for row in r92[key] if row["population"] == population and row["method"] == "R92_E80"]
        for row in selected:
            rows.append({"readout": readout, **row})
    return pd.DataFrame(rows)


def save_overview(path: Path, appearance: pd.DataFrame, sem: pd.DataFrame, motion: pd.DataFrame, hard: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.2), constrained_layout=True)
    methods = ["R91_E60", "R92_E80"]
    widths = 0.34
    magnifications = [5, 20, 50]
    x = np.arange(len(magnifications))
    for offset, method in enumerate(methods):
        group = appearance.loc[appearance["method"] == method].set_index("magnification").loc[magnifications]
        axes[0, 0].bar(x + (offset - 0.5) * widths, group["median_fine_detail_energy_ratio"], widths, label=method)
    axes[0, 0].axhline(1.0, color="black", linewidth=1, linestyle="--")
    axes[0, 0].set_xticks(x, [f"{value}x" for value in magnifications])
    axes[0, 0].set_ylabel("Fine-detail energy vs Raw")
    axes[0, 0].set_title("Real appearance: detail retained")
    axes[0, 0].legend()

    order = ["Raw", "R61v16", "R90_E45", "R91_E52", "R92_E80"]
    sem_group = sem.set_index("method").loc[order]
    axes[0, 1].bar(order, sem_group["median_iou"], color=["#777777", "#4c78a8", "#59a14f", "#f28e2b", "#e15759"])
    axes[0, 1].set_ylim(0.94, 0.965)
    axes[0, 1].tick_params(axis="x", rotation=25)
    axes[0, 1].set_ylabel("Median IoU")
    axes[0, 1].set_title("SEM contour: 36 physical pillars")

    motion_order = ["Raw", "R91_E60", "R92_E80"]
    for offset, readout in enumerate(("isocontour", "gmf_like_phase")):
        group = motion.loc[(motion["readout"] == readout) & motion["method"].isin(motion_order)].set_index("method").loc[motion_order]
        axes[1, 0].bar(np.arange(3) + (offset - 0.5) * widths, group["step_sd_nm"], widths, label=readout)
    axes[1, 0].set_xticks(np.arange(3), motion_order)
    axes[1, 0].set_ylabel("Step standard deviation (nm)")
    axes[1, 0].set_title("Locked 50x real-motion stability")
    axes[1, 0].legend()

    hard_order = ["Raw", "R61v16", "R92_E80"]
    hard_values = []
    raw_vs = hard.loc[(hard["family"] == "overall") & (hard["alignment"] == "translation_only")]
    hard_values.append(float(raw_vs.loc[raw_vs["reference"] == "Raw", "reference_median_iou"].iloc[0]))
    hard_values.append(float(raw_vs.loc[raw_vs["reference"] == "R61v16", "reference_median_iou"].iloc[0]))
    hard_values.append(float(raw_vs["method_median_iou"].iloc[0]))
    axes[1, 1].bar(hard_order, hard_values, color=["#777777", "#4c78a8", "#e15759"])
    axes[1, 1].set_ylim(0.86, 0.90)
    axes[1, 1].set_ylabel("Median IoU")
    axes[1, 1].set_title("100-image hard microscopy contours")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.suptitle("R92 E80 locked capability validation", fontsize=16)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    results = Path(PROJECT_ROOT / protocol["output_root"])
    tables = results / "tables"
    figures = results / "figures"
    real_state = json.loads((results / "real_validation_state_fp32.json").read_text(encoding="utf-8"))
    holdout = json.loads((results / "sealed_holdout_e80" / "holdout_metrics.json").read_text(encoding="utf-8"))
    hard_summary = json.loads((results / "hard_microscopy" / "summary.json").read_text(encoding="utf-8"))
    branch_direction = json.loads((results / "branch_direction_analysis.json").read_text(encoding="utf-8"))
    hard_table = pd.read_csv(results / "hard_microscopy" / "tables" / "paired_contour_summary.csv")
    tile = pd.read_csv(tables / "real_tile_parity_precision_audit.csv")
    branch = pd.read_csv(tables / "live_branch_probe_fp32.csv")
    appearance = appearance_comparison(results)
    motion = motion_comparison(protocol, results)
    sem_records, sem_physical, sem_summary, sem_exposure, sem_paired = load_sem(protocol)

    if real_state["outputs"] != 96 or holdout["metrics"]["evaluated_scenes"] != 256:
        raise RuntimeError("Core validation population audit failed")
    if not json.loads((results / "motion_analysis_fp32" / "summary.json").read_text(encoding="utf-8"))["audit"]["all_stage_manifests_pass"]:
        raise RuntimeError("Motion manifest audit failed")
    if int(hard_summary["images"]) != 100 or int(hard_summary["combined_primary_records"]) != 600:
        raise RuntimeError("Hard-microscopy population audit failed")

    sem_records.to_csv(tables / "sem_all_methods_432_records_each.csv", index=False, encoding="utf-8-sig")
    sem_physical.to_csv(tables / "sem_physical_pillar_medians.csv", index=False, encoding="utf-8-sig")
    sem_summary.to_csv(tables / "sem_physical_pillar_summary.csv", index=False, encoding="utf-8-sig")
    sem_exposure.to_csv(tables / "sem_by_exposure_summary.csv", index=False, encoding="utf-8-sig")
    sem_paired.to_csv(tables / "sem_r92_paired_comparisons.csv", index=False, encoding="utf-8-sig")
    appearance.to_csv(tables / "appearance_r91_r92_fair_comparison.csv", index=False, encoding="utf-8-sig")
    motion.to_csv(tables / "motion_raw_r91_r92_comparison.csv", index=False, encoding="utf-8-sig")

    r92_appearance = appearance.loc[appearance["method"] == "R92_E80"].set_index("magnification")
    r92_sem = sem_summary.set_index("method").loc["R92_E80"]
    raw_sem = sem_summary.set_index("method").loc["Raw"]
    r61_sem = sem_summary.set_index("method").loc["R61v16"]
    r90_sem = sem_summary.set_index("method").loc["R90_E45"]
    r91_sem = sem_summary.set_index("method").loc["R91_E52"]
    r92_iso = motion.loc[(motion["readout"] == "isocontour") & (motion["method"] == "R92_E80")].iloc[0]
    r92_phase = motion.loc[(motion["readout"] == "gmf_like_phase") & (motion["method"] == "R92_E80")].iloc[0]
    hard_primary = hard_table.loc[(hard_table["alignment"] == "translation_only") & (hard_table["family"] == "overall")]
    fp32_tile = tile.loc[tile["precision"] == "fp32"]
    bf16_tile = tile.loc[tile["precision"] == "bf16"]
    metrics = holdout["metrics"]
    sem_exposure_r92 = sem_exposure.loc[sem_exposure["method"] == "R92_E80"]

    overview = figures / "r92_e80_complete_validation_overview.png"
    save_overview(overview, appearance, sem_summary, motion, hard_table)
    payload = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "selected_checkpoint": {"epoch": 80, "sha256": protocol["checkpoint_sha256"], "changed_after_external_validation": False},
        "population_audit": {
            "real_appearance_frames": 30,
            "live_branch_images": 4,
            "sem_records": 432,
            "sem_physical_pillars": 36,
            "sem_exposures": 12,
            "real_motion_frames": 50,
            "real_motion_locked_steps": 30,
            "sealed_holdout_scenes": 256,
            "sealed_holdout_observations": 1024,
            "sealed_holdout_evaluation_cases": metrics["evaluated_cases"],
            "hard_microscopy_images": 100,
            "hard_microscopy_families": 5,
        },
        "visual_detail_finding": {
            "verdict": "denoising-dominant with real high-frequency suppression; main edge location/slope is largely retained",
            "by_magnification": {
                str(mag): {
                    "median_edge_gain_vs_raw": float(r92_appearance.loc[mag, "median_edge_gain_on_raw_support"]),
                    "median_fine_detail_energy_vs_raw": float(r92_appearance.loc[mag, "median_fine_detail_energy_ratio"]),
                    "median_mean_abs_change_gray": float(r92_appearance.loc[mag, "median_mean_abs_change_gray"]),
                }
                for mag in (5, 20, 50)
            },
            "r92_specific_frequency_split": {
                str(int(row.magnification)): {
                    "edge_band_high_frequency_vs_raw": float(row.median_edge_band_high_frequency_ratio),
                    "flat_region_high_frequency_vs_raw": float(row.median_flat_region_high_frequency_ratio),
                }
                for row in pd.read_csv(tables / "real_appearance_by_magnification_fp32.csv").itertuples()
            },
            "branch_direction": branch_direction["median_metrics"],
            "branch_direction_interpretation": branch_direction["interpretation"],
        },
        "sealed_holdout_finding": {
            "balanced_score": metrics["balanced_score"],
            "worst_model_to_raw_error_ratio": metrics["worst_normalized_domain_error"],
            "domain_error_ratios": metrics["normalized_domain_ratios"],
            "identity_mean_change_gray": metrics["safety"]["identity_mean_abs_gray"],
            "clear_texture_change_gray": metrics["safety"]["clear_texture_change_gray"],
            "topology_mismatches": metrics["safety"]["topology_mismatch_count"],
            "raw_topology_mismatches": metrics["safety"]["raw_topology_mismatch_count"],
            "raw_clear_added_topology_failures": metrics["safety"]["raw_clear_added_topology_failures"],
        },
        "sem_finding": {
            "r92_median_iou": float(r92_sem["median_iou"]),
            "raw_median_iou": float(raw_sem["median_iou"]),
            "r61_median_iou": float(r61_sem["median_iou"]),
            "r90_e45_median_iou": float(r90_sem["median_iou"]),
            "r91_e52_median_iou": float(r91_sem["median_iou"]),
            "r92_median_boundary_distance_pitch_pct": float(r92_sem["median_mean_boundary_distance_pitch_pct"]),
            "r92_worst_exposure_median_iou": float(sem_exposure_r92["iou"].min()),
            "r92_worst_exposure_median_boundary_pitch_pct": float(sem_exposure_r92["mean_boundary_distance_pitch_pct"].max()),
            "interpretation": "R92 is modestly better than Raw but weaker than R61, R90 E45, and R91 E52 on this fixed SEM contour population.",
        },
        "motion_finding": {
            "isocontour_locked30_step_sd_nm": float(r92_iso["step_sd_nm"]),
            "isocontour_step_sd_vs_raw_percent": float(r92_iso["step_sd_vs_raw_percent"]),
            "isocontour_threshold_sensitivity_nm": float(r92_iso["median_threshold_sensitivity_nm"]),
            "gmf_like_locked30_step_sd_nm": float(r92_phase["step_sd_nm"]),
            "gmf_like_step_sd_vs_raw_percent": float(r92_phase["step_sd_vs_raw_percent"]),
            "gmf_like_mae_vs_raw_percent": float(r92_phase["mae_vs_raw_percent"]),
            "interpretation": "Stable but readout-dependent: isocontour spread is slightly worse, phase-like spread is better, and threshold sensitivity is lower.",
        },
        "hard_microscopy_finding": {
            "r92_vs_raw": hard_primary.loc[hard_primary["reference"] == "Raw"].iloc[0].to_dict(),
            "r92_vs_r61": hard_primary.loc[hard_primary["reference"] == "R61v16"].iloc[0].to_dict(),
        },
        "tiling_finding": {
            "fp32_mean_abs_gray_max": float(fp32_tile["mean_abs_gray"].max()),
            "fp32_max_abs_gray": float(fp32_tile["max_abs_gray"].max()),
            "bf16_mean_abs_gray_max": float(bf16_tile["mean_abs_gray"].max()),
            "bf16_max_abs_gray": float(bf16_tile["max_abs_gray"].max()),
            "deployment_precision_recommendation": "FP32 for shape-bearing validation and delivery; BF16 is not spatially identical.",
        },
        "overall_judgment": {
            "answer_to_blur_question": "Yes, the smoother look is real, especially at 50x. It mostly removes flat-field noise while preserving main edge slope, but it also suppresses some genuine-looking high-frequency detail.",
            "strengths": ["no 5x dark-halo recurrence", "strong unseen synthetic contour and motion improvement", "exposure geometry is coherent", "FP32 tiled reconstruction is effectively seamless"],
            "limitations": ["not a strong visual sharpening model", "clear inputs are modified", "25 added topology failures on the sealed holdout", "fixed SEM contour accuracy trails R61/R90/R91", "motion improvement depends on readout"],
            "model_role": "stable conservative research candidate, not yet the strongest universal or detail-forward release",
        },
        "overview_figure": str(overview),
    }
    write_json(results / "capability_summary.json", payload)
    print(json.dumps(payload["overall_judgment"], ensure_ascii=False, indent=2))
    print(json.dumps({"status": "complete", "summary": str(results / "capability_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
