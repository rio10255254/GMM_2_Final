from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.split_profile_losses import (
    analytic_profile_image,
    profile_parameter_components,
    profile_parameter_objective,
    reliability_components,
    shift_action_components,
    shift_action_objective,
    shift_reliability_objective,
    width_action_components,
    width_action_objective,
    width_reliability_objective,
)
from training.split_profile_targets import (
    MAXIMUM_CONTRAST_GRAY,
    MAXIMUM_MIDPOINT_OFFSET_GRAY,
    MAXIMUM_NORMAL_SHIFT_PX,
    MAXIMUM_PROFILE_WIDTH_PX,
    MAXIMUM_WIDTH_GAIN,
    MINIMUM_PROFILE_WIDTH_PX,
    MINIMUM_WIDTH_GAIN,
    build_split_profile_targets,
)


def _edge(sdf: torch.Tensor, contrast: float, width: float, shift: float = 0.0) -> torch.Tensor:
    return 0.48 + 0.5 * contrast * torch.tanh((sdf - shift) / width)


def synthetic_cases(side: int = 72) -> dict[str, torch.Tensor]:
    yy, xx = torch.meshgrid(
        torch.arange(side, dtype=torch.float32),
        torch.arange(side, dtype=torch.float32),
        indexing="ij",
    )
    sdf_edge = (xx - side / 2).reshape(1, 1, side, side)
    # Keep the clean edge inside the contractual 72-gray profile range.
    target_edge = _edge(sdf_edge, contrast=0.24, width=1.0)

    # Strong normal-profile evidence despite a smooth illumination field.
    illumination = 0.10 * (yy / (side - 1) - 0.5).reshape(1, 1, side, side)
    uneven = (_edge(sdf_edge, contrast=0.22, width=2.5, shift=0.65) + illumination).clamp(0, 1)

    # Same geometric displacement, but the edge is too weak/noisy to localize.
    ripple = 0.010 * torch.sin(2.1 * xx).reshape(1, 1, side, side)
    low_contrast = (_edge(sdf_edge, contrast=0.015, width=3.0, shift=0.65) + ripple).clamp(0, 1)

    # Boundary-fade removes evidence near the transition while preserving the
    # remote plateaus, so the bounded clean profile should improve identity.
    fade_factor = 1.0 - 0.82 * torch.exp(-sdf_edge.abs() / 3.2)
    faded = (0.48 + (target_edge - 0.48) * fade_factor).clamp(0, 1)
    identity = target_edge.clone()
    flat = torch.full_like(target_edge, 0.41)

    source = torch.cat((uneven, low_contrast, faded, identity, flat), dim=0)
    target = torch.cat((target_edge, target_edge, target_edge, identity, flat), dim=0)
    sdf = torch.cat((sdf_edge, sdf_edge, sdf_edge, sdf_edge, torch.zeros_like(sdf_edge)), dim=0)
    return {
        "source": source,
        "target": target,
        "sdf": sdf,
        "identity": torch.tensor([False, False, False, True, False]),
        "flat": torch.tensor([False, False, False, False, True]),
    }


def _band_mean(value: torch.Tensor, band: torch.Tensor, index: int) -> float:
    weight = band[index]
    return float((value[index] * weight).sum() / weight.sum().clamp_min(1.0e-6))


def test_targets_are_finite_bounded_and_neutral_where_required() -> None:
    targets = build_split_profile_targets(**synthetic_cases())
    for name, value in targets.__dict__.items():
        if isinstance(value, torch.Tensor):
            assert torch.isfinite(value).all(), name

    assert float(targets.width_gain.min()) >= MINIMUM_WIDTH_GAIN
    assert float(targets.width_gain.max()) <= MAXIMUM_WIDTH_GAIN
    assert float(targets.normal_shift.abs().max()) <= MAXIMUM_NORMAL_SHIFT_PX
    assert float(targets.midpoint_offset.abs().max()) <= MAXIMUM_MIDPOINT_OFFSET_GRAY / 255.0 + 1.0e-7
    assert float(targets.signed_plateau_contrast.abs().max()) <= MAXIMUM_CONTRAST_GRAY / 255.0 + 1.0e-7
    assert float(targets.profile_width.min()) >= MINIMUM_PROFILE_WIDTH_PX
    assert float(targets.profile_width.max()) <= MAXIMUM_PROFILE_WIDTH_PX
    for value in (
        targets.width_reliability,
        targets.shift_reliability,
        targets.profile_visibility,
        targets.profile_reliability,
    ):
        assert float(value.min()) >= 0.0
        assert float(value.max()) <= 1.0

    # Clear identity can remain identifiable, but every action target is exact
    # identity.  Flat has neither geometry support nor reliability.
    assert torch.equal(targets.width_gain[3], torch.ones_like(targets.width_gain[3]))
    assert torch.count_nonzero(targets.normal_shift[3]) == 0
    assert torch.count_nonzero(targets.midpoint_offset[3]) == 0
    assert torch.count_nonzero(targets.profile_visibility[3]) == 0
    assert torch.count_nonzero(targets.boundary_band[4]) == 0
    assert torch.count_nonzero(targets.width_reliability[4]) == 0
    assert torch.count_nonzero(targets.shift_reliability[4]) == 0
    assert torch.count_nonzero(targets.profile_visibility[4]) == 0
    assert torch.allclose(
        targets.width_weight,
        targets.boundary_band * targets.profile_sample_validity,
        atol=1.0e-7,
        rtol=0.0,
    )


