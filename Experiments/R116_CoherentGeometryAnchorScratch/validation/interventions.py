"""Inference-only causal interventions for the frozen R116 E42 checkpoint.

These operators are deliberately parameter free.  They isolate whether the
learned normal shift, the unconstrained detail parity, or contour-adjacent
texture is responsible for the remaining geometry errors.  They must never be
used as training initialization.
"""

from __future__ import annotations

import torch

from model.r116_model import warp_local


MODES = ("current", "no_shift", "center_locked", "guarded")


def _bounded_highpass(model, value: torch.Tensor) -> torch.Tensor:
    cap = float(model.config.maximum_detail_delta_gray) / 255.0
    value = value - model.lowpass(value)
    value = cap * torch.tanh(value / cap)
    value = value - model.lowpass(value)
    return value.clamp(-cap, cap)


def _antisymmetric_about_boundary(details, value: torch.Tensor) -> torch.Tensor:
    """Project a residual onto the odd component around the predicted contour."""
    sdf = details.predicted_sdf_px.clamp(-6.0, 6.0)
    reflection_flow = torch.cat(
        (-2.0 * sdf * details.normal_x, -2.0 * sdf * details.normal_y), dim=1,
    )
    reflected = warp_local(value, reflection_flow)
    odd = 0.5 * (value - reflected)
    # Projection is meaningful only in the boundary neighbourhood.  Outside it
    # retain evidence detail, because texture is not a boundary-coordinate cue.
    boundary_blend = torch.sigmoid((5.0 - details.predicted_sdf_px.abs()) / 0.75)
    return boundary_blend * odd + (1.0 - boundary_blend) * value


def output_for_mode(model, raw: torch.Tensor, details, mode: str) -> torch.Tensor:
    if mode not in MODES:
        raise ValueError(f"unknown R116 intervention: {mode}")
    if mode == "current":
        return details.output
    if mode == "no_shift":
        return (raw.float().clamp(0.0, 1.0) + details.bounded_detail).clamp(0.0, 1.0)
    if mode == "center_locked":
        projected = _bounded_highpass(
            model, _antisymmetric_about_boundary(details, details.bounded_detail),
        )
        return (details.geometry_anchor + projected).clamp(0.0, 1.0)

    # Remove evidence-basis texture close to the contour while retaining the
    # trained width action.  A soft guard avoids an artificial ring at the edge
    # of the protected band.
    distance = details.predicted_sdf_px.abs()
    texture_keep = torch.sigmoid((distance - 2.5) / 0.55)
    boundary_support = (
        details.width_gate / details.width_confidence.clamp_min(1.0e-4)
    ).clamp(0.0, 1.0)
    evidence_gate = (boundary_support * details.detail_confidence).clamp(0.0, 1.0)
    combined = details.width_zero_mean_detail + texture_keep * evidence_gate * details.evidence_detail
    projected = _bounded_highpass(model, _antisymmetric_about_boundary(details, combined))
    return (details.geometry_anchor + projected).clamp(0.0, 1.0)


class InterventionWrapper(torch.nn.Module):
    def __init__(self, model: torch.nn.Module, mode: str):
        super().__init__()
        if mode not in MODES:
            raise ValueError(f"unknown R116 intervention: {mode}")
        self.model = model
        self.mode = mode
        self.minimum_halo_px = model.minimum_halo_px

    def forward(self, value: torch.Tensor) -> dict[str, torch.Tensor]:
        details = self.model.forward_details(value)
        values = {name: getattr(details, name) for name in details.__dataclass_fields__}
        values["output"] = output_for_mode(self.model, value, details, self.mode)
        values["profile_visibility"] = torch.maximum(details.width_gate, details.shift_gate)
        return values
