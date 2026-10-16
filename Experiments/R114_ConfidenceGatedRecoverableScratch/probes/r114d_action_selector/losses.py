"""Balanced, boundary-only objectives for the R114D selector."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import torch
import torch.nn.functional as F

from .model import PROBE_ROOT, R114DOutput
from .targets import SelectorTargets


@dataclass(frozen=True)
class LossConfig:
    positive_acceptance_weight: float = 1.0
    negative_acceptance_weight: float = 3.0
    positive_amount_weight: float = 1.0
    negative_amount_weight: float = 1.5
    false_positive_product_weight: float = 2.0

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "LossConfig":
        source = Path(path) if path is not None else PROBE_ROOT / "config.json"
        payload = json.loads(source.read_text(encoding="utf-8"))["loss"]
        return cls(**{key: float(value) for key, value in payload.items()})


@dataclass(frozen=True)
class SelectorLosses:
    total: torch.Tensor
    acceptance_positive: torch.Tensor
    acceptance_negative: torch.Tensor
    amount_positive: torch.Tensor
    amount_negative: torch.Tensor
    false_positive_product: torch.Tensor
    positive_count: torch.Tensor
    negative_count: torch.Tensor


def _masked_mean(value: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weight = mask.to(dtype=value.dtype)
    return (value * weight).sum() / weight.sum().clamp_min(1.0)


def selector_loss(
    prediction: R114DOutput,
    targets: SelectorTargets,
    config: LossConfig | None = None,
) -> SelectorLosses:
    """Class-balanced loss; background pixels never enter any reduction."""

    selected = config or LossConfig.from_json()
    positive = targets.positive_mask
    negative = targets.negative_mask
    acceptance_positive = _masked_mean(
        F.softplus(-prediction.acceptance_logit), positive
    )
    acceptance_negative = _masked_mean(
        F.softplus(prediction.acceptance_logit), negative
    )
    amount_positive = _masked_mean(
        F.smooth_l1_loss(
            prediction.amount,
            targets.amount,
            reduction="none",
            beta=0.05,
        ),
        positive,
    )
    amount_negative = _masked_mean(prediction.amount.square(), negative)
    false_positive_product = _masked_mean(
        prediction.acceptance * prediction.amount,
        negative,
    )
    total = (
        selected.positive_acceptance_weight * acceptance_positive
        + selected.negative_acceptance_weight * acceptance_negative
        + selected.positive_amount_weight * amount_positive
        + selected.negative_amount_weight * amount_negative
        + selected.false_positive_product_weight * false_positive_product
    )
    return SelectorLosses(
        total=total,
        acceptance_positive=acceptance_positive,
        acceptance_negative=acceptance_negative,
        amount_positive=amount_positive,
        amount_negative=amount_negative,
        false_positive_product=false_positive_product,
        positive_count=positive.sum(),
        negative_count=negative.sum(),
    )
