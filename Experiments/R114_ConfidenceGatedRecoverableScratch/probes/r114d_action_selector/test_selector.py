from __future__ import annotations

from dataclasses import replace
import inspect
import json
from pathlib import Path
import sys

import torch


PROBE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PROBE_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from model.r114_split_profile_model import R114SplitProfileModel, SplitProfileConfig
from probes.r114d_action_selector.losses import selector_loss
from probes.r114d_action_selector.model import (
    R114DActionSelector,
    R114DOutput,
    SelectorConfig,
)
from probes.r114d_action_selector.targets import TargetConfig, build_selector_targets


def compact_model() -> R114DActionSelector:
    torch.manual_seed(1145101)
    proposal = R114SplitProfileModel(
        SplitProfileConfig(
            base_channels=8,
            dilations=(1, 2, 1),
            blur_scales_px=(0.8, 1.4),
            minimum_halo_px=24,
            local_range_window_px=5,
        )
    )
    with torch.no_grad():
        proposal.profile_visibility_head.bias.fill_(1.0)
        proposal.profile_signed_contrast_head.bias.fill_(0.6)
    proposal.requires_grad_(False).eval()
    return R114DActionSelector(
        proposal,
        SelectorConfig(channels=8, dilations=(1, 2, 1)),
    )


def structured(side: int = 64) -> torch.Tensor:
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, side),
        torch.linspace(-1.0, 1.0, side),
        indexing="ij",
    )
    return (0.3 + 0.5 * ((xx.square() + yy.square()) < 0.45).float()).reshape(1, 1, side, side)


def test_initial_acceptance_amount_and_action_are_exact_zero() -> None:
    model = compact_model().eval()
    with torch.inference_mode():
        output = model.forward_details(structured())
    assert torch.count_nonzero(output.acceptance) == 0
    assert torch.count_nonzero(output.amount) == 0
    assert torch.count_nonzero(output.causal_gate) == 0
    assert torch.count_nonzero(output.selected_delta) == 0
    assert torch.equal(output.output, output.base_output)


def test_gate_is_exact_required_product_and_e24_bound_is_preserved() -> None:
    model = compact_model().eval()
    with torch.no_grad():
        model.selector.acceptance_head.bias.fill_(1.0)
        model.selector.amount_head.bias.fill_(1.0)
    with torch.inference_mode():
        output = model.forward_details(structured())
    expected = (
        output.boundary_confidence
        * output.correction_need
        * output.recoverability
        * output.acceptance
        * output.amount
    )
    assert torch.allclose(output.causal_gate, expected, atol=0, rtol=0)
    assert torch.allclose(output.profile_gate, expected * output.profile_band, atol=0, rtol=0)
    assert float(output.proposal_delta.abs().max()) <= 48.0 / 255.0 + 1.0e-7
    assert float(output.selected_delta.abs().max()) <= 48.0 / 255.0 + 1.0e-7


def dummy_output(base: torch.Tensor, proposal_delta: torch.Tensor) -> R114DOutput:
    one = torch.ones_like(base)
    zero = torch.zeros_like(base)
    return R114DOutput(
        output=base,
        base_output=base,
        proposal_output=(base + proposal_delta).clamp(0, 1),
        proposal_delta=proposal_delta,
        acceptance_logit=zero,
        amount_logit=zero,
        acceptance=zero,
        amount=zero,
        boundary_confidence=one,
        correction_need=one,
        recoverability=one,
        profile_band=one,
        causal_gate=zero,
        profile_gate=zero,
        selected_delta=zero,
    )


def test_labels_use_signed_gain_and_exact_best_alpha_of_learned_proposal() -> None:
    base = torch.full((1, 1, 9, 11), 0.4)
    delta = torch.full_like(base, 0.2)
    target = base + 0.05  # exact alpha = 0.25
    sdf = torch.zeros_like(base)
    labels = build_selector_targets(
        dummy_output(base, delta),
        target,
        sdf,
        torch.tensor([False]),
        TargetConfig(
            boundary_band_px=12,
            gain_margin_gray_squared=0,
            clear_error_gray=0.1,
            minimum_candidate_delta_gray=0,
            minimum_positive_alpha=0,
        ),
    )
    assert torch.allclose(labels.best_alpha, torch.full_like(base, 0.25), atol=1.0e-6)
    assert torch.all(labels.signed_gain > 0)
    assert torch.all(labels.positive_mask)
    assert torch.allclose(labels.amount, torch.full_like(base, 0.25), atol=1.0e-6)


def test_harmful_clear_and_identity_are_conservative_negatives() -> None:
    base = torch.full((3, 1, 7, 7), 0.4)
    delta = torch.full_like(base, 0.1)
    target = torch.stack(
        [
            torch.full((1, 7, 7), 0.3),  # harmful direction
            torch.full((1, 7, 7), 0.4),  # already clear
            torch.full((1, 7, 7), 0.4),  # identity
        ]
    )
    labels = build_selector_targets(
        dummy_output(base, delta),
        target,
        torch.zeros_like(base),
        torch.tensor([False, False, True]),
    )
    assert torch.all(labels.harmful_negative_mask[0])
    assert torch.all(labels.clear_negative_mask[1])
    assert torch.all(labels.identity_negative_mask[2])
    assert torch.count_nonzero(labels.acceptance) == 0
    assert torch.count_nonzero(labels.amount) == 0


