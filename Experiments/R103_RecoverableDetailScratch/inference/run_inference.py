"""Simple file/folder inference entry for R103 checkpoints."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "inference"):
    sys.path.insert(0, str(folder))

from r103_model import build_model  # noqa: E402
from reconstruct import reconstruct_tensor  # noqa: E402


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def image_paths(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    extensions = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    return sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() in extensions)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "inference")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--core-size", type=int, default=512)
    parser.add_argument("--halo", type=int, default=128)
    parser.add_argument("--tile-batch", type=int, default=1)
    args = parser.parse_args()
    if not args.checkpoint.is_file():
        raise FileNotFoundError(args.checkpoint)
    bounds = CONFIG["model"]["branch_bounds"]
    model = build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]), contour_bound=float(bounds["contour"]),
        texture_bound=float(bounds["texture"]), combined_bound=float(bounds["combined"]),
    )
    payload = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model.load_state_dict(payload["ema_state_dict"], strict=True)
    device = torch.device(args.device)
    model = model.to(device).eval()
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = []
    for path in image_paths(args.source):
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            continue
        tensor = torch.from_numpy(image.astype(np.float32) / 255.0).view(1, 1, *image.shape).to(device)
        prediction = reconstruct_tensor(
            model, tensor, core_size=args.core_size, halo=args.halo, tile_batch=args.tile_batch
        )
        array = np.clip(prediction.float().cpu().squeeze().numpy() * 255.0 + 0.5, 0, 255).astype(np.uint8)
        output_path = args.output / f"{path.stem}_R103.png"
        if not cv2.imwrite(str(output_path), array):
            raise RuntimeError(f"Unable to save {output_path}")
        outputs.append(str(output_path))
    manifest = {
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_epoch": payload.get("epoch"),
        "precision": "float32",
        "core_size": args.core_size,
        "halo": args.halo,
        "tile_batch": args.tile_batch,
        "outputs": outputs,
    }
    (args.output / "inference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
