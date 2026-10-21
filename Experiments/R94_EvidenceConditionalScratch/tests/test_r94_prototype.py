from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_architecture_is_identity_and_private() -> None:
    module = load("r94_model_test", "model/r94_model.py")
    model = module.build_model(base=8).eval()
    image = torch.rand(1, 1, 96, 104)
    with torch.inference_mode():
        details = model(image, return_details=True)
    assert torch.equal(details["output"], image)
    assert torch.count_nonzero(details["correction"]) == 0
    contract = module.architecture_contract(model)
    assert contract["learned_parameter_group_overlap"] is False
    assert contract["independent_edge_painting_branch"] is False
    assert contract["all_correction_paths_controlled"] is True
    assert contract["boundary_and_texture_learned_towers_are_distinct"] is True
    assert contract["need_and_evidence_learned_towers_are_distinct"] is True


def test_counterfactual_clear_targets_are_exact_zero() -> None:
    module = load("r94_targets_test", "training/counterfactual_targets.py")
    target = torch.rand(1, 1, 96, 96)
    noise_free = module.lowpass(target, 3)
    noisy = (noise_free + 0.01 * torch.randn_like(target)).clamp(0, 1)
    views = module.build_counterfactual_views(target, noise_free, noisy)
    clear = views["T_clear"]
    for name in (
        "radiometry_component", "nuisance_component", "local_contrast_component",
        "boundary_component", "texture_component", "radiometry_effective", "nuisance_effective",
        "local_contrast_effective", "boundary_effective", "texture_effective",
        "restoration_raw", "restoration_effective", "need_radiometry", "need_noise",
        "need_local_contrast", "need_boundary", "need_texture",
    ):
        assert torch.count_nonzero(getattr(clear, name)) == 0
    assert torch.equal(clear.boundary_evidence, torch.ones_like(clear.boundary_evidence))
    assert torch.equal(clear.texture_recoverability, torch.ones_like(clear.texture_recoverability))
    assert torch.equal(clear.local_contrast_evidence, torch.ones_like(clear.local_contrast_evidence))


def test_common_descent_does_not_oppose_any_task() -> None:
    module = load("r94_descent_test", "training/common_descent.py")
    gradients = [torch.tensor([1.0, 0.0]), torch.tensor([-0.8, 0.6]), torch.tensor([0.2, 1.0])]
    direction = module.common_descent_direction(gradients, passes=12)
    assert all(float(torch.dot(direction, gradient)) >= -1e-7 for gradient in gradients)
