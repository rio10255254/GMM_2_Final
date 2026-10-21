"""R89 inference with one canonical, phase-aligned tiled reconstruction path."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Iterable

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "model" / "r89_model.py"
EXPERIMENT_ID = "R89_MeasurementNativeScratch"
SUPPORTED = {".png", ".tif", ".tiff", ".bmp", ".jpg", ".jpeg"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_model(checkpoint: Path, device: torch.device) -> tuple[nn.Module, dict[str, Any]]:
    module = load_module("r89_model_inference", MODEL_PATH)
    model = module.build_model(base=24)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if payload.get("experiment_id") != EXPERIMENT_ID:
        raise RuntimeError("Checkpoint does not belong to R89")
    state = payload.get("ema_state_dict")
    if not isinstance(state, dict):
        raise RuntimeError("R89 inference requires the selected EMA weights")
    model.load_state_dict(state, strict=True)
    model.to(device).eval()
    return model, payload


def _reflect_pad(x: torch.Tensor, left: int, right: int, top: int, bottom: int) -> torch.Tensor:
    """Reflect-pad arbitrary amounts, including amounts larger than the image."""
    remaining = [int(left), int(right), int(top), int(bottom)]
    while any(remaining):
        h, w = x.shape[-2:]
        step = [min(remaining[0], max(w - 1, 0)), min(remaining[1], max(w - 1, 0)), min(remaining[2], max(h - 1, 0)), min(remaining[3], max(h - 1, 0))]
        if not any(step):
            return F.pad(x, tuple(remaining), mode="replicate")
        x = F.pad(x, tuple(step), mode="reflect")
        remaining = [value - used for value, used in zip(remaining, step)]
    return x


def canonical_canvas(image: torch.Tensor, core_size: int, halo: int) -> tuple[torch.Tensor, tuple[int, int, int, int]]:
    if image.ndim != 4 or image.shape[0] != 1 or image.shape[1] != 1:
        raise ValueError("Expected one grayscale image shaped [1,1,H,W]")
    if core_size <= 0 or core_size % 8:
        raise ValueError("core_size must be a positive multiple of 8")
    if halo < 0 or halo % 8:
        raise ValueError("halo must be a non-negative multiple of 8")
    h, w = map(int, image.shape[-2:])
    grid_h = int(math.ceil(h / core_size) * core_size)
    grid_w = int(math.ceil(w / core_size) * core_size)
    canvas = _reflect_pad(image, halo, halo + grid_w - w, halo, halo + grid_h - h)
    return canvas, (h, w, grid_h, grid_w)


@torch.inference_mode()
def reconstruct_tensor(
    model: nn.Module,
    image: torch.Tensor,
    *,
    core_size: int = 512,
    halo: int = 192,
    tile_batch: int = 1,
    amp: bool = True,
) -> torch.Tensor:
    """Reconstruct through the deployment tiled path and return the original extent."""
    if halo < int(getattr(model, "minimum_halo_px", 192)):
        raise ValueError(f"halo={halo} is below the model minimum")
    canvas, (h, w, grid_h, grid_w) = canonical_canvas(image, core_size, halo)
    output = torch.empty((1, 1, grid_h, grid_w), device=image.device, dtype=torch.float32)
    locations = [(y, x) for y in range(0, grid_h, core_size) for x in range(0, grid_w, core_size)]
    for start in range(0, len(locations), tile_batch):
        batch_locations = locations[start:start + tile_batch]
        tiles = torch.cat([canvas[..., y:y + core_size + 2 * halo, x:x + core_size + 2 * halo] for y, x in batch_locations], dim=0)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp and image.device.type == "cuda"):
            predictions = model(tiles)
        predictions = predictions.float()[..., halo:halo + core_size, halo:halo + core_size]
        for prediction, (y, x) in zip(predictions, batch_locations):
            output[0, :, y:y + core_size, x:x + core_size] = prediction
    return output[..., :h, :w]


@torch.inference_mode()
def reconstruct_full_reference(
    model: nn.Module,
    image: torch.Tensor,
    *,
    core_size: int = 512,
    halo: int = 192,
    amp: bool = True,
) -> torch.Tensor:
    """Full-canvas reference used only for parity tests, not deployment."""
    canvas, (h, w, _grid_h, _grid_w) = canonical_canvas(image, core_size, halo)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp and image.device.type == "cuda"):
        result = model(canvas).float()
    return result[..., halo:halo + h, halo:halo + w]


def read_gray(path: Path) -> tuple[np.ndarray, np.dtype]:
    encoded = np.fromfile(path, dtype=np.uint8)
    array = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if array is None:
        raise RuntimeError(f"Could not read image: {path}")
    if array.ndim == 3:
        if array.shape[2] == 4:
            array = cv2.cvtColor(array, cv2.COLOR_BGRA2GRAY)
        else:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    if array.dtype not in (np.uint8, np.uint16):
        raise TypeError(f"Only uint8 and uint16 images are supported: {path}")
    return array, array.dtype


def write_image(path: Path, array: np.ndarray) -> None:
    extension = path.suffix.lower()
    if extension not in SUPPORTED:
        raise ValueError(f"Unsupported output extension: {path}")
    success, encoded = cv2.imencode(extension, array)
    if not success:
        raise RuntimeError(f"Could not encode image: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(path)


def image_tensor(array: np.ndarray, device: torch.device) -> torch.Tensor:
    maximum = float(np.iinfo(array.dtype).max)
    return torch.from_numpy(np.ascontiguousarray(array)).to(device=device, dtype=torch.float32).div_(maximum)[None, None]


def output_array(tensor: torch.Tensor, dtype: np.dtype) -> np.ndarray:
    maximum = float(np.iinfo(dtype).max)
    return np.rint(tensor[0, 0].clamp(0, 1).cpu().numpy() * maximum).astype(dtype)


def collect_inputs(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        raise FileNotFoundError(path)
    yield from sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED)


def run(args: argparse.Namespace) -> int:
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    checkpoint = Path(args.checkpoint).resolve()
    model, payload = load_model(checkpoint, device)
    source_root, output_root = Path(args.input).resolve(), Path(args.output).resolve()
    inputs = list(collect_inputs(source_root))
    if not inputs:
        raise RuntimeError("No supported images were found")
    records = []
    for source_path in inputs:
        relative = Path(source_path.name) if source_root.is_file() else source_path.relative_to(source_root)
        destination = output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source, dtype = read_gray(source_path)
        reconstructed = reconstruct_tensor(model, image_tensor(source, device), core_size=args.core_size, halo=args.halo, tile_batch=args.tile_batch, amp=not args.no_amp)
        result = output_array(reconstructed, dtype)
        write_image(destination, result)
        records.append({"input": str(source_path), "output": str(destination), "shape": list(source.shape), "dtype": str(dtype), "input_sha256": sha256_file(source_path), "output_sha256": sha256_file(destination)})
        print(json.dumps({"completed": len(records), "total": len(inputs), "output": str(destination)}, ensure_ascii=False), flush=True)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "checkpoint_epoch": int(payload.get("epoch", -1)),
        "weight_source": "ema_state_dict",
        "core_size": int(args.core_size),
        "halo": int(args.halo),
        "tile_size": int(args.core_size + 2 * args.halo),
        "records": records,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = output_root / "reconstruction_manifest.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, output_root / "reconstruction_manifest.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--core-size", type=int, default=512)
    parser.add_argument("--halo", type=int, default=192)
    parser.add_argument("--tile-batch", type=int, default=1)
    parser.add_argument("--no-amp", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
