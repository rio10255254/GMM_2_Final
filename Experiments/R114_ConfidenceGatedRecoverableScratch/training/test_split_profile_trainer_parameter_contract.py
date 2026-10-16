from __future__ import annotations

from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r114_split_profile_model import build_split_profile_model
from training.train_split_profile import (
    CONFIG,
    assert_exact_parameter_set,
    assert_optimizer_parameter_contract,
    assert_step_parameter_contract,
    build_optimizers,
    compute_step,
    optimizer_parameters,
    select_optimizer,
    set_trainable,
)


def _synthetic_profile_batch(side: int = 48) -> dict[str, torch.Tensor]:
    _yy, xx = torch.meshgrid(
        torch.arange(side, dtype=torch.float32),
        torch.arange(side, dtype=torch.float32),
        indexing="ij",
    )
    sdf = (xx - side / 2).reshape(1, 1, side, side)
    clean = 0.48 + 0.12 * torch.tanh(sdf)
    fade = 1.0 - 0.82 * torch.exp(-sdf.abs() / 3.2)
    damaged = 0.48 + (clean - 0.48) * fade
    source = torch.cat((damaged, clean), dim=0)
    target = torch.cat((clean, clean), dim=0)
    sdf = torch.cat((sdf, sdf), dim=0)
    return {
        "source": source,
        "target": target,
        "sdf": sdf,
        "mask": (sdf >= 0).float(),
        "identity": torch.tensor([False, True]),
        "flat": torch.tensor([False, False]),
    }


def _fresh_compact_model():
    torch.manual_seed(114511)
    return build_split_profile_model(compact=True)


def _ids(parameters) -> set[int]:
    return {id(parameter) for parameter in parameters}


def _names(model, parameters) -> set[str]:
    selected = _ids(parameters)
    return {name for name, parameter in model.named_parameters() if id(parameter) in selected}


def _combined_profile_contract_objective(model, batch) -> torch.Tensor:
    objectives = []
    for objective_hit, objective_name in enumerate(CONFIG["objective_cycles"]["profile"]):
        objective, _metrics, _actual_name = compute_step(
            model,
            batch,
            "profile",
            1,
            1,
            objective_name,
            objective_hit,
            objective_hit + 1,
            False,
        )
        objectives.append(objective)
    return torch.stack(objectives).sum()


def test_profile_optimizer_is_exactly_the_model_profile_contract() -> None:
    model = _fresh_compact_model()
    optimizers, parameter_sets = build_optimizers(model)
    assert_optimizer_parameter_contract(model, optimizers, parameter_sets)
    assert_exact_parameter_set(
        model,
        "test profile optimizer",
        optimizer_parameters(optimizers["profile"]),
        model.profile_parameters(),
    )

    names = _names(model, parameter_sets["profile"])
    assert any(name.startswith("renderer_stem.") for name in names)
    assert any(name.startswith("renderer_tower.") for name in names)
    for prefix in (
        "profile_midpoint_offset_head.",
        "profile_signed_contrast_head.",
        "profile_width_head.",
        "profile_visibility_head.",
    ):
        assert any(name.startswith(prefix) for name in names), prefix
    assert not any(name.startswith("controller.") for name in names)
    assert not any(name.startswith("width_head.") for name in names)
    assert not any(name.startswith("shift_head.") for name in names)


def test_profile_and_joint_stages_activate_the_declared_optimizer_sets() -> None:
    model = _fresh_compact_model()
    optimizers, parameter_sets = build_optimizers(model)

    probes = [
        *(('profile', name, 0) for name in CONFIG["objective_cycles"]["profile"]),
        ("joint_refinement", "profile_guard", 0),
        ("joint_refinement", "geometry_guard", 0),
        ("joint_refinement", "geometry_guard", 1),
        ("joint_refinement", "translation", 0),
        ("joint_refinement", "translation", 1),
        ("joint_refinement", "exposure", 0),
        ("joint_refinement", "exposure", 1),
    ]
    for stage, objective_name, objective_hit in probes:
        optimizer_name = select_optimizer(stage, objective_name, objective_hit)
        set_trainable(model, parameter_sets[optimizer_name])
        assert_step_parameter_contract(
            model,
            stage,
            objective_name,
            objective_hit,
            optimizer_name,
            optimizers[optimizer_name],
            parameter_sets,
        )
        assert _ids(parameter for parameter in model.parameters() if parameter.requires_grad) == _ids(
            parameter_sets[optimizer_name]
        )

    assert select_optimizer("joint_refinement", "profile_guard", 0) == "profile"
    assert _ids(parameter_sets["profile"]) == _ids(model.profile_parameters())


