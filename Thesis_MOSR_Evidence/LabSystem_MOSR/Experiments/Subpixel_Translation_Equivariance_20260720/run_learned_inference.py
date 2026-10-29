from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import torch
from torch.cuda.amp import autocast


EXPERIMENT = Path(__file__).resolve().parent
INPUT_DIR = EXPERIMENT / "inputs" / "shifted"
INPUT_MANIFEST = EXPERIMENT / "inputs" / "input_manifest.csv"
RESULTS_DIR = EXPERIMENT / "results"
QA_DIR = EXPERIMENT / "qa"

LAB_ROOT = EXPERIMENT.parents[1]
BASE_EXPERIMENT = LAB_ROOT / "Experiments" / "BaseUNet_Baseline_20260718"
MODERN_EXPERIMENT = LAB_ROOT / "Experiments" / "Modern_Restoration_Benchmarks_20260719"
PACKAGE = LAB_ROOT / ".." / ".." / "Deliverables" / "Standalone_Models" / "V42_SoftLabelSNR_FullStandalone_20260709"

CHECKPOINTS = {
    "base_unet": BASE_EXPERIMENT
    / "results_full_data_fixed_psf_tiled_e30"
    / "best_base_unet.pth.tar",
    "edsr": MODERN_EXPERIMENT / "results" / "edsr" / "best_edsr.pth.tar",
    "nafnet": MODERN_EXPERIMENT / "results" / "nafnet" / "best_nafnet.pth.tar",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest() -> list[dict[str, str]]:
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 126:
        raise RuntimeError(f"Expected 126 locked inputs, found {len(rows)}")
    filenames = [row["filename"] for row in rows]
    if len(set(filenames)) != len(filenames):
        raise RuntimeError("Input manifest contains duplicate filenames")
    return rows


def read_u16(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    if image.dtype != np.uint16 or image.shape != (512, 512):
        raise RuntimeError(
            f"Expected a 512x512 uint16 image at {path}, got {image.shape} {image.dtype}"
        )
    return image


def write_u16(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if image.dtype != np.uint16:
        raise TypeError(f"Expected uint16 output, got {image.dtype}")
    ok = cv2.imwrite(str(path), image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    if not ok:
        raise RuntimeError(f"Could not write {path}")


def create_visual_previews(rows: list[dict[str, str]]) -> None:
    preview_dir = QA_DIR / "input_previews_8bit"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        if row["axis"] != "reference":
            continue
        source = read_u16(INPUT_DIR / row["filename"])
        preview = np.clip(np.rint(source.astype(np.float32) / 257.0), 0, 255).astype(
            np.uint8
        )
        output = preview_dir / row["filename"].replace(".png", "_preview.png")
        if not cv2.imwrite(str(output), preview):
            raise RuntimeError(f"Could not write preview {output}")


def import_loaders():
    # The original experiment modules use local absolute imports, so both source
    # directories must be placed on sys.path before importing them.
    for folder in (MODERN_EXPERIMENT, BASE_EXPERIMENT):
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))
    base_module = importlib.import_module("infer_base_unet")
    modern_module = importlib.import_module("infer_modern_baseline")
    return base_module.load_model, modern_module.load_model


@torch.inference_mode()
def infer_float_batch(
    model: torch.nn.Module,
    images: list[np.ndarray],
    device: torch.device,
) -> tuple[list[np.ndarray], float]:
    array = np.stack(images, axis=0).astype(np.float32) / 65535.0
    tensor = torch.from_numpy(array)[:, None].to(device, non_blocking=True)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    tick = time.perf_counter()
    with autocast(enabled=device.type == "cuda"):
        prediction = model(tensor)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    seconds = time.perf_counter() - tick
    output = prediction[:, 0].float().clamp_(0.0, 1.0).cpu().numpy()
    quantized = np.clip(np.rint(output * 65535.0), 0, 65535).astype(np.uint16)
    return [quantized[index] for index in range(quantized.shape[0])], seconds


def chunks(items: list[Path], size: int) -> Iterable[list[Path]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def load_method(
    method: str,
    device: torch.device,
    base_loader,
    modern_loader,
) -> tuple[torch.nn.Module, dict, Path]:
    checkpoint = CHECKPOINTS[method]
    if not checkpoint.exists():
        raise FileNotFoundError(checkpoint)
    if method == "base_unet":
        model, metadata = base_loader(checkpoint, device)
    else:
        model, metadata = modern_loader(checkpoint, PACKAGE, device)
    model.eval()
    return model, metadata, checkpoint


def deterministic_repeat_qa(
    model: torch.nn.Module,
    paths: list[Path],
    device: torch.device,
) -> dict[str, object]:
    sample_paths = paths[:2]
    images = [read_u16(path) for path in sample_paths]
    first, _ = infer_float_batch(model, images, device)
    second, _ = infer_float_batch(model, images, device)
    max_level_difference = max(
        int(np.max(np.abs(a.astype(np.int32) - b.astype(np.int32))))
        for a, b in zip(first, second)
    )
    return {
        "filenames": [path.name for path in sample_paths],
        "max_uint16_level_difference": max_level_difference,
        "passed": bool(max_level_difference <= 1),
    }


def run_method(
    method: str,
    paths: list[Path],
    device: torch.device,
    batch_size: int,
    base_loader,
    modern_loader,
) -> dict[str, object]:
    output_dir = RESULTS_DIR / method
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(output_dir.glob("*.png"))
    if existing:
        raise RuntimeError(
            f"Refusing to mix with {len(existing)} existing outputs in {output_dir}"
        )

    model, checkpoint_data, checkpoint = load_method(
        method, device, base_loader, modern_loader
    )

    # One fixed warm-up image is excluded from timing.
    warmup_image = read_u16(paths[0])
    infer_float_batch(model, [warmup_image], device)

    repeat_qa = deterministic_repeat_qa(model, paths, device)
    if not repeat_qa["passed"]:
        raise RuntimeError(f"Deterministic repeat QA failed for {method}: {repeat_qa}")

    records: list[dict[str, object]] = []
    total_inference_seconds = 0.0
    wall_tick = time.perf_counter()
    processed = 0
    for batch_paths in chunks(paths, batch_size):
        images = [read_u16(path) for path in batch_paths]
        outputs, inference_seconds = infer_float_batch(model, images, device)
        total_inference_seconds += inference_seconds
        per_image_seconds = inference_seconds / len(batch_paths)
        for source_path, output in zip(batch_paths, outputs):
            output_path = output_dir / source_path.name
            write_u16(output_path, output)
            records.append(
                {
                    "method": method,
                    "filename": source_path.name,
                    "output_path": str(output_path),
                    "inference_seconds_allocated": per_image_seconds,
                    "dtype": str(output.dtype),
                    "height": int(output.shape[0]),
                    "width": int(output.shape[1]),
                    "minimum": int(output.min()),
                    "maximum": int(output.max()),
                    "mean": float(output.mean()),
                    "clipped_low_fraction": float(np.mean(output == 0)),
                    "clipped_high_fraction": float(np.mean(output == 65535)),
                }
            )
            processed += 1
        print(f"[{method}] {processed}/{len(paths)}", flush=True)
    wall_seconds = time.perf_counter() - wall_tick

    if len(records) != len(paths):
        raise RuntimeError(f"{method} produced {len(records)} outputs, expected {len(paths)}")

    record_path = RESULTS_DIR / f"{method}_inference_records.csv"
    with record_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    summary = {
        "method": method,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "checkpoint_epoch": checkpoint_data.get("epoch"),
        "parameter_count": checkpoint_data.get("parameter_count"),
        "batch_size": batch_size,
        "input_count": len(paths),
        "output_directory": str(output_dir),
        "inference_seconds_total": total_inference_seconds,
        "inference_seconds_per_image": total_inference_seconds / len(paths),
        "wall_seconds": wall_seconds,
        "deterministic_repeat_qa": repeat_qa,
        "output_minimum": min(int(row["minimum"]) for row in records),
        "output_maximum": max(int(row["maximum"]) for row in records),
        "maximum_clipped_low_fraction": max(
            float(row["clipped_low_fraction"]) for row in records
        ),
        "maximum_clipped_high_fraction": max(
            float(row["clipped_high_fraction"]) for row in records
        ),
    }
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--methods",
        nargs="+",
        default=["base_unet", "edsr", "nafnet"],
        choices=sorted(CHECKPOINTS),
    )
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise ValueError("batch size must be positive")
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    torch.manual_seed(1261200)
    np.random.seed(1261200)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(1261200)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True, warn_only=True)

    rows = read_manifest()
    paths = [INPUT_DIR / row["filename"] for row in rows]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing {len(missing)} locked inputs; first={missing[0]}")
    create_visual_previews(rows)

    base_loader, modern_loader = import_loaders()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summaries = []
    for method in args.methods:
        summaries.append(
            run_method(
                method,
                paths,
                device,
                args.batch_size,
                base_loader,
                modern_loader,
            )
        )

    manifest = {
        "experiment": str(EXPERIMENT),
        "input_manifest": str(INPUT_MANIFEST),
        "input_count": len(paths),
        "input_dtype": "uint16",
        "input_normalization": "uint16 / 65535",
        "inference_support": "whole 512x512 crop; no tiling",
        "device": str(device),
        "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "opencv_version": cv2.__version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pid": os.getpid(),
        "methods": summaries,
    }
    output_path = RESULTS_DIR / "learned_inference_manifest.json"
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
