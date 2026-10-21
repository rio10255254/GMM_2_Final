from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import sys

import torch
from torch import nn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r114_split_profile_model import (
    R114SplitProfileModel,
    SplitControllerOutput,
    SplitProfileConfig,
    build_split_profile_model,
    forward_tiled_split,
)


def small_config() -> SplitProfileConfig:
    return SplitProfileConfig(
        base_channels=8,
        dilations=(1, 2, 1),
        blur_scales_px=(0.8, 1.4),
        minimum_halo_px=24,
        local_range_window_px=5,
    )


def structured_input(height: int = 72, width: int = 80) -> torch.Tensor:
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, height),
        torch.linspace(-1.0, 1.0, width),
        indexing="ij",
    )
    ellipse = ((xx / 0.58).square() + (yy / 0.36).square() < 1).float()
    notch = ((xx > 0.08) & (xx < 0.30) & (yy > -0.10) & (yy < 0.12)).float()
    texture = 0.035 * torch.sin(19.0 * xx + 4.0 * yy)
    illumination = 0.08 * xx - 0.04 * yy
    image = 0.20 + 0.58 * (ellipse * (1.0 - notch)) + texture + illumination
    return image.clamp(0, 1)[None, None]


def manual_controller(
    like: torch.Tensor,
    *,
    boundary: float = 1.0,
    need: float = 1.0,
    width_reliability: float = 1.0,
    shift_reliability: float = 1.0,
    recoverability: float = 0.5,
    normalized_sdf: float | torch.Tensor = 0.0,
) -> SplitControllerOutput:
    one = torch.ones_like(like)
    zeros = torch.zeros_like(like)
    recoverable = one * recoverability
    uncertainty = one * (1.0 - recoverability)
    sdf = (
        torch.full_like(like, float(normalized_sdf))
        if not isinstance(normalized_sdf, torch.Tensor)
        else normalized_sdf.to(device=like.device, dtype=like.dtype)
    )
    return SplitControllerOutput(
        normalized_sdf=sdf,
        normal_x=one,
        normal_y=zeros,
        boundary_confidence=one * boundary,
        correction_need=one * need,
        recoverability_uncertainty=torch.cat([recoverable, uncertainty], dim=1),
        width_reliability=one * width_reliability,
        shift_reliability=one * shift_reliability,
    )


