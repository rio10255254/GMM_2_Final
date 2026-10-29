"""Run the predeclared R96 real-microscope holdout audit."""
from __future__ import annotations

import argparse
import csv
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
from skimage.metrics import structural_similarity
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config" / "real_holdout_epoch032_protocol.json"
MODEL_PATH = ROOT / "model" / "r96_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r96_holdout_model", MODEL_PATH)
INFERENCE = load_module("r96_holdout_inference", INFERENCE_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not decode {path}")
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(path)


def as_bool(value: object) -> bool:
    return str(value).lower() == "true"


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
    edge_a, edge_b = edge_image(a), edge_image(b)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(edge_a, edge_b, window)
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


def seam_residual_ratio(raw: np.ndarray, reconstructed: np.ndarray, core: int) -> float:
    residual = np.abs(reconstructed.astype(np.float32) - raw.astype(np.float32))
    seam = np.zeros(raw.shape, dtype=bool)
    reference = np.zeros(raw.shape, dtype=bool)
    for x in range(core, raw.shape[1], core):
        seam[:, max(0, x - 1) : min(raw.shape[1], x + 2)] = True
        reference[:, max(0, x - 12) : max(0, x - 7)] = True
        reference[:, min(raw.shape[1], x + 7) : min(raw.shape[1], x + 12)] = True
    for y in range(core, raw.shape[0], core):
        seam[max(0, y - 1) : min(raw.shape[0], y + 2), :] = True
        reference[max(0, y - 12) : max(0, y - 7), :] = True
        reference[min(raw.shape[0], y + 7) : min(raw.shape[0], y + 12), :] = True
    if not seam.any() or not reference.any():
        return 1.0
    return float(residual[seam].mean() / max(float(residual[reference].mean()), 1e-9))


def appearance_metrics(raw: np.ndarray, reconstructed: np.ndarray, core: int) -> dict[str, float]:
    raw_f, model_f = raw.astype(np.float32), reconstructed.astype(np.float32)
    difference = model_f - raw_f
    absolute = np.abs(difference)
    raw_gradient, model_gradient = gradient_magnitude(raw), gradient_magnitude(reconstructed)
    support = raw_gradient >= float(np.percentile(raw_gradient, 85))
    distance = cv2.distanceTransform((~support).astype(np.uint8), cv2.DIST_L2, 5)
    model_strong = model_gradient >= float(np.percentile(model_gradient, 95))
    raw_detail = raw_f - cv2.GaussianBlur(raw_f, (0, 0), 2.0)
    model_detail = model_f - cv2.GaussianBlur(model_f, (0, 0), 2.0)
    edge_band = cv2.dilate(support.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    flat = distance > 5.0
    return {
        "mean_signed_change_gray": float(difference.mean()),
        "mean_abs_change_gray": float(absolute.mean()),
        "p95_abs_change_gray": float(np.percentile(absolute, 95)),
        "fraction_changed_over_10_gray": float(np.mean(absolute > 10.0)),
        "ssim_to_raw": float(structural_similarity(raw_f, model_f, data_range=255)),
        "edge_gain_on_raw_support": float(
            np.median(model_gradient[support]) / max(float(np.median(raw_gradient[support])), 1e-9)
        ),
        "fine_detail_energy_ratio": float(np.std(model_detail) / max(float(np.std(raw_detail)), 1e-9)),
        "off_source_strong_edge_fraction": float(np.mean(distance[model_strong] > 3.0)),
        "dark_change_fraction_on_edge_band": float(np.mean(difference[edge_band] < -10.0)),
        "bright_change_fraction_on_edge_band": float(np.mean(difference[edge_band] > 10.0)),
        "mean_abs_change_flat_region_gray": float(np.mean(absolute[flat])),
        "tile_seam_residual_ratio": seam_residual_ratio(raw, reconstructed, core),
    }


def label_panel(image: np.ndarray, label: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(panel, (0, 0), (330, 48), (0, 0, 0), -1)
    cv2.putText(panel, label, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
    return panel


def save_montage(
    path: Path,
    rows: list[tuple[int, np.ndarray, np.ndarray]],
    *,
    model_label: str = "R96 E32",
) -> None:
    sheets: list[np.ndarray] = []
    for index, raw, reconstructed in rows:
        scale = min(1.0, 512.0 / raw.shape[1])
        size = (int(raw.shape[1] * scale), int(raw.shape[0] * scale))
        raw_small = cv2.resize(raw, size, interpolation=cv2.INTER_AREA)
        rec_small = cv2.resize(reconstructed, size, interpolation=cv2.INTER_AREA)
        diff = np.clip(np.abs(reconstructed.astype(np.int16) - raw.astype(np.int16)) * 8, 0, 255).astype(np.uint8)
        diff_small = cv2.resize(diff, size, interpolation=cv2.INTER_AREA)
        sheets.append(np.concatenate([
            label_panel(raw_small, f"RAW frame {index}"),
            label_panel(rec_small, model_label),
            label_panel(diff_small, "ABS DIFF x8"),
        ], axis=1))
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), np.concatenate(sheets, axis=0))


def summarize_motion(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for sequence, group in table.groupby("sequence", sort=False):
        reference = group.loc[group["raw_reference_valid"]]
        valid = group.loc[group["valid"]]
        um_per_px = float(group["object_um_per_px"].iloc[0])
        raw_step = valid["raw_dx_px"].abs() * um_per_px
        model_step = valid["r96_dx_px"].abs() * um_per_px
        scale = valid["r96_over_raw_abs_dx"]
        response_ratio = valid["r96_response"] / valid["raw_response"].clip(lower=1e-9)
        rows.append({
            "sequence": sequence,
            "magnification": float(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
            "selected_steps": int(group["step_index"].nunique()),
            "selected_tiles": int(group["tile_id"].nunique()),
            "measurements": int(len(group)),
            "raw_reference_measurements": int(len(reference)),
            "valid_measurements": int(len(valid)),
            "valid_fraction_within_raw_reference": float(len(valid) / max(len(reference), 1)),
            "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
            "median_model_over_raw_abs_dx": float(scale.median()),
            "median_scale_error_fraction": float(abs(scale.median() - 1.0)),
            "median_vector_difference_um": float(valid["vector_difference_um"].median()),
            "p95_vector_difference_um": float(valid["vector_difference_um"].quantile(0.95)),
            "median_difference_of_commanded_step": float(
                valid["vector_difference_um"].median() / float(group["nominal_step_um"].iloc[0])
            ),
            "p95_difference_of_commanded_step": float(
                valid["vector_difference_um"].quantile(0.95) / float(group["nominal_step_um"].iloc[0])
            ),
            "raw_step_std_um": float(raw_step.std(ddof=1)),
            "r96_step_std_um": float(model_step.std(ddof=1)),
            "r96_over_raw_step_std": float(model_step.std(ddof=1) / max(float(raw_step.std(ddof=1)), 1e-12)),
            "median_response_ratio": float(response_ratio.median()),
            "median_r96_ecc": float(valid["r96_ecc"].median()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("declared_before_outputs"):
        raise RuntimeError("Protocol was not locked before outputs")
    output_root = ROOT / "results" / f"real_holdout_epoch_{int(protocol['checkpoint_epoch']):03d}"
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"Refusing to overwrite existing holdout output: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    write_json(output_root / "protocol_snapshot.json", protocol)

    sequence_config_path = Path(PROJECT_ROOT / protocol["source_sequence_config"])
    locked_path = Path(PROJECT_ROOT / protocol["locked_raw_measurements"])
    config = read_json(sequence_config_path)
    locked = pd.read_csv(locked_path)
    checkpoint_path = Path(PROJECT_ROOT / protocol["checkpoint"])
    design = read_json(DESIGN_PATH)
    device_name = args.device or protocol["inference"]["device"]
    device = torch.device(device_name if torch.cuda.is_available() or not str(device_name).startswith("cuda") else "cpu")
    if device.type == "cuda":
        torch.cuda.set_per_process_memory_fraction(
            float(protocol["inference"]["maximum_process_memory_fraction"]), device=device
        )
    torch.set_num_threads(4)

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != int(protocol["checkpoint_epoch"]):
        raise RuntimeError("Checkpoint epoch mismatch")
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    model.eval().to(device)
    core = int(protocol["inference"]["core_size"])
    halo = int(protocol["inference"]["halo"])
    tile_batch = int(protocol["inference"]["tile_batch"])

    manifest = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_run_id": checkpoint["metadata"]["run_id"],
        "source_sequence_config_sha256": sha256_file(sequence_config_path),
        "locked_raw_measurements_sha256": sha256_file(locked_path),
        "device": str(device),
        "started_at_unix": time.time(),
    }
    write_json(output_root / "input_manifest.json", manifest)

    appearance_records: list[dict[str, object]] = []
    reconstruction_records: list[dict[str, object]] = []
    reconstructed_paths: dict[tuple[str, int], Path] = {}
    started = time.perf_counter()
    for sequence in protocol["sequences"]:
        row = config["sequences"][sequence]
        raw_dir = Path(row["raw_dir"])
        raw_paths = sorted(raw_dir.glob("frame_*.bmp"))
        if len(raw_paths) != int(row["frame_count"]):
            raise RuntimeError(f"{sequence}: frame count mismatch")
        appearance_indices = [len(raw_paths) - 1 if int(i) < 0 else int(i) for i in protocol["appearance_frame_indices"]]
        motion_indices = sorted({int(i) for step in protocol["motion_step_indices"] for i in (int(step), int(step) + 1)})
        selected_indices = sorted(set(appearance_indices) | set(motion_indices))
        montage_rows: list[tuple[int, np.ndarray, np.ndarray]] = []
        for index in selected_indices:
            if index >= len(raw_paths):
                raise RuntimeError(f"{sequence}: selected frame {index} is unavailable")
            raw = read_gray(raw_paths[index])
            tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
            frame_started = time.perf_counter()
            with torch.inference_mode():
                prediction = INFERENCE.reconstruct_tensor(
                    model, tensor, core_size=core, halo=halo, tile_batch=tile_batch
                )[0, 0]
            unbounded_min, unbounded_max = float(prediction.min()), float(prediction.max())
            reconstructed = np.rint(prediction.clamp(0.0, 1.0).cpu().numpy() * 255.0).astype(np.uint8)
            destination = output_root / "reconstructions" / sequence / raw_paths[index].name
            write_gray(destination, reconstructed)
            reconstructed_paths[(sequence, index)] = destination
            reconstruction_records.append({
                "sequence": sequence,
                "frame_index": index,
                "source_path": str(raw_paths[index]),
                "source_sha256": sha256_file(raw_paths[index]),
                "output_path": str(destination),
                "output_sha256": sha256_file(destination),
                "seconds": time.perf_counter() - frame_started,
                "unbounded_min": unbounded_min,
                "unbounded_max": unbounded_max,
            })
            if index in appearance_indices:
                appearance_records.append({
                    "sequence": sequence,
                    "magnification": float(row["magnification"]),
                    "nominal_step_um": float(row["nominal_step_um"]),
                    "frame_index": index,
                    **appearance_metrics(raw, reconstructed, core),
                })
                montage_rows.append((index, raw, reconstructed))
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            time.sleep(0.05)
        save_montage(output_root / "figures" / f"{sequence}_contact.png", montage_rows)
        print(f"[reconstruct] {sequence}: {len(selected_indices)} frames", flush=True)

    pd.DataFrame(reconstruction_records).to_csv(output_root / "reconstruction_manifest.csv", index=False)
    appearance = pd.DataFrame(appearance_records)
    appearance.to_csv(output_root / "appearance_metrics.csv", index=False)

    motion_records: list[dict[str, object]] = []
    selected_locked = locked.loc[
        locked["sequence"].isin(protocol["sequences"])
        & locked["step_index"].isin(protocol["motion_step_indices"])
    ].copy()
    for _, raw_row in selected_locked.iterrows():
        sequence = str(raw_row["sequence"])
        step = int(raw_row["step_index"])
        image_a = read_gray(reconstructed_paths[(sequence, step)])
        image_b = read_gray(reconstructed_paths[(sequence, step + 1)])
        tile_h, tile_w = image_a.shape[0] // 6, image_a.shape[1] // 8
        tile_row, tile_column = int(raw_row["tile_row"]), int(raw_row["tile_column"])
        y0, x0 = tile_row * tile_h, tile_column * tile_w
        tile_a = image_a[y0 : y0 + tile_h, x0 : x0 + tile_w]
        tile_b = image_b[y0 : y0 + tile_h, x0 : x0 + tile_w]
        phase_dx, phase_dy, response = phase_shift(tile_a, tile_b)
        try:
            dx, dy, ecc = bounded_ecc_shift(
                tile_a, tile_b, float(raw_row["raw_dx_px"]), float(raw_row["raw_dy_px"])
            )
            finite = all(math.isfinite(value) for value in (dx, dy, ecc))
        except cv2.error:
            dx, dy, ecc, finite = math.nan, math.nan, math.nan, False
        expected_px = float(raw_row["expected_dx_px"])
        limit = max(12.0, expected_px * 2.5)
        raw_valid = as_bool(raw_row["raw_reference_valid"])
        evaluable = bool(finite and ecc >= 0.75 and abs(dx) <= limit and abs(dy) <= limit)
        valid = raw_valid and evaluable
        raw_dx, raw_dy = float(raw_row["raw_dx_px"]), float(raw_row["raw_dy_px"])
        direction = bool(np.sign(raw_dx) == np.sign(dx)) if valid and abs(raw_dx) > 0.05 and abs(dx) > 0.05 else False
        um_per_px = float(raw_row["object_um_per_px"])
        vector = math.hypot(dx - raw_dx, dy - raw_dy) * um_per_px if valid else math.nan
        scale = abs(dx) / max(abs(raw_dx), 1e-9) if valid else math.nan
        motion_records.append({
            "sequence": sequence,
            "magnification": float(raw_row["magnification"]),
            "nominal_step_um": float(raw_row["nominal_step_um"]),
            "object_um_per_px": um_per_px,
            "expected_dx_px": expected_px,
            "step_index": step,
            "tile_id": raw_row["tile_id"],
            "tile_row": tile_row,
            "tile_column": tile_column,
            "raw_dx_px": raw_dx,
            "raw_dy_px": raw_dy,
            "raw_response": float(raw_row["raw_response"]),
            "r96_phase_dx_px": phase_dx,
            "r96_phase_dy_px": phase_dy,
            "r96_response": response,
            "r96_dx_px": dx,
            "r96_dy_px": dy,
            "r96_ecc": ecc,
            "raw_reference_valid": raw_valid,
            "r96_evaluable": evaluable,
            "valid": valid,
            "direction_agreement": direction,
            "r96_over_raw_abs_dx": scale,
            "vector_difference_um": vector,
        })
    motion = pd.DataFrame(motion_records)
    motion.to_csv(output_root / "motion_measurements.csv", index=False)
    motion_summary = summarize_motion(motion)
    motion_summary.to_csv(output_root / "motion_sequence_summary.csv", index=False)

    appearance_summary = appearance.groupby("sequence", sort=False).agg({
        "mean_abs_change_gray": "mean",
        "p95_abs_change_gray": "mean",
        "ssim_to_raw": "mean",
        "edge_gain_on_raw_support": "mean",
        "fine_detail_energy_ratio": "mean",
        "off_source_strong_edge_fraction": "mean",
        "dark_change_fraction_on_edge_band": "mean",
        "mean_abs_change_flat_region_gray": "mean",
        "tile_seam_residual_ratio": "mean",
    }).reset_index()
    appearance_summary.to_csv(output_root / "appearance_sequence_summary.csv", index=False)

    summary = {
        "status": "complete",
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "provisional": True,
        "sequence_count": len(protocol["sequences"]),
        "unique_reconstructed_frames": len(reconstruction_records),
        "appearance_frames": len(appearance),
        "motion_measurements": len(motion),
        "elapsed_seconds": time.perf_counter() - started,
        "appearance_sequence_medians": {
            key: float(appearance_summary[key].median())
            for key in appearance_summary.columns if key != "sequence"
        },
        "motion_sequence_medians": {
            key: float(motion_summary[key].median())
            for key in motion_summary.columns
            if key not in {"sequence"}
        },
        "motion_by_sequence": motion_summary.to_dict(orient="records"),
        "notes": [
            "Appearance metrics compare R96 with Raw and are diagnostics, not clean-truth accuracy.",
            "Motion uses the pre-existing Raw-selected tiles and Raw reference shifts from R68.",
            "Only the five predeclared temporal positions per sequence are evaluated here.",
        ],
    }
    manifest["finished_at_unix"] = time.time()
    manifest["elapsed_seconds"] = summary["elapsed_seconds"]
    write_json(output_root / "input_manifest.json", manifest)
    write_json(output_root / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
