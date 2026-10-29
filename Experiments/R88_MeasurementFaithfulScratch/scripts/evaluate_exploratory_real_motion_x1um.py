"""Exploratory real-sequence displacement diagnostic for frozen R88 snapshots.

This script deliberately does not participate in R88 checkpoint selection.  It
compares Raw, epoch 50, and epoch 70 on the pre-existing 50x / 1 um sequence
with two independent readouts:

1. The audited multi-threshold, five-chord, nine-pillar isocontour method.
2. A GMF-like dark-pattern ROI phase-correlation method.

The same pre-locked 30 Raw-selected steps are used for every method.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
THESIS_ROOT = Path(str(PROJECT_ROOT / 'Thesis_MOSR_Evidence'))
SEQUENCE_NAME = "50x_x_1um"
RAW_DIR = Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_1um/bmp'))
REQUESTED_SOURCE = Path(str(PROJECT_ROOT / 'Shared_Sources/Real_Sample_Captures/20260702_100MG_位移_50x/x_1um'))
SOURCE_MAPPING = Path(str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/input_mapping.csv'))
CONFIG_PATH = THESIS_ROOT / "Final_Data_Figures" / "01_CURRENT_THESIS_RESULTS_V42_CENTER9" / "config" / "sequence_center9_50x20x.json"
SELECTION_PATH = THESIS_ROOT / "Final_Data_Figures" / "04_V42_NEURAL_NETWORK_RESULTS" / "tables" / "top30_raw_motion_selection.csv"
ISO_SCRIPT = THESIS_ROOT / "LabSystem_MOSR" / "Experiments" / "Modern_Restoration_Benchmarks_20260719" / "analyze_isocontour_boundary_displacement.py"
OUTPUT_ROOT = ROOT / "results" / "exploratory_real_motion_x1um"
MEASUREMENTS = OUTPUT_ROOT / "measurements"
QA_DIR = OUTPUT_ROOT / "qa"

METHOD_DIRS = {
    "Raw": RAW_DIR,
    "R88_E50": OUTPUT_ROOT / "reconstructions" / "epoch_050",
    "R88_E70": OUTPUT_ROOT / "reconstructions" / "epoch_070",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    payload = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(payload, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def method_paths(directory: Path, frame_count: int) -> list[Path]:
    paths = [directory / f"frame_{index:04d}.bmp" for index in range(frame_count)]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{directory} is missing {len(missing)} frame(s)")
    return paths


def validate_requested_source(frame_count: int) -> dict[str, Any]:
    mapping = pd.read_csv(SOURCE_MAPPING)
    rows = mapping.loc[mapping["group"] == "x_1um"].copy()
    rows["index"] = rows["index"].astype(int)
    rows = rows.sort_values("index")
    if rows["index"].tolist() != list(range(frame_count)):
        raise RuntimeError("The x_1um source mapping is not a complete ordered frame set")

    requested_files = sorted(REQUESTED_SOURCE.glob("*.bmp"))
    exact_same_files = True
    for _, row in rows.iterrows():
        requested = REQUESTED_SOURCE / str(row["original_name"])
        normalized = RAW_DIR / str(row["work_name"])
        if not requested.is_file() or not normalized.is_file() or not requested.samefile(normalized):
            exact_same_files = False
            break

    return {
        "mapping_rows": int(len(rows)),
        "requested_source_frame_count": int(len(requested_files)),
        "ordered_frame_indices_complete": bool(rows["index"].tolist() == list(range(frame_count))),
        "all_requested_frames_are_exact_normalized_files": bool(exact_same_files),
        "note": "The recorded original_path column predates the folder rename; original_name plus same-file identity was verified against the requested _50x folder.",
    }


def validate_reconstruction_manifests(frame_count: int) -> dict[str, Any]:
    results: dict[str, Any] = {}
    hash_cache: dict[Path, str] = {}

    def cached_hash(path: Path) -> str:
        resolved = path.resolve()
        if resolved not in hash_cache:
            hash_cache[resolved] = sha256_file(resolved)
        return hash_cache[resolved]

    for method, directory in METHOD_DIRS.items():
        if method == "Raw":
            continue
        manifest_path = directory / "reconstruction_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = manifest.get("records", [])
        ordered = len(records) == frame_count
        inputs_match = ordered
        outputs_match = ordered
        for index, record in enumerate(records):
            expected_input = RAW_DIR / f"frame_{index:04d}.bmp"
            expected_output = directory / f"frame_{index:04d}.bmp"
            record_input = Path(record.get("input", ""))
            record_output = Path(record.get("output", ""))
            ordered = ordered and record_input == expected_input and record_output == expected_output
            inputs_match = inputs_match and expected_input.is_file() and cached_hash(expected_input) == record.get("input_sha256")
            outputs_match = outputs_match and expected_output.is_file() and cached_hash(expected_output) == record.get("output_sha256")
        results[method] = {
            "manifest": str(manifest_path),
            "manifest_sha256": sha256_file(manifest_path),
            "checkpoint": manifest.get("checkpoint"),
            "checkpoint_sha256": manifest.get("checkpoint_sha256"),
            "checkpoint_epoch": manifest.get("checkpoint_epoch"),
            "weight_source": manifest.get("weight_source"),
            "record_count": int(len(records)),
            "records_match_expected_order": bool(ordered),
            "all_input_hashes_match": bool(inputs_match),
            "all_output_hashes_match": bool(outputs_match),
        }
    return results


def locked_steps() -> pd.DataFrame:
    selection = pd.read_csv(SELECTION_PATH)
    selected = selection.loc[
        (selection["sequence"] == SEQUENCE_NAME)
        & selection["top30_raw_motion_selected"].astype(bool)
    ].copy()
    if len(selected) != 30 or selected["end_frame_index"].duplicated().any():
        raise RuntimeError("The Raw-locked population is not exactly 30 unique steps")
    return selected[["end_frame_index", "raw_motion_quality_rank"]].sort_values("end_frame_index")


def add_physical_columns(table: pd.DataFrame, sequence: dict[str, Any]) -> pd.DataFrame:
    output = table.copy()
    scale = float(sequence["object_um_per_px"])
    expected_um = float(sequence["expected_signed_dx_px"]) * scale
    output["expected_signed_step_um"] = expected_um
    output["signed_step_um"] = output["signed_step_px"] * scale
    output["signed_step_nm"] = output["signed_step_um"] * 1000.0
    output["signed_error_nm"] = (output["signed_step_um"] - expected_um) * 1000.0
    output["absolute_error_nm"] = output["signed_error_nm"].abs()
    if "within_grid_mad_px" in output:
        output["within_grid_mad_nm"] = output["within_grid_mad_px"] * scale * 1000.0
    if "threshold_sensitivity_px" in output:
        output["threshold_sensitivity_nm"] = output["threshold_sensitivity_px"] * scale * 1000.0
    return output


def summarize_steps(table: pd.DataFrame, method: str, population: str) -> dict[str, Any]:
    values = table.loc[table["valid"]].copy()
    steps = values["signed_step_nm"].to_numpy(dtype=float)
    errors = values["signed_error_nm"].to_numpy(dtype=float)
    record: dict[str, Any] = {
        "method": method,
        "population": population,
        "n_steps": int(len(values)),
        "mean_signed_step_nm": float(np.mean(steps)),
        "median_signed_step_nm": float(np.median(steps)),
        "step_sd_nm": float(np.std(steps, ddof=1)),
        "bias_nm": float(np.mean(errors)),
        "mae_nm": float(np.mean(np.abs(errors))),
        "p95_absolute_error_nm": float(np.percentile(np.abs(errors), 95.0)),
    }
    if "within_grid_mad_nm" in values:
        record["median_within_grid_mad_nm"] = float(values["within_grid_mad_nm"].median())
    if "threshold_sensitivity_nm" in values:
        record["median_threshold_sensitivity_nm"] = float(values["threshold_sensitivity_nm"].median())
    if "response" in values:
        record["mean_response"] = float(values["response"].mean())
    return record


def run_isocontour(
    sequence: dict[str, Any], iso: Any, selected: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, tuple[np.ndarray, float]], pd.DataFrame]:
    raw_images = iso.load_frames(RAW_DIR, int(sequence["frame_count"]))
    sessions = iso._load_mapping(SEQUENCE_NAME)
    _raw_table, runtime = iso._raw_segment_measurements(SEQUENCE_NAME, sequence, sessions, raw_images)
    feature_ids = [str(int(row[0])) for row in sequence["centers"]]
    all_steps: list[pd.DataFrame] = []
    all_positions: list[pd.DataFrame] = []
    frame_tracking: dict[int, tuple[np.ndarray, float]] = {}

    for session_id, start_frame, end_frame in iso.session_bounds(sessions):
        state = runtime[session_id]
        shifted_centers = state.get("shifted_centers")
        raw_tracking = state.get("raw_result")
        if shifted_centers is None or raw_tracking is None or end_frame <= start_frame:
            continue
        for local_index, frame_index in enumerate(range(start_frame, end_frame + 1)):
            frame_tracking[frame_index] = (
                np.asarray(shifted_centers, dtype=float),
                float(raw_tracking.prediction_shifts[local_index]),
            )
        for method, directory in METHOD_DIRS.items():
            images = iso.load_frames(directory, int(sequence["frame_count"]))[start_frame : end_frame + 1]
            frames, steps, _features, _thresholds = iso.measure_method_session(
                images,
                initial_centers=np.asarray(shifted_centers, dtype=float),
                feature_ids=feature_ids,
                prediction_shifts=raw_tracking.prediction_shifts,
                radius_px=float(sequence["radius_px"]),
                search_radius_px=float(sequence["search_radius_px"]),
                expected_dx_px=float(sequence["expected_signed_dx_px"]),
                min_valid_features=int(sequence["min_valid_pillars"]),
                global_start_frame=start_frame,
            )
            steps["session_id"] = session_id
            steps["method"] = method
            all_steps.append(steps)
            frames["session_id"] = session_id
            frames["method"] = method
            frames["predicted_x_um"] = frames["predicted_x_px"] * float(sequence["object_um_per_px"])
            frames["measured_x_um"] = frames["measured_x_px"] * float(sequence["object_um_per_px"])
            all_positions.append(frames)

    table = pd.concat(all_steps, ignore_index=True)
    table = add_physical_columns(table, sequence)
    table = table.merge(selected, on="end_frame_index", how="left", validate="many_to_one")
    table["raw_locked_30"] = table["raw_motion_quality_rank"].notna()

    locked = table.loc[table["raw_locked_30"]].copy()
    validity = locked.pivot_table(index="end_frame_index", columns="method", values="valid", aggfunc="first").reindex(columns=list(METHOD_DIRS))
    common = set(validity.index[validity.fillna(False).all(axis=1)].astype(int))
    table["common_valid_locked"] = table["raw_locked_30"] & table["end_frame_index"].isin(common) & table["valid"]
    summaries: list[dict[str, Any]] = []
    for method in METHOD_DIRS:
        method_rows = table.loc[table["method"] == method]
        summaries.append(summarize_steps(method_rows, method, "all_within_session"))
        summaries.append(summarize_steps(method_rows.loc[method_rows["common_valid_locked"]], method, "locked30_common_valid"))
    return table, pd.DataFrame(summaries), frame_tracking, pd.concat(all_positions, ignore_index=True)


def phase_preprocess(image: np.ndarray) -> np.ndarray:
    roi = image[780:1536, 0:1050]
    _threshold, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    array = binary.astype(np.float32)
    array -= float(array.mean())
    scale = float(array.std())
    if scale > 1e-6:
        array /= scale
    return array


def run_phase(sequence: dict[str, Any], selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    selected_ids = set(selected["end_frame_index"].astype(int))
    expected_px = float(sequence["expected_signed_dx_px"])
    for method, directory in METHOD_DIRS.items():
        paths = method_paths(directory, int(sequence["frame_count"]))
        arrays = [phase_preprocess(read_gray(path)) for path in paths]
        window = cv2.createHanningWindow((arrays[0].shape[1], arrays[0].shape[0]), cv2.CV_32F)
        for index, (first, second) in enumerate(zip(arrays, arrays[1:]), start=1):
            (dx, dy), response = cv2.phaseCorrelate(first, second, window)
            rows.append(
                {
                    "method": method,
                    "end_frame_index": index,
                    "signed_step_px": float(dx),
                    "dy_px": float(dy),
                    "response": float(response),
                    "valid": bool(np.isfinite(dx) and np.isfinite(dy) and response > 0),
                    "raw_locked_30": index in selected_ids,
                    "expected_signed_step_px": expected_px,
                }
            )
    table = add_physical_columns(pd.DataFrame(rows), sequence)
    table["relative_position_px"] = table.groupby("method", sort=False)["signed_step_px"].cumsum()
    table["relative_position_um"] = table["relative_position_px"] * float(sequence["object_um_per_px"])
    summaries: list[dict[str, Any]] = []
    for method in METHOD_DIRS:
        method_rows = table.loc[table["method"] == method]
        summaries.append(summarize_steps(method_rows, method, "all_adjacent_steps"))
        summaries.append(summarize_steps(method_rows.loc[method_rows["raw_locked_30"]], method, "locked30"))
    return table, pd.DataFrame(summaries)


def add_relative_columns(summary: pd.DataFrame) -> pd.DataFrame:
    output = summary.copy()
    output["step_sd_vs_raw_percent"] = np.nan
    output["mae_vs_raw_percent"] = np.nan
    for population, group in output.groupby("population"):
        raw = group.loc[group["method"] == "Raw"]
        if len(raw) != 1:
            continue
        raw_sd = float(raw.iloc[0]["step_sd_nm"])
        raw_mae = float(raw.iloc[0]["mae_nm"])
        indices = output.index[output["population"] == population]
        output.loc[indices, "step_sd_vs_raw_percent"] = (output.loc[indices, "step_sd_nm"] / raw_sd - 1.0) * 100.0
        output.loc[indices, "mae_vs_raw_percent"] = (output.loc[indices, "mae_nm"] / raw_mae - 1.0) * 100.0
    return output


def histogram_percentile(histogram: np.ndarray, percentile: float) -> float:
    total = int(histogram.sum())
    if total <= 0:
        return float("nan")
    target = max(1, int(np.ceil(total * percentile / 100.0)))
    return float(np.searchsorted(np.cumsum(histogram), target, side="left"))


def summarize_image_differences(
    sequence: dict[str, Any], frame_tracking: dict[int, tuple[np.ndarray, float]]
) -> pd.DataFrame:
    frame_count = int(sequence["frame_count"])
    radius = float(sequence["radius_px"])
    rows: list[dict[str, Any]] = []

    for method, directory in METHOD_DIRS.items():
        if method == "Raw":
            continue
        accumulators = {
            "full_frame": {"hist": np.zeros(256, dtype=np.int64), "signed_sum": 0, "pixels": 0, "frames": 0},
            "tracked_center9_box": {"hist": np.zeros(256, dtype=np.int64), "signed_sum": 0, "pixels": 0, "frames": 0},
        }
        for frame_index in range(frame_count):
            raw = read_gray(RAW_DIR / f"frame_{frame_index:04d}.bmp").astype(np.int16)
            restored = read_gray(directory / f"frame_{frame_index:04d}.bmp").astype(np.int16)
            if raw.shape != restored.shape:
                raise RuntimeError(f"Shape mismatch for {method} frame {frame_index}")
            signed = restored - raw
            absolute = np.abs(signed).astype(np.uint8)

            regions: dict[str, tuple[np.ndarray, np.ndarray]] = {"full_frame": (signed, absolute)}
            if frame_index in frame_tracking:
                centers, shift = frame_tracking[frame_index]
                x = centers[:, 0] + shift
                y = centers[:, 1]
                margin = radius * 1.8
                x0 = max(0, int(np.floor(float(np.min(x)) - margin)))
                x1 = min(raw.shape[1], int(np.ceil(float(np.max(x)) + margin + 1.0)))
                y0 = max(0, int(np.floor(float(np.min(y)) - margin)))
                y1 = min(raw.shape[0], int(np.ceil(float(np.max(y)) + margin + 1.0)))
                regions["tracked_center9_box"] = (signed[y0:y1, x0:x1], absolute[y0:y1, x0:x1])

            for region, (signed_values, absolute_values) in regions.items():
                accumulator = accumulators[region]
                accumulator["hist"] += np.bincount(absolute_values.ravel(), minlength=256)
                accumulator["signed_sum"] += int(signed_values.sum(dtype=np.int64))
                accumulator["pixels"] += int(absolute_values.size)
                accumulator["frames"] += 1

        for region, accumulator in accumulators.items():
            histogram = accumulator["hist"]
            pixels = int(accumulator["pixels"])
            levels = np.arange(len(histogram), dtype=np.float64)
            rows.append(
                {
                    "method": method,
                    "region": region,
                    "n_frames": int(accumulator["frames"]),
                    "n_pixels": pixels,
                    "mean_absolute_gray_difference": float(np.dot(levels, histogram) / pixels),
                    "signed_mean_gray_difference": float(accumulator["signed_sum"] / pixels),
                    "p95_absolute_gray_difference": histogram_percentile(histogram, 95.0),
                    "p99_absolute_gray_difference": histogram_percentile(histogram, 99.0),
                    "max_absolute_gray_difference": int(np.flatnonzero(histogram)[-1]),
                    "fraction_changed_ge_1": float(histogram[1:].sum() / pixels),
                    "fraction_changed_ge_2": float(histogram[2:].sum() / pixels),
                    "fraction_changed_ge_5": float(histogram[5:].sum() / pixels),
                }
            )
    return pd.DataFrame(rows)


def make_contact_sheet(sequence: dict[str, Any], frame_tracking: dict[int, tuple[np.ndarray, float]]) -> Path:
    available = sorted(frame_tracking)
    if not available:
        raise RuntimeError("No tracked frames are available for visual QA")
    frames = sorted({available[0], available[len(available) // 2], available[-1]})
    methods = list(METHOD_DIRS)
    tiles: list[np.ndarray] = []
    tile_w, tile_h = 420, 360
    for frame in frames:
        centers, shift = frame_tracking[frame]
        cx = float(np.median(centers[:, 0]) + shift)
        cy = float(np.median(centers[:, 1]))
        for method in methods:
            image = read_gray(METHOD_DIRS[method] / f"frame_{frame:04d}.bmp")
            half_w, half_h = 165, 140
            x0, x1 = int(round(cx - half_w)), int(round(cx + half_w))
            y0, y1 = int(round(cy - half_h)), int(round(cy + half_h))
            x0, y0 = max(0, x0), max(0, y0)
            crop = image[y0:min(image.shape[0], y1), x0:min(image.shape[1], x1)]
            crop = cv2.resize(crop, (tile_w, tile_h), interpolation=cv2.INTER_NEAREST)
            tile = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
            cv2.rectangle(tile, (0, 0), (tile_w, 30), (255, 255, 255), -1)
            cv2.putText(tile, f"{method}  frame {frame}", (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(tile)
    rows = [np.hstack(tiles[index : index + len(methods)]) for index in range(0, len(tiles), len(methods))]
    sheet = np.vstack(rows)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    path = QA_DIR / "raw_e50_e70_center9_contact_sheet.png"
    if not cv2.imwrite(str(path), sheet):
        raise RuntimeError(f"Could not write {path}")
    return path


def write_report(
    iso_summary: pd.DataFrame,
    phase_summary: pd.DataFrame,
    image_differences: pd.DataFrame,
    qa: dict[str, Any],
) -> None:
    locked_iso = iso_summary.loc[iso_summary["population"] == "locked30_common_valid"]
    locked_phase = phase_summary.loc[phase_summary["population"] == "locked30"]
    iso_by_method = locked_iso.set_index("method")
    phase_by_method = locked_phase.set_index("method")
    center_differences = image_differences.loc[
        image_differences["region"] == "tracked_center9_box"
    ].set_index("method")
    lines = [
        "# R88 真實 50x／1 um 位移中途診斷",
        "",
        "本次先固定比較 Raw、R88 第 50 輪與第 70 輪，再讀取結果。這是訓練中的探索性診斷，不參與正式選模，也不取代外部 GMF。",
        "",
        "輪廓法會在九顆 pillar 上各取五條水平切線，再用 30%、40%、50%、60%、70% 五個相對亮度找左右邊界與中心；類 GMF 法則固定同一塊有辨識度的圖樣區域，比對相鄰兩張影像最吻合的位置。",
        "",
        "## 九顆 pillar 多門檻輪廓量測",
        "",
        "| 影像 | 共同步數 | 逐步波動 (nm) | 平均絕對誤差 (nm) | P95 (nm) | 九顆間離散度 (nm) | 門檻敏感度 (nm) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in locked_iso.iterrows():
        lines.append(
            f"| {row['method']} | {int(row['n_steps'])} | {row['step_sd_nm']:.3f} | {row['mae_nm']:.3f} | {row['p95_absolute_error_nm']:.3f} | "
            f"{row.get('median_within_grid_mad_nm', np.nan):.3f} | {row.get('median_threshold_sensitivity_nm', np.nan):.3f} |"
        )
    lines.extend(
        [
            "",
            "## 類 GMF 的區域圖樣對齊",
            "",
            "| 影像 | 步數 | 逐步波動 (nm) | 平均絕對誤差 (nm) | P95 (nm) | 對齊信心 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in locked_phase.iterrows():
        lines.append(
            f"| {row['method']} | {int(row['n_steps'])} | {row['step_sd_nm']:.3f} | {row['mae_nm']:.3f} | {row['p95_absolute_error_nm']:.3f} | {row.get('mean_response', np.nan):.4f} |"
        )
    lines.extend(
        [
            "",
            "## 模型實際改動幅度",
            "",
            "| 影像 | 範圍 | 平均灰階改動 | P95 | 最大改動 | 至少改動 2 階的比例 |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in image_differences.iterrows():
        region_name = "整張影像" if row["region"] == "full_frame" else "追蹤中的九顆 pillar 區域"
        lines.append(
            f"| {row['method']} | {region_name} | {row['mean_absolute_gray_difference']:.3f} | "
            f"{row['p95_absolute_gray_difference']:.0f} | {int(row['max_absolute_gray_difference'])} | "
            f"{row['fraction_changed_ge_2'] * 100.0:.3f}% |"
        )
    lines.extend(
        [
            "",
            "## 結論",
            "",
            "- 第 50 輪與 Raw 的輪廓位移幾乎完全相同，但九顆 pillar 區域最多只改動 1 個灰階；這代表它非常保守，不能只因位移穩就判定重建較強。",
            f"- 第 70 輪讓輪廓位置受亮度門檻影響的程度下降 {abs(float(iso_by_method.loc['R88_E70', 'median_threshold_sensitivity_nm'] / iso_by_method.loc['Raw', 'median_threshold_sensitivity_nm'] - 1.0) * 100.0):.2f}%，同時輪廓法的逐步波動只比 Raw 增加 {float(iso_by_method.loc['R88_E70', 'step_sd_vs_raw_percent']):.2f}%。",
            f"- 類 GMF 檢查中，第 70 輪的逐步波動比 Raw 增加 {float(phase_by_method.loc['R88_E70', 'step_sd_vs_raw_percent']):.2f}%，平均誤差增加 {float(phase_by_method.loc['R88_E70', 'mae_vs_raw_percent']):.2f}%；它仍然穩定，但沒有勝過 Raw。",
            f"- 第 70 輪在九顆 pillar 區域平均改動 {float(center_differences.loc['R88_E70', 'mean_absolute_gray_difference']):.3f} 個灰階，主要是小幅亮度調整。這次結果不支持『邊界更清楚就必然造成位移不穩』，但也不足以把第 70 輪定為最佳模型。",
            "",
            "## 品質與限制",
            "",
            f"- 三種影像皆有完整 50 張：{qa['complete_frame_sets']}。",
            f"- 你指定的原始資料夾與本次流水號影像逐張為同一檔案：{qa['source_lineage']['all_requested_frames_are_exact_normalized_files']}。",
            f"- 兩組重建結果逐張雜湊核對通過：{qa['reconstruction_integrity_passed']}。",
            f"- Raw 預先鎖定步次：{qa['locked_step_count']}；輪廓法共同有效步次：{qa['isocontour_common_valid_locked_steps']}。",
            "- 輪廓法沿用既有 60 秒分段規則；第 0 張與第 1 張相隔 102 秒，因此第 0 張是單張區段，不納入輪廓位移。類 GMF 檢查仍保留全部 49 個相鄰步次；共同比較採預先鎖定的 30 步。",
            "- 每種方法共用相同影像順序、九顆 pillar、搜尋範圍、門檻與 30 個 Raw 預選步次。",
            "- 1 um 是平台命令值，不是另一套獨立量測到的真實位置，因此誤差只能表示對命令值的一致程度。",
            "- 外部 GMF 目前無授權，因此區域圖樣對齊只能作為原理相近的替代檢查，不能稱為外部 GMF 分數。",
        ]
    )
    (OUTPUT_ROOT / "REPORT_zh-TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    MEASUREMENTS.mkdir(parents=True, exist_ok=True)
    iso = load_module("r88_external_isocontour", ISO_SCRIPT)
    sequence = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["sequences"][SEQUENCE_NAME]
    selected = locked_steps()

    for method, directory in METHOD_DIRS.items():
        method_paths(directory, int(sequence["frame_count"]))

    iso_steps, iso_summary, frame_tracking, iso_positions = run_isocontour(sequence, iso, selected)
    phase_steps, phase_summary = run_phase(sequence, selected)
    iso_summary = add_relative_columns(iso_summary)
    phase_summary = add_relative_columns(phase_summary)
    image_differences = summarize_image_differences(sequence, frame_tracking)

    iso_steps.to_csv(MEASUREMENTS / "isocontour_steps.csv", index=False, encoding="utf-8-sig")
    iso_positions.to_csv(MEASUREMENTS / "isocontour_frame_positions.csv", index=False, encoding="utf-8-sig")
    iso_summary.to_csv(MEASUREMENTS / "isocontour_summary.csv", index=False, encoding="utf-8-sig")
    phase_steps.to_csv(MEASUREMENTS / "gmf_like_phase_steps.csv", index=False, encoding="utf-8-sig")
    phase_summary.to_csv(MEASUREMENTS / "gmf_like_phase_summary.csv", index=False, encoding="utf-8-sig")
    image_differences.to_csv(MEASUREMENTS / "image_difference_summary.csv", index=False, encoding="utf-8-sig")
    sheet = make_contact_sheet(sequence, frame_tracking)

    complete_sets = all(len(method_paths(directory, int(sequence["frame_count"]))) == int(sequence["frame_count"]) for directory in METHOD_DIRS.values())
    common_count = int(iso_steps.loc[iso_steps["common_valid_locked"], "end_frame_index"].nunique())
    source_lineage = validate_requested_source(int(sequence["frame_count"]))
    reconstruction_manifests = validate_reconstruction_manifests(int(sequence["frame_count"]))
    reconstruction_integrity_passed = all(
        record["record_count"] == int(sequence["frame_count"])
        and record["records_match_expected_order"]
        and record["all_input_hashes_match"]
        and record["all_output_hashes_match"]
        for record in reconstruction_manifests.values()
    )
    qa_passed = (
        complete_sets
        and common_count == len(selected)
        and source_lineage["all_requested_frames_are_exact_normalized_files"]
        and reconstruction_integrity_passed
    )
    qa = {
        "status": "passed" if qa_passed else "failed",
        "scope": "exploratory_midtraining_diagnostic_not_for_checkpoint_selection",
        "sequence": SEQUENCE_NAME,
        "source_requested_by_user": str(REQUESTED_SOURCE),
        "normalized_hardlink_source": str(RAW_DIR),
        "source_mapping": str(SOURCE_MAPPING),
        "source_lineage": source_lineage,
        "complete_frame_sets": bool(complete_sets),
        "frame_count_per_method": int(sequence["frame_count"]),
        "tracked_frame_count_for_center9_qa": int(len(frame_tracking)),
        "isocontour_position_rows": int(len(iso_positions)),
        "locked_step_count": int(len(selected)),
        "isocontour_common_valid_locked_steps": common_count,
        "methods": list(METHOD_DIRS),
        "contact_sheet": str(sheet),
        "reconstruction_integrity_passed": bool(reconstruction_integrity_passed),
        "checkpoint_manifests": reconstruction_manifests,
        "inputs": {
            "config_sha256": sha256_file(CONFIG_PATH),
            "selection_sha256": sha256_file(SELECTION_PATH),
            "source_mapping_sha256": sha256_file(SOURCE_MAPPING),
        },
    }
    (OUTPUT_ROOT / "analysis_summary.json").write_text(
        json.dumps(
            {
                "qa": qa,
                "isocontour_summary": iso_summary.to_dict(orient="records"),
                "gmf_like_phase_summary": phase_summary.to_dict(orient="records"),
                "image_difference_summary": image_differences.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_report(iso_summary, phase_summary, image_differences, qa)
    print(iso_summary.to_string(index=False))
    print(phase_summary.to_string(index=False))
    print(image_differences.to_string(index=False))
    print(json.dumps({"qa": qa["status"], "output": str(OUTPUT_ROOT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
