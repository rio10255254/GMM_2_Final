"""Scratch-only staged trainer for the R114 split-profile model.

This entry point is intentionally independent from ``training/train.py``.  It
never reads a checkpoint, never resumes a run, and never writes the formal run
registry.  Reliability, width, shift, and bounded profile actions are updated
by separate optimizers and separate objective steps.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import fields
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
from types import SimpleNamespace
import sys
import time
from typing import Any, Iterable, Mapping

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r114_split_profile_model import (  # noqa: E402
    R114SplitProfileModel,
    SplitControllerOutput,
    build_split_profile_model,
    count_parameters,
    forward_tiled_split,
)
from training.dataset import (  # noqa: E402
    ManifestBatchSampler,
    R114Dataset,
    manifest_sha256,
)
from training.losses import (  # noqa: E402
    controller_components,
    controller_objective,
    render_components,
)
from training.split_profile_losses import (  # noqa: E402
    profile_parameter_components,
    reliability_components,
    shift_action_components,
    shift_action_objective,
    shift_reliability_objective,
    width_action_components,
    width_action_objective,
    width_reliability_objective,
)
from training.split_profile_targets import (  # noqa: E402
    SplitProfileTargets,
    build_split_profile_targets,
)
from training.targets import build_spatial_targets  # noqa: E402


CONFIG_PATH = ROOT / "config" / "split_profile_training.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
SOURCE_FILES = (
    CONFIG_PATH,
    ROOT / "config" / "data.json",
    ROOT / "config" / "model.json",
    ROOT / "model" / "r114_model.py",
    ROOT / "model" / "r114_split_profile_model.py",
    ROOT / "training" / "targets.py",
    ROOT / "training" / "losses.py",
    ROOT / "training" / "split_profile_targets.py",
    ROOT / "training" / "split_profile_losses.py",
    ROOT / "training" / "dataset.py",
    ROOT / "training" / "SPLIT_PROFILE_TRAINER_CONTRACT.md",
    ROOT / "scripts" / "train_split_profile.ps1",
    Path(__file__).resolve(),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def model_state_sha256(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")


def worker_seed(worker_id: int) -> None:
    seed = (torch.initial_seed() + worker_id) % (2**32)
    random.seed(seed)
    np.random.seed(seed)


def require_finite(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(f"non-finite tensor: {name}")


def stage_for_epoch(stages: Mapping[str, int], epoch: int) -> tuple[str, int, int]:
    cursor = 0
    for name, length_value in stages.items():
        length = int(length_value)
        if cursor < epoch <= cursor + length:
            return name, epoch - cursor, length
        cursor += length
    raise ValueError(f"epoch {epoch} lies outside the stage schedule")


def cosine_lr(base: float, minimum: float, stage_epoch: int, stage_length: int) -> float:
    fraction = (stage_epoch - 1) / max(stage_length - 1, 1)
    return minimum + 0.5 * (base - minimum) * (1.0 + math.cos(math.pi * fraction))


def move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    return {
        key: value.to(device, non_blocking=True) if isinstance(value, torch.Tensor) else value
        for key, value in batch.items()
    }


def crop_for_smoke(batch: dict[str, Any], size: int) -> dict[str, Any]:
    if size <= 0:
        return batch
    height, width = batch["source"].shape[-2:]
    size = min(int(size), height, width)
    y0 = (height - size) // 2
    x0 = (width - size) // 2
    result: dict[str, Any] = {}
    for key, value in batch.items():
        if isinstance(value, torch.Tensor) and value.ndim == 4:
            result[key] = value[..., y0 : y0 + size, x0 : x0 + size]
        else:
            result[key] = value
    return result


def split_logical_batch(
    batch: dict[str, Any], microbatch_size: int
) -> list[dict[str, Any]]:
    """Split a logical composition batch without changing its optimizer step."""

    logical_size = int(batch["source"].shape[0])
    size = max(1, min(int(microbatch_size), logical_size))
    pieces: list[dict[str, Any]] = []
    for start in range(0, logical_size, size):
        end = min(start + size, logical_size)
        piece: dict[str, Any] = {}
        for key, value in batch.items():
            if isinstance(value, torch.Tensor) and value.ndim > 0 and value.shape[0] == logical_size:
                piece[key] = value[start:end]
            elif isinstance(value, (list, tuple)) and len(value) == logical_size:
                piece[key] = value[start:end]
            else:
                piece[key] = value
        pieces.append(piece)
    return pieces


def make_loader(
    dataset: R114Dataset,
    batch_size: int,
    workers: int,
    epoch: int,
    *,
    shuffle: bool,
    limited: bool,
) -> DataLoader:
    options: dict[str, Any] = {
        "dataset": dataset,
        "num_workers": workers,
        "pin_memory": torch.cuda.is_available(),
        "worker_init_fn": worker_seed,
    }
    if limited:
        # A stratified limited dataset no longer contains complete manifest
        # batches.  Reusing the formal sampler here would silently turn B12
        # into many B1 fragments.  Only complete, unlimited campaigns use the
        # audited composition manifest below.
        options.update(batch_size=batch_size, shuffle=shuffle, drop_last=False)
    else:
        options["batch_sampler"] = ManifestBatchSampler(dataset, batch_size, epoch, shuffle)
    if workers > 0:
        options.update(persistent_workers=False, prefetch_factor=2)
    return DataLoader(**options)


def cycle_loader(loader: DataLoader, count: int) -> Iterable[dict[str, Any]]:
    if len(loader) < 1:
        raise RuntimeError("empty training loader")
    iterator = iter(loader)
    for _ in range(count):
        try:
            yield next(iterator)
        except StopIteration:
            iterator = iter(loader)
            yield next(iterator)


def _controller_from_details(
    details: Any,
    width_reliability: torch.Tensor,
    shift_reliability: torch.Tensor,
) -> SplitControllerOutput:
    return SplitControllerOutput(
        normalized_sdf=details.normalized_sdf,
        normal_x=details.normal_x,
        normal_y=details.normal_y,
        boundary_confidence=details.boundary_confidence,
        correction_need=details.correction_need,
        recoverability_uncertainty=torch.cat(
            [details.recoverability, details.uncertainty], dim=1
        ),
        width_reliability=width_reliability,
        shift_reliability=shift_reliability,
    )


def _replace_details(details: Any, **updates: torch.Tensor) -> SimpleNamespace:
    values = {item.name: getattr(details, item.name) for item in fields(details)}
    values.update(updates)
    return SimpleNamespace(**values)


def geometry_view(
    model: R114SplitProfileModel,
    source: torch.Tensor,
    details: Any,
    split_targets: SplitProfileTargets,
    gate_mode: str,
) -> SimpleNamespace:
    """Return geometry-only output with oracle or detached predicted gates."""

    if gate_mode == "oracle":
        width_reliability = split_targets.width_reliability.detach()
        shift_reliability = split_targets.shift_reliability.detach()
    elif gate_mode == "predicted_detached":
        width_reliability = details.width_reliability.detach()
        shift_reliability = details.shift_reliability.detach()
    elif gate_mode == "predicted":
        width_reliability = details.width_reliability
        shift_reliability = details.shift_reliability
    else:
        raise ValueError(f"unknown gate mode {gate_mode}")
    controller = _controller_from_details(details, width_reliability, shift_reliability)
    renderer_features = model._renderer_features(source)  # local audited model primitive
    geometry = model.apply_geometry(
        source.float(),
        controller,
        details.width_gain,
        details.normal_shift,
        renderer_features.float(),
    )
    return _replace_details(
        details,
        output=geometry.base_output,
        base_output=geometry.base_output,
        shifted_base=geometry.shifted_base,
        width_proposal=geometry.width_proposal,
        delta=geometry.base_output - source.float(),
        geometry_gate=geometry.geometry_gate,
        width_gate=geometry.width_gate,
        shift_gate=geometry.shift_gate,
        effective_width_gain=geometry.effective_width_gain,
        effective_normal_shift=geometry.effective_normal_shift,
        flow=geometry.flow,
    )


def shift_tensor(value: torch.Tensor, dx: float, dy: float) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    theta = value.new_zeros((batch, 2, 3))
    theta[:, 0, 0] = 1.0
    theta[:, 1, 1] = 1.0
    theta[:, 0, 2] = -2.0 * dx / max(width - 1, 1)
    theta[:, 1, 2] = -2.0 * dy / max(height - 1, 1)
    grid = F.affine_grid(theta, value.shape, align_corners=True)
    return F.grid_sample(
        value, grid, mode="bilinear", padding_mode="reflection", align_corners=True
    )


def _geometry_for_source(
    model: R114SplitProfileModel,
    source: torch.Tensor,
    targets: SplitProfileTargets,
    gate_mode: str,
    use_bf16: bool,
) -> SimpleNamespace:
    """Geometry-only fast path; never builds the bounded-profile graph."""

    device_type = source.device.type
    with torch.autocast(
        device_type=device_type,
        dtype=torch.bfloat16,
        enabled=use_bf16 and device_type == "cuda",
    ):
        learned_controller = model.controller(source)
        renderer_features = model._renderer_features(source)
    with torch.autocast(device_type=device_type, enabled=False):
        renderer_fp32 = renderer_features.float()
        width_fraction = torch.sigmoid(model.width_head(renderer_fp32))
        width_gain = model.config.minimum_width_gain + (
            model.config.maximum_width_gain - model.config.minimum_width_gain
        ) * width_fraction
        normal_shift = model.config.maximum_normal_shift_px * torch.tanh(
            model.shift_head(renderer_fp32)
        )
    if gate_mode == "oracle":
        width_reliability = targets.width_reliability.detach()
        shift_reliability = targets.shift_reliability.detach()
    elif gate_mode == "predicted_detached":
        width_reliability = learned_controller.width_reliability.detach()
        shift_reliability = learned_controller.shift_reliability.detach()
    elif gate_mode == "predicted":
        width_reliability = learned_controller.width_reliability
        shift_reliability = learned_controller.shift_reliability
    else:
        raise ValueError(gate_mode)
    controller = SplitControllerOutput(
        normalized_sdf=learned_controller.normalized_sdf,
        normal_x=learned_controller.normal_x,
        normal_y=learned_controller.normal_y,
        boundary_confidence=learned_controller.boundary_confidence,
        correction_need=learned_controller.correction_need,
        recoverability_uncertainty=learned_controller.recoverability_uncertainty,
        width_reliability=width_reliability,
        shift_reliability=shift_reliability,
    )
    geometry = model.apply_geometry(
        source.float(), controller, width_gain, normal_shift, renderer_fp32
    )
    return SimpleNamespace(
        output=geometry.base_output,
        base_output=geometry.base_output,
        shifted_base=geometry.shifted_base,
        width_proposal=geometry.width_proposal,
        delta=geometry.base_output - source.float(),
        normalized_sdf=controller.normalized_sdf,
        normal_x=controller.normal_x,
        normal_y=controller.normal_y,
        boundary_confidence=controller.boundary_confidence,
        correction_need=controller.correction_need,
        recoverability=controller.recoverability,
        uncertainty=controller.uncertainty,
        width_reliability=controller.width_reliability,
        shift_reliability=controller.shift_reliability,
        geometry_gate=geometry.geometry_gate,
        width_gate=geometry.width_gate,
        shift_gate=geometry.shift_gate,
        width_gain=geometry.width_gain,
        normal_shift=geometry.normal_shift,
        effective_width_gain=geometry.effective_width_gain,
        effective_normal_shift=geometry.effective_normal_shift,
        flow=geometry.flow,
    )


def translation_objective(
    model: R114SplitProfileModel,
    source: torch.Tensor,
    targets: SplitProfileTargets,
    gate_mode: str,
    use_bf16: bool,
    step: int,
) -> torch.Tensor:
    offsets = ((0.75, -0.50), (-0.60, 0.85), (1.0, 0.35))
    dx, dy = offsets[step % len(offsets)]
    # The unshifted branch is a teacher target, not a second optimization
    # branch.  Detaching it halves retained activation memory at B12/256.
    with torch.no_grad():
        reference = _geometry_for_source(model, source, targets, gate_mode, use_bf16)
    shifted_source = shift_tensor(source, dx, dy)
    shifted_targets = SimpleNamespace(
        width_reliability=shift_tensor(targets.width_reliability, dx, dy),
        shift_reliability=shift_tensor(targets.shift_reliability, dx, dy),
    )
    shifted = _geometry_for_source(
        model, shifted_source, shifted_targets, gate_mode, use_bf16
    )
    expected = shift_tensor(reference.output, dx, dy)
    margin = 4
    return F.smooth_l1_loss(
        shifted.output[..., margin:-margin, margin:-margin],
        expected[..., margin:-margin, margin:-margin],
        beta=1.0 / 255.0,
    )


def exposure_objective(
    model: R114SplitProfileModel,
    source: torch.Tensor,
    targets: SplitProfileTargets,
    gate_mode: str,
    use_bf16: bool,
    step: int,
) -> torch.Tensor:
    transforms = ((0.90, 0.04), (1.08, -0.03), (0.96, 0.02))
    scale, offset = transforms[step % len(transforms)]
    with torch.no_grad():
        reference = _geometry_for_source(model, source, targets, gate_mode, use_bf16)
    changed_source = (source * scale + offset).clamp(0, 1)
    changed = _geometry_for_source(
        model, changed_source, targets, gate_mode, use_bf16
    )
    expected = (reference.output * scale + offset).clamp(0, 1)
    return F.smooth_l1_loss(changed.output, expected, beta=1.0 / 255.0)


def _unique_parameters(parameters: Iterable[torch.nn.Parameter]) -> list[torch.nn.Parameter]:
    result: list[torch.nn.Parameter] = []
    seen: set[int] = set()
    for parameter in parameters:
        if id(parameter) not in seen:
            result.append(parameter)
            seen.add(id(parameter))
    return result


def _parameter_names(
    model: torch.nn.Module, parameters: Iterable[torch.nn.Parameter]
) -> list[str]:
    names_by_id = {id(parameter): name for name, parameter in model.named_parameters()}
    return sorted(names_by_id.get(id(parameter), f"<unknown:{id(parameter)}>") for parameter in parameters)


def assert_exact_parameter_set(
    model: torch.nn.Module,
    label: str,
    actual: Iterable[torch.nn.Parameter],
    expected: Iterable[torch.nn.Parameter],
) -> list[torch.nn.Parameter]:
    """Fail closed when an optimizer/stage drifts from its model contract."""

    actual_list = list(actual)
    expected_list = list(expected)
    actual_ids = [id(parameter) for parameter in actual_list]
    expected_ids = [id(parameter) for parameter in expected_list]
    if len(actual_ids) != len(set(actual_ids)):
        raise RuntimeError(f"{label} contains duplicate parameters")
    if len(expected_ids) != len(set(expected_ids)):
        raise RuntimeError(f"{label} contract contains duplicate parameters")
    actual_set = set(actual_ids)
    expected_set = set(expected_ids)
    if actual_set != expected_set:
        missing = [parameter for parameter in expected_list if id(parameter) not in actual_set]
        extra = [parameter for parameter in actual_list if id(parameter) not in expected_set]
        raise RuntimeError(
            f"{label} parameter contract mismatch; "
            f"missing={_parameter_names(model, missing)}, "
            f"extra={_parameter_names(model, extra)}"
        )
    return actual_list


def optimizer_parameters(
    optimizer: torch.optim.Optimizer,
) -> list[torch.nn.Parameter]:
    return [
        parameter
        for group in optimizer.param_groups
        for parameter in group["params"]
    ]


def assert_optimizer_parameter_contract(
    model: R114SplitProfileModel,
    optimizers: Mapping[str, torch.optim.Optimizer],
    parameter_sets: Mapping[str, list[torch.nn.Parameter]],
) -> None:
    """Validate declared sets, optimizer contents, and the profile API contract."""

    if set(optimizers) != set(parameter_sets):
        raise RuntimeError(
            "optimizer/parameter-set names differ: "
            f"optimizers={sorted(optimizers)}, sets={sorted(parameter_sets)}"
        )
    for name, parameters in parameter_sets.items():
        assert_exact_parameter_set(
            model,
            f"{name} optimizer",
            optimizer_parameters(optimizers[name]),
            parameters,
        )
    assert_exact_parameter_set(
        model,
        "profile optimizer",
        parameter_sets["profile"],
        model.profile_parameters(),
    )


def build_optimizers(
    model: R114SplitProfileModel,
) -> tuple[dict[str, torch.optim.Optimizer], dict[str, list[torch.nn.Parameter]]]:
    groups = model.parameter_groups()
    parameter_sets = {
        "reliability": _unique_parameters(
            [
                *groups["controller_backbone"],
                *groups["controller_geometry_heads"],
                *groups["recoverability_head"],
                *groups["width_reliability_head"],
                *groups["shift_reliability_head"],
            ]
        ),
        "width": _unique_parameters(
            [*groups["renderer_backbone"], *groups["width_action_head"]]
        ),
        "shift": _unique_parameters(
            [*groups["renderer_backbone"], *groups["shift_action_head"]]
        ),
        # The model contract deliberately includes the shared renderer
        # backbone as well as the four bounded profile heads.  Geometry heads
        # stay frozen and the completed geometry target stays detached, but
        # profile evidence must be allowed to train its feature extractor.
        "profile": _unique_parameters(model.profile_parameters()),
    }
    weight_decay = float(CONFIG["weight_decay"])
    optimizers = {
        name: torch.optim.AdamW(parameters, lr=1.0e-4, weight_decay=weight_decay)
        for name, parameters in parameter_sets.items()
    }
    assert_optimizer_parameter_contract(model, optimizers, parameter_sets)
    return optimizers, parameter_sets


def set_trainable(
    model: torch.nn.Module, selected: Iterable[torch.nn.Parameter]
) -> list[torch.nn.Parameter]:
    selected_list = list(selected)
    selected_ids = {id(value) for value in selected_list}
    for parameter in model.parameters():
        parameter.requires_grad_(id(parameter) in selected_ids)
        parameter.grad = None
    return selected_list


def assert_step_parameter_contract(
    model: R114SplitProfileModel,
    stage: str,
    objective_name: str,
    objective_hit: int,
    optimizer_name: str,
    optimizer: torch.optim.Optimizer,
    parameter_sets: Mapping[str, list[torch.nn.Parameter]],
) -> None:
    """Verify the active set for profile and joint steps before backpropagation."""

    expected_optimizer = select_optimizer(stage, objective_name, objective_hit)
    if optimizer_name != expected_optimizer:
        raise RuntimeError(
            f"{stage}/{objective_name} selected {optimizer_name}, "
            f"expected {expected_optimizer}"
        )
    expected_parameters = parameter_sets[expected_optimizer]
    assert_exact_parameter_set(
        model,
        f"{stage}/{objective_name} optimizer",
        optimizer_parameters(optimizer),
        expected_parameters,
    )
    active_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    assert_exact_parameter_set(
        model,
        f"{stage}/{objective_name} active",
        active_parameters,
        expected_parameters,
    )
    if expected_optimizer == "profile":
        assert_exact_parameter_set(
            model,
            f"{stage}/{objective_name} profile",
            active_parameters,
            model.profile_parameters(),
        )


def select_optimizer(
    stage: str,
    objective_name: str,
    objective_hit: int,
) -> str:
    if stage == "reliability":
        return "reliability"
    if objective_name in {"width_fit"}:
        return "width"
    if objective_name in {"shift_fit"}:
        return "shift"
    if objective_name.startswith("profile"):
        return "profile"
    if objective_name == "geometry_guard":
        return "width" if objective_hit % 2 == 0 else "shift"
    if objective_name in {"render_contour", "translation", "exposure"}:
        return "width" if objective_hit % 2 == 0 else "shift"
    raise ValueError(f"no optimizer mapping for {stage}/{objective_name}")


def configure_optimizer_lr(
    optimizer: torch.optim.Optimizer,
    optimizer_name: str,
    stage: str,
    stage_epoch: int,
    stage_length: int,
) -> float:
    rates = CONFIG["learning_rates"]
    if optimizer_name == "reliability":
        base = float(rates["reliability"])
    elif optimizer_name in {"width", "shift"}:
        base = float(rates["geometry"])
        if stage == "joint_refinement":
            base = float(rates["joint_refinement"])
    else:
        base = float(rates["profile"])
        if stage == "joint_refinement":
            base = float(rates["joint_refinement"])
    learning_rate = cosine_lr(
        base, float(rates["minimum"]), stage_epoch, stage_length
    )
    for group in optimizer.param_groups:
        group["lr"] = learning_rate
    return learning_rate


def _clear_counterfactual(details: Any, batch: dict[str, Any]) -> torch.Tensor:
    mask = (batch["identity"] | batch["flat"]).reshape(-1).bool()
    if not bool(mask.any()):
        return details.correction_need.sum() * 0.0
    values = (
        details.correction_need[mask].square()
        + details.boundary_confidence[mask].square()
        + details.width_reliability[mask].square()
        + details.shift_reliability[mask].square()
    )
    return values.flatten(1).mean(1).mean()


def _safe_profile_visibility_losses(
    predictions: Any,
    targets: SplitProfileTargets,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Stable visibility bootstrap and Dice that excludes empty scenes.

    The model is deliberately initialized at exact zero visibility.  A BCE
    implementation that clamps this zero can have no gradient, while a Dice
    implementation with an empty target can have an unbounded denominator
    gradient.  Smooth-L1 supplies the stable one-sided bootstrap; Dice is used
    only for scenes containing positive target mass.
    """

    prediction = predictions.profile_visibility
    target = targets.profile_visibility
    support = getattr(
        targets,
        "profile_visibility_weight",
        targets.boundary_band
        + targets.flat.reshape(-1, 1, 1, 1).to(prediction.dtype),
    )
    element = F.smooth_l1_loss(prediction, target, beta=0.05, reduction="none")
    numerator = (element * support).flatten(1).sum(1)
    denominator = support.flatten(1).sum(1).clamp_min(1.0e-6)
    bootstrap = (numerator / denominator).mean()

    weight = support
    target_mass = (weight * target).flatten(1).sum(1)
    valid = target_mass > 1.0e-4
    if bool(valid.any()):
        intersection = (weight * prediction * target).flatten(1).sum(1)
        total = (weight * (prediction + target)).flatten(1).sum(1)
        dice = (
            1.0
            - (2.0 * intersection[valid] + 1.0e-6)
            / (total[valid] + 1.0e-6)
        ).mean()
    else:
        dice = prediction.sum() * 0.0
    return bootstrap, dice


