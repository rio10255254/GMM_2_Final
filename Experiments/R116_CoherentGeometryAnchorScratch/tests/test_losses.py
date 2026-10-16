from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import R116Config, build_model
from training.losses import (
    detector_components,
    detail_components,
    geometry_components,
    probability_bce,
    shift_action_components,
    translation_consistency,
    warp_translation,
    width_action_components,
)


def model_and_source():
    config = R116Config(
        base_channels=8,
        action_channels=8,
        detail_channels=8,
        detector_dilations=(1,),
        action_dilations=(1,),
        detail_dilations=(1,),
        blur_scales_px=(0.5, 0.8, 1.1, 1.4),
        profile_offsets_px=(-2, 0, 2),
        coherence_offsets_px=(-1, 0, 1),
        coherence_sigma_px=1.0,
        maximum_predicted_sdf_px=3.0,
        local_range_window_px=5,
        low_frequency_anchor_sigma_px=0.8,
        minimum_halo_px=24,
    )
    model = build_model(config)
    yy, xx = torch.meshgrid(torch.arange(56), torch.arange(64), indexing="ij")
    sdf = torch.sqrt((xx.float() - 31.5) ** 2 + (yy.float() - 27.0) ** 2 + 1.0e-6) - 15.0
    target = (0.2 + 0.55 * torch.sigmoid(-sdf / 0.8))[None, None]
    source = (0.2 + 0.55 * torch.sigmoid(-(sdf - 0.6) / 2.2))[None, None]
    mask = (sdf <= 0).float()[None, None]
    boundary = torch.exp(-sdf.abs() / 1.5)[None, None]
    return model, source, target, sdf[None, None], mask, boundary


def test_all_stage_components_are_finite() -> None:
    model, source, target, sdf, mask, boundary = model_and_source()
    details = model.forward_details(source)
    detector = detector_components(details, sdf, boundary)
    geometry = geometry_components(
        details, target, mask,
        torch.tensor([0.475]), torch.tensor([-1.0]), torch.tensor([False]),
    )
    detail = detail_components(details, target, torch.tensor([False]))
    width = width_action_components(
        details,
        1.0 + boundary,
        boundary,
        boundary,
    )
    shift = shift_action_components(
        details,
        0.5 * boundary,
        boundary,
        boundary,
    )
    for group in (detector, geometry, width, shift, detail):
        assert group
        assert all(torch.isfinite(value) for value in group.values())


def test_translation_consistency_detects_a_mismatch() -> None:
    model, source, _target, _sdf, _mask, _boundary = model_and_source()
    model.eval()
    dx = torch.tensor([0.75])
    dy = torch.tensor([-0.50])
    shifted = warp_translation(source, dx, dy)
    with torch.inference_mode():
        first = model.forward_details(source)
        aligned = model.forward_details(shifted)
        wrong = model.forward_details(source)
    aligned_loss = translation_consistency(first, aligned, dx, dy, margin=12)["output"]
    wrong_loss = translation_consistency(first, wrong, dx, dy, margin=12)["output"]
    assert float(aligned_loss) < float(wrong_loss)


def test_probability_bce_is_finite_at_bfloat16_extremes() -> None:
    prediction = torch.tensor([0.0, 1.0], dtype=torch.bfloat16, requires_grad=True)
    target = torch.tensor([0.25, 0.25], dtype=torch.bfloat16)
    loss = probability_bce(prediction, target).mean()
    assert torch.isfinite(loss)
    loss.backward()
    assert prediction.grad is not None
    assert torch.isfinite(prediction.grad).all()
