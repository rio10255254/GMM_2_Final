"""Adapter allowing the locked ACM runner to evaluate one causal intervention."""

from __future__ import annotations

import os
from pathlib import Path

import torch

from model.r116_model import build_model
from validation.adapter import TileConfig, Prediction, canonical_tile_config, predict_canonical_tiled
from validation.interventions import InterventionWrapper, MODES


def load_model(checkpoint: str | None, device: torch.device):
    if not checkpoint:
        raise ValueError("R116 intervention adapter requires a checkpoint")
    mode = os.environ.get("R116_INTERVENTION_MODE", "")
    if mode not in MODES:
        raise ValueError(f"R116_INTERVENTION_MODE must be one of {MODES}")
    path = Path(checkpoint)
    saved = torch.load(path, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True or saved.get("checkpoint_loaded") is not False:
        raise RuntimeError("R116 intervention validation requires a clean scratch checkpoint")
    model = build_model()
    model.load_state_dict(saved["model"], strict=True)
    model.requires_grad_(False)
    return InterventionWrapper(model.to(device).eval(), mode)