def profile_objective(
    name: str,
    components: Mapping[str, torch.Tensor],
    predictions: Any,
    targets: SplitProfileTargets,
) -> torch.Tensor:
    if name == "profile_parameters":
        return (
            components["profile_midpoint_fit"]
            + components["profile_contrast_fit"]
            + components["profile_width_fit"]
            + components["profile_parameter_range_guard"]
        )
    if name == "profile_visibility":
        bootstrap, valid_dice = _safe_profile_visibility_losses(predictions, targets)
        return (
            bootstrap
            + 0.5 * valid_dice
            + components["profile_action_bound_guard"]
        )
    if name in {"profile_render", "profile_guard"}:
        return (
            components["profile_normal_fit"]
            + 0.65 * components["profile_final_reconstruction"]
            + 1.50 * components["profile_gain_guard"]
            + 0.35 * components["profile_polarity_guard"]
            + 0.15 * components["profile_monotonicity_guard"]
            + 0.35 * components["profile_overshoot_guard"]
        )
    if name == "profile_identity":
        return (
            components["profile_identity_guard"]
            + 0.5 * components["profile_outside_band_guard"]
            + 0.15 * components["profile_local_mean_guard"]
        )
    raise ValueError(name)


def compute_step(
    model: R114SplitProfileModel,
    batch: dict[str, Any],
    stage: str,
    stage_epoch: int,
    stage_length: int,
    objective_name: str,
    objective_hit: int,
    global_step: int,
    use_bf16: bool,
) -> tuple[torch.Tensor, dict[str, torch.Tensor], str]:
    spatial = build_spatial_targets(
        batch["source"], batch["target"], batch["mask"], batch["sdf"],
        batch["identity"], batch["flat"],
    )
    initial_split = build_split_profile_targets(
        batch["source"], batch["target"], batch["sdf"],
        batch["identity"], batch["flat"],
    )
    metrics: dict[str, torch.Tensor] = {}
    if stage == "reliability":
        # Controller viability is FP32 and does not build any renderer graph.
        predicted = model.controller(batch["source"])
        base = controller_components(predicted, spatial)
        reliability = reliability_components(predicted, initial_split)
        metrics.update(base)
        metrics.update(reliability)
        if objective_name == "base_geometry":
            objective = controller_objective(base, objective_hit)
            name = f"base_geometry_{objective_hit % 3}"
        elif objective_name == "width_reliability":
            objective = width_reliability_objective(reliability)
            name = objective_name
        elif objective_name == "shift_reliability":
            objective = shift_reliability_objective(reliability)
            name = objective_name
        elif objective_name == "need_clear_counterfactual":
            clear = _clear_counterfactual(predicted, batch)
            metrics["clear_counterfactual"] = clear
            objective = base["need"] + clear
            name = objective_name
        else:
            raise ValueError(objective_name)
        return objective, metrics, name

    if stage == "oracle_geometry":
        gate_mode = "oracle"
    elif stage == "predicted_geometry":
        # The entire predicted-gate warmup keeps render gradients out of both
        # reliability heads.  Those heads only learn in reliability steps.
        gate_mode = "predicted_detached"
    else:
        gate_mode = "predicted"

    if stage in {"oracle_geometry", "predicted_geometry"}:
        if objective_name == "width_fit":
            geometry = _geometry_for_source(
                model, batch["source"], initial_split, gate_mode, use_bf16
            )
            width = width_action_components(geometry, initial_split)
            metrics.update(width)
            objective = width_action_objective(width)
        elif objective_name == "shift_fit":
            geometry = _geometry_for_source(
                model, batch["source"], initial_split, gate_mode, use_bf16
            )
            shift = shift_action_components(geometry, initial_split)
            metrics.update(shift)
            objective = shift_action_objective(shift)
        elif objective_name == "render_contour":
            geometry = _geometry_for_source(
                model, batch["source"], initial_split, gate_mode, use_bf16
            )
            render = render_components(geometry, batch, spatial)
            metrics.update(render)
            objective = (
                render["contour_dice"]
                + 0.25 * render["contour_bce"]
                + 0.65 * render["reconstruction"]
            )
        elif objective_name == "translation":
            objective = translation_objective(
                model, batch["source"], initial_split, gate_mode, use_bf16, global_step
            )
            metrics["translation"] = objective
        elif objective_name == "exposure":
            objective = exposure_objective(
                model, batch["source"], initial_split, gate_mode, use_bf16, global_step
            )
            metrics["exposure"] = objective
        else:
            raise ValueError(objective_name)
        return objective, metrics, objective_name

    if stage == "joint_refinement" and objective_name in {
        "geometry_guard", "translation", "exposure"
    }:
        if objective_name == "translation":
            objective = translation_objective(
                model, batch["source"], initial_split, "predicted_detached", use_bf16,
                global_step,
            )
            return objective, {"translation": objective}, objective_name
        if objective_name == "exposure":
            objective = exposure_objective(
                model, batch["source"], initial_split, "predicted_detached", use_bf16,
                global_step,
            )
            return objective, {"exposure": objective}, objective_name
        geometry = _geometry_for_source(
            model, batch["source"], initial_split, "predicted_detached", use_bf16
        )
        if objective_hit % 2 == 0:
            width = width_action_components(geometry, initial_split)
            return width_action_objective(width), width, "geometry_guard_width"
        shift = shift_action_components(geometry, initial_split)
        return shift_action_objective(shift), shift, "geometry_guard_shift"

    device_type = batch["source"].device.type
    with torch.autocast(device_type=device_type, enabled=False):
        predicted = model.forward_details(batch["source"].float())

    # Profile targets are always rebuilt from a detached, already-completed
    # geometry output.  No profile loss can redefine the geometry target.
    profile_targets = build_split_profile_targets(
        batch["source"], batch["target"], batch["sdf"],
        batch["identity"], batch["flat"],
        base_output=predicted.base_output.detach(),
        midpoint_source=predicted.shifted_base.detach(),
        deployment_sdf_px=predicted.predicted_sdf_px.detach(),
        deployment_boundary_confidence=predicted.boundary_confidence.detach(),
        midpoint_cue_window_px=model.config.local_range_window_px,
    )
    profile = profile_parameter_components(predicted, profile_targets)
    metrics.update(profile)
    if stage == "profile":
        return (
            profile_objective(objective_name, profile, predicted, profile_targets),
            metrics,
            objective_name,
        )

    if stage == "joint_refinement":
        if objective_name == "profile_guard":
            return (
                profile_objective(objective_name, profile, predicted, profile_targets),
                metrics,
                objective_name,
            )
    raise ValueError(f"unsupported step: {stage}/{objective_name}")


