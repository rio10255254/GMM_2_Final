"""Single formal scratch trainer for the cause-separated R95 model.

There is intentionally no checkpoint/resume/teacher command-line input.  The
only teacher signal is exact procedural stage truth from the same scene.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r95_model.py"
DATASET_PATH = ROOT / "training" / "r95_dataset.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
COMMON_PATH = ROOT / "training" / "common_descent.py"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
RUNS = ROOT / "runs"
RESULTS = ROOT / "results"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r95_training_model", MODEL_PATH)
DATA = load_module("r95_training_dataset", DATASET_PATH)
INFERENCE = load_module("r95_training_inference", INFERENCE_PATH)
COMMON = load_module("r95_training_common_descent", COMMON_PATH)


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def state_sha256(model: nn.Module) -> str:
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


def phase_for_epoch(epoch: int) -> dict[str, Any]:
    for phase in DESIGN["training"]["phases"]:
        if int(phase["epoch_start"]) <= epoch <= int(phase["epoch_end"]):
            return dict(phase)
    raise ValueError(epoch)


def patch_for_epoch(epoch: int, *, smoke: bool = False) -> dict[str, int]:
    if smoke:
        return {"patch_size": 256, "core_size": 128, "scene_batch": 1, "target_effective_scene_batch": 1}
    calibration_path = ROOT / "config" / "gpu_batch_calibration.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8")) if calibration_path.is_file() else {}
    selected = calibration.get("selected_scene_batches", {})
    for row in DESIGN["training"]["patch_schedule"]:
        if int(row["epoch_start"]) <= epoch <= int(row["epoch_end"]):
            stage = dict(row)
            key = str(int(row["patch_size"]))
            stage["scene_batch"] = int(selected.get(key, row["candidate_scene_batch"]))
            stage["gradient_accumulation"] = max(
                1, math.ceil(int(row["target_effective_scene_batch"]) / stage["scene_batch"])
            )
            return {name: int(value) for name, value in stage.items()}
    raise ValueError(epoch)


def learning_rate(epoch: int) -> float:
    anchors = DESIGN["training"]["learning_rate_anchors"]
    if epoch <= int(anchors[0]["epoch"]):
        return float(anchors[0]["learning_rate"])
    for left, right in zip(anchors, anchors[1:]):
        start, end = int(left["epoch"]), int(right["epoch"])
        if start <= epoch <= end:
            position = (epoch - start) / max(end - start, 1)
            blend = 0.5 * (1.0 - math.cos(math.pi * position))
            return float(left["learning_rate"]) + blend * (
                float(right["learning_rate"]) - float(left["learning_rate"])
            )
    return float(anchors[-1]["learning_rate"])


def stage_truth_fraction(epoch: int) -> float:
    phase = phase_for_epoch(epoch)
    if "stage_truth_input_fraction" in phase:
        return float(phase["stage_truth_input_fraction"])
    start, end = (float(v) for v in phase["stage_truth_input_fraction_linear"])
    span = max(int(phase["epoch_end"]) - int(phase["epoch_start"]), 1)
    position = (epoch - int(phase["epoch_start"])) / span
    return start + position * (end - start)


def core_crop(x: torch.Tensor, patch: int, core: int) -> torch.Tensor:
    halo = (patch - core) // 2
    return x[..., halo:halo + core, halo:halo + core]


def gradient_xy(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    kernel = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        device=x.device, dtype=x.dtype,
    ).view(1, 1, 3, 3) / 8.0
    padded = F.pad(x, (1, 1, 1, 1), mode="reflect")
    return F.conv2d(padded, kernel), F.conv2d(padded, kernel.transpose(-1, -2))


def lowpass(x: torch.Tensor, size: int = 9) -> torch.Tensor:
    radius = size // 2
    return F.avg_pool2d(F.pad(x, (radius,) * 4, mode="reflect"), size, stride=1)


def foreground_probability(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    midpoint = midpoint.reshape(-1)
    polarity = polarity.reshape(-1)
    return torch.sigmoid(polarity.view(-1, 1, 1, 1) * (image - midpoint.view(-1, 1, 1, 1)) / 0.04)


def soft_boundary(probability: torch.Tensor) -> torch.Tensor:
    maximum = F.max_pool2d(probability, 5, stride=1, padding=2)
    minimum = -F.max_pool2d(-probability, 5, stride=1, padding=2)
    return (maximum - minimum).clamp(0.0, 1.0)


def centroid(probability: torch.Tensor) -> torch.Tensor:
    h, w = probability.shape[-2:]
    yy = torch.arange(h, device=probability.device, dtype=probability.dtype).view(1, 1, h, 1)
    xx = torch.arange(w, device=probability.device, dtype=probability.dtype).view(1, 1, 1, w)
    mass = probability.sum(dim=(-2, -1)).clamp_min(1e-4)
    return torch.cat([
        (probability * xx).sum(dim=(-2, -1)) / mass,
        (probability * yy).sum(dim=(-2, -1)) / mass,
    ], dim=1)


def _soft_logit_loss(logits: torch.Tensor, truth: torch.Tensor) -> torch.Tensor:
    """Strong gradients at both exact endpoints plus calibrated soft targets."""
    truth = truth.to(logits).clamp(0.0, 1.0)
    return F.binary_cross_entropy_with_logits(logits, truth) + 0.20 * F.smooth_l1_loss(
        torch.sigmoid(logits), truth, beta=0.05,
    )


def _masked_mean(values: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    count = mask.sum()
    total = torch.where(mask, values, torch.zeros_like(values)).sum()
    return total, count


def counterfactual_controls_loss(
    direct_s: dict[str, torch.Tensor],
    direct_t: dict[str, torch.Tensor],
    direct_b: dict[str, torch.Tensor],
    batch: dict[str, Any],
    patch: int,
    core: int,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Jointly supervise S/B/T controls without an all-closed shortcut."""
    truth_need = {
        "s": core_crop(batch["need_truth_s"], patch, core),
        "t": core_crop(batch["need_truth_t"], patch, core),
        "b": core_crop(batch["need_truth_b"], patch, core),
    }
    truth_evidence = {
        "s": core_crop(batch["evidence_truth_s"], patch, core),
        "t": core_crop(batch["evidence_truth_t"], patch, core),
        "b": core_crop(batch["evidence_truth_b"], patch, core),
    }
    direct = {"s": direct_s, "t": direct_t, "b": direct_b}
    need_logits = {
        name: core_crop(outputs["need_logits"], patch, core)
        for name, outputs in direct.items()
    }
    evidence_logits = {
        name: core_crop(outputs["evidence_logits"], patch, core)
        for name, outputs in direct.items()
    }
    need_direct = (
        _soft_logit_loss(need_logits["s"], truth_need["s"])
        + 0.60 * _soft_logit_loss(need_logits["t"], truth_need["t"])
        + 0.80 * _soft_logit_loss(need_logits["b"], truth_need["b"])
    ) / 2.40
    evidence_direct = (
        _soft_logit_loss(evidence_logits["s"], truth_evidence["s"])
        + 0.50 * _soft_logit_loss(evidence_logits["t"], truth_evidence["t"])
        + 0.75 * _soft_logit_loss(evidence_logits["b"], truth_evidence["b"])
    ) / 2.25
    need_probability = {name: torch.sigmoid(value) for name, value in need_logits.items()}
    # The same procedural scene supplies paired differences, so learning must
    # explain which causes disappeared instead of merely matching marginal
    # averages.  Smooth paired regression complements endpoint-safe BCE.
    paired_need = sum(
        F.smooth_l1_loss(
            need_probability[left] - need_probability[right],
            truth_need[left] - truth_need[right], beta=0.05,
        )
        for left, right in (("s", "t"), ("s", "b"), ("b", "t"))
    ) / 3.0
    paired_evidence = sum(
        F.smooth_l1_loss(
            torch.sigmoid(evidence_logits[left]) - torch.sigmoid(evidence_logits[right]),
            truth_evidence[left] - truth_evidence[right], beta=0.05,
        )
        for left, right in (("s", "t"), ("s", "b"), ("b", "t"))
    ) / 3.0
    mask = core_crop(batch["mask"], patch, core).clamp(1e-4, 1.0 - 1e-4)
    support = core_crop(batch["boundary_support_truth"], patch, core)
    geometry = sum(
        F.binary_cross_entropy_with_logits(
            core_crop(outputs["geometry_outputs"][:, 0:1], patch, core), mask,
        )
        for outputs in direct.values()
    ) / 3.0
    boundary = sum(
        F.binary_cross_entropy_with_logits(
            core_crop(outputs["geometry_outputs"][:, 1:2], patch, core), support,
        )
        for outputs in direct.values()
    ) / 3.0
    total = (
        1.45 * need_direct + 0.70 * evidence_direct
        + 0.55 * paired_need + 0.20 * paired_evidence
        + 0.55 * geometry + 0.55 * boundary
    )
    high = truth_need["s"] >= 0.50
    low = truth_need["s"] <= 0.05
    high_sum, high_count = _masked_mean(need_probability["s"], high)
    low_sum, low_count = _masked_mean(need_probability["s"], low)
    high_mean = high_sum / high_count.clamp_min(1)
    low_mean = low_sum / low_count.clamp_min(1)
    return total, {
        "need": F.l1_loss(need_probability["s"], truth_need["s"]),
        "evidence": F.l1_loss(torch.sigmoid(evidence_logits["s"]), truth_evidence["s"]),
        "paired_need": paired_need,
        "geometry": geometry,
        "geometry_boundary": boundary,
        "need_high_mean": high_mean,
        "need_low_mean": low_mean,
        "need_separation": high_mean - low_mean,
        "need_high_sum": high_sum,
        "need_high_count": high_count,
        "need_low_sum": low_sum,
        "need_low_count": low_count,
        "clear_need_mean": need_probability["t"].mean(),
        "noise_free_noise_need": need_probability["b"][:, 1:2].mean(),
    }


