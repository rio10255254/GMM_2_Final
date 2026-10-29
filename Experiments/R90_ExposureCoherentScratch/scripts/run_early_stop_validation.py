"""Run the locked R90 early-stop development comparison.

This script reconstructs the same fixed real frames and SEM exposure stack for
every declared checkpoint.  It deliberately does not access the sealed holdout.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import cv2
import numpy as np
import pandas as pd
from skimage.metrics import structural_similarity
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "early_stop_validation.json"
R78_CONFIG = Path(str(PROJECT_ROOT / 'Experiments/R78_R75v2_BroadRealMicroscopeGeneralization/config/experiment.json'))
INFERENCE = ROOT / "inference" / "reconstruct.py"
RESULTS = ROOT / "results" / "early_stop_validation"
REPORTS = ROOT / "reports" / "early_stop_validation"
RECON = RESULTS / "reconstructions"
TABLES = RESULTS / "tables"
FIGURES = REPORTS / "figures"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("frame_*.bmp") if path.is_file())


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not decode {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", image)
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(path)


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


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


def checkpoint_metrics(payload: dict[str, Any]) -> dict[str, float | int]:
    validation = payload["metrics"]["validation"]
    domains = validation["normalized_domain_ratios"]
    diagnostics = validation["diagnostics"]
    return {
        "balanced_score": float(validation["balanced_score"]),
        "mean_normalized_domain_error": float(validation["mean_normalized_domain_error"]),
        "boundary_ratio": float(domains["boundary"]),
        "identity_texture_ratio": float(domains["texture"]),
        "photometry_ratio": float(domains["photometry"]),
        "exposure_stability_ratio": float(domains["exposure_stability"]),
        "motion_ratio": float(domains["motion"]),
        "identity_mean_abs_gray": float(diagnostics["identity_mean_abs_gray"]),
        "raw_clear_added_topology_failures": int(diagnostics["raw_clear_added_topology_failures"]),
        "motion_mae_px": float(diagnostics["motion_mae_px"]),
        "motion_p95_px": float(diagnostics["motion_p95_px"]),
        "signed_motion_bias_x_px": float(diagnostics["signed_motion_bias_x_px"]),
        "signed_motion_bias_y_px": float(diagnostics["signed_motion_bias_y_px"]),
        "low_branch_edge_leakage_gray": float(diagnostics["low_branch_edge_leakage_gray"]),
    }


def fixed_sources(protocol: dict[str, Any], r78: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    appearance: list[dict[str, Any]] = []
    indices_rule = protocol["development_arms"]["real_appearance"]["fixed_frame_indices"]
    for sequence in protocol["development_arms"]["real_appearance"]["sequences"]:
        item = r78["sequences"][sequence]
        paths = image_paths(Path(PROJECT_ROOT / item["raw_dir"]))
        if len(paths) != int(item["frame_count"]):
            raise RuntimeError(f"{sequence}: expected {item['frame_count']} frames, found {len(paths)}")
        indices = [len(paths) - 1 if int(index) < 0 else int(index) for index in indices_rule]
        if len(indices) != len(set(indices)) or min(indices) < 0 or max(indices) >= len(paths):
            raise RuntimeError(f"{sequence}: invalid fixed frame indices {indices}")
        for index in indices:
            path = paths[index]
            appearance.append({
                "sequence": sequence,
                "magnification": int(item["magnification"]),
                "nominal_step_um": float(item["nominal_step_um"]),
                "frame_index": index,
                "source": str(path),
                "filename": path.name,
                "sha256": sha256_file(path),
            })
    sem: list[dict[str, Any]] = []
    sem_root = Path(PROJECT_ROOT / protocol["development_arms"]["sem_contour"]["optical_inputs"])
    for exposure in protocol["development_arms"]["sem_contour"]["exposures"]:
        path = sem_root / f"{int(exposure)}.bmp"
        if not path.is_file():
            raise FileNotFoundError(path)
        sem.append({"exposure": int(exposure), "source": str(path), "sha256": sha256_file(path)})
    if len(appearance) != int(protocol["development_arms"]["real_appearance"]["expected_frames"]):
        raise RuntimeError("Fixed appearance frame count differs from protocol")
    return appearance, sem


def reconstruct_one(module, model, source: Path, destination: Path, device: torch.device) -> tuple[str, float]:
    if destination.is_file():
        existing = read_gray(destination)
        if existing.shape == read_gray(source).shape:
            return sha256_file(destination), 0.0
    raw, dtype = module.read_gray(source)
    started = time.perf_counter()
    prediction = module.reconstruct_tensor(
        model,
        module.image_tensor(raw, device),
        core_size=512,
        halo=192,
        tile_batch=1,
        amp=True,
    )
    output = module.output_array(prediction, dtype)
    write_bmp(destination, output)
    return sha256_file(destination), time.perf_counter() - started


def panel(image: np.ndarray, label: str, width: int = 512, height: int = 384) -> np.ndarray:
    shown = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    shown = cv2.cvtColor(shown, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(shown, (0, 0), (width, 38), (0, 0, 0), -1)
    cv2.putText(shown, label, (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2, cv2.LINE_AA)
    return shown


def best_detail_crop(image: np.ndarray, size: int = 512) -> tuple[int, int, int]:
    height, width = image.shape
    size = min(size, height, width)
    energy = gradient_magnitude(image)
    best_score, best_y, best_x = -1.0, 0, 0
    step = max(64, size // 4)
    rows = sorted(set(list(range(0, max(1, height - size + 1), step)) + [height - size]))
    cols = sorted(set(list(range(0, max(1, width - size + 1), step)) + [width - size]))
    for y in rows:
        for x in cols:
            score = float(np.mean(energy[y:y + size, x:x + size]))
            if score > best_score:
                best_score, best_y, best_x = score, y, x
    return best_y, best_x, size


def make_montages(appearance_sources: list[dict[str, Any]], stages: list[int]) -> list[str]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    by_sequence: dict[str, list[dict[str, Any]]] = {}
    for row in appearance_sources:
        by_sequence.setdefault(str(row["sequence"]), []).append(row)
    for sequence, rows in by_sequence.items():
        chosen = next((row for row in rows if int(row["frame_index"]) == 24), rows[len(rows) // 2])
        raw = read_gray(Path(chosen["source"]))
        images = [("Raw", raw)]
        for epoch in stages:
            destination = RECON / "appearance" / f"E{epoch:03d}" / sequence / str(chosen["filename"])
            images.append((f"E{epoch}", read_gray(destination)))
        full_grid = np.vstack([
            np.hstack([panel(image, label) for label, image in images[row:row + 3]])
            for row in range(0, 9, 3)
        ])
        full_path = FIGURES / f"{sequence}_full.png"
        cv2.imwrite(str(full_path), full_grid)
        outputs.append(str(full_path))

        y, x, size = best_detail_crop(raw)
        crop_images = [(label, image[y:y + size, x:x + size]) for label, image in images]
        crop_grid = np.vstack([
            np.hstack([panel(image, label, 512, 512) for label, image in crop_images[row:row + 3]])
            for row in range(0, 9, 3)
        ])
        crop_path = FIGURES / f"{sequence}_detail.png"
        cv2.imwrite(str(crop_path), crop_grid)
        outputs.append(str(crop_path))
    return outputs


def main() -> int:
    protocol = read_json(PROTOCOL)
    r78 = read_json(R78_CONFIG)
    stages = [int(value) for value in protocol["stage_candidates"]]
    checkpoints = {
        epoch: Path(PROJECT_ROOT / protocol["checkpoint_root"]) / f"epoch_{epoch:03d}.pth.tar"
        for epoch in stages
    }
    for epoch, checkpoint in checkpoints.items():
        observed = sha256_file(checkpoint)
        expected = str(protocol["checkpoint_sha256"][str(epoch)]).lower()
        if observed != expected:
            raise RuntimeError(f"E{epoch}: checkpoint hash mismatch")
    if sha256_file(Path(PROJECT_ROOT / protocol["model_file"])) != str(protocol["model_file_sha256"]).lower():
        raise RuntimeError("Model file hash mismatch")

    appearance_sources, sem_sources = fixed_sources(protocol, r78)
    source_manifest = {
        "protocol_id": protocol["protocol_id"],
        "created_before_reconstruction": not RECON.exists(),
        "sealed_holdout_accessed": False,
        "appearance": appearance_sources,
        "sem": sem_sources,
    }
    write_json(RESULTS / "fixed_source_manifest.json", source_manifest)
    write_json(RESULTS / "run_state.json", {"status": "running", "started_at_unix": time.time(), "completed_stages": []})

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this multi-stage validation run")
    device = torch.device("cuda:0")
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    if free_bytes < 8 * 2**30:
        raise RuntimeError(f"Only {free_bytes / 2**30:.2f} GiB GPU memory is free; at least 8 GiB is required before starting")
    module = load_module("r90_early_stop_inference", INFERENCE)
    checkpoint_rows: list[dict[str, Any]] = []
    reconstruction_records: list[dict[str, Any]] = []
    completed_stages: list[int] = []
    run_started = time.perf_counter()

    for epoch in stages:
        stage_started = time.perf_counter()
        checkpoint = checkpoints[epoch]
        model, payload = module.load_model(checkpoint, device)
        checkpoint_rows.append({"epoch": epoch, "checkpoint_sha256": sha256_file(checkpoint), **checkpoint_metrics(payload)})
        jobs: list[tuple[str, str, Path, Path]] = []
        for item in appearance_sources:
            source = Path(item["source"])
            destination = RECON / "appearance" / f"E{epoch:03d}" / str(item["sequence"]) / str(item["filename"])
            jobs.append(("appearance", f"{item['sequence']}:{item['frame_index']}", source, destination))
        for item in sem_sources:
            source = Path(item["source"])
            destination = RECON / "sem" / "stage_root" / f"E{epoch:03d}" / "reconstruction" / f"{item['exposure']}.bmp"
            jobs.append(("sem", str(item["exposure"]), source, destination))
        for job_index, (arm, identity, source, destination) in enumerate(jobs, start=1):
            output_hash, seconds = reconstruct_one(module, model, source, destination, device)
            reconstruction_records.append({
                "epoch": epoch, "arm": arm, "identity": identity,
                "source": str(source), "source_sha256": sha256_file(source),
                "output": str(destination), "output_sha256": output_hash,
                "seconds": seconds,
            })
            print(json.dumps({"epoch": epoch, "completed": job_index, "total": len(jobs), "arm": arm, "identity": identity, "seconds": round(seconds, 3)}, ensure_ascii=False), flush=True)
        del model, payload
        torch.cuda.empty_cache()
        completed_stages.append(epoch)
        write_json(RESULTS / "run_state.json", {
            "status": "running", "completed_stages": completed_stages,
            "last_stage_seconds": time.perf_counter() - stage_started,
            "elapsed_seconds": time.perf_counter() - run_started,
        })

    TABLES.mkdir(parents=True, exist_ok=True)
    checkpoint_table = pd.DataFrame(checkpoint_rows)
    checkpoint_table.to_csv(TABLES / "stored_checkpoint_metrics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(reconstruction_records).to_csv(TABLES / "reconstruction_inventory.csv", index=False, encoding="utf-8-sig")

    appearance_rows: list[dict[str, Any]] = []
    for item in appearance_sources:
        raw = read_gray(Path(item["source"]))
        for epoch in stages:
            output = RECON / "appearance" / f"E{epoch:03d}" / str(item["sequence"]) / str(item["filename"])
            appearance_rows.append({
                "epoch": epoch,
                "sequence": item["sequence"],
                "magnification": item["magnification"],
                "nominal_step_um": item["nominal_step_um"],
                "frame_index": item["frame_index"],
                "filename": item["filename"],
                **appearance_metrics(raw, read_gray(output)),
            })
    appearance_table = pd.DataFrame(appearance_rows)
    appearance_table.to_csv(TABLES / "appearance_per_frame.csv", index=False, encoding="utf-8-sig")
    dimensions = {"epoch", "sequence", "magnification", "nominal_step_um", "frame_index", "filename"}
    metric_names = [column for column in appearance_table.columns if column not in dimensions]
    summaries: list[dict[str, Any]] = []
    for (epoch, sequence), group in appearance_table.groupby(["epoch", "sequence"], sort=True):
        row: dict[str, Any] = {
            "epoch": int(epoch), "sequence": sequence, "frames": int(len(group)),
            "magnification": int(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
        }
        for metric in metric_names:
            row[f"median_{metric}"] = float(group[metric].median())
            row[f"p95_{metric}"] = float(group[metric].quantile(0.95))
        summaries.append(row)
    pd.DataFrame(summaries).to_csv(TABLES / "appearance_by_sequence.csv", index=False, encoding="utf-8-sig")
    montage_paths = make_montages(appearance_sources, stages)
    free_after, _ = torch.cuda.mem_get_info(device)
    final_state = {
        "status": "reconstruction_complete",
        "protocol_id": protocol["protocol_id"],
        "sealed_holdout_accessed": False,
        "stages": stages,
        "appearance_frames_per_stage": len(appearance_sources),
        "sem_images_per_stage": len(sem_sources),
        "total_outputs": len(reconstruction_records),
        "elapsed_seconds": time.perf_counter() - run_started,
        "gpu": {
            "name": torch.cuda.get_device_name(device),
            "free_before_gib": free_bytes / 2**30,
            "total_gib": total_bytes / 2**30,
            "free_after_gib": free_after / 2**30,
            "tile_batch": 1,
        },
        "montages": montage_paths,
        "next_step": "Run the frozen MATLAB ACM contour extraction, then analyze all arms together.",
    }
    write_json(RESULTS / "run_state.json", final_state)
    print(json.dumps(final_state, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
