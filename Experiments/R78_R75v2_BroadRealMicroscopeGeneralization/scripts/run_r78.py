from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
LOCKED_RAW = ROOT / "inputs" / "locked_raw"
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
R75_RECON = RESULTS / "reconstructions" / "R75v2E100"
REPORT = ROOT / "reports" / "R78_RESULTS_TW.md"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = sha256(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(f"Locked source changed: {path}\nexpected={expected}\nactual={actual}")


def image_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("frame_*.bmp"))


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not decode image: {path}")
    return image


def hardlink_or_copy(source: Path, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != source.stat().st_size:
            raise RuntimeError(f"Existing locked input differs in size: {target}")
        return "existing"
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def prepare_locked_inputs(config: dict) -> dict:
    locked = config["locked_r68_evidence"]
    require_hash(Path(PROJECT_ROOT / locked["config"]), locked["config_sha256"])
    require_hash(Path(PROJECT_ROOT / locked["measurements"]), locked["measurements_sha256"])
    require_hash(Path(PROJECT_ROOT / locked["summary"]), locked["summary_sha256"])
    require_hash(Path(PROJECT_ROOT / config["r75v2"]["checkpoint"]), config["r75v2"]["checkpoint_sha256"])
    require_hash(
        Path(PROJECT_ROOT / config["acm_sem_evidence"]["per_pillar_summary"]),
        config["acm_sem_evidence"]["per_pillar_summary_sha256"],
    )

    r77_decision = read_json(Path(PROJECT_ROOT / config["acm_sem_evidence"]["decision"]))
    if r77_decision.get("status") != "complete":
        raise RuntimeError("R77 ACM/SEM evidence is not complete")
    acm_table = pd.read_csv(str(PROJECT_ROOT / config["acm_sem_evidence"]["per_pillar_summary"]))
    if len(acm_table) != 36 or acm_table["pillar_id"].nunique() != 36:
        raise RuntimeError("R77 ACM/SEM evidence does not contain 36 independent pillars")

    audit = {
        "experiment_id": config["experiment_id"],
        "eligibility_lock": config["eligibility_lock"],
        "source_hashes_verified": True,
        "r75v2_checkpoint": str(Path(PROJECT_ROOT / config["r75v2"]["checkpoint"]).resolve()),
        "r75v2_checkpoint_sha256": config["r75v2"]["checkpoint_sha256"],
        "r61_checkpoint": str(Path(PROJECT_ROOT / config["r61"]["checkpoint"]).resolve()),
        "total_frames": 0,
        "sequences": {},
        "locked_input_materialization": {"hardlink": 0, "copy": 0, "existing": 0},
        "acm_sem_arm": {"pillars": 36, "exposures": 12, "status": "complete"},
    }

    r61_checkpoint = Path(PROJECT_ROOT / config["r61"]["checkpoint"]).resolve()
    for name, item in config["sequences"].items():
        raw = image_paths(Path(PROJECT_ROOT / item["raw_dir"]))
        r61 = image_paths(Path(PROJECT_ROOT / item["r61_dir"]))
        expected = int(item["frame_count"])
        if len(raw) != expected or len(r61) != expected:
            raise RuntimeError(f"{name}: expected {expected}; Raw={len(raw)}, R61={len(r61)}")
        if [p.name for p in raw] != [p.name for p in r61]:
            raise RuntimeError(f"{name}: Raw and R61 filenames do not match")

        manifest = read_json(Path(PROJECT_ROOT / item["r61_manifest"]))
        if Path(manifest["weights"]).resolve() != r61_checkpoint:
            raise RuntimeError(f"{name}: R61 reconstruction used another checkpoint")
        command = [str(value).lower() for value in manifest.get("command", [])]
        if "--no-psf-from-ckpt" not in command or "--weak-psf-disable" not in command:
            raise RuntimeError(f"{name}: R61 reconstruction is not in the locked real-sample mode")

        for source in raw:
            mode = hardlink_or_copy(source, LOCKED_RAW / name / source.name)
            audit["locked_input_materialization"][mode] += 1

        raw_shape = list(read_gray(raw[0]).shape)
        r61_shape = list(read_gray(r61[0]).shape)
        if raw_shape != [1536, 2048] or r61_shape != raw_shape:
            raise RuntimeError(f"{name}: unexpected image shapes {raw_shape} / {r61_shape}")
        audit["sequences"][name] = {
            "frames": expected,
            "raw_dir": str(Path(PROJECT_ROOT / item["raw_dir"]).resolve()),
            "r61_dir": str(Path(PROJECT_ROOT / item["r61_dir"]).resolve()),
            "locked_raw_dir": str((LOCKED_RAW / name).resolve()),
            "filenames_match": True,
            "shape": raw_shape,
            "r61_checkpoint_match": True,
            "r61_real_sample_mode": True,
        }
        audit["total_frames"] += expected

    if audit["total_frames"] != 301:
        raise RuntimeError(f"Expected 301 frames, found {audit['total_frames']}")
    write_json(RESULTS / "input_audit.json", audit)
    return audit


def valid_r75_manifest(config: dict) -> bool:
    manifest_path = R75_RECON / "inference_manifest.json"
    if not manifest_path.is_file():
        return False
    manifest = read_json(manifest_path)
    return (
        int(manifest.get("image_count", -1)) == 301
        and manifest.get("checkpoint_sha256", "").lower()
        == config["r75v2"]["checkpoint_sha256"].lower()
        and manifest.get("state_key") == "ema_state_dict"
    )


def run_inference(config: dict) -> None:
    if valid_r75_manifest(config):
        print("[infer] verified R75-v2 output already exists; skipping", flush=True)
        return
    if R75_RECON.exists() and any(R75_RECON.rglob("*.bmp")):
        raise RuntimeError(f"Partial or mismatched output exists; inspect before rerun: {R75_RECON}")
    R75_RECON.mkdir(parents=True, exist_ok=True)
    settings = config["r75v2"]
    command = [
        sys.executable,
        str(Path(PROJECT_ROOT / settings["inference_script"])),
        "--checkpoint",
        str(Path(PROJECT_ROOT / settings["checkpoint"])),
        "--input",
        str(LOCKED_RAW),
        "--output",
        str(R75_RECON),
        "--device",
        str(settings["device"]),
        "--tile-size",
        str(settings["tile_size"]),
        "--overlap",
        str(settings["overlap"]),
    ]
    print("[infer] reconstructing 301 locked real microscope frames", flush=True)
    subprocess.run(command, check=True)


def validate_outputs(config: dict) -> dict:
    if not valid_r75_manifest(config):
        raise RuntimeError("R75-v2 inference manifest is missing or does not match epoch 100 EMA weights")
    manifest = read_json(R75_RECON / "inference_manifest.json")
    audit = read_json(RESULTS / "input_audit.json")
    checked = 0
    for name, item in config["sequences"].items():
        raw = image_paths(Path(PROJECT_ROOT / item["raw_dir"]))
        r75 = image_paths(R75_RECON / name)
        expected = int(item["frame_count"])
        if len(r75) != expected or [p.name for p in raw] != [p.name for p in r75]:
            raise RuntimeError(f"{name}: Raw/R75 output coverage mismatch")
        for raw_path, r75_path in zip(raw, r75):
            if read_gray(raw_path).shape != read_gray(r75_path).shape:
                raise RuntimeError(f"Shape mismatch: {r75_path}")
            checked += 1
        audit["sequences"][name]["r75v2_frames"] = expected
        audit["sequences"][name]["r75v2_filenames_match"] = True
        audit["sequences"][name]["r75v2_shapes_match"] = True
    if checked != 301 or int(manifest["image_count"]) != checked:
        raise RuntimeError("R75-v2 output count is not 301")
    audit["r75v2_output_validation"] = {
        "frames_checked": checked,
        "manifest_checkpoint_match": True,
        "ema_weights": True,
        "all_filenames_match": True,
        "all_shapes_match": True,
    }
    write_json(RESULTS / "input_audit.json", audit)
    return audit


def edge_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    edge -= float(edge.mean())
    std = float(edge.std())
    return edge / std if std > 1e-6 else edge


def phase_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    a_edge, b_edge = edge_image(a), edge_image(b)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a_edge, b_edge, window)
    return float(dx), float(dy), float(response)


