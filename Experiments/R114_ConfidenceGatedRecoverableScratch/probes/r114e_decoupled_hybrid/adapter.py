"""Read-only R114E adapter for canonical tiled and locked ACM evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import torch

from inference.tiled_runtime import TileConfig, TiledPrediction, predict_tiled

from .model import PROBE_ROOT, R114EDecoupledHybrid, build_hybrid


REQUIRED_MAPS = (
    "base_output", "shifted_base", "proposal_output", "proposal_delta",
    "candidate_delta", "selected_delta", "acceptance", "amount",
    "boundary_confidence", "correction_need", "recoverability", "profile_band",
    "causal_gate", "profile_gate", "width_gate", "shift_gate", "profile_visibility",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_selector_model(checkpoint: str | Path, device: torch.device | str) -> R114EDecoupledHybrid:
    path = Path(checkpoint).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, Mapping) or not isinstance(payload.get("selector"), Mapping):
        raise RuntimeError("invalid R114E selector checkpoint")
    if int(payload.get("epoch", 0)) < 1:
        raise RuntimeError("R114E selector checkpoint has no completed epoch")
    if payload.get("optimizer_contains_sources") is not False:
        raise RuntimeError("R114E checkpoint does not prove source isolation")
    if payload.get("headroom_status") != "pass_headroom_gate":
        raise RuntimeError("R114E checkpoint lacks passing pre-training headroom evidence")
    model = build_hybrid(device)
    recorded = payload.get("source_provenance")
    if not isinstance(recorded, Mapping):
        raise RuntimeError("R114E checkpoint has no source provenance")
    for role in ("geometry", "profile"):
        if str(recorded[role]["checkpoint_sha256"]).lower() != str(
            model.provenance[role]["checkpoint_sha256"]
        ).lower():
            raise RuntimeError(f"R114E {role} source hash differs from sealed source")
    incompatible = model.selector.load_state_dict(payload["selector"], strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise RuntimeError(f"strict R114E selector load failed: {incompatible}")
    model.requires_grad_(False).to(device).eval()
    model.checkpoint_metadata = {
        "selector_checkpoint": str(path),
        "selector_checkpoint_sha256": _sha256(path),
        "selector_epoch": int(payload["epoch"]),
        "selector_run_id": str(payload.get("run_id", "")),
        "source_provenance": model.provenance,
    }
    return model


class R114EValidationWrapper(torch.nn.Module):
    def __init__(self, model: R114EDecoupledHybrid):
        super().__init__()
        self.model = model
        self.minimum_halo_px = int(model.minimum_halo_px)
        self.checkpoint_metadata = getattr(model, "checkpoint_metadata", {})

    def forward(self, image: torch.Tensor) -> dict[str, torch.Tensor]:
        raw = image.clamp(0.0, 1.0)
        details = self.model.forward_details(raw)
        maps = {name: getattr(details, name) for name in details.__dataclass_fields__}
        maps["delta"] = details.output - raw
        maps["profile_delta"] = details.selected_delta
        maps["profile_proposal_delta"] = details.proposal_delta
        maps["predicted_sdf_px"] = details.predicted_sdf_px
        return maps


def load_model(checkpoint: str | None, device: torch.device) -> torch.nn.Module:
    if not checkpoint:
        raise ValueError("R114E validation requires a selector checkpoint")
    return R114EValidationWrapper(load_selector_model(checkpoint, device))


def canonical_tile_config(model: torch.nn.Module, *, core: int = 768, halo: int | None = None) -> TileConfig:
    required = int(getattr(model, "minimum_halo_px", 0))
    selected = required if halo is None else int(halo)
    if selected < required:
        raise ValueError(f"canonical halo {selected} is smaller than required {required}")
    return TileConfig(
        name="canonical_grid_a", core=int(core), halo=selected, overlap=0,
        origin_y=0, origin_x=0,
    )


@torch.inference_mode()
def predict_canonical_tiled(
    model: torch.nn.Module,
    image: torch.Tensor,
    config: TileConfig | None = None,
) -> TiledPrediction:
    selected = config or canonical_tile_config(model)
    prediction = predict_tiled(model, image, selected)
    missing = sorted(set(REQUIRED_MAPS) - set(prediction.maps))
    if missing:
        raise RuntimeError(f"canonical R114E prediction is missing maps: {missing}")
    nonfinite = [
        name for name, value in {"output": prediction.output, **prediction.maps}.items()
        if not bool(torch.isfinite(value).all())
    ]
    if nonfinite:
        raise RuntimeError(f"canonical R114E prediction has non-finite maps: {nonfinite}")
    return prediction

