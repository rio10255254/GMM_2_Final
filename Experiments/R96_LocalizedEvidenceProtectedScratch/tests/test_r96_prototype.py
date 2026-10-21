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
    module = load("r96_model_test", "model/r96_model.py")
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
    module = load("r96_targets_test", "training/counterfactual_targets.py")
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
    zero = torch.zeros_like(target)
    assert torch.count_nonzero(module.local_energy(zero)) == 0
    assert torch.count_nonzero(module.exact_gate_target(zero)) == 0


def test_control_head_starts_trainable_without_changing_identity() -> None:
    model_module = load("r96_neutral_gate_model_test", "model/r96_model.py")
    trainer = load("r96_neutral_gate_trainer_test", "training/train_r96.py")
    model = model_module.build_model(base=8).train()
    image = torch.rand(2, 1, 64, 64)
    direct = model.forward_control_features(torch.cat([image, image, image], dim=0))
    count = image.shape[0]
    parts = [
        {name: value[offset * count:(offset + 1) * count] for name, value in direct.items()}
        for offset in range(3)
    ]
    zeros5 = torch.zeros(2, 5, 64, 64)
    ones5 = torch.ones(2, 5, 64, 64)
    ones3 = torch.ones(2, 3, 64, 64)
    batch = {
        "need_truth_s": ones5,
        "need_truth_t": zeros5,
        "need_truth_b": torch.cat([ones5[:, :1], zeros5[:, :1], ones5[:, 2:]], dim=1),
        "evidence_truth_s": ones3,
        "evidence_truth_t": ones3,
        "evidence_truth_b": ones3,
        "mask": (image > 0.5).float(),
        "boundary_support_truth": torch.zeros_like(image),
    }
    loss, _ = trainer.counterfactual_controls_loss(*parts, batch, 64, 64)
    loss.backward()
    assert float(model.need_head.bias.grad.abs().sum()) > 0.0
    with torch.inference_mode():
        assert torch.equal(model(image), image)


def test_common_descent_does_not_oppose_any_task() -> None:
    module = load("r96_descent_test", "training/common_descent.py")
    gradients = [torch.tensor([1.0, 0.0]), torch.tensor([-0.8, 0.6]), torch.tensor([0.2, 1.0])]
    direction = module.common_descent_direction(gradients, passes=12)
    assert all(float(torch.dot(direction, gradient)) >= -1e-7 for gradient in gradients)


def test_localized_branch_loss_keeps_sparse_target_gradient() -> None:
    trainer = load("r96_sparse_loss_test", "training/train_r96.py")
    prediction = torch.zeros(1, 1, 64, 64, requires_grad=True)
    truth = torch.zeros_like(prediction)
    truth = truth.clone()
    truth[..., 28:36, 28:36] = 0.08
    old = torch.nn.functional.smooth_l1_loss(prediction, truth, beta=1.0 / 255.0)
    old_gradient = torch.autograd.grad(old, prediction, retain_graph=True)[0].abs().sum()
    localized = trainer._localized_branch_loss(prediction, truth)
    localized_gradient = torch.autograd.grad(localized, prediction)[0].abs().sum()
    assert float(localized_gradient) > float(old_gradient) * 2.0
    zero = torch.zeros(1, 1, 64, 64, requires_grad=True)
    zero_loss = trainer._localized_branch_loss(zero, torch.zeros_like(zero))
    assert float(zero_loss) == 0.0


def test_control_separation_is_within_channel() -> None:
    trainer = load("r96_channel_control_test", "training/train_r96.py")
    logits = torch.zeros(1, 5, 16, 16, requires_grad=True)
    truth = torch.zeros_like(logits)
    for channel in range(5):
        truth[:, channel, 4:8, 4:8] = 0.55 + 0.10 * channel
    loss = trainer._soft_logit_loss(logits, truth)
    loss.backward()
    channel_gradients = logits.grad.abs().sum(dim=(0, 2, 3))
    assert bool(torch.all(channel_gradients > 0))

