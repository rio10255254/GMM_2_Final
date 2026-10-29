from __future__ import annotations

import csv
import importlib.util
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.stats import wilcoxon
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
INPUT_MANIFEST_CSV = EXPERIMENT / "inputs" / "input_manifest.csv"
INPUT_MANIFEST_JSON = EXPERIMENT / "inputs" / "input_manifest.json"
OUTPUT_MAP = EXPERIMENT / "results" / "method_outputs.json"
TABLES = EXPERIMENT / "analysis" / "tables"
QA = EXPERIMENT / "qa"

PILLAR_CORE = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/scripts/pillar_motion_core.py')
)
LINE_CORE = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/source_validation/100mg_linewidth_generalization_20260719/scripts/analyze_100mg_linewidth_generalization.py')
)

METHOD_LABELS = {
    "raw": "Raw",
    "base_unet": "Base U-Net",
    "edsr": "EDSR",
    "nafnet": "NAFNet",
    "mosr": "MOSR",
}
BOOTSTRAP_SEED = 1261200
BOOTSTRAP_DRAWS = 10_000


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PILLAR = load_module("subpixel_pillar_motion_core", PILLAR_CORE)
LINE = load_module("subpixel_line_measurement_core", LINE_CORE)


def read_u16(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    if image.dtype != np.uint16 or image.shape != (512, 512):
        raise RuntimeError(f"Unexpected image at {path}: {image.dtype} {image.shape}")
    return image


def image_8bit_float(path: Path) -> np.ndarray:
    return read_u16(path).astype(np.float32) / 257.0


def method_path(method_dirs: dict[str, Path], method: str, filename: str) -> Path:
    return method_dirs[method] / filename


def translate_float(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        image.astype(np.float32),
        matrix,
        (image.shape[1], image.shape[0]),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def crossing_near(
    radii: np.ndarray,
    values: np.ndarray,
    level: float,
    expected_radius: float,
    side: str,
) -> float | None:
    shifted = values - level
    crossings: list[float] = []
    for index in range(len(values) - 1):
        first = float(shifted[index])
        second = float(shifted[index + 1])
        if first == 0.0 or first * second < 0.0:
            y0 = float(values[index])
            y1 = float(values[index + 1])
            denominator = y1 - y0
            if abs(denominator) < 1e-12:
                crossings.append(float(radii[index]))
            else:
                fraction = (level - y0) / denominator
                crossings.append(
                    float(radii[index] + fraction * (radii[index + 1] - radii[index]))
                )
    if side == "left":
        preferred = [value for value in crossings if value <= expected_radius]
        if preferred:
            return max(preferred)
    elif side == "right":
        preferred = [value for value in crossings if value >= expected_radius]
        if preferred:
            return min(preferred)
    if not crossings:
        return None
    return min(crossings, key=lambda value: abs(value - expected_radius))


def radial_edge_metrics(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    radius_px: float,
) -> dict[str, float] | None:
    # Annular averaging suppresses local defects while preserving the circular
    # boundary. The intensity is normalized from the interior (0) to exterior (1),
    # so the same calculation applies to bright vias and dark pillars.
    step = 0.10
    outer = max(radius_px * 1.9, radius_px + 6.0)
    radii = np.arange(0.0, outer + step * 0.5, step, dtype=np.float32)
    angles = np.linspace(0.0, 2.0 * np.pi, 96, endpoint=False, dtype=np.float32)
    x_map = center_x + np.cos(angles)[:, None] * radii[None, :]
    y_map = center_y + np.sin(angles)[:, None] * radii[None, :]
    samples = cv2.remap(
        image.astype(np.float32),
        x_map,
        y_map,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    profile = np.median(samples, axis=0).astype(np.float64)
    profile = gaussian_filter1d(profile, sigma=0.45 / step)
    inside_mask = (radii >= radius_px * 0.20) & (radii <= radius_px * 0.52)
    outside_mask = (radii >= radius_px * 1.42) & (radii <= outer * 0.94)
    if int(inside_mask.sum()) < 3 or int(outside_mask.sum()) < 3:
        return None
    inside = float(np.median(profile[inside_mask]))
    outside = float(np.median(profile[outside_mask]))
    signed_contrast = outside - inside
    contrast = abs(signed_contrast)
    if not np.isfinite(contrast) or contrast < 4.0:
        return None
    normalized = (profile - inside) / signed_contrast
    r50 = crossing_near(radii, normalized, 0.50, radius_px, "nearest")
    if r50 is None or abs(r50 - radius_px) > max(3.0, radius_px * 0.65):
        return None
    r10 = crossing_near(radii, normalized, 0.10, r50, "left")
    r90 = crossing_near(radii, normalized, 0.90, r50, "right")
    if r10 is None or r90 is None:
        return None
    width = float(r90 - r10)
    if not (0.15 <= width <= max(12.0, radius_px * 1.5)):
        return None
    gradient = np.gradient(normalized, radii.astype(np.float64))
    local = np.abs(radii - r50) <= max(0.8, radius_px * 0.15)
    slope = float(np.max(np.abs(gradient[local]))) if np.any(local) else float("nan")
    normalized_local = normalized[
        (radii >= radius_px * 0.55) & (radii <= radius_px * 1.55)
    ]
    overshoot = max(
        0.0,
        float(np.max(normalized_local) - 1.0),
        float(0.0 - np.min(normalized_local)),
    )
    return {
        "transition_width_px": width,
        "normalized_slope_per_px": slope,
        "contrast_8bit": contrast,
        "overshoot_ratio": overshoot,
        "edge_position_px": float(r50),
    }


def bootstrap_ci(values: np.ndarray, statistic=np.median) -> tuple[float, float]:
    values = np.asarray(values, dtype=np.float64)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_DRAWS, dtype=np.float64)
    for index in range(BOOTSTRAP_DRAWS):
        sample = values[rng.integers(0, len(values), len(values))]
        draws[index] = float(statistic(sample))
    return tuple(float(value) for value in np.quantile(draws, [0.025, 0.975]))


def holm_adjust(p_values: list[float]) -> list[float]:
    order = np.argsort(np.asarray(p_values, dtype=np.float64))
    adjusted = np.empty(len(p_values), dtype=np.float64)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = (len(p_values) - rank) * float(p_values[index])
        running = max(running, candidate)
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    with INPUT_MANIFEST_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        input_rows = list(csv.DictReader(handle))
    input_meta = json.loads(INPUT_MANIFEST_JSON.read_text(encoding="utf-8"))
    case_meta = {case["case_id"]: case for case in input_meta["cases"]}
    method_dirs = {
        key: Path(PROJECT_ROOT / value)
        for key, value in json.loads(OUTPUT_MAP.read_text(encoding="utf-8")).items()
    }
    methods = list(METHOD_LABELS)
    if set(methods) != set(method_dirs):
        raise RuntimeError(f"Method mapping mismatch: {method_dirs.keys()}")

    rows_by_case: dict[str, list[dict[str, str]]] = {}
    for row in input_rows:
        rows_by_case.setdefault(row["case_id"], []).append(row)

    circular_feature_rows: list[dict[str, object]] = []
    line_edge_rows: list[dict[str, object]] = []
    cluster_rows: list[dict[str, object]] = []
    sharpness_rows: list[dict[str, object]] = []
    equivariance_rows: list[dict[str, object]] = []

    for case_id, case_rows in rows_by_case.items():
        case = case_meta[case_id]
        reference_row = next(row for row in case_rows if row["axis"] == "reference")
        shifted_rows = [row for row in case_rows if row["axis"] != "reference"]
        scale_nm = float(case["object_um_per_px"]) * 1000.0
        measurement = case["measurement"]

        # Image-level equivariance uses the same interpolation operator that
        # created the controlled input translations and excludes a 32-pixel border.
        for method in methods:
            reference_u16 = read_u16(
                method_path(method_dirs, method, reference_row["filename"])
            )
            reference_float = reference_u16.astype(np.float32) / 65535.0
            for row in shifted_rows:
                actual = read_u16(
                    method_path(method_dirs, method, row["filename"])
                ).astype(np.float32) / 65535.0
                expected = translate_float(
                    reference_float, float(row["dx_px"]), float(row["dy_px"])
                )
                inner_actual = actual[32:-32, 32:-32]
                inner_expected = expected[32:-32, 32:-32]
                difference = inner_actual.astype(np.float64) - inner_expected.astype(
                    np.float64
                )
                robust_range = float(
                    np.percentile(inner_expected, 98.0)
                    - np.percentile(inner_expected, 2.0)
                )
                equivariance_rows.append(
                    {
                        "method_key": method,
                        "method": METHOD_LABELS[method],
                        "case_id": case_id,
                        "magnification": case["magnification"],
                        "morphology": case["morphology"],
                        "axis": row["axis"],
                        "shift_px": float(row["shift_px"]),
                        "shift_magnitude_px": abs(float(row["shift_px"])),
                        "rmse": float(np.sqrt(np.mean(difference**2))),
                        "mae": float(np.mean(np.abs(difference))),
                        "robust_intensity_range": robust_range,
                        "normalized_rmse": float(
                            np.sqrt(np.mean(difference**2)) / max(robust_range, 1e-8)
                        ),
                    }
                )

        if case["morphology"] != "line":
            centers = measurement["centers"]
            tracker_config = PILLAR.TrackerConfig(
                radius_px=float(measurement["radius_px"]),
                pitch_px=float(measurement["pitch_px"]),
                polarity=str(measurement["polarity"]),
                search_radius_px=float(measurement["search_radius_px"]),
                min_valid_pillars=7,
                min_edge_strength=float(measurement["min_edge_strength"]),
            )
            for method in methods:
                reference_image = image_8bit_float(
                    method_path(method_dirs, method, reference_row["filename"])
                )
                reference_measurements: dict[str, dict[str, object]] = {}
                reference_sharpness: list[dict[str, float]] = []
                for center in centers:
                    feature_id = str(center["feature_id"])
                    mx = PILLAR.measure_pillar_x(
                        reference_image,
                        predicted_x_px=float(center["x"]),
                        predicted_y_px=float(center["y"]),
                        config=tracker_config,
                    )
                    my = PILLAR.measure_pillar_x(
                        reference_image.T,
                        predicted_x_px=float(center["y"]),
                        predicted_y_px=float(center["x"]),
                        config=tracker_config,
                    )
                    valid = bool(mx.valid and my.valid)
                    reference_measurements[feature_id] = {
                        "valid": valid,
                        "x": float(mx.x_px) if mx.valid else float("nan"),
                        "y": float(my.x_px) if my.valid else float("nan"),
                    }
                    if valid:
                        radial = radial_edge_metrics(
                            reference_image,
                            float(mx.x_px),
                            float(my.x_px),
                            float(measurement["radius_px"]),
                        )
                        if radial is not None:
                            reference_sharpness.append(radial)
                            sharpness_rows.append(
                                {
                                    "method_key": method,
                                    "method": METHOD_LABELS[method],
                                    "case_id": case_id,
                                    "magnification": case["magnification"],
                                    "morphology": case["morphology"],
                                    "axis": "reference",
                                    "shift_px": 0.0,
                                    "feature_id": feature_id,
                                    **radial,
                                }
                            )

                for row in shifted_rows:
                    feature_pairs = []
                    sharp_count = 0
                    image = image_8bit_float(
                        method_path(method_dirs, method, row["filename"])
                    )
                    dx_command = float(row["dx_px"])
                    dy_command = float(row["dy_px"])
                    for center in centers:
                        feature_id = str(center["feature_id"])
                        reference = reference_measurements[feature_id]
                        mx = PILLAR.measure_pillar_x(
                            image,
                            predicted_x_px=float(center["x"]) + dx_command,
                            predicted_y_px=float(center["y"]) + dy_command,
                            config=tracker_config,
                        )
                        my = PILLAR.measure_pillar_x(
                            image.T,
                            predicted_x_px=float(center["y"]) + dy_command,
                            predicted_y_px=float(center["x"]) + dx_command,
                            config=tracker_config,
                        )
                        valid = bool(reference["valid"] and mx.valid and my.valid)
                        measured_dx = (
                            float(mx.x_px) - float(reference["x"])
                            if valid
                            else float("nan")
                        )
                        measured_dy = (
                            float(my.x_px) - float(reference["y"])
                            if valid
                            else float("nan")
                        )
                        along = measured_dx if row["axis"] == "x" else measured_dy
                        cross = measured_dy if row["axis"] == "x" else measured_dx
                        command = float(row["shift_px"])
                        feature_record = {
                            "method_key": method,
                            "method": METHOD_LABELS[method],
                            "case_id": case_id,
                            "magnification": case["magnification"],
                            "morphology": case["morphology"],
                            "axis": row["axis"],
                            "shift_px": command,
                            "feature_id": feature_id,
                            "valid": valid,
                            "measured_dx_px": measured_dx,
                            "measured_dy_px": measured_dy,
                            "along_axis_shift_px": along,
                            "along_axis_error_px": along - command if valid else float("nan"),
                            "cross_axis_shift_px": cross,
                        }
                        circular_feature_rows.append(feature_record)
                        if valid:
                            feature_pairs.append(feature_record)
                            radial = radial_edge_metrics(
                                image,
                                float(mx.x_px),
                                float(my.x_px),
                                float(measurement["radius_px"]),
                            )
                            if radial is not None:
                                sharp_count += 1
                                sharpness_rows.append(
                                    {
                                        "method_key": method,
                                        "method": METHOD_LABELS[method],
                                        "case_id": case_id,
                                        "magnification": case["magnification"],
                                        "morphology": case["morphology"],
                                        "axis": row["axis"],
                                        "shift_px": command,
                                        "feature_id": feature_id,
                                        **radial,
                                    }
                                )
                    valid_count = len(feature_pairs)
                    cluster_valid = valid_count >= 7
                    measured_shift = (
                        float(np.median([item["along_axis_shift_px"] for item in feature_pairs]))
                        if cluster_valid
                        else float("nan")
                    )
                    cross_shift = (
                        float(np.median([item["cross_axis_shift_px"] for item in feature_pairs]))
                        if cluster_valid
                        else float("nan")
                    )
                    error = measured_shift - float(row["shift_px"])
                    cluster_rows.append(
                        {
                            "cluster_id": f"{case_id}|{row['axis']}|{float(row['shift_px']):+.2f}",
                            "method_key": method,
                            "method": METHOD_LABELS[method],
                            "case_id": case_id,
                            "magnification": case["magnification"],
                            "morphology": case["morphology"],
                            "axis": row["axis"],
                            "shift_px": float(row["shift_px"]),
                            "shift_magnitude_px": abs(float(row["shift_px"])),
                            "scale_nm_per_px": scale_nm,
                            "primary_endpoint": True,
                            "valid": cluster_valid,
                            "valid_feature_count": valid_count,
                            "sharpness_feature_count": sharp_count,
                            "measured_shift_px": measured_shift,
                            "signed_error_px": error if cluster_valid else float("nan"),
                            "absolute_error_px": abs(error) if cluster_valid else float("nan"),
                            "signed_error_nm": error * scale_nm if cluster_valid else float("nan"),
                            "absolute_error_nm": abs(error) * scale_nm if cluster_valid else float("nan"),
                            "cross_axis_shift_px": cross_shift,
                            "absolute_cross_axis_px": abs(cross_shift)
                            if cluster_valid
                            else float("nan"),
                        }
                    )
        else:
            measured_axis = str(measurement["measured_shift_axis"])
            raw_reference = image_8bit_float(
                method_path(method_dirs, "raw", reference_row["filename"])
            )
            raw_profile = np.median(
                raw_reference, axis=0 if measured_axis == "x" else 1
            )
            guides = LINE.detect_edge_candidates(raw_profile, 0.0, maximum_edges=24)
            if len(guides) < 10:
                raise RuntimeError(f"Only {len(guides)} line guides in {case_id}")

            for method in methods:
                reference_image = image_8bit_float(
                    method_path(method_dirs, method, reference_row["filename"])
                )
                reference_profile = np.median(
                    reference_image, axis=0 if measured_axis == "x" else 1
                )
                references: dict[int, dict[str, float]] = {}
                for edge_index, guide in enumerate(guides):
                    measured = LINE.measure_edge(reference_profile, guide, search_radius=7)
                    if measured is None:
                        continue
                    references[edge_index] = measured
                    sharpness_rows.append(
                        {
                            "method_key": method,
                            "method": METHOD_LABELS[method],
                            "case_id": case_id,
                            "magnification": case["magnification"],
                            "morphology": case["morphology"],
                            "axis": "reference",
                            "shift_px": 0.0,
                            "feature_id": str(edge_index + 1),
                            "transition_width_px": measured["transition_width_px"],
                            "normalized_slope_per_px": measured[
                                "normalized_slope_per_px"
                            ],
                            "contrast_8bit": measured["native_contrast_8bit"],
                            "overshoot_ratio": measured["overshoot_ratio"],
                            "edge_position_px": measured["edge_position_px"],
                        }
                    )

                for row in shifted_rows:
                    image = image_8bit_float(
                        method_path(method_dirs, method, row["filename"])
                    )
                    profile = np.median(image, axis=0 if measured_axis == "x" else 1)
                    expected_shift = (
                        float(row["shift_px"]) if row["axis"] == measured_axis else 0.0
                    )
                    paired_edges = []
                    for edge_index, guide in enumerate(guides):
                        reference = references.get(edge_index)
                        if reference is None:
                            continue
                        measured = LINE.measure_edge(
                            profile, guide + expected_shift, search_radius=7
                        )
                        valid = bool(
                            measured is not None
                            and measured["direction"] == reference["direction"]
                        )
                        measured_shift = (
                            float(measured["edge_position_px"])
                            - float(reference["edge_position_px"])
                            if valid
                            else float("nan")
                        )
                        record = {
                            "method_key": method,
                            "method": METHOD_LABELS[method],
                            "case_id": case_id,
                            "magnification": case["magnification"],
                            "morphology": case["morphology"],
                            "command_axis": row["axis"],
                            "measured_axis": measured_axis,
                            "shift_px": float(row["shift_px"]),
                            "expected_measured_shift_px": expected_shift,
                            "edge_id": edge_index + 1,
                            "valid": valid,
                            "measured_shift_px": measured_shift,
                            "error_px": measured_shift - expected_shift
                            if valid
                            else float("nan"),
                        }
                        line_edge_rows.append(record)
                        if valid:
                            paired_edges.append(record)
                            sharpness_rows.append(
                                {
                                    "method_key": method,
                                    "method": METHOD_LABELS[method],
                                    "case_id": case_id,
                                    "magnification": case["magnification"],
                                    "morphology": case["morphology"],
                                    "axis": row["axis"],
                                    "shift_px": float(row["shift_px"]),
                                    "feature_id": str(edge_index + 1),
                                    "transition_width_px": measured[
                                        "transition_width_px"
                                    ],
                                    "normalized_slope_per_px": measured[
                                        "normalized_slope_per_px"
                                    ],
                                    "contrast_8bit": measured["native_contrast_8bit"],
                                    "overshoot_ratio": measured["overshoot_ratio"],
                                    "edge_position_px": measured["edge_position_px"],
                                }
                            )
                    valid_count = len(paired_edges)
                    cluster_valid = valid_count >= int(
                        measurement["minimum_valid_edges"]
                    )
                    estimate = (
                        float(np.median([item["measured_shift_px"] for item in paired_edges]))
                        if cluster_valid
                        else float("nan")
                    )
                    error = estimate - expected_shift
                    is_primary = row["axis"] == measured_axis
                    cluster_rows.append(
                        {
                            "cluster_id": f"{case_id}|{row['axis']}|{float(row['shift_px']):+.2f}",
                            "method_key": method,
                            "method": METHOD_LABELS[method],
                            "case_id": case_id,
                            "magnification": case["magnification"],
                            "morphology": case["morphology"],
                            "axis": row["axis"],
                            "shift_px": float(row["shift_px"]),
                            "shift_magnitude_px": abs(float(row["shift_px"])),
                            "scale_nm_per_px": scale_nm,
                            "primary_endpoint": is_primary,
                            "valid": cluster_valid,
                            "valid_feature_count": valid_count,
                            "sharpness_feature_count": valid_count,
                            "measured_shift_px": estimate,
                            "signed_error_px": error if cluster_valid else float("nan"),
                            "absolute_error_px": abs(error) if cluster_valid else float("nan"),
                            "signed_error_nm": error * scale_nm if cluster_valid else float("nan"),
                            "absolute_error_nm": abs(error) * scale_nm
                            if cluster_valid
                            else float("nan"),
                            "cross_axis_shift_px": estimate if not is_primary else float("nan"),
                            "absolute_cross_axis_px": abs(estimate)
                            if (cluster_valid and not is_primary)
                            else float("nan"),
                        }
                    )

    circular_table = pd.DataFrame(circular_feature_rows)
    line_table = pd.DataFrame(line_edge_rows)
    cluster_table = pd.DataFrame(cluster_rows)
    sharpness_table = pd.DataFrame(sharpness_rows)
    equivariance_table = pd.DataFrame(equivariance_rows)

    # Aggregate sharpness at the image-cluster grain before comparing methods.
    sharpness_cluster = (
        sharpness_table.groupby(
            [
                "method_key",
                "method",
                "case_id",
                "magnification",
                "morphology",
                "axis",
                "shift_px",
            ],
            as_index=False,
        )
        .agg(
            valid_feature_count=("feature_id", "count"),
            median_transition_width_px=("transition_width_px", "median"),
            median_normalized_slope_per_px=("normalized_slope_per_px", "median"),
            median_contrast_8bit=("contrast_8bit", "median"),
            median_overshoot_ratio=("overshoot_ratio", "median"),
        )
    )

    primary = cluster_table.loc[
        cluster_table["primary_endpoint"] & cluster_table["valid"]
    ].copy()
    summary_rows = []
    for method in methods:
        subset = primary.loc[primary.method_key == method]
        errors = subset.absolute_error_px.to_numpy(float)
        ci_low, ci_high = bootstrap_ci(errors)
        summary_rows.append(
            {
                "method_key": method,
                "method": METHOD_LABELS[method],
                "valid_primary_clusters": len(subset),
                "expected_primary_clusters": 100,
                "valid_rate": len(subset) / 100.0,
                "median_absolute_error_px": float(np.median(errors)),
                "median_absolute_error_px_ci_low": ci_low,
                "median_absolute_error_px_ci_high": ci_high,
                "p95_absolute_error_px": float(np.percentile(errors, 95.0)),
                "mean_absolute_error_px": float(np.mean(errors)),
                "rmse_px": float(np.sqrt(np.mean(subset.signed_error_px.to_numpy(float) ** 2))),
                "median_signed_error_px": float(np.median(subset.signed_error_px)),
                "median_absolute_error_nm": float(np.median(subset.absolute_error_nm)),
                "p95_absolute_error_nm": float(np.percentile(subset.absolute_error_nm, 95.0)),
            }
        )
    summary = pd.DataFrame(summary_rows)

    group_summary = (
        primary.groupby(
            ["method_key", "method", "magnification", "morphology"], as_index=False
        )
        .agg(
            valid_clusters=("cluster_id", "count"),
            median_absolute_error_px=("absolute_error_px", "median"),
            p95_absolute_error_px=("absolute_error_px", lambda x: np.percentile(x, 95.0)),
            median_absolute_error_nm=("absolute_error_nm", "median"),
            p95_absolute_error_nm=("absolute_error_nm", lambda x: np.percentile(x, 95.0)),
            median_signed_error_px=("signed_error_px", "median"),
        )
    )

    shift_summary = (
        primary.groupby(
            ["method_key", "method", "shift_magnitude_px"], as_index=False
        )
        .agg(
            valid_clusters=("cluster_id", "count"),
            median_absolute_error_px=("absolute_error_px", "median"),
            p95_absolute_error_px=("absolute_error_px", lambda x: np.percentile(x, 95.0)),
        )
    )

    equivariance_summary = (
        equivariance_table.groupby(["method_key", "method"], as_index=False)
        .agg(
            median_normalized_rmse=("normalized_rmse", "median"),
            p95_normalized_rmse=("normalized_rmse", lambda x: np.percentile(x, 95.0)),
            median_mae=("mae", "median"),
        )
    )

    sharpness_summary = (
        sharpness_cluster.groupby(["method_key", "method"], as_index=False)
        .agg(
            image_clusters=("case_id", "count"),
            median_transition_width_px=("median_transition_width_px", "median"),
            p95_transition_width_px=(
                "median_transition_width_px",
                lambda x: np.percentile(x, 95.0),
            ),
            median_normalized_slope_per_px=(
                "median_normalized_slope_per_px",
                "median",
            ),
            median_overshoot_ratio=("median_overshoot_ratio", "median"),
            p95_overshoot_ratio=(
                "median_overshoot_ratio",
                lambda x: np.percentile(x, 95.0),
            ),
        )
    )

    cross_axis = cluster_table.loc[
        cluster_table.valid & cluster_table.absolute_cross_axis_px.notna()
    ].copy()
    cross_axis_summary = (
        cross_axis.groupby(["method_key", "method"], as_index=False)
        .agg(
            clusters=("cluster_id", "count"),
            median_absolute_cross_axis_px=("absolute_cross_axis_px", "median"),
            p95_absolute_cross_axis_px=(
                "absolute_cross_axis_px",
                lambda x: np.percentile(x, 95.0),
            ),
        )
    )

    pair_rows = []
    mosr = primary.loc[primary.method_key == "mosr", ["cluster_id", "absolute_error_px"]]
    mosr = mosr.rename(columns={"absolute_error_px": "mosr_error"})
    for comparator in ["raw", "base_unet", "edsr", "nafnet"]:
        other = primary.loc[
            primary.method_key == comparator, ["cluster_id", "absolute_error_px"]
        ].rename(columns={"absolute_error_px": "comparator_error"})
        paired = mosr.merge(other, on="cluster_id", how="inner")
        advantage = paired.comparator_error.to_numpy(float) - paired.mosr_error.to_numpy(
            float
        )
        ci_low, ci_high = bootstrap_ci(advantage)
        nonzero = paired.loc[
            ~np.isclose(paired.comparator_error, paired.mosr_error, atol=1e-12)
        ]
        p_value = (
            float(
                wilcoxon(
                    nonzero.comparator_error,
                    nonzero.mosr_error,
                    alternative="greater",
                    zero_method="wilcox",
                ).pvalue
            )
            if len(nonzero) >= 2
            else float("nan")
        )
        pair_rows.append(
            {
                "comparator_key": comparator,
                "comparator": METHOD_LABELS[comparator],
                "paired_clusters": len(paired),
                "median_comparator_minus_mosr_absolute_error_px": float(
                    np.median(advantage)
                ),
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "mosr_win_fraction": float(np.mean(advantage > 0)),
                "tie_fraction": float(np.mean(np.isclose(advantage, 0.0, atol=1e-12))),
                "mosr_loss_fraction": float(np.mean(advantage < 0)),
                "one_sided_wilcoxon_p": p_value,
            }
        )
    pair_table = pd.DataFrame(pair_rows)
    pair_table["holm_adjusted_p"] = holm_adjust(
        pair_table.one_sided_wilcoxon_p.fillna(1.0).tolist()
    )

    outputs = {
        "circular_feature_measurements.csv": circular_table,
        "line_edge_measurements.csv": line_table,
        "cluster_translation_metrics.csv": cluster_table,
        "primary_translation_summary_by_method.csv": summary,
        "primary_translation_summary_by_group.csv": group_summary,
        "primary_translation_summary_by_shift.csv": shift_summary,
        "image_equivariance_metrics.csv": equivariance_table,
        "image_equivariance_summary.csv": equivariance_summary,
        "sharpness_feature_measurements.csv": sharpness_table,
        "sharpness_cluster_metrics.csv": sharpness_cluster,
        "sharpness_summary.csv": sharpness_summary,
        "cross_axis_summary.csv": cross_axis_summary,
        "paired_mosr_comparisons.csv": pair_table,
    }
    for filename, table in outputs.items():
        table.to_csv(TABLES / filename, index=False, encoding="utf-8-sig")

    expected_counts = {
        "input_rows": 126,
        "equivariance_rows": 600,
        "cluster_rows": 600,
        "primary_cluster_rows": 500,
        "primary_clusters_per_method": 100,
    }
    actual_counts = {
        "input_rows": len(input_rows),
        "equivariance_rows": len(equivariance_table),
        "cluster_rows": len(cluster_table),
        "primary_cluster_rows": int(cluster_table.primary_endpoint.sum()),
        "primary_clusters_per_method": int(
            cluster_table.loc[cluster_table.primary_endpoint]
            .groupby("method_key")
            .size()
            .min()
        ),
    }
    count_passed = expected_counts == actual_counts
    valid_rate_minimum = float(summary.valid_rate.min())
    analysis_qa = {
        "count_expectations": expected_counts,
        "actual_counts": actual_counts,
        "count_passed": count_passed,
        "minimum_primary_valid_rate": valid_rate_minimum,
        "validity_passed": valid_rate_minimum >= 0.95,
        "minimum_sharpness_clusters_per_method": int(
            sharpness_summary.image_clusters.min()
        ),
        "all_metrics_finite": bool(
            np.isfinite(primary.absolute_error_px.to_numpy(float)).all()
            and np.isfinite(equivariance_table.normalized_rmse.to_numpy(float)).all()
        ),
        "measurement_provenance": {
            "circular_boundary_tracker": str(PILLAR_CORE),
            "line_half_height_tracker": str(LINE_CORE),
            "cluster_grain": "fixed case-axis-signed-shift; feature coordinates summarized by median",
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_draws": BOOTSTRAP_DRAWS,
        },
    }
    analysis_qa["passed"] = bool(
        analysis_qa["count_passed"]
        and analysis_qa["validity_passed"]
        and analysis_qa["all_metrics_finite"]
        and analysis_qa["minimum_sharpness_clusters_per_method"] >= 100
    )
    (QA / "analysis_qa.json").write_text(
        json.dumps(analysis_qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    result = {
        "qa": analysis_qa,
        "primary_summary": summary.to_dict(orient="records"),
        "paired_mosr_comparisons": pair_table.to_dict(orient="records"),
        "equivariance_summary": equivariance_summary.to_dict(orient="records"),
        "sharpness_summary": sharpness_summary.to_dict(orient="records"),
    }
    (EXPERIMENT / "analysis" / "analysis_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not analysis_qa["passed"]:
        raise RuntimeError(f"Analysis QA failed: {analysis_qa}")


if __name__ == "__main__":
    main()
