"""Read-only R114D adapter for canonical tiled and locked ACM evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any, Mapping

import torch


PROBE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PROBE_ROOT.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from inference.tiled_runtime import TileConfig, TiledPrediction, predict_tiled  # noqa: E402
from probes.r114d_action_selector.model import (  # noqa: E402
    R114DActionSelector,
    SelectorConfig,
    load_frozen_e24_proposal,
)


R114D_REQUIRED_MAPS = (
    "base_output",
    "proposal_output",
    "proposal_delta",
    "acceptance",
    "amount",
    "boundary_confidence",
    "correction_need",
    "recoverability",
    "profile_band",
    "causal_gate",
    "profile_gate",
    "selected_delta",
    "width_gate",
    "shift_gate",
    "profile_visibility",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_selector_checkpoint(payload: object, checkpoint: Path) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise RuntimeError(f"selector checkpoint is not a mapping: {checkpoint}")
    state = payload.get("selector")
    if not isinstance(state, Mapping):
        raise RuntimeError("selector checkpoint has no selector state mapping")
    if int(payload.get("epoch", 0)) < 1:
        raise RuntimeError("selector checkpoint has no valid completed epoch")
    if payload.get("optimizer_contains_proposal") is not False:
        raise RuntimeError("selector checkpoint does not prove proposal isolation")
    proposal = payload.get("proposal")
    if not isinstance(proposal, Mapping):
        raise RuntimeError("selector checkpoint has no frozen-proposal provenance")
    if int(proposal.get("epoch", -1)) != 24:
        raise RuntimeError("selector checkpoint is not pinned to R114C E24")
    return payload


def load_selector_model(
    checkpoint: str | Path,
    device: torch.device | str,
) -> R114DActionSelector:
    """Load only a completed selector state over the sealed E24 proposal."""

    checkpoint_path = Path(checkpoint).expanduser().resolve()
    if not checkpoint_path.is_file():
        raise FileNotFoundError(checkpoint_path)
    payload = _validate_selector_checkpoint(
        torch.load(checkpoint_path, map_location="cpu", weights_only=False),
        checkpoint_path,
    )
    proposal, proposal_metadata = load_frozen_e24_proposal(device=device)
    recorded = payload["proposal"]
    if str(recorded.get("checkpoint_sha256", "")).lower() != str(
        proposal_metadata["checkpoint_sha256"]
    ).lower():
        raise RuntimeError("selector checkpoint proposal hash differs from sealed E24")
    model = R114DActionSelector(proposal, SelectorConfig.from_json())
    incompatible = model.selector.load_state_dict(payload["selector"], strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise RuntimeError(f"strict selector load failed: {incompatible}")
    model.requires_grad_(False)
    model.to(device).eval()
    model.checkpoint_metadata = {
        "selector_checkpoint": str(checkpoint_path),
        "selector_checkpoint_sha256": _sha256(checkpoint_path),
        "selector_epoch": int(payload["epoch"]),
        "selector_run_id": str(payload.get("run_id", "")),
        "proposal": proposal_metadata,
    }
    return model


class R114DValidationWrapper(torch.nn.Module):
    """Expose R114D output plus selector and frozen-proposal diagnostics."""

    def __init__(self, model: R114DActionSelector):
        super().__init__()
        self.model = model
        self.minimum_halo_px = int(model.minimum_halo_px)
        self.checkpoint_metadata = getattr(model, "checkpoint_metadata", {})

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = image.clamp(0.0, 1.0)
        # Perform one frozen proposal pass, then reproduce the audited R114D
        # selector equation.  This avoids evaluating E24 twice per ACM tile.
        frozen = self.model.proposal.forward_details(raw)
        features = self.model._selector_features(raw, frozen)
        acceptance_logit, amount_logit, acceptance, amount = self.model.selector(features)
        causal_gate = (
            frozen.boundary_confidence
            * frozen.correction_need
            * frozen.recoverability
            * acceptance
            * amount
        )
        profile_gate = causal_gate * frozen.profile_band
        selected_delta = profile_gate * frozen.profile_proposal_delta
        output = (frozen.base_output + selected_delta).clamp(0.0, 1.0)
        return {
            "output": output,
            "base_output": frozen.base_output,
            "proposal_output": (
                frozen.base_output + frozen.profile_proposal_delta
            ).clamp(0.0, 1.0),
            "proposal_delta": frozen.profile_proposal_delta,
            "acceptance_logit": acceptance_logit,
            "amount_logit": amount_logit,
            "acceptance": acceptance,
            "amount": amount,
            "boundary_confidence": frozen.boundary_confidence,
            "correction_need": frozen.correction_need,
            "recoverability": frozen.recoverability,
            "uncertainty": frozen.uncertainty,
            "profile_band": frozen.profile_band,
            "causal_gate": causal_gate,
            "profile_gate": profile_gate,
            "selected_delta": selected_delta,
            "delta": output - raw,
            # Frozen geometry/profile maps retained for the existing locked
            # R73/R74 trace and causal inspection.
            "normalized_sdf": frozen.normalized_sdf,
            "normal_x": frozen.normal_x,
            "normal_y": frozen.normal_y,
            "width_reliability": frozen.width_reliability,
            "shift_reliability": frozen.shift_reliability,
            "geometry_gate": frozen.geometry_gate,
            "width_gate": frozen.width_gate,
            "shift_gate": frozen.shift_gate,
            "width_gain": frozen.width_gain,
            "normal_shift": frozen.normal_shift,
            "effective_width_gain": frozen.effective_width_gain,
            "effective_normal_shift": frozen.effective_normal_shift,
            "profile_visibility": frozen.profile_visibility,
            "predicted_sdf_px": frozen.predicted_sdf_px,
            "profile_proposal": frozen.profile_proposal,
            "profile_proposal_delta": frozen.profile_proposal_delta,
            "profile_delta": selected_delta,
            "proposal_profile_gate": frozen.profile_gate,
        }


def load_model(checkpoint: str | None, device: torch.device) -> torch.nn.Module:
    """Entry point compatible with shared and locked validation runners."""

    if not checkpoint:
        raise ValueError("R114D validation requires a selector checkpoint")
    return R114DValidationWrapper(load_selector_model(checkpoint, device))


def canonical_tile_config(
    model: torch.nn.Module,
    *,
    core: int = 768,
    halo: int | None = None,
) -> TileConfig:
    required_halo = int(getattr(model, "minimum_halo_px", 0))
    selected_halo = required_halo if halo is None else int(halo)
    if selected_halo < required_halo:
        raise ValueError(
            f"canonical halo {selected_halo} is smaller than required {required_halo}"
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
    selected = config or canonical_tile_config(model)
    required_halo = int(getattr(model, "minimum_halo_px", 0))
    if selected.halo < required_halo:
        raise ValueError(
            f"tile halo {selected.halo} is smaller than model requirement {required_halo}"
        )
    prediction = predict_tiled(model, image, selected)
    missing = sorted(set(R114D_REQUIRED_MAPS) - set(prediction.maps))
    if missing:
        raise RuntimeError(f"canonical R114D prediction is missing maps: {missing}")
    tensors = {"output": prediction.output, **prediction.maps}
    nonfinite = sorted(
        name for name, value in tensors.items() if not bool(torch.isfinite(value).all())
    )
    if nonfinite:
        raise RuntimeError(f"canonical R114D prediction has non-finite maps: {nonfinite}")
    return prediction
