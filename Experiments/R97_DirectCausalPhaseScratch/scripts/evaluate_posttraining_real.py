"""Fixed-endpoint real microscope and locked-motion validation for R97 E48."""
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
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r97_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
HELPERS_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/R96_LocalizedEvidenceProtectedScratch/scripts/evaluate_real_holdout.py')
)
R96_MOTION_PATH = Path(
    str(PROJECT_ROOT / 'Experiments/R96_LocalizedEvidenceProtectedScratch/results/final_validation/real_generalization/r96_motion_measurements.csv')
)
OUTPUT = ROOT / "results" / "posttraining_validation" / "real_generalization"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r97_post_real_model", MODEL_PATH)
INFERENCE = load_module("r97_post_real_inference", INFERENCE_PATH)
HELPERS = load_module("r97_post_real_helpers", HELPERS_PATH)


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


def robust_mad(values: pd.Series) -> float:
    array = values.to_numpy(float)
    median = np.median(array)
    return float(1.4826 * np.median(np.abs(array - median)))


def label_panel(image: np.ndarray, label: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 40), (0, 0, 0), -1)
    cv2.putText(panel, label, (8, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    return panel


def save_comparison_montage(
    path: Path,
    rows: list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
) -> None:
    sheets: list[np.ndarray] = []
    for index, raw, r61, r96, r97 in rows:
        scale = min(1.0, 512.0 / raw.shape[1])
        size = (int(raw.shape[1] * scale), int(raw.shape[0] * scale))
        panels: list[np.ndarray] = []
        for image, label in ((raw, f"Raw frame {index}"), (r61, "R61v16"), (r96, "R96 E44"), (r97, "R97 E48")):
            panels.append(label_panel(cv2.resize(image, size, interpolation=cv2.INTER_AREA), label))
        difference = np.clip(np.abs(r97.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
        panels.append(label_panel(cv2.resize(difference, size, interpolation=cv2.INTER_AREA), "R97 abs diff x8"))
        sheets.append(np.concatenate(panels, axis=1))
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), np.concatenate(sheets, axis=0)):
        raise RuntimeError(path)


def canonical_locked_table(locked: pd.DataFrame, r96: pd.DataFrame, r97: pd.DataFrame) -> pd.DataFrame:
    keys = ["sequence", "step_index", "tile_id"]
    if any(frame.duplicated(keys).any() for frame in (locked, r96, r97)):
        raise RuntimeError("Motion keys are not unique")
    base_columns = keys + [
        "magnification", "nominal_step_um", "object_um_per_px", "raw_dx_px", "raw_dy_px",
        "raw_response", "raw_reference_valid",
    ]
    result = locked[base_columns].copy()
    result = result.merge(
        locked[keys + ["r61_dx_px", "r61_dy_px", "r61_response", "r61_ecc", "r61_evaluable", "valid"]]
        .rename(columns={"valid": "r61_valid"}),
        on=keys,
        how="left",
        validate="one_to_one",
    )
    result = result.merge(
        r96[keys + ["r96_dx_px", "r96_dy_px", "r96_response", "r96_ecc", "r96_evaluable", "valid"]]
        .rename(columns={"valid": "r96_valid"}),
        on=keys,
        how="left",
        validate="one_to_one",
    )
    result = result.merge(
        r97[keys + ["r97_dx_px", "r97_dy_px", "r97_response", "r97_ecc", "r97_evaluable", "valid"]]
        .rename(columns={"valid": "r97_valid"}),
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if len(result) != len(locked) or result[keys].isna().any().any():
        raise RuntimeError("Locked motion merge is incomplete")
    for method in ("r61", "r96", "r97"):
        evaluable = result[f"{method}_evaluable"].astype(bool)
        required = [f"{method}_dx_px", f"{method}_dy_px", f"{method}_response", f"{method}_ecc"]
        if result.loc[evaluable, required].isna().any().any():
            raise RuntimeError(f"{method}: evaluable motion rows contain missing coordinates")
    result["common_valid"] = (
        result["raw_reference_valid"].astype(bool)
        & result["r61_valid"].astype(bool)
        & result["r96_valid"].astype(bool)
        & result["r97_valid"].astype(bool)
    )
    return result


def motion_summary(wide: pd.DataFrame, *, common_only: bool) -> pd.DataFrame:
    methods = {
        "Raw": ("raw_dx_px", "raw_dy_px", "raw_response", None, "raw_reference_valid"),
        "R61v16": ("r61_dx_px", "r61_dy_px", "r61_response", "r61_ecc", "r61_valid"),
        "R96E44": ("r96_dx_px", "r96_dy_px", "r96_response", "r96_ecc", "r96_valid"),
        "R97E48": ("r97_dx_px", "r97_dy_px", "r97_response", "r97_ecc", "r97_valid"),
    }
    rows: list[dict[str, object]] = []
    for sequence, sequence_rows in wide.groupby("sequence", sort=False):
        reference_count = int(sequence_rows["raw_reference_valid"].astype(bool).sum())
        for method, (dx_name, dy_name, response_name, ecc_name, valid_name) in methods.items():
            valid_mask = sequence_rows["common_valid"].astype(bool) if common_only else sequence_rows[valid_name].astype(bool)
            group = sequence_rows.loc[valid_mask]
            scale_um = float(sequence_rows["object_um_per_px"].iloc[0])
            nominal = float(sequence_rows["nominal_step_um"].iloc[0])
            step = group[dx_name].abs() * scale_um
            raw_step = group["raw_dx_px"].abs() * scale_um
            vector_delta = np.hypot(
                group[dx_name].to_numpy(float) - group["raw_dx_px"].to_numpy(float),
                group[dy_name].to_numpy(float) - group["raw_dy_px"].to_numpy(float),
            ) * scale_um
            response_ratio = group[response_name] / group["raw_response"].clip(lower=1e-9)
            ratio = step / raw_step.clip(lower=1e-9)
            rows.append({
                "sequence": sequence,
                "method": method,
                "magnification": float(sequence_rows["magnification"].iloc[0]),
                "nominal_step_um": nominal,
                "common_only": bool(common_only),
                "raw_reference_measurements": reference_count,
                "valid_measurements": int(len(group)),
                "valid_fraction_within_raw_reference": float(len(group) / max(reference_count, 1)),
                "median_abs_dx_um": float(step.median()),
                "signed_bias_to_nominal_um": float(step.median() - nominal),
                "median_abs_error_to_nominal_um": float(np.median(np.abs(step.to_numpy(float) - nominal))),
                "step_std_um": float(step.std(ddof=1)),
                "step_robust_mad_um": robust_mad(step),
                "median_model_over_raw_abs_dx": float(ratio.median()),
                "median_scale_error_fraction": float(abs(ratio.median() - 1.0)),
                "median_vector_difference_from_raw_um": float(np.median(vector_delta)),
                "p95_vector_difference_from_raw_um": float(np.quantile(vector_delta, 0.95)),
                "median_response_ratio": float(response_ratio.median()),
                "median_ecc": 1.0 if ecc_name is None else float(group[ecc_name].median()),
            })
    return pd.DataFrame(rows)


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite validation output: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("locked_before_new_posttraining_outputs"):
        raise RuntimeError("Posttraining protocol is not locked")
    arm = protocol["real_microscope_arm"]
    sequence_config_path = Path(PROJECT_ROOT / arm["source_sequence_config"])
    locked_path = Path(PROJECT_ROOT / arm["locked_raw_measurements"])
    checkpoint_path = Path(PROJECT_ROOT / protocol["checkpoint"])
    r96_root = Path(PROJECT_ROOT / arm["r96_reconstruction_root"])
    for required in (sequence_config_path, locked_path, checkpoint_path, R96_MOTION_PATH):
        if not required.is_file():
            raise FileNotFoundError(required)
    config = read_json(sequence_config_path)
    locked = pd.read_csv(locked_path)
    r96_motion = pd.read_csv(R96_MOTION_PATH)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != int(protocol["primary_checkpoint_epoch"]):
        raise RuntimeError("Final checkpoint epoch mismatch")
    design = read_json(DESIGN_PATH)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device(arm["inference"]["device"] if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    torch.set_num_threads(4)
    core = int(arm["inference"]["core_size"])
    halo = int(arm["inference"]["halo"])
    tile_batch = int(arm["inference"]["tile_batch"])
    write_json(OUTPUT / "protocol_snapshot.json", protocol)
    manifest = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "run_id": checkpoint["metadata"]["run_id"],
        "checkpoint_state": protocol["checkpoint_state"],
        "sequence_config_sha256": sha256_file(sequence_config_path),
        "locked_measurements_sha256": sha256_file(locked_path),
        "r96_motion_sha256": sha256_file(R96_MOTION_PATH),
        "device": str(device),
        "precision": arm["inference"]["precision"],
    }
    write_json(OUTPUT / "input_manifest.json", manifest)

    appearance_records: list[dict[str, object]] = []
    reconstruction_records: list[dict[str, object]] = []
    reconstructed: dict[tuple[str, int], Path] = {}
    started = time.perf_counter()
    completed_frames = 0
    total_frames = sum(int(config["sequences"][name]["frame_count"]) for name in arm["sequences"])
    for sequence in arm["sequences"]:
        item = config["sequences"][sequence]
        raw_paths = sorted(Path(item["raw_dir"]).glob("frame_*.bmp"))
        r61_paths = sorted(Path(item["recon_dir"]).glob("frame_*.bmp"))
        r96_paths = [r96_root / sequence / path.name for path in raw_paths]
        if len(raw_paths) != int(item["frame_count"]) or len(r61_paths) != len(raw_paths):
            raise RuntimeError(f"{sequence}: frame inventory mismatch")
        if not all(path.is_file() for path in r96_paths):
            raise RuntimeError(f"{sequence}: R96 comparator inventory mismatch")
        fixed = [len(raw_paths) - 1 if int(i) < 0 else int(i) for i in arm["fixed_visual_indices"]]
        montage_rows: list[tuple[int, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []
        for index, (raw_path, r61_path, r96_path) in enumerate(zip(raw_paths, r61_paths, r96_paths)):
            raw = HELPERS.read_gray(raw_path)
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            frame_started = time.perf_counter()
            with torch.inference_mode():
                prediction = INFERENCE.reconstruct_tensor(
                    model, tensor, core_size=core, halo=halo, tile_batch=tile_batch
                )[0, 0]
            minimum, maximum = float(prediction.min()), float(prediction.max())
            low_clip = float((prediction <= 0.0).float().mean())
            high_clip = float((prediction >= 1.0).float().mean())
            r97 = np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
            destination = OUTPUT / "reconstructions" / sequence / raw_path.name
            HELPERS.write_gray(destination, r97)
            reconstructed[(sequence, index)] = destination
            reconstruction_records.append({
                "sequence": sequence,
                "frame_index": index,
                "source_path": str(raw_path),
                "source_sha256": sha256_file(raw_path),
                "output_path": str(destination),
                "output_sha256": sha256_file(destination),
                "seconds": time.perf_counter() - frame_started,
                "unbounded_min": minimum,
                "unbounded_max": maximum,
                "low_clip_fraction": low_clip,
                "high_clip_fraction": high_clip,
            })
            base = {
                "sequence": sequence,
                "magnification": float(item["magnification"]),
                "nominal_step_um": float(item["nominal_step_um"]),
                "frame_index": index,
            }
            r61 = HELPERS.read_gray(r61_path)
            r96 = HELPERS.read_gray(r96_path)
            for method, image in (("R61v16", r61), ("R96E44", r96), ("R97E48", r97)):
                appearance_records.append({**base, "method": method, **HELPERS.appearance_metrics(raw, image, core)})
            if index in fixed:
                montage_rows.append((index, raw, r61, r96, r97))
            completed_frames += 1
            elapsed = time.perf_counter() - started
            write_json(OUTPUT / "progress.json", {
                "status": "running",
                "sequence": sequence,
                "frame_index": index,
                "completed_frames": completed_frames,
                "total_frames": total_frames,
                "elapsed_seconds": elapsed,
                "estimated_remaining_seconds": elapsed / completed_frames * (total_frames - completed_frames),
            })
            if completed_frames % 10 == 0 or completed_frames == total_frames:
                print(f"[real] {completed_frames}/{total_frames} {sequence} frame {index}", flush=True)
        save_comparison_montage(OUTPUT / "figures" / f"{sequence}_comparison.png", montage_rows)

    recon_manifest = pd.DataFrame(reconstruction_records)
    recon_manifest.to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    appearance = pd.DataFrame(appearance_records)
    appearance.to_csv(OUTPUT / "appearance_per_frame.csv", index=False)
    appearance_summary = appearance.groupby(["sequence", "method"], sort=False).agg({
        "mean_signed_change_gray": ["mean", "median"],
        "mean_abs_change_gray": ["mean", "median"],
        "p95_abs_change_gray": "median",
        "ssim_to_raw": "median",
        "edge_gain_on_raw_support": "median",
        "fine_detail_energy_ratio": "median",
        "off_source_strong_edge_fraction": "median",
        "dark_change_fraction_on_edge_band": "median",
        "bright_change_fraction_on_edge_band": "median",
        "mean_abs_change_flat_region_gray": "median",
        "tile_seam_residual_ratio": "median",
    })
    appearance_summary.columns = ["_".join(column).strip("_") for column in appearance_summary.columns]
    appearance_summary = appearance_summary.reset_index()
    appearance_summary.to_csv(OUTPUT / "appearance_sequence_summary.csv", index=False)

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
            dx, dy, ecc = HELPERS.bounded_ecc_shift(
                tile_a, tile_b, float(row["raw_dx_px"]), float(row["raw_dy_px"])
            )
            finite = all(math.isfinite(value) for value in (dx, dy, ecc))
        except cv2.error:
            dx, dy, ecc, finite = math.nan, math.nan, math.nan, False
        limit = max(12.0, float(row["expected_dx_px"]) * 2.5)
        raw_valid = bool(row["raw_reference_valid"])
        evaluable = bool(finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
        valid = raw_valid and evaluable
        motion_records.append({
            "sequence": sequence,
            "step_index": step,
            "tile_id": row["tile_id"],
            "tile_row": tile_row,
            "tile_column": tile_column,
            "r97_phase_dx_px": phase_dx,
            "r97_phase_dy_px": phase_dy,
            "r97_response": response,
            "r97_dx_px": dx,
            "r97_dy_px": dy,
            "r97_ecc": ecc,
            "r97_evaluable": evaluable,
            "valid": valid,
        })
    r97_motion = pd.DataFrame(motion_records)
    r97_motion.to_csv(OUTPUT / "r97_motion_measurements.csv", index=False)
    wide = canonical_locked_table(locked, r96_motion, r97_motion)
    wide.to_csv(OUTPUT / "motion_locked_wide.csv", index=False)
    method_summary = motion_summary(wide, common_only=False)
    common_summary = motion_summary(wide, common_only=True)
    method_summary.to_csv(OUTPUT / "motion_method_valid_summary.csv", index=False)
    common_summary.to_csv(OUTPUT / "motion_common_valid_summary.csv", index=False)

    elapsed = time.perf_counter() - started
    summary = {
        "status": "complete",
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "unique_real_frames": len(reconstruction_records),
        "appearance_rows": len(appearance),
        "locked_motion_measurements": len(r97_motion),
        "common_valid_motion_measurements": int(wide["common_valid"].sum()),
        "elapsed_seconds": elapsed,
        "reconstruction_hashes_verified": all(
            sha256_file(Path(row["output_path"])) == row["output_sha256"] for row in reconstruction_records
        ),
        "output_finite": bool(np.isfinite(recon_manifest[["unbounded_min", "unbounded_max"]].to_numpy()).all()),
        "maximum_low_clip_fraction": float(recon_manifest["low_clip_fraction"].max()),
        "maximum_high_clip_fraction": float(recon_manifest["high_clip_fraction"].max()),
        "appearance_by_sequence": appearance_summary.to_dict(orient="records"),
        "motion_method_valid": method_summary.to_dict(orient="records"),
        "motion_common_valid": common_summary.to_dict(orient="records"),
        "notes": [
            "All 301 unique real frames were reconstructed from the fixed E48 EMA endpoint.",
            "The exact pre-existing Raw-selected tile and adjacent-step eligibility was reused.",
            "Appearance-to-Raw values measure change and artifacts, not clean-target accuracy.",
            "Common-valid motion rows make Raw, R61, R96 and R97 denominators identical.",
        ],
    }
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "progress.json", {
        "status": "complete",
        "completed_frames": total_frames,
        "total_frames": total_frames,
        "elapsed_seconds": elapsed,
    })
    print(json.dumps({
        "status": summary["status"],
        "unique_real_frames": summary["unique_real_frames"],
        "locked_motion_measurements": summary["locked_motion_measurements"],
        "common_valid_motion_measurements": summary["common_valid_motion_measurements"],
        "elapsed_seconds": summary["elapsed_seconds"],
    }, indent=2), flush=True)


def finalize_existing() -> None:
    """Finish tables after a post-reconstruction aggregation failure without rerunning inference."""
    protocol = read_json(PROTOCOL_PATH)
    arm = protocol["real_microscope_arm"]
    locked_path = Path(PROJECT_ROOT / arm["locked_raw_measurements"])
    locked = pd.read_csv(locked_path)
    r96_motion = pd.read_csv(R96_MOTION_PATH)
    r97_motion = pd.read_csv(OUTPUT / "r97_motion_measurements.csv")
    recon_manifest = pd.read_csv(OUTPUT / "reconstruction_manifest.csv")
    appearance = pd.read_csv(OUTPUT / "appearance_per_frame.csv")
    appearance_summary = pd.read_csv(OUTPUT / "appearance_sequence_summary.csv")
    if len(recon_manifest) != 301 or len(r97_motion) != len(locked) or len(appearance) != 903:
        raise RuntimeError("Existing posttraining outputs are incomplete")
    wide = canonical_locked_table(locked, r96_motion, r97_motion)
    wide.to_csv(OUTPUT / "motion_locked_wide.csv", index=False)
    method_summary = motion_summary(wide, common_only=False)
    common_summary = motion_summary(wide, common_only=True)
    method_summary.to_csv(OUTPUT / "motion_method_valid_summary.csv", index=False)
    common_summary.to_csv(OUTPUT / "motion_common_valid_summary.csv", index=False)
    summary = {
        "status": "complete",
        "checkpoint_epoch": int(protocol["primary_checkpoint_epoch"]),
        "unique_real_frames": len(recon_manifest),
        "appearance_rows": len(appearance),
        "locked_motion_measurements": len(r97_motion),
        "common_valid_motion_measurements": int(wide["common_valid"].sum()),
        "elapsed_seconds": None,
        "reconstruction_hashes_verified": all(
            sha256_file(Path(row["output_path"])) == row["output_sha256"]
            for row in recon_manifest.to_dict(orient="records")
        ),
        "output_finite": bool(np.isfinite(recon_manifest[["unbounded_min", "unbounded_max"]].to_numpy()).all()),
        "maximum_low_clip_fraction": float(recon_manifest["low_clip_fraction"].max()),
        "maximum_high_clip_fraction": float(recon_manifest["high_clip_fraction"].max()),
        "appearance_by_sequence": appearance_summary.to_dict(orient="records"),
        "motion_method_valid": method_summary.to_dict(orient="records"),
        "motion_common_valid": common_summary.to_dict(orient="records"),
        "notes": [
            "All 301 unique real frames were reconstructed from the fixed E48 EMA endpoint.",
            "The exact pre-existing Raw-selected tile and adjacent-step eligibility was reused.",
            "Appearance-to-Raw values measure change and artifacts, not clean-target accuracy.",
            "Common-valid motion rows make Raw, R61, R96 and R97 denominators identical.",
            "Aggregation was finalized from preserved manifests after the original completeness check incorrectly rejected legitimate non-evaluable NaNs.",
        ],
    }
    write_json(OUTPUT / "summary.json", summary)
    write_json(OUTPUT / "progress.json", {
        "status": "complete",
        "completed_frames": 301,
        "total_frames": 301,
        "aggregation_finalized_from_existing_outputs": True,
    })
    print(json.dumps({
        "status": summary["status"],
        "unique_real_frames": summary["unique_real_frames"],
        "locked_motion_measurements": summary["locked_motion_measurements"],
        "common_valid_motion_measurements": summary["common_valid_motion_measurements"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    if "--finalize-existing" in sys.argv:
        finalize_existing()
    else:
        main()