def control_triplet(
    model: nn.Module, batch: dict[str, Any], patch: int, core: int,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    source = batch["source"]
    combined = torch.cat([source, batch["target"], batch["noise_free_source"]], dim=0)
    direct = model.forward_control_features(combined)
    count = source.shape[0]
    direct_s = {name: value[:count] for name, value in direct.items()}
    direct_t = {name: value[count:2 * count] for name, value in direct.items()}
    direct_b = {name: value[2 * count:] for name, value in direct.items()}
    return counterfactual_controls_loss(direct_s, direct_t, direct_b, batch, patch, core)


def branch_losses(details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    pairs = {
        "nuisance": (details["nuisance_raw"], batch["nuisance_target"]),
        "radiometry": (details["radiometry_raw"], batch["radiometry_target"]),
        "local_contrast": (details["local_contrast_raw"], batch["local_contrast_target"]),
        "boundary": (details["boundary_restoration_raw"], batch["boundary_target"]),
        "texture": (details["texture_restoration_raw"], batch["texture_target"]),
    }
    values = {
        name: F.smooth_l1_loss(core_crop(prediction, patch, core), core_crop(truth, patch, core), beta=1.0 / 255.0)
        for name, (prediction, truth) in pairs.items()
    }
    return sum(values.values()), values


def full_output_losses(details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    prediction = core_crop(details["output"], patch, core)
    truth = core_crop(batch["supervised_target"], patch, core)
    raw = core_crop(batch["source"], patch, core)
    mask = core_crop(batch["mask"], patch, core)
    pixel = F.l1_loss(prediction, truth)
    pred_low, truth_low = lowpass(prediction, 17), lowpass(truth, 17)
    multiscale = F.l1_loss(pred_low, truth_low) + F.l1_loss(lowpass(prediction, 7), lowpass(truth, 7))
    px, py = gradient_xy(prediction)
    tx, ty = gradient_xy(truth)
    gradient = F.l1_loss(px, tx) + F.l1_loss(py, ty)
    pred_fine = prediction - lowpass(prediction, 7)
    truth_fine = truth - lowpass(truth, 7)
    texture = F.l1_loss(pred_fine, truth_fine)
    boundary = F.l1_loss(
        soft_boundary(foreground_probability(
            prediction, batch["boundary_level"], batch["polarity"],
        )),
        soft_boundary(mask),
    )
    correction = prediction - raw
    cancellation = (
        details["nuisance_delta"].abs() + details["radiometry_delta"].abs()
        + details["local_contrast_delta"].abs() + details["boundary_delta"].abs()
        + details["texture_delta"].abs() - details["correction"].abs()
    ).clamp_min(0.0)
    cancellation = core_crop(cancellation, patch, core).mean()
    identity_mask = batch["identity"].reshape(-1)
    identity = correction.new_zeros(())
    if bool(identity_mask.any()):
        identity = core_crop(correction, patch, core)[identity_mask].abs().mean()
    total = 1.6 * pixel + 0.6 * multiscale + 0.7 * gradient + 0.8 * texture + 0.5 * boundary + 0.25 * cancellation + 1.3 * identity
    return total, {
        "pixel": pixel, "multiscale": multiscale, "gradient": gradient,
        "texture": texture, "contour": boundary, "cancellation": cancellation,
        "identity": identity,
    }


def motion_loss(
    details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int,
    scenes: int, views: int,
) -> torch.Tensor:
    prediction = core_crop(details["output"], patch, core)
    target = core_crop(batch["target"], patch, core)
    if views < 2:
        return details["output"].sum() * 0.0
    pair_kind = batch["pair_kind"].reshape(-1)
    eligible = pair_kind == 1
    if not bool(eligible.any()):
        return details["output"].sum() * 0.0
    prediction = prediction.reshape(scenes, views, 1, core, core)
    target = target.reshape(scenes, views, 1, core, core)
    mask = core_crop(batch["mask"], patch, core)
    probability = foreground_probability(
        prediction.reshape(-1, 1, core, core),
        batch["boundary_level"],
        batch["polarity"],
    )
    pred_centers = centroid(soft_boundary(probability)).reshape(scenes, views, 2)
    truth_centers = centroid(soft_boundary(mask)).reshape(scenes, views, 2)
    errors = (pred_centers[:, 1] - pred_centers[:, 0]) - (truth_centers[:, 1] - truth_centers[:, 0])
    errors = errors[eligible]
    if errors.numel() == 0:
        # Keep a differentiable zero so grouped gradient projection remains
        # valid on batches that do not contain the signed-motion role.
        return details["output"].sum() * 0.0
    return F.smooth_l1_loss(errors, torch.zeros_like(errors), beta=0.1)


def translation_consistency(model: nn.Module, source: torch.Tensor) -> torch.Tensor:
    if min(source.shape[-2:]) < 64:
        return source.new_zeros(())
    shift = (8, -8)
    with torch.no_grad():
        reference = model(source)
    shifted = torch.roll(source, shifts=shift, dims=(-2, -1))
    prediction = model(shifted)
    expected = torch.roll(reference, shifts=shift, dims=(-2, -1))
    return F.l1_loss(prediction[..., 32:-32, 32:-32], expected[..., 32:-32, 32:-32])


def cross_noise_consistency(
    details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int,
    scenes: int, views: int,
) -> torch.Tensor:
    if views < 2:
        return details["output"].sum() * 0.0
    pair_kind = batch["pair_kind"].reshape(-1)
    eligible = (pair_kind == 1) | (pair_kind == 3) | (pair_kind == 4)
    if not bool(eligible.any()):
        return details["output"].sum() * 0.0
    output = core_crop(details["output"], patch, core).reshape(scenes, views, 1, core, core)
    target = core_crop(batch["target"], patch, core).reshape(scenes, views, 1, core, core)
    residual = output - target
    residual = residual[eligible]
    if residual.numel() == 0:
        return details["output"].sum() * 0.0
    return F.l1_loss(residual[:, 1:], residual[:, :1].expand_as(residual[:, 1:]))


def update_ema(model: nn.Module, ema: nn.Module, decay: float) -> None:
    with torch.no_grad():
        for target, source in zip(ema.parameters(), model.parameters()):
            target.mul_(decay).add_(source, alpha=1.0 - decay)
        for target, source in zip(ema.buffers(), model.buffers()):
            target.copy_(source)


def adaptive_ema_decay(update_count: int, maximum: float) -> float:
    """Remove initialization quickly, then become a stable late-run average."""
    warm_decay = (1.0 + float(update_count)) / (10.0 + float(update_count))
    return min(float(maximum), warm_decay)


def backward_common_descent(
    primary_loss: torch.Tensor,
    auxiliary_losses: list[torch.Tensor],
    parameters: list[nn.Parameter],
    divisor: float,
) -> dict[str, float]:
    """Accumulate a first-order descent direction shared by all objectives.

    Cross-scene motion, noise and translation objectives are never inserted as
    an unconstrained weighted sum.  If no non-opposing direction exists, this
    update becomes zero as declared in the locked design.
    """
    active = [parameter for parameter in parameters if parameter.requires_grad]
    scaled_auxiliary = [
        loss / float(divisor)
        for loss in auxiliary_losses
        if loss.requires_grad and float(loss.detach().abs()) > 0.0
    ]
    auxiliary_gradients: list[tuple[torch.Tensor | None, ...]] = []
    for loss in scaled_auxiliary:
        auxiliary_gradients.append(tuple(torch.autograd.grad(
            loss, active, retain_graph=True, allow_unused=True,
        )))
    primary_gradients = tuple(torch.autograd.grad(
        primary_loss / float(divisor), active, retain_graph=False, allow_unused=True,
    ))

    def flatten(values: tuple[torch.Tensor | None, ...]) -> torch.Tensor:
        return torch.cat([
            (
                torch.zeros_like(parameter, memory_format=torch.contiguous_format)
                if gradient is None else gradient.contiguous()
            ).reshape(-1)
            for parameter, gradient in zip(active, values)
        ])

    primary_flat = flatten(primary_gradients)
    task_flats = [primary_flat] + [flatten(values) for values in auxiliary_gradients]
    if auxiliary_gradients:
        direction = COMMON.common_descent_direction(task_flats, passes=8)
        primary_norm = primary_flat.norm()
        direction_norm = direction.norm()
        if float(direction_norm) > 0.0:
            direction = direction * torch.minimum(
                direction.new_tensor(1.0), 1.25 * primary_norm / direction_norm.clamp_min(1e-12),
            )
    else:
        direction = primary_flat

    offset = 0
    for parameter in active:
        count = parameter.numel()
        gradient = direction[offset:offset + count].view_as(parameter)
        if parameter.grad is None:
            parameter.grad = gradient.detach().clone()
        else:
            parameter.grad.add_(gradient.detach())
        offset += count
    dots = [float(torch.dot(direction, task).detach()) for task in task_flats]
    return {
        "common_direction_norm": float(direction.norm().detach()),
        "common_primary_dot": dots[0],
        "common_min_aux_dot": min(dots[1:]) if len(dots) > 1 else 0.0,
    }


def flatten_batch(batch: dict[str, Any], device: torch.device) -> tuple[dict[str, Any], int, int]:
    scenes, views = batch["source"].shape[:2]
    result: dict[str, Any] = {}
    for name, value in batch.items():
        if torch.is_tensor(value):
            moved = value.to(device, non_blocking=True)
            if moved.ndim >= 2 and tuple(moved.shape[:2]) == (scenes, views):
                result[name] = moved.reshape(scenes * views, *moved.shape[2:])
            elif name in {"boundary_level", "polarity"} and moved.ndim >= 1 and moved.shape[0] == scenes:
                result[name] = moved.repeat_interleave(views, dim=0)
            else:
                result[name] = moved
        else:
            result[name] = value
    return result, scenes, views


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device, patch: int, core: int, max_batches: int = 0) -> dict[str, float]:
    model.eval()
    sums: defaultdict[str, float] = defaultdict(float)
    count = 0
    need_high_sum = 0.0
    need_high_count = 0.0
    need_low_sum = 0.0
    need_low_count = 0.0
    roles_seen: defaultdict[str, int] = defaultdict(int)
    motion_errors: list[float] = []
    for index, raw_batch in enumerate(loader, start=1):
        batch, scenes, views = flatten_batch(raw_batch, device)
        for role in raw_batch.get("role", []):
            roles_seen[str(role)] += 1
        details = model(batch["source"], return_details=True)
        _, values = full_output_losses(details, batch, patch, core)
        _, branches = branch_losses(details, batch, patch, core)
        _, controls_values = control_triplet(model, batch, patch, core)
        need_high_sum += float(controls_values.pop("need_high_sum"))
        need_high_count += float(controls_values.pop("need_high_count"))
        need_low_sum += float(controls_values.pop("need_low_sum"))
        need_low_count += float(controls_values.pop("need_low_count"))
        # These per-batch ratios are recomputed once from the pooled pixels
        # below; averaging them would bias roles with very few high pixels.
        controls_values.pop("need_high_mean", None)
        controls_values.pop("need_low_mean", None)
        controls_values.pop("need_separation", None)
        for name, value in {**values, **{f"branch_{k}": v for k, v in branches.items()}, **controls_values}.items():
            sums[name] += float(value) * scenes
        m = float(motion_loss(details, batch, patch, core, scenes, views))
        sums["motion"] += m * scenes
        motion_errors.append(m)
        count += scenes
        if max_batches and index >= max_batches:
            break
    metrics = {name: value / max(count, 1) for name, value in sums.items()}
    metrics["need_high_mean"] = need_high_sum / max(need_high_count, 1.0)
    metrics["need_low_mean"] = need_low_sum / max(need_low_count, 1.0)
    metrics["need_separation"] = metrics["need_high_mean"] - metrics["need_low_mean"]
    metrics["motion_p95_proxy"] = float(np.quantile(motion_errors, 0.95)) if motion_errors else 0.0
    metrics["validation_role_count"] = float(len(roles_seen))
    metrics["detail_axis"] = metrics.get("texture", 0.0)
    metrics["contour_axis"] = metrics.get("contour", 0.0)
    metrics["identity_axis"] = metrics.get("identity", 0.0) * 255.0
    metrics["motion_axis"] = metrics.get("motion", 0.0)
    metrics["worst_axis"] = max(metrics["detail_axis"], metrics["contour_axis"], metrics["motion_axis"], metrics["identity_axis"] / 255.0)
    return metrics


def read_grayscale(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(path)
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    return image.astype(np.float32) / float(np.iinfo(image.dtype).max)


@torch.no_grad()
def save_real_previews(model: nn.Module, device: torch.device, epoch: int) -> list[str]:
    input_dir = ROOT / "data" / "live_validation"
    output_dir = RESULTS / "real_live_validation" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    model.eval()
    for source_path in sorted(input_dir.glob("*.bmp")):
        raw = np.clip(read_grayscale(source_path), 0.0, 1.0)
        tensor = torch.from_numpy(raw)[None, None].to(device)
        prediction = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)[0, 0].cpu().numpy()
        difference = np.clip(np.abs(prediction - raw) * 8.0, 0.0, 1.0)
        sheet = np.rint(np.concatenate([raw, prediction, difference], axis=1) * 255.0).astype(np.uint8)
        width = raw.shape[1]
        cv2.putText(sheet, "RAW", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet, f"R95 E{epoch}", (width + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        cv2.putText(sheet, "ABS DIFF x8", (2 * width + 8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        path = output_dir / f"{source_path.stem}_raw_r95_diff.png"
        if not cv2.imwrite(str(path), sheet):
            raise RuntimeError(path)
        outputs.append(str(path))
    return outputs


@torch.no_grad()
def save_synthetic_previews(model: nn.Module, dataset: Any, device: torch.device, epoch: int) -> list[str]:
    output_dir = RESULTS / "synthetic_live_validation" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    seen: set[str] = set()
    model.eval()
    for index in range(len(dataset)):
        role = dataset.role_at(index)
        if role in seen:
            continue
        seen.add(role)
        item = dataset[index]
        raw = item["source"][0:1].to(device)
        prediction = model(raw)[0, 0].cpu().numpy()
        target = item["supervised_target"][0, 0].numpy()
        raw_array = item["source"][0, 0].numpy()
        sheet = np.rint(np.clip(np.concatenate([raw_array, prediction, target], axis=1), 0, 1) * 255.0).astype(np.uint8)
        width = raw_array.shape[1]
        for label, x in (("RAW", 8), (f"R95 E{epoch}", width + 8), ("TARGET", 2 * width + 8)):
            cv2.putText(sheet, label, (x, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
        path = output_dir / f"validation_{len(outputs):02d}_{role}.png"
        cv2.imwrite(str(path), sheet)
        outputs.append(str(path))
        if len(outputs) == 7:
            break
    return outputs


def checkpoint_payload(model: nn.Module, ema: nn.Module, epoch: int, metrics: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": DESIGN["experiment_id"], "epoch": int(epoch),
        "model_state_dict": model.state_dict(), "ema_state_dict": ema.state_dict(),
        "metrics": metrics, "metadata": metadata, "checkpoint_loaded": False,
        "resume_source": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--max-validation-batches", type=int, default=0)
    args = parser.parse_args()
    forbidden = ("checkpoint", "resume", "pretrain", "teacher", "pseudo")
    if any(token in " ".join(sys.argv).lower() for token in forbidden):
        raise RuntimeError("R95 formal runs cannot inherit a checkpoint or teacher")
    if args.run_kind == "formal" and not bool(DESIGN.get("formal_training_authorized")):
        raise RuntimeError("Formal R95 training is not authorized")
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.set_num_threads(1)
    seed = int(DESIGN["independence"]["seed"])
    seed_everything(seed)
    package = Path(DESIGN["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    if manifest["content_sha256"] != DESIGN["data"]["source_content_sha256"] or not audit.get("passed"):
        raise RuntimeError("Source package audit/hash mismatch")
    if args.run_kind == "formal" and (RUNS / "formal_run_registry.json").is_file():
        registry = json.loads((RUNS / "formal_run_registry.json").read_text(encoding="utf-8"))
        formal_runs = registry.get("formal_runs", [])
        if formal_runs:
            only = formal_runs[0]
            reusable_pre_epoch = (
                len(formal_runs) == 1
                and int(only.get("completed_epoch", 0)) == 0
                and str(only.get("status", "")) in {"starting", "aborted_before_first_epoch_for_data_loader_optimization"}
            )
            if not reusable_pre_epoch:
                raise RuntimeError("The one authorized R95 formal run already exists")
            # No epoch or optimizer step was completed; replacing this launch
            # preserves the one-run scratch contract.
            (RUNS / "formal_run_registry.json").unlink()

    model = MODEL.build_model(base=int(DESIGN["architecture"]["model_width"])).to(device)
    ema = copy.deepcopy(model).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    parameter_count = MODEL.count_parameters(model)
    if parameter_count != int(DESIGN["architecture"]["parameter_count"]):
        raise RuntimeError("Architecture parameter count changed")
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(DESIGN["training"]["peak_learning_rate"]),
        weight_decay=float(DESIGN["training"]["weight_decay"]),
    )
    if device.type == "cuda":
        # Materialize CUDA/cuDNN before starting the first data epoch.  This
        # avoids a large first-convolution workspace/JIT surprise inside the
        # formal epoch and makes failures visible before any optimizer step.
        warmup = torch.zeros((1, 1, 64, 64), device=device)
        with torch.no_grad(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            model.forward_controls(warmup)
        torch.cuda.synchronize(device)
        del warmup
        torch.cuda.empty_cache()
        if model.need_head.weight.device.type != "cuda":
            raise RuntimeError("R95 model did not remain on CUDA after warmup")
    run_id = f"R95_scratch_seed{seed}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    record_dir = RUNS / (("training_" if args.run_kind == "formal" else "smoke_") + run_id)
    weight_dir = ROOT / "weights" / args.run_kind / f"seed_{seed}" / run_id / "weights"
    record_dir.mkdir(parents=True, exist_ok=False)
    weight_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "experiment_id": DESIGN["experiment_id"], "run_id": run_id,
        "run_kind": args.run_kind, "seed": seed, "device": str(device),
        "parameter_count": parameter_count, "initial_parameter_sha256": state_sha256(model),
        "model_sha256": sha256_file(MODEL_PATH), "trainer_sha256": sha256_file(Path(__file__)),
        "design_sha256": sha256_file(DESIGN_PATH), "dataset_content_sha256": manifest["content_sha256"],
        "checkpoint_loaded": False, "resume_source": None, "teacher_used": False,
        "real_training_pixels": False, "optimizer_fresh": True,
        "started_at": datetime.now().isoformat(), "weight_dir": str(weight_dir),
    }
    startup_trace_path = record_dir / "startup_trace.json"
    json_write(startup_trace_path, {**metadata, "stage": "model_optimizer_and_cuda_warmup_ready", "at": datetime.now().isoformat()})
    json_write(record_dir / "scratch_initialization_audit.json", metadata)
    if args.run_kind == "formal":
        json_write(RUNS / "formal_run_registry.json", {
            "experiment_id": DESIGN["experiment_id"], "formal_run_limit": 1,
            "formal_runs": [{"run_id": run_id, "status": "starting", **metadata}],
        })
    total_epochs = 1 if args.run_kind == "smoke" else int(DESIGN["training"]["planned_epochs"])
    fields = [
        "epoch", "phase", "lr", "seconds", "patch", "core", "scene_batch", "accumulation",
        "stage_truth_fraction", "ema_decay", "optimizer_updates", "gpu_peak_gib",
        "gpu_reserved_gib", "gpu_incremental_reserved_gib", "gpu_peak_free_gib",
        "gpu_current_free_gib",
        "loader_workers_requested", "loader_workers_effective",
        "train_total", "train_controls", "train_branches", "train_output", "train_motion",
        "train_cross_noise", "train_translation", "train_need_separation",
        "val_need_separation", "val_clear_need_mean", "val_detail_axis", "val_contour_axis",
        "val_identity_axis", "val_motion_axis", "val_worst_axis",
    ]
    with (record_dir / "training_log.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()
    active_path = RUNS / "active_run.json"
    latest_validation: dict[str, float] = {}
    optimizer_updates = 0
    current_ema_decay = 0.0
    try:
        for epoch in range(1, total_epochs + 1):
            started = time.perf_counter()
            phase = phase_for_epoch(epoch)
            if epoch <= 6:
                active_groups = {"need_control", "evidence_control", "geometry"}
            elif epoch <= 14:
                active_groups = {
                    "need_control", "evidence_control", "geometry", "nuisance",
                    "radiometry", "local_contrast", "boundary", "texture",
                }
            else:
                active_groups = None
            model.set_active_training_groups(active_groups)
            ema.set_active_training_groups(active_groups)
            stage = patch_for_epoch(epoch, smoke=args.run_kind == "smoke")
            patch, core = stage["patch_size"], stage["core_size"]
            scene_batch = stage["scene_batch"]
            accumulation = stage.get("gradient_accumulation", 1)
            fraction = stage_truth_fraction(epoch) if args.run_kind == "formal" else 1.0
            dataset = DATA.R95SceneDataset(
                package, manifest, "train", patch, core, epoch,
                master_seed=seed,
            )
            sampler = DATA.RoleBalancedBatchSampler(dataset, scene_batch, seed + epoch * 101)
            loader_workers = 0 if os.name == "nt" else int(args.num_workers)
            loader = DataLoader(
                dataset, batch_sampler=sampler, num_workers=loader_workers,
                pin_memory=device.type == "cuda", persistent_workers=False,
            )
            json_write(startup_trace_path, {
                **metadata, "stage": "epoch_loader_ready", "epoch": epoch,
                "dataset_items": len(dataset), "loader_batches": len(loader),
                "at": datetime.now().isoformat(),
            })
            lr = learning_rate(epoch)
            for group in optimizer.param_groups:
                group["lr"] = lr
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
                free_before, total_memory = torch.cuda.mem_get_info(device)
                reserved_before = torch.cuda.memory_reserved(device)
            else:
                total_memory = 0
                free_before = 0
                reserved_before = 0
            model.train()
            optimizer.zero_grad(set_to_none=True)
            sums: defaultdict[str, float] = defaultdict(float)
            seen = 0
            batch_index = 0
            formal_batch_limit = int(DESIGN["training"].get("batches_per_epoch", 0)) if args.run_kind == "formal" else 0
            for raw_batch in loader:
                batch_index += 1
                dataset.set_role_cycle(batch_index % 4)
                if batch_index == 1:
                    json_write(startup_trace_path, {
                        **metadata, "stage": "first_real_batch_loaded", "epoch": epoch,
                        "at": datetime.now().isoformat(),
                    })
                batch, scenes, views = flatten_batch(raw_batch, device)
                total_views = scenes * views
                scene_order = torch.arange(scenes, device=device)
                scene_chunks = list(scene_order.split(max(1, scene_batch // views)))
                for chunk_index, selected_scenes in enumerate(scene_chunks):
                    selected_views = torch.cat([
                        torch.arange(int(scene) * views, (int(scene) + 1) * views, device=device)
                        for scene in selected_scenes
                    ])
                    image_batch: dict[str, Any] = {}
                    for name, value in batch.items():
                        if torch.is_tensor(value) and value.ndim >= 1 and value.shape[0] == total_views:
                            image_batch[name] = value[selected_views]
                        elif name == "pair_kind" and torch.is_tensor(value) and value.ndim >= 1 and value.shape[0] == scenes:
                            image_batch[name] = value[selected_scenes]
                        else:
                            image_batch[name] = value
                    local_scenes = int(selected_scenes.numel())
                    source = image_batch["source"]
                    if batch_index == 1 and chunk_index == 0 and source.device.type != device.type:
                        raise RuntimeError(f"First R95 batch is on {source.device}, expected {device}")
                    with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
                        if batch_index == 1 and chunk_index == 0:
                            json_write(startup_trace_path, {
                                **metadata, "stage": "first_gpu_forward_started", "epoch": epoch,
                                "at": datetime.now().isoformat(),
                            })
                        if epoch <= 6:
                            # Controls/geometry only: one concatenated tower pass
                            # for S, exact T and B counterfactuals.  Correction
                            # paths stay frozen at their identity initialization.
                            combined = torch.cat([source, image_batch["target"], image_batch["noise_free_source"]], dim=0)
                            direct = model.forward_control_features(combined)
                            if batch_index == 1 and chunk_index == 0:
                                json_write(startup_trace_path, {
                                    **metadata, "stage": "first_gpu_forward_finished", "epoch": epoch,
                                    "at": datetime.now().isoformat(),
                                })
                            count = source.shape[0]
                            direct_s = {name: value[:count] for name, value in direct.items()}
                            direct_t = {name: value[count:2 * count] for name, value in direct.items()}
                            direct_b = {name: value[2 * count:] for name, value in direct.items()}
                            control_total, _control_values = counterfactual_controls_loss(
                                direct_s, direct_t, direct_b, image_batch, patch, core,
                            )
                            branch_total = source.new_zeros(())
                            output_total = source.new_zeros(())
                            motion = source.new_zeros(())
                            cross_noise = source.new_zeros(())
                            translation = source.new_zeros(())
                            total = control_total
                        elif epoch <= 14:
                            control_total, _control_values = control_triplet(
                                model, image_batch, patch, core,
                            )
                            stage_truth = {
                                "sensor_clean_base": image_batch["noise_free_source"],
                                "restoration_base": image_batch["optical_source"],
                                "contrast_restored_base": image_batch["optical_source"] + image_batch["local_contrast_target"],
                                "need_truth": image_batch["need_truth_s"],
                                "evidence_truth": image_batch["evidence_truth_s"],
                            }
                            details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=fraction)
                            branch_total, _branch_values = branch_losses(details, image_batch, patch, core)
                            output_total = source.new_zeros(())
                            motion = source.new_zeros(())
                            cross_noise = source.new_zeros(())
                            translation = source.new_zeros(())
                            total = 0.75 * control_total + branch_total
                        else:
                            control_total, _control_values = control_triplet(
                                model, image_batch, patch, core,
                            )
                            stage_truth = {
                                "sensor_clean_base": image_batch["noise_free_source"],
                                "restoration_base": image_batch["optical_source"],
                                "contrast_restored_base": image_batch["optical_source"] + image_batch["local_contrast_target"],
                                "need_truth": image_batch["need_truth_s"],
                                "evidence_truth": image_batch["evidence_truth_s"],
                            }
                            details = model(source, return_details=True, stage_truth=stage_truth, stage_truth_fraction=fraction)
                            branch_total, _branch_values = branch_losses(details, image_batch, patch, core)
                            output_total, _output_values = full_output_losses(details, image_batch, patch, core)
                            motion = motion_loss(details, image_batch, patch, core, local_scenes, views)
                            cross_noise = cross_noise_consistency(details, image_batch, patch, core, local_scenes, views)
                            translation = source.new_zeros(())
                            if epoch <= 26:
                                primary_total = 0.70 * control_total + branch_total + 0.70 * output_total
                                auxiliary_totals: list[torch.Tensor] = []
                            else:
                                primary_total = 0.55 * control_total + branch_total + output_total
                                auxiliary_totals = [0.30 * motion, 0.25 * cross_noise]
                                if batch_index % 8 == 0 and chunk_index == 0:
                                    translation = translation_consistency(model, source[:1])
                                    auxiliary_totals.append(0.15 * translation)
                            total = primary_total + sum(auxiliary_totals)
                    if not bool(torch.isfinite(total)):
                        raise FloatingPointError("Non-finite R95 loss")
                    divisor = float(accumulation * len(scene_chunks))
                    if epoch >= 27:
                        backward_common_descent(
                            primary_total, auxiliary_totals,
                            list(model.parameters()), divisor,
                        )
                    else:
                        (total / divisor).backward()
                    if batch_index == 1 and chunk_index == 0:
                        json_write(startup_trace_path, {
                            **metadata, "stage": "first_backward_finished", "epoch": epoch,
                            "at": datetime.now().isoformat(),
                        })
                    for name, value in {
                        "total": total, "controls": control_total, "branches": branch_total,
                        "output": output_total, "motion": motion,
                        "cross_noise": cross_noise,
                        "translation": translation,
                        "need_separation": _control_values["need_separation"],
                    }.items():
                        sums[name] += float(value.detach()) * local_scenes
                    seen += local_scenes
                if batch_index % accumulation == 0 or batch_index == len(loader):
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    if not bool(torch.isfinite(norm)):
                        raise FloatingPointError("Non-finite R95 gradient")
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_updates += 1
                    current_ema_decay = adaptive_ema_decay(
                        optimizer_updates, float(DESIGN["training"]["ema_decay"]),
                    )
                    update_ema(model, ema, current_ema_decay)
                if (args.max_train_batches and batch_index >= args.max_train_batches) or (
                    formal_batch_limit and batch_index >= formal_batch_limit
                ):
                    break
            train_metrics = {name: value / max(seen, 1) for name, value in sums.items()}
            validate_now = epoch == 1 or epoch % int(DESIGN["training"]["validation_every_epochs"]) == 0 or epoch == total_epochs
            preview_paths: list[str] = []
            real_preview_paths: list[str] = []
            if validate_now:
                model_groups = ema._active_training_groups
                ema.set_active_training_groups(None)
                validation_patch, validation_core = ((256, 128) if args.run_kind == "smoke" else (768, 384))
                validation_dataset = DATA.R95SceneDataset(
                    package, manifest, "validation", validation_patch, validation_core, 0,
                    all_observations=True, master_seed=seed,
                )
                validation_loader = DataLoader(
                    validation_dataset,
                    batch_sampler=DATA.RoleBalancedValidationSampler(
                        validation_dataset,
                        per_role=int(DESIGN["training"].get("validation_scenes_per_role", 8)),
                    ),
                    num_workers=0 if os.name == "nt" else int(args.num_workers), pin_memory=device.type == "cuda",
                )
                latest_validation = evaluate(
                    ema, validation_loader, device, validation_patch, validation_core,
                    max_batches=int(args.max_validation_batches),
                )
                preview_paths = save_synthetic_previews(ema, validation_dataset, device, epoch)
                if epoch % int(DESIGN["training"]["live_real_preview_every_epochs"]) == 0 or epoch == total_epochs:
                    real_preview_paths = save_real_previews(ema, device, epoch)
                ema.set_active_training_groups(model_groups)
            elapsed = time.perf_counter() - started
            peak = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
            reserved = torch.cuda.max_memory_reserved(device) / 2**30 if device.type == "cuda" else 0.0
            incremental_reserved = max(0.0, (torch.cuda.max_memory_reserved(device) - reserved_before) / 2**30) if device.type == "cuda" else 0.0
            peak_free = max(0.0, free_before / 2**30 - incremental_reserved) if device.type == "cuda" else 0.0
            current_free = torch.cuda.mem_get_info(device)[0] / 2**30 if device.type == "cuda" else 0.0
            minimum_free = float(DESIGN["training"]["gpu_batch_calibration"]["minimum_memory_left_for_desktop_gib"])
            if args.run_kind == "formal" and peak_free < minimum_free:
                raise RuntimeError(f"R95 stopped: only {peak_free:.2f} GiB measured free at peak")
            row = {
                "epoch": epoch, "phase": phase["name"], "lr": lr, "seconds": elapsed,
                "patch": patch, "core": core, "scene_batch": scene_batch,
                "accumulation": accumulation, "stage_truth_fraction": fraction,
                "ema_decay": current_ema_decay, "optimizer_updates": optimizer_updates,
                "gpu_peak_gib": peak, "gpu_reserved_gib": reserved,
                "gpu_incremental_reserved_gib": incremental_reserved,
                "gpu_peak_free_gib": peak_free, "gpu_current_free_gib": current_free,
                "loader_workers_requested": int(args.num_workers),
                "loader_workers_effective": 0 if os.name == "nt" else int(args.num_workers),
                **{f"train_{name}": train_metrics.get(name, "") for name in ("total", "controls", "branches", "output", "motion", "cross_noise", "translation", "need_separation")},
                "val_need_separation": latest_validation.get("need_separation", "") if validate_now else "",
                "val_clear_need_mean": latest_validation.get("clear_need_mean", "") if validate_now else "",
                **{f"val_{name}": latest_validation.get(name, "") if validate_now else "" for name in ("detail_axis", "contour_axis", "identity_axis", "motion_axis", "worst_axis")},
            }
            with (record_dir / "training_log.csv").open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fields).writerow(row)
            metrics = {
                "train": train_metrics, "validation": latest_validation if validate_now else None,
                "phase": phase, "stage": stage, "stage_truth_fraction": fraction,
                "lr": lr, "seconds": elapsed, "gpu_peak_gib": peak,
                "ema_decay": current_ema_decay, "optimizer_updates": optimizer_updates,
                "gpu_reserved_gib": reserved,
                "gpu_incremental_reserved_gib": incremental_reserved,
                "gpu_peak_free_gib": peak_free, "gpu_current_free_gib": current_free,
            }
            if epoch == 1 or epoch % int(DESIGN["training"]["checkpoint_every_epochs"]) == 0 or epoch == total_epochs:
                payload = checkpoint_payload(model, ema, epoch, metrics, metadata)
                torch.save(payload, weight_dir / f"epoch_{epoch:03d}.pth.tar")
                torch.save(payload, weight_dir / "latest.pth.tar")
            progress = {
                **metadata, "status": "active", "planned_epochs": total_epochs,
                "completed_epoch": epoch, "latest_metrics": metrics,
                "synthetic_preview_paths": preview_paths, "real_preview_paths": real_preview_paths,
            }
            json_write(active_path, progress)
            json_write(record_dir / "run_progress.json", progress)
            if args.run_kind == "formal":
                registry = json.loads((RUNS / "formal_run_registry.json").read_text(encoding="utf-8"))
                registry["formal_runs"][0].update(status="active", completed_epoch=epoch)
                json_write(RUNS / "formal_run_registry.json", registry)
            print(json.dumps({"epoch": epoch, "phase": phase["name"], "train": train_metrics, "validation": latest_validation if validate_now else None, "seconds": elapsed, "gpu_peak_gib": peak, "gpu_peak_free_gib": peak_free, "ema_decay": current_ema_decay, "optimizer_updates": optimizer_updates}, ensure_ascii=False), flush=True)
            if args.max_train_batches:
                break
        status = "complete" if args.run_kind == "formal" and epoch == total_epochs else "smoke_complete"
        summary = {
            **metadata, "status": status, "planned_epochs": total_epochs,
            "completed_epoch": epoch, "final_validation": latest_validation,
            "finished_at": datetime.now().isoformat(), "training_log": str(record_dir / "training_log.csv"),
        }
        json_write(active_path, summary)
        json_write(record_dir / "run_summary.json", summary)
        if args.run_kind == "formal":
            registry = json.loads((RUNS / "formal_run_registry.json").read_text(encoding="utf-8"))
            registry["formal_runs"][0].update(status=status, completed_epoch=epoch, finished_at=summary["finished_at"])
            json_write(RUNS / "formal_run_registry.json", registry)
        return 0
    except BaseException as exc:
        failure = {**metadata, "status": "failed", "error": repr(exc), "failed_at": datetime.now().isoformat()}
        json_write(active_path, failure)
        json_write(record_dir / "failure.json", failure)
        if args.run_kind == "formal" and (RUNS / "formal_run_registry.json").is_file():
            registry = json.loads((RUNS / "formal_run_registry.json").read_text(encoding="utf-8"))
            registry["formal_runs"][0].update(status="failed", error=repr(exc))
            json_write(RUNS / "formal_run_registry.json", registry)
        raise


if __name__ == "__main__":
    raise SystemExit(main())