@torch.no_grad()
def validate(
    model: R114SplitProfileModel,
    device: torch.device,
    batch_size: int,
    workers: int,
    limit: int,
    smoke: bool,
    smoke_size: int,
) -> tuple[dict[str, Any], list[dict[str, np.ndarray]]]:
    model.eval()
    dataset = R114Dataset("validation", epoch=0, limit=limit)
    loader = make_loader(
        dataset, batch_size, workers, 0, shuffle=False, limited=smoke or bool(limit)
    )
    totals: dict[str, float] = {}
    scenes = 0
    previews: list[dict[str, np.ndarray]] = []
    tile_max_abs: float | None = None
    for batch_index, batch_data in enumerate(loader):
        batch = crop_for_smoke(move_batch(batch_data, device), smoke_size if smoke else 0)
        details = model.forward_details(batch["source"])
        batch_count = int(batch["source"].shape[0])
        scenes += batch_count
        measurements = {
            "mae": (details.output - batch["target"]).abs().flatten(1).mean(1),
            "base_mae": (details.base_output - batch["target"]).abs().flatten(1).mean(1),
            "delta_abs": details.delta.abs().flatten(1).mean(1),
            "boundary_mean": details.boundary_confidence.flatten(1).mean(1),
            "need_mean": details.correction_need.flatten(1).mean(1),
            "width_reliability_mean": details.width_reliability.flatten(1).mean(1),
            "shift_reliability_mean": details.shift_reliability.flatten(1).mean(1),
            "profile_visibility_mean": details.profile_visibility.flatten(1).mean(1),
        }
        for name, values in measurements.items():
            require_finite(f"validation_{name}", values)
            totals[name] = totals.get(name, 0.0) + float(values.sum().cpu())
        if not previews:
            for index in range(min(batch_count, 4)):
                previews.append(
                    {
                        "source": batch["source"][index, 0].cpu().numpy(),
                        "output": details.output[index, 0].cpu().numpy(),
                        "target": batch["target"][index, 0].cpu().numpy(),
                    }
                )
            tile_source = batch["source"][0:1]
            core = max(16, min(tile_source.shape[-2:]) // 2)
            tiled = forward_tiled_split(
                model, tile_source, core_size=core, halo=model.minimum_halo_px
            )
            tile_max_abs = float((tiled.output - details.output[0:1]).abs().max().cpu())
        if smoke and batch_index >= 0:
            break
    summary: dict[str, Any] = {
        name: total / max(scenes, 1) for name, total in totals.items()
    }
    summary["scenes"] = scenes
    summary["canonical_tile_max_abs"] = tile_max_abs
    return {"summary": summary, "canonical_tile_only": True}, previews


def save_preview(path: Path, previews: list[dict[str, np.ndarray]]) -> None:
    if not previews:
        return
    rows = []
    for record in previews:
        images = []
        for name in ("source", "output", "target"):
            image = np.clip(record[name] * 255.0 + 0.5, 0, 255).astype(np.uint8)
            images.append(image)
        rows.append(np.concatenate(images, axis=1))
    montage = np.concatenate(rows, axis=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), montage):
        raise OSError(f"failed to write preview {path}")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def _gpu_metrics(device: torch.device) -> dict[str, float | None]:
    if device.type != "cuda":
        return {
            "gpu_peak_allocated_gib": None,
            "gpu_peak_reserved_gib": None,
            "gpu_free_end_gib": None,
            "gpu_min_free_estimate_gib": None,
        }
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    peak_reserved = torch.cuda.max_memory_reserved(device)
    return {
        "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
        "gpu_peak_reserved_gib": peak_reserved / 2**30,
        "gpu_free_end_gib": free_bytes / 2**30,
        "gpu_min_free_estimate_gib": (total_bytes - peak_reserved) / 2**30,
    }


