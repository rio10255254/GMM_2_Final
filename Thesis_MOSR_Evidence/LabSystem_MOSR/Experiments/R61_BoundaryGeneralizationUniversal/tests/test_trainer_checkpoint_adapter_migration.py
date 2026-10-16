from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch


MODEL_DIR = Path(__file__).resolve().parents[5] / "Model"
TRAINER_PATH = MODEL_DIR / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"


def load_trainer_module():
    sys.path.insert(0, str(MODEL_DIR))
    spec = importlib.util.spec_from_file_location("geoedge_trainer_checkpoint_migration_test", TRAINER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_single_mode_boundary_adapter_weights_expand_into_polarity_split_modes():
    trainer = load_trainer_module()
    old_weight = torch.arange(12, dtype=torch.float32).reshape(1, 12, 1, 1)
    old_bias = torch.tensor([0.125], dtype=torch.float32)
    checkpoint_state = {
        "boundary_adapter.delta.weight": old_weight,
        "boundary_adapter.delta.bias": old_bias,
    }
    current_state = {
        "boundary_adapter.delta.weight": torch.zeros(2, 12, 1, 1),
        "boundary_adapter.delta.bias": torch.zeros(2),
    }

    filtered, skipped, expanded = trainer._filter_checkpoint_state_for_load(checkpoint_state, current_state)

    assert skipped == []
    assert expanded == ["boundary_adapter.delta.weight", "boundary_adapter.delta.bias"]
    assert torch.equal(filtered["boundary_adapter.delta.weight"][0], old_weight[0])
    assert torch.equal(filtered["boundary_adapter.delta.weight"][1], old_weight[0])
    assert torch.equal(filtered["boundary_adapter.delta.bias"], old_bias.repeat(2))


def test_boundary_adapter_first_conv_expands_for_orientation_inputs_without_changing_old_channels():
    trainer = load_trainer_module()
    old_weight = torch.arange(16 * 9 * 3 * 3, dtype=torch.float32).reshape(16, 9, 3, 3)
    checkpoint_state = {
        "boundary_adapter.body.0.weight": old_weight,
        "boundary_adapter.body.0.bias": torch.ones(16),
    }
    current_state = {
        "boundary_adapter.body.0.weight": torch.full((16, 12, 3, 3), -1.0),
        "boundary_adapter.body.0.bias": torch.zeros(16),
    }

    filtered, skipped, expanded = trainer._filter_checkpoint_state_for_load(checkpoint_state, current_state)

    assert skipped == []
    assert expanded == ["boundary_adapter.body.0.weight"]
    assert torch.equal(filtered["boundary_adapter.body.0.weight"][:, :9], old_weight)
    assert torch.count_nonzero(filtered["boundary_adapter.body.0.weight"][:, 9:]) == 0
    assert torch.equal(filtered["boundary_adapter.body.0.bias"], checkpoint_state["boundary_adapter.body.0.bias"])
