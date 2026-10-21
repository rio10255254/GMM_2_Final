"""Seam-free canonical tiling for the strictly local R117 model."""

from __future__ import annotations

import torch


@torch.inference_mode()
def forward_tiled(model, image: torch.Tensor, core_size: int = 768, halo: int | None = None) -> torch.Tensor:
    selected_halo = int(model.minimum_halo_px if halo is None else halo)
    if selected_halo < int(model.minimum_halo_px):
        raise ValueError("halo is below the R117 locality contract")
    height, width = image.shape[-2:]
    output = torch.empty_like(image, dtype=torch.float32)
    coverage = torch.zeros_like(image, dtype=torch.int16)
    for y0 in range(0, height, int(core_size)):
        y1 = min(height, y0 + int(core_size))
        sy0, sy1 = max(0, y0 - selected_halo), min(height, y1 + selected_halo)
        for x0 in range(0, width, int(core_size)):
            x1 = min(width, x0 + int(core_size))
            sx0, sx1 = max(0, x0 - selected_halo), min(width, x1 + selected_halo)
            tile = model(image[..., sy0:sy1, sx0:sx1])
            output[..., y0:y1, x0:x1] = tile[..., y0 - sy0:y1 - sy0, x0 - sx0:x1 - sx0]
            coverage[..., y0:y1, x0:x1] += 1
    if not bool((coverage == 1).all()) or not bool(torch.isfinite(output).all()):
        raise RuntimeError("invalid R117 tiled reconstruction")
    return output