def test_shift_reliability_separates_low_contrast_from_uneven_illumination() -> None:
    targets = build_split_profile_targets(**synthetic_cases())
    uneven = _band_mean(targets.shift_reliability, targets.boundary_band, 0)
    low_contrast = _band_mean(targets.shift_reliability, targets.boundary_band, 1)
    assert uneven > low_contrast + 0.08, (uneven, low_contrast)
    # Both scenes keep a nonzero signed oracle target; uncertainty is expressed
    # by reliability, not by falsifying the shift label to zero.
    assert abs(_band_mean(targets.normal_shift, targets.boundary_band, 1)) > 0.10


def test_boundary_fade_activates_bounded_profile_visibility() -> None:
    targets = build_split_profile_targets(**synthetic_cases())
    fade_visibility = _band_mean(targets.profile_visibility, targets.boundary_band, 2)
    assert fade_visibility > 0.10, fade_visibility
    assert torch.count_nonzero(targets.profile_visibility[3]) == 0


def test_dark_edge_keeps_signed_polarity_and_shift_direction() -> None:
    side = 64
    _yy, xx = torch.meshgrid(
        torch.arange(side, dtype=torch.float32),
        torch.arange(side, dtype=torch.float32),
        indexing="ij",
    )
    sdf = (xx - side / 2).reshape(1, 1, side, side)
    target = _edge(sdf, contrast=-0.24, width=1.0)
    source = _edge(sdf, contrast=-0.22, width=2.4, shift=0.70)
    targets = build_split_profile_targets(
        source=source,
        target=target,
        sdf=sdf,
        identity=torch.tensor([False]),
        flat=torch.tensor([False]),
    )
    center = targets.boundary_binary.bool()
    assert float(targets.signed_plateau_contrast[center].median()) < 0.0
    assert float(targets.normal_shift[center].median()) > 0.10
    assert float(targets.shift_reliability[center].median()) > 0.0


def test_midpoint_target_uses_the_same_geometry_base_cue_as_runtime() -> None:
    side = 64
    _yy, xx = torch.meshgrid(
        torch.arange(side, dtype=torch.float32),
        torch.arange(side, dtype=torch.float32),
        indexing="ij",
    )
    sdf = (xx - side / 2).reshape(1, 1, side, side)
    target = _edge(sdf, contrast=0.20, width=1.0)
    source = _edge(sdf, contrast=0.18, width=2.4) - 0.03
    # Deliberately make the frozen geometry-base cue differ from raw/source.
    base_output = (source + 0.04).clamp(0, 1)
    midpoint_source = (source + 0.07).clamp(0, 1)
    targets = build_split_profile_targets(
        source=source,
        target=target,
        sdf=sdf,
        identity=torch.tensor([False]),
        flat=torch.tensor([False]),
        base_output=base_output,
        midpoint_source=midpoint_source,
    )
    padded = F.pad(midpoint_source, (10, 10, 10, 10), mode="replicate")
    expected_cue = 0.5 * (
        F.max_pool2d(padded, 21, stride=1)
        - F.max_pool2d(-padded, 21, stride=1)
    )
    assert torch.equal(targets.raw_midpoint_cue, expected_cue)
    predictions = SimpleNamespace(
        midpoint_offset=targets.midpoint_offset,
        signed_plateau_contrast=targets.signed_plateau_contrast,
        profile_width=targets.profile_width,
    )
    proposal = analytic_profile_image(predictions, targets)
    center = targets.boundary_binary.bool()
    # The action midpoint must align to clean truth even though source and base
    # have different local midpoint cues.
    target_midpoint = float(target[center].median())
    proposal_midpoint = float(proposal[center].median())
    assert abs(proposal_midpoint - target_midpoint) < 0.01
    source_cue_error = float((targets.raw_midpoint_cue[center] - source[center]).abs().median())
    assert source_cue_error > 0.03


