from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon


EXPERIMENT = Path(__file__).resolve().parent
MANIFEST_PATH = EXPERIMENT / "evaluation_manifest.json"
AUDIT_SCRIPTS = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\01_CURRENT_THESIS_RESULTS_V42_CENTER9\scripts"
)
if str(AUDIT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(AUDIT_SCRIPTS))

from audit_all_displacement_sequences import (  # noqa: E402
    APPROVED_SEQUENCES,
    _load_mapping,
    _raw_segment_measurements,
)


METHODS = ("Raw", "NAFNet", "EDSR", "MOSR")
THRESHOLD_LEVELS = (0.30, 0.40, 0.50, 0.60, 0.70)
CHORD_FRACTIONS = (-0.45, -0.225, 0.0, 0.225, 0.45)
MIN_NATIVE_CONTRAST = 5.0


@dataclass(frozen=True)
class FeatureMeasurement:
    valid: bool
    x_px: float
    centers_by_level: dict[float, float]
    widths_by_level: dict[float, float]
    valid_chords_by_level: dict[float, int]
    contrast_8bit: float
    threshold_center_span_px: float


def read_gray(path: Path) -> np.ndarray:
    payload = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(payload, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def load_frames(directory: Path, frame_count: int) -> list[np.ndarray]:
    paths = [directory / f"frame_{index:04d}.bmp" for index in range(frame_count)]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"{directory} is missing {len(missing)} frame(s); first missing: {missing[0].name}"
        )
    return [read_gray(path) for path in paths]


def method_sequence_dir(
    manifest: dict[str, Any],
    method: str,
    sequence_name: str,
    raw_dir: Path,
) -> Path:
    if method == "Raw":
        return raw_dir
    root = Path(manifest["methods"][method]["sequence_root"])
    mapped = manifest["sequence_name_map"][sequence_name][method]
    return root / mapped


def load_config(path: Path, morphology: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))["sequences"]
    if morphology == "pillar":
        return payload
    if morphology != "via":
        raise ValueError(morphology)
    converted: dict[str, dict[str, Any]] = {}
    for sequence_name, source in payload.items():
        item = dict(source)
        item["min_valid_pillars"] = int(item.pop("min_valid_features"))
        item["min_edge_strength"] = 1.0
        item["centers"] = [
            [index, center["x"], center["y"]]
            for index, center in enumerate(item["centers"], start=1)
        ]
        converted[sequence_name] = item
    return converted


def session_bounds(sessions: pd.DataFrame) -> list[tuple[int, int, int]]:
    output: list[tuple[int, int, int]] = []
    for session_id, group in sessions.groupby("session_id", sort=True):
        output.append(
            (
                int(session_id),
                int(group["frame_index"].min()),
                int(group["frame_index"].max()),
            )
        )
    return output


def sample_horizontal_profile(image: np.ndarray, y_px: float) -> np.ndarray:
    width = image.shape[1]
    x_map = np.arange(width, dtype=np.float32)[None, :]
    y_map = np.full((1, width), float(y_px), dtype=np.float32)
    profile = cv2.remap(
        image.astype(np.float32),
        x_map,
        y_map,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )[0]
    return cv2.GaussianBlur(profile[None, :], (0, 0), sigmaX=0.60)[0]


def median_interval(profile: np.ndarray, start: float, stop: float) -> float | None:
    left = max(0, int(np.floor(min(start, stop))))
    right = min(len(profile), int(np.ceil(max(start, stop))) + 1)
    if right - left < 2:
        return None
    value = float(np.median(profile[left:right]))
    return value if np.isfinite(value) else None


