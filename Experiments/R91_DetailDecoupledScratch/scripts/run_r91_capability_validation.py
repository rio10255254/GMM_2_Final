"""Run the predeclared R91 real-image, SEM, motion, branch, and tile probes."""
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
PROTOCOL = ROOT / "config" / "capability_validation_20260811.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"
RESULTS = ROOT / "results" / "capability_diagnosis_20260811"
RECON = RESULTS / "reconstructions_fp32"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
PRIMARY_AMP = False


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
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


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", image)
    if not success:
        raise RuntimeError(path)
    encoded.tofile(path)


def image_paths(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("frame_*.bmp") if path.is_file())


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
        "mean_abs_change_flat_region_gray": float(np.mean(absolute[flat])) if np.any(flat) else 0.0,
    }


def fixed_sources(protocol: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    appearance_arm = protocol["arms"]["fixed_real_appearance"]
    source_config = read_json(Path(PROJECT_ROOT / appearance_arm["source_config"]))
    appearance: list[dict[str, Any]] = []
    for sequence in appearance_arm["sequences"]:
        item = source_config["sequences"][sequence]
        paths = image_paths(Path(item["raw_dir"]))
        if len(paths) != int(item["frame_count"]):
            raise RuntimeError(f"{sequence}: frame count mismatch")
        indices = [len(paths) - 1 if int(index) < 0 else int(index) for index in appearance_arm["fixed_frame_indices"]]
        if len(indices) != len(set(indices)) or min(indices) < 0 or max(indices) >= len(paths):
            raise RuntimeError(f"{sequence}: invalid frame indices")
        for index in indices:
            path = paths[index]
            appearance.append({
                "sequence": sequence,
                "magnification": int(item["magnification"]),
                "nominal_step_um": float(item["nominal_step_um"]),
                "frame_index": index,
                "filename": path.name,
                "source": str(path),
                "sha256": sha256_file(path),
            })
    if len(appearance) != int(appearance_arm["expected_frames_per_stage"]):
        raise RuntimeError("Fixed appearance population mismatch")

    live_root = Path(PROJECT_ROOT / protocol["arms"]["fixed_live_branch_probe"]["input_directory"])
    live = []
    for path in sorted(live_root.glob("*.bmp")):
        live.append({"filename": path.name, "source": str(path), "sha256": sha256_file(path)})
    if len(live) != int(protocol["arms"]["fixed_live_branch_probe"]["expected_images"]):
        raise RuntimeError("Live branch-probe population mismatch")

    sem_arm = protocol["arms"]["sem_contour"]
    sem_root = Path(PROJECT_ROOT / sem_arm["optical_inputs"])
    sem = []
    for exposure in sem_arm["exposures"]:
        path = sem_root / f"{int(exposure)}.bmp"
        if not path.is_file():
            raise FileNotFoundError(path)
        sem.append({"exposure": int(exposure), "source": str(path), "sha256": sha256_file(path)})

    motion_arm = protocol["arms"]["real_motion"]
    motion_root = Path(PROJECT_ROOT / motion_arm["ordered_source"])
    motion_paths = image_paths(motion_root)
    if len(motion_paths) != int(motion_arm["expected_frames_per_stage"]):
        raise RuntimeError("Motion population mismatch")
    motion = [
        {"frame_index": index, "filename": path.name, "source": str(path), "sha256": sha256_file(path)}
        for index, path in enumerate(motion_paths)
    ]
    return appearance, live, sem, motion


def reconstruct_one(module, model, source: Path, destination: Path, device: torch.device) -> tuple[str, float]:
    if destination.is_file():
        output = read_gray(destination)
        if output.shape == read_gray(source).shape:
            return sha256_file(destination), 0.0
    raw, dtype = module.read_gray(source)
    started = time.perf_counter()
    prediction = module.reconstruct_tensor(model, module.image_tensor(raw, device), core_size=512, halo=192, tile_batch=1, amp=PRIMARY_AMP)
    output = module.output_array(prediction, dtype)
    write_bmp(destination, output)
    return sha256_file(destination), time.perf_counter() - started


@torch.inference_mode()
def branch_probe(module, model, source: Path, epoch: int, device: torch.device) -> tuple[dict[str, Any], np.ndarray]:
    raw, dtype = module.read_gray(source)
    tensor = module.image_tensor(raw, device)
    canvas, (height, width, _grid_h, _grid_w) = module.canonical_canvas(tensor, 512, 192)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=PRIMARY_AMP):
        details = model(canvas, return_details=True)
    cropped = {name: value.float()[..., 192:192 + height, 192:192 + width] for name, value in details.items()}
    output = module.output_array(cropped["output"], dtype)
    raw_gradient = gradient_magnitude(raw)
    edge = raw_gradient >= float(np.percentile(raw_gradient, 85))
    edge_band = cv2.dilate(edge.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    flat = cv2.distanceTransform((~edge).astype(np.uint8), cv2.DIST_L2, 5) > 5.0
    record: dict[str, Any] = {"epoch": epoch, "filename": source.name, **appearance_metrics(raw, output)}
    for name in ("low_delta", "detail_delta", "detail_fine_delta", "detail_medium_delta", "edge_delta", "correction"):
        array = cropped[name][0, 0].cpu().numpy() * 255.0
        record[f"{name}_signed_mean_gray"] = float(array.mean())
        record[f"{name}_mean_abs_gray"] = float(np.abs(array).mean())
        record[f"{name}_p95_abs_gray"] = float(np.percentile(np.abs(array), 95))
        record[f"{name}_edge_band_mean_abs_gray"] = float(np.abs(array[edge_band]).mean())
        record[f"{name}_flat_mean_abs_gray"] = float(np.abs(array[flat]).mean()) if np.any(flat) else 0.0
    return record, output


@torch.inference_mode()
def tile_probe(module, model, source: Path, epoch: int, device: torch.device, core_sizes: list[int]) -> list[dict[str, Any]]:
    raw, _dtype = module.read_gray(source)
    height, width = raw.shape
    crop_h, crop_w = min(733, height), min(901, width)
    y = (height - crop_h) // 2
    x = (width - crop_w) // 2
    tensor = module.image_tensor(raw[y:y + crop_h, x:x + crop_w], device)
    rows = []
    for core in core_sizes:
        for precision, amp in (("bf16", True), ("fp32", False)):
            full = module.reconstruct_full_reference(model, tensor, core_size=core, halo=192, amp=amp)
            for tile_batch in (1, 2):
                tiled = module.reconstruct_tensor(model, tensor, core_size=core, halo=192, tile_batch=tile_batch, amp=amp)
                difference = (full - tiled).abs()
                rows.append({
                    "epoch": epoch,
                    "source": str(source),
                    "crop_shape": f"{crop_h}x{crop_w}",
                    "core_size": core,
                    "precision": precision,
                    "tile_batch": tile_batch,
                    "mean_abs_gray": float(difference.mean() * 255.0),
                    "p99_abs_gray": float(torch.quantile(difference, 0.99) * 255.0),
                    "max_abs_gray": float(difference.max() * 255.0),
                    "nonidentity_mean_change_gray": float((tiled - tensor).abs().mean() * 255.0),
                })
    return rows


def panel(image: np.ndarray, label: str, width: int = 420, height: int = 420) -> np.ndarray:
    shown = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    shown = cv2.cvtColor(shown, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(shown, (0, 0), (width, 36), (0, 0, 0), -1)
    cv2.putText(shown, label, (9, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2, cv2.LINE_AA)
    return shown


def save_live_montage(filename: str, raw: np.ndarray, outputs: dict[int, np.ndarray]) -> Path:
    images = [("Raw", raw)] + [(f"R91 E{epoch}", outputs[epoch]) for epoch in sorted(outputs)]
    rows = [np.hstack([panel(image, label) for label, image in images[index:index + 3]]) for index in range(0, len(images), 3)]
    canvas = np.vstack(rows)
    path = FIGURES / f"live_probe_{Path(filename).stem}_fp32.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".png", canvas)
    if not success:
        raise RuntimeError(path)
    encoded.tofile(path)
    return path


def summarize_appearance(table: pd.DataFrame) -> pd.DataFrame:
    dimensions = {"epoch", "sequence", "magnification", "nominal_step_um", "frame_index", "filename"}
    metrics = [name for name in table.columns if name not in dimensions]
    rows: list[dict[str, Any]] = []
    for (epoch, sequence), group in table.groupby(["epoch", "sequence"], sort=True):
        row: dict[str, Any] = {
            "epoch": int(epoch),
            "sequence": str(sequence),
            "magnification": int(group["magnification"].iloc[0]),
            "nominal_step_um": float(group["nominal_step_um"].iloc[0]),
            "frames": int(len(group)),
        }
        for metric in metrics:
            row[f"median_{metric}"] = float(group[metric].median())
            row[f"p95_{metric}"] = float(group[metric].quantile(0.95))
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    protocol = read_json(PROTOCOL)
    appearance_stages = [int(value) for value in protocol["representative_stages"]["appearance_and_branch"]]
    sem_stages = {int(value) for value in protocol["representative_stages"]["sem_contour"]}
    motion_stages = {int(value) for value in protocol["representative_stages"]["real_motion"]}
    all_stages = appearance_stages
    checkpoint_root = Path(PROJECT_ROOT / protocol["checkpoint_root"])
    checkpoints = {epoch: checkpoint_root / f"epoch_{epoch:03d}.pth.tar" for epoch in all_stages}
    for epoch, checkpoint in checkpoints.items():
        if sha256_file(checkpoint) != str(protocol["checkpoint_sha256"][str(epoch)]).lower():
            raise RuntimeError(f"E{epoch}: checkpoint hash mismatch")
    if sha256_file(Path(PROJECT_ROOT / protocol["model_file"])) != str(protocol["model_file_sha256"]).lower():
        raise RuntimeError("R91 model hash mismatch")

    appearance, live, sem, motion = fixed_sources(protocol)
    source_manifest = {
        "protocol_id": protocol["protocol_id"],
        "created_before_reconstruction_outputs": not RECON.exists(),
        "sealed_holdout_accessed": False,
        "appearance": appearance,
        "live_branch_probe": live,
        "sem": sem,
        "motion": motion,
    }
    write_json(RESULTS / "fixed_source_manifest_fp32.json", source_manifest)
    write_json(RESULTS / "real_validation_state_fp32.json", {"status": "running", "completed_stages": []})

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    free_before, total_memory = torch.cuda.mem_get_info(device)
    if free_before < 8 * 2**30:
        raise RuntimeError(f"Only {free_before / 2**30:.2f} GiB is free")
    module = load_module("r91_capability_inference", INFERENCE)
    records: list[dict[str, Any]] = []
    appearance_rows: list[dict[str, Any]] = []
    branch_rows: list[dict[str, Any]] = []
    tile_rows: list[dict[str, Any]] = []
    live_outputs: dict[str, dict[int, np.ndarray]] = {item["filename"]: {} for item in live}
    completed: list[int] = []
    started = time.perf_counter()

    for epoch in all_stages:
        checkpoint = checkpoints[epoch]
        model, payload = module.load_model(checkpoint, device)
        stage_records: list[dict[str, Any]] = []
        jobs: list[tuple[str, str, Path, Path]] = []
        for item in appearance:
            source = Path(item["source"])
            destination = RECON / "appearance" / f"E{epoch:03d}" / str(item["sequence"]) / str(item["filename"])
            jobs.append(("appearance", f"{item['sequence']}:{item['frame_index']}", source, destination))
        for item in live:
            source = Path(item["source"])
            destination = RECON / "live_probe" / f"E{epoch:03d}" / str(item["filename"])
            jobs.append(("live_probe", str(item["filename"]), source, destination))
        if epoch in sem_stages:
            for item in sem:
                source = Path(item["source"])
                destination = RECON / "sem" / "stage_root" / f"E{epoch:03d}" / "reconstruction" / f"{item['exposure']}.bmp"
                jobs.append(("sem", str(item["exposure"]), source, destination))
        if epoch in motion_stages:
            for item in motion:
                source = Path(item["source"])
                destination = RECON / "motion" / f"E{epoch:03d}" / str(item["filename"])
                jobs.append(("motion", str(item["frame_index"]), source, destination))

        stage_started = time.perf_counter()
        for index, (arm, identity, source, destination) in enumerate(jobs, start=1):
            output_hash, seconds = reconstruct_one(module, model, source, destination, device)
            record = {
                "epoch": epoch,
                "arm": arm,
                "identity": identity,
                "source": str(source),
                "source_sha256": sha256_file(source),
                "output": str(destination),
                "output_sha256": output_hash,
                "seconds": seconds,
            }
            records.append(record)
            stage_records.append(record)
            if index % 10 == 0 or index == len(jobs):
                print(json.dumps({"epoch": epoch, "completed": index, "total": len(jobs), "arm": arm, "elapsed_seconds": round(time.perf_counter() - started, 1)}, ensure_ascii=False), flush=True)

        for item in appearance:
            raw = read_gray(Path(item["source"]))
            output = read_gray(RECON / "appearance" / f"E{epoch:03d}" / str(item["sequence"]) / str(item["filename"]))
            appearance_rows.append({
                "epoch": epoch,
                "sequence": item["sequence"],
                "magnification": item["magnification"],
                "nominal_step_um": item["nominal_step_um"],
                "frame_index": item["frame_index"],
                "filename": item["filename"],
                **appearance_metrics(raw, output),
            })
        for item in live:
            probe, output = branch_probe(module, model, Path(item["source"]), epoch, device)
            branch_rows.append(probe)
            live_outputs[item["filename"]][epoch] = output
        tile_rows.extend(tile_probe(module, model, Path(appearance[0]["source"]), epoch, device, [int(value) for value in protocol["arms"]["tiled_reconstruction"]["core_sizes"]]))

        write_json(RECON / f"E{epoch:03d}_manifest.json", {
            "protocol_id": protocol["protocol_id"],
            "experiment_id": "R91_DetailDecoupledScratch",
            "epoch": epoch,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256_file(checkpoint),
            "weight_source": "ema_state_dict",
            "records": stage_records,
        })
        del model, payload
        torch.cuda.empty_cache()
        completed.append(epoch)
        write_json(RESULTS / "real_validation_state_fp32.json", {
            "status": "running",
            "completed_stages": completed,
            "last_stage_seconds": time.perf_counter() - stage_started,
            "elapsed_seconds": time.perf_counter() - started,
        })

    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(TABLES / "reconstruction_inventory_fp32.csv", index=False, encoding="utf-8-sig")
    appearance_table = pd.DataFrame(appearance_rows)
    appearance_table.to_csv(TABLES / "real_appearance_per_frame_fp32.csv", index=False, encoding="utf-8-sig")
    summarize_appearance(appearance_table).to_csv(TABLES / "real_appearance_by_sequence_fp32.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(branch_rows).to_csv(TABLES / "live_branch_probe_fp32.csv", index=False, encoding="utf-8-sig")
    tile_table = pd.DataFrame(tile_rows)
    tile_table.to_csv(TABLES / "real_tile_parity_precision_audit.csv", index=False, encoding="utf-8-sig")
    montages = []
    for item in live:
        raw = read_gray(Path(item["source"]))
        montages.append(str(save_live_montage(item["filename"], raw, live_outputs[item["filename"]])))

    inventory = pd.DataFrame(records)
    expected_outputs = 5 * (30 + 4) + 4 * 12 + 4 * 50
    if len(inventory) != expected_outputs:
        raise RuntimeError(f"Output count mismatch: {len(inventory)} != {expected_outputs}")
    canonical_tile = tile_table.loc[(tile_table["precision"] == "bf16") & (tile_table["tile_batch"] == 1)]
    fp32_tile = tile_table.loc[tile_table["precision"] == "fp32"]
    accelerated_bf16 = tile_table.loc[(tile_table["precision"] == "bf16") & (tile_table["tile_batch"] == 2)]
    if float(canonical_tile["mean_abs_gray"].max()) > 0.001 or float(canonical_tile["p99_abs_gray"].max()) > 0.01:
        raise RuntimeError(
            "Canonical tile parity has a spatially meaningful regression: "
            f"mean={canonical_tile['mean_abs_gray'].max()}, p99={canonical_tile['p99_abs_gray'].max()}"
        )
    if float(fp32_tile["mean_abs_gray"].max()) > 0.001 or float(fp32_tile["p99_abs_gray"].max()) > 0.01:
        raise RuntimeError(
            "FP32 tile parity has a spatially meaningful regression: "
            f"mean={fp32_tile['mean_abs_gray'].max()}, p99={fp32_tile['p99_abs_gray'].max()}"
        )
    free_after, _ = torch.cuda.mem_get_info(device)
    state = {
        "status": "reconstruction_complete",
        "protocol_id": protocol["protocol_id"],
        "primary_precision": "fp32",
        "primary_tile_batch": 1,
        "sealed_holdout_accessed": False,
        "completed_stages": completed,
        "outputs": int(len(inventory)),
        "appearance_rows": int(len(appearance_table)),
        "branch_rows": int(len(branch_rows)),
        "tile_rows": int(len(tile_table)),
        "canonical_bf16_tile_max_abs_gray": float(canonical_tile["max_abs_gray"].max()),
        "canonical_bf16_tile_mean_abs_gray_max": float(canonical_tile["mean_abs_gray"].max()),
        "canonical_bf16_tile_p99_abs_gray_max": float(canonical_tile["p99_abs_gray"].max()),
        "fp32_tile_max_abs_gray": float(fp32_tile["max_abs_gray"].max()),
        "fp32_tile_mean_abs_gray_max": float(fp32_tile["mean_abs_gray"].max()),
        "fp32_tile_p99_abs_gray_max": float(fp32_tile["p99_abs_gray"].max()),
        "accelerated_bf16_batch2_tile_max_abs_gray": float(accelerated_bf16["max_abs_gray"].max()),
        "accelerated_bf16_batch2_is_numerically_batch_dependent": bool(float(accelerated_bf16["max_abs_gray"].max()) > 0.03),
        "elapsed_seconds": time.perf_counter() - started,
        "gpu": {
            "name": torch.cuda.get_device_name(device),
            "free_before_gib": free_before / 2**30,
            "total_gib": total_memory / 2**30,
            "free_after_gib": free_after / 2**30,
        },
        "montages": montages,
        "next_step": "Run the fixed MATLAB ACM rule, then the locked motion and combined analyses.",
    }
    write_json(RESULTS / "real_validation_state_fp32.json", state)
    print(json.dumps(state, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
