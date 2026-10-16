from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch


INFER_PATH = Path(__file__).resolve().parents[5] / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"


def load_infer_module():
    spec = importlib.util.spec_from_file_location("geoedge_infer_boundary_adapter_test", INFER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_infer_arch_detects_boundary_residual_adapter_from_checkpoint_state():
    infer = load_infer_module()
    state = {
        "e1.0.conv.weight": torch.zeros(8, 1, 3, 3),
        "boundary_adapter.max_residual": torch.tensor(0.03125),
        "boundary_adapter.body.0.weight": torch.zeros(12, 9, 3, 3),
        "boundary_adapter.gate.bias": torch.full((1,), -1.5),
        "boundary_adapter.delta.weight": torch.zeros(1, 12, 1, 1),
        "boundary_adapter.delta.bias": torch.zeros(1),
    }

    arch = infer.infer_arch_from_state(state)

    assert arch["boundary_residual_adapter_enable"] is True
    assert arch["boundary_residual_adapter_hidden"] == 12
    assert arch["boundary_residual_adapter_max"] == 0.03125
    assert arch["boundary_residual_adapter_gate_bias"] == -1.5
    assert arch["boundary_residual_adapter_delta_bias"] is True


def test_infer_arch_keeps_boundary_residual_adapter_disabled_for_old_checkpoint_state():
    infer = load_infer_module()
    state = {
        "e1.0.conv.weight": torch.zeros(8, 1, 3, 3),
    }

    arch = infer.infer_arch_from_state(state)

    assert arch["boundary_residual_adapter_enable"] is False


def test_infer_arch_uses_checkpoint_boundary_adapter_metadata():
    infer = load_infer_module()
    state = {
        "e1.0.conv.weight": torch.zeros(8, 1, 3, 3),
        "boundary_adapter.max_residual": torch.tensor(0.025),
        "boundary_adapter.body.0.weight": torch.zeros(12, 9, 3, 3),
        "boundary_adapter.gate.bias": torch.full((1,), -2.0),
        "boundary_adapter.delta.weight": torch.zeros(1, 12, 1, 1),
    }
    ckpt_obj = {
        "model_config": {
            "boundary_residual_adapter": {
                "delta_bias": False,
                "zero_mean": True,
                "edge_gate": True,
            }
        }
    }

    arch = infer.infer_arch_from_state(state, ckpt_obj=ckpt_obj)

    assert arch["boundary_residual_adapter_delta_bias"] is False
    assert arch["boundary_residual_adapter_zero_mean"] is True
    assert arch["boundary_residual_adapter_edge_gate"] is True


def test_infer_arch_detects_polarity_split_boundary_adapter_from_delta_modes():
    infer = load_infer_module()
    state = {
        "e1.0.conv.weight": torch.zeros(8, 1, 3, 3),
        "boundary_adapter.max_residual": torch.tensor(0.025),
        "boundary_adapter.body.0.weight": torch.zeros(12, 9, 3, 3),
        "boundary_adapter.gate.bias": torch.full((1,), -2.0),
        "boundary_adapter.delta.weight": torch.zeros(2, 12, 1, 1),
        "boundary_adapter.delta.bias": torch.zeros(2),
        "boundary_adapter.polarity_gate.weight": torch.zeros(2, 12, 1, 1),
    }

    arch = infer.infer_arch_from_state(state)

    assert arch["boundary_residual_adapter_polarity_split"] is True


def test_infer_arch_detects_orientation_boundary_adapter_from_extra_body_inputs():
    infer = load_infer_module()
    state = {
        "e1.0.conv.weight": torch.zeros(8, 1, 3, 3),
        "boundary_adapter.max_residual": torch.tensor(0.025),
        "boundary_adapter.body.0.weight": torch.zeros(12, 12, 3, 3),
        "boundary_adapter.gate.bias": torch.full((1,), -2.0),
        "boundary_adapter.delta.weight": torch.zeros(1, 12, 1, 1),
        "boundary_adapter.delta.bias": torch.zeros(1),
    }

    arch = infer.infer_arch_from_state(state)

    assert arch["boundary_residual_adapter_orientation_inputs"] is True


def test_infer_arch_uses_checkpoint_orientation_adapter_metadata():
    infer = load_infer_module()
    state = {
        "e1.0.conv.weight": torch.zeros(8, 1, 3, 3),
        "boundary_adapter.max_residual": torch.tensor(0.025),
        "boundary_adapter.body.0.weight": torch.zeros(12, 12, 3, 3),
        "boundary_adapter.gate.bias": torch.full((1,), -2.0),
        "boundary_adapter.delta.weight": torch.zeros(1, 12, 1, 1),
    }
    ckpt_obj = {
        "model_config": {
            "boundary_residual_adapter": {
                "orientation_inputs": True,
            }
        }
    }

    arch = infer.infer_arch_from_state(state, ckpt_obj=ckpt_obj)

    assert arch["boundary_residual_adapter_orientation_inputs"] is True
