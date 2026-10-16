"""Frozen R114C-E24 proposal plus a new local causal action selector.

Inference accepts only one image.  Targets never enter this module.  The
sealed E24 model supplies a geometry base and one bounded learned profile
proposal.  The new selector may only decide whether to accept that proposal
and how much of it to apply.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import torch
from torch import nn
import torch.nn.functional as F


PROBE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PROBE_ROOT.parents[1]

# Import the audited proposal architecture, but do not edit or subclass its
# implementation.  The proposal object is frozen immediately after loading.
from model.r114_model import LocalConv2d  # noqa: E402
from model.r114_split_profile_model import (  # noqa: E402
    R114SplitProfileModel,
    SplitReconstructionOutput,
    build_split_profile_model,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SelectorConfig:
    channels: int = 24
    dilations: tuple[int, ...] = (1, 2, 4, 2, 1)

    def __post_init__(self) -> None:
        if self.channels < 4:
            raise ValueError("selector channels must be at least 4")
        if not self.dilations or any(int(value) < 1 for value in self.dilations):
            raise ValueError("selector dilations must contain positive integers")

    @property
    def receptive_field_radius_px(self) -> int:
        # One radius from the stem and two dilated 3x3 convolutions per block.
        return 1 + 2 * sum(int(value) for value in self.dilations)

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "SelectorConfig":
        source = Path(path) if path is not None else PROBE_ROOT / "config.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        return cls(
            channels=int(payload["selector_channels"]),
            dilations=tuple(int(value) for value in payload["selector_dilations"]),
        )


class SelectorResidualBlock(nn.Module):
    """Strictly local residual block without spatial/global normalization."""

    def __init__(self, channels: int, dilation: int):
        super().__init__()
        self.first = LocalConv2d(channels, channels, 3, dilation=dilation)
        self.second = LocalConv2d(channels, channels, 3, dilation=dilation)
        self.scale = nn.Parameter(torch.tensor(0.10, dtype=torch.float32))

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        residual = self.second(F.silu(self.first(value)))
        return value + torch.tanh(self.scale) * residual


class LocalSelectorHead(nn.Module):
    """Predict acceptance and amount from inference-safe frozen features.

    Both terminal heads are initialized to exact zero.  The bounded positive
    mapping therefore yields exact zero everywhere at initialization while
    retaining a positive one-sided derivative.  During training, acceptance
    is calibrated with its raw logit and amount with its bounded output.
    """

    input_channels = 10

    def __init__(self, config: SelectorConfig):
        super().__init__()
        self.config = config
        self.stem = LocalConv2d(self.input_channels, config.channels, 3)
        self.blocks = nn.Sequential(
            *[SelectorResidualBlock(config.channels, value) for value in config.dilations]
        )
        self.acceptance_head = nn.Conv2d(config.channels, 1, 1)
        self.amount_head = nn.Conv2d(config.channels, 1, 1)
        self._initialize()

    def _initialize(self) -> None:
        for root in (self.stem, self.blocks):
            for module in root.modules():
                if isinstance(module, nn.Conv2d):
                    nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)
        nn.init.zeros_(self.acceptance_head.weight)
        nn.init.zeros_(self.acceptance_head.bias)
        nn.init.zeros_(self.amount_head.weight)
        nn.init.zeros_(self.amount_head.bias)

    @staticmethod
    def bounded_positive(logit: torch.Tensor) -> torch.Tensor:
        # softplus(0)-log(2) is exactly zero in FP32.  Clamp provides the
        # desired zero floor and a positive one-sided gradient at initialization.
        return torch.clamp(F.softplus(logit) - math.log(2.0), min=0.0, max=1.0)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, ...]:
        hidden = self.blocks(F.silu(self.stem(features)))
        acceptance_logit = self.acceptance_head(hidden)
        amount_logit = self.amount_head(hidden)
        acceptance = self.bounded_positive(acceptance_logit)
        amount = self.bounded_positive(amount_logit)
        return acceptance_logit, amount_logit, acceptance, amount


@dataclass(frozen=True)
class R114DOutput:
    output: torch.Tensor
    base_output: torch.Tensor
    proposal_output: torch.Tensor
    proposal_delta: torch.Tensor
    acceptance_logit: torch.Tensor
    amount_logit: torch.Tensor
    acceptance: torch.Tensor
    amount: torch.Tensor
    boundary_confidence: torch.Tensor
    correction_need: torch.Tensor
    recoverability: torch.Tensor
    profile_band: torch.Tensor
    causal_gate: torch.Tensor
    profile_gate: torch.Tensor
    selected_delta: torch.Tensor


def load_frozen_e24_proposal(
    checkpoint_path: str | Path | None = None,
    config_path: str | Path | None = None,
    device: str | torch.device = "cpu",
) -> tuple[R114SplitProfileModel, dict[str, Any]]:
    """Strictly load and freeze the sealed R114C E24 proposal checkpoint."""

    config_source = Path(config_path) if config_path is not None else PROBE_ROOT / "config.json"
    payload = json.loads(config_source.read_text(encoding="utf-8"))
    checkpoint = Path(checkpoint_path or payload["proposal_checkpoint"])
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    actual_hash = _sha256(checkpoint)
    expected_hash = str(payload["proposal_checkpoint_sha256"]).lower()
    if actual_hash != expected_hash:
        raise RuntimeError(
            f"sealed E24 checkpoint hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    required_epoch = int(payload["required_proposal_epoch"])
    if int(saved.get("epoch", -1)) != required_epoch:
        raise RuntimeError(
            f"proposal checkpoint must be epoch {required_epoch}, got {saved.get('epoch')}"
        )
    proposal = build_split_profile_model()
    incompatible = proposal.load_state_dict(saved["model"], strict=True)
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise RuntimeError(f"strict proposal load failed: {incompatible}")
    proposal.requires_grad_(False)
    proposal.eval()
    proposal.to(device)
    metadata = {
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": actual_hash,
        "epoch": required_epoch,
        "source_run_id": saved.get("run_id"),
        "source_stage": saved.get("stage"),
        "proposal_parameters": sum(parameter.numel() for parameter in proposal.parameters()),
        "proposal_trainable_parameters": sum(
            parameter.numel() for parameter in proposal.parameters() if parameter.requires_grad
        ),
    }
    return proposal, metadata


class R114DActionSelector(nn.Module):
    """Apply only a selected fraction of the frozen learned E24 proposal."""

    def __init__(
        self,
        proposal: R114SplitProfileModel,
        config: SelectorConfig | None = None,
    ):
        super().__init__()
        self.proposal = proposal
        self.proposal.requires_grad_(False)
        self.proposal.eval()
        self.selector_config = config or SelectorConfig.from_json()
        self.selector = LocalSelectorHead(self.selector_config)

    def train(self, mode: bool = True) -> "R114DActionSelector":
        super().train(mode)
        # nn.Module.train recursively toggles children; restore the sealed
        # proposal to eval after every call.
        self.proposal.eval()
        return self

    @property
    def minimum_halo_px(self) -> int:
        return self.proposal.minimum_halo_px + self.selector_config.receptive_field_radius_px

    def selector_parameters(self) -> list[nn.Parameter]:
        return list(self.selector.parameters())

    @staticmethod
    def _selector_features(raw: torch.Tensor, details: SplitReconstructionOutput) -> torch.Tensor:
        return torch.cat(
            [
                raw,
                details.base_output,
                details.profile_proposal_delta,
                details.boundary_confidence,
                details.correction_need,
                details.recoverability,
                details.uncertainty,
                details.profile_band,
                details.profile_visibility,
                torch.tanh(details.normalized_sdf),
            ],
            dim=1,
        ).detach()

    def forward_details(self, value: torch.Tensor) -> R114DOutput:
        if value.ndim != 4 or value.shape[1] != 1:
            raise ValueError("expected input shape [batch, 1, height, width]")
        if not value.is_floating_point():
            raise TypeError("R114D input must be floating point")
        raw = value.clamp(0.0, 1.0)
        # The proposal is always frozen, including when the wrapper is in train
        # mode.  No graph or target-dependent value can enter this branch.
        with torch.no_grad():
            frozen = self.proposal.forward_details(raw)
        features = self._selector_features(raw, frozen)
        acceptance_logit, amount_logit, acceptance, amount = self.selector(features)
        boundary = frozen.boundary_confidence.detach()
        need = frozen.correction_need.detach()
        recoverability = frozen.recoverability.detach()
        band = frozen.profile_band.detach()
        proposal_delta = frozen.profile_proposal_delta.detach()
        causal_gate = boundary * need * recoverability * acceptance * amount
        profile_gate = causal_gate * band
        selected_delta = profile_gate * proposal_delta
        base = frozen.base_output.detach()
        output = (base + selected_delta).clamp(0.0, 1.0)
        proposal_output = (base + proposal_delta).clamp(0.0, 1.0)
        return R114DOutput(
            output=output,
            base_output=base,
            proposal_output=proposal_output,
            proposal_delta=proposal_delta,
            acceptance_logit=acceptance_logit,
            amount_logit=amount_logit,
            acceptance=acceptance,
            amount=amount,
            boundary_confidence=boundary,
            correction_need=need,
            recoverability=recoverability,
            profile_band=band,
            causal_gate=causal_gate,
            profile_gate=profile_gate,
            selected_delta=selected_delta,
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.forward_details(value).output


def forward_tiled_selector(
    model: R114DActionSelector,
    value: torch.Tensor,
    core_size: int,
    halo: int | None = None,
) -> R114DOutput:
    """Stitch selector outputs using enough halo for proposal plus selector."""

    if value.ndim != 4 or value.shape[1] != 1:
        raise ValueError("expected input shape [batch, 1, height, width]")
    if core_size < 1:
        raise ValueError("core_size must be positive")
    actual_halo = model.minimum_halo_px if halo is None else int(halo)
    if actual_halo < model.minimum_halo_px:
        raise ValueError(
            f"halo {actual_halo} is smaller than required {model.minimum_halo_px}"
        )
    height, width = value.shape[-2:]
    canvases: dict[str, torch.Tensor] = {}
    for y0 in range(0, height, core_size):
        y1 = min(y0 + core_size, height)
        tile_y0, tile_y1 = max(0, y0 - actual_halo), min(height, y1 + actual_halo)
        for x0 in range(0, width, core_size):
            x1 = min(x0 + core_size, width)
            tile_x0, tile_x1 = max(0, x0 - actual_halo), min(width, x1 + actual_halo)
            tile = model.forward_details(value[..., tile_y0:tile_y1, tile_x0:tile_x1])
            for item in fields(tile):
                name = item.name
                tensor = getattr(tile, name)
                if name not in canvases:
                    canvases[name] = tensor.new_empty(
                        tensor.shape[0], tensor.shape[1], height, width
                    )
                cy0, cy1 = y0 - tile_y0, y1 - tile_y0
                cx0, cx1 = x0 - tile_x0, x1 - tile_x0
                canvases[name][..., y0:y1, x0:x1] = tensor[..., cy0:cy1, cx0:cx1]
    return R114DOutput(**canvases)


def parameter_counts(model: R114DActionSelector) -> dict[str, int]:
    return {
        "proposal_total": sum(parameter.numel() for parameter in model.proposal.parameters()),
        "proposal_trainable": sum(
            parameter.numel() for parameter in model.proposal.parameters() if parameter.requires_grad
        ),
        "selector_total": sum(parameter.numel() for parameter in model.selector.parameters()),
        "selector_trainable": sum(
            parameter.numel() for parameter in model.selector.parameters() if parameter.requires_grad
        ),
    }
