"""Reconstruct a folder of grayscale images with an R107 checkpoint."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "model")); sys.path.insert(0, str(ROOT / "inference"))
from r107_model import build_model  # noqa: E402
from reconstruct import reconstruct_tensor  # noqa: E402


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None: raise RuntimeError(path)
    if image.ndim == 3: image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16: return image.astype(np.float32) / 65535.0
    return image.astype(np.float32) / 255.0


def save_gray(path: Path, image: np.ndarray, bit_depth: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if bit_depth == 16: value = np.round(np.clip(image, 0, 1) * 65535).astype(np.uint16)
    else: value = np.round(np.clip(image, 0, 1) * 255).astype(np.uint8)
    encoded = cv2.imencode(path.suffix or ".png", value)[1]; encoded.tofile(str(path))


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--checkpoint", required=True); parser.add_argument("--input", required=True); parser.add_argument("--output", required=True); parser.add_argument("--core-size", type=int, default=int(CONFIG["inference"]["core_size"])); parser.add_argument("--halo", type=int, default=int(CONFIG["inference"]["halo"])); parser.add_argument("--tile-batch", type=int, default=int(CONFIG["inference"]["tile_batch"])); parser.add_argument("--bit-depth", type=int, choices=[8,16], default=8); args = parser.parse_args()
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu"); checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False); model = build_model().to(device); model.load_state_dict(checkpoint["model"], strict=True); model.eval()
    source, output = Path(args.input), Path(args.output); extensions = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}; files = [source] if source.is_file() else sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() in extensions)
    rows=[]
    for index, path in enumerate(files):
        image=read_gray(path); tensor=torch.from_numpy(image[None,None]).to(device); prediction=reconstruct_tensor(model,tensor,core_size=args.core_size,halo=args.halo,tile_batch=args.tile_batch)[0,0].cpu().numpy(); destination=output/path.with_suffix(".png").name if output.suffix=="" else output; save_gray(destination,prediction,args.bit_depth); rows.append({"index":index,"input":str(path),"output":str(destination),"height":image.shape[0],"width":image.shape[1]}); print(json.dumps(rows[-1]),flush=True)
    output.mkdir(parents=True,exist_ok=True) if output.suffix=="" else output.parent.mkdir(parents=True,exist_ok=True)
    manifest=(output/"reconstruction_manifest.csv") if output.suffix=="" else output.with_suffix(".manifest.csv")
    with manifest.open("w",newline="",encoding="utf-8-sig") as handle: writer=csv.DictWriter(handle,fieldnames=list(rows[0].keys()) if rows else ["index","input","output","height","width"]); writer.writeheader(); writer.writerows(rows)
    return 0


if __name__=="__main__": raise SystemExit(main())

