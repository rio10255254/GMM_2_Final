from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from pillar_motion_core import TrackerConfig, track_pillar_grid
PROJECT_ROOT = Path(__file__).resolve().parents[5]


EXPECTED_SEQUENCE_KEYS = {
    "50x_x_0p5um",
    "50x_x_1um",
    "20x_0p5um",
    "20x_1um",
    "5x_0p5um",
    "5x_1um",
}
EXPECTED_PILLAR_IDS = {22, 23, 24, 28, 29, 30, 34, 35, 36}
SUBPIXEL_ERROR_LIMIT_PX = {"50x": 0.08, "20x": 0.10, "5x": 0.10}


def build_expected_filenames(sequence: dict[str, Any]) -> list[str]:
    frame_count = int(sequence["frame_count"])
    if frame_count < 2:
        raise ValueError("frame_count must be at least two")
    names = [f"frame_{index:04d}.bmp" for index in range(frame_count)]
    if names[0] != str(sequence["first_frame"]):
        raise ValueError("first_frame does not match frame_count convention")
    if names[-1] != str(sequence["last_frame"]):
        raise ValueError("last_frame does not match frame_count convention")
    return names


def _validate_sequence(sequence_key: str, sequence: dict[str, Any]) -> None:
    required = {
        "raw_dir",
        "v42_dir",
        "frame_count",
        "first_frame",
        "last_frame",
        "object_um_per_px",
        "nominal_step_um",
        "expected_signed_dx_px",
        "polarity",
        "radius_px",
        "pitch_px",
        "search_radius_px",
        "min_valid_pillars",
        "min_edge_strength",
        "centers",
    }
    missing = sorted(required - set(sequence))
    if missing:
        raise ValueError(f"{sequence_key}: missing fields {missing}")

    centers = sequence["centers"]
    if len(centers) != 9:
        raise ValueError(f"{sequence_key}: exactly nine centers are required")
    ids = [int(row[0]) for row in centers]
    if set(ids) != EXPECTED_PILLAR_IDS or len(set(ids)) != 9:
        raise ValueError(f"{sequence_key}: center identities do not match SEM center nine")
    coordinates = np.asarray([[float(row[1]), float(row[2])] for row in centers])
    if coordinates.shape != (9, 2) or not np.isfinite(coordinates).all():
        raise ValueError(f"{sequence_key}: invalid center coordinates")

    pitch = float(sequence["pitch_px"])
    search = float(sequence["search_radius_px"])
    expected = float(sequence["expected_signed_dx_px"])
    if not np.isfinite([pitch, search, expected]).all() or pitch <= 0 or search <= 0:
        raise ValueError(f"{sequence_key}: invalid motion geometry")
    if search >= pitch * 0.5:
        raise ValueError(f"{sequence_key}: search window reaches half a pitch")
    if abs(expected) >= pitch * 0.5:
        raise ValueError(f"{sequence_key}: expected step reaches half a pitch")
    build_expected_filenames(sequence)


def load_locked_config(path: str | Path, *, verify_files: bool) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("locked_before_v42_measurement") is not True:
        raise ValueError("sequence configuration is not prelocked")
    sequences = config.get("sequences")
    if not isinstance(sequences, dict) or set(sequences) != EXPECTED_SEQUENCE_KEYS:
        raise ValueError("configuration must contain exactly the six locked sequences")

    for key, sequence in sequences.items():
        _validate_sequence(key, sequence)
        if not verify_files:
            continue
        names = build_expected_filenames(sequence)
        for case_key in ("raw_dir", "v42_dir"):
            directory = Path(sequence[case_key])
            if not directory.is_dir():
                raise FileNotFoundError(f"{key}: missing {case_key}: {directory}")
            missing = [name for name in names if not (directory / name).is_file()]
            if missing:
                preview = ", ".join(missing[:3])
                raise FileNotFoundError(
                    f"{key}: {case_key} is missing {len(missing)} locked frames: {preview}"
                )
    return config


def _read_grayscale(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"could not decode image: {path}")
    return image


def _tracker_config(sequence: dict[str, Any]) -> TrackerConfig:
    return TrackerConfig(
        radius_px=float(sequence["radius_px"]),
        pitch_px=float(sequence["pitch_px"]),
        polarity=str(sequence["polarity"]),
        search_radius_px=float(sequence["search_radius_px"]),
        min_valid_pillars=int(sequence["min_valid_pillars"]),
        min_edge_strength=float(sequence["min_edge_strength"]),
        max_chord_mad_px=(
            None
            if sequence.get("max_chord_mad_px") is None
            else float(sequence["max_chord_mad_px"])
        ),
    )


def _initial_centers(sequence: dict[str, Any]) -> list[tuple[str, float, float]]:
    return [
        (str(int(pillar_id)), float(x_px), float(y_px))
        for pillar_id, x_px, y_px in sequence["centers"]
    ]


