"""Validation adapter for the scratch-only R114 split-profile model.

The adapter is intentionally inference-only.  It exposes the same
``load_model(checkpoint, device)`` entry point consumed by
``validation/run_validation.py`` and a small canonical-tiled helper for
standalone callers.  All spatial diagnostics are returned with the
reconstruction so the shared tiled runtime stitches every map with the exact
same grid as the output image.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "inference") not in sys.path:
    sys.path.insert(0, str(ROOT / "inference"))

from inference.tiled_runtime import TileConfig, TiledPrediction, predict_tiled
from model.r114_split_profile_model import build_split_profile_model


# These are the maps that must be present before a split-profile result is
# considered inspectable.  The wrapper returns additional intermediate maps as
# well, but validation should not silently pass without the independent width,
# shift, and bounded-profile controls that distinguish this model.
SPLIT_PROFILE_REQUIRED_MAPS = (
    "normalized_sdf",
    "normal_x",
    "normal_y",
    "boundary_confidence",
    "correction_need",
    "recoverability",
    "uncertainty",
    "width_reliability",
    "shift_reliability",
    "geometry_gate",
    "width_gate",
    "shift_gate",
    "width_gain",
    "normal_shift",
    "effective_width_gain",
    "effective_normal_shift",
    "profile_midpoint_cue",
    "midpoint_offset",
    "profile_midpoint",
    "signed_plateau_contrast",
    "profile_width",
    "profile_visibility",
    "predicted_sdf_px",
    "profile_band",
    "profile_gate",
    "profile_proposal",
    "profile_proposal_delta",
    "profile_delta",
)


class SplitProfileValidationWrapper(torch.nn.Module):
    """Return reconstruction plus every causal inspection map."""

    def __init__(self, model: torch.nn.Module):
        super().__init__()
        self.model = model
        self.minimum_halo_px = int(model.minimum_halo_px)

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        details = self.model.forward_details(image)
        return {
            "output": details.output,
            # Reconstruction stages and final change.
            "base_output": details.base_output,
            "shifted_base": details.shifted_base,
            "width_proposal": details.width_proposal,
            "profile_output": details.profile_output,
            "delta": details.delta,
            # Boundary geometry and evidence.
            "normalized_sdf": details.normalized_sdf,
            "normal_x": details.normal_x,
            "normal_y": details.normal_y,
            "boundary_confidence": details.boundary_confidence,
            "correction_need": details.correction_need,
            "recoverability": details.recoverability,
            "uncertainty": details.uncertainty,
            # Independent reliability and geometry controls.
            "width_reliability": details.width_reliability,
            "shift_reliability": details.shift_reliability,
            "geometry_gate": details.geometry_gate,
            "width_gate": details.width_gate,
            "shift_gate": details.shift_gate,
            "width_gain": details.width_gain,
            "normal_shift": details.normal_shift,
            "effective_width_gain": details.effective_width_gain,
            "effective_normal_shift": details.effective_normal_shift,
            # Bounded analytic profile controls and action.
            "profile_midpoint_cue": details.profile_midpoint_cue,
            "midpoint_offset": details.midpoint_offset,
            "profile_midpoint": details.profile_midpoint,
            "signed_plateau_contrast": details.signed_plateau_contrast,
            "profile_width": details.profile_width,
            "profile_visibility": details.profile_visibility,
            "predicted_sdf_px": details.predicted_sdf_px,
            "profile_band": details.profile_band,
            "profile_gate": details.profile_gate,
            "profile_proposal": details.profile_proposal,
            "profile_proposal_delta": details.profile_proposal_delta,
            "profile_delta": details.profile_delta,
        }


def _validate_checkpoint_payload(payload: object, checkpoint: Path) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise RuntimeError(f"checkpoint is not a mapping: {checkpoint}")
    if payload.get("scratch") is not True:
        raise RuntimeError("checkpoint violates the R114 scratch-only contract")
    if payload.get("foreign_checkpoint_loaded") is not False:
        raise RuntimeError("checkpoint records a foreign checkpoint load")
    if payload.get("resume_supported") is not False:
        raise RuntimeError("checkpoint does not record the no-resume split-profile contract")
    state = payload.get("model")
    if not isinstance(state, Mapping):
        raise RuntimeError("checkpoint does not contain a model state mapping")
    required_state_keys = {
        "controller.width_reliability_head.weight",
        "controller.shift_reliability_head.weight",
        "profile_midpoint_offset_head.weight",
        "profile_visibility_head.weight",
    }
    missing = sorted(required_state_keys - set(state))
    if missing:
        raise RuntimeError(f"checkpoint is not an R114 split-profile model; missing {missing}")
    return payload


def load_model(checkpoint: str | None, device: torch.device) -> torch.nn.Module:
    """Load a frozen split-profile checkpoint and enforce its provenance."""

    if not checkpoint:
        raise ValueError("R114 split-profile validation requires a checkpoint")
    checkpoint_path = Path(checkpoint).expanduser().resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(checkpoint_path)
    payload = _validate_checkpoint_payload(
        torch.load(checkpoint_path, map_location="cpu"), checkpoint_path
    )
    model = build_split_profile_model()
    model.load_state_dict(payload["model"], strict=True)
    model.requires_grad_(False)
    return SplitProfileValidationWrapper(model.to(device).eval())


def canonical_tile_config(
    model: torch.nn.Module,
    *,
    core: int = 768,
    halo: int | None = None,
) -> TileConfig:
    """Build the unshifted deployment grid used as canonical reconstruction."""

    required_halo = int(getattr(model, "minimum_halo_px", 0))
    selected_halo = required_halo if halo is None else int(halo)
    if selected_halo < required_halo:
        raise ValueError(
            f"canonical halo {selected_halo} is smaller than model requirement {required_halo}"
        )
    return TileConfig(
        name="canonical_grid_a",
        core=int(core),
        halo=selected_halo,
        overlap=0,
        origin_y=0,
        origin_x=0,
    )


@torch.inference_mode()
def predict_canonical_tiled(
    model: torch.nn.Module,
    image: torch.Tensor,
    config: TileConfig | None = None,
) -> TiledPrediction:
    """Run the canonical tiled policy and verify all required diagnostics."""

    selected = config or canonical_tile_config(model)
    required_halo = int(getattr(model, "minimum_halo_px", 0))
    if selected.halo < required_halo:
        raise ValueError(
            f"tile halo {selected.halo} is smaller than model requirement {required_halo}"
        )
    prediction = predict_tiled(model, image, selected)
    missing = sorted(set(SPLIT_PROFILE_REQUIRED_MAPS) - set(prediction.maps))
    if missing:
        raise RuntimeError(f"canonical prediction is missing required maps: {missing}")
    tensors = {"output": prediction.output, **prediction.maps}
    nonfinite = sorted(name for name, value in tensors.items() if not bool(torch.isfinite(value).all()))
    if nonfinite:
        raise RuntimeError(f"canonical prediction contains non-finite tensors: {nonfinite}")
    return prediction