def _dummy_predictions(targets):
    shape = targets.width_gain.shape
    leaves = {
        "width_rel": torch.nn.Parameter(torch.full(shape, -0.35)),
        "shift_rel": torch.nn.Parameter(torch.full(shape, 0.15)),
        "width": torch.nn.Parameter(torch.full(shape, -0.20)),
        "shift": torch.nn.Parameter(torch.full(shape, 0.22)),
        "midpoint": torch.nn.Parameter(torch.full(shape, 0.18)),
        "contrast": torch.nn.Parameter(torch.full(shape, -0.14)),
        "profile_width": torch.nn.Parameter(torch.full(shape, 0.28)),
        "visibility": torch.nn.Parameter(torch.full(shape, -0.25)),
    }
    midpoint_offset = (24.0 / 255.0) * torch.tanh(leaves["midpoint"])
    signed_contrast = (72.0 / 255.0) * torch.tanh(leaves["contrast"])
    profile_width = 0.8 + 2.7 * torch.sigmoid(leaves["profile_width"])
    profile_visibility = torch.sigmoid(leaves["visibility"])
    proposal = (
        targets.raw_midpoint_cue
        + midpoint_offset
        + 0.5 * signed_contrast * torch.tanh(targets.deployment_sdf / profile_width)
    ).clamp(0, 1)
    proposal_delta = (proposal - targets.base_image).clamp(-48.0 / 255.0, 48.0 / 255.0)
    profile_gate = targets.deployment_band * profile_visibility
    profile_output = (targets.base_image + profile_gate * proposal_delta).clamp(0, 1)
    prediction = SimpleNamespace(
        width_reliability=torch.sigmoid(leaves["width_rel"]),
        shift_reliability=torch.sigmoid(leaves["shift_rel"]),
        width_gain=1.0 + 2.5 * torch.sigmoid(leaves["width"]),
        normal_shift=1.5 * torch.tanh(leaves["shift"]),
        midpoint_offset=midpoint_offset,
        signed_plateau_contrast=signed_contrast,
        profile_width=profile_width,
        profile_visibility=profile_visibility,
        profile_proposal=proposal,
        profile_output=profile_output,
        output=profile_output,
    )
    return prediction, leaves


def test_visibility_uses_deployment_coordinate_and_rejects_wrong_direction() -> None:
    cases = synthetic_cases(side=64)
    base = cases["source"]
    boundary = torch.ones_like(base)
    aligned = build_split_profile_targets(
        **cases,
        base_output=base,
        midpoint_source=base,
        deployment_sdf_px=cases["sdf"],
        deployment_boundary_confidence=boundary,
    )
    # Flip the inference coordinate without changing paired truth.  The old
    # true-SDF proposal incorrectly kept the same positive visibility label;
    # the deployment-aligned counterfactual must now suppress it.
    wrong = build_split_profile_targets(
        **cases,
        base_output=base,
        midpoint_source=base,
        deployment_sdf_px=-cases["sdf"],
        deployment_boundary_confidence=boundary,
    )
    fade = 2
    aligned_visibility = _band_mean(
        aligned.profile_visibility,
        aligned.profile_visibility_weight,
        fade,
    )
    wrong_visibility = _band_mean(
        wrong.profile_visibility,
        wrong.profile_visibility_weight,
        fade,
    )
    assert aligned_visibility > wrong_visibility + 0.10, (
        aligned_visibility,
        wrong_visibility,
    )
    assert _band_mean(wrong.coordinate_reliability, wrong.boundary_band, fade) < 0.05


def test_each_stage_loss_is_finite_and_has_its_own_gradients() -> None:
    targets = build_split_profile_targets(**synthetic_cases(side=64))

    prediction, leaves = _dummy_predictions(targets)
    reliability = reliability_components(prediction, targets)
    reliability_total = width_reliability_objective(reliability) + shift_reliability_objective(reliability)
    assert torch.isfinite(reliability_total)
    reliability_total.backward()
    assert leaves["width_rel"].grad is not None and float(leaves["width_rel"].grad.abs().sum()) > 0
    assert leaves["shift_rel"].grad is not None and float(leaves["shift_rel"].grad.abs().sum()) > 0

    prediction, leaves = _dummy_predictions(targets)
    width_total = width_action_objective(width_action_components(prediction, targets))
    assert torch.isfinite(width_total)
    width_total.backward()
    assert leaves["width"].grad is not None and float(leaves["width"].grad.abs().sum()) > 0
    assert leaves["shift"].grad is None

    prediction, leaves = _dummy_predictions(targets)
    shift_total = shift_action_objective(shift_action_components(prediction, targets))
    assert torch.isfinite(shift_total)
    shift_total.backward()
    assert leaves["shift"].grad is not None and float(leaves["shift"].grad.abs().sum()) > 0
    assert leaves["width"].grad is None

    prediction, leaves = _dummy_predictions(targets)
    profile_total = profile_parameter_objective(profile_parameter_components(prediction, targets))
    assert torch.isfinite(profile_total)
    profile_total.backward()
    for name in ("midpoint", "contrast", "profile_width", "visibility"):
        assert leaves[name].grad is not None and float(leaves[name].grad.abs().sum()) > 0, name
    assert leaves["width"].grad is None
    assert leaves["shift"].grad is None
