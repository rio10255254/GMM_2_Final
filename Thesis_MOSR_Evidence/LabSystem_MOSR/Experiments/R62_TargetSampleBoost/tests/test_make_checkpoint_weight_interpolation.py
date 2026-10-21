from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import torch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "make_checkpoint_weight_interpolation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("make_checkpoint_weight_interpolation", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_interpolates_state_and_ema_weights_while_preserving_safe_config(tmp_path: Path):
    module = load_module()
    base = tmp_path / "base.pth.tar"
    trained = tmp_path / "trained.pth.tar"
    output = tmp_path / "mixed.pth.tar"
    base_cfg = {"raw_anchor_output": {"mode": "blend", "alpha": 0.10, "sigma": 2.0, "detail_gain": 0.35}}
    torch.save(
        {
            "state_dict": {"w": torch.tensor([0.0, 2.0]), "count": torch.tensor([3])},
            "ema_state_dict": {"w": torch.tensor([10.0, 20.0])},
            "model_config": base_cfg,
            "epoch": 7,
        },
        base,
    )
    torch.save(
        {
            "state_dict": {"w": torch.tensor([10.0, 6.0]), "count": torch.tensor([9])},
            "ema_state_dict": {"w": torch.tensor([30.0, 60.0])},
            "model_config": {"raw_anchor_output": {"mode": "none"}},
            "epoch": 9,
        },
        trained,
    )

    info = module.interpolate_checkpoints(base, trained, output, alpha=0.25)

    mixed = torch.load(output, map_location="cpu")
    assert torch.allclose(mixed["state_dict"]["w"], torch.tensor([2.5, 3.0]))
    assert torch.equal(mixed["state_dict"]["count"], torch.tensor([3]))
    assert torch.allclose(mixed["ema_state_dict"]["w"], torch.tensor([15.0, 30.0]))
    assert mixed["model_config"] == base_cfg
    assert mixed["epoch"] == 7
    assert mixed["checkpoint_weight_interpolation"]["alpha"] == 0.25
    assert info["interpolated_tensors"] == 2
    assert info["preserved_tensors"] == 1


def test_interpolation_rejects_alpha_outside_unit_interval(tmp_path: Path):
    module = load_module()
    base = tmp_path / "base.pth.tar"
    trained = tmp_path / "trained.pth.tar"
    torch.save({"state_dict": {}}, base)
    torch.save({"state_dict": {}}, trained)

    with pytest.raises(ValueError, match="alpha"):
        module.interpolate_checkpoints(base, trained, tmp_path / "mixed.pth.tar", alpha=1.25)
