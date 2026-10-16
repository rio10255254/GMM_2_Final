"""Canonical phase-aligned full/tiled inference for the R94 prototype."""
from __future__ import annotations

import math

import torch
from torch import nn
import torch.nn.functional as F


def _reflect_pad(x: torch.Tensor, left: int, right: int, top: int, bottom: int) -> torch.Tensor:
    remaining = [int(left), int(right), int(top), int(bottom)]
    while any(remaining):
        h, w = x.shape[-2:]
        step = [
            min(remaining[0], max(w - 1, 0)),
            min(remaining[1], max(w - 1, 0)),
            min(remaining[2], max(h - 1, 0)),
            min(remaining[3], max(h - 1, 0)),
        ]
        if not any(step):
            return F.pad(x, tuple(remaining), mode="replicate")
        x = F.pad(x, tuple(step), mode="reflect")
        remaining = [value - used for value, used in zip(remaining, step)]
    return x


def canonical_canvas(image: torch.Tensor, core_size: int, halo: int) -> tuple[torch.Tensor, tuple[int, int, int, int]]:
    if image.ndim != 4 or image.shape[0] != 1 or image.shape[1] != 1:
        raise ValueError("Expected one grayscale image shaped [1,1,H,W]")
    if core_size <= 0 or core_size % 8 or halo < 0 or halo % 8:
        raise ValueError("core_size and halo must be non-negative multiples of 8")
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
) -> torch.Tensor:
    if halo < int(getattr(model, "minimum_halo_px", 192)):
        raise ValueError("halo is below the model minimum")
    canvas, (h, w, grid_h, grid_w) = canonical_canvas(image, core_size, halo)
    output = torch.empty((1, 1, grid_h, grid_w), device=image.device, dtype=torch.float32)
    locations = [(y, x) for y in range(0, grid_h, core_size) for x in range(0, grid_w, core_size)]
    for start in range(0, len(locations), tile_batch):
        selected = locations[start : start + tile_batch]
        tiles = torch.cat(
            [canvas[..., y : y + core_size + 2 * halo, x : x + core_size + 2 * halo] for y, x in selected], dim=0
        )
        predictions = model(tiles).float()[..., halo : halo + core_size, halo : halo + core_size]
        for prediction, (y, x) in zip(predictions, selected):
            output[0, :, y : y + core_size, x : x + core_size] = prediction
    return output[..., :h, :w]


@torch.inference_mode()
def reconstruct_full_reference(
    model: nn.Module,
    image: torch.Tensor,
    *,
    core_size: int = 512,
    halo: int = 192,
) -> torch.Tensor:
    canvas, (h, w, _grid_h, _grid_w) = canonical_canvas(image, core_size, halo)
    result = model(canvas).float()
    return result[..., halo : halo + h, halo : halo + w]

