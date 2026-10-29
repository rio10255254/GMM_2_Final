"""Correct R112 radial/ring measurements without spatial downsampling.

The source images stay at their native 5120 x 5120 resolution.  Each 1400 px
crop is aligned with the external GMF floating-point centre, then sampled on a
polar grid with bilinear interpolation.  Radial peaks and half-maximum
crossings are continuous-valued; no floor-radius bins are used.

Full-crop texture statistics and true, dynamically detected half-maximum
annulus statistics are emitted as different columns so they cannot be
silently conflated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
PROJECT_ROOT = Path(__file__).resolve().parents[4]


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
R112 = Path(str(PROJECT_ROOT / 'Experiments/R112_V42R109GMFMechanismDecomposition'))
R112_CONFIG = R112 / "config" / "experiment.json"
OUTPUT = ROOT / "results" / "measurement_qa"

CROP_SIZE = 1400
RADIAL_STEP_PX = 0.25
ANGLE_SAMPLES = 720
MAX_RADIUS_PX = 696.0
PEAK_SEARCH_RANGE_PX = (300.0, 680.0)
INNER_BASELINE_RANGE_PX = (80.0, 300.0)
OUTER_BASELINE_RANGE_PX = (680.0, 696.0)

# These preserve the physical scales used by R112 after accounting for its 4x
# downsample: 1.5 * 4 = 6 px and 20 * 4 = 80 px.
HIGH_PASS_SIGMA_PX = 6.0
LOW_PASS_SIGMA_PX = 80.0

ARM_ORDER = ("Raw", "V42 E120", "R109 E48")


@dataclass(frozen=True)
class RingFeatures:
    peak_radius_px: float
    peak_intensity_gray: float
    inner_halfmax_radius_px: float
    outer_halfmax_radius_px: float
    halfmax_width_px: float
    contrast_gray: float
    inner_baseline_gray: float
    outer_baseline_gray: float
    inner_outer_baseline_difference_gray: float
    halfmax_threshold_gray: float


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read image: {path}")
    if image.shape != (5120, 5120):
        raise RuntimeError(f"Unexpected image shape {image.shape}: {path}")
    return image


def parse_score(path: Path, arm: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) % 2:
            raise RuntimeError(f"{path}:{line_number}: odd field count")
        values = {parts[index]: parts[index + 1] for index in range(0, len(parts), 2)}
        match = re.fullmatch(r"frame_(\d{4})\.bmp", values.get("FileName", ""))
        if match is None:
            raise RuntimeError(f"{path}:{line_number}: invalid FileName")
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
    table = pd.DataFrame(rows).sort_values("frame_index").reset_index(drop=True)
    expected = list(range(1, 101))
    if len(table) != 100 or table["frame_index"].tolist() != expected:
        raise RuntimeError(f"{arm}: expected exactly frame_0001 through frame_0100")
    if table[["x_px_external", "y_px_external", "scale_external", "score_external"]].isna().any().any():
        raise RuntimeError(f"{arm}: non-finite coordinate or score field")
    return table


def build_polar_maps(
    crop_size: int = CROP_SIZE,
    radial_step_px: float = RADIAL_STEP_PX,
    angle_samples: int = ANGLE_SAMPLES,
    max_radius_px: float = MAX_RADIUS_PX,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return radii and native-resolution bilinear-remap coordinates."""
    if crop_size < 8 or radial_step_px <= 0 or angle_samples < 16:
        raise ValueError("Invalid polar sampling configuration")
    radii = np.arange(0.0, max_radius_px + radial_step_px * 0.5, radial_step_px, dtype=np.float32)
    angles = np.linspace(0.0, 2.0 * np.pi, angle_samples, endpoint=False, dtype=np.float32)
    center = np.float32((crop_size - 1) / 2.0)
    map_x = center + radii[:, None] * np.cos(angles)[None, :]
    map_y = center + radii[:, None] * np.sin(angles)[None, :]
    return radii.astype(np.float64), map_x.astype(np.float32), map_y.astype(np.float32)