def renderer_features(model: R114SplitProfileModel, raw: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        return model._renderer_features(raw)


def test_complete_output_shapes_finiteness_ranges_and_parameter_groups() -> None:
    torch.manual_seed(114201)
    model = R114SplitProfileModel(small_config()).eval()
    value = structured_input()
    with torch.inference_mode():
        output = model.forward_details(value)

    one = (1, 1, 72, 80)
    two = (1, 2, 72, 80)
    for item in fields(output):
        tensor = getattr(output, item.name)
        assert tensor.shape == (two if item.name == "flow" else one), item.name
        assert torch.isfinite(tensor).all(), item.name
    for name in (
        "boundary_confidence",
        "correction_need",
        "recoverability",
        "uncertainty",
        "width_reliability",
        "shift_reliability",
        "geometry_gate",
        "width_gate",
        "shift_gate",
        "profile_visibility",
        "profile_band",
        "profile_gate",
    ):
        tensor = getattr(output, name)
        assert float(tensor.min()) >= 0.0, name
        assert float(tensor.max()) <= 1.0, name
    assert float(output.width_gain.min()) >= 1.0
    assert float(output.width_gain.max()) <= 3.5
    assert float(output.normal_shift.abs().max()) <= 1.5
    assert float(output.midpoint_offset.abs().max()) <= 24.0 / 255.0 + 1.0e-7
    assert float(output.signed_plateau_contrast.abs().max()) <= 72.0 / 255.0 + 1.0e-7
    assert float(output.profile_width.min()) >= 0.8
    assert float(output.profile_width.max()) <= 3.5
    assert float(output.profile_proposal_delta.abs().max()) <= 48.0 / 255.0 + 1.0e-7
    assert float(output.profile_delta.abs().max()) <= 48.0 / 255.0 + 1.0e-7
    assert torch.allclose(
        output.profile_gate,
        output.boundary_confidence
        * output.profile_visibility
        * output.profile_band,
        atol=1.0e-7,
        rtol=0,
    )
    assert float(output.output.min()) >= 0.0
    assert float(output.output.max()) <= 1.0
    normal_length = torch.sqrt(output.normal_x.square() + output.normal_y.square())
    assert torch.allclose(normal_length, torch.ones_like(normal_length), atol=2.0e-4, rtol=0)

    groups = model.parameter_groups()
    assert {
        "controller_backbone",
        "controller_geometry_heads",
            "recoverability_head",
        "width_reliability_head",
        "shift_reliability_head",
        "renderer_backbone",
        "width_action_head",
            "shift_action_head",
            "profile_midpoint_offset_head",
            "profile_signed_contrast_head",
            "profile_width_head",
            "profile_visibility_head",
    } == set(groups)
    ids = [id(parameter) for group in groups.values() for parameter in group]
    assert len(ids) == len(set(ids))
    assert set(ids) == {id(parameter) for parameter in model.parameters()}


def test_independent_reliability_heads_and_exact_gate_formulas() -> None:
    torch.manual_seed(114202)
    model = R114SplitProfileModel(small_config()).eval()
    assert model.controller.width_reliability_head is not model.controller.shift_reliability_head
    assert "controller.width_reliability_head.weight" in model.state_dict()
    assert "controller.shift_reliability_head.weight" in model.state_dict()

    # Force a high-width / low-shift quadrant.  Independent sigmoid heads must
    # not behave like a two-class softmax pair.
    with torch.no_grad():
        model.controller.width_reliability_head.weight.zero_()
        model.controller.width_reliability_head.bias.fill_(4.0)
        model.controller.shift_reliability_head.weight.zero_()
        model.controller.shift_reliability_head.bias.fill_(-4.0)
    value = structured_input()
    with torch.inference_mode():
        output = model.forward_details(value)
    assert float(output.width_reliability.mean()) > 0.98
    assert float(output.shift_reliability.mean()) < 0.02
    assert torch.allclose(
        output.geometry_gate,
        output.boundary_confidence * output.correction_need,
        atol=1.0e-7,
        rtol=0,
    )
    assert torch.allclose(
        output.width_gate,
        output.boundary_confidence * output.correction_need * output.width_reliability,
        atol=1.0e-7,
        rtol=0,
    )
    assert torch.allclose(
        output.shift_gate,
        output.boundary_confidence * output.correction_need * output.shift_reliability,
        atol=1.0e-7,
        rtol=0,
    )
    expected_flow = torch.cat(
        [
            output.normal_shift * output.normal_x * output.shift_gate,
            output.normal_shift * output.normal_y * output.shift_gate,
        ],
        dim=1,
    )
    assert torch.allclose(output.flow, expected_flow, atol=1.0e-7, rtol=0)


def test_low_reliability_is_exactly_neutral_and_legacy_gate_cannot_actuate() -> None:
    torch.manual_seed(114203)
    model = R114SplitProfileModel(small_config()).eval()
    raw = structured_input(60, 68)
    maps = manual_controller(
        raw,
        boundary=1.0,
        need=1.0,
        width_reliability=0.0,
        shift_reliability=0.0,
    )
    features = renderer_features(model, raw)
    width_gain = torch.full_like(raw, 3.5)
    normal_shift = torch.full_like(raw, 1.5)
    with torch.inference_mode():
        geometry = model.apply_geometry(raw, maps, width_gain, normal_shift, features)

    # The legacy diagnostic is fully on.  Exact identity therefore proves it
    # no longer controls either action path.
    assert torch.count_nonzero(geometry.geometry_gate != 1.0) == 0
    assert torch.count_nonzero(geometry.width_gate) == 0
    assert torch.count_nonzero(geometry.shift_gate) == 0
    assert torch.count_nonzero(geometry.flow) == 0
    assert torch.allclose(geometry.effective_width_gain, torch.ones_like(raw), atol=0, rtol=0)
    assert torch.count_nonzero(geometry.effective_normal_shift) == 0
    assert torch.allclose(geometry.shifted_base, raw, atol=1.0e-6, rtol=0)
    assert torch.allclose(geometry.base_output, raw, atol=1.0e-6, rtol=0)

    # A clear, well-localized edge may have high reliabilities.  Identity must
    # come from correction_need=0 rather than pretending the edge is unknown.
    clear_maps = manual_controller(
        raw,
        boundary=1.0,
        need=0.0,
        width_reliability=1.0,
        shift_reliability=1.0,
    )
    with torch.inference_mode():
        clear_geometry = model.apply_geometry(
            raw, clear_maps, width_gain, normal_shift, features
        )
    assert torch.count_nonzero(clear_geometry.width_gate) == 0
    assert torch.count_nonzero(clear_geometry.shift_gate) == 0
    assert torch.allclose(clear_geometry.base_output, raw, atol=1.0e-6, rtol=0)


def test_shift_and_width_actions_are_causally_decoupled() -> None:
    torch.manual_seed(114204)
    model = R114SplitProfileModel(small_config()).eval()
    raw = structured_input(64, 70)
    features = renderer_features(model, raw)
    gain_low = torch.ones_like(raw)
    gain_high = torch.full_like(raw, 3.25)
    shift_left = torch.full_like(raw, -1.1)
    shift_right = torch.full_like(raw, 1.1)

    # Pure shift: changing the width proposal cannot change the base output.
    shift_only = manual_controller(raw, width_reliability=0.0, shift_reliability=1.0)
    with torch.inference_mode():
        shift_a = model.apply_geometry(raw, shift_only, gain_low, shift_right, features)
        shift_b = model.apply_geometry(raw, shift_only, gain_high, shift_right, features)
    assert torch.allclose(shift_a.base_output, shift_a.shifted_base, atol=0, rtol=0)
    assert torch.allclose(shift_a.base_output, shift_b.base_output, atol=1.0e-7, rtol=0)
    assert float((shift_a.base_output - raw).abs().mean()) > 1.0e-4

    # Pure width: changing even an extreme shift proposal cannot move output.
    width_only = manual_controller(raw, width_reliability=1.0, shift_reliability=0.0)
    with torch.inference_mode():
        width_a = model.apply_geometry(raw, width_only, gain_high, shift_left, features)
        width_b = model.apply_geometry(raw, width_only, gain_high, shift_right, features)
    assert torch.count_nonzero(width_a.flow) == 0
    assert torch.allclose(width_a.shifted_base, raw, atol=1.0e-6, rtol=0)
    assert torch.allclose(width_a.base_output, width_b.base_output, atol=1.0e-7, rtol=0)
    assert float((width_a.base_output - raw).abs().mean()) > 1.0e-4
    assert torch.allclose(
        width_a.base_output,
        width_a.shifted_base + width_a.width_gate * (
            width_a.width_proposal - width_a.shifted_base
        ),
        atol=1.0e-7,
        rtol=0,
    )


def test_recoverability_is_isolated_from_geometry_actions() -> None:
    torch.manual_seed(114205)
    model = R114SplitProfileModel(small_config()).eval()
    raw = structured_input(58, 66)
    features = renderer_features(model, raw)
    width_gain = torch.full_like(raw, 2.4)
    normal_shift = torch.full_like(raw, 0.7)
    low = manual_controller(raw, recoverability=0.0)
    high = manual_controller(raw, recoverability=1.0)
    with torch.inference_mode():
        low_geometry = model.apply_geometry(raw, low, width_gain, normal_shift, features)
        high_geometry = model.apply_geometry(raw, high, width_gain, normal_shift, features)
    for name in ("width_gate", "shift_gate", "flow", "shifted_base", "base_output"):
        assert torch.allclose(
            getattr(low_geometry, name), getattr(high_geometry, name), atol=0, rtol=0
        ), name
    assert torch.count_nonzero(low.recoverability) == 0
    assert torch.count_nonzero(high.recoverability != 1.0) == 0


def test_profile_band_is_smooth_and_action_is_exactly_zero_outside_14px() -> None:
    model = R114SplitProfileModel(small_config()).eval()
    sdf_px = torch.tensor([[[[-15.0, -14.0, -12.0, -10.0, 0.0, 10.0, 12.0, 14.0, 15.0]]]])
    base = torch.full_like(sdf_px, 0.40)
    maps = manual_controller(
        base,
        recoverability=1.0,
        normalized_sdf=sdf_px / model.config.sdf_unit_scale_px,
    )
    with torch.inference_mode():
        action = model.apply_profile_action(
            base_output=base,
            controller=maps,
            midpoint_offset=torch.full_like(base, 18.0 / 255.0),
            signed_plateau_contrast=torch.full_like(base, 60.0 / 255.0),
            profile_width=torch.full_like(base, 1.35),
            profile_visibility=torch.ones_like(base),
            midpoint_source=base,
        )
    expected_band = torch.tensor([0.0, 0.0, 0.5, 1.0, 1.0, 1.0, 0.5, 0.0, 0.0])
    assert torch.allclose(action.profile_band.flatten(), expected_band, atol=1.0e-7, rtol=0)
    outside = sdf_px.abs() >= 14.0
    assert torch.count_nonzero(action.profile_gate[outside]) == 0
    assert torch.count_nonzero(action.profile_delta[outside]) == 0
    assert float(action.profile_delta.abs().max()) <= 48.0 / 255.0 + 1.0e-7


def test_signed_profile_contrast_preserves_and_reverses_polarity() -> None:
    model = R114SplitProfileModel(small_config()).eval()
    sdf_px = torch.linspace(-6.0, 6.0, 41).reshape(1, 1, 1, 41)
    base = torch.full_like(sdf_px, 0.50)
    maps = manual_controller(
        base,
        recoverability=1.0,
        normalized_sdf=sdf_px / model.config.sdf_unit_scale_px,
    )

    def apply(signed_gray: float):
        return model.apply_profile_action(
            base_output=base,
            controller=maps,
            midpoint_offset=torch.zeros_like(base),
            signed_plateau_contrast=torch.full_like(base, signed_gray / 255.0),
            profile_width=torch.full_like(base, 1.35),
            profile_visibility=torch.ones_like(base),
            midpoint_source=base,
        )

    with torch.inference_mode():
        positive = apply(60.0)
        negative = apply(-60.0)
    radius = model.config.local_range_window_px // 2
    interior = slice(radius, -radius)
    positive_line = positive.profile_delta[0, 0, 0, interior]
    negative_line = negative.profile_delta[0, 0, 0, interior]
    assert float(positive_line[0]) < 0 < float(positive_line[-1])
    assert float(negative_line[0]) > 0 > float(negative_line[-1])
    assert torch.allclose(positive_line, -negative_line, atol=1.0e-7, rtol=0)


def test_profile_gate_uses_boundary_visibility_and_band_without_double_suppression() -> None:
    model = R114SplitProfileModel(small_config()).eval()
    base = torch.full((1, 1, 19, 23), 0.40)
    offset = torch.full_like(base, 20.0 / 255.0)
    contrast = torch.full_like(base, 64.0 / 255.0)
    width = torch.full_like(base, 1.2)
    visibility = torch.ones_like(base)

    def run(**controller_values):
        values = {"recoverability": 1.0}
        values.update(controller_values)
        maps = manual_controller(base, **values)
        return model.apply_profile_action(
            base,
            maps,
            offset,
            contrast,
            width,
            visibility,
            midpoint_source=base,
        )

    with torch.inference_mode():
        active = run()
        boundary_off = run(boundary=0.0)
        need_off = run(need=0.0)
        recoverability_off = run(recoverability=0.0)
        visibility_off = model.apply_profile_action(
            base,
            manual_controller(base, recoverability=1.0),
            offset,
            contrast,
            width,
            torch.zeros_like(base),
            midpoint_source=base,
        )
        band_off = run(normalized_sdf=15.0 / model.config.sdf_unit_scale_px)
    assert float(active.profile_delta.abs().max()) > 1.0e-4
    for name, action in {
        "boundary": boundary_off,
        "visibility": visibility_off,
        "band": band_off,
    }.items():
        assert torch.count_nonzero(action.profile_gate) == 0, name
        assert torch.count_nonzero(action.profile_delta) == 0, name
        assert torch.equal(action.profile_output, base), name
    # Visibility is itself trained as the counterfactual usefulness estimate.
    # Reusing need/recoverability here suppressed the same evidence twice and
    # was a measured cause of the E24 failure.
    assert torch.allclose(need_off.profile_gate, active.profile_gate, atol=1.0e-7, rtol=0)
    assert torch.allclose(
        recoverability_off.profile_gate,
        active.profile_gate,
        atol=1.0e-7,
        rtol=0,
    )


def test_profile_heads_and_active_action_have_input_gradients() -> None:
    torch.manual_seed(114210)
    model = R114SplitProfileModel(small_config()).eval()
    with torch.no_grad():
        model.profile_visibility_head.weight.normal_(mean=0.0, std=0.02)
        model.profile_visibility_head.bias.fill_(1.0)
    value = structured_input(57, 63).requires_grad_(True)
    output = model.forward_details(value)
    spatial_weight = torch.linspace(0.5, 1.5, 57 * 63).reshape(1, 1, 57, 63)
    maps = {
        "midpoint_offset": output.midpoint_offset,
        "signed_plateau_contrast": output.signed_plateau_contrast,
        "profile_width": output.profile_width,
        "profile_visibility": output.profile_visibility,
        "profile_output": output.profile_output,
    }
    for index, (name, tensor) in enumerate(maps.items()):
        gradient = torch.autograd.grad(
            (tensor * spatial_weight).mean(),
            value,
            retain_graph=index < len(maps) - 1,
        )[0]
        assert torch.isfinite(gradient).all(), name
        assert float(gradient.abs().sum()) > 1.0e-8, name

    model.zero_grad(set_to_none=True)
    output = model.forward_details(value.detach())
    head_loss = (
        (output.midpoint_offset * spatial_weight).mean()
        + (output.signed_plateau_contrast * spatial_weight).mean()
        + (output.profile_width * spatial_weight).mean()
        + (output.profile_visibility * spatial_weight).mean()
    )
    head_loss.backward()
    for head in (
        model.profile_midpoint_offset_head,
        model.profile_signed_contrast_head,
        model.profile_width_head,
        model.profile_visibility_head,
    ):
        assert head.weight.grad is not None
        assert torch.isfinite(head.weight.grad).all()
        assert float(head.weight.grad.abs().sum()) > 1.0e-8


def test_new_reliability_maps_have_input_and_head_gradients() -> None:
    torch.manual_seed(114206)
    model = R114SplitProfileModel(small_config()).eval()
    value = structured_input(62, 67).requires_grad_(True)
    controller = model.controller(value)
    spatial_weight = torch.linspace(0.4, 1.6, 62 * 67).reshape(1, 1, 62, 67)
    maps = {
        "width_reliability": controller.width_reliability,
        "shift_reliability": controller.shift_reliability,
        "width_gate": controller.width_gate,
        "shift_gate": controller.shift_gate,
    }
    for index, (name, tensor) in enumerate(maps.items()):
        gradient = torch.autograd.grad(
            (tensor * spatial_weight).mean(),
            value,
            retain_graph=index < len(maps) - 1,
        )[0]
        assert torch.isfinite(gradient).all(), name
        assert float(gradient.abs().sum()) > 1.0e-8, name

    model.zero_grad(set_to_none=True)
    controller = model.controller(value.detach())
    (controller.width_reliability.mean() + controller.shift_reliability.mean()).backward()
    for head in (
        model.controller.width_reliability_head,
        model.controller.shift_reliability_head,
    ):
        assert head.weight.grad is not None
        assert torch.isfinite(head.weight.grad).all()
        assert float(head.weight.grad.abs().sum()) > 1.0e-8


def test_full_and_tiled_outputs_match_with_real_interior_tiles() -> None:
    torch.manual_seed(114207)
    model = R114SplitProfileModel(small_config()).eval()
    with torch.no_grad():
        model.profile_visibility_head.weight.normal_(mean=0.0, std=0.02)
        model.profile_visibility_head.bias.fill_(1.0)
        model.profile_signed_contrast_head.bias.fill_(0.5)
    # 83x91 is larger than 2*halo + core, so interior tiles do not silently
    # degenerate into whole-image calls.
    value = structured_input(83, 91)
    assert value.shape[-2] > 2 * model.minimum_halo_px + 27
    with torch.inference_mode():
        full = model.forward_details(value)
        tiled = forward_tiled_split(model, value, core_size=27)
    assert float(full.profile_delta.abs().max()) > 1.0e-6
    for item in fields(full):
        name = item.name
        error = (getattr(full, name) - getattr(tiled, name)).abs().max()
        assert float(error) <= 2.0e-5, f"{name}: {float(error)}"


def test_local_modules_no_free_residual_and_fresh_scratch_initialization() -> None:
    torch.manual_seed(114208)
    first = R114SplitProfileModel(small_config()).eval()
    value = structured_input(60, 64)
    with torch.inference_mode():
        output = first.forward_details(value)
    assert torch.count_nonzero(output.profile_visibility) == 0
    assert torch.count_nonzero(output.profile_gate) == 0
    assert torch.count_nonzero(output.profile_delta) == 0
    assert torch.equal(output.profile_output, output.base_output)
    assert torch.equal(output.output, output.profile_output)

    forbidden = (
        nn.GroupNorm,
        nn.BatchNorm2d,
        nn.InstanceNorm2d,
        nn.AdaptiveAvgPool2d,
        nn.AdaptiveMaxPool2d,
    )
    assert not any(isinstance(module, forbidden) for module in first.modules())
    names = " ".join(first.state_dict()).lower()
    assert "raw_anchor" not in names
    assert "checkpoint" not in names
    assert "detail_head" not in names
    assert "residual_head" not in names
    renderer_radius = first.renderer_cues.maximum_radius + 1 + 2 * sum(
        block.first.conv.dilation[0] for block in first.renderer_tower
    )
    required_action_radius = (
        renderer_radius
        + first.width_profile_action.action_radius_px
        + int(torch.ceil(torch.tensor(first.config.maximum_normal_shift_px)).item())
        + first.config.local_range_window_px // 2
    )
    assert first.minimum_halo_px >= required_action_radius

    torch.manual_seed(114209)
    second = build_split_profile_model(config=small_config())
    assert set(first.state_dict()) == set(second.state_dict())
    assert any(
        not torch.equal(first.state_dict()[name], second.state_dict()[name])
        for name in first.state_dict()
        if first.state_dict()[name].is_floating_point()
    )