def validate_real_crop_subpixel(
    sequence_key: str,
    sequence: dict[str, Any],
    *,
    known_shifts_px: Iterable[float],
    prediction_factors: Iterable[float] = (0.0, -0.7, 0.7),
    image_case: str = "Raw",
) -> pd.DataFrame:
    _validate_sequence(sequence_key, sequence)
    first_name = build_expected_filenames(sequence)[0]
    case_to_directory = {"Raw": "raw_dir", "V42 epoch 120": "v42_dir"}
    if image_case not in case_to_directory:
        raise ValueError("image_case must be 'Raw' or 'V42 epoch 120'")
    source_path = Path(PROJECT_ROOT / sequence[case_to_directory[image_case]]) / first_name
    source = _read_grayscale(source_path)
    config = _tracker_config(sequence)
    centers = _initial_centers(sequence)
    records: list[dict[str, Any]] = []

    for known_shift in known_shifts_px:
        shift = float(known_shift)
        if not np.isfinite(shift):
            raise ValueError("known shifts must be finite")
        transform = np.asarray([[1.0, 0.0, shift], [0.0, 1.0, 0.0]], dtype=np.float32)
        shifted = cv2.warpAffine(
            source,
            transform,
            (source.shape[1], source.shape[0]),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        for factor_value in prediction_factors:
            factor = float(factor_value)
            if not np.isfinite(factor):
                raise ValueError("prediction factors must be finite")
            prediction = factor * shift
            result = track_pillar_grid(
                [source, shifted],
                centers,
                config=config,
                expected_step_dx_px=prediction,
            )
            row = result.steps.iloc[0]
            estimated = (
                float(row["consensus_dx_px"]) if bool(row["analysis_valid"]) else np.nan
            )
            mode = (
                "zero"
                if factor == 0.0
                else ("wrong_direction" if factor < 0.0 else "partial_correct_direction")
            )
            records.append(
                {
                    "sequence": sequence_key,
                    "image_case": image_case,
                    "known_shift_px": shift,
                    "prediction_factor": factor,
                    "prediction_mode": mode,
                    "prediction_px": prediction,
                    "estimated_shift_px": estimated,
                    "abs_error_px": (
                        abs(estimated - shift) if np.isfinite(estimated) else np.nan
                    ),
                    "analysis_valid": bool(row["analysis_valid"]),
                    "valid_pillars": int(row["valid_pillars"]),
                }
            )
    return pd.DataFrame(records)


def evaluate_subpixel_validation(
    validation: pd.DataFrame,
    *,
    maximum_error_px: float,
) -> dict[str, Any]:
    limit = float(maximum_error_px)
    if not np.isfinite(limit) or limit <= 0:
        raise ValueError("maximum_error_px must be finite and positive")
    required = int(len(validation))
    if required == 0:
        raise ValueError("subpixel validation table is empty")
    errors = validation["abs_error_px"].to_numpy(dtype=float)
    valid = validation["analysis_valid"].astype(bool).to_numpy()
    passed = valid & np.isfinite(errors) & (errors <= limit)
    finite_errors = errors[np.isfinite(errors)]
    return {
        "available": bool(passed.all()),
        "required_trials": required,
        "passed_trials": int(passed.sum()),
        "maximum_error_px": float(np.max(finite_errors)) if finite_errors.size else np.nan,
        "allowed_error_px": limit,
    }


def apply_common_valid_population(
    case_steps: pd.DataFrame,
    comparison: pd.DataFrame,
    *,
    case_suffix: str | None = None,
) -> pd.DataFrame:
    if comparison["step_index"].duplicated().any():
        raise ValueError("comparison contains duplicate step indices")
    common = comparison.set_index("step_index")["common_valid"].astype(bool)
    result = case_steps.copy()
    common_mask = result["step_index"].map(common).fillna(False).astype(bool)
    result["analysis_valid"] = result["analysis_valid"].astype(bool) & common_mask
    if case_suffix is not None:
        if case_suffix not in {"raw", "v42"}:
            raise ValueError("case_suffix must be 'raw' or 'v42'")
        comparison_by_step = comparison.set_index("step_index")
        replacement_columns = {
            "consensus_dx_px": f"consensus_dx_px_{case_suffix}",
            "within_grid_disagreement_px": (
                f"within_grid_disagreement_px_{case_suffix}"
            ),
            "pillar_step_sd_px": f"pillar_step_sd_px_{case_suffix}",
            "consensus_dx_um": f"consensus_dx_um_{case_suffix}",
            "step_magnitude_um": f"step_magnitude_um_{case_suffix}",
            "within_grid_disagreement_nm": (
                f"within_grid_disagreement_nm_{case_suffix}"
            ),
        }
        for target, source in replacement_columns.items():
            if source not in comparison_by_step:
                raise ValueError(f"comparison is missing {source}")
            result[target] = result["step_index"].map(comparison_by_step[source])
    measurement_columns = [
        "consensus_dx_px",
        "within_grid_disagreement_px",
        "pillar_step_sd_px",
        "consensus_dx_um",
        "step_magnitude_um",
        "within_grid_disagreement_nm",
    ]
    for column in measurement_columns:
        if column in result:
            result.loc[~result["analysis_valid"], column] = np.nan
    return result


def build_common_pillar_comparison(
    raw_pillar_steps: pd.DataFrame,
    v42_pillar_steps: pd.DataFrame,
    *,
    frame_count: int,
    min_common_pillars: int,
    object_um_per_px: float,
) -> pd.DataFrame:
    minimum = int(min_common_pillars)
    if not 1 <= minimum <= 9:
        raise ValueError("min_common_pillars must be in 1..9")
    scale = float(object_um_per_px)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("object_um_per_px must be finite and positive")
    required = {"step_index", "pillar_id", "pillar_valid", "pillar_dx_px"}
    for label, table in (("Raw", raw_pillar_steps), ("V42", v42_pillar_steps)):
        missing = required - set(table)
        if missing:
            raise ValueError(f"{label} pillar table missing {sorted(missing)}")
        if table.duplicated(["step_index", "pillar_id"]).any():
            raise ValueError(f"{label} pillar table contains duplicate identities")
        counts = table.groupby("step_index").size()
        expected_steps = list(range(1, int(frame_count)))
        if counts.index.astype(int).tolist() != expected_steps or not (counts == 9).all():
            raise ValueError(f"{label} pillar table must contain nine rows for every step")

    raw = raw_pillar_steps.loc[:, sorted(required)].copy()
    v42 = v42_pillar_steps.loc[:, sorted(required)].copy()
    raw["pillar_id"] = raw["pillar_id"].astype(str)
    v42["pillar_id"] = v42["pillar_id"].astype(str)
    merged = raw.merge(
        v42,
        on=["step_index", "pillar_id"],
        how="inner",
        suffixes=("_raw", "_v42"),
        validate="one_to_one",
    )
    records: list[dict[str, Any]] = []
    for step_index in range(1, int(frame_count)):
        step = merged.loc[merged["step_index"] == step_index].copy()
        common_mask = (
            step["pillar_valid_raw"].astype(bool)
            & step["pillar_valid_v42"].astype(bool)
            & np.isfinite(step["pillar_dx_px_raw"].to_numpy(dtype=float))
            & np.isfinite(step["pillar_dx_px_v42"].to_numpy(dtype=float))
        )
        common = step.loc[common_mask].copy()
        common = common.sort_values("pillar_id", key=lambda values: values.astype(int))
        common_count = int(len(common))
        valid = bool(common_count >= minimum)
        record: dict[str, Any] = {
            "step_index": int(step_index),
            "common_valid": valid,
            "analysis_valid_raw": valid,
            "analysis_valid_v42": valid,
            "common_pillars": common_count,
            "common_pillar_ids": ";".join(common["pillar_id"].tolist()),
        }
        for suffix in ("raw", "v42"):
            values = common[f"pillar_dx_px_{suffix}"].to_numpy(dtype=float)
            if valid:
                consensus = float(np.median(values))
                residual = values - consensus
                disagreement = float(1.4826 * np.median(np.abs(residual)))
                step_sd = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            else:
                consensus = np.nan
                disagreement = np.nan
                step_sd = np.nan
            record[f"consensus_dx_px_{suffix}"] = consensus
            record[f"within_grid_disagreement_px_{suffix}"] = disagreement
            record[f"pillar_step_sd_px_{suffix}"] = step_sd
            record[f"consensus_dx_um_{suffix}"] = consensus * scale
            record[f"step_magnitude_um_{suffix}"] = abs(consensus * scale)
            record[f"within_grid_disagreement_nm_{suffix}"] = (
                disagreement * scale * 1000.0
            )
        records.append(record)
    return pd.DataFrame(records)


def _load_locked_images(directory: str | Path, names: Iterable[str]) -> list[np.ndarray]:
    root = Path(directory)
    images: list[np.ndarray] = []
    for name in names:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        images.append(_read_grayscale(path))
    return images


def _annotate_tracking_table(
    table: pd.DataFrame,
    *,
    sequence_key: str,
    case: str,
    object_um_per_px: float,
    prediction_source: str,
) -> pd.DataFrame:
    annotated = table.copy()
    annotated.insert(0, "sequence", sequence_key)
    annotated.insert(1, "case", case)
    annotated.insert(2, "prediction_source", prediction_source)
    scale = float(object_um_per_px)
    if "consensus_dx_px" in annotated:
        annotated["consensus_dx_um"] = annotated["consensus_dx_px"] * scale
        annotated["step_magnitude_um"] = annotated["consensus_dx_um"].abs()
    if "within_grid_disagreement_px" in annotated:
        annotated["within_grid_disagreement_nm"] = (
            annotated["within_grid_disagreement_px"] * scale * 1000.0
        )
    if "pillar_dx_px" in annotated:
        annotated["pillar_dx_um"] = annotated["pillar_dx_px"] * scale
    if "within_grid_residual_px" in annotated:
        annotated["within_grid_residual_nm"] = (
            annotated["within_grid_residual_px"] * scale * 1000.0
        )
    return annotated


def _compare_case_steps(
    raw_steps: pd.DataFrame,
    v42_steps: pd.DataFrame,
    *,
    frame_count: int,
) -> pd.DataFrame:
    assert_complete_step_schedule(raw_steps, frame_count=frame_count, label="Raw")
    assert_complete_step_schedule(v42_steps, frame_count=frame_count, label="V42")
    schedule = pd.DataFrame({"step_index": np.arange(1, int(frame_count), dtype=int)})
    raw = raw_steps.drop(columns=["sequence", "case"], errors="ignore")
    v42 = v42_steps.drop(columns=["sequence", "case"], errors="ignore")
    comparison = schedule.merge(raw, on="step_index", how="left").merge(
        v42,
        on="step_index",
        how="left",
        suffixes=("_raw", "_v42"),
    )
    raw_valid = comparison["analysis_valid_raw"].fillna(False).astype(bool)
    v42_valid = comparison["analysis_valid_v42"].fillna(False).astype(bool)
    comparison.insert(1, "common_valid", raw_valid & v42_valid)
    return comparison


def assert_complete_step_schedule(
    steps: pd.DataFrame,
    *,
    frame_count: int,
    label: str,
) -> None:
    if "step_index" not in steps:
        raise ValueError(f"{label}: step_index is missing")
    if steps["step_index"].duplicated().any():
        raise ValueError(f"{label}: duplicate step indices")
    expected = list(range(1, int(frame_count)))
    actual = steps["step_index"].astype(int).tolist()
    if actual != expected:
        raise ValueError(
            f"{label}: rows must match the complete scheduled step range 1..{frame_count - 1}"
        )


def run_locked_sequence(
    sequence_key: str,
    sequence: dict[str, Any],
    *,
    prediction_mode: str = "raw_guided",
) -> dict[str, Any]:
    _validate_sequence(sequence_key, sequence)
    names = build_expected_filenames(sequence)
    config = _tracker_config(sequence)
    centers = _initial_centers(sequence)
    scale = float(sequence["object_um_per_px"])
    expected = float(sequence["expected_signed_dx_px"])
    valid_modes = {"raw_guided", "fixed_nominal", "v42_guided"}
    if prediction_mode not in valid_modes:
        raise ValueError(f"prediction_mode must be one of {sorted(valid_modes)}")

    if prediction_mode == "raw_guided":
        raw_images = _load_locked_images(sequence["raw_dir"], names)
        raw_result = track_pillar_grid(
            raw_images,
            centers,
            config=config,
            expected_step_dx_px=expected,
        )
        del raw_images
        v42_images = _load_locked_images(sequence["v42_dir"], names)
        v42_result = track_pillar_grid(
            v42_images,
            centers,
            config=config,
            expected_step_dx_px=expected,
            shared_prediction_shifts=raw_result.prediction_shifts,
        )
        del v42_images
        raw_prediction_source = "raw_adaptive_from_previous_measurement"
        v42_prediction_source = "shared_raw_prediction_path"
    elif prediction_mode == "fixed_nominal":
        fixed_path = tuple(expected * index for index in range(len(names)))
        raw_images = _load_locked_images(sequence["raw_dir"], names)
        raw_result = track_pillar_grid(
            raw_images,
            centers,
            config=config,
            expected_step_dx_px=expected,
            shared_prediction_shifts=fixed_path,
        )
        del raw_images
        v42_images = _load_locked_images(sequence["v42_dir"], names)
        v42_result = track_pillar_grid(
            v42_images,
            centers,
            config=config,
            expected_step_dx_px=expected,
            shared_prediction_shifts=fixed_path,
        )
        del v42_images
        raw_prediction_source = "shared_fixed_nominal_path"
        v42_prediction_source = "shared_fixed_nominal_path"
    else:
        v42_images = _load_locked_images(sequence["v42_dir"], names)
        v42_result = track_pillar_grid(
            v42_images,
            centers,
            config=config,
            expected_step_dx_px=expected,
        )
        del v42_images
        raw_images = _load_locked_images(sequence["raw_dir"], names)
        raw_result = track_pillar_grid(
            raw_images,
            centers,
            config=config,
            expected_step_dx_px=expected,
            shared_prediction_shifts=v42_result.prediction_shifts,
        )
        del raw_images
        raw_prediction_source = "shared_v42_prediction_path"
        v42_prediction_source = "v42_adaptive_from_previous_measurement"

    raw_frames = _annotate_tracking_table(
        raw_result.frames,
        sequence_key=sequence_key,
        case="Raw",
        object_um_per_px=scale,
        prediction_source=raw_prediction_source,
    )
    v42_frames = _annotate_tracking_table(
        v42_result.frames,
        sequence_key=sequence_key,
        case="V42 epoch 120",
        object_um_per_px=scale,
        prediction_source=v42_prediction_source,
    )
    raw_steps = _annotate_tracking_table(
        raw_result.steps,
        sequence_key=sequence_key,
        case="Raw",
        object_um_per_px=scale,
        prediction_source=raw_prediction_source,
    )
    v42_steps = _annotate_tracking_table(
        v42_result.steps,
        sequence_key=sequence_key,
        case="V42 epoch 120",
        object_um_per_px=scale,
        prediction_source=v42_prediction_source,
    )
    raw_pillars = _annotate_tracking_table(
        raw_result.pillar_steps,
        sequence_key=sequence_key,
        case="Raw",
        object_um_per_px=scale,
        prediction_source=raw_prediction_source,
    )
    v42_pillars = _annotate_tracking_table(
        v42_result.pillar_steps,
        sequence_key=sequence_key,
        case="V42 epoch 120",
        object_um_per_px=scale,
        prediction_source=v42_prediction_source,
    )
    comparison = build_common_pillar_comparison(
        raw_pillars,
        v42_pillars,
        frame_count=int(sequence["frame_count"]),
        min_common_pillars=int(sequence["min_valid_pillars"]),
        object_um_per_px=scale,
    )
    comparison.insert(0, "sequence", sequence_key)
    return {
        "prediction_mode": prediction_mode,
        "filenames": names,
        "raw_frames": raw_frames,
        "v42_frames": v42_frames,
        "raw_steps": raw_steps,
        "v42_steps": v42_steps,
        "raw_pillar_steps": raw_pillars,
        "v42_pillar_steps": v42_pillars,
        "comparison": comparison,
        "raw_prediction_shifts": tuple(raw_result.prediction_shifts),
        "v42_prediction_shifts": tuple(v42_result.prediction_shifts),
    }


def _identity_crop_bounds(
    image: np.ndarray,
    centers: list[tuple[str, float, float]],
    radius_px: float,
) -> tuple[int, int, int, int]:
    margin = max(8.0, float(radius_px) * 2.4)
    xs = np.asarray([center[1] for center in centers], dtype=float)
    ys = np.asarray([center[2] for center in centers], dtype=float)
    x0 = max(0, int(np.floor(xs.min() - margin)))
    x1 = min(image.shape[1], int(np.ceil(xs.max() + margin)) + 1)
    y0 = max(0, int(np.floor(ys.min() - margin)))
    y1 = min(image.shape[0], int(np.ceil(ys.max() + margin)) + 1)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("identity crop does not intersect the image")
    return x0, x1, y0, y1


def _plot_identity_overlay(
    sequence_key: str,
    sequence: dict[str, Any],
    output_path: Path,
) -> None:
    first_name = build_expected_filenames(sequence)[0]
    raw = _read_grayscale(Path(sequence["raw_dir"]) / first_name)
    v42 = _read_grayscale(Path(sequence["v42_dir"]) / first_name)
    if raw.shape != v42.shape:
        raise ValueError(f"{sequence_key}: Raw and V42 frame shapes differ")
    centers = _initial_centers(sequence)
    x0, x1, y0, y1 = _identity_crop_bounds(raw, centers, float(sequence["radius_px"]))

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    axes[0].imshow(raw, cmap="gray", vmin=0, vmax=255)
    axes[0].add_patch(
        Rectangle(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            fill=False,
            edgecolor="#e63946",
            linewidth=1.7,
        )
    )
    axes[0].set_title("Raw frame 0: locked center-nine area")
    axes[0].set_axis_off()

    for axis, image, title in (
        (axes[1], raw, "Raw: exact SEM identities"),
        (axes[2], v42, "V42 epoch 120: same identities"),
    ):
        axis.imshow(image[y0:y1, x0:x1], cmap="gray", vmin=0, vmax=255)
        for pillar_id, x_px, y_px in centers:
            local_x = x_px - x0
            local_y = y_px - y0
            axis.scatter(
                [local_x],
                [local_y],
                s=48,
                facecolors="none",
                edgecolors="#ffd166",
                linewidths=1.4,
            )
            axis.text(
                local_x + 2,
                local_y - 2,
                f"P{pillar_id}",
                color="#00e5ff",
                fontsize=8,
                weight="bold",
            )
        axis.set_title(title)
        axis.set_axis_off()
    fig.suptitle(f"{sequence_key}: prelocked physical-center pillars", fontsize=13)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_step_trace(
    sequence_key: str,
    sequence: dict[str, Any],
    result: dict[str, Any],
    output_path: Path,
) -> None:
    fig, axis = plt.subplots(figsize=(11, 5.6), constrained_layout=True)
    styles = {
        "Raw": ("#d62728", "s"),
        "V42 epoch 120": ("#1f77b4", "o"),
    }
    expected_signed_um = (
        float(sequence["expected_signed_dx_px"]) * float(sequence["object_um_per_px"])
    )
    axis.axhline(
        expected_signed_um,
        color="#333333",
        linestyle="--",
        linewidth=1.2,
        label=f"Signed nominal command ({expected_signed_um:g} um)",
    )
    for key, label in (("raw_steps", "Raw"), ("v42_steps", "V42 epoch 120")):
        table = result[key]
        color, marker = styles[label]
        valid = table["analysis_valid"].astype(bool)
        axis.plot(
            table.loc[valid, "step_index"],
            table.loc[valid, "consensus_dx_um"],
            color=color,
            marker=marker,
            markersize=3.8,
            linewidth=1.0,
            label=f"{label} valid ({int(valid.sum())}/{len(table)})",
        )
        if (~valid).any():
            axis.scatter(
                table.loc[~valid, "step_index"],
                np.full(int((~valid).sum()), expected_signed_um),
                color=color,
                marker="x",
                s=38,
                linewidths=1.4,
                label=f"{label} rejected",
            )
    axis.set_xlabel("Consecutive step index")
    axis.set_ylabel("Signed measured step (um)")
    axis.set_title(f"{sequence_key}: all scheduled consecutive steps")
    axis.grid(True, alpha=0.25)
    axis.legend(ncol=2, fontsize=8)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_residuals(
    sequence_key: str,
    result: dict[str, Any],
    output_path: Path,
) -> None:
    tables = [result["raw_pillar_steps"], result["v42_pillar_steps"]]
    labels = ["Raw", "V42 epoch 120"]
    matrices: list[pd.DataFrame] = []
    all_values: list[np.ndarray] = []
    for table in tables:
        matrix = table.pivot(
            index="pillar_id",
            columns="step_index",
            values="within_grid_residual_nm",
        ).sort_index(key=lambda values: values.astype(int))
        matrices.append(matrix)
        finite = matrix.to_numpy(dtype=float)
        all_values.append(finite[np.isfinite(finite)])
    finite_values = np.concatenate([values for values in all_values if values.size])
    limit = max(1.0, float(np.max(np.abs(finite_values)))) if finite_values.size else 1.0

    cmap = plt.get_cmap("coolwarm").copy()
    cmap.set_bad("#d9d9d9")
    fig, axes = plt.subplots(2, 1, figsize=(12, 6.8), constrained_layout=True)
    image_handle = None
    for axis, matrix, label in zip(axes, matrices, labels):
        image_handle = axis.imshow(
            np.ma.masked_invalid(matrix.to_numpy(dtype=float)),
            aspect="auto",
            interpolation="nearest",
            cmap=cmap,
            vmin=-limit,
            vmax=limit,
        )
        axis.set_yticks(np.arange(len(matrix.index)))
        axis.set_yticklabels([f"P{value}" for value in matrix.index])
        columns = matrix.columns.to_numpy(dtype=int)
        if len(columns):
            tick_indices = np.linspace(0, len(columns) - 1, min(10, len(columns)), dtype=int)
            axis.set_xticks(tick_indices)
            axis.set_xticklabels(columns[tick_indices])
        axis.set_ylabel(label)
    axes[-1].set_xlabel("Consecutive step index")
    fig.suptitle(
        f"{sequence_key}: pillar residual from nine-pillar common motion\n"
        "Gray cells were rejected; both cases use the same color scale",
        fontsize=12,
    )
    if image_handle is not None:
        colorbar = fig.colorbar(image_handle, ax=axes, shrink=0.9)
        colorbar.set_label("Within-grid residual (nm)")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def write_sequence_outputs(
    sequence_key: str,
    sequence: dict[str, Any],
    result: dict[str, Any],
    *,
    output_root: str | Path,
) -> dict[str, Path]:
    root = Path(output_root)
    table_dir = root / "tables"
    figure_dir = root / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    frames_csv = table_dir / f"{sequence_key}_frames.csv"
    steps_csv = table_dir / f"{sequence_key}_steps.csv"
    pillar_steps_csv = table_dir / f"{sequence_key}_pillar_steps.csv"
    comparison_csv = table_dir / f"{sequence_key}_comparison.csv"
    pd.concat([result["raw_frames"], result["v42_frames"]], ignore_index=True).to_csv(
        frames_csv, index=False
    )
    pd.concat([result["raw_steps"], result["v42_steps"]], ignore_index=True).to_csv(
        steps_csv, index=False
    )
    pd.concat(
        [result["raw_pillar_steps"], result["v42_pillar_steps"]], ignore_index=True
    ).to_csv(pillar_steps_csv, index=False)
    result["comparison"].to_csv(comparison_csv, index=False)

    identity_overlay = figure_dir / f"{sequence_key}_identity_overlay.png"
    step_trace = figure_dir / f"{sequence_key}_step_trace.png"
    residual_figure = figure_dir / f"{sequence_key}_within_grid_residuals.png"
    _plot_identity_overlay(sequence_key, sequence, identity_overlay)
    _plot_step_trace(sequence_key, sequence, result, step_trace)
    _plot_residuals(sequence_key, result, residual_figure)
    return {
        "frames_csv": frames_csv,
        "steps_csv": steps_csv,
        "pillar_steps_csv": pillar_steps_csv,
        "comparison_csv": comparison_csv,
        "identity_overlay": identity_overlay,
        "step_trace": step_trace,
        "residual_figure": residual_figure,
    }


def _summaries_for_sequence(
    sequence_key: str,
    sequence: dict[str, Any],
    result: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    scale = float(sequence["object_um_per_px"])
    nominal = float(sequence["nominal_step_um"])
    expected = float(sequence["expected_signed_dx_px"])
    for population in ("case_valid", "common_valid"):
        for table_key, case in (("raw_steps", "Raw"), ("v42_steps", "V42 epoch 120")):
            table = result[table_key]
            if population == "common_valid":
                table = apply_common_valid_population(
                    table,
                    result["comparison"],
                    case_suffix=("raw" if case == "Raw" else "v42"),
                )
            summary = summarize_case_steps(
                table,
                case=case,
                object_um_per_px=scale,
                nominal_step_um=nominal,
                expected_signed_dx_px=expected,
                scheduled_steps=int(sequence["frame_count"]) - 1,
            )
            summary.update(
                {
                    "sequence": sequence_key,
                    "dataset": sequence.get("dataset", ""),
                    "group": sequence.get("group", sequence_key),
                    "magnification": sequence.get("magnification", ""),
                    "population": population,
                    "measurement_status": "available",
                }
            )
            records.append(summary)
    return records


def _build_comparison_summary(summary: pd.DataFrame) -> pd.DataFrame:
    common = summary.loc[summary["population"] == "common_valid"].copy()
    records: list[dict[str, Any]] = []
    metrics = [
        "scheduled_steps",
        "valid_steps",
        "coverage_pct",
        "mean_step_magnitude_um",
        "step_magnitude_sd_nm",
        "signed_step_sd_nm",
        "wrong_direction_steps",
        "wrong_direction_pct",
        "magnitude_bias_to_nominal_nm",
        "rmse_to_nominal_command_nm",
        "mean_within_grid_disagreement_nm",
    ]
    for sequence_key, group in common.groupby("sequence", sort=False):
        raw = group.loc[group["case"] == "Raw"]
        v42 = group.loc[group["case"] == "V42 epoch 120"]
        if len(raw) != 1 or len(v42) != 1:
            raise ValueError(f"{sequence_key}: expected one common-valid summary per case")
        raw_row = raw.iloc[0]
        v42_row = v42.iloc[0]
        record: dict[str, Any] = {
            "sequence": sequence_key,
            "magnification": raw_row["magnification"],
            "nominal_step_um": raw_row["nominal_step_um"],
        }
        for metric in metrics:
            record[f"raw_{metric}"] = raw_row[metric]
            record[f"v42_{metric}"] = v42_row[metric]
        raw_sd = float(raw_row["signed_step_sd_nm"])
        v42_sd = float(v42_row["signed_step_sd_nm"])
        raw_grid = float(raw_row["mean_within_grid_disagreement_nm"])
        v42_grid = float(v42_row["mean_within_grid_disagreement_nm"])
        record["v42_step_sd_reduction_nm"] = raw_sd - v42_sd
        record["v42_step_sd_reduction_pct"] = (
            100.0 * (raw_sd - v42_sd) / raw_sd if np.isfinite(raw_sd) and raw_sd > 0 else np.nan
        )
        record["v42_within_grid_reduction_nm"] = raw_grid - v42_grid
        record["v42_within_grid_reduction_pct"] = (
            100.0 * (raw_grid - v42_grid) / raw_grid
            if np.isfinite(raw_grid) and raw_grid > 0
            else np.nan
        )
        records.append(record)
    return pd.DataFrame(records)


def _plot_subpixel_validation(validation: pd.DataFrame, output_path: Path) -> None:
    grouped = validation.groupby("sequence", sort=False).agg(
        maximum_error_px=("abs_error_px", "max"),
        allowed_error_px=("allowed_error_px", "first"),
        all_trials_passed=("trial_passed", "all"),
    )
    labels = grouped.index.tolist()
    errors = grouped["maximum_error_px"].to_numpy(dtype=float)
    limits = grouped["allowed_error_px"].to_numpy(dtype=float)
    passed = grouped["all_trials_passed"].astype(bool).to_numpy()
    colors = np.where(passed, "#2a9d8f", "#d62828")
    fig, axis = plt.subplots(figsize=(13, 5.6), constrained_layout=True)
    x = np.arange(len(grouped))
    axis.bar(x, errors, color=colors, width=0.72, label="Absolute recovery error")
    axis.scatter(x, limits, color="#222222", marker="_", s=180, label="Allowed limit")
    axis.set_xticks(x)
    axis.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    axis.set_ylabel("Absolute error (px)")
    axis.set_title(
        "Detector-only validation: digital shifts applied after Raw/V42 reconstruction\n"
        "Zero, wrong-direction, and partial correct-direction predictions"
    )
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def prediction_mode_comparable(
    valid_steps: int,
    scheduled_steps: int,
    *,
    minimum_coverage: float = 0.80,
) -> bool:
    scheduled = int(scheduled_steps)
    valid = int(valid_steps)
    if scheduled <= 0 or valid < 0 or valid > scheduled:
        raise ValueError("invalid prediction-mode coverage counts")
    if not 0.0 < float(minimum_coverage) <= 1.0:
        raise ValueError("minimum_coverage must be in (0, 1]")
    return bool(valid / scheduled >= float(minimum_coverage))


def _plot_cross_sequence_summary(summary: pd.DataFrame, output_path: Path) -> None:
    labels = summary["sequence"].tolist()
    x = np.arange(len(labels), dtype=float)
    width = 0.36
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.2), constrained_layout=True)
    pairs = [
        (
            axes[0],
            "raw_signed_step_sd_nm",
            "v42_signed_step_sd_nm",
            "Signed step-to-step standard deviation (nm)",
        ),
        (
            axes[1],
            "raw_mean_within_grid_disagreement_nm",
            "v42_mean_within_grid_disagreement_nm",
            "Mean nine-pillar disagreement (nm)",
        ),
    ]
    for axis, raw_column, v42_column, ylabel in pairs:
        axis.bar(x - width / 2, summary[raw_column], width, color="#d62728", label="Raw")
        axis.bar(
            x + width / 2,
            summary[v42_column],
            width,
            color="#1f77b4",
            label="V42 epoch 120",
        )
        axis.set_ylabel(ylabel)
        axis.set_xticks(x)
        axis.set_xticklabels(labels, rotation=20, ha="right")
        axis.grid(axis="y", alpha=0.25)
        axis.legend()
    fig.suptitle("Physical-center nine-pillar displacement comparison (common valid steps)")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def run_all_sequences(
    config_path: str | Path,
    *,
    output_root: str | Path,
) -> dict[str, Path]:
    config = load_locked_config(config_path, verify_files=True)
    root = Path(output_root)
    table_dir = root / "tables"
    figure_dir = root / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    validation_tables: list[pd.DataFrame] = []
    availability: dict[str, dict[str, Any]] = {}
    for sequence_key, sequence in config["sequences"].items():
        magnification = str(sequence["magnification"])
        limit = min(
            SUBPIXEL_ERROR_LIMIT_PX[magnification],
            0.10
            * float(sequence["nominal_step_um"])
            / float(sequence["object_um_per_px"]),
        )
        case_tables = [
            validate_real_crop_subpixel(
                sequence_key,
                sequence,
                known_shifts_px=(-0.37, 0.29),
                image_case=image_case,
            )
            for image_case in ("Raw", "V42 epoch 120")
        ]
        validation = pd.concat(case_tables, ignore_index=True)
        status = evaluate_subpixel_validation(validation, maximum_error_px=limit)
        validation["allowed_error_px"] = limit
        validation["trial_passed"] = (
            validation["analysis_valid"].astype(bool)
            & np.isfinite(validation["abs_error_px"])
            & (validation["abs_error_px"] <= limit)
        )
        validation["sequence_available"] = bool(status["available"])
        validation_tables.append(validation)
        availability[sequence_key] = status
    validation_all = pd.concat(validation_tables, ignore_index=True)
    validation_csv = table_dir / "real_crop_subpixel_validation.csv"
    validation_all.to_csv(validation_csv, index=False)
    _plot_subpixel_validation(
        validation_all,
        figure_dir / "real_crop_subpixel_validation.png",
    )

    all_frames: list[pd.DataFrame] = []
    all_steps: list[pd.DataFrame] = []
    all_pillar_steps: list[pd.DataFrame] = []
    all_comparisons: list[pd.DataFrame] = []
    summary_records: list[dict[str, Any]] = []
    for sequence_key, sequence in config["sequences"].items():
        if not availability[sequence_key]["available"]:
            continue
        result = run_locked_sequence(sequence_key, sequence)
        write_sequence_outputs(sequence_key, sequence, result, output_root=root)
        all_frames.extend([result["raw_frames"], result["v42_frames"]])
        all_steps.extend([result["raw_steps"], result["v42_steps"]])
        all_pillar_steps.extend(
            [result["raw_pillar_steps"], result["v42_pillar_steps"]]
        )
        all_comparisons.append(result["comparison"])
        summary_records.extend(_summaries_for_sequence(sequence_key, sequence, result))

    if len(summary_records) != len(config["sequences"]) * 4:
        unavailable = [key for key, status in availability.items() if not status["available"]]
        raise RuntimeError(
            "one or more prelocked sequences failed real-crop validation; "
            f"no substitute ROI was used: {unavailable}"
        )

    combined_paths = {
        "frames": table_dir / "all_frames.csv",
        "steps": table_dir / "all_steps.csv",
        "pillar_steps": table_dir / "all_pillar_steps.csv",
        "comparison": table_dir / "all_raw_v42_step_comparisons.csv",
        "summary": table_dir / "sequence_summary_long.csv",
        "comparison_summary": table_dir / "raw_v42_common_valid_summary.csv",
        "validation": validation_csv,
    }
    pd.concat(all_frames, ignore_index=True).to_csv(combined_paths["frames"], index=False)
    pd.concat(all_steps, ignore_index=True).to_csv(combined_paths["steps"], index=False)
    pd.concat(all_pillar_steps, ignore_index=True).to_csv(
        combined_paths["pillar_steps"], index=False
    )
    pd.concat(all_comparisons, ignore_index=True).to_csv(
        combined_paths["comparison"], index=False
    )
    summary = pd.DataFrame(summary_records)
    summary.to_csv(combined_paths["summary"], index=False)
    comparison_summary = _build_comparison_summary(summary)
    comparison_summary.to_csv(combined_paths["comparison_summary"], index=False)
    _plot_cross_sequence_summary(
        comparison_summary,
        figure_dir / "raw_v42_cross_sequence_summary.png",
    )

    metadata = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "config_path": str(Path(config_path).resolve()),
        "selection_rule": config["selection_rule"],
        "primary_population": config["primary_population"],
        "case_rule": config["case_rule"],
        "rejection_rule": config["rejection_rule"],
        "stage_truth_limit": config["stage_truth_limit"],
        "prediction_asymmetry": (
            "The primary prelocked design uses Raw-adaptive prediction windows and applies "
            "that same path to V42. This is explicit and is not a symmetric blind tracker."
        ),
        "subpixel_validation": availability,
        "claim_limit": (
            "SEM supplies pillar identity and diameter truth. Commanded stage motion is a "
            "nominal reference, not independent displacement ground truth."
        ),
    }
    metadata_path = root / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    combined_paths["metadata"] = metadata_path
    return combined_paths


