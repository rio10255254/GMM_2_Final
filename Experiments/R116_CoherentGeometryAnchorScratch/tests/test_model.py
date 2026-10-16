from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inference.tiled import forward_tiled
from model.r116_model import R116Config, build_model, count_parameters, warp_local, warp_local_many


def config() -> R116Config:
    return R116Config(
        base_channels=12,
        action_channels=10,
        detail_channels=10,
        detector_dilations=(1, 1),
        action_dilations=(1, 1),
        detail_dilations=(1, 1),
        blur_scales_px=(0.55, 0.85, 1.2, 1.6),
        profile_offsets_px=(-3, 0, 3),
        coherence_offsets_px=(-2, 0, 2),
        coherence_sigma_px=1.5,
        maximum_predicted_sdf_px=3.0,
        local_range_window_px=7,
        low_frequency_anchor_sigma_px=1.0,
        minimum_halo_px=40,
    )


def fixture(height: int = 96, width: int = 104) -> torch.Tensor:
    yy, xx = torch.meshgrid(
        torch.arange(height, dtype=torch.float32),
        torch.arange(width, dtype=torch.float32),
        indexing="ij",
    )
    radius = torch.sqrt((xx - width * 0.53) ** 2 + (yy - height * 0.47) ** 2 + 1.0e-6)
    value = 0.24 + 0.50 * torch.sigmoid(-(radius - 23.0) / 2.2)
    value += 0.025 * torch.sin(xx / 4.5) * torch.cos(yy / 6.5)
    return value.clamp(0, 1)[None, None]


def test_initial_output_is_safe_near_identity() -> None:
    model = build_model(config()).eval()
    source = fixture()
    with torch.inference_mode():
        details = model.forward_details(source)
    assert torch.equal(details.geometry_anchor, source)
    assert torch.equal(details.width_gain, torch.ones_like(details.width_gain))
    assert torch.equal(details.output, source)
    assert float(details.output.min()) >= 0.0
    assert float(details.output.max()) <= 1.0
    assert torch.isfinite(details.output).all()


def test_isolated_detector_matches_full_forward() -> None:
    model = build_model(config()).eval()
    source = fixture(72, 80)
    with torch.inference_mode():
        isolated = model.forward_detection(source)
        full = model.forward_details(source)
    assert torch.equal(isolated.boundary_logits, full.boundary_logits)
    assert torch.equal(isolated.boundary_confidence, full.boundary_confidence)
    assert torch.equal(isolated.predicted_sdf_px, full.predicted_sdf_px)


def test_parameter_groups_are_disjoint_and_exhaustive() -> None:
    model = build_model(config())
    groups = model.parameter_groups()
    assert set(groups) == {"detector", "width", "shift", "detail"}
    identifiers = {name: {id(parameter) for parameter in values} for name, values in groups.items()}
    names = tuple(identifiers)
    for index, left in enumerate(names):
        for right in names[index + 1:]:
            assert not identifiers[left] & identifiers[right]
    assert set().union(*identifiers.values()) == {id(parameter) for parameter in model.parameters()}


def test_model_contains_no_forbidden_global_or_spatial_normalization() -> None:
    model = build_model(config())
    forbidden = (
        torch.nn.BatchNorm1d,
        torch.nn.BatchNorm2d,
        torch.nn.BatchNorm3d,
        torch.nn.GroupNorm,
        torch.nn.LayerNorm,
        torch.nn.InstanceNorm1d,
        torch.nn.InstanceNorm2d,
        torch.nn.InstanceNorm3d,
        torch.nn.AdaptiveAvgPool1d,
        torch.nn.AdaptiveAvgPool2d,
        torch.nn.AdaptiveAvgPool3d,
        torch.nn.AdaptiveMaxPool1d,
        torch.nn.AdaptiveMaxPool2d,
        torch.nn.AdaptiveMaxPool3d,
    )
    assert not any(isinstance(module, forbidden) for module in model.modules())
    assert count_parameters(model) < 4_024_238


