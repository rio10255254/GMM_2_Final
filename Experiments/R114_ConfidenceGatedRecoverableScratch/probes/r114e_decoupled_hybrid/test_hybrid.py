from __future__ import annotations

import json
from pathlib import Path

import torch

from model.r114_split_profile_model import R114SplitProfileModel, SplitProfileConfig
from probes.r114d_action_selector.model import SelectorConfig
from probes.r114e_decoupled_hybrid.model import R114EDecoupledHybrid


def _compact_pair() -> R114EDecoupledHybrid:
    config = SplitProfileConfig(
        base_channels=8,
        dilations=(1, 2, 1),
        blur_scales_px=(0.8, 1.4),
        minimum_halo_px=24,
        local_range_window_px=5,
    )
    torch.manual_seed(1146101)
    e20 = R114SplitProfileModel(config)
    torch.manual_seed(1146102)
    e24 = R114SplitProfileModel(config)
    with torch.no_grad():
        e24.profile_visibility_head.bias.fill_(1.0)
        e24.profile_signed_contrast_head.bias.fill_(0.5)
    return R114EDecoupledHybrid(
        e20,
        e24,
        SelectorConfig(channels=8, dilations=(1, 2, 1)),
    )


def _image(side: int = 64) -> torch.Tensor:
    yy, xx = torch.meshgrid(torch.arange(side), torch.arange(side), indexing="ij")
    return (0.25 + 0.55 * (((xx - side / 2) ** 2 + (yy - side / 2) ** 2) < 13**2)).float()[None, None]


def test_zero_selector_is_exact_e20_geometry_base() -> None:
    model = _compact_pair().eval()
    image = _image()
    with torch.inference_mode():
        output = model.forward_details(image)
        _, geometry = model._geometry_only(model.geometry_model, image)
    assert torch.equal(output.output, geometry.base_output)
    assert torch.count_nonzero(output.acceptance) == 0
    assert torch.count_nonzero(output.amount) == 0
    assert torch.count_nonzero(output.selected_delta) == 0


def test_e24_geometry_width_shift_and_forward_are_never_called(monkeypatch) -> None:
    model = _compact_pair().eval()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden E24 geometry path was called")
    monkeypatch.setattr(model.profile_model, "forward_details", forbidden)
    monkeypatch.setattr(model.profile_model, "apply_geometry", forbidden)
    monkeypatch.setattr(model.profile_model.controller, "forward", forbidden)
    monkeypatch.setattr(model.profile_model.width_head, "forward", forbidden)
    monkeypatch.setattr(model.profile_model.shift_head, "forward", forbidden)
    with torch.inference_mode():
        output = model.forward_details(_image())
    assert torch.isfinite(output.profile_proposal).all()


def test_full_gate_is_exact_required_product_and_bound_is_preserved() -> None:
    model = _compact_pair().eval()
    with torch.no_grad():
        model.selector.acceptance_head.bias.fill_(1.0)
        model.selector.amount_head.bias.fill_(1.0)
    with torch.inference_mode():
        output = model.forward_details(_image())
    required = (
        output.boundary_confidence
        * output.correction_need
        * output.recoverability
        * output.acceptance
        * output.amount
    )
    assert torch.equal(output.causal_gate, required)
    assert torch.equal(output.profile_gate, required * output.profile_band)
    assert float(output.proposal_delta.abs().max()) <= 48.0 / 255.0 + 1e-7
    assert float(output.selected_delta.abs().max()) <= 48.0 / 255.0 + 1e-7


def test_only_selector_is_trainable() -> None:
    model = _compact_pair()
    assert not any(p.requires_grad for p in model.geometry_model.parameters())
    assert not any(p.requires_grad for p in model.profile_model.parameters())
    assert all(p.requires_grad for p in model.selector.parameters())


def test_config_locks_both_source_hashes() -> None:
    root = Path(__file__).resolve().parent
    payload = json.loads((root / "config.json").read_text(encoding="utf-8"))
    assert payload["geometry_checkpoint_sha256"] == "887a494ca1ff23b19399608ecfb7f095abcff6818eba95f0d6bec4da575562b4"
    assert payload["profile_checkpoint_sha256"] == "909439fad61df63da628db33ed2f93974c2fdc2b18ac11da98d3058bb595e311"