def crossing_near(
    normalized: np.ndarray,
    *,
    level: float,
    expected_x: float,
    half_width: float,
    direction: str,
) -> float | None:
    start = max(0, int(np.floor(expected_x - half_width)))
    stop = min(len(normalized) - 1, int(np.ceil(expected_x + half_width)))
    candidates: list[float] = []
    for index in range(start, stop):
        first = float(normalized[index])
        second = float(normalized[index + 1])
        if not np.isfinite(first) or not np.isfinite(second) or first == second:
            continue
        if direction == "up":
            crossed = first <= level < second
        elif direction == "down":
            crossed = first >= level > second
        else:
            raise ValueError(direction)
        if not crossed:
            continue
        fraction = (level - first) / (second - first)
        candidates.append(float(index) + float(np.clip(fraction, 0.0, 1.0)))
    if not candidates:
        return None
    return min(candidates, key=lambda value: abs(value - expected_x))


def measure_feature(
    image: np.ndarray,
    *,
    predicted_x_px: float,
    predicted_y_px: float,
    radius_px: float,
    search_radius_px: float,
) -> FeatureMeasurement:
    height, width = image.shape
    if not (0 <= predicted_x_px < width and 0 <= predicted_y_px < height):
        return FeatureMeasurement(False, np.nan, {}, {}, {}, np.nan, np.nan)

    centers: dict[float, list[float]] = {level: [] for level in THRESHOLD_LEVELS}
    widths: dict[float, list[float]] = {level: [] for level in THRESHOLD_LEVELS}
    contrasts: list[float] = []
    radius = float(radius_px)
    crossing_half_width = float(search_radius_px) + max(1.0, radius * 0.22)

    for fraction in CHORD_FRACTIONS:
        y_px = float(predicted_y_px) + float(fraction) * radius
        if y_px < 1 or y_px >= height - 1:
            continue
        half_chord = radius * float(np.sqrt(max(0.0, 1.0 - fraction**2)))
        left_expected = float(predicted_x_px) - half_chord
        right_expected = float(predicted_x_px) + half_chord
        profile = sample_horizontal_profile(image, y_px)

        inside = median_interval(
            profile,
            float(predicted_x_px) - max(1.0, 0.24 * half_chord),
            float(predicted_x_px) + max(1.0, 0.24 * half_chord),
        )
        left_outside = median_interval(
            profile,
            left_expected - 0.58 * radius,
            left_expected - 0.24 * radius,
        )
        right_outside = median_interval(
            profile,
            right_expected + 0.24 * radius,
            right_expected + 0.58 * radius,
        )
        if inside is None or left_outside is None or right_outside is None:
            continue
        left_contrast = abs(inside - left_outside)
        right_contrast = abs(inside - right_outside)
        contrast = float(min(left_contrast, right_contrast))
        if contrast < MIN_NATIVE_CONTRAST:
            continue
        contrasts.append(contrast)

        left_normalized = (profile - left_outside) / (inside - left_outside)
        right_normalized = (profile - right_outside) / (inside - right_outside)
        for level in THRESHOLD_LEVELS:
            left_x = crossing_near(
                left_normalized,
                level=level,
                expected_x=left_expected,
                half_width=crossing_half_width,
                direction="up",
            )
            right_x = crossing_near(
                right_normalized,
                level=level,
                expected_x=right_expected,
                half_width=crossing_half_width,
                direction="down",
            )
            if left_x is None or right_x is None or right_x <= left_x:
                continue
            center_x = 0.5 * (left_x + right_x)
            if abs(center_x - float(predicted_x_px)) >= float(search_radius_px):
                continue
            centers[level].append(center_x)
            widths[level].append(right_x - left_x)

    minimum_chords = 2 if radius < 10.0 else 3
    centers_by_level = {
        level: float(np.median(values))
        for level, values in centers.items()
        if len(values) >= minimum_chords
    }
    widths_by_level = {
        level: float(np.median(widths[level]))
        for level in centers_by_level
    }
    valid_chords_by_level = {
        level: len(centers[level])
        for level in centers_by_level
    }
    if len(centers_by_level) < 3:
        return FeatureMeasurement(
            False,
            np.nan,
            centers_by_level,
            widths_by_level,
            valid_chords_by_level,
            float(np.median(contrasts)) if contrasts else np.nan,
            np.nan,
        )
    center_values = np.asarray(list(centers_by_level.values()), dtype=np.float64)
    return FeatureMeasurement(
        True,
        float(np.median(center_values)),
        centers_by_level,
        widths_by_level,
        valid_chords_by_level,
        float(np.median(contrasts)),
        float(np.ptp(center_values)),
    )


