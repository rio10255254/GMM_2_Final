"""Inference-only adapter from R116 checkpoints to the locked ACM runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import build_model


class Wrapper(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.minimum_halo_px = model.minimum_halo_px

    def forward(self, value: torch.Tensor) -> dict[str, torch.Tensor]:
        details = self.model.forward_details(value)
        values = {name: getattr(details, name) for name in details.__dataclass_fields__}
        values["profile_visibility"] = torch.maximum(
            details.width_gate, details.shift_gate,
        )
        return values


def load_model(checkpoint: str | None, device: torch.device):
    if not checkpoint:
        raise ValueError("R116 adapter requires a checkpoint")
    path = Path(checkpoint)
    saved = torch.load(path, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True or saved.get("checkpoint_loaded") is not False:
        raise RuntimeError("R116 validation requires a clean scratch checkpoint")
    model = build_model()
    model.load_state_dict(saved["model"], strict=True)
    model.requires_grad_(False)
    return Wrapper(model.to(device).eval())


@dataclass(frozen=True)
class TileConfig:
    name: str
    core: int
    halo: int
    overlap: int = 0
    origin_y: int = 0
    origin_x: int = 0


@dataclass(frozen=True)
class Prediction:
    output: torch.Tensor
    maps: dict[str, torch.Tensor]
    coverage: torch.Tensor
    tile_count: int


def canonical_tile_config(model, *, core: int = 768,
                          halo: int | None = None) -> TileConfig:
    required = int(model.minimum_halo_px)
    selected = required if halo is None else int(halo)
    if selected < required:
        raise ValueError("R116 halo below locality contract")
    return TileConfig("canonical_grid_a", int(core), selected)


@torch.inference_mode()
def predict_canonical_tiled(model, image: torch.Tensor,
                            config: TileConfig | None = None) -> Prediction:
    selected = config or canonical_tile_config(model)
    height, width = image.shape[-2:]
    output = torch.empty_like(image, dtype=torch.float32)
    coverage = torch.zeros_like(image, dtype=torch.int16)
    maps: dict[str, torch.Tensor] = {}
    count = 0
    for y0 in range(0, height, selected.core):
        y1 = min(height, y0 + selected.core)
        sy0, sy1 = max(0, y0 - selected.halo), min(height, y1 + selected.halo)
        for x0 in range(0, width, selected.core):
            x1 = min(width, x0 + selected.core)
            sx0, sx1 = max(0, x0 - selected.halo), min(width, x1 + selected.halo)
            values = model(image[..., sy0:sy1, sx0:sx1])
            cy0, cy1 = y0 - sy0, y1 - sy0
            cx0, cx1 = x0 - sx0, x1 - sx0
            output[..., y0:y1, x0:x1] = values["output"][..., cy0:cy1, cx0:cx1]
            coverage[..., y0:y1, x0:x1] += 1
            for name, tensor in values.items():
                if name == "output":
                    continue
                if name not in maps:
                    maps[name] = tensor.new_empty(
                        tensor.shape[0], tensor.shape[1], height, width,
                    )
                maps[name][..., y0:y1, x0:x1] = tensor[..., cy0:cy1, cx0:cx1]
            count += 1
    if not bool((coverage == 1).all()):
        raise RuntimeError("R116 canonical tile coverage invalid")
    if not bool(torch.isfinite(output).all()) or any(
        not bool(torch.isfinite(value).all()) for value in maps.values()
    ):
        raise FloatingPointError("R116 tiled output contains non-finite values")
    return Prediction(output, maps, coverage, count)
