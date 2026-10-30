from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import correlate, correlation_lags, find_peaks
from scipy.stats import wilcoxon
PROJECT_ROOT = Path(__file__).resolve().parents[6]


OUTPUT = Path(__file__).resolve().parents[1]
TABLES = OUTPUT / "tables"
CROPS = OUTPUT / "images"
PIXEL_UM = 0.069

SELECTION_PATH = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/tables/top30_raw_motion_selection.csv')
)
BASE_ROOT = Path(
    str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/BaseUNet_Baseline_20260718/results_full_data_fixed_psf_tiled_e30/real_inference/sequences')
)
MOSR_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/02_V42_E120_SOURCE_MATERIAL/reconstructions')
)

METHODS = ("Raw", "Base U-Net", "MOSR")
SEQUENCES = {
    "50x_x_0p5um": {
        "nominal_step_um": 0.5,
        "raw": Path(
            str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp')
        ),
        "base": BASE_ROOT / "50x_x_0p5um",
        "mosr": MOSR_ROOT / "50x_0p5um",
    },
    "50x_x_1um": {
        "nominal_step_um": 1.0,
        "raw": Path(
            str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp')
        ),
        "base": BASE_ROOT / "50x_x_1um",
        "mosr": MOSR_ROOT / "50x_1um",
    },
}
ROIS = {
    "vertical_lines": {
        "label": "Vertical-line region",
        "x": 100,
        "y": 90,
        "width": 700,
        "height": 560,
        "profile_axis": 0,
    },
    "horizontal_lines": {
        "label": "Horizontal-line region",
        "x": 1050,
        "y": 850,
        "width": 700,
        "height": 560,
        "profile_axis": 1,
    },
}


