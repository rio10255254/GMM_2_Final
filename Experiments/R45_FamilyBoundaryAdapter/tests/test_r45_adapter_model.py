import sys
from pathlib import Path

import torch
from torch import nn


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from r45_adapter_model import (  # noqa: E402
    FamilyAdapterConfig,
    FamilyAdapterWrapper,
    family_from_stage,
    save_adapter_checkpoint,
    load_adapter_checkpoint,
)


class TinyBase(nn.Module):
    def forward(self, x):
        return x * 0.5


def test_family_from_stage_maps_motion_targets():
    assert family_from_stage("stage_45_motion_regions") == "large_regions"
    assert family_from_stage("stage_47_motion_mixed") == "mixed_fields"
    assert family_from_stage("stage_42_motion_grids") == "grids"


def test_wrapper_keeps_non_target_family_identical():
    cfg = FamilyAdapterConfig(target_families=("large_regions",), residual_scale=0.25)
    wrapper = FamilyAdapterWrapper(TinyBase(), cfg)
    x = torch.rand(2, 1, 16, 16)
    y = wrapper(x, family="grids")
    assert torch.allclose(y, x * 0.5)


def test_wrapper_starts_as_base_for_target_family():
    cfg = FamilyAdapterConfig(target_families=("large_regions",), residual_scale=0.25)
    wrapper = FamilyAdapterWrapper(TinyBase(), cfg)
    x = torch.rand(2, 1, 16, 16)
    y = wrapper(x, family="large_regions")
    assert torch.allclose(y, x * 0.5)


def test_base_model_is_frozen_and_only_adapter_trains():
    cfg = FamilyAdapterConfig(target_families=("large_regions", "mixed_fields"), residual_scale=0.25)
    wrapper = FamilyAdapterWrapper(TinyBase(), cfg)
    assert all(not p.requires_grad for p in wrapper.base_model.parameters())
    adapter_params = [p for p in wrapper.adapters.parameters()]
    assert adapter_params
    assert all(p.requires_grad for p in adapter_params)


def test_adapter_checkpoint_roundtrip(tmp_path):
    cfg = FamilyAdapterConfig(target_families=("large_regions", "mixed_fields"), residual_scale=0.25, hidden_channels=8)
    wrapper = FamilyAdapterWrapper(TinyBase(), cfg)
    ckpt_path = tmp_path / "adapter.pth"
    save_adapter_checkpoint(
        ckpt_path,
        wrapper=wrapper,
        base_checkpoint="base.pth.tar",
        history=[{"epoch": 1, "loss": 0.5}],
    )
    loaded = load_adapter_checkpoint(ckpt_path)
    assert loaded["config"]["target_families"] == ["large_regions", "mixed_fields"]
    assert loaded["base_checkpoint"] == "base.pth.tar"
    assert loaded["history"][0]["epoch"] == 1
    assert "adapters" in loaded
