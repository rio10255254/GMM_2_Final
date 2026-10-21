from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch
from torch import nn


MODEL_DIR = Path(__file__).resolve().parents[5] / "Model"
TRAINER_PATH = MODEL_DIR / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"


def load_trainer_module():
    sys.path.insert(0, str(MODEL_DIR))
    spec = importlib.util.spec_from_file_location("geoedge_trainer_freeze_test", TRAINER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TinyBoundaryModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.e1 = nn.Conv2d(1, 4, 3, padding=1)
        self.p1 = nn.Sequential(nn.Conv2d(4, 4, 3, padding=1), nn.ReLU())
        self.out = nn.Conv2d(4, 1, 1)
        self.physics_layer = nn.Conv2d(1, 1, 1)
        self.weak_psf_block = nn.Conv2d(4, 4, 1)


def trainable_names(model: nn.Module) -> set[str]:
    return {name for name, param in model.named_parameters() if param.requires_grad}


def optimizer_param_ids(optimizer: torch.optim.Optimizer) -> set[int]:
    ids: set[int] = set()
    for group in optimizer.param_groups:
        ids.update(id(param) for param in group["params"])
    return ids


def test_trainable_filter_leaves_model_unchanged_when_no_patterns():
    trainer = load_trainer_module()
    model = TinyBoundaryModel()
    before = trainable_names(model)

    summary = trainer.apply_trainable_name_filter(model, ())

    assert summary["enabled"] is False
    assert trainable_names(model) == before


def test_trainable_filter_freezes_everything_except_matching_tail_layers():
    trainer = load_trainer_module()
    model = TinyBoundaryModel()

    summary = trainer.apply_trainable_name_filter(model, ("p1", "out"))

    assert summary["enabled"] is True
    assert summary["trainable_count"] > 0
    assert summary["frozen_count"] > 0
    assert trainable_names(model) == {
        "p1.0.weight",
        "p1.0.bias",
        "out.weight",
        "out.bias",
    }


def test_build_optimizer_uses_only_trainable_parameters_after_filter():
    trainer = load_trainer_module()
    model = TinyBoundaryModel()
    trainer.CFG.LR = 1e-4
    trainer.CFG.WEIGHT_DECAY = 0.0
    trainer.CFG.PHYSICS_LR_MULT = 0.1
    trainer.CFG.WEAK_PSF_LR_MULT = 0.1
    trainer.apply_trainable_name_filter(model, ("p1", "out"))

    optimizer = trainer._build_optimizer(model)
    trainable_param_ids = {id(param) for param in model.parameters() if param.requires_grad}

    assert optimizer_param_ids(optimizer) == trainable_param_ids
    assert all(len(group["params"]) > 0 for group in optimizer.param_groups)