def test_profile_contract_has_full_gradient_coverage_and_one_step_updates_only_it() -> None:
    model = _fresh_compact_model().train()
    batch = _synthetic_profile_batch()
    optimizers, parameter_sets = build_optimizers(model)
    optimizer = optimizers["profile"]
    profile_parameters = set_trainable(model, parameter_sets["profile"])
    assert_step_parameter_contract(
        model,
        "profile",
        "profile_parameters",
        0,
        "profile",
        optimizer,
        parameter_sets,
    )
    optimizer.zero_grad(set_to_none=True)
    before = {id(parameter): parameter.detach().clone() for parameter in model.parameters()}

    # This is one diagnostic optimizer step over the complete profile-stage
    # objective cycle.  It proves graph reachability for every parameter in
    # the contract without changing the real alternating training schedule.
    objective = _combined_profile_contract_objective(model, batch)
    assert torch.isfinite(objective)
    objective.backward()
    for parameter in profile_parameters:
        assert parameter.grad is not None
        assert torch.isfinite(parameter.grad).all()
        assert float(parameter.grad.abs().sum()) > 1.0e-12
    for parameter in model.parameters():
        if id(parameter) not in _ids(profile_parameters):
            assert parameter.grad is None

    optimizer.step()
    for parameter in profile_parameters:
        assert not torch.equal(parameter.detach(), before[id(parameter)])
    for parameter in model.parameters():
        if id(parameter) not in _ids(profile_parameters):
            assert torch.equal(parameter.detach(), before[id(parameter)])

    changed_names = {
        name
        for name, parameter in model.named_parameters()
        if not torch.equal(parameter.detach(), before[id(parameter)])
    }
    assert any(name.startswith("renderer_stem.") for name in changed_names)
    assert any(name.startswith("renderer_tower.") for name in changed_names)
    for prefix in (
        "profile_midpoint_offset_head.",
        "profile_signed_contrast_head.",
        "profile_width_head.",
        "profile_visibility_head.",
    ):
        assert any(name.startswith(prefix) for name in changed_names), prefix


def test_joint_profile_guard_updates_shared_backbone_but_nothing_outside_contract() -> None:
    model = _fresh_compact_model().train()
    batch = _synthetic_profile_batch()
    optimizers, parameter_sets = build_optimizers(model)
    optimizer = optimizers["profile"]
    set_trainable(model, parameter_sets["profile"])

    # Give visibility a valid non-neutral warmup, as the real profile stage
    # does before joint refinement.
    optimizer.zero_grad(set_to_none=True)
    _combined_profile_contract_objective(model, batch).backward()
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)

    set_trainable(model, parameter_sets["profile"])
    assert_step_parameter_contract(
        model,
        "joint_refinement",
        "profile_guard",
        0,
        "profile",
        optimizer,
        parameter_sets,
    )
    before = {id(parameter): parameter.detach().clone() for parameter in model.parameters()}
    objective, _metrics, actual_name = compute_step(
        model,
        batch,
        "joint_refinement",
        1,
        1,
        "profile_guard",
        0,
        20,
        False,
    )
    assert actual_name == "profile_guard"
    assert torch.isfinite(objective)
    objective.backward()
    backbone = model.parameter_groups()["renderer_backbone"]
    assert any(
        parameter.grad is not None and float(parameter.grad.abs().sum()) > 1.0e-12
        for parameter in backbone
    )
    optimizer.step()

    profile_ids = _ids(model.profile_parameters())
    assert any(
        not torch.equal(parameter.detach(), before[id(parameter)])
        for parameter in backbone
    )
    for parameter in model.parameters():
        if id(parameter) not in profile_ids:
            assert torch.equal(parameter.detach(), before[id(parameter)])
