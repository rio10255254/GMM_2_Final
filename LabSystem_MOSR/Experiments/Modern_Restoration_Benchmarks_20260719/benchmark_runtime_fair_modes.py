from __future__ import annotations

import argparse
import csv
import gc
import json
from pathlib import Path

import numpy as np
import torch

from benchmark_models import (
    FULL_FRAME,
    direct_full_frame,
    load_named_model,
    patch_benchmark,
    read_gray_u8,
    reconstruct_tiled,
    summarize_times,
    synchronize,
)


EXPERIMENT = Path(__file__).resolve().parent
METHODS = ("Base U-Net", "NAFNet", "EDSR", "MOSR")


def timed_direct(
    model: torch.nn.Module,
    image: np.ndarray,
    device: torch.device,
    iterations: int,
) -> tuple[dict[str, float], float]:
    for _ in range(2):
        direct_full_frame(model, image, device)
    synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    times: list[float] = []
    for _ in range(iterations):
        result, seconds = direct_full_frame(model, image, device)
        if result.shape != image.shape:
            raise RuntimeError("Direct output shape mismatch")
        times.append(seconds)
    peak_mb = float(torch.cuda.max_memory_allocated(device) / 2**20)
    return summarize_times(times), peak_mb


def timed_tiled(
    model: torch.nn.Module,
    image: np.ndarray,
    device: torch.device,
    iterations: int,
) -> tuple[dict[str, float], float]:
    reconstruct_tiled(model, image, device, 256, 128, 32)
    synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    times: list[float] = []
    for _ in range(iterations):
        result, seconds = reconstruct_tiled(model, image, device, 256, 128, 32)
        if result.shape != image.shape:
            raise RuntimeError("Tiled output shape mismatch")
        times.append(seconds)
    peak_mb = float(torch.cuda.max_memory_allocated(device) / 2**20)
    return summarize_times(times), peak_mb


def main(
    output_root: Path,
    patch_iterations: int,
    direct_iterations: int,
    tiled_iterations: int,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("CUDA is required")
    image = read_gray_u8(FULL_FRAME)
    crop = image[640:896, 896:1152]
    patch = torch.from_numpy(crop.astype(np.float32) / 255.0)[None, None].to(device)
    rows: list[dict[str, object]] = []
    for method in METHODS:
        model, _ = load_named_model(method, device)
        patch_times, patch_peak_mb = patch_benchmark(
            model, patch, device, patch_iterations
        )
        patch_stats = summarize_times(patch_times)
        direct_stats, direct_peak_mb = timed_direct(
            model, image, device, direct_iterations
        )
        tiled_stats, tiled_peak_mb = timed_tiled(
            model, image, device, tiled_iterations
        )
        megapixels = image.size / 1.0e6
        row = {
            "method": method,
            "parameter_count": sum(p.numel() for p in model.parameters()),
            "patch_median_ms": patch_stats["median_ms"],
            "patch_p95_ms": patch_stats["p95_ms"],
            "patch_peak_gpu_memory_mb": patch_peak_mb,
            "direct_median_ms": direct_stats["median_ms"],
            "direct_p95_ms": direct_stats["p95_ms"],
            "direct_peak_gpu_memory_mb": direct_peak_mb,
            "direct_megapixels_per_second": megapixels
            / (direct_stats["median_ms"] / 1000.0),
            "tiled_median_ms": tiled_stats["median_ms"],
            "tiled_p95_ms": tiled_stats["p95_ms"],
            "tiled_peak_gpu_memory_mb": tiled_peak_mb,
            "tiled_megapixels_per_second": megapixels
            / (tiled_stats["median_ms"] / 1000.0),
        }
        rows.append(row)
        print(json.dumps(row, indent=2), flush=True)
        del model
        gc.collect()
        torch.cuda.empty_cache()

    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "fair_runtime_modes.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "purpose": "Separate model compute from deployed inference-path overhead",
        "input": str(FULL_FRAME),
        "shape": list(image.shape),
        "gpu": torch.cuda.get_device_name(device),
        "precision": "CUDA automatic mixed precision",
        "patch": "All models use the same 256x256 batch-one patch",
        "direct": "All models use one direct 2048x1536 forward",
        "tiled": "All models use 256-pixel tiles, 128-pixel overlap, batch 32",
        "note": "Direct and tiled modes are diagnostic compute comparisons; they do not replace each model's formal deployed output path.",
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "runtime_fair_modes",
    )
    parser.add_argument("--patch-iterations", type=int, default=30)
    parser.add_argument("--direct-iterations", type=int, default=6)
    parser.add_argument("--tiled-iterations", type=int, default=4)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        args.output_root.resolve(),
        args.patch_iterations,
        args.direct_iterations,
        args.tiled_iterations,
    )
