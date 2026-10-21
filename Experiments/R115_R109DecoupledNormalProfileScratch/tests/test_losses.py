from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r115_model import build_model
from training.losses import factor_targets, profile_evidence_components, profile_objective
from training.r115_dataset import R115Dataset


def test_online_factor_target_makes_only_bounded_residual_adjustments() -> None:
    source = torch.full((1, 1, 16, 16), 0.4)
    target = source.clone()
    target[..., 4:12, 4:12] += 0.1
    sdf = torch.zeros_like(source)
    identity = torch.tensor([False])
    helpful = torch.zeros_like(source)
    helpful[..., 4:12, 4:12] = 0.08
    harmful = -helpful
    positive = factor_targets(helpful, source, target, sdf, identity)
    negative = factor_targets(harmful, source, target, sdf, identity)
    assert float(positive.factor[..., 4:12, 4:12].mean()) > 1.0
    assert float(negative.factor[..., 4:12, 4:12].mean()) < 1.0
    assert float(positive.factor.min()) >= 0.85
    assert float(positive.factor.max()) <= 1.15


def test_profile_objective_updates_only_profile_branch() -> None:
    dataset = R115Dataset("train", epoch=1, arm="B", limit=2)
    rows = [dataset[0], dataset[1]]
    batch = {
        name: torch.stack([row[name] for row in rows])
        for name in ("source", "target", "sdf", "identity")
    }
    source = batch["source"].reshape(-1, 1, 256, 256)
    target = batch["target"].reshape(-1, 1, 256, 256)
    sdf = batch["sdf"].reshape(-1, 1, 256, 256)
    identity = batch["identity"].reshape(-1)
    model = build_model().train()
    for parameter in model.detector_parameters() + model.geometry_parameters():
        parameter.requires_grad_(False)
    details = model.forward_details(source)
    components, _shift, _width = profile_evidence_components(
        details, source, target, sdf, identity
    )
    loss = profile_objective(components)
    assert torch.isfinite(loss)
    loss.backward()
    assert any(
        parameter.grad is not None and float(parameter.grad.abs().sum()) > 0
        for parameter in model.profile_parameters()
    )
    assert all(parameter.grad is None for parameter in model.detector_parameters())
    assert all(parameter.grad is None for parameter in model.geometry_parameters())
