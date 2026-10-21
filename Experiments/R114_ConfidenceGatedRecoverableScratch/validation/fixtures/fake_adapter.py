"""Deterministic local fake used only to test the R114 validation plumbing."""
from __future__ import annotations

import torch
import torch.nn.functional as F


class FakeTileSafeModel(torch.nn.Module):
    minimum_halo_px = 4

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        padded = F.pad(image, (1, 1, 1, 1), mode="reflect")
        gx = 0.5 * (padded[..., 1:-1, 2:] - padded[..., 1:-1, :-2])
        gy = 0.5 * (padded[..., 2:, 1:-1] - padded[..., :-2, 1:-1])
        magnitude = torch.sqrt(gx.square() + gy.square() + 1e-8)
        normal_x = gx / magnitude.clamp_min(1e-4)
        normal_y = gy / magnitude.clamp_min(1e-4)
        boundary = torch.sigmoid((magnitude - .035) * 24.0)
        local_mean = F.avg_pool2d(padded, 3, stride=1)
        need = torch.sigmoid((torch.abs(image - local_mean) - .012) * 18.0)
        recoverability = torch.clamp(magnitude / .18, 0.0, 1.0)
        geometry_gate = boundary * need
        detail_gate = geometry_gate * recoverability
        zeros = torch.zeros_like(image)
        return {
            "output": image,
            "normalized_sdf": torch.tanh((image - .5) * 4.0),
            "normal_x": normal_x,
            "normal_y": normal_y,
            "boundary_confidence": boundary,
            "correction_need": need,
            "recoverability": recoverability,
            "geometry_gate": geometry_gate,
            "detail_gate": detail_gate,
            "width_gain": torch.ones_like(image),
            "normal_shift": zeros,
            "detail": zeros,
        }


def load_model(checkpoint: str | None, device: torch.device) -> torch.nn.Module:
    if checkpoint:
        raise ValueError("The validation fake does not accept checkpoints")
    return FakeTileSafeModel().to(device).eval()
