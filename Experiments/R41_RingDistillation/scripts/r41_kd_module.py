"""Small role-gated knowledge-distillation helpers for R41."""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn


ROLE_RING = 0
ROLE_SHAPE = 1
ROLE_MICRO = 2


def freeze_teacher(model: nn.Module) -> nn.Module:
    model.eval()
    for param in model.parameters():
        param.requires_grad_(False)
    return model


def _teacher_pred(teacher: nn.Module, src: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        return teacher(src).float().clamp(0.0, 1.0)


def role_gated_kd_loss(
    pred: torch.Tensor,
    src: torch.Tensor,
    role: torch.Tensor | None,
    *,
    teacher_combo: nn.Module | None,
    teacher_r40: nn.Module | None,
    weight_combo: float,
    weight_r40: float,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Return already-weighted KD loss and per-teacher weighted components."""
    zero = pred.new_tensor(0.0)
    parts = {"combo": zero, "r40": zero}
    if role is None:
        return zero, parts

    role = role.to(device=pred.device, dtype=torch.long).view(-1)
    pred01 = pred.float().clamp(0.0, 1.0)
    total = zero

    combo_w = float(weight_combo)
    if combo_w > 0.0 and teacher_combo is not None:
        mask = role == ROLE_RING
        if bool(mask.any().item()):
            target = _teacher_pred(teacher_combo, src[mask])
            parts["combo"] = pred.new_tensor(combo_w) * F.mse_loss(pred01[mask], target)
            total = total + parts["combo"]

    r40_w = float(weight_r40)
    if r40_w > 0.0 and teacher_r40 is not None:
        mask = role == ROLE_MICRO
        if bool(mask.any().item()):
            target = _teacher_pred(teacher_r40, src[mask])
            parts["r40"] = pred.new_tensor(r40_w) * F.mse_loss(pred01[mask], target)
            total = total + parts["r40"]

    return total, parts


def checkpoint_exists(path: str | Path) -> bool:
    return bool(str(path).strip()) and Path(path).is_file()