def radial_profile_subpixel(crop: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    """Mean intensity along subpixel-sampled circles, never floor-binned."""
    if crop.ndim != 2:
        raise ValueError("radial_profile_subpixel expects one grayscale plane")
    polar = cv2.remap(
        crop.astype(np.float32, copy=False),
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    return polar.mean(axis=1, dtype=np.float64)


def _median_in_range(radii: np.ndarray, profile: np.ndarray, lower: float, upper: float) -> float:
    mask = (radii >= lower) & (radii < upper)
    if not np.any(mask):
        raise RuntimeError(f"Empty radial baseline range [{lower}, {upper})")
    return float(np.median(profile[mask]))


def _parabolic_peak(radii: np.ndarray, profile: np.ndarray, index: int) -> tuple[float, float]:
    if index <= 0 or index >= len(profile) - 1:
        return float(radii[index]), float(profile[index])
    left, center, right = map(float, profile[index - 1 : index + 2])
    denominator = left - 2.0 * center + right
    if abs(denominator) < 1e-12:
        return float(radii[index]), center
    delta = float(np.clip(0.5 * (left - right) / denominator, -1.0, 1.0))
    step = float(radii[index + 1] - radii[index])
    vertex_x = float(radii[index] + delta * step)
    vertex_y = float(center - 0.25 * (left - right) * delta)
    return vertex_x, vertex_y


def _linear_crossing(x0: float, y0: float, x1: float, y1: float, threshold: float) -> float:
    if abs(y1 - y0) < 1e-12:
        return float(0.5 * (x0 + x1))
    fraction = float(np.clip((threshold - y0) / (y1 - y0), 0.0, 1.0))
    return float(x0 + fraction * (x1 - x0))


def radial_features_subpixel(radii: np.ndarray, profile: np.ndarray) -> RingFeatures:
    """Find the bright ring peak and continuous half-maximum crossings."""
    search = (radii >= PEAK_SEARCH_RANGE_PX[0]) & (radii < PEAK_SEARCH_RANGE_PX[1])
    search_indices = np.flatnonzero(search)
    if not len(search_indices):
        raise RuntimeError("Peak search range is empty")
    peak_index = int(search_indices[int(np.argmax(profile[search]))])
    peak_radius, peak_intensity = _parabolic_peak(radii, profile, peak_index)

    inner_baseline = _median_in_range(radii, profile, *INNER_BASELINE_RANGE_PX)
    outer_baseline = _median_in_range(radii, profile, *OUTER_BASELINE_RANGE_PX)
    baseline = 0.5 * (inner_baseline + outer_baseline)
    threshold = baseline + 0.5 * (peak_intensity - baseline)

    left_candidates = np.flatnonzero(profile[:peak_index] <= threshold)
    right_candidates = np.flatnonzero(profile[peak_index + 1 :] <= threshold)
    if not len(left_candidates) or not len(right_candidates):
        raise RuntimeError("Could not bracket both ring half-maximum crossings")
    left0 = int(left_candidates[-1])
    left1 = left0 + 1
    right1 = int(peak_index + 1 + right_candidates[0])
    right0 = right1 - 1
    inner = _linear_crossing(
        float(radii[left0]), float(profile[left0]),
        float(radii[left1]), float(profile[left1]), threshold,
    )
    outer = _linear_crossing(
        float(radii[right0]), float(profile[right0]),
        float(radii[right1]), float(profile[right1]), threshold,
    )
    if not (inner < peak_radius < outer):
        raise RuntimeError(f"Invalid ring geometry: inner={inner}, peak={peak_radius}, outer={outer}")
    return RingFeatures(
        peak_radius_px=peak_radius,
        peak_intensity_gray=peak_intensity,
        inner_halfmax_radius_px=inner,
        outer_halfmax_radius_px=outer,
        halfmax_width_px=outer - inner,
        contrast_gray=peak_intensity - baseline,
        inner_baseline_gray=inner_baseline,
        outer_baseline_gray=outer_baseline,
        inner_outer_baseline_difference_gray=inner_baseline - outer_baseline,
        halfmax_threshold_gray=threshold,
    )


def annulus_weights(shape: tuple[int, int], inner_radius: float, outer_radius: float) -> np.ndarray:
    """Approximate subpixel boundary coverage with a 1-pixel linear ramp."""
    height, width = shape
    yy, xx = np.indices(shape, dtype=np.float32)
    radius = np.sqrt((xx - (width - 1) / 2.0) ** 2 + (yy - (height - 1) / 2.0) ** 2)
    inner_weight = np.clip(radius - (inner_radius - 0.5), 0.0, 1.0)
    outer_weight = np.clip((outer_radius + 0.5) - radius, 0.0, 1.0)
    return inner_weight * outer_weight


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights, dtype=np.float64))
    if total <= 0:
        return float("nan")
    return float(np.sum(values.astype(np.float64) * weights, dtype=np.float64) / total)


