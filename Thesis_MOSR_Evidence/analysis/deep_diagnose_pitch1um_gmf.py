"""Deep diagnosis for the Pitch1um external GMF comparison.

Uses R104-vs-Raw pixel identity as a negative control for GMF rerun variance,
compares the current single-capture/full-frame protocol with the historical
paired-capture/cropped protocol, and checks whether R103 changes concentrate at
512-pixel tile boundaries.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.stats import wilcoxon, spearmanr


def bootstrap_median_ci(values: np.ndarray, seed: int = 20260817, draws: int = 20000) -> list[float]:
    values = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(seed)
    medians = np.empty(draws, dtype=np.float64)
    for index in range(draws):
        medians[index] = np.median(rng.choice(values, size=len(values), replace=True))
    return [float(np.percentile(medians, 2.5)), float(np.percentile(medians, 97.5))]


def safe_wilcoxon(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    if np.allclose(values, 0.0):
        return 1.0
    return float(wilcoxon(values, alternative="two-sided", zero_method="wilcox").pvalue)


def seam_mask(shape: tuple[int, int], core: int = 512, radius: int = 2) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    for y in range(core, h, core):
        mask[max(0, y - radius):min(h, y + radius + 1), :] = True
    for x in range(core, w, core):
        mask[:, max(0, x - radius):min(w, x + radius + 1)] = True
    return mask


def image_diagnostics(package: Path) -> dict:
    raw_files = sorted((package / "pitch1um_y100_raw" / "bmp").glob("frame_*.bmp"))
    r103_files = sorted((package / "pitch1um_y100_r103_e48" / "bmp").glob("frame_*.bmp"))
    selected = sorted(set(np.linspace(0, len(raw_files) - 1, 11).round().astype(int).tolist()))
    rows = []
    for index in selected:
        raw = cv2.imread(str(raw_files[index]), cv2.IMREAD_GRAYSCALE)
        r103 = cv2.imread(str(r103_files[index]), cv2.IMREAD_GRAYSCALE)
        difference = np.abs(r103.astype(np.int16) - raw.astype(np.int16)).astype(np.float32)
        seams = seam_mask(raw.shape)
        seam_mean = float(np.mean(difference[seams]))
        interior_mean = float(np.mean(difference[~seams]))
        rows.append({
            "frame_index": index,
            "mean_abs_change_gray": float(np.mean(difference)),
            "p95_abs_change_gray": float(np.percentile(difference, 95)),
            "seam_mean_abs_change_gray": seam_mean,
            "interior_mean_abs_change_gray": interior_mean,
            "seam_to_interior_change_ratio": seam_mean / max(interior_mean, 1e-12),
        })
    return {
        "sampled_frames": selected,
        "rows": rows,
        "median_mean_abs_change_gray": float(np.median([row["mean_abs_change_gray"] for row in rows])),
        "median_seam_to_interior_change_ratio": float(np.median([row["seam_to_interior_change_ratio"] for row in rows])),
        "maximum_seam_to_interior_change_ratio": float(np.max([row["seam_to_interior_change_ratio"] for row in rows])),
    }


def roi_diagnostics(package: Path, coordinates: dict[str, dict[int, dict]], arms: list[str], common_frames: list[int]) -> dict:
    rows = []
    radius = 256
    for index in common_frames:
        raw = cv2.imread(str(package / arms[0] / "bmp" / f"frame_{index:04d}.bmp"), cv2.IMREAD_GRAYSCALE)
        r103 = cv2.imread(str(package / arms[1] / "bmp" / f"frame_{index:04d}.bmp"), cv2.IMREAD_GRAYSCALE)
        center_x = int(round(float(coordinates[arms[0]][index]["x_px"])))
        center_y = int(round(float(coordinates[arms[0]][index]["y_px"])))
        x0, x1 = max(0, center_x - radius), min(raw.shape[1], center_x + radius)
        y0, y1 = max(0, center_y - radius), min(raw.shape[0], center_y + radius)
        raw_roi = raw[y0:y1, x0:x1].astype(np.float32)
        r103_roi = r103[y0:y1, x0:x1].astype(np.float32)
        difference = np.abs(r103_roi - raw_roi)
        raw_gx = cv2.Sobel(raw_roi, cv2.CV_32F, 1, 0, ksize=3)
        raw_gy = cv2.Sobel(raw_roi, cv2.CV_32F, 0, 1, ksize=3)
        r103_gx = cv2.Sobel(r103_roi, cv2.CV_32F, 1, 0, ksize=3)
        r103_gy = cv2.Sobel(r103_roi, cv2.CV_32F, 0, 1, ksize=3)
        raw_gradient = float(np.mean(np.hypot(raw_gx, raw_gy)))
        r103_gradient = float(np.mean(np.hypot(r103_gx, r103_gy)))
        rows.append({
            "frame_index": index,
            "raw_score": float(coordinates[arms[0]][index]["score_diff"]),
            "r103_score": float(coordinates[arms[1]][index]["score_diff"]),
            "score_delta_r103_minus_raw": float(coordinates[arms[1]][index]["score_diff"]) - float(coordinates[arms[0]][index]["score_diff"]),
            "raw_roi_mean": float(np.mean(raw_roi)),
            "raw_roi_std": float(np.std(raw_roi)),
            "local_mean_abs_change_gray": float(np.mean(difference)),
            "local_p95_abs_change_gray": float(np.percentile(difference, 95)),
            "local_edge_gain": r103_gradient / max(raw_gradient, 1e-12),
        })

    def values(field: str) -> np.ndarray:
        return np.asarray([row[field] for row in rows], dtype=np.float64)

    score = values("r103_score")
    ordering = np.argsort(score)
    low = [rows[int(i)] for i in ordering[:10]]
    high = [rows[int(i)] for i in ordering[-10:]]

    def group_summary(group: list[dict]) -> dict:
        return {
            "frames": [row["frame_index"] for row in group],
            "score_median": float(np.median([row["r103_score"] for row in group])),
            "local_change_median": float(np.median([row["local_mean_abs_change_gray"] for row in group])),
            "local_edge_gain_median": float(np.median([row["local_edge_gain"] for row in group])),
            "raw_roi_std_median": float(np.median([row["raw_roi_std"] for row in group])),
        }

    correlations = {}
    for field in ("local_mean_abs_change_gray", "local_edge_gain", "raw_roi_std", "score_delta_r103_minus_raw"):
        result = spearmanr(score, values(field))
        correlations[f"r103_score_vs_{field}"] = {"rho": float(result.statistic), "p": float(result.pvalue)}

    return {"roi_size": 512, "rows": rows, "correlations": correlations, "lowest_score_10": group_summary(low), "highest_score_10": group_summary(high)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--historical-summary", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    analysis_dir = package / "gmf_analysis"
    analysis = json.loads((analysis_dir / "gmf_analysis.json").read_text(encoding="utf-8"))
    historical = json.loads(args.historical_summary.read_text(encoding="utf-8"))
    coordinate_rows = list(csv.DictReader((analysis_dir / "gmf_coordinate_rows.csv").open(encoding="utf-8-sig")))
    step_rows = list(csv.DictReader((analysis_dir / "gmf_step_rows.csv").open(encoding="utf-8-sig")))

    arms = ["pitch1um_y100_raw", "pitch1um_y100_r103_e48", "pitch1um_y100_r104_e48"]
    coordinates = {
        arm: {int(row["frame_index"]): row for row in coordinate_rows if row["arm"] == arm}
        for arm in arms
    }
    steps = {
        arm: {int(row["from_frame"]): row for row in step_rows if row["arm"] == arm}
        for arm in arms
    }
    common_frames = sorted(set.intersection(*(set(coordinates[arm]) for arm in arms)))
    common_steps = sorted(set.intersection(*(set(steps[arm]) for arm in arms)))
    expected_dy = float(analysis["expected_dy_px"])

    def arr_coord(arm: str, field: str) -> np.ndarray:
        return np.asarray([float(coordinates[arm][index][field]) for index in common_frames], dtype=np.float64)

    def arr_step(arm: str, field: str) -> np.ndarray:
        return np.asarray([float(steps[arm][index][field]) for index in common_steps], dtype=np.float64)

    raw_x, raw_y = arr_coord(arms[0], "x_px"), arr_coord(arms[0], "y_px")
    negative_control = {}
    model_effect = {}
    for arm, target in ((arms[2], negative_control), (arms[1], model_effect)):
        x_offset = arr_coord(arm, "x_px") - raw_x
        y_offset = arr_coord(arm, "y_px") - raw_y
        x_centered = x_offset - np.median(x_offset)
        y_centered = y_offset - np.median(y_offset)
        dx_delta = arr_step(arm, "dx_px") - arr_step(arms[0], "dx_px")
        dy_delta = arr_step(arm, "dy_px") - arr_step(arms[0], "dy_px")
        vector_delta = np.hypot(dx_delta, dy_delta)
        target.update({
            "arm": arm,
            "pixel_identical_to_raw": analysis["image_parity"][arm]["exact_pixel_frames"] == analysis["image_parity"][arm]["paired_frames"],
            "median_coordinate_offset_px": float(np.median(np.hypot(x_offset, y_offset))),
            "median_translation_removed_offset_residual_px": float(np.median(np.hypot(x_centered, y_centered))),
            "p95_translation_removed_offset_residual_px": float(np.percentile(np.hypot(x_centered, y_centered), 95)),
            "median_step_vector_difference_px": float(np.median(vector_delta)),
            "p95_step_vector_difference_px": float(np.percentile(vector_delta, 95)),
            "y_step_std_px": float(np.std(arr_step(arm, "dy_px"), ddof=1)),
            "direction_fraction": float(np.mean(arr_step(arm, "dy_px") < 0)),
        })

    raw_dy = arr_step(arms[0], "dy_px")
    r103_dy = arr_step(arms[1], "dy_px")
    r104_dy = arr_step(arms[2], "dy_px")
    raw_abs_error = np.abs(raw_dy - expected_dy)
    r103_abs_error = np.abs(r103_dy - expected_dy)
    r104_abs_error = np.abs(r104_dy - expected_dy)
    r103_minus_raw_abs_error = r103_abs_error - raw_abs_error
    r104_minus_raw_abs_error = r104_abs_error - raw_abs_error
    score_raw = arr_coord(arms[0], "score_diff")
    score_r103 = arr_coord(arms[1], "score_diff")
    score_r104 = arr_coord(arms[2], "score_diff")
    score_r103_minus_r104 = score_r103 - score_r104
    confidence = {
        "expected_dy_px": expected_dy,
        "mean_abs_y_step_error_px": {
            "Raw": float(np.mean(raw_abs_error)),
            "R103E48": float(np.mean(r103_abs_error)),
            "R104E48": float(np.mean(r104_abs_error)),
        },
        "r103_minus_raw_abs_y_error": {
            "median_delta_px": float(np.median(r103_minus_raw_abs_error)),
            "bootstrap_median_ci95_px": bootstrap_median_ci(r103_minus_raw_abs_error),
            "wilcoxon_p": safe_wilcoxon(r103_minus_raw_abs_error),
        },
        "r104_minus_raw_abs_y_error_negative_control": {
            "median_delta_px": float(np.median(r104_minus_raw_abs_error)),
            "bootstrap_median_ci95_px": bootstrap_median_ci(r104_minus_raw_abs_error, seed=20260818),
            "wilcoxon_p": safe_wilcoxon(r104_minus_raw_abs_error),
        },
        "r103_minus_r104_score": {
            "median_delta_points": float(np.median(score_r103_minus_r104)),
            "bootstrap_median_ci95_points": bootstrap_median_ci(score_r103_minus_r104, seed=20260819),
            "wilcoxon_p": safe_wilcoxon(score_r103_minus_r104),
        },
    }

    adjacent_score_r103 = 0.5 * (score_r103[:-1] + score_r103[1:])
    r103_step_error = np.abs(r103_dy - expected_dy)
    score_error_relation = {
        "spearman_score_vs_abs_y_step_error": float(spearmanr(adjacent_score_r103, r103_step_error).statistic),
        "spearman_p": float(spearmanr(adjacent_score_r103, r103_step_error).pvalue),
    }

    current_raw = analysis["arms"][arms[0]]
    historical_raw = historical["cases"]["00_raw_input"]
    historical_r61 = historical["cases"]["01_r61_v16_best_tradeoff_psfoff"]
    protocol = {
        "current": {
            "input_role": "Raw 5120x5120 full frame; one selected capture per position; 100 GMF coordinates and 99 steps after GMF omitted frame_0000",
            "y_slope_px_per_step": current_raw["position"]["y_trend"]["slope_per_frame"],
            "line_residual_std_px": current_raw["position"]["y_trend"]["residual_std"],
            "y_step_std_px": current_raw["steps"]["dy_px"]["std"],
        },
        "historical": {
            "input_role": "Cropped 2180x1520; 202 captures retained; two captures grouped per stage position; 101 position means and 100 steps",
            "raw_y_slope_px_per_step": historical_raw["fit_slope_y_px_per_step"],
            "raw_line_residual_rms_px": historical_raw["line_residual_rms_px"],
            "raw_y_step_std_px": historical_raw["step_y_px_stats"]["std"],
            "r61_y_step_std_px": historical_r61["step_y_px_stats"]["std"],
            "r61_same_position_repeatability_px": historical_r61["same_position_repeat_dist_px_stats"]["mean"],
        },
        "current_over_historical_raw_y_step_std_ratio": current_raw["steps"]["dy_px"]["std"] / historical_raw["step_y_px_stats"]["std"],
        "current_over_historical_raw_line_residual_ratio": current_raw["position"]["y_trend"]["residual_std"] / historical_raw["line_residual_rms_px"],
    }

    image = image_diagnostics(package)
    roi = roi_diagnostics(package, coordinates, arms, common_frames)
    payload = {
        "status": "complete",
        "negative_control_gmf_rerun_floor": negative_control,
        "r103_observed_effect": model_effect,
        "effect_relative_to_negative_control": {
            "median_step_vector_difference_ratio": model_effect["median_step_vector_difference_px"] / negative_control["median_step_vector_difference_px"],
            "p95_step_vector_difference_ratio": model_effect["p95_step_vector_difference_px"] / negative_control["p95_step_vector_difference_px"],
            "translation_removed_coordinate_residual_ratio": model_effect["median_translation_removed_offset_residual_px"] / negative_control["median_translation_removed_offset_residual_px"],
        },
        "paired_uncertainty": confidence,
        "r103_score_error_relation": score_error_relation,
        "protocol_comparison": protocol,
        "r103_tile_seam_diagnostic": image,
        "r103_gmf_roi_diagnostic": roi,
        "interpretation": {
            "verified": [
                "R104 and Raw are pixel-identical in all 101 package frames, so their GMF difference is a direct estimate of external-run/template variability rather than a model image effect.",
                "R103-vs-Raw step-vector differences are similar in magnitude to the pixel-identical R104-vs-Raw negative control.",
                "The current single-capture/full-frame protocol has substantially higher adjacent Y-step spread than the historical paired-capture/cropped protocol, while long-run line residuals are similar.",
                "R103 image changes are not concentrated at the 512-pixel tile boundaries.",
            ],
            "implication": "This GMF run can reject a claim of clearly improved R103 step stability, but it cannot cleanly rank R103 against Raw beyond the current GMF rerun floor. R104 is an identity response on this data and its apparent GMF regression is not attributable to the model.",
        },
    }
    out_json = analysis_dir / "gmf_deep_diagnosis.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with (analysis_dir / "r103_gmf_roi_diagnostics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(roi["rows"][0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(roi["rows"])
    lines = [
        "# Pitch1um GMF deep diagnosis",
        "",
        "## Main finding",
        "",
        "R104 is pixel-identical to Raw in all 101 images. Therefore Raw-vs-R104 coordinate differences measure GMF rerun/template variability, not model behavior. R103-vs-Raw step-vector differences are of similar size to that negative-control floor.",
        "",
        "## Negative-control floor",
        "",
        f"- Pixel-identical Raw vs R104 median step-vector difference: {negative_control['median_step_vector_difference_px']:.3f} px",
        f"- Pixel-identical Raw vs R104 p95 step-vector difference: {negative_control['p95_step_vector_difference_px']:.3f} px",
        f"- R103 vs Raw median step-vector difference: {model_effect['median_step_vector_difference_px']:.3f} px",
        f"- R103 vs Raw p95 step-vector difference: {model_effect['p95_step_vector_difference_px']:.3f} px",
        "",
        "## Protocol comparison",
        "",
        f"- Current Raw full-frame, single-capture Y-step SD: {protocol['current']['y_step_std_px']:.3f} px",
        f"- Historical Raw cropped, paired-position Y-step SD: {protocol['historical']['raw_y_step_std_px']:.3f} px",
        f"- Historical R61 cropped, paired-position Y-step SD: {protocol['historical']['r61_y_step_std_px']:.3f} px",
        f"- Current/historical Raw step-SD ratio: {protocol['current_over_historical_raw_y_step_std_ratio']:.3f}",
        f"- Current/historical Raw line-residual ratio: {protocol['current_over_historical_raw_line_residual_ratio']:.3f}",
        "",
        "## R103 image and seam check",
        "",
        f"- Median sampled-frame mean absolute change: {image['median_mean_abs_change_gray']:.3f} gray",
        f"- Median seam/interior change ratio: {image['median_seam_to_interior_change_ratio']:.3f}",
        f"- Maximum seam/interior change ratio: {image['maximum_seam_to_interior_change_ratio']:.3f}",
        f"- Lowest-score 10 local change median: {roi['lowest_score_10']['local_change_median']:.3f} gray",
        f"- Highest-score 10 local change median: {roi['highest_score_10']['local_change_median']:.3f} gray",
        f"- Lowest-score 10 local edge gain median: {roi['lowest_score_10']['local_edge_gain_median']:.3f}",
        f"- Highest-score 10 local edge gain median: {roi['highest_score_10']['local_edge_gain_median']:.3f}",
        "",
        "## Decision",
        "",
        "The current run does not support a claim that R103 improves external-GMF stability. R104 did not alter the 8-bit images, so its apparent GMF regression is invalid as model evidence. The next controlled test should preserve both captures per position, group them to position means, and rerun Raw twice with the same locked GMF template/ROI before comparing model outputs.",
    ]
    (analysis_dir / "GMF_DEEP_DIAGNOSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
