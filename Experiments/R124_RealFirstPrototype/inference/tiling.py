"""Native-coordinate tiling with explicit complete iterative context."""
from __future__ import annotations
import torch


def _boundaries(size: int, core: int, phase: int):
    return sorted({0, size, *range(phase % core, size, core)})


@torch.inference_mode()
def tiled_forward(model, raw: torch.Tensor, core: int = 256, halo: int | None = None,
                  origin: tuple[int, int] = (0, 0), trace: bool = False):
    if trace:
        raise ValueError('Use forward_details on an explicit diagnostic window for stage traces')
    model._validate_input(raw)
    if model.training:
        raise ValueError('Set model.eval() for tiled inference')
    if type(core) is not int or core < 1:
        raise ValueError('core must be a positive integer')
    halo = model.required_halo if halo is None else halo
    if type(halo) is not int or halo < model.required_halo:
        raise ValueError(f'halo must be at least {model.required_halo} native pixels')
    if len(origin) != 2 or any(type(x) is not int for x in origin):
        raise ValueError('origin must be two native integer coordinates')
    h, w = raw.shape[-2:]
    yy, xx = _boundaries(h, core, origin[0]), _boundaries(w, core, origin[1])
    out = torch.empty_like(raw)
    for y0, y1 in zip(yy, yy[1:]):
        for x0, x1 in zip(xx, xx[1:]):
            sy, ey = max(0, y0-halo), min(h, y1+halo)
            sx, ex = max(0, x0-halo), min(w, x1+halo)
            part = model(raw[..., sy:ey, sx:ex])
            out[..., y0:y1, x0:x1] = part[..., y0-sy:y1-sy, x0-sx:x1-sx]
    if not torch.isfinite(out).all():
        raise FloatingPointError('Nonfinite tiled output')
    return out
