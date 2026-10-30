from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import torch
import torch.nn.functional as F


MODEL_DIR = Path(__file__).resolve().parents[4] / "Model"
TRAINER_PATH = MODEL_DIR / "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py"


def load_trainer_module():
    sys.path.insert(0, str(MODEL_DIR))
    spec = importlib.util.spec_from_file_location("geoedge_trainer_boundary_position_test", TRAINER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def vertical_step(edge_x: int, size: int = 48) -> torch.Tensor:
    x = torch.zeros(1, 1, size, size)
    x[:, :, :, edge_x:] = 1.0
    return x


def vertical_boundary_geom(edge_x: int, size: int = 48) -> dict[str, torch.Tensor]:
    centerline = torch.zeros(1, 1, size, size)
    centerline[:, :, :, edge_x] = 1.0
    yy, xx = torch.meshgrid(torch.arange(size), torch.arange(size), indexing="ij")
    distance = torch.abs(xx.float() - float(edge_x)).unsqueeze(0).unsqueeze(0)
    boundary = F.max_pool2d(centerline, kernel_size=3, stride=1, padding=1)
    return {"centerline": centerline, "boundary": boundary, "distance": distance}


def test_boundary_position_loss_prefers_edges_on_truth_centerline():
    trainer = load_trainer_module()
    geom = vertical_boundary_geom(edge_x=24)
    aligned = vertical_step(edge_x=24)
    shifted = vertical_step(edge_x=30)

    aligned_loss, aligned_parts = trainer.boundary_position_loss(aligned, geom)
    shifted_loss, shifted_parts = trainer.boundary_position_loss(shifted, geom)

    assert aligned_loss < shifted_loss * 0.25
    assert aligned_parts["distance"] < shifted_parts["distance"] * 0.25


def test_boundary_position_loss_returns_zero_without_geometry():
    trainer = load_trainer_module()
    pred = vertical_step(edge_x=24)

    loss, parts = trainer.boundary_position_loss(pred, None)

    assert loss.item() == 0.0
    assert parts["distance"].item() == 0.0
    assert parts["coverage"].item() == 0.0
