"""Summarize the frozen-rule SEM/ACM contour validation for R90 E55."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.stats import wilcoxon


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "reports" / "full_validation_epoch055" / "validation_protocol.json"
SEM_ROOT = ROOT / "results" / "full_validation_epoch055" / "sem_acm"
R90_TABLE = SEM_ROOT / "acm_output" / "R90E55" / "tables" / "primary_contour_metrics.csv"
R90_MASK = SEM_ROOT / "acm_output" / "R90E55" / "masks" / "stage_primary_masks.mat"
FULL_ACM_TABLE_ROOT = SEM_ROOT / "sensitivity_full" / "results" / "tables"
BASE_MASK = Path(r"D:\GMM_2_Final\Experiments\R89_MeasurementNativeScratch\results\final_validation\sem_acm_epoch100\acm_validation\results\masks\acm_primary_masks.mat")
R69_TABLE = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\tables\primary_contour_metrics.csv")
R89_TABLE = Path(r"D:\GMM_2_Final\Experiments\R89_MeasurementNativeScratch\results\final_validation\sem_acm_epoch100\acm_validation\results\tables\primary_contour_metrics.csv")
RAW_DIR = ROOT / "results" / "full_validation_epoch055" / "sem_acm" / "locked_optical_inputs"
R61_DIR = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\inference_runs\reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020\r61v16_psfoff_sem_paired_50x")
R89_DIR = Path(r"D:\GMM_2_Final\Experiments\R89_MeasurementNativeScratch\results\final_validation\sem_acm_epoch100\reconstruction")
R90_DIR = SEM_ROOT / "stage_root" / "R90E55" / "reconstruction"
OUTPUT = ROOT / "reports" / "full_validation_epoch055" / "sem_acm"

METRICS = {
    "iou": "higher", "dice": "higher",
    "mean_boundary_distance_pitch_pct": "lower", "hd95_pitch_pct": "lower",
    "area_error_pct": "lower", "perimeter_error_pct": "lower",
    "circularity_abs_error": "lower",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def holm(values: list[float]) -> list[float]:
    array = np.asarray(values, dtype=float)
    order = np.argsort(array)
    adjusted = np.empty_like(array)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(array) - rank) * array[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def load_tables() -> tuple[pd.DataFrame, dict]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    pairing = Path(protocol["sem_acm_arm"]["pairing"])
    if sha256_file(pairing) != protocol["sem_acm_arm"]["pairing_sha256"]:
        raise RuntimeError("Verified SEM pairing changed")
    r69, r89, r90 = pd.read_csv(R69_TABLE), pd.read_csv(R89_TABLE), pd.read_csv(R90_TABLE)
    if len(r69) != 864 or len(r89) != 864 or len(r90) != 432:
        raise RuntimeError("Unexpected ACM table size")
    if any(frame.isna().any().any() for frame in (r69, r89, r90)):
        raise RuntimeError("ACM table contains missing values")
    expected = set((exposure, pillar) for exposure in range(13, 25) for pillar in range(1, 37))
    for label, frame, method in (("Raw", r69, "Raw"), ("R61v16", r69, "R61v16"), ("R89E100", r89, "R89E100"), ("R90E55", r90, "R90E55")):
        selected = frame.loc[frame["method"] == method]
        identities = set(map(tuple, selected[["exposure", "pillar_id"]].astype(int).to_numpy()))
        if len(selected) != 432 or len(identities) != 432 or identities != expected:
            raise RuntimeError(f"{label}: exposure/pillar identities are incomplete")
    raw69 = r69.loc[r69["method"] == "Raw"].reset_index(drop=True)
    raw89 = r89.loc[r89["method"] == "Raw"].reset_index(drop=True)
    columns = list(METRICS) + ["centroid_alignment_shift_px"]
    raw_difference = float(np.max(np.abs(raw69[columns].to_numpy() - raw89[columns].to_numpy())))
    frames = []
    for label, frame, method in (("Raw", r69, "Raw"), ("R61v16", r69, "R61v16"), ("R89E100", r89, "R89E100"), ("R90E55", r90, "R90E55")):
        selected = frame.loc[frame["method"] == method].copy()
        selected["method"] = label
        frames.append(selected)
    audit = {
        "status": "complete", "pairing_sha256_verified": True,
        "physical_pillars": 36, "exposures": 12, "records_per_method": 432,
        "raw_reference_exact_between_r69_and_r89": raw_difference == 0.0,
        "raw_reference_max_absolute_difference": raw_difference,
        "translation_only_alignment": True, "scale_fitting": False, "rotation_fitting": False,
    }
    return pd.concat(frames, ignore_index=True), audit


def analyze(combined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    metrics = list(METRICS)
    physical = combined.groupby(["pillar_id", "method"], observed=True)[metrics].median().unstack("method")
    method_rows = []
    for method in ("Raw", "R61v16", "R89E100", "R90E55"):
        row = {"method": method, "independent_pillars": 36, "repeated_exposures": 12}
        for metric in metrics:
            values = physical[(metric, method)].to_numpy(float)
            row[f"median_{metric}"] = float(np.median(values))
            row[f"q1_{metric}"] = float(np.percentile(values, 25))
            row[f"q3_{metric}"] = float(np.percentile(values, 75))
        method_rows.append(row)
    method_summary = pd.DataFrame(method_rows)

    comparisons = []
    for comparator in ("Raw", "R61v16", "R89E100"):
        pending, p_values = [], []
        for metric, direction in METRICS.items():
            source = physical[(metric, comparator)].to_numpy(float)
            candidate = physical[(metric, "R90E55")].to_numpy(float)
            improvement = candidate - source if direction == "higher" else source - candidate
            try:
                p_value = float(wilcoxon(candidate, source, alternative="two-sided", zero_method="wilcox").pvalue)
            except ValueError:
                p_value = 1.0
            pending.append({
                "comparison": f"R90E55_vs_{comparator}", "comparator": comparator,
                "metric": metric, "direction": direction,
                "comparator_median": float(np.median(source)), "r90_median": float(np.median(candidate)),
                "median_improvement_positive_is_r90_better": float(np.median(improvement)),
                "improved_pillars": int(np.count_nonzero(improvement > 1e-9)),
                "tied_pillars": int(np.count_nonzero(np.abs(improvement) <= 1e-9)),
                "worsened_pillars": int(np.count_nonzero(improvement < -1e-9)),
                "wilcoxon_p_two_sided": p_value,
            })
            p_values.append(p_value)
        for row, adjusted in zip(pending, holm(p_values)):
            row["wilcoxon_p_holm_within_comparison"] = adjusted
            comparisons.append(row)
    comparison_table = pd.DataFrame(comparisons)

    exposure = combined.groupby(["exposure", "method"], observed=True)[metrics].median().reset_index()
    exposure_rows = []
    for exposure_id in range(13, 25):
        raw = exposure.loc[(exposure["exposure"] == exposure_id) & (exposure["method"] == "Raw")].iloc[0]
        r90 = exposure.loc[(exposure["exposure"] == exposure_id) & (exposure["method"] == "R90E55")].iloc[0]
        exposure_rows.append({
            "exposure": exposure_id, "raw_median_iou": float(raw["iou"]), "r90_median_iou": float(r90["iou"]),
            "r90_minus_raw_iou": float(r90["iou"] - raw["iou"]),
            "raw_median_boundary_pitch_pct": float(raw["mean_boundary_distance_pitch_pct"]),
            "r90_median_boundary_pitch_pct": float(r90["mean_boundary_distance_pitch_pct"]),
            "raw_minus_r90_boundary_pitch_pct": float(raw["mean_boundary_distance_pitch_pct"] - r90["mean_boundary_distance_pitch_pct"]),
            "iou_improved": bool(r90["iou"] > raw["iou"]),
            "boundary_improved": bool(r90["mean_boundary_distance_pitch_pct"] < raw["mean_boundary_distance_pitch_pct"]),
        })
    exposure_table = pd.DataFrame(exposure_rows)
    summary = {
        "r90_iou_improved_exposures": int(exposure_table["iou_improved"].sum()),
        "r90_boundary_improved_exposures": int(exposure_table["boundary_improved"].sum()),
        "adequate_exposure_13_to_22_iou_improved": int(exposure_table.loc[exposure_table["exposure"] <= 22, "iou_improved"].sum()),
        "dark_exposure_23_to_24_iou_improved": int(exposure_table.loc[exposure_table["exposure"] >= 23, "iou_improved"].sum()),
    }
    return method_summary, comparison_table, exposure_table, summary


def analyze_sensitivity() -> tuple[pd.DataFrame, dict]:
    sensitivity = pd.read_csv(FULL_ACM_TABLE_ROOT / "acm_sensitivity_metrics.csv")
    if len(sensitivity) != 648 or set(sensitivity["method"]) != {"Raw", "R90E55"}:
        raise RuntimeError("Sensitivity ACM table is incomplete")
    if sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity ACM table contains missing values")
    summary = sensitivity.groupby(["preset", "exposure", "method"], observed=True)[
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    ].median().reset_index()
    rows = []
    for preset in sorted(summary["preset"].unique()):
        for exposure in (13, 18, 24):
            raw = summary.loc[(summary["preset"] == preset) & (summary["exposure"] == exposure) & (summary["method"] == "Raw")].iloc[0]
            r90 = summary.loc[(summary["preset"] == preset) & (summary["exposure"] == exposure) & (summary["method"] == "R90E55")].iloc[0]
            rows.append({
                "preset": preset, "exposure": exposure,
                "raw_median_iou": float(raw["iou"]), "r90_median_iou": float(r90["iou"]),
                "r90_minus_raw_iou": float(r90["iou"] - raw["iou"]),
                "raw_median_boundary_pitch_pct": float(raw["mean_boundary_distance_pitch_pct"]),
                "r90_median_boundary_pitch_pct": float(r90["mean_boundary_distance_pitch_pct"]),
                "raw_minus_r90_boundary_pitch_pct": float(raw["mean_boundary_distance_pitch_pct"] - r90["mean_boundary_distance_pitch_pct"]),
                "iou_improved": bool(r90["iou"] > raw["iou"]),
                "boundary_improved": bool(r90["mean_boundary_distance_pitch_pct"] < raw["mean_boundary_distance_pitch_pct"]),
            })
    table = pd.DataFrame(rows)
    stage_primary = pd.read_csv(R90_TABLE).sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
    full_primary = pd.read_csv(FULL_ACM_TABLE_ROOT / "primary_contour_metrics.csv")
    full_primary = full_primary.loc[full_primary["method"] == "R90E55"].sort_values(["exposure", "pillar_id"]).reset_index(drop=True)
    columns = list(METRICS) + ["centroid_alignment_shift_px"]
    parity = float(np.max(np.abs(stage_primary[columns].to_numpy() - full_primary[columns].to_numpy())))
    audit = {
        "records": 648, "presets": sorted(table["preset"].unique().tolist()),
        "exposures": [13, 18, 24], "primary_parallel_vs_full_max_absolute_difference": parity,
        "primary_reproduction_within_1e_6": bool(parity <= 1e-6),
        "exposure_13_improves_all_presets": bool(table.loc[table["exposure"] == 13, ["iou_improved", "boundary_improved"]].all().all()),
        "exposure_18_worsens_all_presets": bool((~table.loc[table["exposure"] == 18, ["iou_improved", "boundary_improved"]]).all().all()),
        "exposure_24_improves_all_presets": bool(table.loc[table["exposure"] == 24, ["iou_improved", "boundary_improved"]].all().all()),
    }
    return table, audit


def make_overlays() -> list[str]:
    base = loadmat(BASE_MASK)
    stage = loadmat(R90_MASK)
    truth = base["truth_masks"].astype(bool)
    cells = stage["recon_cells"]
    predicted = stage["aligned_masks"].astype(bool)
    outputs = []
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for exposure_index, exposure in ((0, 13), (5, 18), (11, 24)):
        rows = []
        for grid_row in range(6):
            panels = []
            for grid_col in range(6):
                pillar = grid_row * 6 + grid_col
                gray = cells[:, :, pillar, exposure_index]
                rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                truth_edge = cv2.morphologyEx(truth[:, :, pillar].astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
                pred_edge = cv2.morphologyEx(predicted[:, :, pillar, exposure_index].astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
                rgb[truth_edge] = (0, 255, 0)
                rgb[pred_edge] = (0, 0, 255)
                overlap = truth_edge & pred_edge
                rgb[overlap] = (0, 255, 255)
                cv2.putText(rgb, str(pillar + 1), (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
                panels.append(rgb)
            rows.append(np.hstack(panels))
        sheet = np.vstack(rows)
        path = OUTPUT / f"r90_sem_overlay_exposure_{exposure}.png"
        cv2.imwrite(str(path), sheet)
        outputs.append(str(path))
    return outputs


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def make_full_comparisons() -> list[str]:
    outputs = []
    for exposure in (13, 18, 19, 24):
        raw = read_gray(RAW_DIR / f"{exposure}.bmp")
        images = [
            ("RAW", raw),
            ("R61v16", read_gray(R61_DIR / f"{exposure}.bmp")),
            ("R89E100", read_gray(R89_DIR / f"{exposure}.bmp")),
            ("R90E55", read_gray(R90_DIR / f"{exposure}.bmp")),
        ]
        panels = []
        for label, image in images:
            panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            cv2.rectangle(panel, (0, 0), (220, 42), (0, 0, 0), -1)
            cv2.putText(panel, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
            panels.append(panel)
        difference = np.clip(np.abs(images[-1][1].astype(np.int16) - raw.astype(np.int16)) * 4, 0, 255).astype(np.uint8)
        panel = cv2.cvtColor(difference, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (300, 42), (0, 0, 0), -1)
        cv2.putText(panel, "R90 ABS DIFF x4", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        panels.append(panel)
        path = OUTPUT / f"sem_full_comparison_exposure_{exposure}.png"
        cv2.imwrite(str(path), np.hstack(panels))
        outputs.append(str(path))
    return outputs


def main() -> int:
    combined, audit = load_tables()
    method_summary, comparisons, exposure_summary, short = analyze(combined)
    sensitivity_summary, sensitivity_audit = analyze_sensitivity()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    method_summary.to_csv(OUTPUT / "method_summary.csv", index=False, encoding="utf-8-sig")
    comparisons.to_csv(OUTPUT / "r90_paired_comparisons.csv", index=False, encoding="utf-8-sig")
    exposure_summary.to_csv(OUTPUT / "exposure_summary.csv", index=False, encoding="utf-8-sig")
    sensitivity_summary.to_csv(OUTPUT / "sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    overlays = make_overlays()
    full_comparisons = make_full_comparisons()
    summary = {
        "status": "complete", "method": "frozen Chan-Vese ACM with translation-only alignment",
        "audit": audit, "exposure_robustness": short, "overlay_files": overlays,
        "sensitivity_audit": sensitivity_audit,
        "full_comparison_files": full_comparisons,
        "claim_limit": "SEM pairing supports contour comparison for these 36 central physical pillars. It does not establish performance on every future sample.",
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