def test_background_never_enters_target_support_or_loss() -> None:
    base = torch.full((1, 1, 21, 21), 0.4)
    delta = torch.full_like(base, 0.1)
    target = base.clone()
    target[..., 9:12, :] = 0.45
    sdf = torch.full_like(base, 30.0)
    sdf[..., 9:12, :] = 0.0
    first = build_selector_targets(
        dummy_output(base, delta), target, sdf, torch.tensor([False])
    )
    changed_target = target.clone()
    changed_target[sdf.abs() > 12] = 0.95
    second = build_selector_targets(
        dummy_output(base, delta), changed_target, sdf, torch.tensor([False])
    )
    assert torch.count_nonzero(
        first.supervision_mask
        & ~first.boundary_band
        & ~first.identity_negative_mask
    ) == 0
    assert torch.equal(first.supervision_mask, second.supervision_mask)
    assert torch.equal(first.acceptance, second.acceptance)
    assert torch.equal(first.amount, second.amount)


def test_identity_hard_negatives_are_capped_and_only_exception_outside_true_band() -> None:
    base = torch.full((1, 1, 31, 31), 0.4)
    delta = torch.full_like(base, 0.1)
    sdf = torch.full_like(base, 30.0)
    sdf[..., 14:17, :] = 0.0
    labels = build_selector_targets(
        dummy_output(base, delta),
        base,
        sdf,
        torch.tensor([True]),
    )
    outside_identity = labels.identity_negative_mask & ~labels.boundary_band
    assert 0 < int(outside_identity.sum()) <= int(labels.boundary_band.sum())
    unauthorized = (
        labels.supervision_mask
        & ~labels.boundary_band
        & ~labels.identity_negative_mask
    )
    assert torch.count_nonzero(unauthorized) == 0


def test_gradients_are_selector_only_and_both_heads_can_leave_zero() -> None:
    model = compact_model().train()
    source = structured()
    prediction = model.forward_details(source)
    target = (prediction.base_output + 0.5 * prediction.proposal_delta.sign() * prediction.proposal_delta.abs()).clamp(0, 1)
    sdf = torch.zeros_like(source)
    labels = build_selector_targets(
        prediction,
        target,
        sdf,
        torch.tensor([False]),
        TargetConfig(
            gain_margin_gray_squared=0,
            clear_error_gray=0,
            minimum_candidate_delta_gray=0,
            minimum_positive_alpha=0,
        ),
    )
    losses = selector_loss(prediction, labels)
    losses.total.backward()
    assert model.selector.acceptance_head.weight.grad is not None
    assert model.selector.amount_head.weight.grad is not None
    assert float(model.selector.acceptance_head.weight.grad.abs().sum()) > 0
    assert float(model.selector.amount_head.weight.grad.abs().sum()) > 0
    assert all(parameter.grad is None for parameter in model.proposal.parameters())


def test_inference_has_no_target_argument_or_target_copy_path() -> None:
    model = compact_model().eval()
    signature = inspect.signature(model.forward_details)
    assert tuple(signature.parameters) == ("value",)
    source = structured()
    with torch.inference_mode():
        first = model.forward_details(source)
    # Build radically different training labels.  Since labels are outside the
    # inference module, they cannot alter any inference tensor.
    _ = build_selector_targets(
        first,
        torch.zeros_like(source),
        torch.zeros_like(source),
        torch.tensor([False]),
    )
    _ = build_selector_targets(
        first,
        torch.ones_like(source),
        torch.zeros_like(source),
        torch.tensor([False]),
    )
    with torch.inference_mode():
        second = model.forward_details(source)
    for field in first.__dataclass_fields__:
        assert torch.equal(getattr(first, field), getattr(second, field)), field


def test_selector_is_local_and_forbidden_global_modules_are_absent() -> None:
    model = compact_model().eval()
    forbidden = (
        torch.nn.BatchNorm2d,
        torch.nn.InstanceNorm2d,
        torch.nn.GroupNorm,
        torch.nn.AdaptiveAvgPool2d,
        torch.nn.AdaptiveMaxPool2d,
    )
    assert not any(isinstance(module, forbidden) for module in model.selector.modules())
    radius = model.selector_config.receptive_field_radius_px
    features = torch.zeros(1, 10, 49, 49)
    perturbed = features.clone()
    perturbed[..., 24, 24] = 1.0
    with torch.no_grad():
        model.selector.acceptance_head.weight.normal_(0, 0.1)
        first = model.selector(features)[0]
        second = model.selector(perturbed)[0]
    difference = (first - second).abs()[0, 0]
    yy, xx = torch.meshgrid(torch.arange(49), torch.arange(49), indexing="ij")
    outside = (yy - 24).abs().maximum((xx - 24).abs()) > radius
    assert torch.count_nonzero(difference[outside]) == 0


def test_config_is_pinned_to_sealed_e24_hash() -> None:
    payload = json.loads((PROBE_ROOT / "config.json").read_text(encoding="utf-8"))
    assert payload["required_proposal_epoch"] == 24
    assert payload["proposal_checkpoint_sha256"] == "909439fad61df63da628db33ed2f93974c2fdc2b18ac11da98d3058bb595e311"