def _plot_prediction_sensitivity(summary: pd.DataFrame, output_path: Path) -> None:
    common = summary.loc[summary["population"] == "common_valid"].copy()
    sequence_order = list(dict.fromkeys(common["sequence"].tolist()))
    mode_order = ["raw_guided", "fixed_nominal", "v42_guided"]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), constrained_layout=True)
    for axis, sequence_key in zip(axes.flat, sequence_order):
        group = common.loc[common["sequence"] == sequence_key]
        raw = (
            group.loc[group["case"] == "Raw"]
            .set_index("prediction_mode")
            .reindex(mode_order)
        )
        v42 = (
            group.loc[group["case"] == "V42 epoch 120"]
            .set_index("prediction_mode")
            .reindex(mode_order)
        )
        comparable_by_mode: dict[str, bool] = {}
        for mode in mode_order:
            valid_count = min(
                int(raw.loc[mode, "valid_steps"]),
                int(v42.loc[mode, "valid_steps"]),
            )
            scheduled_count = int(raw.loc[mode, "scheduled_steps"])
            comparable_by_mode[mode] = prediction_mode_comparable(
                valid_count,
                scheduled_count,
            )
            if not comparable_by_mode[mode]:
                raw.loc[mode, "signed_step_sd_nm"] = np.nan
                v42.loc[mode, "signed_step_sd_nm"] = np.nan
        x = np.arange(len(mode_order), dtype=float)
        width = 0.36
        axis.bar(
            x - width / 2,
            raw["signed_step_sd_nm"],
            width,
            color="#d62728",
            label="Raw",
        )
        axis.bar(
            x + width / 2,
            v42["signed_step_sd_nm"],
            width,
            color="#1f77b4",
            label="V42 epoch 120",
        )
        axis.set_xticks(x)
        axis.set_xticklabels(["Raw guided", "Fixed", "V42 guided"], rotation=16)
        axis.margins(x=0.18)
        axis.set_title(sequence_key)
        axis.set_ylabel("Signed step SD (nm)")
        axis.grid(axis="y", alpha=0.25)
        any_comparable = any(comparable_by_mode.values())
        if any_comparable:
            axis.legend(fontsize=8)
        else:
            axis.set_ylim(0.0, 1.0)
            axis.set_yticks([])
            axis.set_ylabel("Insufficient coverage")
            axis.grid(False)
        for index, mode in enumerate(mode_order):
            if not comparable_by_mode[mode]:
                valid_count = min(
                    int(
                        group.loc[
                            (group["prediction_mode"] == mode)
                            & (group["case"] == "Raw"),
                            "valid_steps",
                        ].iloc[0]
                    ),
                    int(
                        group.loc[
                            (group["prediction_mode"] == mode)
                            & (group["case"] == "V42 epoch 120"),
                            "valid_steps",
                        ].iloc[0]
                    ),
                )
                scheduled_count = int(
                    group.loc[
                        (group["prediction_mode"] == mode)
                        & (group["case"] == "Raw"),
                        "scheduled_steps",
                    ].iloc[0]
                )
                axis.text(
                    ([0.18, 1.0, 1.82][index] if not any_comparable else index),
                    (0.50 if not any_comparable else 0.04),
                    f"Not comparable\n{valid_count}/{scheduled_count}",
                    transform=axis.get_xaxis_transform(),
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="#7f0000",
                    weight="bold",
                )
    fig.suptitle("Sensitivity to prediction-window source (same center-nine identities)")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def run_prediction_sensitivity(
    config_path: str | Path,
    *,
    output_root: str | Path,
) -> dict[str, Path]:
    config = load_locked_config(config_path, verify_files=True)
    root = Path(output_root)
    table_dir = root / "tables"
    figure_dir = root / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    modes = ("raw_guided", "fixed_nominal", "v42_guided")
    summary_records: list[dict[str, Any]] = []
    comparison_tables: list[pd.DataFrame] = []
    for sequence_key, sequence in config["sequences"].items():
        for mode in modes:
            result = run_locked_sequence(
                sequence_key,
                sequence,
                prediction_mode=mode,
            )
            records = _summaries_for_sequence(sequence_key, sequence, result)
            for record in records:
                record["prediction_mode"] = mode
            summary_records.extend(records)
            comparison = result["comparison"].copy()
            comparison.insert(1, "prediction_mode", mode)
            comparison_tables.append(comparison)

    summary = pd.DataFrame(summary_records)
    comparisons = pd.concat(comparison_tables, ignore_index=True)
    common = summary.loc[summary["population"] == "common_valid"].copy()
    range_summary = (
        common.groupby(["sequence", "case"], sort=False)
        .agg(
            valid_steps_min=("valid_steps", "min"),
            valid_steps_max=("valid_steps", "max"),
            mean_signed_step_um_min=("mean_signed_step_um", "min"),
            mean_signed_step_um_max=("mean_signed_step_um", "max"),
            signed_step_sd_nm_min=("signed_step_sd_nm", "min"),
            signed_step_sd_nm_max=("signed_step_sd_nm", "max"),
            within_grid_nm_min=("mean_within_grid_disagreement_nm", "min"),
            within_grid_nm_max=("mean_within_grid_disagreement_nm", "max"),
        )
        .reset_index()
    )
    range_summary["mean_signed_step_range_nm"] = (
        range_summary["mean_signed_step_um_max"]
        - range_summary["mean_signed_step_um_min"]
    ) * 1000.0
    range_summary["signed_step_sd_range_nm"] = (
        range_summary["signed_step_sd_nm_max"]
        - range_summary["signed_step_sd_nm_min"]
    )
    range_summary["within_grid_range_nm"] = (
        range_summary["within_grid_nm_max"] - range_summary["within_grid_nm_min"]
    )

    advantage_records: list[dict[str, Any]] = []
    for (sequence_key, mode), group in common.groupby(
        ["sequence", "prediction_mode"], sort=False
    ):
        raw = group.loc[group["case"] == "Raw"].iloc[0]
        v42 = group.loc[group["case"] == "V42 epoch 120"].iloc[0]
        advantage_records.append(
            {
                "sequence": sequence_key,
                "prediction_mode": mode,
                "common_valid_steps": int(raw["valid_steps"]),
                "scheduled_steps": int(raw["scheduled_steps"]),
                "mode_comparable": prediction_mode_comparable(
                    int(raw["valid_steps"]),
                    int(raw["scheduled_steps"]),
                ),
                "raw_signed_step_sd_nm": raw["signed_step_sd_nm"],
                "v42_signed_step_sd_nm": v42["signed_step_sd_nm"],
                "v42_signed_sd_reduction_nm": (
                    raw["signed_step_sd_nm"] - v42["signed_step_sd_nm"]
                ),
                "raw_within_grid_nm": raw["mean_within_grid_disagreement_nm"],
                "v42_within_grid_nm": v42["mean_within_grid_disagreement_nm"],
                "v42_within_grid_reduction_nm": (
                    raw["mean_within_grid_disagreement_nm"]
                    - v42["mean_within_grid_disagreement_nm"]
                ),
            }
        )
    advantage = pd.DataFrame(advantage_records)

    paths = {
        "summary": table_dir / "prediction_mode_summary_long.csv",
        "comparisons": table_dir / "prediction_mode_step_comparisons.csv",
        "range_summary": table_dir / "prediction_mode_metric_ranges.csv",
        "advantage": table_dir / "prediction_mode_raw_v42_advantage.csv",
        "figure": figure_dir / "prediction_mode_signed_sd.png",
    }
    summary.to_csv(paths["summary"], index=False)
    comparisons.to_csv(paths["comparisons"], index=False)
    range_summary.to_csv(paths["range_summary"], index=False)
    advantage.to_csv(paths["advantage"], index=False)
    _plot_prediction_sensitivity(summary, paths["figure"])
    return paths


