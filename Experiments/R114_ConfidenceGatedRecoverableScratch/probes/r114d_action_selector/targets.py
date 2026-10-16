"""Online causal labels derived only from the current frozen learned proposal."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import torch

from .model import PROBE_ROOT, R114DOutput


@dataclass(frozen=True)
class TargetConfig:
    boundary_band_px: float = 12.0
    gain_margin_gray_squared: float = 0.25
    clear_error_gray: float = 1.0
    minimum_candidate_delta_gray: float = 0.25
    minimum_positive_alpha: float = 0.05
    identity_hard_negative_max_ratio_to_true_band: float = 1.0

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "TargetConfig":
        source = Path(path) if path is not None else PROBE_ROOT / "config.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        return cls(
            boundary_band_px=float(payload["boundary_band_px"]),
            gain_margin_gray_squared=float(payload["gain_margin_gray_squared"]),
            clear_error_gray=float(payload["clear_error_gray"]),
            minimum_candidate_delta_gray=float(payload["minimum_candidate_delta_gray"]),
            minimum_positive_alpha=float(payload["minimum_positive_alpha"]),
            identity_hard_negative_max_ratio_to_true_band=float(
                payload["identity_hard_negative_max_ratio_to_true_band"]
            ),
        )


@dataclass(frozen=True)
class SelectorTargets:
    acceptance: torch.Tensor
    amount: torch.Tensor
    signed_gain: torch.Tensor
    best_alpha: torch.Tensor
    candidate_delta: torch.Tensor
    boundary_band: torch.Tensor
    positive_mask: torch.Tensor
    harmful_negative_mask: torch.Tensor
    clear_negative_mask: torch.Tensor
    identity_negative_mask: torch.Tensor
    negative_mask: torch.Tensor
    supervision_mask: torch.Tensor


def build_selector_targets(
    frozen_output: R114DOutput,
    target: torch.Tensor,
    true_sdf_px: torch.Tensor,
    identity: torch.Tensor,
    config: TargetConfig | None = None,
) -> SelectorTargets:
    """Build per-step labels from E24's learned proposal versus clean truth.

    No oracle midpoint, contrast, width, visibility, or displacement parameter
    is computed here.  The only candidate direction is the proposal emitted by
    the frozen E24 model.  Ground truth is used solely to measure whether that
    fixed direction helps and to calculate its best scalar alpha.
    """

    selected = config or TargetConfig.from_json()
    if target.shape != frozen_output.base_output.shape:
        raise ValueError("target and frozen base shapes differ")
    if true_sdf_px.shape != target.shape:
        raise ValueError("true_sdf_px and target shapes differ")
    if identity.ndim != 1 or identity.shape[0] != target.shape[0]:
        raise ValueError("identity must have shape [batch]")

    base = frozen_output.base_output.detach()
    target = target.detach()
    candidate_delta = (
        frozen_output.boundary_confidence.detach()
        * frozen_output.correction_need.detach()
        * frozen_output.recoverability.detach()
        * frozen_output.profile_band.detach()
        * frozen_output.proposal_delta.detach()
    )
    base_residual = target - base
    denominator = candidate_delta.square().clamp_min((0.01 / 255.0) ** 2)
    best_alpha = (base_residual * candidate_delta / denominator).clamp(0.0, 1.0)
    best_candidate = (base + best_alpha * candidate_delta).clamp(0.0, 1.0)
    best_residual = target - best_candidate
    # Signed causal gain is measured at the best permitted amount.  A useful
    # proposal that would overshoot at alpha=1 therefore remains acceptable;
    # the amount target learns the smaller safe fraction.
    signed_gain = base_residual.square() - best_residual.square()

    boundary_band = true_sdf_px.detach().abs() <= selected.boundary_band_px
    gain_margin = selected.gain_margin_gray_squared / (255.0 ** 2)
    minimum_delta = selected.minimum_candidate_delta_gray / 255.0
    actionable = candidate_delta.abs() >= minimum_delta
    positive = (
        boundary_band
        & actionable
        & (signed_gain > gain_margin)
        & (best_alpha >= selected.minimum_positive_alpha)
    )
    # A non-positive directional derivative means no non-negative amount of
    # this frozen proposal can help.  It is a true causal hard negative.
    harmful = boundary_band & actionable & (base_residual * candidate_delta <= 0.0)
    clear = boundary_band & (base_residual.abs() <= selected.clear_error_gray / 255.0)
    identity_map = identity.to(device=target.device, dtype=torch.bool).view(-1, 1, 1, 1)
    # Identity edges inside the true band are always negatives.  Outside the
    # true band, admit only the strongest frozen-proposal risks and cap their
    # count by the scene's true-band size.  This catches hallucinated actions
    # without letting a full identity background dominate the loss.
    identity_negative = boundary_band & identity_map
    identity_outside = torch.zeros_like(boundary_band)
    risk = candidate_delta.abs()
    for batch_index in range(target.shape[0]):
        if not bool(identity[batch_index]):
            continue
        candidate = (
            ~boundary_band[batch_index]
            & (risk[batch_index] >= minimum_delta)
        )
        available = int(candidate.sum())
        true_band_count = int(boundary_band[batch_index].sum())
        maximum = int(
            max(1, round(
                true_band_count
                * selected.identity_hard_negative_max_ratio_to_true_band
            ))
        )
        count = min(available, maximum)
        if count <= 0:
            continue
        flat_risk = risk[batch_index].reshape(-1)
        flat_candidate = candidate.reshape(-1)
        indices = torch.nonzero(flat_candidate, as_tuple=False).flatten()
        chosen = indices[torch.topk(flat_risk[indices], k=count, sorted=False).indices]
        identity_outside[batch_index].view(-1)[chosen] = True
    identity_negative = identity_negative | identity_outside
    negative = (~positive) & (harmful | clear | identity_negative)
    supervision = positive | negative
    acceptance = positive.to(dtype=target.dtype)
    amount = torch.where(positive, best_alpha, torch.zeros_like(best_alpha))
    return SelectorTargets(
        acceptance=acceptance,
        amount=amount,
        signed_gain=signed_gain,
        best_alpha=best_alpha,
        candidate_delta=candidate_delta,
        boundary_band=boundary_band,
        positive_mask=positive,
        harmful_negative_mask=harmful & ~positive,
        clear_negative_mask=clear & ~positive,
        identity_negative_mask=identity_negative & ~positive,
        negative_mask=negative,
        supervision_mask=supervision,
    )
