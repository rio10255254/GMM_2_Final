from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inference.tiled import forward_tiled
from model.r115_model import build_model, load_r109_for_probe
PROJECT_ROOT = Path(__file__).resolve().parents[3]


R109 = Path(
    str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch/weights/selected/R109.pth')
)


def fixture(height: int = 96, width: int = 104) -> torch.Tensor:
    yy, xx = torch.meshgrid(
        torch.arange(height, dtype=torch.float32),
        torch.arange(width, dtype=torch.float32),
        indexing="ij",
    )
    radius = torch.sqrt((xx - width * 0.53) ** 2 + (yy - height * 0.47) ** 2)
    image = 0.24 + 0.48 * torch.sigmoid(-(radius - 24.0) / 2.4)
    image += 0.035 * torch.sin(xx / 4.5) * torch.cos(yy / 7.0)
    return image.clamp(0, 1)[None, None]


def test_initial_profile_branch_is_exact_identity_on_actions() -> None:
    model = build_model().eval()
    details = model.forward_details(fixture())
    for name in ("shift_factor", "width_factor"):
        value = getattr(details, name)
        assert torch.equal(value, torch.ones_like(value)), name
    for name in ("shift_adjustment", "width_adjustment"):
        value = getattr(details, name)
        assert torch.equal(value, torch.zeros_like(value)), name
    assert torch.equal(details.output, details.baseline_output)


def test_r109_probe_load_reproduces_r109_output() -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    r109_path = Path(
        str(PROJECT_ROOT / 'Experiments/R109_StagedMidpointWidthScratch/model/r109_model.py')
    )
    spec = spec_from_file_location("r109_reference_model", r109_path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    saved = torch.load(R109, map_location="cpu", weights_only=False)
    reference = module.build_model().eval()
    reference.load_state_dict(saved["model"], strict=True)
    candidate = build_model().eval()
    metadata = load_r109_for_probe(candidate, R109)
    value = fixture()
    with torch.inference_mode():
        expected = reference(value)
        actual = candidate(value)
    assert metadata["epoch"] == 48
    assert float((actual - expected).abs().max()) <= 2.0e-6


def test_parameter_groups_are_disjoint_and_exhaustive() -> None:
    model = build_model()
    groups = [model.detector_parameters(), model.geometry_parameters(), model.profile_parameters()]
    identifiers = [{id(item) for item in group} for group in groups]
    assert not (identifiers[0] & identifiers[1])
    assert not (identifiers[0] & identifiers[2])
    assert not (identifiers[1] & identifiers[2])
    assert set.union(*identifiers) == {id(item) for item in model.parameters()}


def test_profile_loss_cannot_reach_geometry_parameters() -> None:
    model = build_model().train()
    value = fixture(64, 72)
    details = model.forward_details(value)
    loss = (
        details.shift_factor.mean()
        + details.width_factor.mean()
    )
    loss.backward()
    assert any(parameter.grad is not None for parameter in model.profile_parameters())
    assert all(parameter.grad is None for parameter in model.detector_parameters())
    assert all(parameter.grad is None for parameter in model.geometry_parameters())


def test_active_profile_heads_are_bounded_and_local() -> None:
    model = build_model().eval()
    with torch.no_grad():
        for head in (
            model.shift_adjust_head,
            model.width_adjust_head,
        ):
            head.bias.fill_(0.8)
    details = model.forward_details(fixture())
    for name in ("shift_factor", "width_factor"):
        value = getattr(details, name)
        assert float(value.min()) >= 0.85 - 1.0e-6
        assert float(value.max()) <= 1.15 + 1.0e-6
    assert torch.isfinite(details.output).all()
    assert float(details.output.min()) >= 0.0
    assert float(details.output.max()) <= 1.0


def test_tiled_interior_matches_full() -> None:
    model = build_model().eval()
    value = fixture(520, 548)
    with torch.inference_mode():
        full = model(value)
        tiled = forward_tiled(model, value, core_size=256, halo=model.minimum_halo_px)
    # Physical outer-border padding differs by construction; the canonical
    # deployment comparison is the shared interior.
    margin = model.minimum_halo_px
    difference = (full - tiled).abs()[..., margin:-margin, margin:-margin]
    assert float(difference.max()) < 1.0e-4