def main() -> None:
    package_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run the prelocked SEM-anchored center-nine displacement validation."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=package_root / "config" / "sequence_center9.json",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=package_root / "displacement",
    )
    args = parser.parse_args()
    paths = run_all_sequences(args.config, output_root=args.output_root)
    summary = pd.read_csv(paths["comparison_summary"])
    print(summary.to_string(index=False))
    print(f"\nOutputs: {args.output_root.resolve()}")


def summarize_case_steps(
    steps: pd.DataFrame,
    *,
    case: str,
    object_um_per_px: float,
    nominal_step_um: float,
    expected_signed_dx_px: float,
    scheduled_steps: int | None = None,
) -> dict[str, Any]:
    scheduled = int(len(steps) if scheduled_steps is None else scheduled_steps)
    if scheduled == 0:
        raise ValueError("steps table is empty")
    if scheduled_steps is not None:
        assert_complete_step_schedule(
            steps,
            frame_count=scheduled + 1,
            label=f"{case} summary",
        )
    scale = float(object_um_per_px)
    nominal = float(nominal_step_um)
    expected_px = float(expected_signed_dx_px)
    if not np.isfinite([scale, nominal, expected_px]).all() or scale <= 0 or nominal <= 0:
        raise ValueError("physical scale and nominal step must be finite and positive")

    valid_mask = steps["analysis_valid"].astype(bool) & np.isfinite(
        steps["consensus_dx_px"].to_numpy(dtype=float)
    )
    valid_steps = steps.loc[valid_mask]
    valid_count = int(len(valid_steps))
    signed_um = valid_steps["consensus_dx_px"].to_numpy(dtype=float) * scale
    magnitude_um = np.abs(signed_um)
    disagreement_nm = (
        valid_steps["within_grid_disagreement_px"].to_numpy(dtype=float) * scale * 1000.0
    )
    expected_signed_um = expected_px * scale
    wrong_direction = (
        signed_um * expected_signed_um <= 0.0
        if signed_um.size
        else np.asarray([], dtype=bool)
    )

    def finite_mean(values: np.ndarray) -> float:
        finite = values[np.isfinite(values)]
        return float(np.mean(finite)) if finite.size else np.nan

    return {
        "case": str(case),
        "scheduled_steps": scheduled,
        "valid_steps": valid_count,
        "rejected_steps": scheduled - valid_count,
        "coverage_pct": 100.0 * valid_count / scheduled,
        "mean_signed_step_um": finite_mean(signed_um),
        "mean_step_magnitude_um": finite_mean(magnitude_um),
        "step_magnitude_sd_nm": (
            float(np.std(magnitude_um, ddof=1) * 1000.0)
            if magnitude_um.size > 1
            else (0.0 if magnitude_um.size == 1 else np.nan)
        ),
        "signed_step_sd_nm": (
            float(np.std(signed_um, ddof=1) * 1000.0)
            if signed_um.size > 1
            else (0.0 if signed_um.size == 1 else np.nan)
        ),
        "wrong_direction_steps": int(wrong_direction.sum()),
        "wrong_direction_pct": (
            100.0 * float(wrong_direction.sum()) / valid_count if valid_count else np.nan
        ),
        "signed_bias_to_nominal_command_nm": (
            finite_mean(signed_um - expected_signed_um) * 1000.0
            if signed_um.size
            else np.nan
        ),
        "magnitude_bias_to_nominal_nm": (
            finite_mean(magnitude_um - nominal) * 1000.0
            if magnitude_um.size
            else np.nan
        ),
        "rmse_to_nominal_command_nm": (
            float(np.sqrt(np.mean(np.square(signed_um - expected_signed_um))) * 1000.0)
            if signed_um.size
            else np.nan
        ),
        "mean_within_grid_disagreement_nm": finite_mean(disagreement_nm),
        "object_um_per_px": scale,
        "nominal_step_um": nominal,
        "expected_signed_dx_px": expected_px,
    }


if __name__ == "__main__":
    main()
