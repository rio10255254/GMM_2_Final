"""Generate frozen R109 output counterfactuals for external GMF testing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = Path(
    str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch/weights/selected/R109.pth')
)
R109_MODEL_FILE = Path(
    str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch/model/r109_model.py')
)
VARIANTS = (
    "r109_current",
    "r109_no_normal_shift",
    "raw_anchor_half_detail",
    "geometry_anchor_half_detail",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Blur(nn.Module):
    def __init__(self, sigma: float):
        super().__init__()
        radius = max(1, int(math.ceil(3 * float(sigma))))
        axis = torch.arange(-radius, radius + 1, dtype=torch.float32)
        row = torch.exp(-0.5 * (axis / float(sigma)).square())
        row /= row.sum()
        self.radius = radius
        self.register_buffer("horizontal", row.view(1, 1, 1, -1))
        self.register_buffer("vertical", row.view(1, 1, -1, 1))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        mode = "reflect" if min(value.shape[-2:]) > self.radius else "replicate"
        result = F.conv2d(
            F.pad(value, (self.radius, self.radius, 0, 0), mode=mode),
            self.horizontal.to(device=value.device, dtype=value.dtype),
        )
        return F.conv2d(
            F.pad(result, (0, 0, self.radius, self.radius), mode=mode),
            self.vertical.to(device=value.device, dtype=value.dtype),
        )


def load_r109(checkpoint: Path, device: torch.device):
    spec = importlib.util.spec_from_file_location("r116_r109_reference", R109_MODEL_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {R109_MODEL_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = torch.load(checkpoint, map_location=device, weights_only=False)
    model = module.build_model().to(device)
    model.load_state_dict(payload["model"], strict=True)
    model.eval()
    return module, model, payload


def width_transform(value: torch.Tensor, width_gain: torch.Tensor,
                    window: int = 21) -> torch.Tensor:
    radius = window // 2
    local_max = F.max_pool2d(value, window, stride=1, padding=radius)
    local_min = -F.max_pool2d(-value, window, stride=1, padding=radius)
    dynamic = (local_max - local_min).clamp_min(2.0 / 255.0)
    unit = ((value - local_min) / dynamic).clamp(1.0e-3, 1.0 - 1.0e-3)
    corrected = torch.sigmoid(width_gain * (torch.log(unit) - torch.log1p(-unit)))
    return local_min + dynamic * corrected


def tile_variants(model, tile: torch.Tensor, blur: Blur) -> dict[str, torch.Tensor]:
    details = model.forward_details(tile)
    raw = tile.float().clamp(0.0, 1.0)
    current = details.output.float()
    no_shift_proposal = width_transform(raw, details.width_gain.float())
    no_shift = (raw + details.support.float() * (no_shift_proposal - raw)).clamp(0.0, 1.0)

    raw_residual = current - raw
    raw_high = raw_residual - blur(raw_residual)
    raw_anchor = (raw + 0.5 * raw_high).clamp(0.0, 1.0)

    geometry_anchor = model.warp(raw, details.flow.float() * details.support.float())
    geometry_residual = current - geometry_anchor
    geometry_high = geometry_residual - blur(geometry_residual)
    geometry_detail = (geometry_anchor + 0.5 * geometry_high).clamp(0.0, 1.0)
    return {
        "r109_current": current,
        "r109_no_normal_shift": no_shift,
        "raw_anchor_half_detail": raw_anchor,
        "geometry_anchor_half_detail": geometry_detail,
    }


@torch.inference_mode()
def tiled_variants(model, image: np.ndarray, device: torch.device,
                   core: int, halo: int, blur: Blur) -> dict[str, np.ndarray]:
    tensor = torch.from_numpy(image[None, None]).to(device=device, dtype=torch.float32)
    height, width = image.shape
    mode = "reflect" if min(height, width) > halo else "replicate"
    padded = F.pad(tensor, (halo, halo, halo, halo), mode=mode)
    outputs = {name: torch.empty_like(tensor) for name in VARIANTS}
    for y0 in range(0, height, core):
        y1 = min(y0 + core, height)
        for x0 in range(0, width, core):
            x1 = min(x0 + core, width)
            tile = padded[..., y0:y1 + 2 * halo, x0:x1 + 2 * halo]
            values = tile_variants(model, tile, blur)
            for name, value in values.items():
                outputs[name][..., y0:y1, x0:x1] = value[
                    ...,
                    halo:halo + (y1 - y0),
                    halo:halo + (x1 - x0),
                ]
    return {name: value[0, 0].cpu().numpy() for name, value in outputs.items()}


def read_image(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"cannot read {path}")
    return value.astype(np.float32) / 255.0


def write_image(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = cv2.imencode(".bmp", np.rint(np.clip(value, 0, 1) * 255).astype(np.uint8))[1]
    encoded.tofile(str(path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--core", type=int, default=1024)
    parser.add_argument("--halo", type=int, default=224)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    source = Path(args.input).resolve()
    destination = Path(args.output).resolve()
    checkpoint = Path(args.checkpoint).resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    files = [source] if source.is_file() else sorted(
        item for item in source.rglob("*")
        if item.is_file() and item.suffix.lower() in {".bmp", ".png", ".tif", ".tiff"}
    )
    if args.limit > 0:
        files = files[:args.limit]
    if not files:
        raise RuntimeError("no images found")
    device = torch.device(args.device)
    _module, model, payload = load_r109(checkpoint, device)
    blur = Blur(3.2).to(device).eval()
    rows = []
    for index, path in enumerate(files, 1):
        relative = Path(path.name) if source.is_file() else path.relative_to(source)
        values = tiled_variants(model, read_image(path), device, args.core, args.halo, blur)
        row = {"input": str(path), "input_sha256": sha256(path)}
        for name, value in values.items():
            output_path = (destination / name / relative).with_suffix(".bmp")
            write_image(output_path, value)
            row[f"{name}_output"] = str(output_path)
            row[f"{name}_sha256"] = sha256(output_path)
        rows.append(row)
        print(json.dumps({"done": index, "total": len(files), "file": path.name}), flush=True)

    destination.mkdir(parents=True, exist_ok=True)
    table = destination / "counterfactual_manifest.csv"
    with table.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "status": "complete",
        "images": len(rows),
        "variants": list(VARIANTS),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "checkpoint_epoch": int(payload.get("epoch", -1)),
        "core": args.core,
        "halo": args.halo,
        "external_gmf_required_for_ranking": True,
        "formal_training_authorized": False,
    }
    (destination / "counterfactual_state.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
