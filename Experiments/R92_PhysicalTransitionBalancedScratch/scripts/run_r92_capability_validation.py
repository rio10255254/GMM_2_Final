"""Run the locked R92 E80 real-image, SEM, motion, branch, and tile probes."""
from __future__ import annotations

import copy
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
import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"
R91_HELPER = Path(r"D:\GMM_2_Final\Experiments\R91_DetailDecoupledScratch\scripts\run_r91_capability_validation.py")
EPOCH = 80


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def extra_appearance_metrics(raw: np.ndarray, reconstructed: np.ndarray) -> dict[str, float]:
    """Separate edge/detail retention from flat-field noise suppression."""
    raw_f = raw.astype(np.float32)
    recon_f = reconstructed.astype(np.float32)
    raw_gradient = cv2.magnitude(
        cv2.Sobel(cv2.GaussianBlur(raw_f, (0, 0), 1.0), cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(cv2.GaussianBlur(raw_f, (0, 0), 1.0), cv2.CV_32F, 0, 1, ksize=3),
    )
    support = raw_gradient >= float(np.percentile(raw_gradient, 85))
    edge_band = cv2.dilate(support.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    distance = cv2.distanceTransform((~support).astype(np.uint8), cv2.DIST_L2, 5)
    flat = distance > 7.0
    raw_high = raw_f - cv2.GaussianBlur(raw_f, (0, 0), 1.6)
    recon_high = recon_f - cv2.GaussianBlur(recon_f, (0, 0), 1.6)

    def rms(array: np.ndarray, mask: np.ndarray) -> float:
        values = array[mask]
        return float(np.sqrt(np.mean(values * values))) if values.size else 0.0

    raw_edge, recon_edge = rms(raw_high, edge_band), rms(recon_high, edge_band)
    raw_flat, recon_flat = rms(raw_high, flat), rms(recon_high, flat)
    raw_lap = cv2.Laplacian(cv2.GaussianBlur(raw_f, (0, 0), 0.7), cv2.CV_32F, ksize=3)
    recon_lap = cv2.Laplacian(cv2.GaussianBlur(recon_f, (0, 0), 0.7), cv2.CV_32F, ksize=3)
    return {
        "edge_band_high_frequency_ratio": recon_edge / max(raw_edge, 1e-9),
        "flat_region_high_frequency_ratio": recon_flat / max(raw_flat, 1e-9),
        "laplacian_energy_ratio": float(np.std(recon_lap) / max(float(np.std(raw_lap)), 1e-9)),
        "edge_to_flat_detail_ratio_change": (recon_edge / max(recon_flat, 1e-9)) / max(raw_edge / max(raw_flat, 1e-9), 1e-9),
    }


def panel(image: np.ndarray, label: str, interpolation: int = cv2.INTER_AREA) -> np.ndarray:
    shown = cv2.resize(image, (420, 420), interpolation=interpolation)
    if shown.ndim == 2:
        shown = cv2.cvtColor(shown, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(shown, (0, 0), (420, 38), (0, 0, 0), -1)
    cv2.putText(shown, label, (9, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.66, (255, 255, 255), 2, cv2.LINE_AA)
    return shown


def save_pair_montage(path: Path, raw: np.ndarray, reconstructed: np.ndarray, label: str) -> None:
    height, width = raw.shape
    crop_height, crop_width = max(64, height // 2), max(64, width // 2)
    y0, x0 = (height - crop_height) // 2, (width - crop_width) // 2
    raw_crop = raw[y0:y0 + crop_height, x0:x0 + crop_width]
    recon_crop = reconstructed[y0:y0 + crop_height, x0:x0 + crop_width]
    difference = np.clip(np.abs(reconstructed.astype(np.float32) - raw.astype(np.float32)) * 8.0, 0, 255).astype(np.uint8)
    difference_crop = difference[y0:y0 + crop_height, x0:x0 + crop_width]
    top = np.hstack([
        panel(raw, f"Raw full - {label}"),
        panel(reconstructed, "R92 E80 full"),
        panel(difference, "Absolute change x8"),
    ])
    bottom = np.hstack([
        panel(raw_crop, "Raw centre crop", cv2.INTER_NEAREST),
        panel(recon_crop, "R92 E80 centre crop", cv2.INTER_NEAREST),
        panel(difference_crop, "Crop change x8", cv2.INTER_NEAREST),
    ])
    canvas = np.vstack([top, bottom])
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", canvas)
    if not success:
        raise RuntimeError(path)
    encoded.tofile(path)


def summarize_by_magnification(table: pd.DataFrame) -> pd.DataFrame:
    dimensions = {"epoch", "sequence", "magnification", "nominal_step_um", "frame_index", "filename"}
    metrics = [column for column in table.columns if column not in dimensions]
    rows: list[dict[str, Any]] = []
    for magnification, group in table.groupby("magnification", sort=True):
        row: dict[str, Any] = {"epoch": EPOCH, "magnification": int(magnification), "frames": int(len(group))}
        for metric in metrics:
            row[f"median_{metric}"] = float(group[metric].median())
            row[f"p05_{metric}"] = float(group[metric].quantile(0.05))
            row[f"p95_{metric}"] = float(group[metric].quantile(0.95))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    results = Path(protocol["output_root"])
    recon_root = results / "reconstructions_fp32"
    tables = results / "tables"
    figures = results / "figures"
    checkpoint = Path(protocol["checkpoint_root"]) / f"epoch_{EPOCH:03d}.pth.tar"
    helper = load_module("r92_r91_validation_helpers", R91_HELPER)
    inference = load_module("r92_capability_inference", INFERENCE)
    helper.PRIMARY_AMP = False

    required_hashes = {
        checkpoint: protocol["checkpoint_sha256"],
        Path(protocol["model_file"]): protocol["model_file_sha256"],
        Path(protocol["inference_file"]): protocol["inference_file_sha256"],
        Path(protocol["training_summary"]): protocol["training_summary_sha256"],
    }
    for path, expected in required_hashes.items():
        if not path.is_file() or helper.sha256_file(path) != str(expected).lower():
            raise RuntimeError(f"Locked artifact hash mismatch: {path}")

    compat = copy.deepcopy(protocol)
    compat["arms"]["fixed_real_appearance"]["expected_frames_per_stage"] = int(protocol["arms"]["fixed_real_appearance"]["expected_frames"])
    compat["arms"]["real_motion"]["expected_frames_per_stage"] = int(protocol["arms"]["real_motion"]["expected_frames"])
    appearance, live, sem, motion = helper.fixed_sources(compat)
    if (len(appearance), len(live), len(sem), len(motion)) != (30, 4, 12, 50):
        raise RuntimeError("Locked source population mismatch")

    source_manifest = {
        "protocol_id": protocol["protocol_id"],
        "checkpoint_selected_before_external_outputs": bool(protocol["locked_before_external_outputs"]),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": helper.sha256_file(checkpoint),
        "created_before_reconstruction_outputs": not recon_root.exists(),
        "sealed_holdout_accessed": False,
        "appearance": appearance,
        "live_branch_probe": live,
        "sem": sem,
        "motion": motion,
    }
    write_json(results / "fixed_source_manifest_fp32.json", source_manifest)
    write_json(results / "real_validation_state_fp32.json", {"status": "running", "epoch": EPOCH})

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    free_before, total_memory = torch.cuda.mem_get_info(device)
    if free_before < 7 * 2**30:
        raise RuntimeError(f"Only {free_before / 2**30:.2f} GiB GPU memory is free")
    model, payload = inference.load_model(checkpoint, device)
    if int(payload.get("epoch", -1)) != EPOCH:
        raise RuntimeError("Checkpoint epoch mismatch")

    jobs: list[tuple[str, str, Path, Path]] = []
    for item in appearance:
        jobs.append(("appearance", f"{item['sequence']}:{item['frame_index']}", Path(item["source"]), recon_root / "appearance" / "E080" / str(item["sequence"]) / str(item["filename"])))
    for item in live:
        jobs.append(("live_probe", str(item["filename"]), Path(item["source"]), recon_root / "live_probe" / "E080" / str(item["filename"])))
    for item in sem:
        jobs.append(("sem", str(item["exposure"]), Path(item["source"]), recon_root / "sem" / "stage_root" / "E080" / "reconstruction" / f"{item['exposure']}.bmp"))
    for item in motion:
        jobs.append(("motion", str(item["frame_index"]), Path(item["source"]), recon_root / "motion" / "E080" / str(item["filename"])))

    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    for index, (arm, identity, source, destination) in enumerate(jobs, start=1):
        output_hash, seconds = helper.reconstruct_one(inference, model, source, destination, device)
        records.append({
            "epoch": EPOCH,
            "arm": arm,
            "identity": identity,
            "source": str(source),
            "source_sha256": helper.sha256_file(source),
            "output": str(destination),
            "output_sha256": output_hash,
            "seconds": seconds,
        })
        if index % 8 == 0 or index == len(jobs):
            print(json.dumps({"completed": index, "total": len(jobs), "arm": arm, "elapsed_seconds": round(time.perf_counter() - started, 1)}), flush=True)

    if len(records) != 96:
        raise RuntimeError(f"Output count mismatch: {len(records)}")
    write_json(recon_root / "E080_manifest.json", {
        "protocol_id": protocol["protocol_id"],
        "experiment_id": "R92_PhysicalTransitionBalancedScratch",
        "epoch": EPOCH,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": helper.sha256_file(checkpoint),
        "weight_source": "ema_state_dict",
        "precision": "fp32",
        "records": records,
    })

    appearance_rows: list[dict[str, Any]] = []
    for item in appearance:
        raw = helper.read_gray(Path(item["source"]))
        output = helper.read_gray(recon_root / "appearance" / "E080" / str(item["sequence"]) / str(item["filename"]))
        appearance_rows.append({
            "epoch": EPOCH,
            "sequence": item["sequence"],
            "magnification": item["magnification"],
            "nominal_step_um": item["nominal_step_um"],
            "frame_index": item["frame_index"],
            "filename": item["filename"],
            **helper.appearance_metrics(raw, output),
            **extra_appearance_metrics(raw, output),
        })

    branch_rows: list[dict[str, Any]] = []
    for item in live:
        record, _output = helper.branch_probe(inference, model, Path(item["source"]), EPOCH, device)
        branch_rows.append(record)

    tile_rows = helper.tile_probe(
        inference,
        model,
        Path(appearance[0]["source"]),
        EPOCH,
        device,
        [int(value) for value in protocol["arms"]["tiled_reconstruction"]["core_sizes"]],
    )

    tables.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(tables / "reconstruction_inventory_fp32.csv", index=False, encoding="utf-8-sig")
    appearance_table = pd.DataFrame(appearance_rows)
    appearance_table.to_csv(tables / "real_appearance_per_frame_fp32.csv", index=False, encoding="utf-8-sig")
    helper.summarize_appearance(appearance_table).to_csv(tables / "real_appearance_by_sequence_fp32.csv", index=False, encoding="utf-8-sig")
    summarize_by_magnification(appearance_table).to_csv(tables / "real_appearance_by_magnification_fp32.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(branch_rows).to_csv(tables / "live_branch_probe_fp32.csv", index=False, encoding="utf-8-sig")
    tile_table = pd.DataFrame(tile_rows)
    tile_table.to_csv(tables / "real_tile_parity_precision_audit.csv", index=False, encoding="utf-8-sig")

    montages: list[str] = []
    for sequence in protocol["arms"]["fixed_real_appearance"]["sequences"]:
        item = next(row for row in appearance if row["sequence"] == sequence and int(row["frame_index"]) == 24)
        raw = helper.read_gray(Path(item["source"]))
        output = helper.read_gray(recon_root / "appearance" / "E080" / sequence / str(item["filename"]))
        montage = figures / f"appearance_{sequence}_frame24_raw_vs_r92_e80.png"
        save_pair_montage(montage, raw, output, sequence)
        montages.append(str(montage))
    for item in live:
        raw = helper.read_gray(Path(item["source"]))
        output = helper.read_gray(recon_root / "live_probe" / "E080" / str(item["filename"]))
        montage = figures / f"live_{Path(item['filename']).stem}_raw_vs_r92_e80.png"
        save_pair_montage(montage, raw, output, str(item["filename"]))
        montages.append(str(montage))

    fp32_tile = tile_table.loc[tile_table["precision"] == "fp32"]
    bf16_tile = tile_table.loc[tile_table["precision"] == "bf16"]
    if float(fp32_tile["mean_abs_gray"].max()) > 0.001 or float(fp32_tile["p99_abs_gray"].max()) > 0.01:
        raise RuntimeError("FP32 tile parity regression")
    free_after, _ = torch.cuda.mem_get_info(device)
    state = {
        "status": "reconstruction_complete",
        "protocol_id": protocol["protocol_id"],
        "epoch": EPOCH,
        "outputs": len(records),
        "appearance_rows": len(appearance_rows),
        "branch_rows": len(branch_rows),
        "tile_rows": len(tile_rows),
        "fp32_tile_mean_abs_gray_max": float(fp32_tile["mean_abs_gray"].max()),
        "fp32_tile_p99_abs_gray_max": float(fp32_tile["p99_abs_gray"].max()),
        "fp32_tile_max_abs_gray": float(fp32_tile["max_abs_gray"].max()),
        "bf16_tile_mean_abs_gray_max": float(bf16_tile["mean_abs_gray"].max()),
        "bf16_tile_max_abs_gray": float(bf16_tile["max_abs_gray"].max()),
        "elapsed_seconds": time.perf_counter() - started,
        "gpu": {
            "name": torch.cuda.get_device_name(device),
            "free_before_gib": free_before / 2**30,
            "total_gib": total_memory / 2**30,
            "free_after_gib": free_after / 2**30,
        },
        "montages": montages,
        "sealed_holdout_accessed": False,
        "next_step": "Run sealed holdout, fixed SEM ACM, locked real motion, and hard-microscopy ACM.",
    }
    write_json(results / "real_validation_state_fp32.json", state)
    print(json.dumps(state, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
