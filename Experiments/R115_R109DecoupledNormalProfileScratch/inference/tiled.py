"""Canonical non-overlapping tiled inference for R115."""
from __future__ import annotations

import torch

from model.r115_model import R115Model


@torch.no_grad()
def forward_tiled(
    model: R115Model,
    value: torch.Tensor,
    core_size: int = 512,
    halo: int | None = None,
) -> torch.Tensor:
    if value.ndim != 4 or value.shape[1] != 1:
        raise ValueError("expected [batch, 1, height, width]")
    actual_halo = model.minimum_halo_px if halo is None else int(halo)
    if actual_halo < model.minimum_halo_px:
        raise ValueError("halo is smaller than the R115 locality contract")
    height, width = value.shape[-2:]
    output = torch.empty_like(value, dtype=torch.float32)
    for y0 in range(0, height, core_size):
        y1 = min(height, y0 + core_size)
        sy0, sy1 = max(0, y0 - actual_halo), min(height, y1 + actual_halo)
        for x0 in range(0, width, core_size):
            x1 = min(width, x0 + core_size)
            sx0, sx1 = max(0, x0 - actual_halo), min(width, x1 + actual_halo)
            tile = model(value[..., sy0:sy1, sx0:sx1])
            output[..., y0:y1, x0:x1] = tile[
                ..., y0 - sy0:y1 - sy0, x0 - sx0:x1 - sx0
            ]
    return output

