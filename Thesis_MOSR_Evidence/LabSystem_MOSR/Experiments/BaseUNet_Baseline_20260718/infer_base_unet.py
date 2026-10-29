from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.cuda.amp import autocast

from train_base_unet import (
    DEFAULT_PACKAGE,
    BaseUNet,
    build_fixed_psf_layer,
    read_gray_u8,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
DEFAULT_CHECKPOINT = EXPERIMENT / "results" / "best_base_unet.pth.tar"
DEFAULT_OUTPUT = EXPERIMENT / "results" / "real_inference"
SEQUENCE_CONFIG = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json')
)
STATIC_INPUTS = {
    "static_50x_center9": Path(
        str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/20260618_100MG/Image__2026-06-18__17-10-31.bmp')
    ),
    "static_20x_frame49": Path(
        str(PROJECT_ROOT / 'Analyses/20260704_20x_5x_analysis/raw_inputs/20x_1um/bmp/frame_0049.bmp')
    ),
}


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(path.suffix or ".bmp", image)
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


@torch.inference_mode()
def reconstruct(model: BaseUNet, image_u8: np.ndarray, device: torch.device) -> np.ndarray:
    source = torch.from_numpy(image_u8.astype(np.float32) / 255.0)[None, None].to(device)
    original_height, original_width = source.shape[-2:]
    pad_height = (-original_height) % 8
    pad_width = (-original_width) % 8
    if pad_height or pad_width:
        source = F.pad(source, (0, pad_width, 0, pad_height), mode="reflect")
    with autocast(enabled=device.type == "cuda"):
        prediction = model(source)
    prediction = prediction[..., :original_height, :original_width]
    result = prediction[0, 0].float().cpu().numpy()
    return np.clip(np.rint(result * 255.0), 0, 255).astype(np.uint8)


def _tile_positions(length: int, tile_size: int, stride: int) -> list[int]:
    if length <= tile_size:
        return [0]
    positions = list(range(0, length - tile_size + 1, stride))
    last = length - tile_size
    if positions[-1] != last:
        positions.append(last)
    return positions


