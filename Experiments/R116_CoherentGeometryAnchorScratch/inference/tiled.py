"""Canonical one-time outer padding and core-only tiled inference for R116."""

from __future__ import annotations

import torch
import torch.nn.functional as F


@torch.inference_mode()
def forward_tiled(model, value: torch.Tensor, core_size: int = 1024,
                  halo: int | None = None) -> torch.Tensor:
    if value.ndim != 4 or value.shape[1] != 1:
        raise ValueError("expected [batch, 1, height, width]")
    if core_size < 1:
        raise ValueError("core_size must be positive")
    actual_halo = int(model.minimum_halo_px if halo is None else halo)
    if actual_halo < int(model.minimum_halo_px):
        raise ValueError(
            f"halo {actual_halo} is smaller than the model minimum {model.minimum_halo_px}"
        )
    height, width = value.shape[-2:]
    mode = "reflect" if min(height, width) > actual_halo else "replicate"
    padded = F.pad(
        value,
        (actual_halo, actual_halo, actual_halo, actual_halo),
        mode=mode,
    )
    output = torch.empty_like(value)
    for y0 in range(0, height, core_size):
        y1 = min(y0 + core_size, height)
        for x0 in range(0, width, core_size):
            x1 = min(x0 + core_size, width)
            tile = padded[
                ...,
                y0:y1 + 2 * actual_halo,
                x0:x1 + 2 * actual_halo,
            ]
            reconstructed = model(tile)
            output[..., y0:y1, x0:x1] = reconstructed[
                ...,
                actual_halo:actual_halo + (y1 - y0),
                actual_halo:actual_halo + (x1 - x0),
            ]
    return output