def measure_method_session(
    images: list[np.ndarray],
    *,
    initial_centers: np.ndarray,
    feature_ids: list[str],
    prediction_shifts: tuple[float, ...],
    radius_px: float,
    search_radius_px: float,
    expected_dx_px: float,
    min_valid_features: int,
    global_start_frame: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame_records: list[dict[str, object]] = []
    measurements: list[dict[str, FeatureMeasurement]] = []
    for local_frame, (image, prediction_shift) in enumerate(
        zip(images, prediction_shifts, strict=True)
    ):
        measured: dict[str, FeatureMeasurement] = {}
        for feature_id, (initial_x, initial_y) in zip(
            feature_ids, initial_centers, strict=True
        ):
            predicted_x = float(initial_x) + float(prediction_shift)
            result = measure_feature(
                image,
                predicted_x_px=predicted_x,
                predicted_y_px=float(initial_y),
                radius_px=radius_px,
                search_radius_px=search_radius_px,
            )
            if result.valid:
                measured[feature_id] = result
            frame_records.append(
                {
                    "frame_index": global_start_frame + local_frame,
                    "feature_id": feature_id,
                    "predicted_x_px": predicted_x,
                    "measured_x_px": result.x_px,
                    "valid": result.valid,
                    "valid_levels": len(result.centers_by_level),
                    "contrast_8bit": result.contrast_8bit,
                    "threshold_center_span_px": result.threshold_center_span_px,
                }
            )
        measurements.append(measured)

    step_records: list[dict[str, object]] = []
    feature_step_records: list[dict[str, object]] = []
    threshold_step_records: list[dict[str, object]] = []
    for local_frame in range(1, len(images)):
        previous = measurements[local_frame - 1]
        current = measurements[local_frame]
        feature_displacements: list[tuple[str, float, float, dict[float, float]]] = []
        for feature_id in feature_ids:
            if feature_id not in previous or feature_id not in current:
                continue
            common_levels = sorted(
                set(previous[feature_id].centers_by_level)
                & set(current[feature_id].centers_by_level)
            )
            level_dx = {
                level: current[feature_id].centers_by_level[level]
                - previous[feature_id].centers_by_level[level]
                for level in common_levels
            }
            if len(level_dx) < 3:
                continue
            values = np.asarray(list(level_dx.values()), dtype=np.float64)
            feature_dx = float(np.median(values))
            threshold_span = float(np.ptp(values))
            feature_displacements.append(
                (feature_id, feature_dx, threshold_span, level_dx)
            )

        if len(feature_displacements) >= min_valid_features:
            values = np.asarray(
                [item[1] for item in feature_displacements], dtype=np.float64
            )
            preliminary = float(np.median(values))
            residuals = values - preliminary
            mad = float(np.median(np.abs(residuals)))
            residual_limit = max(
                3.0 * 1.4826 * mad,
                max(0.35, 0.18 * abs(float(expected_dx_px))),
            )
            keep = np.abs(residuals) <= residual_limit
        else:
            keep = np.zeros(len(feature_displacements), dtype=bool)

        accepted = [
            item
            for item, accepted_flag in zip(feature_displacements, keep, strict=True)
            if accepted_flag
        ]
        valid = len(accepted) >= min_valid_features
        if valid:
            accepted_values = np.asarray([item[1] for item in accepted], dtype=np.float64)
            consensus = float(np.median(accepted_values))
            disagreement = float(
                1.4826 * np.median(np.abs(accepted_values - consensus))
            )
            threshold_sensitivity = float(np.median([item[2] for item in accepted]))
        else:
            consensus = np.nan
            disagreement = np.nan
            threshold_sensitivity = np.nan

        end_frame = global_start_frame + local_frame
        step_records.append(
            {
                "end_frame_index": end_frame,
                "valid": valid,
                "valid_features": len(accepted),
                "candidate_features": len(feature_displacements),
                "signed_step_px": consensus,
                "within_grid_mad_px": disagreement,
                "threshold_sensitivity_px": threshold_sensitivity,
            }
        )
        accepted_ids = {item[0] for item in accepted}
        for feature_id, feature_dx, threshold_span, level_dx in feature_displacements:
            feature_step_records.append(
                {
                    "end_frame_index": end_frame,
                    "feature_id": feature_id,
                    "accepted": bool(feature_id in accepted_ids and valid),
                    "signed_step_px": feature_dx,
                    "threshold_sensitivity_px": threshold_span,
                }
            )
            for level, dx_px in level_dx.items():
                threshold_step_records.append(
                    {
                        "end_frame_index": end_frame,
                        "feature_id": feature_id,
                        "level": level,
                        "accepted": bool(feature_id in accepted_ids and valid),
                        "signed_step_px": dx_px,
                    }
                )
    return (
        pd.DataFrame(frame_records),
        pd.DataFrame(step_records),
        pd.DataFrame(feature_step_records),
        pd.DataFrame(threshold_step_records),
    )


def summarize_group(group: pd.DataFrame) -> dict[str, object]:
    values = group.loc[group["common_valid"]].copy()
    errors = values["signed_error_nm"].to_numpy(dtype=float)
    absolute = np.abs(errors)
    return {
        "n": len(values),
        "mean_signed_step_nm": float(values["signed_step_nm"].mean()),
        "bias_nm": float(np.mean(errors)),
        "error_sd_nm": float(np.std(errors, ddof=1)) if len(errors) > 1 else np.nan,
        "mae_nm": float(np.mean(absolute)),
        "median_absolute_error_nm": float(np.median(absolute)),
        "rmse_nm": float(np.sqrt(np.mean(errors**2))),
        "p95_absolute_error_nm": float(np.percentile(absolute, 95.0)),
        "median_within_grid_mad_nm": float(values["within_grid_mad_nm"].median()),
        "median_threshold_sensitivity_nm": float(
            values["threshold_sensitivity_nm"].median()
        ),
    }


def paired_comparisons(common_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(20260724)
    scopes = [
        ("all", common_table),
        *[
            (f"{morphology}_{magnification}", group)
            for (morphology, magnification), group in common_table.groupby(
                ["morphology", "magnification"], sort=False
            )
        ],
    ]
    for scope, scoped in scopes:
        wide = scoped.pivot_table(
            index=["morphology", "sequence", "end_frame_index"],
            columns="method",
            values="absolute_error_nm",
        )
        if "EDSR" not in wide or "MOSR" not in wide:
            continue
        paired = wide[["EDSR", "MOSR"]].dropna()
        difference = (
            paired["MOSR"].to_numpy(dtype=float)
            - paired["EDSR"].to_numpy(dtype=float)
        )
        draws = np.empty(10000, dtype=np.float64)
        for index in range(len(draws)):
            sampled = rng.integers(0, len(difference), len(difference))
            draws[index] = float(np.mean(difference[sampled]))
        try:
            statistic, p_value = wilcoxon(
                paired["MOSR"], paired["EDSR"], zero_method="wilcox"
            )
        except ValueError:
            statistic, p_value = np.nan, np.nan
        rows.append(
            {
                "scope": scope,
                "paired_steps": len(paired),
                "edsr_mae_nm": float(paired["EDSR"].mean()),
                "mosr_mae_nm": float(paired["MOSR"].mean()),
                "mosr_minus_edsr_mae_nm": float(np.mean(difference)),
                "bootstrap_ci_low_nm": float(np.percentile(draws, 2.5)),
                "bootstrap_ci_high_nm": float(np.percentile(draws, 97.5)),
                "wilcoxon_statistic": float(statistic),
                "wilcoxon_p_value": float(p_value),
            }
        )
    return pd.DataFrame(rows)


def build_report(
    output_root: Path,
    pooled: pd.DataFrame,
    comparisons: pd.DataFrame,
    qa: dict[str, object],
) -> None:
    lines = [
        "# 等灰階輪廓邊界位移驗證",
        "",
        "本次量測以圓形結構左右邊界的 30%、40%、50%、60% 與 70% 等灰階交點定位中心，",
        "再以九個結構的位移中位數作為每一步結果。所有方法共用 Raw 建立的預測位置、",
        "相同 30 步與相同有效性規則，未依模型調整門檻或刪除步次。",
        "",
        "## 共同有效步次結果",
        "",
        "| 形貌 | 倍率 | 方法 | 步數 | MAE (nm) | 中位絕對誤差 (nm) | P95 (nm) | 門檻敏感度 (nm) |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in pooled.iterrows():
        lines.append(
            "| {morphology} | {magnification} | {method} | {n:d} | "
            "{mae_nm:.3f} | {median_absolute_error_nm:.3f} | "
            "{p95_absolute_error_nm:.3f} | {median_threshold_sensitivity_nm:.3f} |".format(
                **row.to_dict()
            )
        )
    lines.extend(
        [
            "",
            "## EDSR 與 MOSR 成對比較",
            "",
            "| 範圍 | 共同步數 | EDSR MAE (nm) | MOSR MAE (nm) | MOSR−EDSR (nm) | 95% CI (nm) | p 值 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in comparisons.iterrows():
        lines.append(
            "| {scope} | {paired_steps:d} | {edsr_mae_nm:.3f} | {mosr_mae_nm:.3f} | "
            "{mosr_minus_edsr_mae_nm:.3f} | [{bootstrap_ci_low_nm:.3f}, "
            "{bootstrap_ci_high_nm:.3f}] | {wilcoxon_p_value:.4f} |".format(
                **row.to_dict()
            )
        )
    lines.extend(
        [
            "",
            "## 品質檢查",
            "",
            f"- 已鎖定序列數：{qa['sequence_count']}",
            f"- 每個序列預先選定步數：{qa['locked_steps_per_sequence']}",
            f"- 原始量測列數：{qa['step_rows']}",
            f"- 共同有效列數：{qa['common_valid_rows']}",
            f"- 重複鍵數：{qa['duplicate_keys']}",
            f"- 主要數值缺值數：{qa['primary_metric_nulls']}",
        ]
    )
    (output_root / "VALIDATION_REPORT_zh-TW.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main(output_root: Path, manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    unavailable = [method for method in METHODS if method not in manifest["methods"]]
    if unavailable:
        raise RuntimeError(f"Missing methods in manifest: {unavailable}")
    selection = pd.read_csv(manifest["top30_selection"])
    selection = selection.loc[
        selection["top30_raw_motion_selected"].astype(bool)
        & selection["sequence"].isin(APPROVED_SEQUENCES)
    ].copy()
    counts = selection.groupby("sequence").size()
    if not counts.eq(30).all() or set(counts.index) != set(APPROVED_SEQUENCES):
        raise RuntimeError("Locked selection must contain exactly 30 steps per sequence")

    all_frames: list[pd.DataFrame] = []
    all_steps: list[pd.DataFrame] = []
    all_feature_steps: list[pd.DataFrame] = []
    all_threshold_steps: list[pd.DataFrame] = []

    for morphology, config_key in (("pillar", "pillar_config"), ("via", "via_config")):
        configs = load_config(Path(manifest[config_key]), morphology)
        for sequence_name in APPROVED_SEQUENCES:
            sequence = configs[sequence_name]
            frame_count = int(sequence["frame_count"])
            raw_dir = Path(sequence["raw_dir"])
            raw_images = load_frames(raw_dir, frame_count)
            sessions = _load_mapping(sequence_name)
            _, runtime = _raw_segment_measurements(
                sequence_name,
                sequence,
                sessions,
                raw_images,
            )
            initial_ids = [str(int(row[0])) for row in sequence["centers"]]
            for method in METHODS:
                directory = method_sequence_dir(
                    manifest,
                    method,
                    sequence_name,
                    raw_dir,
                )
                images = raw_images if method == "Raw" else load_frames(directory, frame_count)
                method_frames: list[pd.DataFrame] = []
                method_steps: list[pd.DataFrame] = []
                method_features: list[pd.DataFrame] = []
                method_thresholds: list[pd.DataFrame] = []
                for session_id, start_frame, end_frame in session_bounds(sessions):
                    state = runtime[session_id]
                    raw_tracking = state.get("raw_result")
                    shifted_centers = state.get("shifted_centers")
                    if (
                        raw_tracking is None
                        or shifted_centers is None
                        or end_frame <= start_frame
                    ):
                        continue
                    segment = images[start_frame : end_frame + 1]
                    frames, steps, features, thresholds = measure_method_session(
                        segment,
                        initial_centers=np.asarray(shifted_centers, dtype=float),
                        feature_ids=initial_ids,
                        prediction_shifts=raw_tracking.prediction_shifts,
                        radius_px=float(sequence["radius_px"]),
                        search_radius_px=float(sequence["search_radius_px"]),
                        expected_dx_px=float(sequence["expected_signed_dx_px"]),
                        min_valid_features=int(sequence["min_valid_pillars"]),
                        global_start_frame=start_frame,
                    )
                    for table in (frames, steps, features, thresholds):
                        table["session_id"] = session_id
                    method_frames.append(frames)
                    method_steps.append(steps)
                    method_features.append(features)
                    method_thresholds.append(thresholds)

                frame_table = pd.concat(method_frames, ignore_index=True)
                step_table = pd.concat(method_steps, ignore_index=True)
                feature_table = pd.concat(method_features, ignore_index=True)
                threshold_table = pd.concat(method_thresholds, ignore_index=True)
                for table in (frame_table, step_table, feature_table, threshold_table):
                    table["morphology"] = morphology
                    table["sequence"] = sequence_name
                    table["magnification"] = sequence["magnification"]
                    table["method"] = method
                object_um_per_px = float(sequence["object_um_per_px"])
                expected_um = float(sequence["expected_signed_dx_px"]) * object_um_per_px
                step_table["expected_signed_step_um"] = expected_um
                step_table["signed_step_um"] = (
                    step_table["signed_step_px"] * object_um_per_px
                )
                step_table["signed_step_nm"] = step_table["signed_step_um"] * 1000.0
                step_table["signed_error_nm"] = (
                    step_table["signed_step_um"] - expected_um
                ) * 1000.0
                step_table["absolute_error_nm"] = step_table["signed_error_nm"].abs()
                step_table["within_grid_mad_nm"] = (
                    step_table["within_grid_mad_px"] * object_um_per_px * 1000.0
                )
                step_table["threshold_sensitivity_nm"] = (
                    step_table["threshold_sensitivity_px"]
                    * object_um_per_px
                    * 1000.0
                )
                all_frames.append(frame_table)
                all_steps.append(step_table)
                all_feature_steps.append(feature_table)
                all_threshold_steps.append(threshold_table)
                print(
                    f"{morphology} {sequence_name} {method}: "
                    f"{int(step_table['valid'].sum())}/{len(step_table)} valid steps",
                    flush=True,
                )

    frame_output = pd.concat(all_frames, ignore_index=True)
    step_output = pd.concat(all_steps, ignore_index=True)
    feature_output = pd.concat(all_feature_steps, ignore_index=True)
    threshold_output = pd.concat(all_threshold_steps, ignore_index=True)
    step_output = step_output.merge(
        selection[
            ["sequence", "end_frame_index", "raw_motion_quality_rank"]
        ],
        on=["sequence", "end_frame_index"],
        how="inner",
        validate="many_to_one",
    )
    if step_output.groupby(["morphology", "sequence", "method"]).size().ne(30).any():
        raise RuntimeError("A method does not have exactly 30 locked step rows")

    validity = step_output.pivot_table(
        index=["morphology", "sequence", "end_frame_index"],
        columns="method",
        values="valid",
        aggfunc="first",
    ).reindex(columns=METHODS)
    common_keys = validity.index[validity.fillna(False).all(axis=1)]
    common_index = pd.MultiIndex.from_frame(
        step_output[["morphology", "sequence", "end_frame_index"]]
    )
    step_output["common_valid"] = common_index.isin(common_keys)

    summary_rows: list[dict[str, object]] = []
    for keys, group in step_output.groupby(
        ["morphology", "magnification", "method"], sort=False
    ):
        record = {
            "morphology": keys[0],
            "magnification": keys[1],
            "method": keys[2],
        }
        record.update(summarize_group(group))
        summary_rows.append(record)
    pooled = pd.DataFrame(summary_rows)
    comparisons = paired_comparisons(step_output.loc[step_output["common_valid"]])

    duplicate_keys = int(
        step_output.duplicated(
            ["morphology", "sequence", "method", "end_frame_index"]
        ).sum()
    )
    primary_nulls = int(
        step_output.loc[
            step_output["common_valid"],
            ["signed_step_nm", "signed_error_nm", "absolute_error_nm"],
        ].isna().sum().sum()
    )
    qa = {
        "sequence_count": len(APPROVED_SEQUENCES),
        "locked_steps_per_sequence": 30,
        "methods": list(METHODS),
        "morphologies": ["pillar", "via"],
        "step_rows": len(step_output),
        "common_valid_rows": int(step_output["common_valid"].sum()),
        "common_valid_unique_steps": len(common_keys),
        "duplicate_keys": duplicate_keys,
        "primary_metric_nulls": primary_nulls,
        "threshold_levels": list(THRESHOLD_LEVELS),
        "chord_fractions": list(CHORD_FRACTIONS),
        "minimum_native_contrast_8bit": MIN_NATIVE_CONTRAST,
    }
    if duplicate_keys or primary_nulls:
        raise RuntimeError(f"QA failed: {qa}")

    output_root.mkdir(parents=True, exist_ok=True)
    frame_output.to_csv(
        output_root / "frame_feature_measurements.csv",
        index=False,
        encoding="utf-8-sig",
    )
    step_output.to_csv(
        output_root / "step_measurements_locked30.csv",
        index=False,
        encoding="utf-8-sig",
    )
    feature_output.to_csv(
        output_root / "feature_step_measurements.csv",
        index=False,
        encoding="utf-8-sig",
    )
    threshold_output.to_csv(
        output_root / "threshold_level_measurements.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pooled.to_csv(
        output_root / "summary_by_morphology_magnification.csv",
        index=False,
        encoding="utf-8-sig",
    )
    comparisons.to_csv(
        output_root / "paired_edsr_mosr_comparisons.csv",
        index=False,
        encoding="utf-8-sig",
    )
    (output_root / "qa_summary.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metadata = {
        "purpose": "Boundary-coordinate displacement validation using fixed multi-threshold isocontours",
        "measurement": (
            "For each of nine circular features, use symmetric left/right crossings at "
            "30%, 40%, 50%, 60%, and 70% local contrast on five horizontal chords; "
            "take the median threshold displacement per feature and the median across features."
        ),
        "fairness": (
            "Raw, NAFNet, EDSR, and MOSR share the same Raw-defined position windows, "
            "pre-locked 30 steps, thresholds, validity rules, and physical pixel scales."
        ),
        "position_reference": (
            "The PI platform-reported commanded step stored for each capture group is "
            "treated as the displacement reference; no method-specific calibration is applied."
        ),
        "manifest": str(manifest_path),
        "outputs": {
            "steps": "step_measurements_locked30.csv",
            "summary": "summary_by_morphology_magnification.csv",
            "comparisons": "paired_edsr_mosr_comparisons.csv",
            "qa": "qa_summary.json",
        },
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    build_report(output_root, pooled, comparisons, qa)
    print(pooled.to_string(index=False), flush=True)
    print(comparisons.to_string(index=False), flush=True)
    print(json.dumps(qa, ensure_ascii=False, indent=2), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=(
            EXPERIMENT
            / "evaluation"
            / "isocontour_boundary_validation_20260724"
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_PATH,
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(arguments.output_root.resolve(), arguments.manifest.resolve())
