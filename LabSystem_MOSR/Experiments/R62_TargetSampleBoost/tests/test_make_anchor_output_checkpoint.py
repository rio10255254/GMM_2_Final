from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import torch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "make_anchor_output_checkpoint.py"


def load_module():
    spec = importlib.util.spec_from_file_location("make_anchor_output_checkpoint", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_patch_checkpoint_sets_anchor_output_without_changing_weights(tmp_path: Path):
    module = load_module()
    src = tmp_path / "src.pth.tar"
    dst = tmp_path / "dst.pth.tar"
    weight = torch.tensor([1.0, 2.0, 3.0])
    torch.save({"state_dict": {"w": weight}, "model_config": {"boundary_residual_adapter": {"enable": True}}}, src)

    info = module.patch_anchor_output_checkpoint(
        src,
        dst,
        mode="blend",
        alpha=0.10,
        sigma=2.0,
        detail_gain=0.35,
    )

    patched = torch.load(dst, map_location="cpu")
    assert info["source_checkpoint"] == str(src)
    assert info["output_checkpoint"] == str(dst)
    assert torch.equal(patched["state_dict"]["w"], weight)
    assert patched["model_config"]["boundary_residual_adapter"]["enable"] is True
    assert patched["model_config"]["raw_anchor_output"] == {
        "mode": "blend",
        "alpha": 0.10,
        "sigma": 2.0,
        "detail_gain": 0.35,
    }
    assert patched["anchor_output_checkpoint_patch"]["source_checkpoint"] == str(src)


def test_patch_checkpoint_rejects_invalid_blend_alpha(tmp_path: Path):
    module = load_module()
    src = tmp_path / "src.pth.tar"
    torch.save({"state_dict": {}}, src)

    with pytest.raises(ValueError, match="alpha"):
        module.patch_anchor_output_checkpoint(src, tmp_path / "dst.pth.tar", mode="blend", alpha=1.5)
