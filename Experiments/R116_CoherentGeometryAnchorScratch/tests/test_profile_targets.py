from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.profile_targets import build_profile_targets


def edge_batch(side: int = 72):
    yy, xx = torch.meshgrid(
        torch.arange(side, dtype=torch.float32),
        torch.arange(side, dtype=torch.float32),
        indexing="ij",
    )
    sdf = xx - side * 0.5
    target = 0.25 + 0.50 * torch.sigmoid(sdf / 0.75)
    broad_shifted = 0.25 + 0.50 * torch.sigmoid((sdf - 0.65) / 2.4)
    flat = torch.full_like(target, 0.42)
    source = torch.stack((broad_shifted, target, flat))[:, None]
    target_batch = torch.stack((target, target, flat))[:, None]
    sdf_batch = torch.stack((sdf, sdf, torch.full_like(sdf, 20.0)))[:, None]
    return source, target_batch, sdf_batch


def test_profile_targets_are_finite_bounded_and_neutral() -> None:
    source, target, sdf = edge_batch()
    values = build_profile_targets(
        source,
        target,
        sdf,
        identity=torch.tensor([False, True, False]),
        flat=torch.tensor([False, False, True]),
        offsets_px=(-9, -6, -3, 0, 3, 6, 9),
    )
    for value in values.__dict__.values():
        assert torch.isfinite(value).all()
    assert float(values.width_gain.min()) >= 1.0
    assert float(values.width_gain.max()) <= 3.5
    assert float(values.normal_shift.abs().max()) <= 1.5
    assert torch.equal(values.width_gain[1], torch.ones_like(values.width_gain[1]))
    assert torch.count_nonzero(values.normal_shift[1]) == 0
    assert torch.count_nonzero(values.boundary_band[2]) == 0
    assert torch.count_nonzero(values.width_reliability[2]) == 0
    assert torch.count_nonzero(values.shift_reliability[2]) == 0


def test_broad_shifted_edge_produces_non_neutral_actions() -> None:
    source, target, sdf = edge_batch()
    values = build_profile_targets(
        source[:1],
        target[:1],
        sdf[:1],
        offsets_px=(-9, -6, -3, 0, 3, 6, 9),
    )
    center = values.boundary_band > 0.8
    assert float(values.width_gain[center].median()) > 1.2
    assert abs(float(values.normal_shift[center].median())) > 0.1
    assert float(values.width_reliability[center].median()) > 0.0
    assert float(values.shift_reliability[center].median()) > 0.0


def test_predicted_coordinate_is_supported_without_using_target_at_inference() -> None:
    source, target, sdf = edge_batch()
    predicted = sdf[:1] + 0.5
    values = build_profile_targets(
        source[:1],
        target[:1],
        sdf[:1],
        predicted_sdf_px=predicted,
        offsets_px=(-9, -6, -3, 0, 3, 6, 9),
    )
    assert torch.isfinite(values.width_gain).all()
    assert float(values.sample_validity.mean()) > 0.5
