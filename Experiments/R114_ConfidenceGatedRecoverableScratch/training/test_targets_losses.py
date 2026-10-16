from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import build_full_model
from training.losses import controller_components, controller_objective, geometry_parameter_components, render_components
from training.targets import build_spatial_targets


def synthetic_batch(batch: int = 3, side: int = 64):
    yy, xx = torch.meshgrid(torch.arange(side), torch.arange(side), indexing="ij")
    radius = torch.sqrt((xx - side / 2) ** 2 + (yy - side / 2) ** 2)
    sdf = (radius - side * 0.25).float()[None, None].repeat(batch, 1, 1, 1)
    mask = (sdf < 0).float()
    target = 0.2 + 0.6 * mask
    source = torch.nn.functional.avg_pool2d(target, 7, stride=1, padding=3)
    source[1] = target[1]
    source[2] = 0.4
    identity = torch.tensor([False, True, False])
    flat = torch.tensor([False, False, True])
    return {
        "source": source,
        "target": target,
        "mask": mask,
        "sdf": sdf,
        "identity": identity,
        "flat": flat,
        "midpoint": torch.tensor([0.5, 0.5, 0.5]),
        "polarity": torch.tensor([1.0, 1.0, 1.0]),
    }


def test_spatial_targets_are_finite_and_identity_safe() -> None:
    batch = synthetic_batch()
    targets = build_spatial_targets(**{name: batch[name] for name in ("source", "target", "mask", "sdf", "identity", "flat")})
    for value in targets.__dict__.values():
        assert torch.isfinite(value).all()
    assert torch.count_nonzero(targets.need[1]) == 0
    assert torch.count_nonzero(targets.normal_shift[1]) == 0
    assert torch.allclose(targets.width_gain[1], torch.ones_like(targets.width_gain[1]))
    assert torch.count_nonzero(targets.boundary[2]) == 0


def test_all_stage_losses_backpropagate() -> None:
    torch.manual_seed(11420)
    batch = synthetic_batch()
    model = build_full_model(detail_enabled=False, compact=True)
    details = model.forward_details(batch["source"])
    targets = build_spatial_targets(**{name: batch[name] for name in ("source", "target", "mask", "sdf", "identity", "flat")})
    controller = controller_components(details, targets)
    geometry = geometry_parameter_components(details, targets)
    render = render_components(details, batch, targets)
    total = sum(controller_objective(controller, cycle) for cycle in range(3))
    total = total + geometry["width"] + geometry["shift"] + 0.1 * geometry["tangent_coherence"]
    total = total + render["contour_dice"] + render["reconstruction"] + render["identity"]
    assert torch.isfinite(total)
    total.backward()
    assert any(parameter.grad is not None and torch.isfinite(parameter.grad).all() for parameter in model.parameters())
