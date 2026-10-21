"""Evaluate R91 stages on the locked 50x / 1 um real-motion sequence."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260811.json"
RESULTS = ROOT / "results" / "capability_diagnosis_20260811"
RECON_ROOT = RESULTS / "reconstructions_fp32"
OUTPUT = RESULTS / "motion_analysis_fp32"
TABLES = OUTPUT / "tables"
FIGURES = OUTPUT / "figures"
ISO_SCRIPT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\Modern_Restoration_Benchmarks_20260719\analyze_isocontour_boundary_displacement.py")
SEQUENCE_NAME = "50x_x_1um"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
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
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def method_paths(directory: Path, frame_count: int) -> list[Path]:
    paths = [directory / f"frame_{index:04d}.bmp" for index in range(frame_count)]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{directory}: missing {len(missing)} frame(s)")
    return paths


def locked_steps(path: Path) -> pd.DataFrame:
    selection = pd.read_csv(path)
    selected = selection.loc[
        (selection["sequence"] == SEQUENCE_NAME)
        & selection["top30_raw_motion_selected"].astype(bool)
    ].copy()
    if len(selected) != 30 or selected["end_frame_index"].duplicated().any():
        raise RuntimeError("Locked Raw step population is not 30 unique steps")
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
    steps = values["signed_step_nm"].to_numpy(float)
    errors = values["signed_error_nm"].to_numpy(float)
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
    sequence: dict[str, Any],
    iso: Any,
    selected: pd.DataFrame,
    method_dirs: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, tuple[np.ndarray, float]], pd.DataFrame]:
    raw_dir = method_dirs["Raw"]
    raw_images = iso.load_frames(raw_dir, int(sequence["frame_count"]))
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
            frame_tracking[frame_index] = (np.asarray(shifted_centers, dtype=float), float(raw_tracking.prediction_shifts[local_index]))
        for method, directory in method_dirs.items():
            images = iso.load_frames(directory, int(sequence["frame_count"]))[start_frame:end_frame + 1]
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
    table = add_physical_columns(pd.concat(all_steps, ignore_index=True), sequence)
    table = table.merge(selected, on="end_frame_index", how="left", validate="many_to_one")
    table["raw_locked_30"] = table["raw_motion_quality_rank"].notna()
    locked = table.loc[table["raw_locked_30"]]
    validity = locked.pivot_table(index="end_frame_index", columns="method", values="valid", aggfunc="first").reindex(columns=list(method_dirs))
    common = set(validity.index[validity.fillna(False).all(axis=1)].astype(int))
    table["common_valid_locked"] = table["raw_locked_30"] & table["end_frame_index"].isin(common) & table["valid"]
    summaries: list[dict[str, Any]] = []
    for method in method_dirs:
        rows = table.loc[table["method"] == method]
        summaries.append(summarize_steps(rows, method, "all_within_session"))
        summaries.append(summarize_steps(rows.loc[rows["common_valid_locked"]], method, "locked30_common_valid"))
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


def run_phase(
    sequence: dict[str, Any],
    selected: pd.DataFrame,
    method_dirs: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    selected_ids = set(selected["end_frame_index"].astype(int))
    expected_px = float(sequence["expected_signed_dx_px"])
    for method, directory in method_dirs.items():
        paths = method_paths(directory, int(sequence["frame_count"]))
        arrays = [phase_preprocess(read_gray(path)) for path in paths]
        window = cv2.createHanningWindow((arrays[0].shape[1], arrays[0].shape[0]), cv2.CV_32F)
        for index, (first, second) in enumerate(zip(arrays, arrays[1:]), start=1):
            (dx, dy), response = cv2.phaseCorrelate(first, second, window)
            rows.append({
                "method": method,
                "end_frame_index": index,
                "signed_step_px": float(dx),
                "dy_px": float(dy),
                "response": float(response),
                "valid": bool(np.isfinite(dx) and np.isfinite(dy) and response > 0),
                "raw_locked_30": index in selected_ids,
                "expected_signed_step_px": expected_px,
            })
    table = add_physical_columns(pd.DataFrame(rows), sequence)
    summaries: list[dict[str, Any]] = []
    for method in method_dirs:
        rows = table.loc[table["method"] == method]
        summaries.append(summarize_steps(rows, method, "all_adjacent_steps"))
        summaries.append(summarize_steps(rows.loc[rows["raw_locked_30"]], method, "locked30"))
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


def source_and_manifest_audit(protocol: dict[str, Any], method_dirs: dict[str, Path], frame_count: int) -> dict[str, Any]:
    arm = protocol["arms"]["real_motion"]
    mapping = pd.read_csv(arm["source_mapping"])
    rows = mapping.loc[mapping["group"] == "x_1um"].sort_values("index")
    requested = Path(arm["requested_source"])
    ordered = Path(arm["ordered_source"])
    same_files = len(rows) == frame_count
    for row in rows.itertuples(index=False):
        source = requested / str(row.original_name)
        normalized = ordered / str(row.work_name)
        same_files = same_files and source.is_file() and normalized.is_file() and source.samefile(normalized)
    stage_audit: dict[str, Any] = {}
    for method, directory in method_dirs.items():
        if method == "Raw":
            continue
        epoch = int(method.split("E")[-1])
        manifest_path = RECON_ROOT / f"E{epoch:03d}_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = sorted((row for row in manifest["records"] if row["arm"] == "motion"), key=lambda row: int(row["identity"]))
        passed = len(records) == frame_count
        for index, record in enumerate(records):
            expected_source = ordered / f"frame_{index:04d}.bmp"
            expected_output = directory / f"frame_{index:04d}.bmp"
            passed = (
                passed
                and Path(record["source"]) == expected_source
                and Path(record["output"]) == expected_output
                and sha256_file(expected_source) == record["source_sha256"]
                and sha256_file(expected_output) == record["output_sha256"]
            )
        stage_audit[method] = {"manifest": str(manifest_path), "motion_records": len(records), "hashes_and_order_pass": bool(passed)}
    return {
        "requested_and_ordered_sources_are_same_files": bool(same_files),
        "mapping_rows": int(len(rows)),
        "stage_manifests": stage_audit,
        "all_stage_manifests_pass": all(row["hashes_and_order_pass"] for row in stage_audit.values()),
    }


def make_contact_sheet(method_dirs: dict[str, Path], frame_tracking: dict[int, tuple[np.ndarray, float]]) -> Path:
    frames = [min(frame_tracking), sorted(frame_tracking)[len(frame_tracking) // 2], max(frame_tracking)]
    tiles: list[np.ndarray] = []
    for frame in frames:
        centers, shift = frame_tracking[frame]
        cx = float(np.median(centers[:, 0]) + shift)
        cy = float(np.median(centers[:, 1]))
        for method, directory in method_dirs.items():
            image = read_gray(directory / f"frame_{frame:04d}.bmp")
            x0, x1 = max(0, int(cx - 165)), min(image.shape[1], int(cx + 165))
            y0, y1 = max(0, int(cy - 140)), min(image.shape[0], int(cy + 140))
            crop = cv2.resize(image[y0:y1, x0:x1], (330, 280), interpolation=cv2.INTER_NEAREST)
            tile = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
            cv2.rectangle(tile, (0, 0), (330, 30), (255, 255, 255), -1)
            cv2.putText(tile, f"{method} frame {frame}", (7, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.53, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(tile)
    columns = len(method_dirs)
    sheet = np.vstack([np.hstack(tiles[index:index + columns]) for index in range(0, len(tiles), columns)])
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / "r91_motion_center9_contact_sheet.png"
    success, encoded = cv2.imencode(".png", sheet)
    if not success:
        raise RuntimeError(path)
    encoded.tofile(path)
    return path


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    arm = protocol["arms"]["real_motion"]
    stages = [int(value) for value in protocol["representative_stages"]["real_motion"]]
    method_dirs = {"Raw": Path(arm["ordered_source"])}
    method_dirs.update({f"R91_E{epoch}": RECON_ROOT / "motion" / f"E{epoch:03d}" for epoch in stages})
    sequence = json.loads(Path(arm["sequence_config"]).read_text(encoding="utf-8"))["sequences"][SEQUENCE_NAME]
    frame_count = int(sequence["frame_count"])
    for directory in method_dirs.values():
        method_paths(directory, frame_count)
    selected = locked_steps(Path(arm["locked_steps"]))
    audit = source_and_manifest_audit(protocol, method_dirs, frame_count)
    if not audit["requested_and_ordered_sources_are_same_files"] or not audit["all_stage_manifests_pass"]:
        raise RuntimeError(f"Motion input audit failed: {audit}")
    iso = load_module("r91_external_isocontour", ISO_SCRIPT)
    iso_steps, iso_summary, tracking, positions = run_isocontour(sequence, iso, selected, method_dirs)
    phase_steps, phase_summary = run_phase(sequence, selected, method_dirs)
    iso_summary = add_relative_columns(iso_summary)
    phase_summary = add_relative_columns(phase_summary)
    common = int(iso_steps.loc[iso_steps["common_valid_locked"], "end_frame_index"].nunique())
    if common != 30:
        raise RuntimeError(f"Only {common}/30 locked steps are common-valid")
    TABLES.mkdir(parents=True, exist_ok=True)
    iso_steps.to_csv(TABLES / "isocontour_steps.csv", index=False, encoding="utf-8-sig")
    positions.to_csv(TABLES / "isocontour_positions.csv", index=False, encoding="utf-8-sig")
    iso_summary.to_csv(TABLES / "isocontour_summary.csv", index=False, encoding="utf-8-sig")
    phase_steps.to_csv(TABLES / "gmf_like_phase_steps.csv", index=False, encoding="utf-8-sig")
    phase_summary.to_csv(TABLES / "gmf_like_phase_summary.csv", index=False, encoding="utf-8-sig")
    sheet = make_contact_sheet(method_dirs, tracking)
    payload = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "audit": audit,
        "frame_count_per_method": frame_count,
        "locked_steps": 30,
        "common_valid_locked_steps": common,
        "isocontour_summary": iso_summary.replace({np.nan: None}).to_dict(orient="records"),
        "gmf_like_phase_summary": phase_summary.replace({np.nan: None}).to_dict(orient="records"),
        "contact_sheet": str(sheet),
        "external_gmf_used": False,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(iso_summary.to_string(index=False))
    print(phase_summary.to_string(index=False))
    print(json.dumps({"status": "complete", "common_valid_locked_steps": common, "output": str(OUTPUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