def bounded_ecc_shift(
    a: np.ndarray, b: np.ndarray, initial_dx: float, initial_dy: float
) -> tuple[float, float, float]:
    a_float = cv2.GaussianBlur(a.astype(np.float32) / 255.0, (0, 0), 1.0)
    b_float = cv2.GaussianBlur(b.astype(np.float32) / 255.0, (0, 0), 1.0)
    warp = np.array([[1.0, 0.0, initial_dx], [0.0, 1.0, initial_dy]], dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-6)
    correlation, refined = cv2.findTransformECC(
        a_float, b_float, warp, cv2.MOTION_TRANSLATION, criteria, None, 1
    )
    return float(refined[0, 2]), float(refined[1, 2]), float(correlation)


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().eq("true")


def standardized_r61_rows(locked: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(
        {
            "sequence": locked["sequence"],
            "method": "R61v16",
            "magnification": locked["magnification"],
            "nominal_step_um": locked["nominal_step_um"],
            "object_um_per_px": locked["object_um_per_px"],
            "expected_dx_px": locked["expected_dx_px"],
            "step_index": locked["step_index"],
            "time_gap_s": locked["time_gap_s"],
            "tile_id": locked["tile_id"],
            "tile_row": locked["tile_row"],
            "tile_column": locked["tile_column"],
            "edge_score": locked["edge_score"],
            "raw_dx_px": locked["raw_dx_px"],
            "raw_dy_px": locked["raw_dy_px"],
            "raw_response": locked["raw_response"],
            "model_phase_dx_px": locked["r61_phase_dx_px"],
            "model_phase_dy_px": locked["r61_phase_dy_px"],
            "model_response": locked["r61_response"],
            "model_dx_px": locked["r61_dx_px"],
            "model_dy_px": locked["r61_dy_px"],
            "model_ecc": locked["r61_ecc"],
            "raw_reference_valid": as_bool(locked["raw_reference_valid"]),
            "model_evaluable": as_bool(locked["r61_evaluable"]),
            "valid": as_bool(locked["valid"]),
            "direction_agreement": as_bool(locked["direction_agreement"]),
            "model_over_raw_abs_dx": locked["r61_over_raw_abs_dx"],
            "vector_difference_um": locked["r61_raw_vector_difference_um"],
        }
    )
    return output


def compute_r75_rows(config: dict, locked: pd.DataFrame) -> pd.DataFrame:
    records: list[dict] = []
    grid = config["tile_grid"]
    tile_h, tile_w = 1536 // int(grid["rows"]), 2048 // int(grid["columns"])
    for sequence, sequence_rows in locked.groupby("sequence", sort=False):
        print(f"[motion] {sequence}", flush=True)
        recon = image_paths(R75_RECON / sequence)
        for step_index, step_rows in sequence_rows.groupby("step_index", sort=True):
            index = int(step_index)
            rec_a, rec_b = read_gray(recon[index]), read_gray(recon[index + 1])
            for _, row in step_rows.iterrows():
                tile_row, tile_column = int(row["tile_row"]), int(row["tile_column"])
                y0, x0 = tile_row * tile_h, tile_column * tile_w
                tile_a = rec_a[y0 : y0 + tile_h, x0 : x0 + tile_w]
                tile_b = rec_b[y0 : y0 + tile_h, x0 : x0 + tile_w]
                phase_dx, phase_dy, response = phase_shift(tile_a, tile_b)
                try:
                    dx, dy, ecc = bounded_ecc_shift(
                        tile_a, tile_b, float(row["raw_dx_px"]), float(row["raw_dy_px"])
                    )
                    ecc_ok = math.isfinite(ecc)
                except cv2.error:
                    dx, dy, ecc, ecc_ok = math.nan, math.nan, math.nan, False
                expected_px = float(row["expected_dx_px"])
                shift_limit = max(12.0, expected_px * 2.5)
                raw_valid = bool(row["raw_reference_valid"])
                evaluable = bool(
                    ecc_ok
                    and ecc >= 0.75
                    and abs(dx) <= shift_limit
                    and abs(dy) <= shift_limit
                )
                valid = raw_valid and evaluable
                raw_dx, raw_dy = float(row["raw_dx_px"]), float(row["raw_dy_px"])
                direction = bool(np.sign(raw_dx) == np.sign(dx)) if valid and abs(raw_dx) > 0.05 and abs(dx) > 0.05 else False
                object_um_per_px = float(row["object_um_per_px"])
                difference_um = math.hypot(dx - raw_dx, dy - raw_dy) * object_um_per_px if valid else math.nan
                scale = abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan
                records.append(
                    {
                        "sequence": sequence,
                        "method": "R75v2E100",
                        "magnification": float(row["magnification"]),
                        "nominal_step_um": float(row["nominal_step_um"]),
                        "object_um_per_px": object_um_per_px,
                        "expected_dx_px": expected_px,
                        "step_index": index,
                        "time_gap_s": row["time_gap_s"],
                        "tile_id": row["tile_id"],
                        "tile_row": tile_row,
                        "tile_column": tile_column,
                        "edge_score": float(row["edge_score"]),
                        "raw_dx_px": raw_dx,
                        "raw_dy_px": raw_dy,
                        "raw_response": float(row["raw_response"]),
                        "model_phase_dx_px": phase_dx,
                        "model_phase_dy_px": phase_dy,
                        "model_response": response,
                        "model_dx_px": dx,
                        "model_dy_px": dy,
                        "model_ecc": ecc,
                        "raw_reference_valid": raw_valid,
                        "model_evaluable": evaluable,
                        "valid": valid,
                        "direction_agreement": direction,
                        "model_over_raw_abs_dx": scale,
                        "vector_difference_um": difference_um,
                    }
                )
    return pd.DataFrame(records)


def summarize_motion(table: pd.DataFrame, gates: dict) -> pd.DataFrame:
    summaries = []
    for (sequence, method), group in table.groupby(["sequence", "method"], sort=False):
        reference = group.loc[group["raw_reference_valid"]].copy()
        valid = group.loc[group["valid"]].copy()
        if reference.empty or valid.empty:
            raise RuntimeError(f"{sequence}/{method}: no valid measurements")
        response_ratio = valid["model_response"] / valid["raw_response"].clip(lower=1e-9)
        scale = float(valid["model_over_raw_abs_dx"].median())
        row = {
            "sequence": sequence,
            "method": method,
            "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
            "selected_tiles": int(group["tile_id"].nunique()),
            "used_steps": int(group["step_index"].nunique()),
            "tile_measurements": int(len(group)),
            "raw_reference_measurements": int(len(reference)),
            "raw_reference_fraction": float(group["raw_reference_valid"].mean()),
            "valid_measurements": int(len(valid)),
            "valid_fraction": float(len(valid) / len(reference)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
            "median_model_over_raw_abs_dx": scale,
            "median_scale_error_fraction": abs(scale - 1.0),
            "median_vector_difference_um": float(valid["vector_difference_um"].median()),
            "p95_vector_difference_um": float(valid["vector_difference_um"].quantile(0.95)),
            "median_difference_of_step": float(
                valid["vector_difference_um"].median() / valid["nominal_step_um"].iloc[0]
            ),
            "p95_difference_of_step": float(
                valid["vector_difference_um"].quantile(0.95) / valid["nominal_step_um"].iloc[0]
            ),
            "median_response_ratio": float(response_ratio.median()),
            "median_model_ecc": float(valid["model_ecc"].median()),
            "raw_median_abs_dx_um": float(
                valid["raw_dx_px"].abs().median() * valid["object_um_per_px"].iloc[0]
            ),
            "model_median_abs_dx_um": float(
                valid["model_dx_px"].abs().median() * valid["object_um_per_px"].iloc[0]
            ),
        }
        row["pass_valid_fraction"] = row["valid_fraction"] >= gates["minimum_valid_fraction"]
        row["pass_direction"] = row["direction_agreement_fraction"] >= gates["minimum_direction_agreement"]
        row["pass_scale"] = row["median_scale_error_fraction"] <= gates["maximum_median_scale_error_fraction"]
        row["pass_median_difference"] = row["median_difference_of_step"] <= gates["maximum_median_difference_of_step"]
        row["pass_p95_difference"] = row["p95_difference_of_step"] <= gates["maximum_p95_difference_of_step"]
        row["pass_response"] = row["median_response_ratio"] >= gates["minimum_median_response_ratio"]
        row["pass_ecc"] = row["median_model_ecc"] >= gates["minimum_median_ecc"]
        row["sequence_pass"] = all(value for key, value in row.items() if key.startswith("pass_"))
        summaries.append(row)
    return pd.DataFrame(summaries)


def verify_r61_reproduction(config: dict, summary: pd.DataFrame) -> dict:
    original = pd.read_csv(str(PROJECT_ROOT / config["locked_r68_evidence"]["summary"]))
    current = summary.loc[summary["method"] == "R61v16"].set_index("sequence")
    original = original.set_index("sequence")
    mappings = {
        "valid_fraction": "valid_fraction",
        "direction_agreement_fraction": "direction_agreement_fraction",
        "median_scale_error_fraction": "median_scale_error_fraction",
        "median_vector_difference_um": "median_vector_difference_um",
        "p95_vector_difference_um": "p95_vector_difference_um",
        "median_response_ratio": "median_response_ratio",
        "median_model_ecc": "median_r61_ecc",
    }
    maximum = 0.0
    for new_name, old_name in mappings.items():
        delta = (current[new_name] - original[old_name]).abs().max()
        maximum = max(maximum, float(delta))
    if maximum > 1e-12:
        raise RuntimeError(f"R61 reproduction differs from locked R68 summary by {maximum}")
    return {"passed": True, "maximum_absolute_difference": maximum}


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def artifact_diagnostics(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    settings = config["artifact_diagnostic"]
    sensitivity = []
    primary = []
    for sequence, item in config["sequences"].items():
        raw_paths = image_paths(Path(PROJECT_ROOT / item["raw_dir"]))
        method_paths = {
            "R61v16": image_paths(Path(PROJECT_ROOT / item["r61_dir"])),
            "R75v2E100": image_paths(R75_RECON / sequence),
        }
        indices = [len(raw_paths) - 1 if value == -1 else int(value) for value in settings["frame_indices"]]
        if len(set(indices)) != len(indices) or max(indices) >= len(raw_paths):
            raise RuntimeError(f"{sequence}: invalid frozen artifact frame indices {indices}")
        for index in indices:
            raw_gradient = gradient_magnitude(read_gray(raw_paths[index]))
            for method, paths in method_paths.items():
                model_gradient = gradient_magnitude(read_gray(paths[index]))
                for raw_percentile in settings["raw_edge_percentile_sensitivity"]:
                    raw_threshold = float(np.percentile(raw_gradient, raw_percentile))
                    raw_support = raw_gradient >= raw_threshold
                    distance = cv2.distanceTransform((~raw_support).astype(np.uint8), cv2.DIST_L2, 5)
                    model_threshold = float(
                        np.percentile(model_gradient, settings["primary_reconstruction_edge_percentile"])
                    )
                    strong_model_edge = model_gradient >= model_threshold
                    for distance_px in settings["distance_px_sensitivity"]:
                        off_source = float(np.mean(distance[strong_model_edge] > float(distance_px)))
                        record = {
                            "sequence": sequence,
                            "frame_index": index,
                            "method": method,
                            "raw_edge_percentile": int(raw_percentile),
                            "model_edge_percentile": int(settings["primary_reconstruction_edge_percentile"]),
                            "distance_px": int(distance_px),
                            "off_source_strong_edge_fraction": off_source,
                        }
                        sensitivity.append(record)
                        if (
                            int(raw_percentile) == int(settings["primary_raw_edge_percentile"])
                            and int(distance_px) == int(settings["primary_distance_px"])
                        ):
                            raw_values = raw_gradient[raw_support]
                            model_values = model_gradient[raw_support]
                            edge_gain = float(np.median(model_values) / max(float(np.median(raw_values)), 1e-9))
                            primary.append({**record, "edge_gain_on_raw_support": edge_gain})

    sensitivity_table = pd.DataFrame(sensitivity)
    primary_table = pd.DataFrame(primary)
    comparison = []
    for (raw_percentile, distance_px), group in sensitivity_table.groupby(
        ["raw_edge_percentile", "distance_px"]
    ):
        medians = group.groupby("method")["off_source_strong_edge_fraction"].median()
        comparison.append(
            {
                "raw_edge_percentile": int(raw_percentile),
                "distance_px": int(distance_px),
                "r75v2_not_higher_than_r61": bool(medians["R75v2E100"] <= medians["R61v16"]),
                "r61_median": float(medians["R61v16"]),
                "r75v2_median": float(medians["R75v2E100"]),
            }
        )
    comparison_table = pd.DataFrame(comparison)
    direction = {
        "settings_count": int(len(comparison_table)),
        "r75v2_not_higher_count": int(comparison_table["r75v2_not_higher_than_r61"].sum()),
        "direction_consistent_all_settings": bool(comparison_table["r75v2_not_higher_than_r61"].all()),
        "interpretation": settings["interpretation"],
    }
    return sensitivity_table, primary_table, direction


def acm_truth_summary(config: dict) -> pd.DataFrame:
    source = pd.read_csv(str(PROJECT_ROOT / config["acm_sem_evidence"]["per_pillar_summary"]))
    methods = {
        "Raw": "raw",
        "R61v16": "r61v16",
        "R75v2E100": "r75v2_e100",
    }
    metrics = [
        "iou",
        "mean_boundary_distance_pitch_pct",
        "hd95_pitch_pct",
        "area_error_pct",
        "perimeter_error_pct",
        "circularity_abs_error",
    ]
    rows = []
    for method, prefix in methods.items():
        row = {"method": method, "independent_pillars": int(source["pillar_id"].nunique())}
        for metric in metrics:
            row[f"median_{metric}"] = float(source[f"{prefix}_{metric}"].median())
        rows.append(row)
    return pd.DataFrame(rows)


def model_decision(summary: pd.DataFrame, artifact_direction: dict, config: dict) -> dict:
    methods = {}
    ranking = []
    for method, group in summary.groupby("method"):
        passed = int(group["sequence_pass"].sum())
        record = {
            "passed_sequences": passed,
            "total_sequences": int(len(group)),
            "broad_real_fov_pass": bool(group["sequence_pass"].all()),
            "worst_median_difference_of_step": float(group["median_difference_of_step"].max()),
            "worst_p95_difference_of_step": float(group["p95_difference_of_step"].max()),
            "worst_median_scale_error_fraction": float(group["median_scale_error_fraction"].max()),
        }
        methods[method] = record
        ranking.append(
            (
                -passed,
                record["worst_median_difference_of_step"],
                record["worst_p95_difference_of_step"],
                record["worst_median_scale_error_fraction"],
                method,
            )
        )
    ranking.sort()
    r77 = read_json(Path(PROJECT_ROOT / config["acm_sem_evidence"]["decision"]))
    decision = {
        "status": "complete",
        "coverage": {
            "real_frames": 301,
            "sequences": 6,
            "magnifications": [5, 20, 50],
            "nominal_steps_um": [0.5, 1.0],
            "acm_sem_pillars": 36,
            "acm_sem_exposures": 12,
        },
        "models": methods,
        "worst_case_first_preference": ranking[0][-1],
        "artifact_diagnostic": artifact_direction,
        "r75v2_acm_sem": {
            "coarse_contour_gate_vs_raw": bool(r77["final_e100"]["coarse_contour_gate_vs_raw"]),
            "all_exposure_gate_vs_raw": bool(r77["final_e100"]["all_exposure_universal_gate_vs_raw"]),
            "fine_shape_gate_vs_raw": bool(r77["final_e100"]["fine_shape_gate_vs_raw"]),
            "comparison_to_r61": r77["final_e100"]["comparison_to_prior_models"]["R61v16"],
        },
        "universal_cross_sample_pass": False,
        "reason_universal_not_claimed": config["claim_boundaries"]["not_claimed"],
    }
    followup_path = RESULTS / "followup_5x_decision.json"
    if followup_path.is_file():
        decision["post_hoc_5x_confirmation"] = read_json(followup_path)
    followup_motion_path = RESULTS / "followup_5x_tile1024_motion_decision.json"
    if followup_motion_path.is_file():
        decision["post_hoc_5x_tile1024_motion"] = read_json(followup_motion_path)
    decision["current_recommendation"] = {
        "project_generalization_baseline": "R61v16",
        "r75v2_status": "promising at 20x/50x but not ready as the broad default",
        "blocking_findings": [
            "5x fine-detail collapse with the locked 512-pixel inference setting",
            "larger 1024-pixel tiles reduce the 5x artifact but do not fully restore fine detail",
            "ACM/SEM fine non-circular shape gate remains failed",
        ],
    }
    return decision


def make_figures(summary: pd.DataFrame, artifact: pd.DataFrame, acm: pd.DataFrame, config: dict) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 150, "font.size": 9})
    colors = {"R61v16": "#2b6cb0", "R75v2E100": "#dd6b20"}
    sequences = list(config["sequences"].keys())
    x = np.arange(len(sequences))
    width = 0.36

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for offset, method in enumerate(["R61v16", "R75v2E100"]):
        data = summary.loc[summary["method"] == method].set_index("sequence").loc[sequences]
        axes[0].bar(x + (offset - 0.5) * width, data["median_difference_of_step"] * 100, width, label=method, color=colors[method])
        axes[1].bar(x + (offset - 0.5) * width, data["p95_difference_of_step"] * 100, width, label=method, color=colors[method])
    axes[0].axhline(10, color="#9b2c2c", linestyle="--", linewidth=1, label="Gate")
    axes[1].axhline(25, color="#9b2c2c", linestyle="--", linewidth=1, label="Gate")
    axes[0].set_ylabel("Median difference (% of step)")
    axes[1].set_ylabel("P95 difference (% of step)")
    axes[1].set_xticks(x, sequences, rotation=25, ha="right")
    axes[0].set_title("Locked real-FOV motion preservation")
    axes[0].legend(ncol=3)
    axes[1].legend(ncol=3)
    fig.tight_layout()
    fig.savefig(FIGURES / "01_motion_comparison.png", bbox_inches="tight")
    plt.close(fig)

    primary_group = artifact.groupby(["sequence", "method"], as_index=False).agg(
        off_source=("off_source_strong_edge_fraction", "median"),
        edge_gain=("edge_gain_on_raw_support", "median"),
    )
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for offset, method in enumerate(["R61v16", "R75v2E100"]):
        data = primary_group.loc[primary_group["method"] == method].set_index("sequence").loc[sequences]
        axes[0].bar(x + (offset - 0.5) * width, data["off_source"] * 100, width, label=method, color=colors[method])
        axes[1].bar(x + (offset - 0.5) * width, data["edge_gain"], width, label=method, color=colors[method])
    axes[0].set_ylabel("Strong edges away from Raw (%)")
    axes[1].set_ylabel("Edge gain on Raw support (x)")
    axes[1].set_xticks(x, sequences, rotation=25, ha="right")
    axes[0].set_title("No-reference artifact diagnostic (not an accuracy gate)")
    axes[0].legend()
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(FIGURES / "02_artifact_diagnostic.png", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    metrics = [
        ("median_iou", "Contour IoU", True),
        ("median_mean_boundary_distance_pitch_pct", "Boundary distance (% pitch)", False),
        ("median_perimeter_error_pct", "Perimeter error (%)", False),
    ]
    acm_indexed = acm.set_index("method").loc[["Raw", "R61v16", "R75v2E100"]]
    acm_colors = ["#718096", colors["R61v16"], colors["R75v2E100"]]
    for axis, (metric, title, higher) in zip(axes, metrics):
        values = acm_indexed[metric].to_numpy()
        axis.bar(np.arange(3), values, color=acm_colors)
        axis.set_xticks(np.arange(3), ["Raw", "R61", "R75-v2"], rotation=15)
        axis.set_title(title + (" (higher is better)" if higher else " (lower is better)"))
        for index, value in enumerate(values):
            axis.text(index, value, f"{value:.4f}", ha="center", va="bottom", fontsize=8)
    fig.suptitle("ACM contour accuracy against SEM truth: 36 pillars")
    fig.tight_layout()
    fig.savefig(FIGURES / "03_acm_sem_truth_comparison.png", bbox_inches="tight")
    plt.close(fig)

    selected = ["5x_0p5um", "20x_0p5um", "50x_0p5um"]
    fig, axes = plt.subplots(3, 3, figsize=(12, 9))
    for row_index, sequence in enumerate(selected):
        item = config["sequences"][sequence]
        images = [
            read_gray(image_paths(Path(PROJECT_ROOT / item["raw_dir"]))[0]),
            read_gray(image_paths(Path(PROJECT_ROOT / item["r61_dir"]))[0]),
            read_gray(image_paths(R75_RECON / sequence)[0]),
        ]
        for column_index, (image, label) in enumerate(zip(images, ["Raw", "R61v16", "R75v2E100"])):
            lo, hi = np.percentile(image, [0.5, 99.5])
            axes[row_index, column_index].imshow(image, cmap="gray", vmin=lo, vmax=hi)
            axes[row_index, column_index].axis("off")
            axes[row_index, column_index].set_title(f"{sequence} | {label}")
    fig.suptitle("Fixed first-frame comparison; no visual cherry-picking")
    fig.tight_layout()
    fig.savefig(FIGURES / "04_fixed_raw_r61_r75_contact_sheet.png", bbox_inches="tight")
    plt.close(fig)


def write_report(
    summary: pd.DataFrame,
    artifact: pd.DataFrame,
    acm: pd.DataFrame,
    decision: dict,
) -> None:
    methods = decision["models"]
    preference = decision["worst_case_first_preference"]
    acm_indexed = acm.set_index("method")
    artifact_by_sequence = artifact.groupby(["sequence", "method"])[
        "off_source_strong_edge_fraction"
    ].median()
    primary_artifact = artifact.groupby("method")["off_source_strong_edge_fraction"].median()
    followup_summary_path = TABLES / "followup_5x_summary.csv"
    followup = pd.read_csv(followup_summary_path) if followup_summary_path.is_file() else None
    lines = [
        "# R78：R75-v2 廣泛真實顯微影像泛化驗證",
        "",
        "## 結論先行",
        "",
        f"這次把 301 張真實顯微影像全部納入，涵蓋 5x、20x、50x，0.5 µm 與 1.0 µm 位移，共六組連續影像。每組固定取 24 個有內容的位置；長時間中斷與原圖本身無法可靠量位移的位置，沿用先前已鎖定的排除規則。",
        "",
        f"- R61 通過 {methods['R61v16']['passed_sequences']}/6 組；R75-v2 第 100 輪通過 {methods['R75v2E100']['passed_sequences']}/6 組。",
        f"- 以最差場景優先，而不是只看平均分數，目前較穩定的是 **{preference}**。",
        f"- SEM／ACM 的 36 顆柱輪廓比較中，R75-v2 的輪廓重疊中位數為 {acm_indexed.loc['R75v2E100', 'median_iou']:.4f}，R61 為 {acm_indexed.loc['R61v16', 'median_iou']:.4f}。",
        f"- R75-v2 的細小非圓形細節仍未過關，而且 5 倍畫面會大量遺失細密圖案，因此現在不能稱為任何顯微影像都能使用的通用模型。",
        "",
        "## 六組真實影像的位移保持結果",
        "",
        "| 影像組 | 模型 | 可用比例 | 方向一致 | 位移比例 | 中位差 | P95 差 | 結果 |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in summary.sort_values(["sequence", "method"]).iterrows():
        lines.append(
            f"| {row['sequence']} | {row['method']} | {row['valid_fraction']:.1%} | "
            f"{row['direction_agreement_fraction']:.1%} | {row['median_model_over_raw_abs_dx']:.3f} | "
            f"{row['median_vector_difference_um']*1000:.1f} nm | {row['p95_vector_difference_um']*1000:.1f} nm | "
            f"{'通過' if row['sequence_pass'] else '未通過'} |"
        )
    lines += [
        "",
        "這裡檢查的是模型有沒有在不同倍率、不同位置與不同位移量下扭曲物體的移動關係。它能抓出局部圖案被拉動、跳格或位移比例改變，但不能取代 SEM 形狀真值。",
        "",
        "## SEM／ACM 真實形狀對照",
        "",
        "| 方法 | 輪廓重疊 | 平均邊界距離（柱距 %） | 面積誤差 | 周長誤差 |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in acm.iterrows():
        lines.append(
            f"| {row['method']} | {row['median_iou']:.4f} | "
            f"{row['median_mean_boundary_distance_pitch_pct']:.4f} | "
            f"{row['median_area_error_pct']:.3f}% | {row['median_perimeter_error_pct']:.3f}% |"
        )
    lines += [
        "",
        "這一部分才是在回答形狀準不準：36 顆柱各算一次，12 個曝光只是同一批柱子的重複觀察。R75-v2 的主要外框優於原圖，但周長與非圓細節仍比原圖差。",
        "",
        "## 新增假邊緣風險檢查",
        "",
        f"固定抽取每組第 1、13、25、37 與最後一張，共 30 張。整體中位數看起來接近：R61 為 {primary_artifact['R61v16']:.2%}，R75-v2 為 {primary_artifact['R75v2E100']:.2%}；但平均值掩蓋了倍率差異。R75-v2 在兩組 5 倍影像分別升到 {artifact_by_sequence.loc[('5x_0p5um', 'R75v2E100')]:.2%} 與 {artifact_by_sequence.loc[('5x_1um', 'R75v2E100')]:.2%}，R61 只有 {artifact_by_sequence.loc[('5x_0p5um', 'R61v16')]:.2%} 與 {artifact_by_sequence.loc[('5x_1um', 'R61v16')]:.2%}。對照圖也可直接看到 5 倍細網格被抹平並出現大片帶狀結構。這只是警示指標，不能取代 SEM 真值；但它足以指出 5 倍輸出不應直接使用。",
        "",
        "## 5 倍異常的追加確認",
        "",
    ]
    if followup is not None:
        followup_index = followup.set_index(["sequence", "method"])
        r75_default_detail = float(
            followup.loc[followup["method"] == "R75v2E100", "median_fine_detail_energy_ratio"].median()
        )
        r75_large_detail = float(
            followup.loc[
                followup["method"] == "R75v2E100_tile1024", "median_fine_detail_energy_ratio"
            ].median()
        )
        r75_default_off = float(
            followup.loc[
                followup["method"] == "R75v2E100",
                "median_off_source_strong_edge_fraction",
            ].median()
        )
        r75_large_off = float(
            followup.loc[
                followup["method"] == "R75v2E100_tile1024",
                "median_off_source_strong_edge_fraction",
            ].median()
        )
        lines += [
            "主要檢查發現 5 倍問題後，另外把全部 100 張 5 倍影像重新核對。這是追加確認，不是事先設定的升級門檻。",
            "",
            f"- 原本 512 像素重建區塊下，100/100 張都重複出現警訊；細節能量中位數只剩原圖約 {r75_default_detail:.1%}，偏離原圖的強邊緣約 {r75_default_off:.1%}。",
            f"- 改成 1024 像素區塊後，偏離強邊緣降到約 {r75_large_off:.1%}，但細節只回升到約 {r75_large_detail:.1%}，仍未完整恢復。",
            "- 較大區塊在兩組 5 倍影像的位移檢查仍然通過；這也證明『位置能跟著移動』與『細節有沒有被保留』必須分開判斷。",
            "- 因此切圖大小會加重問題，但不是唯一原因；R75-v2 本身仍缺少低倍率、超密集細節的能力。",
            "",
        ]
    lines += [
        "## 可以下的結論與還不能下的結論",
        "",
        "現在可以說：R75-v2 已在六組真實顯微連續影像與一組 36 顆柱的 SEM 輪廓真值上接受檢查。它在 20 倍與 50 倍有競爭力，不是只在合成圖上有效；但 5 倍細節保存不合格。",
        "",
        "目前決策：R61 仍保留為廣泛場景基準。R75-v2 暫時只列為 20 倍／50 倍候選，不應直接取代 R61。",
        "",
        "現在仍不能說：任何一個模型已保證適用所有樣品。現有 301 張影像只來自兩個拍攝日期，樣品身分也沒有完整編號；還缺不同批次、不同材質、不同顯微鏡與真正未參與開發的新樣品。",
        "",
        "## 下一輪最有價值的新增資料",
        "",
        "1. 至少三個有明確批號的新樣品，每個樣品先封存影像再跑模型。",
        "2. 每個樣品包含規則柱、非圓柱、線條、缺口、顆粒污染與空白背景。",
        "3. 每種形狀保留低亮、中亮、高亮與輕微失焦版本。",
        "4. 其中一部分再拍 SEM，讓 ACM 能直接判斷形狀，而不是只看穩定性。",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze(config: dict) -> None:
    locked = pd.read_csv(str(PROJECT_ROOT / config["locked_r68_evidence"]["measurements"]))
    locked["raw_reference_valid"] = as_bool(locked["raw_reference_valid"])
    r61 = standardized_r61_rows(locked)
    r75 = compute_r75_rows(config, locked)
    combined = pd.concat([r61, r75], ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    combined.to_csv(TABLES / "tile_motion_measurements.csv", index=False)
    summary = summarize_motion(combined, config["motion_gates"])
    summary.to_csv(TABLES / "sequence_method_summary.csv", index=False)
    reproduction = verify_r61_reproduction(config, summary)
    sensitivity, artifact, artifact_direction = artifact_diagnostics(config)
    sensitivity.to_csv(TABLES / "artifact_edge_sensitivity.csv", index=False)
    artifact.to_csv(TABLES / "artifact_edge_primary.csv", index=False)
    acm = acm_truth_summary(config)
    acm.to_csv(TABLES / "acm_sem_truth_summary.csv", index=False)
    decision = model_decision(summary, artifact_direction, config)
    decision["r61_locked_result_reproduced"] = reproduction
    write_json(RESULTS / "decision.json", decision)
    make_figures(summary, artifact, acm, config)
    write_report(summary, artifact, acm, decision)
    print(summary.to_string(index=False), flush=True)
    print(f"[report] {REPORT}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="R78 broad real microscope generalization validation")
    parser.add_argument("--stage", choices=["prepare", "infer", "validate", "analyze", "all"], default="all")
    args = parser.parse_args()
    config = read_json(CONFIG_PATH)
    if args.stage in {"prepare", "all"}:
        audit = prepare_locked_inputs(config)
        print(f"[prepare] locked {audit['total_frames']} real microscope frames", flush=True)
    if args.stage in {"infer", "all"}:
        if not (RESULTS / "input_audit.json").is_file():
            prepare_locked_inputs(config)
        run_inference(config)
    if args.stage in {"validate", "all"}:
        audit = validate_outputs(config)
        print(f"[validate] {audit['r75v2_output_validation']['frames_checked']} R75-v2 outputs passed", flush=True)
    if args.stage in {"analyze", "all"}:
        if not (RESULTS / "input_audit.json").is_file():
            raise RuntimeError("Run prepare and inference before analyze")
        validate_outputs(config)
        analyze(config)


if __name__ == "__main__":
    main()
