from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.cuda.amp import autocast


EXPERIMENT = Path(__file__).resolve().parent
BASE_EXPERIMENT = EXPERIMENT.parent / "BaseUNet_Baseline_20260718"
if str(BASE_EXPERIMENT) not in sys.path:
    sys.path.insert(0, str(BASE_EXPERIMENT))

from train_base_unet import read_gray_u8  # noqa: E402
from train_modern_baseline import (  # noqa: E402
    DEFAULT_PACKAGE,
    TrainConfig,
    build_training_model,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


SEQUENCE_CONFIG = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/01_CURRENT_THESIS_RESULTS_V42_CENTER9/config/sequence_center9_50x20x.json')
)


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(path.suffix or ".bmp", image)
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def tile_positions(length: int, tile_size: int, stride: int) -> list[int]:
    if length <= tile_size:
        return [0]
    positions = list(range(0, length - tile_size + 1, stride))
    last = length - tile_size
    if positions[-1] != last:
        positions.append(last)
    return positions


def feather_window(tile_size: int, overlap: int) -> np.ndarray:
    if overlap <= 0:
        return np.ones((tile_size, tile_size), dtype=np.float32)
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
    model: torch.nn.Module,
    image_u8: np.ndarray,
    device: torch.device,
    tile_size: int = 256,
    overlap: int = 128,
    tile_batch: int = 32,
) -> tuple[np.ndarray, float]:
    if tile_size <= 0 or overlap < 0 or overlap >= tile_size:
        raise ValueError("Require tile_size > overlap >= 0")
    stride = tile_size - overlap
    pad = overlap // 2
    source = image_u8.astype(np.float32) / 255.0
    padded = np.pad(source, ((pad, pad), (pad, pad)), mode="reflect")
    height, width = padded.shape
    add_y = max(0, tile_size - height)
    add_x = max(0, tile_size - width)
    if add_y or add_x:
        padded = np.pad(padded, ((0, add_y), (0, add_x)), mode="reflect")
        height, width = padded.shape

    ys = tile_positions(height, tile_size, stride)
    xs = tile_positions(width, tile_size, stride)
    positions = [(y, x) for y in ys for x in xs]
    window = feather_window(tile_size, overlap)
    accumulation = np.zeros_like(padded, dtype=np.float32)
    weights = np.zeros_like(padded, dtype=np.float32)

    if device.type == "cuda":
        torch.cuda.synchronize(device)
    tick = time.perf_counter()
    model.eval()
    for start in range(0, len(positions), tile_batch):
        chunk = positions[start : start + tile_batch]
        tiles = np.stack(
            [padded[y : y + tile_size, x : x + tile_size] for y, x in chunk],
            axis=0,
        )
        tensor = torch.from_numpy(tiles)[:, None].to(device, non_blocking=True)
        with autocast(enabled=device.type == "cuda"):
            predictions = model(tensor)
        outputs = predictions[:, 0].float().cpu().numpy()
        for output, (y, x) in zip(outputs, chunk):
            accumulation[y : y + tile_size, x : x + tile_size] += output * window
            weights[y : y + tile_size, x : x + tile_size] += window
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    inference_seconds = time.perf_counter() - tick

    reconstructed = accumulation / np.maximum(weights, 1.0e-8)
    reconstructed = reconstructed[
        pad : pad + image_u8.shape[0], pad : pad + image_u8.shape[1]
    ]
    result = np.clip(np.rint(reconstructed * 255.0), 0, 255).astype(np.uint8)
    return result, inference_seconds


def load_model(
    checkpoint_path: Path,
    package: Path,
    device: torch.device,
) -> tuple[torch.nn.Module, dict]:
    checkpoint = torch.load(checkpoint_path, map_location=device)
    training_config = dict(checkpoint.get("training_config", {}))
    model_key = str(checkpoint.get("model_key", training_config.get("model_key", "")))
    if not model_key:
        raise RuntimeError("Checkpoint does not declare its model key")
    allowed = TrainConfig.__dataclass_fields__
    config = TrainConfig(
        **{key: value for key, value in training_config.items() if key in allowed}
    )
    if config.model_key != model_key:
        config = TrainConfig(
            **{
                **{key: value for key, value in training_config.items() if key in allowed},
                "model_key": model_key,
            }
        )
    model = build_training_model(package, config, device)
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    model.eval()
    return model, checkpoint


def main(
    checkpoint: Path,
    output: Path,
    package: Path,
    limit: int,
    tile_size: int,
    overlap: int,
    tile_batch: int,
) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, checkpoint_data = load_model(checkpoint, package, device)
    configuration = json.loads(SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    sequences = configuration.get("sequences", configuration)
    records: list[dict[str, object]] = []
    total_tick = time.perf_counter()

    for sequence_name, sequence in sequences.items():
        raw_dir = Path(PROJECT_ROOT / sequence["raw_dir"])
        source_paths = sorted(raw_dir.glob("*.bmp"))
        if limit > 0:
            source_paths = source_paths[:limit]
        target_dir = output / "sequences" / sequence_name
        for index, source_path in enumerate(source_paths, start=1):
            source = read_gray_u8(source_path)
            result, inference_seconds = reconstruct_tiled(
                model,
                source,
                device,
                tile_size=tile_size,
                overlap=overlap,
                tile_batch=tile_batch,
            )
            target_path = target_dir / source_path.name
            write_gray(target_path, result)
            records.append(
                {
                    "sequence": sequence_name,
                    "frame": source_path.name,
                    "source": str(source_path),
                    "output": str(target_path),
                    "height": int(source.shape[0]),
                    "width": int(source.shape[1]),
                    "inference_seconds": inference_seconds,
                }
            )
            if index == 1 or index % 10 == 0 or index == len(source_paths):
                print(
                    f"{sequence_name}: {index}/{len(source_paths)} "
                    f"({inference_seconds:.3f} s)",
                    flush=True,
                )

    output.mkdir(parents=True, exist_ok=True)
    with (output / "frame_timings.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    times = np.asarray([float(record["inference_seconds"]) for record in records])
    manifest = {
        "purpose": "Modern learned restoration inference on every formal displacement frame",
        "checkpoint": str(checkpoint),
        "checkpoint_epoch": int(checkpoint_data.get("epoch", 0)),
        "checkpoint_validation": checkpoint_data.get("validation", {}),
        "model_key": checkpoint_data.get("model_key"),
        "model_parameter_count": int(checkpoint_data.get("parameter_count", 0)),
        "package": str(package),
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "frame_count": len(records),
        "tile_size": tile_size,
        "tile_overlap": overlap,
        "tile_batch": tile_batch,
        "median_inference_seconds": float(np.median(times)),
        "mean_inference_seconds": float(np.mean(times)),
        "total_elapsed_seconds": time.perf_counter() - total_tick,
    }
    (output / "inference_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--tile-size", type=int, default=256)
    parser.add_argument("--overlap", type=int, default=128)
    parser.add_argument("--tile-batch", type=int, default=32)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(
        arguments.checkpoint.resolve(),
        arguments.output.resolve(),
        arguments.package.resolve(),
        arguments.limit,
        arguments.tile_size,
        arguments.overlap,
        arguments.tile_batch,
    )