def _feather_window(tile_size: int, overlap: int) -> np.ndarray:
    edge = max(1, overlap // 2)
    vector = np.ones(tile_size, dtype=np.float32)
    phase = np.linspace(0.0, np.pi / 2.0, edge, endpoint=False, dtype=np.float32)
    ramp = np.sin(phase) ** 2
    vector[:edge] = ramp
    vector[-edge:] = ramp[::-1]
    vector = np.maximum(vector, 1.0e-3)
    return vector[:, None] * vector[None, :]


@torch.inference_mode()
def reconstruct_tiled(
    model: BaseUNet,
    image_u8: np.ndarray,
    device: torch.device,
    tile_size: int = 256,
    overlap: int = 128,
    tile_batch: int = 24,
) -> np.ndarray:
    """Infer with the same spatial support used during patch training.

    Overlapping tiles are reflect-padded and feathered.  This prevents the
    spatial statistics of a mixed full FOV from replacing the 256-pixel patch
    statistics seen during training.
    """
    tile_size = int(tile_size)
    overlap = int(overlap)
    tile_batch = max(1, int(tile_batch))
    if tile_size <= 0 or overlap < 0 or overlap >= tile_size:
        raise ValueError("Require tile_size > overlap >= 0")
    stride = tile_size - overlap
    pad = overlap // 2
    source = image_u8.astype(np.float32) / 255.0
    padded = np.pad(source, ((pad, pad), (pad, pad)), mode="reflect")
    height, width = padded.shape
    if height < tile_size or width < tile_size:
        add_y = max(0, tile_size - height)
        add_x = max(0, tile_size - width)
        padded = np.pad(padded, ((0, add_y), (0, add_x)), mode="reflect")
        height, width = padded.shape

    y_positions = _tile_positions(height, tile_size, stride)
    x_positions = _tile_positions(width, tile_size, stride)
    positions = [(y, x) for y in y_positions for x in x_positions]
    window = _feather_window(tile_size, overlap)
    accumulation = np.zeros_like(padded, dtype=np.float32)
    weights = np.zeros_like(padded, dtype=np.float32)

    model.eval()
    for start in range(0, len(positions), tile_batch):
        chunk = positions[start : start + tile_batch]
        tiles = np.stack(
            [padded[y : y + tile_size, x : x + tile_size] for y, x in chunk], axis=0
        )
        tensor = torch.from_numpy(tiles)[:, None].to(device)
        with autocast(enabled=device.type == "cuda"):
            predictions = model(tensor)
        outputs = predictions[:, 0].float().cpu().numpy()
        for output, (y, x) in zip(outputs, chunk):
            accumulation[y : y + tile_size, x : x + tile_size] += output * window
            weights[y : y + tile_size, x : x + tile_size] += window

    reconstructed = accumulation / np.maximum(weights, 1.0e-8)
    reconstructed = reconstructed[pad : pad + image_u8.shape[0], pad : pad + image_u8.shape[1]]
    return np.clip(np.rint(reconstructed * 255.0), 0, 255).astype(np.uint8)


def load_model(checkpoint_path: Path, device: torch.device) -> tuple[BaseUNet, dict]:
    checkpoint = torch.load(checkpoint_path, map_location=device)
    model_config = checkpoint.get("model_config", {})
    base_channels = int(model_config.get("base_channels", 48))
    input_adapter = None
    if bool(model_config.get("fixed_psf", False)):
        configured_path = str(model_config.get("psf_path", "") or "").strip()
        psf_path = (
            Path(configured_path)
            if configured_path
            else DEFAULT_PACKAGE / "psf" / "PSF_fitted_2D_FOVstack.mat"
        )
        input_adapter = build_fixed_psf_layer(
            DEFAULT_PACKAGE,
            psf_path,
            reg=float(model_config.get("psf_reg", 10.0)),
            alpha=float(model_config.get("psf_alpha", 0.10)),
        )
    model = BaseUNet(base_channels, input_adapter=input_adapter).to(device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    return model, checkpoint


def main(
    checkpoint_path: Path,
    output: Path,
    limit: int,
    tiled: bool,
    tile_size: int,
    tile_overlap: int,
    tile_batch: int,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint = load_model(checkpoint_path, device)
    configuration = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    sequences = configuration.get("sequences", configuration)
    if not isinstance(sequences, dict):
        raise RuntimeError("Sequence configuration is not a mapping")
    records: list[dict] = []
    start = time.time()

    for sequence_name, sequence in sequences.items():
        raw_dir = Path(PROJECT_ROOT / sequence["raw_dir"])
        source_paths = sorted(raw_dir.glob("*.bmp"))
        if limit > 0:
            source_paths = source_paths[:limit]
        target_dir = output / "sequences" / sequence_name
        for source_path in source_paths:
            tick = time.time()
            source = read_gray_u8(source_path)
            prediction = (
                reconstruct_tiled(
                    model,
                    source,
                    device,
                    tile_size=tile_size,
                    overlap=tile_overlap,
                    tile_batch=tile_batch,
                )
                if tiled
                else reconstruct(model, source, device)
            )
            target_path = target_dir / source_path.name
            write_gray(target_path, prediction)
            records.append(
                {
                    "kind": "sequence",
                    "sequence": sequence_name,
                    "source": str(source_path),
                    "output": str(target_path),
                    "height": int(source.shape[0]),
                    "width": int(source.shape[1]),
                    "seconds": time.time() - tick,
                }
            )
        print(f"{sequence_name}: {len(source_paths)} frame(s)", flush=True)

    for name, source_path in STATIC_INPUTS.items():
        tick = time.time()
        source = read_gray_u8(source_path)
        prediction = (
            reconstruct_tiled(
                model,
                source,
                device,
                tile_size=tile_size,
                overlap=tile_overlap,
                tile_batch=tile_batch,
            )
            if tiled
            else reconstruct(model, source, device)
        )
        target_path = output / "static" / f"{name}_base_unet.bmp"
        write_gray(target_path, prediction)
        records.append(
            {
                "kind": "static",
                "name": name,
                "source": str(source_path),
                "output": str(target_path),
                "height": int(source.shape[0]),
                "width": int(source.shape[1]),
                "seconds": time.time() - tick,
            }
        )
        print(f"{name}: done", flush=True)

    manifest = {
        "purpose": "Base U-Net inference for the same CD and displacement inputs used by MOSR",
        "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_validation": checkpoint.get("validation", {}),
        "model_parameter_count": int(checkpoint.get("parameter_count", 0)),
        "device": str(device),
        "limited_frames_per_sequence": limit,
        "inference_mode": "overlap_tiled" if tiled else "full_frame",
        "tile_size": int(tile_size) if tiled else None,
        "tile_overlap": int(tile_overlap) if tiled else None,
        "tile_batch": int(tile_batch) if tiled else None,
        "record_count": len(records),
        "elapsed_seconds": time.time() - start,
        "records": records,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "inference_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "records"}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--tiled", action="store_true")
    parser.add_argument("--tile-size", type=int, default=256)
    parser.add_argument("--tile-overlap", type=int, default=128)
    parser.add_argument("--tile-batch", type=int, default=24)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(
        args.checkpoint.resolve(),
        args.output.resolve(),
        args.limit,
        args.tiled,
        args.tile_size,
        args.tile_overlap,
        args.tile_batch,
    )
