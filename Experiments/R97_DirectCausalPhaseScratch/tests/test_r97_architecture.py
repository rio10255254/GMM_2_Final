from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest
import torch


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load("r97_test_model", ROOT / "model" / "r97_model.py")
INFERENCE = load("r97_test_inference", ROOT / "inference" / "reconstruct.py")
PERIODIC = load("r97_test_periodic", ROOT / "training" / "periodic_disambiguation.py")


def test_identity_initialization_and_contract():
    torch.manual_seed(97)
    model = MODEL.build_model(base=8).eval()
    source = torch.rand(1, 1, 127, 139)
    with torch.no_grad():
        details = model(source, return_details=True)
    assert torch.equal(details["output"], source)
    assert torch.count_nonzero(details["correction"]) == 0
    contract = MODEL.architecture_contract(model)
    assert contract["learned_amplitude_gate_present"] is False
    assert contract["branches_predict_applied_correction_directly"] is True
    assert contract["texture_is_source_phase_locked"] is True
    assert contract["learned_parameter_group_overlap"] is False


def test_texture_is_linear_combination_of_source_bands():
    torch.manual_seed(9701)
    model = MODEL.build_model(base=8).eval()
    source = torch.rand(1, 1, 128, 128)
    with torch.no_grad():
        model.texture_head.weight.normal_(0.0, 0.02)
        model.texture_head.bias.fill_(0.03)
        details = model(source, return_details=True)
    recomposed = (details["texture_coefficients"] * details["texture_candidates"]).sum(dim=1, keepdim=True)
    # Envelope limiting may only shrink the candidate, never create an
    # independent texture phase.  Sign agreement therefore remains exact
    # wherever the final correction is nonzero.
    active = details["texture_delta"].abs() > 1e-8
    assert torch.all(details["texture_delta"][active] * recomposed[active] >= 0)


def test_full_and_tiled_outputs_are_exact_after_nonzero_activation():
    torch.manual_seed(9702)
    model = MODEL.build_model(base=4).eval()
    with torch.no_grad():
        for head in (
            model.radiometry_head, model.nuisance_head, model.local_contrast_head,
            model.boundary_head, model.texture_head, model.geometry_head,
        ):
            head.weight.normal_(0.0, 0.01)
            head.bias.normal_(0.0, 0.01)
    source = torch.rand(1, 1, 197, 213)
    full = INFERENCE.reconstruct_full_reference(model, source, core_size=64, halo=192)
    tiled = INFERENCE.reconstruct_tensor(model, source, core_size=64, halo=192, tile_batch=2)
    assert torch.equal(full, tiled)


def test_periodic_generator_is_deterministic_and_contains_shift_pairs():
    first = PERIODIC.make_periodic_batch(2, 128, 9703)
    second = PERIODIC.make_periodic_batch(2, 128, 9703)
    assert torch.equal(first.source, second.source)
    assert torch.equal(first.target, second.target)
    assert first.source.shape == (4, 1, 128, 128)
    assert first.shift_xy.abs().max() > 0
    assert first.period_xy.min() >= 24


def test_wrong_period_margin_prefers_true_shift_for_clean_targets():
    batch = PERIODIC.make_periodic_batch(4, 192, 9704)
    loss, metrics = PERIODIC.wrong_period_margin_loss(
        batch.target, batch.shift_xy, batch.period_xy,
    )
    assert torch.isfinite(loss)
    assert float(metrics["match_margin"]) > 0.01
    assert float(metrics["wrong_pitch_rate"]) <= 0.25


def test_phase_anchor_backward_is_finite_on_flat_and_edged_regions():
    flat = torch.full((1, 1, 128, 128), 0.5, requires_grad=True)
    edge = torch.zeros((1, 1, 128, 128), requires_grad=True)
    with torch.no_grad():
        edge[..., 48:80, 40:88] = 0.8
    source = torch.cat([flat.detach(), edge.detach()], dim=0)
    output = torch.cat([flat, edge], dim=0)
    loss = PERIODIC.phase_anchor_loss(source, output)
    loss.backward()
    assert torch.isfinite(loss)
    assert flat.grad is not None and torch.isfinite(flat.grad).all()
    assert edge.grad is not None and torch.isfinite(edge.grad).all()


def test_periodic_similarity_backward_is_finite_for_constant_inputs():
    reference = torch.zeros((1, 3, 128, 128))
    moved = torch.zeros((1, 3, 128, 128), requires_grad=True)
    score = PERIODIC._normalized_similarity(reference, moved).sum()
    score.backward()
    assert torch.isfinite(score)
    assert moved.grad is not None and torch.isfinite(moved.grad).all()


@pytest.mark.parametrize("height,width", [(128, 128), (135, 141)])
def test_shift_equivariance_on_valid_interior(height: int, width: int):
    torch.manual_seed(height + width)
    model = MODEL.build_model(base=4).eval()
    with torch.no_grad():
        for head in (model.boundary_head, model.texture_head, model.local_contrast_head):
            head.weight.normal_(0.0, 0.01)
            head.bias.normal_(0.0, 0.01)
    source = torch.rand(1, 1, height + 192, width + 192)
    shift = (8, -8)
    original = model(source)
    moved = model(torch.roll(source, shifts=shift, dims=(-2, -1)))
    expected = torch.roll(original, shifts=shift, dims=(-2, -1))
    assert float((moved[..., 72:-72, 72:-72] - expected[..., 72:-72, 72:-72]).abs().max()) < 1e-5
