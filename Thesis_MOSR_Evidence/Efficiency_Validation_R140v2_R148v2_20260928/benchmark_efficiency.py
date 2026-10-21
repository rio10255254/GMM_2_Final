from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import statistics
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch


R140 = Path(r"D:\GMM_2_Final\Experiments\R140v2_StableUNet")
R148 = Path(r"D:\GMM_2_Final\Experiments\R148v2_HybridContextNativePSF")
CHECKPOINTS = {
    "r140": R140 / "runs/formal_8192/checkpoints/step08192.pth",
    "r148": R148 / "runs/formal_8192/checkpoints/step08192.pth",
}
EXPECTED_SHA = {
    "r140": "b96980287f02329b36f2188886462e51cadabad2259c8a13018f68e3b3f2650c",
    "r148": "8daddf823166b373d3c3b437ebb9869e3d2260ed83d72613140669d92ee0db22",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_model(kind: str, device: torch.device):
    root = R140 if kind == "r140" else R148
    sys.path.insert(0, str(root))
    model_module = load_module(f"{kind}_model", root / "model.py")
    cfg = json.loads((root / "config/model.json").read_text(encoding="utf-8"))
    checkpoint_path = CHECKPOINTS[kind]
    actual = sha256(checkpoint_path)
    if actual != EXPECTED_SHA[kind]:
        raise RuntimeError(f"Checkpoint SHA mismatch for {kind}: {actual}")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = model_module.Model(cfg, root).to(device).eval()
    model.load_state_dict(checkpoint["model"], strict=True)
    return model, cfg, actual


def load_image(path: Path, device: torch.device):
    raw = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if raw is None or raw.ndim != 2:
        raise RuntimeError(f"Cannot load monochrome image: {path}")
    scale = 255.0 if raw.dtype == np.uint8 else 65535.0
    x = torch.from_numpy(raw.astype(np.float32)[None, None] / scale).to(device)
    return raw, x


def r140_tiled(model, x: torch.Tensor, core: int, halo: int) -> torch.Tensor:
    if core % 8 or halo % 8:
        raise ValueError("R140 core and halo must be multiples of 8 for phase alignment")
    _, _, height, width = x.shape
    out = torch.empty_like(x)
    for y0 in range(0, height, core):
        for x0 in range(0, width, core):
            y1, x1 = min(height, y0 + core), min(width, x0 + core)
            top, bottom = max(0, y0 - halo), min(height, y1 + halo)
            left, right = max(0, x0 - halo), min(width, x1 + halo)
            tile = x[..., top:bottom, left:right]
            if min(tile.shape[-2:]) < 202:
                raise ValueError(f"R140 tile too small at {(y0, x0)}: {tuple(tile.shape[-2:])}")
            value = model(tile)
            out[..., y0:y1, x0:x1] = value[..., y0-top:y1-top, x0-left:x1-left]
    return out


def run_forward(kind: str, model, x: torch.Tensor, mode: str, core: int, halo: int):
    if mode == "full":
        return model(x)
    if kind == "r140":
        return r140_tiled(model, x, core, halo)
    model.cfg["inference_core"] = int(core)
    model.cfg["inference_halo"] = int(halo)
    return model.forward_tiled(x)


def percentile(values, q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def compare(reference: np.ndarray, output: np.ndarray, core: int | None):
    difference = np.abs(output.astype(np.float64) - reference.astype(np.float64))
    record = {
        "mae_float": float(difference.mean()),
        "rmse_float": float(np.sqrt(np.square(difference).mean())),
        "p99_float": percentile(difference, 99),
        "max_float": float(difference.max()),
        "mae_gray_levels": float(difference.mean() * 255.0),
        "p99_gray_levels": float(percentile(difference, 99) * 255.0),
        "max_gray_levels": float(difference.max() * 255.0),
        "changed_after_u8_fraction": float(np.mean(np.rint(output * 255.0) != np.rint(reference * 255.0))),
    }
    if core:
        height, width = output.shape
        seam = np.zeros((height, width), dtype=bool)
        band = 4
        for y in range(core, height, core):
            seam[max(0, y-band):min(height, y+band+1), :] = True
        for x in range(core, width, core):
            seam[:, max(0, x-band):min(width, x+band+1)] = True
        if seam.any() and (~seam).any():
            seam_mae = float(difference[seam].mean())
            interior_mae = float(difference[~seam].mean())
            record.update({
                "seam_band_pixels": int(seam.sum()),
                "seam_mae_gray_levels": seam_mae * 255.0,
                "interior_mae_gray_levels": interior_mae * 255.0,
                "seam_to_interior_ratio": seam_mae / max(interior_mae, 1e-15),
                "seam_max_gray_levels": float(difference[seam].max() * 255.0),
            })
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("r140", "r148"), required=True)
    parser.add_argument("--mode", choices=("full", "tiled"), required=True)
    parser.add_argument("--core", type=int, default=0)
    parser.add_argument("--halo", type=int, default=0)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--save-array", type=Path)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=4)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this controlled benchmark")
    torch.manual_seed(20260928)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    device = torch.device("cuda:0")
    raw, x = load_image(args.image, device)
    model, cfg, checkpoint_sha = load_model(args.model, device)
    parameter_count = sum(p.numel() for p in model.parameters())
    torch.cuda.synchronize()

    with torch.inference_mode():
        for _ in range(args.warmup):
            warm = run_forward(args.model, model, x, args.mode, args.core, args.halo)
            torch.cuda.synchronize()
            del warm
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        idle_allocated = int(torch.cuda.memory_allocated())
        idle_reserved = int(torch.cuda.memory_reserved())
        wall_times = []
        peaks = []
        peak_reserved = []
        free_before = []
        output = None
        for _ in range(args.repeats):
            torch.cuda.reset_peak_memory_stats()
            free, total = torch.cuda.mem_get_info()
            free_before.append(int(free))
            started = time.perf_counter()
            output = run_forward(args.model, model, x, args.mode, args.core, args.halo)
            torch.cuda.synchronize()
            wall_times.append(time.perf_counter() - started)
            peaks.append(int(torch.cuda.max_memory_allocated()))
            peak_reserved.append(int(torch.cuda.max_memory_reserved()))
            if not torch.isfinite(output).all():
                raise RuntimeError("Non-finite output")

    assert output is not None
    array = output.detach().cpu().numpy()[0, 0].astype(np.float32)
    result = {
        "model": cfg["model_name"],
        "kind": args.model,
        "mode": args.mode,
        "core": args.core if args.mode == "tiled" else None,
        "halo": args.halo if args.mode == "tiled" else None,
        "shape": list(raw.shape),
        "precision": "FP32",
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "checkpoint_sha256": checkpoint_sha,
        "source_path": str(args.image),
        "source_sha256": sha256(args.image),
        "parameter_count": int(parameter_count),
        "warmup": args.warmup,
        "repeats": args.repeats,
        "wall_seconds": wall_times,
        "median_seconds": float(statistics.median(wall_times)),
        "mean_seconds": float(statistics.mean(wall_times)),
        "p90_seconds": percentile(wall_times, 90),
        "minimum_seconds": float(min(wall_times)),
        "maximum_seconds": float(max(wall_times)),
        "idle_allocated_bytes": idle_allocated,
        "idle_reserved_bytes": idle_reserved,
        "peak_allocated_bytes": int(max(peaks)),
        "incremental_peak_allocated_bytes": int(max(peaks) - idle_allocated),
        "peak_reserved_bytes": int(max(peak_reserved)),
        "minimum_global_free_before_bytes": int(min(free_before)),
        "global_total_bytes": int(total),
        "output_min": float(array.min()),
        "output_max": float(array.max()),
        "output_mean": float(array.mean()),
        "output_std": float(array.std()),
    }
    if args.reference:
        with np.load(args.reference, allow_pickle=False) as z:
            reference = z["output"]
        if reference.shape != array.shape:
            raise RuntimeError("Reference shape mismatch")
        result["difference_from_full"] = compare(reference, array, args.core if args.mode == "tiled" else None)
    if args.save_array:
        args.save_array.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(args.save_array, output=array)
        result["saved_array"] = str(args.save_array)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
