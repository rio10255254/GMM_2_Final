"""Validate R90 E55 on the six locked real microscope sequences."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from skimage.metrics import structural_similarity
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "reports" / "full_validation_epoch055" / "validation_protocol.json"
R78_CONFIG_PATH = Path(str(PROJECT_ROOT / 'Experiments/R78_R75v2_BroadRealMicroscopeGeneralization/config/experiment.json'))
RESULTS = ROOT / "results" / "full_validation_epoch055"
RECON_ROOT = RESULTS / "reconstructions"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def image_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("frame_*.bmp"))


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not decode {path}")
    return image


def as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().eq("true")


def edge_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    edge -= float(edge.mean())
    scale = float(edge.std())
    return edge / scale if scale > 1e-6 else edge


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def phase_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    a_edge, b_edge = edge_image(a), edge_image(b)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a_edge, b_edge, window)
    return float(dx), float(dy), float(response)


def bounded_ecc_shift(a: np.ndarray, b: np.ndarray, initial_dx: float, initial_dy: float) -> tuple[float, float, float]:
    a_float = cv2.GaussianBlur(a.astype(np.float32) / 255.0, (0, 0), 1.0)
    b_float = cv2.GaussianBlur(b.astype(np.float32) / 255.0, (0, 0), 1.0)
    warp = np.array([[1.0, 0.0, initial_dx], [0.0, 1.0, initial_dy]], dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-6)
    correlation, refined = cv2.findTransformECC(
        a_float, b_float, warp, cv2.MOTION_TRANSLATION, criteria, None, 1
    )
    return float(refined[0, 2]), float(refined[1, 2]), float(correlation)


def verify_inputs(protocol: dict, config: dict) -> dict:
    locked_path = Path(protocol["real_motion_arm"]["locked_measurements"])
    if sha256_file(locked_path) != protocol["real_motion_arm"]["locked_measurements_sha256"]:
        raise RuntimeError("Locked Raw eligibility table changed")
    audit = {"status": "complete", "locked_table_hash_verified": True, "sequences": {}}
    for sequence, item in config["sequences"].items():
        raw_paths = image_paths(Path(PROJECT_ROOT / item["raw_dir"]))
        if len(raw_paths) != int(item["frame_count"]):
            raise RuntimeError(f"{sequence}: Raw frame count mismatch")
        methods = {"R61v16": image_paths(Path(PROJECT_ROOT / item["r61_dir"]))}
        for label in ("R89E100", "R90E55"):
            directory = RECON_ROOT / label / sequence
            paths = image_paths(directory)
            manifest_path = directory / "reconstruction_manifest.json"
            if not manifest_path.is_file():
                raise RuntimeError(f"{sequence}/{label}: manifest missing")
            manifest = read_json(manifest_path)
            record = protocol["comparison_models"][label]
            if manifest["checkpoint_sha256"] != record["checkpoint_sha256"]:
                raise RuntimeError(f"{sequence}/{label}: checkpoint mismatch")
            if int(manifest["checkpoint_epoch"]) != int(record["checkpoint_epoch"]):
                raise RuntimeError(f"{sequence}/{label}: epoch mismatch")
            methods[label] = paths
        raw_names = [path.name for path in raw_paths]
        for label, paths in methods.items():
            if [path.name for path in paths] != raw_names:
                raise RuntimeError(f"{sequence}/{label}: frame identities differ from Raw")
            if read_gray(paths[0]).shape != read_gray(raw_paths[0]).shape:
                raise RuntimeError(f"{sequence}/{label}: shape differs from Raw")
        audit["sequences"][sequence] = {
            "frames": len(raw_paths),
            "shape": list(read_gray(raw_paths[0]).shape),
            "all_model_filenames_match_raw": True,
            "all_checkpoint_manifests_match": True,
        }
    audit["total_frames"] = int(sum(row["frames"] for row in audit["sequences"].values()))
    if audit["total_frames"] != 301:
        raise RuntimeError("Expected 301 unique real frames")
    write_json(RESULTS / "input_audit.json", audit)
    return audit


def standardized_r61_rows(locked: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "sequence": locked["sequence"], "method": "R61v16",
        "magnification": locked["magnification"], "nominal_step_um": locked["nominal_step_um"],
        "object_um_per_px": locked["object_um_per_px"], "expected_dx_px": locked["expected_dx_px"],
        "step_index": locked["step_index"], "time_gap_s": locked["time_gap_s"],
        "tile_id": locked["tile_id"], "tile_row": locked["tile_row"], "tile_column": locked["tile_column"],
        "edge_score": locked["edge_score"], "raw_dx_px": locked["raw_dx_px"], "raw_dy_px": locked["raw_dy_px"],
        "raw_response": locked["raw_response"], "model_phase_dx_px": locked["r61_phase_dx_px"],
        "model_phase_dy_px": locked["r61_phase_dy_px"], "model_response": locked["r61_response"],
        "model_dx_px": locked["r61_dx_px"], "model_dy_px": locked["r61_dy_px"], "model_ecc": locked["r61_ecc"],
        "raw_reference_valid": as_bool(locked["raw_reference_valid"]),
        "model_evaluable": as_bool(locked["r61_evaluable"]), "valid": as_bool(locked["valid"]),
        "direction_agreement": as_bool(locked["direction_agreement"]),
        "model_over_raw_abs_dx": locked["r61_over_raw_abs_dx"],
        "vector_difference_um": locked["r61_raw_vector_difference_um"],
    })


def compute_model_rows(label: str, config: dict, locked: pd.DataFrame) -> pd.DataFrame:
    records: list[dict] = []
    tile_h, tile_w = 1536 // 6, 2048 // 8
    for sequence, sequence_rows in locked.groupby("sequence", sort=False):
        print(f"[motion] {label} {sequence}", flush=True)
        recon = image_paths(RECON_ROOT / label / sequence)
        for step_index, step_rows in sequence_rows.groupby("step_index", sort=True):
            index = int(step_index)
            rec_a, rec_b = read_gray(recon[index]), read_gray(recon[index + 1])
            for _, row in step_rows.iterrows():
                tile_row, tile_column = int(row["tile_row"]), int(row["tile_column"])
                y0, x0 = tile_row * tile_h, tile_column * tile_w
                tile_a = rec_a[y0:y0 + tile_h, x0:x0 + tile_w]
                tile_b = rec_b[y0:y0 + tile_h, x0:x0 + tile_w]
                phase_dx, phase_dy, response = phase_shift(tile_a, tile_b)
                try:
                    dx, dy, ecc = bounded_ecc_shift(tile_a, tile_b, float(row["raw_dx_px"]), float(row["raw_dy_px"]))
                    ecc_ok = math.isfinite(ecc)
                except cv2.error:
                    dx, dy, ecc, ecc_ok = math.nan, math.nan, math.nan, False
                expected_px = float(row["expected_dx_px"])
                shift_limit = max(12.0, expected_px * 2.5)
                raw_valid = bool(row["raw_reference_valid"])
                evaluable = bool(ecc_ok and ecc >= 0.75 and abs(dx) <= shift_limit and abs(dy) <= shift_limit)
                valid = raw_valid and evaluable
                raw_dx, raw_dy = float(row["raw_dx_px"]), float(row["raw_dy_px"])
                direction = bool(np.sign(raw_dx) == np.sign(dx)) if valid and abs(raw_dx) > 0.05 and abs(dx) > 0.05 else False
                um_per_px = float(row["object_um_per_px"])
                difference_um = math.hypot(dx - raw_dx, dy - raw_dy) * um_per_px if valid else math.nan
                scale = abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan
                records.append({
                    "sequence": sequence, "method": label, "magnification": float(row["magnification"]),
                    "nominal_step_um": float(row["nominal_step_um"]), "object_um_per_px": um_per_px,
                    "expected_dx_px": expected_px, "step_index": index, "time_gap_s": row["time_gap_s"],
                    "tile_id": row["tile_id"], "tile_row": tile_row, "tile_column": tile_column,
                    "edge_score": float(row["edge_score"]), "raw_dx_px": raw_dx, "raw_dy_px": raw_dy,
                    "raw_response": float(row["raw_response"]), "model_phase_dx_px": phase_dx,
                    "model_phase_dy_px": phase_dy, "model_response": response, "model_dx_px": dx,
                    "model_dy_px": dy, "model_ecc": ecc, "raw_reference_valid": raw_valid,
                    "model_evaluable": evaluable, "valid": valid, "direction_agreement": direction,
                    "model_over_raw_abs_dx": scale, "vector_difference_um": difference_um,
                })
    return pd.DataFrame(records)


def robust_mad(values: pd.Series) -> float:
    array = values.to_numpy(float)
    median = np.median(array)
    return float(1.4826 * np.median(np.abs(array - median)))


def summarize_motion(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (sequence, method), group in table.groupby(["sequence", "method"], sort=False):
        reference = group.loc[group["raw_reference_valid"]].copy()
        valid = group.loc[group["valid"]].copy()
        if reference.empty or valid.empty:
            raise RuntimeError(f"{sequence}/{method}: no valid measurements")
        um_per_px = float(valid["object_um_per_px"].iloc[0])
        raw_step = valid["raw_dx_px"].abs() * um_per_px
        model_step = valid["model_dx_px"].abs() * um_per_px
        delta = model_step - raw_step
        vector = valid["vector_difference_um"]
        response_ratio = valid["model_response"] / valid["raw_response"].clip(lower=1e-9)
        scale = float(valid["model_over_raw_abs_dx"].median())
        rows.append({
            "sequence": sequence, "method": method, "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]), "selected_tiles": int(group["tile_id"].nunique()),
            "used_steps": int(group["step_index"].nunique()), "tile_measurements": int(len(group)),
            "raw_reference_measurements": int(len(reference)), "valid_measurements": int(len(valid)),
            "valid_fraction_within_raw_reference": float(len(valid) / len(reference)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
            "median_model_over_raw_abs_dx": scale, "median_scale_error_fraction": abs(scale - 1.0),
            "raw_median_abs_dx_um": float(raw_step.median()), "model_median_abs_dx_um": float(model_step.median()),
            "raw_step_std_um": float(raw_step.std(ddof=1)), "model_step_std_um": float(model_step.std(ddof=1)),
            "model_over_raw_step_std": float(model_step.std(ddof=1) / max(raw_step.std(ddof=1), 1e-12)),
            "raw_step_robust_mad_um": robust_mad(raw_step), "model_step_robust_mad_um": robust_mad(model_step),
            "median_signed_model_minus_raw_step_um": float(delta.median()),
            "mean_signed_model_minus_raw_step_um": float(delta.mean()),
            "paired_delta_std_um": float(delta.std(ddof=1)),
            "median_vector_difference_um": float(vector.median()), "p95_vector_difference_um": float(vector.quantile(0.95)),
            "median_difference_of_commanded_step": float(vector.median() / valid["nominal_step_um"].iloc[0]),
            "p95_difference_of_commanded_step": float(vector.quantile(0.95) / valid["nominal_step_um"].iloc[0]),
            "median_response_ratio": float(response_ratio.median()), "median_model_ecc": float(valid["model_ecc"].median()),
        })
    return pd.DataFrame(rows)


def appearance_metrics(raw: np.ndarray, model: np.ndarray) -> dict[str, float]:
    raw_f, model_f = raw.astype(np.float32), model.astype(np.float32)
    difference = model_f - raw_f
    absolute = np.abs(difference)
    raw_gradient, model_gradient = gradient_magnitude(raw), gradient_magnitude(model)
    raw_threshold = float(np.percentile(raw_gradient, 85))
    raw_support = raw_gradient >= raw_threshold
    distance = cv2.distanceTransform((~raw_support).astype(np.uint8), cv2.DIST_L2, 5)
    model_strong = model_gradient >= float(np.percentile(model_gradient, 95))
    raw_detail = raw_f - cv2.GaussianBlur(raw_f, (0, 0), 2.0)
    model_detail = model_f - cv2.GaussianBlur(model_f, (0, 0), 2.0)
    edge_band = cv2.dilate(raw_support.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    flat = distance > 5.0
    return {
        "mean_signed_change_gray": float(difference.mean()),
        "mean_abs_change_gray": float(absolute.mean()),
        "p95_abs_change_gray": float(np.percentile(absolute, 95)),
        "fraction_changed_over_10_gray": float(np.mean(absolute > 10.0)),
        "ssim_to_raw": float(structural_similarity(raw_f, model_f, data_range=255)),
        "edge_gain_on_raw_support": float(np.median(model_gradient[raw_support]) / max(float(np.median(raw_gradient[raw_support])), 1e-9)),
        "fine_detail_energy_ratio": float(np.std(model_detail) / max(float(np.std(raw_detail)), 1e-9)),
        "off_source_strong_edge_fraction": float(np.mean(distance[model_strong] > 3.0)),
        "dark_change_fraction_on_raw_edge_band": float(np.mean(difference[edge_band] < -10.0)),
        "bright_change_fraction_on_raw_edge_band": float(np.mean(difference[edge_band] > 10.0)),
        "mean_abs_change_flat_region_gray": float(np.mean(absolute[flat])),
    }


def save_montage(sequence: str, raw: np.ndarray, methods: dict[str, np.ndarray]) -> None:
    panels = []
    for label, image in [("RAW", raw), *methods.items()]:
        panel = cv2.resize(image, None, fx=0.32, fy=0.32, interpolation=cv2.INTER_AREA)
        panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (260, 40), (0, 0, 0), -1)
        cv2.putText(panel, label, (10, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
        panels.append(panel)
    diff = np.clip(np.abs(methods["R90E55"].astype(np.int16) - raw.astype(np.int16)) * 4, 0, 255).astype(np.uint8)
    panel = cv2.resize(diff, None, fx=0.32, fy=0.32, interpolation=cv2.INTER_AREA)
    panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (320, 40), (0, 0, 0), -1)
    cv2.putText(panel, "R90 ABS DIFF x4", (10, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    panels.append(panel)
    FIGURES.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(FIGURES / f"{sequence}_representative.png"), np.hstack(panels))


def evaluate_appearance(config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for sequence, item in config["sequences"].items():
        raw_paths = image_paths(Path(PROJECT_ROOT / item["raw_dir"]))
        paths_by_method = {
            "R61v16": image_paths(Path(PROJECT_ROOT / item["r61_dir"])),
            "R89E100": image_paths(RECON_ROOT / "R89E100" / sequence),
            "R90E55": image_paths(RECON_ROOT / "R90E55" / sequence),
        }
        for index, raw_path in enumerate(raw_paths):
            raw = read_gray(raw_path)
            for method, paths in paths_by_method.items():
                rows.append({
                    "sequence": sequence, "magnification": float(item["magnification"]),
                    "nominal_step_um": float(item["nominal_step_um"]), "frame_index": index,
                    "filename": raw_path.name, "method": method,
                    **appearance_metrics(raw, read_gray(paths[index])),
                })
            if index == 24:
                save_montage(sequence, raw, {label: read_gray(paths[index]) for label, paths in paths_by_method.items()})
        print(f"[appearance] {sequence}: {len(raw_paths)} frames", flush=True)
    table = pd.DataFrame(rows)
    metric_names = [column for column in table.columns if column not in {
        "sequence", "magnification", "nominal_step_um", "frame_index", "filename", "method"
    }]
    summaries = []
    for (sequence, method), group in table.groupby(["sequence", "method"], sort=False):
        record = {"sequence": sequence, "method": method, "frames": int(len(group)),
                  "magnification": float(group["magnification"].iloc[0]),
                  "nominal_step_um": float(group["nominal_step_um"].iloc[0])}
        for metric in metric_names:
            record[f"median_{metric}"] = float(group[metric].median())
            record[f"p95_{metric}"] = float(group[metric].quantile(0.95))
        summaries.append(record)
    return table, pd.DataFrame(summaries)


def comparison_summary(motion: pd.DataFrame, appearance: pd.DataFrame) -> dict:
    result: dict[str, object] = {"motion": {}, "appearance": {}}
    indexed_motion = motion.set_index(["sequence", "method"])
    for comparator in ("R61v16", "R89E100"):
        records = []
        for sequence in motion["sequence"].unique():
            r90 = indexed_motion.loc[(sequence, "R90E55")]
            other = indexed_motion.loc[(sequence, comparator)]
            records.append({
                "sequence": sequence,
                "r90_minus_comparator_step_std_um": float(r90["model_step_std_um"] - other["model_step_std_um"]),
                "r90_minus_comparator_paired_delta_std_um": float(r90["paired_delta_std_um"] - other["paired_delta_std_um"]),
                "r90_minus_comparator_p95_vector_difference_um": float(r90["p95_vector_difference_um"] - other["p95_vector_difference_um"]),
                "r90_minus_comparator_abs_systematic_shift_um": float(abs(r90["mean_signed_model_minus_raw_step_um"]) - abs(other["mean_signed_model_minus_raw_step_um"])),
            })
        result["motion"][f"R90E55_vs_{comparator}"] = records
    indexed_appearance = appearance.set_index(["sequence", "method"])
    for comparator in ("R61v16", "R89E100"):
        records = []
        for sequence in appearance["sequence"].unique():
            r90 = indexed_appearance.loc[(sequence, "R90E55")]
            other = indexed_appearance.loc[(sequence, comparator)]
            records.append({
                "sequence": sequence,
                "r90_minus_comparator_off_source_edge_fraction": float(r90["median_off_source_strong_edge_fraction"] - other["median_off_source_strong_edge_fraction"]),
                "r90_minus_comparator_dark_edge_fraction": float(r90["median_dark_change_fraction_on_raw_edge_band"] - other["median_dark_change_fraction_on_raw_edge_band"]),
                "r90_minus_comparator_fine_detail_energy_ratio": float(r90["median_fine_detail_energy_ratio"] - other["median_fine_detail_energy_ratio"]),
                "r90_minus_comparator_ssim_to_raw": float(r90["median_ssim_to_raw"] - other["median_ssim_to_raw"]),
            })
        result["appearance"][f"R90E55_vs_{comparator}"] = records
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["all", "motion", "appearance"], default="all")
    args = parser.parse_args()
    TABLES.mkdir(parents=True, exist_ok=True)
    protocol, config = read_json(PROTOCOL_PATH), read_json(R78_CONFIG_PATH)
    verify_inputs(protocol, config)
    locked = pd.read_csv(protocol["real_motion_arm"]["locked_measurements"])
    locked["raw_reference_valid"] = as_bool(locked["raw_reference_valid"])

    motion_summary = None
    if args.stage in {"all", "motion"}:
        frames = [standardized_r61_rows(locked)]
        for label in ("R89E100", "R90E55"):
            frames.append(compute_model_rows(label, config, locked))
        motion_table = pd.concat(frames, ignore_index=True)
        motion_table.to_csv(TABLES / "real_motion_tile_measurements.csv", index=False, encoding="utf-8-sig")
        motion_summary = summarize_motion(motion_table)
        motion_summary.to_csv(TABLES / "real_motion_sequence_summary.csv", index=False, encoding="utf-8-sig")

    appearance_summary = None
    if args.stage in {"all", "appearance"}:
        appearance_table, appearance_summary = evaluate_appearance(config)
        appearance_table.to_csv(TABLES / "real_appearance_all_frames.csv", index=False, encoding="utf-8-sig")
        appearance_summary.to_csv(TABLES / "real_appearance_sequence_summary.csv", index=False, encoding="utf-8-sig")

    motion_path = TABLES / "real_motion_sequence_summary.csv"
    appearance_path = TABLES / "real_appearance_sequence_summary.csv"
    if motion_summary is None and motion_path.is_file():
        motion_summary = pd.read_csv(motion_path)
    if appearance_summary is None and appearance_path.is_file():
        appearance_summary = pd.read_csv(appearance_path)
    if motion_summary is None or appearance_summary is None:
        completed = []
        if motion_summary is not None:
            completed.append("motion")
        if appearance_summary is not None:
            completed.append("appearance")
        partial = {
            "status": "stage_complete_waiting_for_other_stage",
            "protocol_id": protocol["protocol_id"],
            "completed_stages": completed,
        }
        write_json(RESULTS / "real_generalization_partial_status.json", partial)
        print(json.dumps(partial, ensure_ascii=False))
        return 0
    comparison = comparison_summary(motion_summary, appearance_summary)
    final = {
        "status": "complete", "protocol_id": protocol["protocol_id"], "unique_real_frames": 301,
        "sequences": 6, "magnifications": [5, 20, 50], "nominal_steps_um": [0.5, 1.0],
        "raw_eligibility_locked_before_model_outputs": True,
        "model_output_based_exclusions": False,
        "claim_limit": "Commanded motion and Raw are not independent position truth; motion results test stability and agreement, while appearance diagnostics flag changes but do not prove shape accuracy.",
        "paired_comparisons": comparison,
    }
    write_json(RESULTS / "real_generalization_summary.json", final)
    print(json.dumps(final, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