def _progress_payload(
    *,
    run_id: str,
    campaign: str,
    epoch: int,
    epochs: int,
    stage: str,
    batch: int,
    batches: int,
    global_step: int,
    objective: str,
    started: float,
    step_ema: float | None,
    epoch_ema: float | None,
) -> dict[str, Any]:
    elapsed = time.perf_counter() - started
    remaining_in_epoch = max(batches - batch, 0)
    epoch_remaining = None if step_ema is None else step_ema * remaining_in_epoch
    total_remaining = None
    if epoch_ema is not None:
        total_remaining = epoch_remaining or 0.0
        total_remaining += epoch_ema * max(epochs - epoch, 0)
    return {
        "status": "running",
        "run_id": run_id,
        "campaign": campaign,
        "epoch": epoch,
        "total_epochs": epochs,
        "stage": stage,
        "batch": batch,
        "batches_in_epoch": batches,
        "global_step": global_step,
        "latest_objective": objective,
        "elapsed_seconds": elapsed,
        "epoch_remaining_seconds": epoch_remaining,
        "total_remaining_seconds": total_remaining,
        "updated_at": utc_now(),
    }


def train(args: argparse.Namespace) -> int:
    if args.resume or args.checkpoint or args.initial_weights:
        raise RuntimeError(
            "R114 split-profile is scratch-only; resume and foreign weights are forbidden"
        )
    campaign = CONFIG["campaigns"][args.campaign]
    if bool(campaign.get("formal")) and not args.authorize_formal:
        raise RuntimeError("formal campaign requires explicit --authorize-formal")
    if args.authorize_formal and args.campaign != "formal":
        raise ValueError("--authorize-formal is valid only with --campaign formal")

    stages = {name: int(value) for name, value in campaign["stages"].items()}
    if args.smoke:
        # The integration smoke deliberately covers every stage once even
        # though a normal reliability_probe stops after its first stage.
        stages = {
            "reliability": 1,
            "oracle_geometry": 1,
            "predicted_geometry": 1,
            "profile": 1,
            "joint_refinement": 1,
        }
    epochs = sum(stages.values())
    batch_size = int(args.batch_size or (2 if args.smoke else CONFIG["default_batch_size"]))
    workers = int(args.workers if args.workers is not None else (0 if args.smoke else CONFIG["workers"]))
    seed = int(CONFIG["seed"])
    seed_everything(seed)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    device = torch.device(
        "cuda:0" if args.device == "cuda" else (
            "cuda:0" if args.device == "auto" and torch.cuda.is_available() else "cpu"
        )
    )
    microbatch_config = CONFIG["microbatching"]
    configured_microbatch_size = int(
        args.microbatch_size or microbatch_config["default_microbatch_size"]
    )
    high_memory_stages = set(microbatch_config["high_memory_stages"])
    if device.type == "cuda":
        device_name = torch.cuda.get_device_name(device)
    else:
        device_name = "CPU smoke"

    run_id = args.run_id or (
        f"r114_split_{'smoke' if args.smoke else args.campaign}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    run_dir = ROOT / "runs" / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    model = build_split_profile_model(
        compact=args.smoke and not args.full_model_smoke
    ).to(device)
    initial_hash = model_state_sha256(model)
    optimizers, parameter_sets = build_optimizers(model)
    source_hashes = {str(path.relative_to(ROOT)): file_sha256(path) for path in SOURCE_FILES}
    provenance = {
        "scratch": True,
        "resume_supported": False,
        "foreign_checkpoint_loaded": False,
        "initial_state_sha256": initial_hash,
        "dataset_manifest_sha256": manifest_sha256(),
        "source_sha256": source_hashes,
        "seed": seed,
    }
    atomic_json(run_dir / "scratch_provenance.json", provenance)
    state: dict[str, Any] = {
        "status": "running",
        "run_id": run_id,
        "campaign": args.campaign,
        "formal": bool(campaign.get("formal")),
        "smoke": bool(args.smoke),
        "full_model_smoke": bool(args.full_model_smoke),
        "scratch": True,
        "foreign_checkpoint_loaded": False,
        "initial_state_sha256": initial_hash,
        "device": device_name,
        "parameters": count_parameters(model),
        "epochs": epochs,
        "stages": stages,
        "batch_size": batch_size,
        "logical_batch_size": batch_size,
        "microbatch_policy": {
            "high_memory_stages": sorted(high_memory_stages),
            "microbatch_size": configured_microbatch_size,
            "scene_count_weighted_accumulation": True,
            "optimizer_steps_per_logical_batch": 1,
        },
        "workers": workers,
        "started_at": utc_now(),
    }
    atomic_json(run_dir / "run_state.json", state)
    print(json.dumps(state, ensure_ascii=False), flush=True)

    history: list[dict[str, Any]] = []
    global_step = 0
    started = time.perf_counter()
    step_ema: float | None = None
    epoch_ema: float | None = None
    objective_hits: dict[tuple[str, str], int] = {}
    try:
        for epoch in range(1, epochs + 1):
            stage, stage_epoch, stage_length = stage_for_epoch(stages, epoch)
            cycle = list(CONFIG["objective_cycles"][stage])
            data_limit = int(
                args.data_limit
                or (24 if args.full_model_smoke else (16 if args.smoke else 0))
            )
            dataset = R114Dataset("train", epoch=epoch, limit=data_limit)
            loader = make_loader(
                dataset,
                batch_size,
                workers,
                epoch,
                shuffle=True,
                limited=args.smoke or bool(data_limit),
            )
            steps_in_epoch = len(cycle) if args.smoke else len(loader)
            batches = cycle_loader(loader, steps_in_epoch) if args.smoke else iter(loader)
            model.train()
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
            epoch_started = time.perf_counter()
            totals: dict[str, float] = {}
            counts: dict[str, int] = {}
            learning_rates: dict[str, float] = {}
            stage_microbatch_size = (
                min(configured_microbatch_size, batch_size)
                if stage in high_memory_stages
                else batch_size
            )
            for batch_index, batch_data in enumerate(batches, start=1):
                step_started = time.perf_counter()
                global_step += 1
                objective_name = cycle[(batch_index - 1) % len(cycle)]
                hit_key = (stage, objective_name)
                objective_hit = objective_hits.get(hit_key, 0)
                objective_hits[hit_key] = objective_hit + 1
                optimizer_name = select_optimizer(stage, objective_name, objective_hit)
                optimizer = optimizers[optimizer_name]
                trainable = set_trainable(model, parameter_sets[optimizer_name])
                assert_step_parameter_contract(
                    model,
                    stage,
                    objective_name,
                    objective_hit,
                    optimizer_name,
                    optimizer,
                    parameter_sets,
                )
                learning_rate = configure_optimizer_lr(
                    optimizer, optimizer_name, stage, stage_epoch, stage_length
                )
                learning_rates[optimizer_name] = learning_rate
                optimizer.zero_grad(set_to_none=True)
                logical_batch = crop_for_smoke(
                    move_batch(batch_data, device),
                    (
                        0
                        if args.full_model_smoke
                        else (int(args.smoke_size) if args.smoke else 0)
                    ),
                )
                logical_scene_count = int(logical_batch["source"].shape[0])
                microbatches = split_logical_batch(
                    logical_batch, stage_microbatch_size
                )
                use_bf16 = (
                    device.type == "cuda"
                    # The analytic profile visibility/dice path has a very
                    # small denominator at its exact-neutral initialization.
                    # Keep profile and final guard stages in FP32; BF16 is
                    # reserved for the empirically stable geometry actions.
                    and stage in {"oracle_geometry", "predicted_geometry"}
                    and CONFIG["precision"] == "stagewise_fp32_controller_bf16_actions"
                    and not args.force_fp32
                )
                step_objective = 0.0
                step_metrics: dict[str, float] = {}
                actual_name = ""
                for microbatch in microbatches:
                    micro_scene_count = int(microbatch["source"].shape[0])
                    scene_weight = micro_scene_count / max(logical_scene_count, 1)
                    objective, metrics, micro_name = compute_step(
                        model, microbatch, stage, stage_epoch, stage_length,
                        objective_name, objective_hit, global_step, use_bf16,
                    )
                    require_finite("objective", objective)
                    (objective * scene_weight).backward()
                    step_objective += float(objective.detach().cpu()) * scene_weight
                    for name, value in metrics.items():
                        require_finite(name, value)
                        step_metrics[name] = (
                            step_metrics.get(name, 0.0)
                            + float(value.detach().cpu()) * scene_weight
                        )
                    if actual_name and actual_name != micro_name:
                        raise RuntimeError(
                            f"microbatch objective mismatch: {actual_name} vs {micro_name}"
                        )
                    actual_name = micro_name
                gradient_norm = torch.nn.utils.clip_grad_norm_(
                    trainable, float(CONFIG["gradient_clip"])
                )
                require_finite("gradient_norm", gradient_norm)
                if float(gradient_norm.detach().cpu()) > 100_000.0:
                    raise FloatingPointError(
                        f"exploding pre-clip gradient {float(gradient_norm):.6g} "
                        f"at {stage}/{actual_name}"
                    )
                optimizer.step()
                totals["objective"] = totals.get("objective", 0.0) + step_objective
                totals["gradient_norm"] = totals.get("gradient_norm", 0.0) + float(gradient_norm.detach().cpu())
                for name, value in step_metrics.items():
                    totals[name] = totals.get(name, 0.0) + value
                counts[actual_name] = counts.get(actual_name, 0) + 1
                step_duration = time.perf_counter() - step_started
                step_ema = step_duration if step_ema is None else 0.18 * step_duration + 0.82 * step_ema
                progress = _progress_payload(
                    run_id=run_id, campaign=args.campaign, epoch=epoch, epochs=epochs,
                    stage=stage, batch=batch_index, batches=steps_in_epoch,
                    global_step=global_step, objective=actual_name, started=started,
                    step_ema=step_ema, epoch_ema=epoch_ema,
                )
                progress.update(
                    logical_batch_size=logical_scene_count,
                    microbatch_size=min(stage_microbatch_size, logical_scene_count),
                    accumulation_steps=len(microbatches),
                    optimizer_steps_this_logical_batch=1,
                )
                atomic_json(run_dir / "progress.json", progress)
                if args.smoke or batch_index % 25 == 0:
                    print(json.dumps({"progress": progress}, ensure_ascii=False), flush=True)

            validation_due = (
                epoch % int(CONFIG["validation_every_epochs"]) == 0
                or epoch == epochs
                or args.smoke
            )
            validation: dict[str, Any] = {"summary": {}, "skipped": True}
            previews: list[dict[str, np.ndarray]] = []
            if validation_due:
                validation, previews = validate(
                    model, device, batch_size, min(workers, 2),
                    int(args.validation_limit or (8 if args.smoke else 128)),
                    args.smoke,
                    0 if args.full_model_smoke else int(args.smoke_size),
                )
                atomic_json(run_dir / "validation" / f"epoch_{epoch:03d}.json", validation)
            if device.type == "cuda":
                # Release cached blocks before measuring actual memory left for
                # other applications. Peak counters remain intact.
                torch.cuda.empty_cache()
            duration = time.perf_counter() - epoch_started
            epoch_ema = duration if epoch_ema is None else 0.25 * duration + 0.75 * epoch_ema
            row: dict[str, Any] = {
                "epoch": epoch,
                "stage": stage,
                "stage_epoch": stage_epoch,
                "stage_length": stage_length,
                "global_step": global_step,
                "duration_seconds": duration,
                "batches": steps_in_epoch,
                "logical_batch_size": batch_size,
                "microbatch_size": stage_microbatch_size,
                "accumulation_steps": math.ceil(batch_size / stage_microbatch_size),
                "optimizer_steps_per_logical_batch": 1,
                "precision": "bf16_actions" if use_bf16 else "fp32",
                **_gpu_metrics(device),
                **{f"lr_{name}": value for name, value in learning_rates.items()},
                **{f"train_{name}": value / max(steps_in_epoch, 1) for name, value in totals.items()},
                **{f"objective_count_{name}": count for name, count in counts.items()},
                **{
                    f"validation_{name}": value
                    for name, value in validation.get("summary", {}).items()
                    if isinstance(value, (int, float)) or value is None
                },
            }
            history.append(row)
            write_csv(run_dir / "training_log.csv", history)
            atomic_json(run_dir / "training_history.json", history)
            if (
                epoch % int(CONFIG["preview_every_epochs"]) == 0
                or epoch == epochs
                or args.smoke
            ):
                save_preview(run_dir / "previews" / f"epoch_{epoch:03d}.png", previews)
            checkpoint_path: Path | None = None
            if (
                epoch % int(CONFIG["checkpoint_every_epochs"]) == 0
                or epoch == epochs
                or args.smoke
            ):
                checkpoint_path = run_dir / "weights" / f"epoch_{epoch:03d}.pth"
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(
                    {
                        "model": model.state_dict(),
                        "epoch": epoch,
                        "stage": stage,
                        "campaign": args.campaign,
                        "run_id": run_id,
                        "scratch": True,
                        "resume_supported": False,
                        "foreign_checkpoint_loaded": False,
                        "initial_state_sha256": initial_hash,
                        "source_sha256": source_hashes,
                        "validation": validation.get("summary", {}),
                    },
                    checkpoint_path,
                )
            progress = _progress_payload(
                run_id=run_id, campaign=args.campaign, epoch=epoch, epochs=epochs,
                stage=stage, batch=steps_in_epoch, batches=steps_in_epoch,
                global_step=global_step, objective="epoch_complete", started=started,
                step_ema=step_ema, epoch_ema=epoch_ema,
            )
            progress.update(
                logical_batch_size=batch_size,
                microbatch_size=stage_microbatch_size,
                accumulation_steps=math.ceil(batch_size / stage_microbatch_size),
                optimizer_steps_this_logical_batch=1,
            )
            progress["latest_checkpoint"] = str(checkpoint_path or "")
            atomic_json(run_dir / "progress.json", progress)
            print(json.dumps(row, ensure_ascii=False), flush=True)

        final_hash = model_state_sha256(model)
        state.update(
            {
                "status": "complete",
                "epochs_completed": epochs,
                "global_step": global_step,
                "elapsed_seconds": time.perf_counter() - started,
                "completed_at": utc_now(),
                "final_state_sha256": final_hash,
                "model_changed_from_initial": final_hash != initial_hash,
            }
        )
        atomic_json(run_dir / "run_state.json", state)
        final_progress = json.loads((run_dir / "progress.json").read_text(encoding="utf-8"))
        final_progress.update(status="complete", updated_at=utc_now())
        atomic_json(run_dir / "progress.json", final_progress)
        print(json.dumps(state, ensure_ascii=False), flush=True)
        return 0
    except BaseException as error:
        failure = {
            "status": "failed",
            "run_id": run_id,
            "campaign": args.campaign,
            "global_step": global_step,
            "error_type": type(error).__name__,
            "error": repr(error),
            "failed_at": utc_now(),
        }
        atomic_json(run_dir / "failure.json", failure)
        state.update(failure)
        atomic_json(run_dir / "run_state.json", state)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independent scratch-only R114 split-profile trainer"
    )
    parser.add_argument("--campaign", choices=tuple(CONFIG["campaigns"]), required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--batch-size", type=int, choices=tuple(CONFIG["batch_candidates"]), default=0)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--validation-limit", type=int, default=0)
    parser.add_argument("--data-limit", type=int, default=0)
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--force-fp32", action="store_true")
    parser.add_argument("--microbatch-size", type=int, default=0)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--full-model-smoke", action="store_true")
    parser.add_argument("--smoke-size", type=int, default=64)
    parser.add_argument("--authorize-formal", action="store_true")
    # These options are accepted only to emit an unambiguous scratch-contract
    # error instead of silently ignoring a familiar resume argument.
    parser.add_argument("--resume", default="")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--initial-weights", default="")
    args = parser.parse_args()
    if args.full_model_smoke and not args.smoke:
        parser.error("--full-model-smoke requires --smoke")
    return args


def main() -> int:
    return train(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
