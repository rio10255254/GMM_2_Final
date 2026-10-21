"""Load a frozen R114 checkpoint for the generic validation scaffold."""
from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import build_full_model


class ValidationWrapper(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.minimum_halo_px = model.minimum_halo_px

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        details = self.model.forward_details(image)
        return {
            "output": details.output,
            "normalized_sdf": details.normalized_sdf,
            "normal_x": details.normal_x,
            "normal_y": details.normal_y,
            "boundary_confidence": details.boundary_confidence,
            "correction_need": details.correction_need,
            "recoverability": details.recoverability,
            "geometry_gate": details.geometry_gate,
            "detail_gate": details.detail_gate,
            "width_gain": details.width_gain,
            "normal_shift": details.normal_shift,
            "detail": details.detail,
        }


def load_model(checkpoint: str | None, device: torch.device) -> torch.nn.Module:
    if not checkpoint:
        raise ValueError("R114 validation requires a checkpoint")
    payload = torch.load(Path(checkpoint), map_location="cpu")
    if not bool(payload.get("scratch")) or bool(payload.get("foreign_checkpoint_loaded")):
        raise RuntimeError("checkpoint violates the R114 scratch-only contract")
    model = build_full_model(detail_enabled=bool(payload.get("detail_enabled", False)))
    model.load_state_dict(payload["model"], strict=True)
    return ValidationWrapper(model.to(device).eval())