def weighted_std(values: np.ndarray, weights: np.ndarray) -> float:
    mean = weighted_mean(values, weights)
    total = float(np.sum(weights, dtype=np.float64))
    if total <= 1:
        return float("nan")
    variance = float(np.sum(weights * (values.astype(np.float64) - mean) ** 2, dtype=np.float64) / total)
    return float(math.sqrt(max(variance, 0.0)))


def weighted_rms(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights, dtype=np.float64))
    if total <= 0:
        return float("nan")
    return float(math.sqrt(np.sum(weights * values.astype(np.float64) ** 2, dtype=np.float64) / total))


def normalized_correlation(left: np.ndarray, right: np.ndarray) -> float:
    a = left.astype(np.float64)
    b = right.astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.sum(a * b) / denominator) if denominator > 0 else float("nan")


def measure_crop(
    crop: np.ndarray,
    radii: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
) -> tuple[dict[str, float], np.ndarray]:
    crop_f = crop.astype(np.float32)
    profile = radial_profile_subpixel(crop_f, map_x, map_y)
    ring = radial_features_subpixel(radii, profile)
    weights = annulus_weights(crop.shape, ring.inner_halfmax_radius_px, ring.outer_halfmax_radius_px)
    high = crop_f - cv2.GaussianBlur(crop_f, (0, 0), HIGH_PASS_SIGMA_PX)
    low = cv2.GaussianBlur(crop_f, (0, 0), LOW_PASS_SIGMA_PX)
    row = {
        # The half-maximum midpoint is the primary ring radius.  It remains
        # stable when a broad real profile contains two nearly equal local
        # maxima; the local peak is retained as a diagnostic only.
        "ring_halfmax_center_radius_px": 0.5 * (
            ring.inner_halfmax_radius_px + ring.outer_halfmax_radius_px
        ),
        "ring_peak_radius_px": ring.peak_radius_px,
        "ring_peak_intensity_gray": ring.peak_intensity_gray,
        "ring_inner_halfmax_radius_px": ring.inner_halfmax_radius_px,
        "ring_outer_halfmax_radius_px": ring.outer_halfmax_radius_px,
        "ring_halfmax_width_px": ring.halfmax_width_px,
        "ring_contrast_gray": ring.contrast_gray,
        "ring_inner_baseline_gray": ring.inner_baseline_gray,
        "ring_outer_baseline_gray": ring.outer_baseline_gray,
        "ring_inner_outer_baseline_difference_gray": ring.inner_outer_baseline_difference_gray,
        "ring_halfmax_threshold_gray": ring.halfmax_threshold_gray,
        # Full-crop values explicitly retain their spatial scope in the name.
        "full_crop_mean_gray": float(crop_f.mean()),
        "full_crop_std_gray": float(crop_f.std(ddof=1)),
        "full_crop_high_frequency_rms_gray": float(np.sqrt(np.mean(high.astype(np.float64) ** 2))),
        "full_crop_low_frequency_std_gray": float(low.std(ddof=1)),
        # Annulus values use only the detected half-maximum ring band.
        "annulus_effective_pixel_count": float(np.sum(weights, dtype=np.float64)),
        "annulus_mean_gray": weighted_mean(crop_f, weights),
        "annulus_std_gray": weighted_std(crop_f, weights),
        "annulus_high_frequency_rms_gray": weighted_rms(high, weights),
        "annulus_low_frequency_std_gray": weighted_std(low, weights),
    }
    return row, profile


