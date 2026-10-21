"""Tile-safe inference primitives shared by R114 validation and delivery.

The runtime deliberately knows nothing about the concrete R114 model.  A model
may return a tensor, a mapping with an ``output`` entry, or an object with an
``output`` attribute.  Spatial internal maps are stitched with exactly the
same grid as the reconstructed image so validation can inspect them.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import json
import math

import cv2
import numpy as np
import torch
import torch.nn.functional as F


OUTPUT_KEYS = ("output", "reconstruction", "image", "prediction")


@dataclass(frozen=True)
class TileConfig:
    name: str
    core: int
    halo: int
    overlap: int = 0
    origin_y: int = 0
    origin_x: int = 0

    @property
    def stride(self) -> int:
        return self.core - self.overlap

    def validate(self) -> None:
        if self.core <= 0:
            raise ValueError("core must be positive")
        if self.halo < 0:
            raise ValueError("halo must be non-negative")
        if not 0 <= self.overlap < self.core:
            raise ValueError("overlap must be in [0, core)")
        if self.origin_y < 0 or self.origin_x < 0:
            raise ValueError("origins must be non-negative")
        if self.origin_y >= self.stride or self.origin_x >= self.stride:
            raise ValueError("origins must be smaller than the tile stride")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "TileConfig":
        origin = payload.get("origin", (payload.get("origin_y", 0), payload.get("origin_x", 0)))
        return cls(
            name=str(payload["name"]),
            core=int(payload["core"]),
            halo=int(payload["halo"]),
            overlap=int(payload.get("overlap", 0)),
            origin_y=int(origin[0]),
            origin_x=int(origin[1]),
        )


@dataclass
class Prediction:
    output: torch.Tensor
    maps: dict[str, torch.Tensor]


@dataclass
class TiledPrediction(Prediction):
    coverage: torch.Tensor
    tile_count: int


def _tensor_maps(payload: Mapping[str, Any], output_key: str) -> dict[str, torch.Tensor]:
    maps: dict[str, torch.Tensor] = {}
    for key, value in payload.items():
        if key == output_key or not isinstance(value, torch.Tensor):
            continue
        if value.ndim in (3, 4):
            maps[str(key)] = value
    return maps


def split_prediction(value: Any) -> Prediction:
    """Normalize supported model return types into output + internal maps."""
    if isinstance(value, torch.Tensor):
        return Prediction(value, {})
    if isinstance(value, Mapping):
        output_key = next((key for key in OUTPUT_KEYS if isinstance(value.get(key), torch.Tensor)), None)
        if output_key is None:
            raise TypeError("Model mapping does not contain a tensor output")
        return Prediction(value[output_key], _tensor_maps(value, output_key))
    output = getattr(value, "output", None)
    if not isinstance(output, torch.Tensor):
        raise TypeError(f"Unsupported model output type: {type(value)!r}")
    payload = vars(value) if hasattr(value, "__dict__") else {}
    return Prediction(output, _tensor_maps(payload, "output"))


def predict(model: torch.nn.Module, image: torch.Tensor) -> Prediction:
    result = split_prediction(model(image))
    if result.output.ndim != 4:
        raise ValueError(f"Expected BCHW output, got {tuple(result.output.shape)}")
    if result.output.shape[0] != image.shape[0] or result.output.shape[-2:] != image.shape[-2:]:
        raise ValueError(
            f"Model must preserve batch and spatial shape: input={tuple(image.shape)}, "
            f"output={tuple(result.output.shape)}"
        )
    return result


def reflect_pad_large(image: torch.Tensor, amount: int) -> torch.Tensor:
    """Reflect-pad even when the requested pad is larger than an input axis."""
    if amount <= 0:
        return image
    remaining = [amount, amount, amount, amount]
    result = image
    while any(remaining):
        height, width = result.shape[-2:]
        step = [
            min(remaining[0], max(width - 1, 0)),
            min(remaining[1], max(width - 1, 0)),
            min(remaining[2], max(height - 1, 0)),
            min(remaining[3], max(height - 1, 0)),
        ]
        if not any(step):
            return F.pad(result, tuple(remaining), mode="replicate")
        result = F.pad(result, tuple(step), mode="reflect")
        remaining = [left - used for left, used in zip(remaining, step)]
    return result


def axis_starts(length: int, config: TileConfig, axis: str) -> list[int]:
    origin = config.origin_y if axis == "y" else config.origin_x
    starts = [-origin]
    while starts[-1] + config.core < length:
        starts.append(starts[-1] + config.stride)
    return starts


def _spatialize(value: torch.Tensor, output_shape: tuple[int, int]) -> torch.Tensor | None:
    if value.ndim == 3:
        value = value[:, None]
    if value.ndim != 4:
        return None
    if value.shape[-2:] != output_shape:
        value = F.interpolate(value.float(), size=output_shape, mode="bilinear", align_corners=False)
    return value.float()


@torch.inference_mode()
def predict_tiled(model: torch.nn.Module, image: torch.Tensor, config: TileConfig) -> TiledPrediction:
    """Run arbitrary-origin tiled inference with optional overlapping cores."""
    config.validate()
    if image.ndim != 4 or image.shape[0] != 1:
        raise ValueError("Tiled inference expects exactly one BCHW image")
    height, width = map(int, image.shape[-2:])
    pad = config.halo + config.core
    padded = reflect_pad_large(image, pad)
    output_sum: torch.Tensor | None = None
    map_sums: dict[str, torch.Tensor] = {}
    map_weights: dict[str, torch.Tensor] = {}
    coverage = torch.zeros((1, 1, height, width), device=image.device, dtype=torch.float32)
    tile_count = 0

    for top in axis_starts(height, config, "y"):
        for left in axis_starts(width, config, "x"):
            tile = padded[
                ...,
                top + pad - config.halo : top + pad + config.core + config.halo,
                left + pad - config.halo : left + pad + config.core + config.halo,
            ]
            tile_result = predict(model, tile)
            core_output = tile_result.output.float()[
                ...,
                config.halo : config.halo + config.core,
                config.halo : config.halo + config.core,
            ]
            if output_sum is None:
                output_sum = torch.zeros(
                    (1, core_output.shape[1], height, width),
                    device=image.device,
                    dtype=torch.float32,
                )

            out_top, out_left = max(0, top), max(0, left)
            out_bottom, out_right = min(height, top + config.core), min(width, left + config.core)
            if out_top >= out_bottom or out_left >= out_right:
                continue
            crop_top, crop_left = out_top - top, out_left - left
            crop_bottom = crop_top + out_bottom - out_top
            crop_right = crop_left + out_right - out_left
            output_sum[..., out_top:out_bottom, out_left:out_right] += core_output[
                ..., crop_top:crop_bottom, crop_left:crop_right
            ]
            coverage[..., out_top:out_bottom, out_left:out_right] += 1.0

            for name, raw_map in tile_result.maps.items():
                spatial = _spatialize(raw_map, tile_result.output.shape[-2:])
                if spatial is None:
                    continue
                core_map = spatial[
                    ...,
                    config.halo : config.halo + config.core,
                    config.halo : config.halo + config.core,
                ]
                if name not in map_sums:
                    map_sums[name] = torch.zeros(
                        (1, core_map.shape[1], height, width),
                        device=image.device,
                        dtype=torch.float32,
                    )
                    map_weights[name] = torch.zeros(
                        (1, 1, height, width), device=image.device, dtype=torch.float32
                    )
                map_sums[name][..., out_top:out_bottom, out_left:out_right] += core_map[
                    ..., crop_top:crop_bottom, crop_left:crop_right
                ]
                map_weights[name][..., out_top:out_bottom, out_left:out_right] += 1.0
            tile_count += 1

    if output_sum is None or bool((coverage <= 0).any()):
        raise RuntimeError("Tile grid did not cover the complete image")
    output = output_sum / coverage
    maps = {name: value / map_weights[name].clamp_min(1.0) for name, value in map_sums.items()}
    return TiledPrediction(output=output, maps=maps, coverage=coverage, tile_count=tile_count)


def seam_mask(height: int, width: int, config: TileConfig, band: int = 2) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for top in axis_starts(height, config, "y"):
        for boundary in (top, top + config.core):
            if 0 < boundary < height:
                mask[max(0, boundary - band) : min(height, boundary + band + 1), :] = True
    for left in axis_starts(width, config, "x"):
        for boundary in (left, left + config.core):
            if 0 < boundary < width:
                mask[:, max(0, left - band) : min(width, left + band + 1)] = True
    return mask


def _map_to_uint8(name: str, value: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    finite = np.isfinite(value)
    stats = {
        "finite_fraction": float(finite.mean()),
        "minimum": float(np.nanmin(value)) if finite.any() else math.nan,
        "maximum": float(np.nanmax(value)) if finite.any() else math.nan,
        "mean": float(np.nanmean(value)) if finite.any() else math.nan,
        "standard_deviation": float(np.nanstd(value)) if finite.any() else math.nan,
    }
    clean = np.nan_to_num(value, nan=0.0, posinf=0.0, neginf=0.0)
    if name in {"normal_x", "normal_y", "normal_shift", "sdf", "normalized_sdf", "detail"}:
        scale = max(float(np.quantile(np.abs(clean), .995)), 1e-6)
        normalized = np.clip(0.5 + 0.5 * clean / scale, 0.0, 1.0)
    else:
        low, high = np.quantile(clean, [.005, .995])
        if high - low < 1e-8:
            normalized = np.zeros_like(clean)
        else:
            normalized = np.clip((clean - low) / (high - low), 0.0, 1.0)
    return np.rint(normalized * 255.0).astype(np.uint8), stats


def save_internal_maps(directory: Path, maps: Mapping[str, torch.Tensor]) -> dict[str, dict[str, float]]:
    """Save lossless arrays plus viewable PNG previews for all spatial maps."""
    directory.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict[str, float]] = {}
    for name, tensor in sorted(maps.items()):
        value = tensor.detach().float().cpu().numpy()
        np.save(directory / f"{name}.npy", value)
        first = value[0, 0] if value.ndim == 4 else value[0]
        preview, stats = _map_to_uint8(name, first)
        encoded = cv2.imencode(".png", preview)[1]
        encoded.tofile(directory / f"{name}.png")
        summary[name] = stats
    (directory / "map_statistics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary
