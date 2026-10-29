"""Image-level and template-location diagnostics for Raw, V42, and R109."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "image_mechanisms"
OUTPUT.mkdir(parents=True, exist_ok=True)

DOWNSAMPLE = 4
ALIGNED_CROP_FULL = 1400
ALIGNED_CROP_SMALL = ALIGNED_CROP_FULL // DOWNSAMPLE
TEMPLATE_SIZE_SMALL = 320
SEARCH_MARGIN_SMALL = 40
EXPECTED_Y_STEP_SMALL = -8.0 / DOWNSAMPLE


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def parse_score(path: Path, arm: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) % 2:
            raise RuntimeError(f"{path}:{line_number} odd field count")
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        match = re.fullmatch(r"frame_(\d{4})\.bmp", values["FileName"])
        if match is None:
            raise RuntimeError(f"{path}:{line_number} bad filename")
        rows.append(
            {
                "arm": arm,
                "frame_name": values["FileName"],
                "frame_index": int(match.group(1)),
                "x_px_external": float(values["PosX"]),
                "y_px_external": float(values["PosY"]),
                "scale_external": float(values["Scale"]),
                "score_external": float(values["Score0"]),
            }
        )
    frame = pd.DataFrame(rows).sort_values("frame_index").reset_index(drop=True)
    if len(frame) != 100 or frame["frame_index"].tolist() != list(range(1, 101)):
        raise RuntimeError(f"{arm} coordinate population mismatch")
    return frame


def normalized_correlation(left: np.ndarray, right: np.ndarray) -> float:
    a = left.astype(np.float64)
    b = right.astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.sum(a * b) / denominator) if denominator > 0 else float("nan")


def subpixel_peak(values: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return float(index)
    left, center, right = (float(values[index - 1]), float(values[index]), float(values[index + 1]))
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return float(index)
    return float(index + np.clip(0.5 * (left - right) / denominator, -1.0, 1.0))


def radial_profile(image: np.ndarray) -> np.ndarray:
    height, width = image.shape
    yy, xx = np.indices(image.shape, dtype=np.float32)
    radius = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (height - 1) / 2.0) ** 2)
    index = np.floor(radius).astype(np.int32)
    max_radius = min(height, width) // 2
    sums = np.bincount(index.ravel(), weights=image.astype(np.float64).ravel(), minlength=max_radius + 1)
    counts = np.bincount(index.ravel(), minlength=max_radius + 1)
    return sums[:max_radius] / np.maximum(counts[:max_radius], 1)


def radial_features(profile: np.ndarray) -> dict[str, float]:
    search = profile[75:170]
    peak_index = int(np.argmax(search)) + 75
    inner_baseline = float(np.median(profile[20:75]))
    outer_baseline = float(np.median(profile[170:174]))
    baseline = 0.5 * (inner_baseline + outer_baseline)
    peak = float(profile[peak_index])
    threshold = baseline + 0.5 * (peak - baseline)
    inner_candidates = np.flatnonzero(profile[:peak_index] <= threshold)
    outer_candidates = np.flatnonzero(profile[peak_index:] <= threshold)
    inner = float(inner_candidates[-1]) if len(inner_candidates) else float("nan")
    outer = float(peak_index + outer_candidates[0]) if len(outer_candidates) else float("nan")
    return {
        "ring_peak_radius_px": float(peak_index * DOWNSAMPLE),
        "ring_halfmax_width_px": float((outer - inner) * DOWNSAMPLE),
        "ring_contrast_gray": peak - baseline,
        "inner_outer_baseline_difference_gray": inner_baseline - outer_baseline,
    }


def load_arm(arm: str, entry: dict[str, str]) -> tuple[pd.DataFrame, list[np.ndarray], list[np.ndarray]]:
    coordinates = parse_score(Path(PROJECT_ROOT / entry["score"]), arm)
    image_dir = Path(PROJECT_ROOT / entry["image_dir"])
    aligned: list[np.ndarray] = []
    small_frames: list[np.ndarray] = []
    feature_rows: list[dict[str, object]] = []
    for row in coordinates.itertuples(index=False):
        image = read_gray(image_dir / row.frame_name)
        small = cv2.resize(image, (image.shape[1] // DOWNSAMPLE, image.shape[0] // DOWNSAMPLE), interpolation=cv2.INTER_AREA)
        center_small = (float(row.x_px_external / DOWNSAMPLE), float(row.y_px_external / DOWNSAMPLE))
        crop = cv2.getRectSubPix(small, (ALIGNED_CROP_SMALL, ALIGNED_CROP_SMALL), center_small)
        profile = radial_profile(crop)
        features = radial_features(profile)
        high = crop.astype(np.float32) - cv2.GaussianBlur(crop.astype(np.float32), (0, 0), 1.5)
        low = cv2.GaussianBlur(crop.astype(np.float32), (0, 0), 20.0)
        feature_rows.append(
            {
                "arm": arm,
                "frame_name": row.frame_name,
                "frame_index": int(row.frame_index),
                "x_px_external": float(row.x_px_external),
                "y_px_external": float(row.y_px_external),
                "scale_external": float(row.scale_external),
                "score_external": float(row.score_external),
                "aligned_crop_mean_gray": float(crop.mean()),
                "aligned_crop_std_gray": float(crop.std(ddof=1)),
                "high_frequency_rms_gray": float(np.sqrt(np.mean(high**2))),
                "low_frequency_std_gray": float(low.std(ddof=1)),
                **features,
            }
        )
        aligned.append(crop)
        small_frames.append(small)
        if len(aligned) % 20 == 0:
            print(json.dumps({"arm": arm, "loaded": len(aligned), "total": 100}), flush=True)

    stack = np.stack(aligned).astype(np.float32)
    template = np.median(stack, axis=0)
    profiles = np.stack([radial_profile(image) for image in aligned])
    table = pd.DataFrame(feature_rows)
    table["ncc_to_arm_median_template"] = [normalized_correlation(image, template) for image in aligned]
    table["mae_to_arm_median_template_gray"] = [float(np.mean(np.abs(image.astype(np.float32) - template))) for image in aligned]
    table["radial_profile_rmse_to_arm_mean"] = np.sqrt(np.mean((profiles - profiles.mean(axis=0, keepdims=True)) ** 2, axis=1))
    return table, aligned, small_frames


def locate_with_fixed_template(frames: list[np.ndarray], first_external: pd.Series) -> tuple[pd.DataFrame, dict[str, float]]:
    template_center = (float(first_external["x_px_external"] / DOWNSAMPLE), float(first_external["y_px_external"] / DOWNSAMPLE))
    template = cv2.getRectSubPix(frames[0], (TEMPLATE_SIZE_SMALL, TEMPLATE_SIZE_SMALL), template_center)
    rows: list[dict[str, object]] = []
    for offset, image in enumerate(frames):
        predicted_x = template_center[0]
        predicted_y = template_center[1] + offset * EXPECTED_Y_STEP_SMALL
        search_size = TEMPLATE_SIZE_SMALL + 2 * SEARCH_MARGIN_SMALL
        search = cv2.getRectSubPix(image, (search_size, search_size), (predicted_x, predicted_y))
        score = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
        _, maximum, _, peak = cv2.minMaxLoc(score)
        peak_x = subpixel_peak(score[int(peak[1]), :], int(peak[0]))
        peak_y = subpixel_peak(score[:, int(peak[0])], int(peak[1]))
        center_x = (predicted_x + peak_x - SEARCH_MARGIN_SMALL) * DOWNSAMPLE
        center_y = (predicted_y + peak_y - SEARCH_MARGIN_SMALL) * DOWNSAMPLE
        rows.append(
            {
                "frame_index": offset + 1,
                "x_px_surrogate": center_x,
                "y_px_surrogate": center_y,
                "score_surrogate": float(maximum),
            }
        )
    table = pd.DataFrame(rows)
    dx = np.diff(table["x_px_surrogate"].to_numpy(dtype=float))
    dy = np.diff(table["y_px_surrogate"].to_numpy(dtype=float))
    error = dy + 8.0
    summary = {
        "steps": len(dy),
        "y_step_mean_px": float(np.mean(dy)),
        "y_step_std_px": float(np.std(dy, ddof=1)),
        "y_error_mae_px": float(np.mean(np.abs(error))),
        "wrong_direction_steps": int(np.sum(dy >= 0)),
        "x_step_std_px": float(np.std(dx, ddof=1)),
        "score_median": float(np.median(table["score_surrogate"])),
    }
    return table, summary


def hybrid_frames(raw: list[np.ndarray], r109: list[np.ndarray]) -> dict[str, list[np.ndarray]]:
    variants: dict[str, list[np.ndarray]] = {
        "Raw": raw,
        "R109 current": r109,
        "R109 residual blend 0.5": [],
        "R109 V42-like raw-anchor detail": [],
        "R109 high-pass residual only": [],
    }
    for raw_image, model_image in zip(raw, r109):
        raw_f = raw_image.astype(np.float32)
        model_f = model_image.astype(np.float32)
        variants["R109 residual blend 0.5"].append(np.clip(raw_f + 0.5 * (model_f - raw_f), 0, 255).astype(np.uint8))
        model_low = cv2.GaussianBlur(model_f, (0, 0), 0.5)
        anchor = raw_f + 0.35 * (model_f - model_low)
        anchor += raw_f.mean() - anchor.mean()
        variants["R109 V42-like raw-anchor detail"].append(np.clip(anchor, 0, 255).astype(np.uint8))
        residual = model_f - raw_f
        residual_high = residual - cv2.GaussianBlur(residual, (0, 0), 1.0)
        variants["R109 high-pass residual only"].append(np.clip(raw_f + residual_high, 0, 255).astype(np.uint8))
    return variants


def correlations(table: pd.DataFrame) -> dict[str, object]:
    features = [
        "ncc_to_arm_median_template",
        "mae_to_arm_median_template_gray",
        "radial_profile_rmse_to_arm_mean",
        "ring_peak_radius_px",
        "ring_halfmax_width_px",
        "ring_contrast_gray",
        "high_frequency_rms_gray",
        "low_frequency_std_gray",
    ]
    output: dict[str, object] = {}
    for feature in features:
        valid = table[[feature, "score_external"]].dropna()
        correlation, p_value = spearmanr(valid[feature], valid["score_external"])
        output[feature] = {"spearman_vs_external_score": float(correlation), "p_value": float(p_value)}
    return output


def main() -> int:
    all_tables: list[pd.DataFrame] = []
    aligned_by_arm: dict[str, list[np.ndarray]] = {}
    frames_by_arm: dict[str, list[np.ndarray]] = {}
    external_coordinates: dict[str, pd.DataFrame] = {}
    surrogate_rows: list[dict[str, object]] = []
    for arm in ("Raw", "V42 E120", "R109 E48"):
        table, aligned, frames = load_arm(arm, CONFIG["models"][arm])
        all_tables.append(table)
        aligned_by_arm[arm] = aligned
        frames_by_arm[arm] = frames
        external_coordinates[arm] = parse_score(Path(PROJECT_ROOT / CONFIG["models"][arm]["score"]), arm)
        surrogate_table, surrogate_summary = locate_with_fixed_template(frames, external_coordinates[arm].iloc[0])
        surrogate_table.insert(0, "arm", arm)
        surrogate_table.to_csv(OUTPUT / f"surrogate_coordinates_{arm.replace(' ', '_')}.csv", index=False, encoding="utf-8-sig")
        surrogate_rows.append({"arm": arm, **surrogate_summary})

    frame_features = pd.concat(all_tables, ignore_index=True)
    frame_features.to_csv(OUTPUT / "frame_features.csv", index=False, encoding="utf-8-sig")
    surrogate_summary = pd.DataFrame(surrogate_rows)
    surrogate_summary.to_csv(OUTPUT / "surrogate_arm_summary.csv", index=False, encoding="utf-8-sig")
    surrogate_order = surrogate_summary.sort_values("y_step_std_px")["arm"].tolist()
    external_order = ["V42 E120", "R109 E48", "Raw"]
    surrogate_valid = surrogate_order == external_order

    template_summary_rows: list[dict[str, object]] = []
    for arm, table in frame_features.groupby("arm", sort=False):
        template_summary_rows.append(
            {
                "arm": arm,
                "ncc_median": float(table["ncc_to_arm_median_template"].median()),
                "ncc_p05": float(table["ncc_to_arm_median_template"].quantile(0.05)),
                "template_mae_median_gray": float(table["mae_to_arm_median_template_gray"].median()),
                "radial_profile_rmse_median": float(table["radial_profile_rmse_to_arm_mean"].median()),
                "ring_peak_radius_std_px": float(table["ring_peak_radius_px"].std(ddof=1)),
                "ring_width_std_px": float(table["ring_halfmax_width_px"].std(ddof=1)),
                "ring_contrast_std_gray": float(table["ring_contrast_gray"].std(ddof=1)),
                "high_frequency_rms_median_gray": float(table["high_frequency_rms_gray"].median()),
                "external_score_median": float(table["score_external"].median()),
                "external_scale_std": float(table["scale_external"].std(ddof=1)),
            }
        )
    template_summary = pd.DataFrame(template_summary_rows)
    template_summary.to_csv(OUTPUT / "template_stability_summary.csv", index=False, encoding="utf-8-sig")

    counterfactual: list[dict[str, object]] = []
    if surrogate_valid:
        first = external_coordinates["Raw"].iloc[0]
        variants = hybrid_frames(frames_by_arm["Raw"], frames_by_arm["R109 E48"])
        for name, frames in variants.items():
            _, summary = locate_with_fixed_template(frames, first)
            counterfactual.append({"variant": name, **summary})
    pd.DataFrame(counterfactual).to_csv(OUTPUT / "counterfactual_surrogate_summary.csv", index=False, encoding="utf-8-sig")

    correlation_results = {
        arm: correlations(group)
        for arm, group in frame_features.groupby("arm", sort=False)
    }
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "population": CONFIG["population"],
        "aligned_crop_full_px": ALIGNED_CROP_FULL,
        "downsample_factor": DOWNSAMPLE,
        "external_arm_order_best_to_worst": external_order,
        "surrogate_arm_order_best_to_worst": surrogate_order,
        "surrogate_ranking_valid": surrogate_valid,
        "template_stability": template_summary.to_dict(orient="records"),
        "surrogate": surrogate_summary.to_dict(orient="records"),
        "counterfactuals": counterfactual,
        "correlations": correlation_results,
        "interpretation_boundary": "Counterfactual results are directional only and require external GMF confirmation.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "surrogate_ranking_valid": surrogate_valid, "surrogate_order": surrogate_order}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