def truthy(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    return image.astype(np.float64)


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix if path.suffix else ".png"
    ok, encoded = cv2.imencode(suffix, np.clip(np.rint(image), 0, 255).astype(np.uint8))
    if not ok:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def method_directory(sequence: dict, method: str) -> Path:
    return {
        "Raw": sequence["raw"],
        "Base U-Net": sequence["base"],
        "MOSR": sequence["mosr"],
    }[method]


def frame_path(sequence: dict, method: str, frame_index: int) -> Path:
    return method_directory(sequence, method) / f"frame_{frame_index:04d}.bmp"


def crop_image(image: np.ndarray, roi: dict) -> np.ndarray:
    x, y = int(roi["x"]), int(roi["y"])
    width, height = int(roi["width"]), int(roi["height"])
    return image[y : y + height, x : x + width]


def line_profile(image: np.ndarray, roi: dict) -> np.ndarray:
    crop = crop_image(image, roi)
    return np.median(crop, axis=int(roi["profile_axis"]))


def robust_normalize(profile: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(profile, [2.0, 98.0])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(profile, dtype=np.float64)
    return np.clip((profile - lo) / (hi - lo), 0.0, 1.0)


def detect_edge_candidates(
    raw_profile: np.ndarray,
    expected_shift_px: float = 0.0,
    maximum_edges: int = 24,
) -> list[int]:
    normalized = robust_normalize(raw_profile)
    smoothed = gaussian_filter1d(normalized, sigma=1.0)
    strength = np.abs(np.gradient(smoothed))
    all_candidates, properties = find_peaks(strength, distance=20, prominence=0.02)
    margin = max(18, int(np.ceil(abs(expected_shift_px))) + 18)
    candidates = all_candidates[
        (all_candidates > margin) & (all_candidates < len(raw_profile) - margin)
    ]
    if len(candidates) > maximum_edges:
        prominence_map = dict(
            zip(all_candidates.tolist(), properties["prominences"].tolist())
        )
        candidates = np.asarray(
            sorted(
                sorted(
                    candidates.tolist(),
                    key=lambda value: prominence_map.get(int(value), 0.0),
                    reverse=True,
                )[:maximum_edges]
            ),
            dtype=int,
        )
    return [int(value) for value in candidates]


def crossing_positions(profile: np.ndarray, level: float, indices: np.ndarray) -> list[float]:
    values = profile[indices] - level
    output: list[float] = []
    for index in range(len(indices) - 1):
        first = float(values[index])
        second = float(values[index + 1])
        if first == 0.0 or first * second < 0.0:
            x0, x1 = int(indices[index]), int(indices[index + 1])
            denominator = float(profile[x1] - profile[x0])
            if abs(denominator) < 1.0e-12:
                output.append(float(x0))
            else:
                output.append(float(x0 + (level - profile[x0]) / denominator))
    return output


def measure_edge(
    native_profile: np.ndarray,
    expected_center: float,
    search_radius: int = 7,
) -> dict[str, float] | None:
    profile = gaussian_filter1d(np.asarray(native_profile, dtype=np.float64), sigma=0.75)
    gradient = np.gradient(profile)
    lo = max(15, int(np.floor(expected_center - search_radius)))
    hi = min(len(profile) - 16, int(np.ceil(expected_center + search_radius)))
    if hi <= lo:
        return None
    peak_index = int(np.argmax(np.abs(gradient[lo : hi + 1]))) + lo
    left_level = float(np.median(profile[peak_index - 14 : peak_index - 7]))
    right_level = float(np.median(profile[peak_index + 7 : peak_index + 14]))
    signed_contrast = right_level - left_level
    native_contrast = abs(signed_contrast)
    if not np.isfinite(native_contrast) or native_contrast < 12.0:
        return None
    normalized = (profile - left_level) / signed_contrast
    indices = np.arange(peak_index - 14, peak_index + 15)
    candidates50 = crossing_positions(normalized, 0.50, indices)
    if not candidates50:
        return None
    position50 = min(candidates50, key=lambda value: abs(value - peak_index))
    candidates10 = [
        value for value in crossing_positions(normalized, 0.10, indices) if value <= position50
    ]
    candidates90 = [
        value for value in crossing_positions(normalized, 0.90, indices) if value >= position50
    ]
    if not candidates10 or not candidates90:
        return None
    position10 = max(candidates10)
    position90 = min(candidates90)
    transition_width = position90 - position10
    if not (0.25 <= transition_width <= 20.0):
        return None
    local_gradient = np.max(np.abs(gradient[peak_index - 3 : peak_index + 4]))
    normalized_slope = float(local_gradient / native_contrast)
    local_lo = max(0, peak_index - 18)
    local_hi = min(len(profile), peak_index + 19)
    local_values = profile[local_lo:local_hi]
    lower, upper = sorted((left_level, right_level))
    overshoot = max(
        0.0,
        float(np.max(local_values) - upper),
        float(lower - np.min(local_values)),
    ) / native_contrast
    return {
        "edge_position_px": float(position50),
        "direction": float(np.sign(signed_contrast)),
        "transition_width_px": float(transition_width),
        "normalized_slope_per_px": normalized_slope,
        "native_contrast_8bit": float(native_contrast),
        "overshoot_ratio": float(overshoot),
    }


def line_geometry(edge_rows: list[dict[str, float]]) -> dict[str, float | int]:
    edges = sorted(edge_rows, key=lambda row: row["edge_position_px"])
    falling = [row["edge_position_px"] for row in edges if row["direction"] < 0]
    pitches = [
        float(second - first)
        for first, second in zip(falling[:-1], falling[1:])
        if 50.0 <= second - first <= 90.0
    ]
    median_pitch = float(np.median(pitches)) if pitches else float("nan")
    # A local defect can hide one edge and make a much narrower false pair.  The
    # pitch-derived interval keeps only physically consistent dark-line pairs
    # without using SEM dimensions or a reconstructed-image-specific threshold.
    minimum_width = 0.40 * median_pitch if np.isfinite(median_pitch) else 28.0
    maximum_width = 0.80 * median_pitch if np.isfinite(median_pitch) else 60.0
    dark_widths: list[float] = []
    for row in edges:
        if row["direction"] >= 0:
            continue
        next_rising = [
            other["edge_position_px"]
            for other in edges
            if other["direction"] > 0 and other["edge_position_px"] > row["edge_position_px"]
        ]
        if next_rising:
            width = min(next_rising) - row["edge_position_px"]
            if minimum_width <= width <= maximum_width:
                dark_widths.append(float(width))
    median_width = float(np.median(dark_widths)) if dark_widths else float("nan")
    return {
        "dark_line_count": int(len(dark_widths)),
        "pitch_count": int(len(pitches)),
        "apparent_dark_line_width_px": median_width,
        "apparent_pitch_px": median_pitch,
        "apparent_duty_cycle": median_width / median_pitch
        if np.isfinite(median_width) and np.isfinite(median_pitch) and median_pitch > 0
        else float("nan"),
    }


def profile_correlation_shift(
    reference_profile: np.ndarray,
    moving_profile: np.ndarray,
    expected_shift_px: float,
) -> float:
    reference = np.asarray(reference_profile, dtype=np.float64).copy()
    moving = np.asarray(moving_profile, dtype=np.float64).copy()
    x = np.linspace(-1.0, 1.0, len(reference))
    for profile in (reference, moving):
        trend = np.polyfit(x, profile, 2)
        profile -= np.polyval(trend, x)
        profile *= np.hanning(len(profile))
        standard_deviation = float(np.std(profile))
        if standard_deviation <= 1.0e-12:
            return float("nan")
        profile /= standard_deviation
    correlation = correlate(moving, reference, mode="full", method="fft")
    lags = correlation_lags(len(moving), len(reference), mode="full")
    valid = np.flatnonzero(
        (lags >= expected_shift_px - 5.0) & (lags <= expected_shift_px + 5.0)
    )
    if len(valid) == 0:
        return float("nan")
    index = int(valid[np.argmax(correlation[valid])])
    offset = 0.0
    if 0 < index < len(correlation) - 1:
        denominator = correlation[index - 1] - 2.0 * correlation[index] + correlation[index + 1]
        if abs(denominator) > 1.0e-12:
            offset = 0.5 * (
                correlation[index - 1] - correlation[index + 1]
            ) / denominator
    return float(lags[index] + np.clip(offset, -1.0, 1.0))


def analyze_sharpness(selection: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edge_rows: list[dict] = []
    frame_rows: list[dict] = []
    for sequence_name, chosen in selection.groupby("sequence", sort=False):
        sequence = SEQUENCES[sequence_name]
        for frame_index in sorted(chosen.end_frame_index.astype(int).unique()):
            images = {
                method: read_gray(frame_path(sequence, method, frame_index))
                for method in METHODS
            }
            for orientation, roi in ROIS.items():
                crops = {method: crop_image(image, roi) for method, image in images.items()}
                profiles = {
                    method: np.median(crop, axis=int(roi["profile_axis"]))
                    for method, crop in crops.items()
                }
                candidates = detect_edge_candidates(profiles["Raw"])
                for method in METHODS:
                    crop = crops[method]
                    measurements: list[dict] = []
                    for edge_index, candidate in enumerate(candidates, start=1):
                        measured = measure_edge(profiles[method], candidate)
                        if measured is None:
                            continue
                        measurements.append(measured)
                        edge_rows.append(
                            {
                                "sequence": sequence_name,
                                "nominal_step_um": sequence["nominal_step_um"],
                                "frame_index": frame_index,
                                "orientation": orientation,
                                "method": method,
                                "edge_index": edge_index,
                                "raw_candidate_position_px": candidate,
                                **measured,
                                "transition_width_nm": measured["transition_width_px"]
                                * PIXEL_UM
                                * 1000.0,
                            }
                        )
                    geometry = line_geometry(measurements)
                    frame_rows.append(
                        {
                            "sequence": sequence_name,
                            "nominal_step_um": sequence["nominal_step_um"],
                            "frame_index": frame_index,
                            "orientation": orientation,
                            "method": method,
                            "raw_candidate_edges": len(candidates),
                            "valid_edges": len(measurements),
                            "median_transition_width_nm": float(
                                np.median([row["transition_width_px"] for row in measurements])
                                * PIXEL_UM
                                * 1000.0
                            )
                            if measurements
                            else float("nan"),
                            "median_normalized_slope_per_px": float(
                                np.median([row["normalized_slope_per_px"] for row in measurements])
                            )
                            if measurements
                            else float("nan"),
                            "median_native_contrast_8bit": float(
                                np.median([row["native_contrast_8bit"] for row in measurements])
                            )
                            if measurements
                            else float("nan"),
                            "median_overshoot_ratio": float(
                                np.median([row["overshoot_ratio"] for row in measurements])
                            )
                            if measurements
                            else float("nan"),
                            "native_crop_mean_8bit": float(np.mean(crop)),
                            "native_crop_std_8bit": float(np.std(crop, ddof=1)),
                            "native_crop_p02_8bit": float(np.percentile(crop, 2.0)),
                            "native_crop_p98_8bit": float(np.percentile(crop, 98.0)),
                            "native_crop_clipped_low_percent": float(
                                np.mean(crop <= 1.0) * 100.0
                            ),
                            "native_crop_clipped_high_percent": float(
                                np.mean(crop >= 254.0) * 100.0
                            ),
                            **geometry,
                            "apparent_dark_line_width_um": float(
                                geometry["apparent_dark_line_width_px"] * PIXEL_UM
                            ),
                            "apparent_pitch_um": float(geometry["apparent_pitch_px"] * PIXEL_UM),
                        }
                    )
    return pd.DataFrame(edge_rows), pd.DataFrame(frame_rows)


def analyze_displacement(selection: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edge_shift_rows: list[dict] = []
    step_rows: list[dict] = []
    vertical_roi = ROIS["vertical_lines"]
    for sequence_name, chosen in selection.groupby("sequence", sort=False):
        sequence = SEQUENCES[sequence_name]
        nominal_step_um = float(sequence["nominal_step_um"])
        expected_signed_shift_px = -nominal_step_um / PIXEL_UM
        for _, selected in chosen.sort_values("end_frame_index").iterrows():
            end_frame = int(selected.end_frame_index)
            start_frame = end_frame - 1
            raw_reference = read_gray(frame_path(sequence, "Raw", start_frame))
            raw_profile = line_profile(raw_reference, vertical_roi)
            candidates = detect_edge_candidates(raw_profile, expected_signed_shift_px)
            for method in METHODS:
                reference = (
                    raw_reference
                    if method == "Raw"
                    else read_gray(frame_path(sequence, method, start_frame))
                )
                moving = read_gray(frame_path(sequence, method, end_frame))
                reference_profile = line_profile(reference, vertical_roi)
                moving_profile = line_profile(moving, vertical_roi)
                shifts: list[float] = []
                for edge_index, candidate in enumerate(candidates, start=1):
                    reference_edge = measure_edge(reference_profile, candidate, search_radius=7)
                    moving_edge = measure_edge(
                        moving_profile,
                        candidate + expected_signed_shift_px,
                        search_radius=8,
                    )
                    if reference_edge is None or moving_edge is None:
                        continue
                    if reference_edge["direction"] != moving_edge["direction"]:
                        continue
                    shift_px = moving_edge["edge_position_px"] - reference_edge["edge_position_px"]
                    if abs(shift_px - expected_signed_shift_px) > max(
                        2.5, abs(expected_signed_shift_px) * 0.45
                    ):
                        continue
                    shifts.append(float(shift_px))
                    edge_shift_rows.append(
                        {
                            "sequence": sequence_name,
                            "nominal_step_um": nominal_step_um,
                            "start_frame_index": start_frame,
                            "end_frame_index": end_frame,
                            "method": method,
                            "edge_index": edge_index,
                            "raw_candidate_position_px": candidate,
                            "reference_edge_position_px": reference_edge["edge_position_px"],
                            "moving_edge_position_px": moving_edge["edge_position_px"],
                            "edge_shift_px": shift_px,
                            "edge_step_um": -shift_px * PIXEL_UM,
                            "edge_abs_error_nm": abs(-shift_px * PIXEL_UM - nominal_step_um)
                            * 1000.0,
                        }
                    )
                edge_shift = float(np.median(shifts)) if shifts else float("nan")
                boundary_step_um = -edge_shift * PIXEL_UM
                within_edge_mad_nm = (
                    float(np.median(np.abs(np.asarray(shifts) - np.median(shifts))))
                    * PIXEL_UM
                    * 1000.0
                    if shifts
                    else float("nan")
                )
                profile_shift = profile_correlation_shift(
                    reference_profile,
                    moving_profile,
                    expected_signed_shift_px,
                )
                profile_step_um = -profile_shift * PIXEL_UM
                step_rows.append(
                    {
                        "sequence": sequence_name,
                        "nominal_step_um": nominal_step_um,
                        "start_frame_index": start_frame,
                        "end_frame_index": end_frame,
                        "raw_motion_quality_rank": int(selected.raw_motion_quality_rank),
                        "method": method,
                        "raw_candidate_edges": len(candidates),
                        "usable_edges": len(shifts),
                        "boundary_shift_px": edge_shift,
                        "boundary_step_um": boundary_step_um,
                        "boundary_signed_error_nm": (boundary_step_um - nominal_step_um) * 1000.0,
                        "boundary_abs_error_nm": abs(boundary_step_um - nominal_step_um) * 1000.0,
                        "within_edge_mad_nm": within_edge_mad_nm,
                        "profile_shift_px": profile_shift,
                        "profile_step_um": profile_step_um,
                        "profile_signed_error_nm": (profile_step_um - nominal_step_um) * 1000.0,
                        "profile_abs_error_nm": abs(profile_step_um - nominal_step_um) * 1000.0,
                    }
                )
    return pd.DataFrame(edge_shift_rows), pd.DataFrame(step_rows)


def build_sharpness_summary(frame_table: pd.DataFrame) -> pd.DataFrame:
    return (
        frame_table.groupby(["orientation", "method"], as_index=False)
        .agg(
            frame_count=("frame_index", "count"),
            minimum_valid_edges=("valid_edges", "min"),
            median_transition_width_nm=("median_transition_width_nm", "median"),
            median_normalized_slope_per_px=("median_normalized_slope_per_px", "median"),
            median_native_contrast_8bit=("median_native_contrast_8bit", "median"),
            median_overshoot_ratio=("median_overshoot_ratio", "median"),
            native_crop_mean_8bit=("native_crop_mean_8bit", "median"),
            native_crop_std_8bit=("native_crop_std_8bit", "median"),
            native_crop_p02_8bit=("native_crop_p02_8bit", "median"),
            native_crop_p98_8bit=("native_crop_p98_8bit", "median"),
            native_crop_clipped_low_percent=(
                "native_crop_clipped_low_percent",
                "median",
            ),
            native_crop_clipped_high_percent=(
                "native_crop_clipped_high_percent",
                "median",
            ),
            apparent_dark_line_width_um=("apparent_dark_line_width_um", "median"),
            apparent_dark_line_width_frame_sd_nm=(
                "apparent_dark_line_width_um",
                lambda values: float(values.std(ddof=1) * 1000.0),
            ),
            apparent_pitch_um=("apparent_pitch_um", "median"),
            apparent_pitch_frame_sd_nm=(
                "apparent_pitch_um",
                lambda values: float(values.std(ddof=1) * 1000.0),
            ),
            apparent_duty_cycle=("apparent_duty_cycle", "median"),
        )
    )


def build_displacement_summary(step_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    for (sequence_name, method), group in step_table.groupby(["sequence", "method"], sort=False):
        nominal = float(group.nominal_step_um.iloc[0])
        rows.append(
            {
                "sequence": sequence_name,
                "nominal_step_um": nominal,
                "method": method,
                "step_count": int(len(group)),
                "boundary_valid_steps": int(group.boundary_step_um.notna().sum()),
                "boundary_mae_nm": float(group.boundary_abs_error_nm.mean()),
                "boundary_bias_nm": float(group.boundary_signed_error_nm.mean()),
                "boundary_step_sd_nm": float(group.boundary_step_um.std(ddof=1) * 1000.0),
                "median_within_edge_mad_nm": float(group.within_edge_mad_nm.median()),
                "median_usable_edges": float(group.usable_edges.median()),
                "profile_valid_steps": int(group.profile_step_um.notna().sum()),
                "profile_mae_nm": float(group.profile_abs_error_nm.mean()),
                "profile_bias_nm": float(group.profile_signed_error_nm.mean()),
                "profile_step_sd_nm": float(group.profile_step_um.std(ddof=1) * 1000.0),
            }
        )
    per_sequence = pd.DataFrame(rows)
    pooled_rows: list[dict] = []
    for method, group in step_table.groupby("method", sort=False):
        pooled_rows.append(
            {
                "method": method,
                "step_count": int(len(group)),
                "boundary_valid_steps": int(group.boundary_step_um.notna().sum()),
                "boundary_mae_nm": float(group.boundary_abs_error_nm.mean()),
                "boundary_median_abs_error_nm": float(group.boundary_abs_error_nm.median()),
                "median_within_edge_mad_nm": float(group.within_edge_mad_nm.median()),
                "profile_valid_steps": int(group.profile_step_um.notna().sum()),
                "profile_mae_nm": float(group.profile_abs_error_nm.mean()),
                "profile_median_abs_error_nm": float(group.profile_abs_error_nm.median()),
            }
        )
    pooled = pd.DataFrame(pooled_rows)
    return per_sequence, pooled


def build_paired_tests(step_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for metric in ("boundary_abs_error_nm", "profile_abs_error_nm"):
        wide = step_table.pivot_table(
            index=["sequence", "end_frame_index"], columns="method", values=metric
        ).dropna()
        raw = wide["Raw"]
        for method in ("Base U-Net", "MOSR"):
            candidate = wide[method]
            difference = candidate - raw
            try:
                statistic, p_value = wilcoxon(candidate, raw, zero_method="wilcox")
            except ValueError:
                statistic, p_value = float("nan"), float("nan")
            rows.append(
                {
                    "metric": metric,
                    "candidate_method": method,
                    "paired_step_count": int(len(wide)),
                    "raw_mean_nm": float(raw.mean()),
                    "candidate_mean_nm": float(candidate.mean()),
                    "candidate_minus_raw_mean_nm": float(difference.mean()),
                    "candidate_minus_raw_median_nm": float(difference.median()),
                    "wilcoxon_statistic": float(statistic),
                    "wilcoxon_p_value": float(p_value),
                }
            )
    return pd.DataFrame(rows)


def build_reconstruction_agreement(step_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for estimator, column in (
        ("shared_edge", "boundary_step_um"),
        ("full_profile", "profile_step_um"),
    ):
        wide = step_table.pivot_table(
            index=["sequence", "end_frame_index"], columns="method", values=column
        ).dropna()
        for method in ("Base U-Net", "MOSR"):
            differences_nm = (wide[method] - wide["Raw"]) * 1000.0
            for sequence_name in SEQUENCES:
                sequence_values = differences_nm.loc[sequence_name]
                rows.append(
                    {
                        "scope": sequence_name,
                        "estimator": estimator,
                        "candidate_method": method,
                        "paired_step_count": int(len(sequence_values)),
                        "mean_absolute_difference_from_raw_nm": float(
                            np.mean(np.abs(sequence_values))
                        ),
                        "median_absolute_difference_from_raw_nm": float(
                            np.median(np.abs(sequence_values))
                        ),
                        "mean_signed_difference_from_raw_nm": float(
                            np.mean(sequence_values)
                        ),
                    }
                )
            rows.append(
                {
                    "scope": "pooled_all_available_steps",
                    "estimator": estimator,
                    "candidate_method": method,
                    "paired_step_count": int(len(differences_nm)),
                    "mean_absolute_difference_from_raw_nm": float(
                        np.mean(np.abs(differences_nm))
                    ),
                    "median_absolute_difference_from_raw_nm": float(
                        np.median(np.abs(differences_nm))
                    ),
                    "mean_signed_difference_from_raw_nm": float(np.mean(differences_nm)),
                }
            )
    return pd.DataFrame(rows)


def all_available_step_selection() -> pd.DataFrame:
    rows: list[dict] = []
    for sequence_name in SEQUENCES:
        last_frame = 50 if sequence_name == "50x_x_0p5um" else 49
        for end_frame in range(1, last_frame + 1):
            rows.append(
                {
                    "sequence": sequence_name,
                    "end_frame_index": end_frame,
                    "raw_motion_quality_rank": end_frame,
                }
            )
    return pd.DataFrame(rows)


def export_reference_images() -> None:
    sequence = SEQUENCES["50x_x_0p5um"]
    images = {method: read_gray(frame_path(sequence, method, 0)) for method in METHODS}
    for orientation, roi in ROIS.items():
        for method, image in images.items():
            safe_method = method.lower().replace(" ", "_").replace("-", "_")
            write_image(CROPS / f"{orientation}_{safe_method}.png", crop_image(image, roi))
    overlay = np.clip(np.rint(images["Raw"]), 0, 255).astype(np.uint8)
    overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2BGR)
    colors = {"vertical_lines": (30, 120, 220), "horizontal_lines": (50, 170, 60)}
    for orientation, roi in ROIS.items():
        x, y = int(roi["x"]), int(roi["y"])
        width, height = int(roi["width"]), int(roi["height"])
        cv2.rectangle(overlay, (x, y), (x + width, y + height), colors[orientation], 5)
        cv2.putText(
            overlay,
            roi["label"],
            (x + 12, y + 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            colors[orientation],
            2,
            cv2.LINE_AA,
        )
    write_image(CROPS / "raw_frame0000_roi_overlay.png", overlay)


def validate_inputs(selection: pd.DataFrame) -> None:
    if len(selection) != 60 or selection.groupby("sequence").size().to_dict() != {
        "50x_x_0p5um": 30,
        "50x_x_1um": 30,
    }:
        raise RuntimeError("Expected exactly 30 locked steps for each 50x sequence")
    for sequence_name, sequence in SEQUENCES.items():
        expected_frames = 51 if sequence_name == "50x_x_0p5um" else 50
        for method in METHODS:
            directory = method_directory(sequence, method)
            actual = len(list(directory.glob("frame_*.bmp")))
            if actual != expected_frames:
                raise RuntimeError(
                    f"{sequence_name}/{method}: expected {expected_frames} frames, found {actual}"
                )
            sample = read_gray(frame_path(sequence, method, 0))
            if sample.shape != (1536, 2048):
                raise RuntimeError(f"{sequence_name}/{method}: unexpected image shape {sample.shape}")
    for roi_name, roi in ROIS.items():
        if roi["x"] + roi["width"] > 2048 or roi["y"] + roi["height"] > 1536:
            raise RuntimeError(f"{roi_name} exceeds image bounds")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    CROPS.mkdir(parents=True, exist_ok=True)
    selection = pd.read_csv(SELECTION_PATH)
    selection = selection.loc[
        truthy(selection.top30_raw_motion_selected)
        & selection.sequence.isin(SEQUENCES),
        :,
    ].copy()
    validate_inputs(selection)
    export_reference_images()

    edge_table, frame_table = analyze_sharpness(selection)
    edge_shift_table, step_table = analyze_displacement(selection)
    all_step_selection = all_available_step_selection()
    all_edge_shift_table, all_step_table = analyze_displacement(all_step_selection)
    sharpness_summary = build_sharpness_summary(frame_table)
    displacement_by_sequence, displacement_pooled = build_displacement_summary(step_table)
    all_displacement_by_sequence, all_displacement_pooled = build_displacement_summary(
        all_step_table
    )
    all_step_agreement = build_reconstruction_agreement(all_step_table)
    paired_tests = build_paired_tests(step_table)

    expected_frame_rows = 60 * 2 * 3
    expected_step_rows = 60 * 3
    if len(frame_table) != expected_frame_rows:
        raise RuntimeError(f"Expected {expected_frame_rows} frame rows, found {len(frame_table)}")
    if len(step_table) != expected_step_rows:
        raise RuntimeError(f"Expected {expected_step_rows} displacement rows, found {len(step_table)}")
    if frame_table.valid_edges.min() < 10:
        raise RuntimeError(f"Minimum valid line edges is only {frame_table.valid_edges.min()}")
    if not (step_table.usable_edges >= 8).all():
        raise RuntimeError("At least one displacement step has fewer than eight usable edges")
    if step_table[["boundary_step_um", "profile_step_um"]].isna().any().any():
        raise RuntimeError("At least one displacement result is missing")
    if len(all_step_table) != 99 * 3:
        raise RuntimeError(
            f"Expected {99 * 3} all-step displacement rows, found {len(all_step_table)}"
        )
    all_step_valid_fraction = float(
        all_step_table[["boundary_step_um", "profile_step_um"]].notna().all(axis=1).mean()
    )
    if all_step_valid_fraction < 0.95:
        raise RuntimeError(
            f"Only {all_step_valid_fraction:.1%} of all-step displacement rows are valid"
        )

    tables = {
        "locked_50x_steps.csv": selection,
        "line_edge_measurements.csv": edge_table,
        "line_frame_metrics.csv": frame_table,
        "line_sharpness_summary.csv": sharpness_summary,
        "line_displacement_per_edge.csv": edge_shift_table,
        "line_displacement_per_step.csv": step_table,
        "line_displacement_by_sequence.csv": displacement_by_sequence,
        "line_displacement_pooled.csv": displacement_pooled,
        "line_displacement_paired_tests.csv": paired_tests,
        "line_displacement_all_available_per_edge.csv": all_edge_shift_table,
        "line_displacement_all_available_per_step.csv": all_step_table,
        "line_displacement_all_available_by_sequence.csv": all_displacement_by_sequence,
        "line_displacement_all_available_pooled.csv": all_displacement_pooled,
        "line_displacement_all_available_reconstruction_vs_raw.csv": all_step_agreement,
    }
    for filename, table in tables.items():
        table.to_csv(TABLES / filename, index=False, encoding="utf-8-sig")

    manifest = {
        "purpose": "100MG line-pattern reconstruction-transfer audit without SEM CD truth",
        "date": "2026-07-19",
        "camera": "Basler ace acA2040-120um",
        "magnification": "50x",
        "object_um_per_px": PIXEL_UM,
        "methods": list(METHODS),
        "sequences": {
            name: {
                "nominal_step_um": config["nominal_step_um"],
                "raw": str(config["raw"]),
                "base_unet": str(config["base"]),
                "mosr": str(config["mosr"]),
            }
            for name, config in SEQUENCES.items()
        },
        "rois": ROIS,
        "selection": {
            "source": str(SELECTION_PATH),
            "rule": "same pre-locked top 30 raw-motion steps per sequence",
            "step_count": int(len(selection)),
        },
        "data_lineage_audit": {
            "strict_unseen_generalization": False,
            "interpretation": (
                "in-domain cross-structure and measurement-transfer audit; the same "
                "20260702_100MG capture family is present in the model training package"
            ),
            "v42_split_evidence": {
                "training_entries_from_20260702_100MG": 1103,
                "validation_entries_from_20260702_100MG": 491,
                "split": "grouped_seed1337_val120",
            },
            "base_unet_uses_same_training_split": True,
            "strict_test_requirement": (
                "a new post-training capture or leave-one-capture-family-out retraining"
            ),
        },
        "measurement": {
            "sharpness": "shared Raw edge guides; identical local 10-90 percent rule on native grayscale",
            "apparent_line_width": "paired 50 percent dark-line crossings; no SEM truth, therefore not absolute CD",
            "boundary_displacement": "median of shared individual line-edge 50 percent crossing shifts",
            "profile_displacement": "independent subpixel correlation of the full median line profile",
        },
        "qa": {
            "frame_metric_rows": int(len(frame_table)),
            "edge_measurement_rows": int(len(edge_table)),
            "displacement_step_rows": int(len(step_table)),
            "displacement_edge_rows": int(len(edge_shift_table)),
            "minimum_valid_edges_per_frame": int(frame_table.valid_edges.min()),
            "minimum_usable_edges_per_step": int(step_table.usable_edges.min()),
            "all_displacement_steps_valid": bool(
                step_table[["boundary_step_um", "profile_step_um"]].notna().all().all()
            ),
            "all_available_displacement_step_rows": int(len(all_step_table)),
            "all_available_displacement_steps_valid": bool(
                all_step_table[["boundary_step_um", "profile_step_um"]]
                .notna()
                .all()
                .all()
            ),
            "all_available_displacement_row_valid_fraction": all_step_valid_fraction,
        },
        "sharpness_summary": sharpness_summary.to_dict(orient="records"),
        "displacement_pooled": displacement_pooled.to_dict(orient="records"),
        "all_available_displacement_pooled": all_displacement_pooled.to_dict(
            orient="records"
        ),
        "all_available_reconstruction_vs_raw": all_step_agreement.to_dict(
            orient="records"
        ),
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(sharpness_summary.to_string(index=False))
    print(displacement_by_sequence.to_string(index=False))
    print(displacement_pooled.to_string(index=False))
    print(json.dumps(manifest["qa"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
