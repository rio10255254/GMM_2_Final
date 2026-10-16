"""Frozen E20 geometry plus frozen E24 profile heads and a local selector."""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from model.r114_split_profile_model import (
    ProfileActionOutput,
    R114SplitProfileModel,
    SplitControllerOutput,
    SplitGeometryOutput,
    build_split_profile_model,
)
from probes.r114d_action_selector.model import LocalSelectorHead, SelectorConfig


PROBE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PROBE_ROOT.parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tensor_hash(module: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _load_sealed_model(
    checkpoint: Path,
    expected_hash: str,
    required_epoch: int,
    required_stage: str,
    role: str,
    device: torch.device | str,
) -> tuple[R114SplitProfileModel, dict[str, Any]]:
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    actual_hash = _sha256(checkpoint)
    if actual_hash.lower() != expected_hash.lower():
        raise RuntimeError(
            f"sealed {role} checkpoint hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if int(saved.get("epoch", -1)) != int(required_epoch):
        raise RuntimeError(f"{role} checkpoint epoch mismatch")
    if str(saved.get("stage", "")) != str(required_stage):
        raise RuntimeError(f"{role} checkpoint stage mismatch")
    model = build_split_profile_model()
    incompatible = model.load_state_dict(saved["model"], strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise RuntimeError(f"strict {role} load failed: {incompatible}")
    model.requires_grad_(False).eval().to(device)
    return model, {
        "role": role,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": actual_hash,
        "epoch": required_epoch,
        "stage": required_stage,
        "source_run_id": saved.get("run_id"),
        "state_sha256": _tensor_hash(model),
    }


def load_frozen_sources(
    config_path: str | Path | None = None,
    device: torch.device | str = "cpu",
) -> tuple[R114SplitProfileModel, R114SplitProfileModel, dict[str, Any]]:
    source = Path(config_path) if config_path is not None else PROBE_ROOT / "config.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    geometry, geometry_meta = _load_sealed_model(
        Path(payload["geometry_checkpoint"]),
        str(payload["geometry_checkpoint_sha256"]),
        int(payload["required_geometry_epoch"]),
        str(payload["required_geometry_stage"]),
        "E20_geometry",
        device,
    )
    profile, profile_meta = _load_sealed_model(
        Path(payload["profile_checkpoint"]),
        str(payload["profile_checkpoint_sha256"]),
        int(payload["required_profile_epoch"]),
        str(payload["required_profile_stage"]),
        "E24_profile_heads",
        device,
    )
    return geometry, profile, {"geometry": geometry_meta, "profile": profile_meta}


@dataclass(frozen=True)
class E24ProfileParameters:
    midpoint_offset: torch.Tensor
    signed_plateau_contrast: torch.Tensor
    profile_width: torch.Tensor
    profile_visibility: torch.Tensor


@dataclass(frozen=True)
class R114EOutput:
    output: torch.Tensor
    base_output: torch.Tensor
    shifted_base: torch.Tensor
    proposal_output: torch.Tensor
    proposal_delta: torch.Tensor
    candidate_delta: torch.Tensor
    selected_delta: torch.Tensor
    acceptance_logit: torch.Tensor
    amount_logit: torch.Tensor
    acceptance: torch.Tensor
    amount: torch.Tensor
    causal_gate: torch.Tensor
    profile_gate: torch.Tensor
    boundary_confidence: torch.Tensor
    correction_need: torch.Tensor
    recoverability: torch.Tensor
    uncertainty: torch.Tensor
    normalized_sdf: torch.Tensor
    normal_x: torch.Tensor
    normal_y: torch.Tensor
    width_reliability: torch.Tensor
    shift_reliability: torch.Tensor
    geometry_gate: torch.Tensor
    width_gate: torch.Tensor
    shift_gate: torch.Tensor
    width_gain: torch.Tensor
    normal_shift: torch.Tensor
    effective_width_gain: torch.Tensor
    effective_normal_shift: torch.Tensor
    profile_midpoint_cue: torch.Tensor
    midpoint_offset: torch.Tensor
    profile_midpoint: torch.Tensor
    signed_plateau_contrast: torch.Tensor
    profile_width: torch.Tensor
    profile_visibility: torch.Tensor
    predicted_sdf_px: torch.Tensor
    profile_band: torch.Tensor
    profile_proposal: torch.Tensor


class R114EDecoupledHybrid(torch.nn.Module):
    """Apply E24 profile proposals exclusively on the sealed E20 geometry base."""

    def __init__(
        self,
        geometry_model: R114SplitProfileModel,
        profile_model: R114SplitProfileModel,
        selector_config: SelectorConfig | None = None,
        provenance: dict[str, Any] | None = None,
    ):
        super().__init__()
        self.geometry_model = geometry_model.requires_grad_(False).eval()
        self.profile_model = profile_model.requires_grad_(False).eval()
        self.selector_config = selector_config or SelectorConfig.from_json(PROBE_ROOT / "config.json")
        self.selector = LocalSelectorHead(self.selector_config)
        self.provenance = provenance or {}

    def train(self, mode: bool = True) -> "R114EDecoupledHybrid":
        super().train(mode)
        self.geometry_model.eval()
        self.profile_model.eval()
        return self

    @property
    def minimum_halo_px(self) -> int:
        return max(
            self.geometry_model.minimum_halo_px,
            self.profile_model.minimum_halo_px,
        ) + self.selector_config.receptive_field_radius_px

    def selector_parameters(self) -> list[torch.nn.Parameter]:
        return list(self.selector.parameters())

    @staticmethod
    def _geometry_only(
        model: R114SplitProfileModel,
        raw: torch.Tensor,
    ) -> tuple[SplitControllerOutput, SplitGeometryOutput]:
        controller = model.controller(raw)
        renderer_features = model._renderer_features(raw)
        with torch.autocast(device_type=raw.device.type, enabled=False):
            features = renderer_features.float()
            fraction = torch.sigmoid(model.width_head(features))
            width_gain = model.config.minimum_width_gain + (
                model.config.maximum_width_gain - model.config.minimum_width_gain
            ) * fraction
            normal_shift = model.config.maximum_normal_shift_px * torch.tanh(
                model.shift_head(features)
            )
        geometry = model.apply_geometry(
            raw.float(), controller, width_gain, normal_shift, features
        )
        return controller, geometry

    @staticmethod
    def _e24_profile_parameters(
        model: R114SplitProfileModel,
        raw: torch.Tensor,
    ) -> E24ProfileParameters:
        # Deliberately direct: E24 controller, width/shift heads, geometry,
        # base, and forward_details are never evaluated here.
        renderer_features = model._renderer_features(raw)
        with torch.autocast(device_type=raw.device.type, enabled=False):
            features = renderer_features.float()
            midpoint_offset = (
                model.config.maximum_midpoint_offset_gray_levels
                / 255.0
                * torch.tanh(model.profile_midpoint_offset_head(features))
            )
            signed_contrast = (
                model.config.maximum_signed_contrast_gray_levels
                / 255.0
                * torch.tanh(model.profile_signed_contrast_head(features))
            )
            width_fraction = torch.sigmoid(model.profile_width_head(features))
            profile_width = model.config.minimum_profile_width_px + (
                model.config.maximum_profile_width_px
                - model.config.minimum_profile_width_px
            ) * width_fraction
            visibility = model._bounded_profile_visibility(
                model.profile_visibility_head(features)
            )
        return E24ProfileParameters(
            midpoint_offset=midpoint_offset,
            signed_plateau_contrast=signed_contrast,
            profile_width=profile_width,
            profile_visibility=visibility,
        )

    @staticmethod
    def _selector_features(
        raw: torch.Tensor,
        geometry: SplitGeometryOutput,
        controller: SplitControllerOutput,
        profile: ProfileActionOutput,
    ) -> torch.Tensor:
        return torch.cat(
            [
                raw,
                geometry.base_output,
                profile.profile_proposal_delta,
                controller.boundary_confidence,
                controller.correction_need,
                controller.recoverability,
                controller.uncertainty,
                profile.profile_band,
                profile.profile_visibility,
                torch.tanh(controller.normalized_sdf),
            ],
            dim=1,
        ).detach()

    def forward_details(self, value: torch.Tensor) -> R114EOutput:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("expected input shape [batch, 1, height, width]")
        if not value.is_floating_point():
            raise TypeError("R114E input must be floating point")
        raw = value.clamp(0.0, 1.0)
        with torch.no_grad():
            controller, geometry = self._geometry_only(self.geometry_model, raw)
            parameters = self._e24_profile_parameters(self.profile_model, raw)
            # Use E24's analytic profile renderer, but feed it only the sealed
            # E20 geometry/base/controller tensors.  The renderer contains no
            # learned state; this explicit ownership keeps the causal contract
            # easy to audit.
            profile = self.profile_model.apply_profile_action(
                base_output=geometry.base_output,
                controller=controller,
                midpoint_offset=parameters.midpoint_offset,
                signed_plateau_contrast=parameters.signed_plateau_contrast,
                profile_width=parameters.profile_width,
                profile_visibility=parameters.profile_visibility,
                midpoint_source=geometry.shifted_base,
            )
        selector_features = self._selector_features(raw, geometry, controller, profile)
        acceptance_logit, amount_logit, acceptance, amount = self.selector(selector_features)
        boundary = controller.boundary_confidence.detach()
        need = controller.correction_need.detach()
        recoverability = controller.recoverability.detach()
        band = profile.profile_band.detach()
        proposal_delta = profile.profile_proposal_delta.detach()
        causal_gate = boundary * need * recoverability * acceptance * amount
        profile_gate = causal_gate * band
        candidate_delta = boundary * need * recoverability * band * proposal_delta
        selected_delta = acceptance * amount * candidate_delta
        base = geometry.base_output.detach()
        output = (base + selected_delta).clamp(0.0, 1.0)
        return R114EOutput(
            output=output,
            base_output=base,
            shifted_base=geometry.shifted_base.detach(),
            proposal_output=(base + candidate_delta).clamp(0.0, 1.0),
            proposal_delta=proposal_delta,
            candidate_delta=candidate_delta,
            selected_delta=selected_delta,
            acceptance_logit=acceptance_logit,
            amount_logit=amount_logit,
            acceptance=acceptance,
            amount=amount,
            causal_gate=causal_gate,
            profile_gate=profile_gate,
            boundary_confidence=boundary,
            correction_need=need,
            recoverability=recoverability,
            uncertainty=controller.uncertainty.detach(),
            normalized_sdf=controller.normalized_sdf.detach(),
            normal_x=controller.normal_x.detach(),
            normal_y=controller.normal_y.detach(),
            width_reliability=controller.width_reliability.detach(),
            shift_reliability=controller.shift_reliability.detach(),
            geometry_gate=geometry.geometry_gate.detach(),
            width_gate=geometry.width_gate.detach(),
            shift_gate=geometry.shift_gate.detach(),
            width_gain=geometry.width_gain.detach(),
            normal_shift=geometry.normal_shift.detach(),
            effective_width_gain=geometry.effective_width_gain.detach(),
            effective_normal_shift=geometry.effective_normal_shift.detach(),
            profile_midpoint_cue=profile.profile_midpoint_cue.detach(),
            midpoint_offset=parameters.midpoint_offset.detach(),
            profile_midpoint=profile.profile_midpoint.detach(),
            signed_plateau_contrast=parameters.signed_plateau_contrast.detach(),
            profile_width=parameters.profile_width.detach(),
            profile_visibility=parameters.profile_visibility.detach(),
            predicted_sdf_px=profile.predicted_sdf_px.detach(),
            profile_band=band,
            profile_proposal=profile.profile_proposal.detach(),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def build_hybrid(device: torch.device | str = "cpu") -> R114EDecoupledHybrid:
    geometry, profile, provenance = load_frozen_sources(device=device)
    return R114EDecoupledHybrid(
        geometry,
        profile,
        SelectorConfig.from_json(PROBE_ROOT / "config.json"),
        provenance,
    ).to(device)


def parameter_counts(model: R114EDecoupledHybrid) -> dict[str, int]:
    return {
        "e20_total": sum(p.numel() for p in model.geometry_model.parameters()),
        "e20_trainable": sum(p.numel() for p in model.geometry_model.parameters() if p.requires_grad),
        "e24_total": sum(p.numel() for p in model.profile_model.parameters()),
        "e24_trainable": sum(p.numel() for p in model.profile_model.parameters() if p.requires_grad),
        "selector_total": sum(p.numel() for p in model.selector.parameters()),
        "selector_trainable": sum(p.numel() for p in model.selector.parameters() if p.requires_grad),
    }


def source_state_hashes(model: R114EDecoupledHybrid) -> dict[str, str]:
    return {
        "geometry": _tensor_hash(model.geometry_model),
        "profile": _tensor_hash(model.profile_model),
    }