def _safe_spearman(left: pd.Series, right: pd.Series) -> dict[str, float | None]:
    valid = pd.DataFrame({"left": left, "right": right}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < 3 or valid["left"].nunique() < 2 or valid["right"].nunique() < 2:
        return {"rho": None, "p_value": None, "n": int(len(valid))}
    rho, p_value = spearmanr(valid["left"], valid["right"])
    return {"rho": float(rho), "p_value": float(p_value), "n": int(len(valid))}


def summarize(table: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    rows: list[dict[str, object]] = []
    correlations: dict[str, object] = {}
    for arm in ARM_ORDER:
        arm_table = table.loc[table["arm"] == arm].copy()
        rows.append(
            {
                "arm": arm,
                "frames": int(len(arm_table)),
                "ring_center_radius_mean_px": float(arm_table["ring_halfmax_center_radius_px"].mean()),
                "ring_center_radius_std_px": float(arm_table["ring_halfmax_center_radius_px"].std(ddof=1)),
                "ring_center_radius_min_px": float(arm_table["ring_halfmax_center_radius_px"].min()),
                "ring_center_radius_max_px": float(arm_table["ring_halfmax_center_radius_px"].max()),
                "ring_peak_radius_mean_px": float(arm_table["ring_peak_radius_px"].mean()),
                "ring_peak_radius_std_px": float(arm_table["ring_peak_radius_px"].std(ddof=1)),
                "ring_peak_radius_min_px": float(arm_table["ring_peak_radius_px"].min()),
                "ring_peak_radius_max_px": float(arm_table["ring_peak_radius_px"].max()),
                "ring_width_mean_px": float(arm_table["ring_halfmax_width_px"].mean()),
                "ring_width_std_px": float(arm_table["ring_halfmax_width_px"].std(ddof=1)),
                "ring_width_min_px": float(arm_table["ring_halfmax_width_px"].min()),
                "ring_width_max_px": float(arm_table["ring_halfmax_width_px"].max()),
                "ring_contrast_mean_gray": float(arm_table["ring_contrast_gray"].mean()),
                "ring_contrast_std_gray": float(arm_table["ring_contrast_gray"].std(ddof=1)),
                "annulus_high_frequency_rms_median_gray": float(arm_table["annulus_high_frequency_rms_gray"].median()),
                "annulus_high_frequency_rms_std_gray": float(arm_table["annulus_high_frequency_rms_gray"].std(ddof=1)),
                "annulus_low_frequency_std_median_gray": float(arm_table["annulus_low_frequency_std_gray"].median()),
                "annulus_low_frequency_std_std_gray": float(arm_table["annulus_low_frequency_std_gray"].std(ddof=1)),
                "full_crop_high_frequency_rms_median_gray": float(arm_table["full_crop_high_frequency_rms_gray"].median()),
                "full_crop_low_frequency_std_median_gray": float(arm_table["full_crop_low_frequency_std_gray"].median()),
                "external_score_median": float(arm_table["score_external"].median()),
                "external_scale_std": float(arm_table["scale_external"].std(ddof=1)),
            }
        )
        correlations[arm] = {
            metric: _safe_spearman(arm_table[metric], arm_table["score_external"])
            for metric in (
                "ring_halfmax_center_radius_px",
                "ring_peak_radius_px",
                "ring_halfmax_width_px",
                "ring_contrast_gray",
                "annulus_high_frequency_rms_gray",
                "annulus_low_frequency_std_gray",
                "full_crop_high_frequency_rms_gray",
                "full_crop_low_frequency_std_gray",
            )
        }
    return pd.DataFrame(rows), correlations


def validate_source_population(config: dict[str, object]) -> dict[str, object]:
    manifest: dict[str, object] = {
        "r112_config": str(R112_CONFIG),
        "r112_config_sha256": sha256_file(R112_CONFIG),
        "arms": {},
    }
    for arm in ARM_ORDER:
        entry = config["models"][arm]
        image_dir = Path(PROJECT_ROOT / entry["image_dir"])
        score_path = Path(PROJECT_ROOT / entry["score"])
        coordinates = parse_score(score_path, arm)
        image_paths = [image_dir / name for name in coordinates["frame_name"]]
        missing = [str(path) for path in image_paths if not path.is_file()]
        if missing:
            raise RuntimeError(f"{arm}: {len(missing)} score-linked images are missing")
        shapes = {read_gray(image_paths[index]).shape for index in (0, len(image_paths) - 1)}
        if shapes != {(5120, 5120)}:
            raise RuntimeError(f"{arm}: unexpected endpoint shapes {shapes}")
        manifest["arms"][arm] = {
            "image_dir": str(image_dir),
            "score": str(score_path),
            "score_sha256": sha256_file(score_path),
            "score_rows": int(len(coordinates)),
            "score_linked_images": int(len(image_paths)),
            "first_frame": coordinates.iloc[0]["frame_name"],
            "last_frame": coordinates.iloc[-1]["frame_name"],
            "endpoint_shape": [5120, 5120],
        }
    return manifest


def run(selected_arms: Iterable[str] = ARM_ORDER, limit: int | None = None) -> dict[str, object]:
    selected_arms = tuple(selected_arms)
    invalid = sorted(set(selected_arms) - set(ARM_ORDER))
    if invalid:
        raise ValueError(f"Unknown arms: {invalid}")
    config = json.loads(R112_CONFIG.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = validate_source_population(config)
    radii, map_x, map_y = build_polar_maps()
    all_rows: list[dict[str, object]] = []
    profile_rows: list[dict[str, object]] = []
    total_per_arm = 100 if limit is None else min(int(limit), 100)

    for arm in selected_arms:
        entry = config["models"][arm]
        coordinates = parse_score(Path(PROJECT_ROOT / entry["score"]), arm).iloc[:total_per_arm]
        image_dir = Path(PROJECT_ROOT / entry["image_dir"])
        for sequence_number, row in enumerate(coordinates.itertuples(index=False), 1):
            image_path = image_dir / row.frame_name
            image = read_gray(image_path)
            crop = cv2.getRectSubPix(
                image,
                (CROP_SIZE, CROP_SIZE),
                (float(row.x_px_external), float(row.y_px_external)),
            )
            if crop.shape != (CROP_SIZE, CROP_SIZE):
                raise RuntimeError(f"{arm}/{row.frame_name}: invalid aligned crop shape {crop.shape}")
            metrics, profile = measure_crop(crop, radii, map_x, map_y)
            all_rows.append(
                {
                    "arm": arm,
                    "frame_name": row.frame_name,
                    "frame_index": int(row.frame_index),
                    "x_px_external": float(row.x_px_external),
                    "y_px_external": float(row.y_px_external),
                    "scale_external": float(row.scale_external),
                    "score_external": float(row.score_external),
                    **metrics,
                }
            )
            for radius, value in zip(radii, profile):
                profile_rows.append(
                    {
                        "arm": arm,
                        "frame_name": row.frame_name,
                        "radius_px": float(radius),
                        "mean_intensity_gray": float(value),
                    }
                )
            print(
                json.dumps(
                    {"arm": arm, "measured": sequence_number, "total": total_per_arm},
                    ensure_ascii=False,
                ),
                flush=True,
            )

    frame_table = pd.DataFrame(all_rows)
    profile_table = pd.DataFrame(profile_rows)
    frame_path = OUTPUT / "corrected_frame_metrics.csv"
    profile_path = OUTPUT / "corrected_radial_profiles.csv.gz"
    summary_path = OUTPUT / "corrected_arm_summary.csv"
    json_path = OUTPUT / "analysis_summary.json"
    manifest_path = OUTPUT / "source_manifest.json"
    frame_table.to_csv(frame_path, index=False, encoding="utf-8-sig", float_format="%.10g")
    profile_table.to_csv(profile_path, index=False, encoding="utf-8", compression="gzip", float_format="%.10g")
    summary_table, correlations = summarize(frame_table)
    summary_table.to_csv(summary_path, index=False, encoding="utf-8-sig", float_format="%.10g")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    result: dict[str, object] = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "method": {
            "native_image_shape": [5120, 5120],
            "aligned_crop_size_px": CROP_SIZE,
            "spatial_downsample_factor": 1,
            "center_alignment": "cv2.getRectSubPix at external floating-point GMF coordinate",
            "radial_sampling": "native-resolution cv2.remap bilinear polar sampling",
            "radial_step_px": RADIAL_STEP_PX,
            "angle_samples": ANGLE_SAMPLES,
            "radius_bin_flooring": False,
            "peak_localization": "three-point parabolic interpolation",
            "primary_ring_radius": "midpoint of continuous inner and outer half-maximum crossings",
            "local_profile_peak_role": "diagnostic only because broad profiles can contain nearly tied local maxima",
            "halfmax_crossings": "linear subpixel interpolation",
            "annulus_definition": "dynamic inner-to-outer half-maximum radii with 1-pixel soft boundary coverage",
            "full_crop_and_annulus_scopes_are_separate": True,
            "high_pass_sigma_px": HIGH_PASS_SIGMA_PX,
            "low_pass_sigma_px": LOW_PASS_SIGMA_PX,
        },
        "population": {
            "arms": list(selected_arms),
            "frames_per_arm": total_per_arm,
            "frame_rows": int(len(frame_table)),
            "radial_profile_rows": int(len(profile_table)),
        },
        # pandas' JSON encoder converts development-run NaN (for example a
        # one-frame sample standard deviation) to JSON null.  The formal
        # 100-frame run has finite values, but --limit should remain usable.
        "arm_summary": json.loads(summary_table.to_json(orient="records")),
        "correlations_vs_external_score": correlations,
        "interpretation_limits": [
            "External GMF coordinates are used only for alignment and compatibility correlation, not as physical contour truth.",
            "The radial profile is a circular average; non-circular contour fidelity requires ACM/SEM validation outside this measurement.",
            "The half-maximum midpoint is the primary ring radius; the brightest local radial-profile maximum is diagnostic and is not used as a stability claim.",
            "Annulus texture values and full-crop texture values have different spatial support and must not be substituted for each other.",
        ],
    }
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": "complete", "frame_rows": len(frame_table), "summary": str(summary_path)}, ensure_ascii=False), flush=True)
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", choices=ARM_ORDER, help="Measure only one or more arms")
    parser.add_argument("--limit", type=int, default=None, help="Development-only frame limit per arm")
    parser.add_argument("--output-dir", type=Path, default=None, help="Explicit output directory")
    return parser.parse_args(argv)


def resolve_output_dir(args: argparse.Namespace, arms: tuple[str, ...]) -> Path:
    if args.output_dir is not None:
        return args.output_dir.resolve()
    if args.limit is not None or arms != ARM_ORDER:
        return ROOT / "results" / "measurement_qa_dev"
    return ROOT / "results" / "measurement_qa"


def main(argv: list[str] | None = None) -> int:
    global OUTPUT
    args = parse_args(sys.argv[1:] if argv is None else argv)
    arms = tuple(args.arm) if args.arm else ARM_ORDER
    # Never let a partial/development invocation overwrite the canonical
    # 100 x 3 result population.
    OUTPUT = resolve_output_dir(args, arms)
    run(arms, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
