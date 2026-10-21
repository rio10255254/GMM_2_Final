"""Direct staged target for the bounded detail arm.

The target is recomputed from the current detached base renderer output.  It is
not a free image residual: it goes through the same support, half-bound carrier,
and local high-pass projection as the deployed branch.
"""
from __future__ import annotations

import json
from pathlib import Path

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
SCFG = CONFIG["training"]["bounded_detail_supervision"]


@torch.no_grad()
def build_supervision_targets(model, details, target: torch.Tensor,
                              identity: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Return the exact bounded carrier and its deployed high-pass projection."""
    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"]) / 255.0
    half = .5 * bound
    residual = target.float() - details.base_output.detach().float()
    carrier = half * torch.tanh(residual / max(half, 1e-8)) * details.support.detach().float()
    projected = carrier - model.detail_projection(carrier)
    if bool(SCFG["identity_target_is_zero"]):
        carrier = carrier.clone(); projected = projected.clone()
        carrier[identity] = 0; projected[identity] = 0
    return carrier, projected


@torch.no_grad()
def build_supervision_target(model, details, target: torch.Tensor, identity: torch.Tensor) -> torch.Tensor:
    return build_supervision_targets(model, details, target, identity)[1]


def detail_supervision_loss(details, target_detail: torch.Tensor) -> torch.Tensor:
    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"]) / 255.0
    beta = float(SCFG["smooth_l1_beta_gray_levels"]) / 255.0
    target_need = (target_detail.detach().abs() / max(.15 * bound, 1e-8)).clamp(0, 1)
    weight = .12 + .88 * torch.maximum(details.support.detach(), target_need)
    value = F.smooth_l1_loss(details.detail, target_detail, beta=beta, reduction="none")
    return (value * weight).sum() / weight.sum().clamp_min(1e-8)


def carrier_supervision_loss(details, target_carrier: torch.Tensor) -> torch.Tensor:
    """Auxiliary parameterization loss; it does not alter the deployed output."""
    bound = float(CONFIG["model"]["detail"]["maximum_amplitude_gray_levels"]) / 255.0
    beta = float(SCFG["smooth_l1_beta_gray_levels"]) / 255.0
    target_need = (target_carrier.detach().abs() / max(.075 * bound, 1e-8)).clamp(0, 1)
    weight = .12 + .88 * torch.maximum(details.support.detach(), target_need)
    value = F.smooth_l1_loss(details.detail_carrier, target_carrier, beta=beta, reduction="none")
    return (value * weight).sum() / weight.sum().clamp_min(1e-8)


def renderer_epoch_weight(arm: str, renderer_epoch: int) -> float:
    if arm != SCFG["enabled_arm"]:
        return 0.0
    schedule = [float(value) for value in SCFG["renderer_epoch_weights"]]
    if renderer_epoch < 1 or renderer_epoch > len(schedule):
        raise ValueError(f"renderer_epoch {renderer_epoch} outside schedule 1..{len(schedule)}")
    return schedule[renderer_epoch - 1]


@torch.no_grad()
def supervision_statistics(details, target_detail: torch.Tensor) -> dict[str, float]:
    difference = details.detail - target_detail
    target_energy = float(target_detail.abs().mean().cpu()) * 255
    prediction_energy = float(details.detail.abs().mean().cpu()) * 255
    utilization = 0.0 if target_energy < .01 else prediction_energy / target_energy
    return {
        "detail_target_abs_mean_gray": target_energy,
        "detail_prediction_abs_mean_gray": prediction_energy,
        "detail_supervision_mae_gray": float(difference.abs().mean().cpu()) * 255,
        "detail_target_utilization_ratio": utilization,
    }
