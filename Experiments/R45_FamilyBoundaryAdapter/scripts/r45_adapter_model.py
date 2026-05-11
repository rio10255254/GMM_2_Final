"""R45 family-routed residual adapter.

The base model stays frozen.  Small residual adapters are activated only for
the feature families that R44 diagnostics identified as weak.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import torch
from torch import nn


REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "Model"

STAGE_TO_FAMILY = {
    "stage_41_motion_lines": "thin_lines",
    "stage_42_motion_grids": "grids",
    "stage_43_motion_junctions": "junctions",
    "stage_44_motion_curves": "curves",
    "stage_45_motion_regions": "large_regions",
    "stage_46_motion_defects": "defects",
    "stage_47_motion_mixed": "mixed_fields",
}


def family_from_stage(stage: str) -> str:
    stage = str(stage).strip()
    if stage not in STAGE_TO_FAMILY:
        raise ValueError(f"unknown R44/R45 motion stage: {stage}")
    return STAGE_TO_FAMILY[stage]


@dataclass(frozen=True)
class FamilyAdapterConfig:
    target_families: tuple[str, ...] = ("large_regions", "mixed_fields")
    input_channels: int = 2
    hidden_channels: int = 16
    num_blocks: int = 3
    residual_scale: float = 0.18

    @classmethod
    def from_dict(cls, data: dict) -> "FamilyAdapterConfig":
        payload = dict(data)
        payload["target_families"] = tuple(payload.get("target_families", cls.target_families))
        return cls(**payload)

    def to_json_dict(self) -> dict:
        payload = asdict(self)
        payload["target_families"] = list(self.target_families)
        return payload


class ResidualAdapter(nn.Module):
    def __init__(self, cfg: FamilyAdapterConfig):
        super().__init__()
        layers: list[nn.Module] = [
            nn.Conv2d(int(cfg.input_channels), int(cfg.hidden_channels), kernel_size=3, padding=1),
            nn.GELU(),
        ]
        for _ in range(max(0, int(cfg.num_blocks) - 1)):
            layers.extend(
                [
                    nn.Conv2d(int(cfg.hidden_channels), int(cfg.hidden_channels), kernel_size=3, padding=1),
                    nn.GELU(),
                ]
            )
        final = nn.Conv2d(int(cfg.hidden_channels), 1, kernel_size=3, padding=1)
        nn.init.zeros_(final.weight)
        nn.init.zeros_(final.bias)
        layers.append(final)
        self.net = nn.Sequential(*layers)

    def forward(self, src: torch.Tensor, base_pred: torch.Tensor) -> torch.Tensor:
        x = torch.cat([src, base_pred], dim=1)
        return self.net(x)


class FamilyAdapterWrapper(nn.Module):
    def __init__(self, base_model: nn.Module, cfg: FamilyAdapterConfig):
        super().__init__()
        self.base_model = base_model
        self.cfg = cfg
        for p in self.base_model.parameters():
            p.requires_grad_(False)
        self.base_model.eval()
        self.adapters = nn.ModuleDict({family: ResidualAdapter(cfg) for family in cfg.target_families})

    def base_predict(self, src: torch.Tensor) -> torch.Tensor:
        was_training = self.base_model.training
        self.base_model.eval()
        with torch.no_grad():
            pred = self.base_model(src).clamp(0.0, 1.0)
        if was_training:
            self.base_model.eval()
        return pred

    def adapt(self, src: torch.Tensor, base_pred: torch.Tensor, family: str) -> torch.Tensor:
        family = str(family)
        if family not in self.adapters:
            return base_pred
        residual = torch.tanh(self.adapters[family](src, base_pred)) * float(self.cfg.residual_scale)
        return (base_pred + residual).clamp(0.0, 1.0)

    def adapt_with_families(self, src: torch.Tensor, base_pred: torch.Tensor, families: Sequence[str]) -> torch.Tensor:
        if len(families) != int(src.shape[0]):
            raise ValueError(f"family count mismatch: {len(families)} vs batch {src.shape[0]}")
        out = base_pred.clone()
        for family in sorted(set(str(f) for f in families)):
            if family not in self.adapters:
                continue
            idx = [i for i, item in enumerate(families) if str(item) == family]
            if not idx:
                continue
            index = torch.as_tensor(idx, device=src.device, dtype=torch.long)
            out[index] = self.adapt(src.index_select(0, index), base_pred.index_select(0, index), family)
        return out

    def forward(self, src: torch.Tensor, family: str = "") -> torch.Tensor:
        base_pred = self.base_predict(src)
        return self.adapt(src, base_pred, family)

    def forward_with_families(self, src: torch.Tensor, families: Sequence[str]) -> torch.Tensor:
        base_pred = self.base_predict(src)
        return self.adapt_with_families(src, base_pred, families)


def load_frozen_base_model(checkpoint_path: str | Path, device: str | torch.device) -> nn.Module:
    if str(MODEL_DIR) not in sys.path:
        sys.path.insert(0, str(MODEL_DIR))
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    device = torch.device(device)
    trainer.CFG.DEVICE = str(device)
    model = trainer._build_model_from_cfg()
    trainer.load_ckpt(str(checkpoint_path), model, optimizer=None, ema_model=None)
    model.to(device)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model


def build_wrapper_from_checkpoint(
    *,
    base_checkpoint: str | Path,
    adapter_checkpoint: str | Path | None,
    device: str | torch.device,
    cfg: FamilyAdapterConfig | None = None,
) -> FamilyAdapterWrapper:
    device = torch.device(device)
    if adapter_checkpoint is not None:
        payload = load_adapter_checkpoint(adapter_checkpoint)
        cfg = FamilyAdapterConfig.from_dict(payload["config"])
        base_checkpoint = payload.get("base_checkpoint", str(base_checkpoint))
    if cfg is None:
        cfg = FamilyAdapterConfig()
    base_model = load_frozen_base_model(base_checkpoint, device)
    wrapper = FamilyAdapterWrapper(base_model, cfg).to(device)
    if adapter_checkpoint is not None:
        wrapper.adapters.load_state_dict(payload["adapters"], strict=True)
    return wrapper


def save_adapter_checkpoint(
    path: str | Path,
    *,
    wrapper: FamilyAdapterWrapper,
    base_checkpoint: str | Path,
    history: list[dict],
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "r45_family_boundary_adapter_v1",
        "base_checkpoint": str(base_checkpoint),
        "config": wrapper.cfg.to_json_dict(),
        "adapters": wrapper.adapters.state_dict(),
        "history": history,
    }
    torch.save(payload, path)
    meta_path = path.with_suffix(path.suffix + ".json")
    meta = {k: v for k, v in payload.items() if k != "adapters"}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_adapter_checkpoint(path: str | Path) -> dict:
    return torch.load(Path(path), map_location="cpu")
