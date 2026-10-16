"""Reconstruct one grayscale image with an R100 training checkpoint."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--core-size", type=int, default=512)
    parser.add_argument("--halo", type=int, default=192)
    parser.add_argument("--tile-batch", type=int, default=1)
    parser.add_argument("--raw-weights", action="store_true", help="Use non-EMA weights")
    args = parser.parse_args()

    model_module = load_module("r100_inference_model", ROOT / "model" / "r100_model.py")
    inference = load_module("r100_inference_tiling", ROOT / "inference" / "reconstruct.py")
    device = torch.device(args.device)
    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    state_key = "model_state_dict" if args.raw_weights else "ema_state_dict"
    if state_key not in checkpoint:
        raise KeyError(f"Checkpoint does not contain {state_key}")
    model = model_module.build_model(base=24).to(device).eval()
    model.load_state_dict(checkpoint[state_key], strict=True)

    image = cv2.imread(str(args.input), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(args.input)
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        scale = 65535.0
    elif image.dtype == np.uint8:
        scale = 255.0
    else:
        scale = float(np.max(image)) if float(np.max(image)) > 1.0 else 1.0
    tensor = torch.from_numpy(np.asarray(image, dtype=np.float32) / max(scale, 1e-6)).view(1, 1, *image.shape).to(device)
    output = inference.reconstruct_tensor(
        model,
        tensor,
        core_size=int(args.core_size),
        halo=int(args.halo),
        tile_batch=int(args.tile_batch),
    )
    array = output[0, 0].clamp(0.0, 1.0).cpu().numpy()
    if image.dtype == np.uint16:
        encoded = np.clip(np.rint(array * 65535.0), 0, 65535).astype(np.uint16)
    else:
        encoded = np.clip(np.rint(array * 255.0), 0, 255).astype(np.uint8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), encoded):
        raise IOError(f"Failed to write {args.output}")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
