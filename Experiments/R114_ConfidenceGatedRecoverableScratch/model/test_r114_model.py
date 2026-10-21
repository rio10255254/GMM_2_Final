from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path
import sys

import torch
from torch import nn


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from r114_model import ModelConfig, build_model, count_parameters, forward_tiled


def compact_config() -> ModelConfig:
    return ModelConfig(
        base_channels=12,
        dilations=(1, 2, 2, 1),
        blur_scales_px=(0.8, 1.6),
        minimum_halo_px=23,
    )


def structured_input(height: int = 80, width: int = 88) -> torch.Tensor:
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, height),
        torch.linspace(-1.0, 1.0, width),
        indexing="ij",
    )
    ellipse = ((xx / 0.58).square() + (yy / 0.36).square() < 1).float()
    texture = 0.04 * torch.sin(17.0 * xx + 3.0 * yy)
    illumination = 0.12 * xx - 0.06 * yy
    return (0.22 + 0.55 * ellipse + texture + illumination).clamp(0, 1)[None, None]


def test_output_shapes_ranges_and_finiteness() -> None:
    torch.manual_seed(11401)
    model = build_model(compact_config()).eval()
    value = structured_input()
    with torch.inference_mode():
        output = model(value)

    expected_one = (1, 1, 80, 88)
    assert output.normalized_sdf.shape == expected_one
    assert output.normal_x.shape == expected_one
    assert output.normal_y.shape == expected_one
    assert output.boundary_confidence.shape == expected_one
    assert output.correction_need.shape == expected_one
    assert output.recoverability_uncertainty.shape == (1, 2, 80, 88)
    for item in fields(output):
        assert torch.isfinite(getattr(output, item.name)).all(), item.name
    assert output.boundary_confidence.min() >= 0
    assert output.boundary_confidence.max() <= 1
    assert output.correction_need.min() >= 0
    assert output.correction_need.max() <= 1
    assert output.recoverability_uncertainty.min() >= 0
    assert output.recoverability_uncertainty.max() <= 1
    assert torch.allclose(
        output.recoverability_uncertainty.sum(1),
        torch.ones_like(output.recoverability_uncertainty[:, 0]),
        atol=1e-6,
        rtol=0,
    )
    normal_length = torch.sqrt(output.normal_x.square() + output.normal_y.square())
    assert torch.allclose(normal_length, torch.ones_like(normal_length), atol=2e-4, rtol=0)
    assert count_parameters(model) > 0


def test_default_48_channel_model_smoke() -> None:
    torch.manual_seed(11400)
    model = build_model().eval()
    value = structured_input(64, 72)
    with torch.inference_mode():
        output = model(value)
    assert output.normalized_sdf.shape == (1, 1, 64, 72)
    assert output.recoverability_uncertainty.shape == (1, 2, 64, 72)
    assert all(torch.isfinite(getattr(output, item.name)).all() for item in fields(output))
    assert model.exact_receptive_field_radius_px == 101
    assert model.minimum_halo_px == 192
    # One controller tower is intentionally about half of R109's duplicated
    # detector/renderer towers; this probe does not yet contain a renderer.
    assert count_parameters(model) > 300_000
    shared = json.loads((HERE.parent / "config" / "model.json").read_text(encoding="utf-8"))
    assert model.config.base_channels == shared["base_channels"]
    assert list(model.config.dilations) == shared["dilations"]
    assert list(model.config.blur_scales_px) == shared["blur_scales_px"]
    assert model.config.normalization == shared["normalization"]
    assert model.minimum_halo_px == shared["minimum_halo_px"]


def test_every_controller_output_has_nonzero_input_gradient() -> None:
    torch.manual_seed(11402)
    model = build_model(compact_config()).eval()
    value = structured_input(72, 76).requires_grad_(True)
    output = model(value)
    spatial_weight = torch.linspace(0.5, 1.5, 72 * 76).reshape(1, 1, 72, 76)
    maps = {
        "normalized_sdf": output.normalized_sdf,
        "normal_x": output.normal_x,
        "normal_y": output.normal_y,
        "boundary_confidence": output.boundary_confidence,
        "correction_need": output.correction_need,
        "recoverability": output.recoverability,
        "uncertainty": output.uncertainty,
    }
    for index, (name, tensor) in enumerate(maps.items()):
        scalar = (tensor * spatial_weight).mean()
        gradient = torch.autograd.grad(
            scalar,
            value,
            retain_graph=index < len(maps) - 1,
            allow_unused=False,
        )[0]
        assert torch.isfinite(gradient).all(), name
        assert float(gradient.abs().sum()) > 1e-8, name


def test_full_and_overlapping_tile_outputs_match() -> None:
    torch.manual_seed(11403)
    model = build_model(compact_config()).eval()
    value = structured_input(101, 117)
    with torch.inference_mode():
        full = model(value)
        tiled = forward_tiled(model, value, core_size=37)
    for item in fields(full):
        name = item.name
        error = (getattr(full, name) - getattr(tiled, name)).abs().max()
        assert float(error) <= 2e-5, f"{name}: {float(error)}"


def test_contract_has_no_spatial_normalization_or_inherited_state() -> None:
    torch.manual_seed(11404)
    first = build_model(compact_config())
    torch.manual_seed(11405)
    second = build_model(compact_config())
    forbidden = (nn.GroupNorm, nn.BatchNorm2d, nn.InstanceNorm2d, nn.AdaptiveAvgPool2d)
    assert not any(isinstance(module, forbidden) for module in first.modules())
    assert set(first.state_dict()) == set(second.state_dict())
    assert any(
        not torch.equal(first.state_dict()[name], second.state_dict()[name])
        for name in first.state_dict()
        if first.state_dict()[name].is_floating_point()
    )
    names = " ".join(first.state_dict()).lower()
    assert "raw_anchor" not in names
    assert "checkpoint" not in names
    assert "necessity" not in names
