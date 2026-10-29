"""Complete all-frame real microscope and locked motion validation for R96 E44."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import cv2
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config" / "final_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r96_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
HELPERS_PATH = ROOT / "scripts" / "evaluate_real_holdout.py"
OUTPUT = ROOT / "results" / "final_validation" / "real_generalization"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r96_final_model", MODEL_PATH)
INFERENCE = load_module("r96_final_inference", INFERENCE_PATH)
HELPERS = load_module("r96_final_helpers", HELPERS_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_mad(series: pd.Series) -> float:
    values = series.to_numpy(float)
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def summarize_r96_motion(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sequence, group in table.groupby("sequence", sort=False):
        reference = group.loc[group["raw_reference_valid"]]
        valid = group.loc[group["valid"]]
        um_per_px = float(group["object_um_per_px"].iloc[0])
        raw_step = valid["raw_dx_px"].abs() * um_per_px
        model_step = valid["r96_dx_px"].abs() * um_per_px
        delta = model_step - raw_step
        vector = valid["vector_difference_um"]
        response_ratio = valid["r96_response"] / valid["raw_response"].clip(lower=1e-9)
        scale = float(valid["r96_over_raw_abs_dx"].median())
        rows.append({
            "sequence": sequence,
            "method": "R96E44",
            "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
            "selected_tiles": int(group["tile_id"].nunique()),
            "used_steps": int(group["step_index"].nunique()),
            "tile_measurements": int(len(group)),
            "raw_reference_measurements": int(len(reference)),
            "valid_measurements": int(len(valid)),
            "valid_fraction_within_raw_reference": float(len(valid) / max(len(reference), 1)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
            "median_model_over_raw_abs_dx": scale,
            "median_scale_error_fraction": abs(scale - 1.0),
            "raw_median_abs_dx_um": float(raw_step.median()),
            "model_median_abs_dx_um": float(model_step.median()),
            "raw_step_std_um": float(raw_step.std(ddof=1)),
            "model_step_std_um": float(model_step.std(ddof=1)),
            "model_over_raw_step_std": float(model_step.std(ddof=1) / max(float(raw_step.std(ddof=1)), 1e-12)),
            "raw_step_robust_mad_um": robust_mad(raw_step),
            "model_step_robust_mad_um": robust_mad(model_step),
            "median_signed_model_minus_raw_step_um": float(delta.median()),
            "paired_delta_std_um": float(delta.std(ddof=1)),
            "median_vector_difference_um": float(vector.median()),
            "p95_vector_difference_um": float(vector.quantile(0.95)),
            "median_difference_of_commanded_step": float(vector.median() / float(group["nominal_step_um"].iloc[0])),
            "p95_difference_of_commanded_step": float(vector.quantile(0.95) / float(group["nominal_step_um"].iloc[0])),
            "median_response_ratio": float(response_ratio.median()),
            "median_model_ecc": float(valid["r96_ecc"].median()),
        })
    return pd.DataFrame(rows)


def standardized_r61_summary(locked: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sequence, group in locked.groupby("sequence", sort=False):
        reference = group.loc[group["raw_reference_valid"]]
        valid = group.loc[group["valid"]]
        um_per_px = float(group["object_um_per_px"].iloc[0])
        raw_step = valid["raw_dx_px"].abs() * um_per_px
        model_step = valid["r61_dx_px"].abs() * um_per_px
        delta = model_step - raw_step
        vector = valid["r61_raw_vector_difference_um"]
        response_ratio = valid["r61_response"] / valid["raw_response"].clip(lower=1e-9)
        scale = float(valid["r61_over_raw_abs_dx"].median())
        rows.append({
            "sequence": sequence, "method": "R61v16",
            "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
            "selected_tiles": int(group["tile_id"].nunique()), "used_steps": int(group["step_index"].nunique()),
            "tile_measurements": int(len(group)), "raw_reference_measurements": int(len(reference)),
            "valid_measurements": int(len(valid)),
            "valid_fraction_within_raw_reference": float(len(valid) / max(len(reference), 1)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
            "median_model_over_raw_abs_dx": scale, "median_scale_error_fraction": abs(scale - 1.0),
            "raw_median_abs_dx_um": float(raw_step.median()), "model_median_abs_dx_um": float(model_step.median()),
            "raw_step_std_um": float(raw_step.std(ddof=1)), "model_step_std_um": float(model_step.std(ddof=1)),
            "model_over_raw_step_std": float(model_step.std(ddof=1) / max(float(raw_step.std(ddof=1)), 1e-12)),
            "raw_step_robust_mad_um": robust_mad(raw_step), "model_step_robust_mad_um": robust_mad(model_step),
            "median_signed_model_minus_raw_step_um": float(delta.median()),
            "paired_delta_std_um": float(delta.std(ddof=1)),
            "median_vector_difference_um": float(vector.median()), "p95_vector_difference_um": float(vector.quantile(0.95)),
            "median_difference_of_commanded_step": float(vector.median() / float(group["nominal_step_um"].iloc[0])),
            "p95_difference_of_commanded_step": float(vector.quantile(0.95) / float(group["nominal_step_um"].iloc[0])),
            "median_response_ratio": float(response_ratio.median()), "median_model_ecc": float(valid["r61_ecc"].median()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite final validation: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("locked_before_epoch44_outputs"):
        raise RuntimeError("Final protocol was not locked")
    arm = protocol["real_microscope_arm"]
    sequence_config_path = Path(PROJECT_ROOT / arm["source_sequence_config"])
    locked_path = Path(PROJECT_ROOT / arm["locked_raw_measurements"])
    checkpoint_path = Path(PROJECT_ROOT / protocol["checkpoint"])
    config = read_json(sequence_config_path)
    locked = pd.read_csv(locked_path)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != int(protocol["primary_checkpoint_epoch"]):
        raise RuntimeError("Final checkpoint epoch mismatch")
    design = read_json(DESIGN_PATH)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device(arm["inference"]["device"] if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    torch.set_num_threads(4)
    core, halo = int(arm["inference"]["core_size"]), int(arm["inference"]["halo"])
    write_json(OUTPUT / "protocol_snapshot.json", protocol)
    manifest = {
        "checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_sha256": sha256_file(checkpoint_path), "run_id": checkpoint["metadata"]["run_id"],
        "sequence_config_sha256": sha256_file(sequence_config_path),
        "locked_measurements_sha256": sha256_file(locked_path), "device": str(device),
    }
    write_json(OUTPUT / "input_manifest.json", manifest)

    appearance_records: list[dict[str, object]] = []
    reconstruction_records: list[dict[str, object]] = []
    reconstructed: dict[tuple[str, int], Path] = {}
    started = time.perf_counter()
    for sequence in arm["sequences"]:
        item = config["sequences"][sequence]
        raw_paths = sorted(Path(item["raw_dir"]).glob("frame_*.bmp"))
        r61_paths = sorted(Path(item["recon_dir"]).glob("frame_*.bmp"))
        if len(raw_paths) != int(item["frame_count"]) or len(r61_paths) != len(raw_paths):
            raise RuntimeError(f"{sequence}: frame inventory mismatch")
        fixed = [len(raw_paths) - 1 if int(i) < 0 else int(i) for i in arm["fixed_visual_indices"]]
        montage_rows: list[tuple[int, np.ndarray, np.ndarray]] = []
        for index, (raw_path, r61_path) in enumerate(zip(raw_paths, r61_paths)):
            raw = HELPERS.read_gray(raw_path)
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            frame_started = time.perf_counter()
            with torch.inference_mode():
                prediction = INFERENCE.reconstruct_tensor(model, tensor, core_size=core, halo=halo, tile_batch=1)[0, 0]
            minimum, maximum = float(prediction.min()), float(prediction.max())
            r96 = np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
            destination = OUTPUT / "reconstructions" / sequence / raw_path.name
            HELPERS.write_gray(destination, r96)
            reconstructed[(sequence, index)] = destination
            reconstruction_records.append({
                "sequence": sequence, "frame_index": index, "source_path": str(raw_path),
                "source_sha256": sha256_file(raw_path), "output_path": str(destination),
                "output_sha256": sha256_file(destination), "seconds": time.perf_counter() - frame_started,
                "unbounded_min": minimum, "unbounded_max": maximum,
            })
            base = {"sequence": sequence, "magnification": float(item["magnification"]),
                    "nominal_step_um": float(item["nominal_step_um"]), "frame_index": index}
            appearance_records.append({**base, "method": "R96E44", **HELPERS.appearance_metrics(raw, r96, core)})
            r61 = HELPERS.read_gray(r61_path)
            appearance_records.append({**base, "method": "R61v16", **HELPERS.appearance_metrics(raw, r61, core)})
            if index in fixed:
                montage_rows.append((index, raw, r96))
        HELPERS.save_montage(
            OUTPUT / "figures" / f"{sequence}_raw_r96e44_diff.png",
            montage_rows,
            model_label="R96 E44",
        )
        print(f"[real] {sequence}: {len(raw_paths)} frames", flush=True)

    recon_manifest = pd.DataFrame(reconstruction_records)
    recon_manifest.to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    appearance = pd.DataFrame(appearance_records)
    appearance.to_csv(OUTPUT / "appearance_per_frame.csv", index=False)
    appearance_summary = appearance.groupby(["sequence", "method"], sort=False).agg({
        "mean_abs_change_gray": ["mean", "median"], "p95_abs_change_gray": "median", "ssim_to_raw": "median",
        "edge_gain_on_raw_support": "median", "fine_detail_energy_ratio": "median",
        "off_source_strong_edge_fraction": "median", "dark_change_fraction_on_edge_band": "median",
        "mean_abs_change_flat_region_gray": "median", "tile_seam_residual_ratio": "median",
    })
    appearance_summary.columns = ["_".join(column).strip("_") for column in appearance_summary.columns]
    appearance_summary.reset_index().to_csv(OUTPUT / "appearance_sequence_summary.csv", index=False)

    motion_records: list[dict[str, object]] = []
    for _, row in locked.iterrows():
        sequence, step = str(row["sequence"]), int(row["step_index"])
        image_a = HELPERS.read_gray(reconstructed[(sequence, step)])
        image_b = HELPERS.read_gray(reconstructed[(sequence, step + 1)])
        tile_h, tile_w = image_a.shape[0] // 6, image_a.shape[1] // 8
        tile_row, tile_column = int(row["tile_row"]), int(row["tile_column"])
        y0, x0 = tile_row * tile_h, tile_column * tile_w
        tile_a = image_a[y0:y0 + tile_h, x0:x0 + tile_w]
        tile_b = image_b[y0:y0 + tile_h, x0:x0 + tile_w]
        phase_dx, phase_dy, response = HELPERS.phase_shift(tile_a, tile_b)
        try:
            dx, dy, ecc = HELPERS.bounded_ecc_shift(tile_a, tile_b, float(row["raw_dx_px"]), float(row["raw_dy_px"]))
            finite = all(math.isfinite(value) for value in (dx, dy, ecc))
        except cv2.error:
            dx, dy, ecc, finite = math.nan, math.nan, math.nan, False
        limit = max(12.0, float(row["expected_dx_px"]) * 2.5)
        raw_valid = bool(row["raw_reference_valid"])
        evaluable = bool(finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
        valid = raw_valid and evaluable
        raw_dx, raw_dy = float(row["raw_dx_px"]), float(row["raw_dy_px"])
        um_per_px = float(row["object_um_per_px"])
        motion_records.append({
            "sequence": sequence, "magnification": float(row["magnification"]),
            "nominal_step_um": float(row["nominal_step_um"]), "object_um_per_px": um_per_px,
            "expected_dx_px": float(row["expected_dx_px"]), "step_index": step, "tile_id": row["tile_id"],
            "tile_row": tile_row, "tile_column": tile_column, "raw_dx_px": raw_dx, "raw_dy_px": raw_dy,
            "raw_response": float(row["raw_response"]), "r96_phase_dx_px": phase_dx,
            "r96_phase_dy_px": phase_dy, "r96_response": response, "r96_dx_px": dx, "r96_dy_px": dy,
            "r96_ecc": ecc, "raw_reference_valid": raw_valid, "r96_evaluable": evaluable, "valid": valid,
            "direction_agreement": bool(np.sign(raw_dx) == np.sign(dx)) if valid and abs(raw_dx) > .05 and abs(dx) > .05 else False,
            "r96_over_raw_abs_dx": abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan,
            "vector_difference_um": math.hypot(dx - raw_dx, dy - raw_dy) * um_per_px if valid else math.nan,
        })
    motion = pd.DataFrame(motion_records)
    motion.to_csv(OUTPUT / "r96_motion_measurements.csv", index=False)
    r96_summary = summarize_r96_motion(motion)
    r61_summary = standardized_r61_summary(locked)
    motion_summary = pd.concat([r61_summary, r96_summary], ignore_index=True)
    motion_summary.to_csv(OUTPUT / "motion_sequence_summary.csv", index=False)

    summary = {
        "status": "complete", "checkpoint_epoch": int(checkpoint["epoch"]),
        "unique_real_frames": len(reconstruction_records), "appearance_rows": len(appearance),
        "motion_measurements": len(motion), "elapsed_seconds": time.perf_counter() - started,
        "r96_motion_by_sequence": r96_summary.to_dict(orient="records"),
        "r61_motion_by_sequence": r61_summary.to_dict(orient="records"),
        "appearance_by_sequence": appearance_summary.reset_index().to_dict(orient="records"),
        "reconstruction_hashes_verified": all(
            sha256_file(Path(row["output_path"])) == row["output_sha256"] for row in reconstruction_records
        ),
        "notes": [
            "All 301 unique real frames were reconstructed.",
            "Every locked R68 Raw-selected motion measurement was reused without changing eligibility.",
            "Appearance-to-Raw values diagnose change and artifacts; they are not clean-target accuracy.",
        ],
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