def test_detail_is_bounded_and_low_frequency_is_suppressed() -> None:
    model = build_model(config()).eval()
    with torch.no_grad():
        model.boundary_head.bias.fill_(3.0)
        model.width_head.bias[0] = 1.5
        model.width_head.bias[1] = 3.0
        model.detail_head.bias[:3] = torch.tensor([0.8, -0.4, 0.5])
        model.detail_head.bias[3] = 3.0
    with torch.inference_mode():
        details = model.forward_details(fixture())
    cap = model.config.maximum_detail_delta_gray / 255.0
    assert float(details.bounded_detail.abs().max()) <= cap + 1.0e-6
    detail_mean = float(details.bounded_detail.abs().mean())
    leakage_mean = float(details.low_frequency_leakage.abs().mean())
    assert detail_mean > 1.0e-5
    assert leakage_mean < detail_mean * 0.55


def test_detail_gradient_does_not_reach_other_paths_when_they_are_frozen() -> None:
    model = build_model(config()).train()
    groups = model.parameter_groups()
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == "detail")
    details = model.forward_details(fixture(72, 80))
    loss = details.output.square().mean() + details.evidence_detail.abs().mean()
    loss.backward()
    assert any(parameter.grad is not None for parameter in groups["detail"])
    for name in ("detector", "width", "shift"):
        assert all(parameter.grad is None for parameter in groups[name])


def test_zero_shift_is_exact_identity_but_keeps_shift_gradient() -> None:
    model = build_model(config()).train()
    groups = model.parameter_groups()
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == "shift")
    source = fixture(72, 80)
    details = model.forward_details(source)
    assert torch.equal(details.geometry_anchor, source)
    target = torch.roll(source, shifts=1, dims=-1)
    loss = torch.abs(details.geometry_anchor[..., 8:-8, 8:-8] - target[..., 8:-8, 8:-8]).mean()
    loss.backward()
    shift_head_gradients = [
        parameter.grad for parameter in model.shift_head.parameters()
        if parameter.grad is not None
    ]
    assert shift_head_gradients
    assert sum(float(value.abs().sum()) for value in shift_head_gradients) > 0.0


def test_identity_width_is_exact_but_keeps_width_gradient() -> None:
    model = build_model(config()).train()
    groups = model.parameter_groups()
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == "width")
    source = fixture(72, 80)
    details = model.forward_details(source)
    assert torch.equal(details.width_gain, torch.ones_like(details.width_gain))
    assert torch.equal(details.output, source)
    target = torch.where(source > 0.48, torch.ones_like(source) * 0.76, torch.ones_like(source) * 0.24)
    loss = torch.abs(details.output - target).mean()
    loss.backward()
    width_head_gradients = [
        parameter.grad for parameter in model.width_head.parameters()
        if parameter.grad is not None
    ]
    assert width_head_gradients
    assert sum(float(value.abs().sum()) for value in width_head_gradients) > 0.0


def test_canonical_tiling_is_grid_stable() -> None:
    model = build_model(config()).eval()
    source = fixture(136, 152)
    with torch.inference_mode():
        first = forward_tiled(model, source, core_size=48, halo=40)
        second = forward_tiled(model, source, core_size=64, halo=40)
    difference = (first - second).abs()
    assert float(difference.mean()) < 2.0e-5
    assert float(torch.quantile(difference.flatten(), 0.99)) < 2.0e-4
    assert float(difference.max()) < 2.0e-3


def test_vectorized_local_sampling_matches_individual_sampling() -> None:
    source = fixture(48, 56).requires_grad_(True)
    generator = torch.Generator().manual_seed(116)
    flows = 0.8 * torch.randn((1, 5, 2, 48, 56), generator=generator)
    flows[:, 2].zero_()
    vectorized = warp_local_many(source, flows)
    reference = torch.stack([warp_local(source, flows[:, index]) for index in range(5)], dim=1)
    assert torch.allclose(vectorized, reference, atol=1.0e-7, rtol=1.0e-6)
    vectorized.square().mean().backward()
    assert source.grad is not None
    assert bool(torch.isfinite(source.grad).all())
