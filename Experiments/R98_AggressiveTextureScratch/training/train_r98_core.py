"""R98 scratch trainer: aggressive source-locked detail with position guards."""
from __future__ import annotations

import argparse
import copy
import csv
from datetime import datetime
import hashlib
import importlib.util
import json
import math
import msvcrt
import os
from pathlib import Path
import random
import sys
import time
from typing import Any
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r98_model.py"
DATASET_PATH = ROOT / "training" / "r98_dataset.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
PERIODIC_PATH = ROOT / "training" / "periodic_disambiguation.py"
TARGETS_PATH = ROOT / "training" / "counterfactual_targets.py"
REPLAY_PATH = ROOT / "training" / "causal_stage_replay.py"
DESIGN = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r98_core_model", MODEL_PATH)
DATA = load_module("r98_core_data", DATASET_PATH)
INFERENCE = load_module("r98_core_inference", INFERENCE_PATH)
PERIODIC = load_module("r98_core_periodic", PERIODIC_PATH)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def save_checkpoint(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def acquire_formal_lock():
    """Hold one Windows byte-range lock for the lifetime of a formal trainer."""
    path = ROOT / "runs" / "formal_trainer.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        raise RuntimeError("the sole R98 formal trainer is already running") from exc
    return handle


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def model_hash(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")


def phase_for_epoch(epoch: int) -> dict[str, Any]:
    for phase in DESIGN["training"]["phases"]:
        if int(phase["epoch_start"]) <= epoch <= int(phase["epoch_end"]):
            return dict(phase)
    raise ValueError(epoch)


def stage_for_epoch(epoch: int, smoke: bool) -> dict[str, int]:
    if smoke:
        return {"patch_size": 256, "core_size": 128, "scene_batch": 1, "accumulation": 1}
    policy_path = ROOT / "config" / "execution_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8")) if policy_path.is_file() else {}
    overrides = policy.get("scene_batch_overrides", {})
    for stage in DESIGN["training"]["patch_schedule"]:
        if int(stage["epoch_start"]) <= epoch <= int(stage["epoch_end"]):
            patch = int(stage["patch_size"])
            scene_batch = int(overrides.get(str(patch), stage["candidate_scene_batch"]))
            target = int(stage["target_effective_scene_batch"])
            return {
                "patch_size": patch,
                "core_size": int(stage["core_size"]),
                "scene_batch": scene_batch,
                "accumulation": max(1, math.ceil(target / scene_batch)),
            }
    raise ValueError(epoch)


def learning_rate(epoch: int) -> float:
    anchors = DESIGN["training"]["learning_rate_anchors"]
    if epoch <= int(anchors[0]["epoch"]):
        return float(anchors[0]["learning_rate"])
    for left, right in zip(anchors, anchors[1:]):
        if int(left["epoch"]) <= epoch <= int(right["epoch"]):
            position = (epoch - int(left["epoch"])) / max(1, int(right["epoch"]) - int(left["epoch"]))
            blend = 0.5 * (1.0 - math.cos(math.pi * position))
            return float(left["learning_rate"]) + blend * (float(right["learning_rate"]) - float(left["learning_rate"]))
    return float(anchors[-1]["learning_rate"])


def stage_truth_fraction(epoch: int) -> float:
    phase = phase_for_epoch(epoch)
    if "stage_truth_input_fraction" in phase:
        return float(phase["stage_truth_input_fraction"])
    start, end = (float(value) for value in phase["stage_truth_input_fraction_linear"])
    span = max(1, int(phase["epoch_end"]) - int(phase["epoch_start"]))
    position = (epoch - int(phase["epoch_start"])) / span
    return start + position * (end - start)


def core_crop(x: torch.Tensor, patch: int, core: int) -> torch.Tensor:
    halo = (patch - core) // 2
    return x[..., halo:halo + core, halo:halo + core]


def lowpass(x: torch.Tensor, size: int) -> torch.Tensor:
    radius = size // 2
    return F.avg_pool2d(F.pad(x, (radius,) * 4, mode="reflect"), size, stride=1)


def gradients(x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    kernel = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        device=x.device, dtype=x.dtype,
    ).view(1, 1, 3, 3) / 8.0
    padded = F.pad(x, (1, 1, 1, 1), mode="reflect")
    return F.conv2d(padded, kernel), F.conv2d(padded, kernel.transpose(-1, -2))


def soft_boundary(x: torch.Tensor) -> torch.Tensor:
    maximum = F.max_pool2d(x, 5, stride=1, padding=2)
    minimum = -F.max_pool2d(-x, 5, stride=1, padding=2)
    return (maximum - minimum).clamp(0.0, 1.0)


def foreground(image: torch.Tensor, midpoint: torch.Tensor, polarity: torch.Tensor) -> torch.Tensor:
    return torch.sigmoid(
        polarity.reshape(-1, 1, 1, 1)
        * (image - midpoint.reshape(-1, 1, 1, 1)) / 0.04
    )


def flatten_batch(raw: dict[str, Any], device: torch.device) -> tuple[dict[str, Any], int, int]:
    scenes, views = raw["source"].shape[:2]
    result: dict[str, Any] = {}
    for name, value in raw.items():
        if torch.is_tensor(value):
            value = value.to(device, non_blocking=True)
            if value.ndim == 4:
                value = value.contiguous(memory_format=torch.channels_last)
            if value.ndim >= 2 and tuple(value.shape[:2]) == (scenes, views):
                result[name] = value.reshape(scenes * views, *value.shape[2:])
            elif name in {"boundary_level", "polarity"} and value.ndim >= 1 and value.shape[0] == scenes:
                result[name] = value.repeat_interleave(views, dim=0)
            else:
                result[name] = value
        else:
            result[name] = value
    return result, scenes, views


def prefetched_batches(loader: DataLoader, dataset: Any, limit: int):
    """Prepare the next CPU batch while CUDA works on the current one."""
    iterator = iter(loader)
    dataset.set_role_cycle(1 % 4)
    current = next(iterator, None)
    if current is None:
        return
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="r98-data") as executor:
        for index in range(1, int(limit) + 1):
            if index < limit:
                dataset.set_role_cycle((index + 1) % 4)
                pending = executor.submit(next, iterator, None)
            else:
                pending = None
            yield index, current
            if pending is None:
                return
            current = pending.result()
            if current is None:
                return


def combined_epoch_batches(
    broad_loader: DataLoader,
    broad_dataset: Any,
    broad_limit: int,
    focus_loader: DataLoader,
    focus_dataset: Any,
):
    """Run the broad R97-style pass and then the locked R98 texture pass."""
    index = 0
    for _broad_index, raw in prefetched_batches(broad_loader, broad_dataset, broad_limit):
        index += 1
        yield index, raw
    for _focus_index, raw in prefetched_batches(focus_loader, focus_dataset, len(focus_loader)):
        index += 1
        yield index, raw


def calibration_crop(
    batch: dict[str, Any], scenes: int, views: int, patch: int,
    epoch: int, batch_index: int,
) -> tuple[dict[str, Any], int, int]:
    """One representative view with enough context for an exact S/B/T update."""
    selected_scene = (epoch + batch_index) % max(scenes, 1)
    selected_view = (epoch * 3 + batch_index) % max(views, 1)
    selected = selected_scene * views + selected_view
    crop_patch = min(int(patch), 512)
    crop_core = min(crop_patch - 128, 256)
    crop_core = max(128, crop_core // 8 * 8)
    maximum = patch - crop_patch
    # Move the calibration window over a small deterministic aligned grid so
    # the S/B/T supervision is not permanently restricted to the image centre.
    if maximum > 0:
        grid = maximum // 8 + 1
        y0 = ((epoch * 17 + batch_index * 7) % grid) * 8
        x0 = ((epoch * 11 + batch_index * 13) % grid) * 8
    else:
        y0 = x0 = 0
    total_views = scenes * views
    result: dict[str, Any] = {}
    for name, value in batch.items():
        if torch.is_tensor(value) and value.ndim >= 1 and value.shape[0] == total_views:
            value = value[selected:selected + 1]
            if value.ndim >= 4 and tuple(value.shape[-2:]) == (patch, patch):
                value = value[..., y0:y0 + crop_patch, x0:x0 + crop_patch]
            result[name] = value
        elif torch.is_tensor(value) and value.ndim >= 1 and value.shape[0] == scenes:
            result[name] = value[selected_scene:selected_scene + 1]
        else:
            result[name] = value
    return result, crop_patch, crop_core


BRANCH_DETAILS = {
    "nuisance": "nuisance_delta",
    "radiometry": "radiometry_delta",
    "local_contrast": "local_contrast_delta",
    "boundary": "boundary_delta",
    "texture": "texture_delta",
}


def sparse_normalized_loss(prediction: torch.Tensor, truth: torch.Tensor) -> torch.Tensor:
    beta = 1.0 / 255.0
    amplitude = truth.detach().abs()
    scale = amplitude.flatten(1).mean(dim=1).clamp_min(beta).view(-1, 1, 1, 1)
    normalized = F.smooth_l1_loss(prediction / scale, truth / scale, beta=0.25, reduction="none")
    support = amplitude / (amplitude + 0.50 * beta)
    active = (normalized * support).sum() / support.sum().clamp_min(1.0)
    quiet = (prediction.abs() * (1.0 - support)).sum() / (1.0 - support).sum().clamp_min(1.0)
    absolute = F.smooth_l1_loss(prediction, truth, beta=beta)
    return 0.55 * active + 0.30 * absolute + 0.15 * quiet


def branch_loss(
    details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int, suffix: str,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    values: dict[str, torch.Tensor] = {}
    for branch, detail_name in BRANCH_DETAILS.items():
        prediction = core_crop(details[detail_name], patch, core)
        truth = core_crop(batch[f"{branch}_applied_target_{suffix}"], patch, core)
        values[branch] = sparse_normalized_loss(prediction, truth)
    configured = DESIGN["training"]["loss_weights"]
    weighted = []
    for branch, value in values.items():
        if branch == "texture":
            weight = float(configured["texture_branch"])
        elif branch == "boundary":
            weight = float(configured["boundary_branch"])
        else:
            weight = float(configured["other_branch"])
        weighted.append(weight * value)
    return sum(weighted), values


def stage_truth(batch: dict[str, Any], suffix: str) -> dict[str, torch.Tensor]:
    source = {"s": batch["source"], "b": batch["noise_free_source"], "t": batch["target"]}[suffix]
    optical = batch["optical_source"] if suffix in {"s", "b"} else source
    return {
        "sensor_clean_base": batch["noise_free_source"] if suffix == "s" else source,
        "restoration_base": optical,
        "contrast_restored_base": optical + batch[f"local_contrast_applied_target_{suffix}"],
    }


def geometry_loss(model: nn.Module, batch: dict[str, Any], patch: int, core: int) -> torch.Tensor:
    source = batch["source"]
    direct = model.forward_geometry_features(torch.cat([source, batch["noise_free_source"], batch["target"]], dim=0))
    count = source.shape[0]
    mask = core_crop(batch["mask"], patch, core).clamp(1e-4, 1.0 - 1e-4)
    support = core_crop(batch["boundary_support_truth"], patch, core)
    total = source.new_zeros(())
    for start in (0, count, 2 * count):
        output = core_crop(direct["geometry_outputs"][start:start + count], patch, core)
        total = total + F.binary_cross_entropy_with_logits(output[:, 0:1], mask)
        total = total + F.binary_cross_entropy_with_logits(output[:, 1:2], support)
    return total / 3.0


def output_loss(details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    prediction = core_crop(details["output"], patch, core)
    truth = core_crop(batch["supervised_target_s"], patch, core)
    raw = core_crop(batch["source"], patch, core)
    pixel = F.smooth_l1_loss(prediction, truth, beta=1.0 / 255.0)
    multiscale = F.l1_loss(lowpass(prediction, 7), lowpass(truth, 7)) + F.l1_loss(lowpass(prediction, 17), lowpass(truth, 17))
    px, py = gradients(prediction)
    tx, ty = gradients(truth)
    gradient = F.l1_loss(px, tx) + F.l1_loss(py, ty)
    texture = F.l1_loss(prediction - lowpass(prediction, 7), truth - lowpass(truth, 7))
    contour = F.l1_loss(
        soft_boundary(foreground(prediction, batch["boundary_level"], batch["polarity"])),
        soft_boundary(core_crop(batch["mask"], patch, core)),
    )
    phase = PERIODIC.phase_anchor_loss(raw, prediction)
    cancellation = core_crop(
        sum(details[name].abs() for name in BRANCH_DETAILS.values()) - details["correction"].abs(),
        patch, core,
    ).clamp_min(0.0).mean()
    weights = DESIGN["training"]["loss_weights"]
    total = (
        float(weights["pixel"]) * pixel
        + float(weights["multiscale"]) * multiscale
        + float(weights["gradient"]) * gradient
        + float(weights["texture"]) * texture
        + float(weights["contour"]) * contour
        + float(weights["phase"]) * phase
        + float(weights["cancellation"]) * cancellation
    )
    return total, {
        "pixel": pixel, "multiscale": multiscale, "gradient": gradient,
        "texture": texture, "contour": contour, "phase": phase,
        "cancellation": cancellation,
    }


def direct_triplet_loss(
    model: nn.Module, batch: dict[str, Any], patch: int, core: int,
    fraction: float,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    del fraction  # The calibration pass deliberately uses exact causal bases.
    source_count = batch["source"].shape[0]
    combined_source = torch.cat(
        [batch["source"], batch["noise_free_source"], batch["target"]], dim=0,
    )
    combined_truth = {
        name: torch.cat([stage_truth(batch, suffix)[name] for suffix in ("s", "b", "t")], dim=0)
        for name in ("sensor_clean_base", "restoration_base", "contrast_restored_base")
    }
    combined_details = model(
        combined_source, return_details=True, stage_truth=combined_truth,
        stage_truth_fraction=1.0,
    )
    totals = []
    metrics: dict[str, torch.Tensor] = {}
    mask = core_crop(batch["mask"], patch, core).clamp(1e-4, 1.0 - 1e-4)
    support = core_crop(batch["boundary_support_truth"], patch, core)
    geometry_terms = []
    for index, suffix in enumerate(("s", "b", "t")):
        start = index * source_count
        details = {
            name: value[start:start + source_count]
            for name, value in combined_details.items()
        }
        geometry_terms.append(
            F.binary_cross_entropy_with_logits(
                core_crop(details["geometry_logits"], patch, core), mask,
            )
            + F.binary_cross_entropy_with_logits(
                core_crop(details["boundary_logits"], patch, core), support,
            )
        )
        branches, values = branch_loss(details, batch, patch, core, suffix)
        truth = core_crop(batch[f"supervised_target_{suffix}"], patch, core)
        output = F.smooth_l1_loss(core_crop(details["output"], patch, core), truth, beta=1.0 / 255.0)
        totals.append(branches + 0.65 * output)
        for name, value in values.items():
            metrics[f"{suffix}_{name}"] = value
        metrics[f"{suffix}_output"] = output
    metrics["geometry"] = sum(geometry_terms) / 3.0
    return sum(totals) / 3.0, metrics


def motion_centroid_loss(details: dict[str, torch.Tensor], batch: dict[str, Any], patch: int, core: int, scenes: int, views: int) -> torch.Tensor:
    if views < 2:
        return details["output"].sum() * 0.0
    eligible = (batch["pair_kind"].reshape(-1) == 1).to(details["output"].dtype)
    prediction = core_crop(details["output"], patch, core).reshape(scenes, views, 1, core, core)
    truth = core_crop(batch["target"], patch, core).reshape(scenes, views, 1, core, core)
    yy = torch.arange(core, device=prediction.device, dtype=prediction.dtype).view(1, 1, 1, core, 1)
    xx = torch.arange(core, device=prediction.device, dtype=prediction.dtype).view(1, 1, 1, 1, core)

    def center(image: torch.Tensor) -> torch.Tensor:
        gx, gy = gradients(image.reshape(-1, 1, core, core))
        weight = torch.sqrt(gx.square() + gy.square() + 1e-8).reshape(scenes, views, 1, core, core)
        mass = weight.sum(dim=(-2, -1)).clamp_min(1e-4)
        return torch.cat([(weight * xx).sum(dim=(-2, -1)) / mass, (weight * yy).sum(dim=(-2, -1)) / mass], dim=2)

    error = (center(prediction)[:, 1] - center(prediction)[:, 0]) - (center(truth)[:, 1] - center(truth)[:, 0])
    value = F.smooth_l1_loss(error, torch.zeros_like(error), beta=0.1, reduction="none").mean(dim=1)
    return (value * eligible).sum() / eligible.sum().clamp_min(1.0)


def translation_loss(model: nn.Module, source: torch.Tensor) -> torch.Tensor:
    if min(source.shape[-2:]) <= 80:
        return source.new_zeros(())
    shift = (8, -8)
    with torch.no_grad():
        reference = model(source)
    moved = torch.roll(source, shifts=shift, dims=(-2, -1))
    output = model(moved)
    expected = torch.roll(reference, shifts=shift, dims=(-2, -1))
    margin = min(32, min(source.shape[-2:]) // 4)
    return F.l1_loss(
        output[..., margin:-margin, margin:-margin],
        expected[..., margin:-margin, margin:-margin],
    )


def update_ema(model: nn.Module, ema: nn.Module, updates: int, maximum: float) -> float:
    decay = min(float(maximum), (1.0 + float(updates)) / (10.0 + float(updates)))
    with torch.no_grad():
        for target, source in zip(ema.parameters(), model.parameters()):
            target.mul_(decay).add_(source, alpha=1.0 - decay)
        for target, source in zip(ema.buffers(), model.buffers()):
            target.copy_(source)
    return decay


@torch.no_grad()
def validate(model: nn.Module, package: Path, manifest: dict[str, Any], device: torch.device, seed: int, smoke: bool, maximum: int = 0) -> dict[str, float]:
    patch, core = (256, 128) if smoke else (768, 384)
    dataset = DATA.R98SceneDataset(package, manifest, "validation", patch, core, 0, all_observations=True, master_seed=seed)
    per_role = 1 if smoke else int(DESIGN["training"]["online_validation_scenes_per_role"])
    loader = DataLoader(dataset, batch_sampler=DATA.RoleBalancedValidationSampler(dataset, per_role=per_role), num_workers=0)
    sums: dict[str, float] = {}
    count = 0
    model.eval()
    for raw in loader:
        batch, scenes, views = flatten_batch(raw, device)
        details = model(batch["source"], return_details=True)
        branches, branch_values = branch_loss(details, batch, patch, core, "s")
        output, values = output_loss(details, batch, patch, core)
        identity = core_crop(model(batch["target"]) - batch["target"], patch, core).abs().mean()
        motion = motion_centroid_loss(details, batch, patch, core, scenes, views)
        metrics = {**values, **{f"branch_{name}": value for name, value in branch_values.items()}, "identity": identity, "motion": motion}
        for name, value in metrics.items():
            sums[name] = sums.get(name, 0.0) + float(value) * scenes
        count += scenes
        if maximum and count >= maximum:
            break
    periodic = PERIODIC.make_periodic_batch(2, 192 if smoke else 256, seed + 970000, device=device)
    periodic_output = model(periodic.source)
    periodic_loss, periodic_metrics = PERIODIC.wrong_period_margin_loss(periodic_output, periodic.shift_xy, periodic.period_xy)
    result = {name: value / max(count, 1) for name, value in sums.items()}
    result.update({f"periodic_{name}": float(value) for name, value in periodic_metrics.items()})
    result["periodic_loss"] = float(periodic_loss)
    result["identity_gray"] = 255.0 * result.get("identity", 0.0)
    return result


def save_previews(model: nn.Module, device: torch.device, epoch: int) -> list[str]:
    output_dir = ROOT / "results" / "live_validation" / f"epoch_{epoch:03d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    model.eval()
    with torch.no_grad():
        for source_path in sorted((ROOT / "data" / "live_validation").glob("*.bmp")):
            image = cv2.imdecode(np.fromfile(source_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            raw = image.astype(np.float32) / 255.0
            tensor = torch.from_numpy(raw)[None, None].to(device)
            output = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)[0, 0].cpu().numpy()
            diff = np.clip(np.abs(output - raw) * 8.0, 0.0, 1.0)
            sheet = np.rint(np.concatenate([raw, output, diff], axis=1) * 255.0).astype(np.uint8)
            width = raw.shape[1]
            for label, x in (("RAW", 8), (f"R98 E{epoch}", width + 8), ("ABS DIFF x8", 2 * width + 8)):
                cv2.putText(sheet, label, (x, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 255, 2, cv2.LINE_AA)
            path = output_dir / f"{source_path.stem}.png"
            cv2.imwrite(str(path), sheet)
            paths.append(str(path))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--max-validation-batches", type=int, default=0)
    parser.add_argument("--continue-formal", action="store_true")
    args = parser.parse_args()
    if args.continue_formal and args.run_kind != "formal":
        raise RuntimeError("same-run continuation is available only for the formal run")
    if args.run_kind == "formal" and DESIGN.get("formal_training_authorized") is not True:
        raise RuntimeError("R98 formal training is not authorized before preflight approval")
    forbidden = ("--checkpoint", "--resume", "--teacher", "--pretrain")
    if any(token in sys.argv for token in forbidden):
        raise RuntimeError("R98 must start from a fresh random initialization")
    formal_lock = acquire_formal_lock() if args.run_kind == "formal" else None

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    torch.set_num_threads(max(1, args.cpu_threads))
    seed = int(DESIGN["independence"]["seed"])
    seed_all(seed)
    package = Path(PROJECT_ROOT / DESIGN["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    if not audit.get("passed") or manifest.get("content_sha256") != DESIGN["data"]["source_content_sha256"]:
        raise RuntimeError("hash-locked procedural source package failed verification")

    model = MODEL.build_model(base=int(DESIGN["architecture"]["model_width"])).to(device)
    if device.type == "cuda":
        model = model.to(memory_format=torch.channels_last)
    ema = copy.deepcopy(model).eval()
    for parameter in ema.parameters():
        parameter.requires_grad_(False)
    parameter_count = MODEL.count_parameters(model)
    if parameter_count != int(DESIGN["architecture"]["parameter_count"]):
        raise RuntimeError("R98 architecture parameter count changed")
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(DESIGN["training"]["peak_learning_rate"]),
        weight_decay=float(DESIGN["training"]["weight_decay"]),
        fused=device.type == "cuda",
    )
    initial_hash = model_hash(model)
    total_epochs = 1 if args.run_kind == "smoke" else int(DESIGN["training"]["planned_epochs"])
    active_path = ROOT / "runs" / "active_run.json"
    fields = [
        "epoch", "phase", "lr", "seconds", "train_seconds", "validation_seconds", "patch", "core",
        "scene_batch", "accumulation", "stage_truth_fraction", "optimizer_updates", "ema_decay",
        "gpu_peak_gib", "gpu_peak_free_gib", "train_total", "train_geometry", "train_branch",
        "train_output", "train_motion", "train_periodic", "train_phase_anchor", "train_periodic_margin",
        "val_texture", "val_contour", "val_identity_gray", "val_motion", "val_periodic_margin", "val_wrong_pitch_rate",
    ]
    start_epoch = 1
    optimizer_updates = 0
    ema_decay = 0.0
    same_run_continuation = bool(args.continue_formal)
    if same_run_continuation:
        registry_path = ROOT / "runs" / "formal_run_registry.json"
        if not registry_path.is_file():
            raise RuntimeError("no formal R98 run exists to continue")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        formal_runs = registry.get("formal_runs", [])
        if len(formal_runs) != 1 or formal_runs[0].get("status") == "complete":
            raise RuntimeError("formal R98 continuation requires exactly one incomplete run")
        entry = formal_runs[0]
        run_id = str(entry["run_id"])
        record_dir = ROOT / "runs" / f"training_{run_id}"
        weight_dir = Path(entry["weight_dir"])
        latest_path = weight_dir / "latest.pth.tar"
        if not record_dir.is_dir() or not latest_path.is_file():
            raise RuntimeError("same-run continuation is missing its run folder or latest checkpoint")
        checkpoint = torch.load(latest_path, map_location=device, weights_only=False)
        metadata = dict(checkpoint.get("metadata", {}))
        if checkpoint.get("experiment_id") != DESIGN["experiment_id"] or metadata.get("run_id") != run_id:
            raise RuntimeError("same-run checkpoint identity does not match the formal registry")
        expected_hashes = {
            "initial_parameter_sha256": initial_hash,
            "model_sha256": sha256_file(MODEL_PATH),
            "trainer_sha256": sha256_file(Path(__file__)),
            "targets_sha256": sha256_file(TARGETS_PATH),
            "replay_sha256": sha256_file(REPLAY_PATH),
            "design_sha256": sha256_file(DESIGN_PATH),
            "dataset_content_sha256": manifest["content_sha256"],
        }
        if any(metadata.get(name) != value for name, value in expected_hashes.items()):
            raise RuntimeError("same-run checkpoint was created by a different R98 contract")
        model.load_state_dict(checkpoint["model_state_dict"])
        ema.load_state_dict(checkpoint["ema_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        optimizer_updates = int(checkpoint.get("optimizer_updates", 0))
        ema_decay = min(
            float(DESIGN["training"]["ema_decay"]),
            (1.0 + float(optimizer_updates)) / (10.0 + float(optimizer_updates)),
        ) if optimizer_updates else 0.0
        start_epoch = int(checkpoint["epoch"]) + 1
        if start_epoch > total_epochs:
            raise RuntimeError("formal R98 run already contains its final epoch")
        registry["formal_runs"][0].update(
            status="resuming", completed_epoch=start_epoch - 1,
            trainer_pid=os.getpid(),
            resume_count=int(entry.get("resume_count", 0)) + 1,
            resumed_at=datetime.now().isoformat(),
        )
        write_json(registry_path, registry)
        write_json(active_path, {
            **metadata, "status": "resuming", "completed_epoch": start_epoch - 1,
            "planned_epochs": total_epochs, "trainer_pid": os.getpid(),
            "same_run_continuation": True,
        })
    else:
        run_id = f"R98_scratch_seed{seed}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        record_dir = ROOT / "runs" / (("smoke_" if args.run_kind == "smoke" else "training_") + run_id)
        weight_dir = ROOT / "weights" / args.run_kind / f"seed_{seed}" / run_id / "weights"
        record_dir.mkdir(parents=True, exist_ok=False)
        weight_dir.mkdir(parents=True, exist_ok=False)
        metadata = {
            "experiment_id": DESIGN["experiment_id"], "run_id": run_id,
            "run_kind": args.run_kind, "seed": seed, "device": str(device),
            "parameter_count": parameter_count, "initial_parameter_sha256": initial_hash,
            "model_sha256": sha256_file(MODEL_PATH), "trainer_sha256": sha256_file(Path(__file__)),
            "targets_sha256": sha256_file(TARGETS_PATH), "replay_sha256": sha256_file(REPLAY_PATH),
            "design_sha256": sha256_file(DESIGN_PATH), "dataset_content_sha256": manifest["content_sha256"],
            "checkpoint_loaded": False, "teacher_used": False, "real_training_pixels": False,
            "optimizer_fresh": True, "started_at": datetime.now().isoformat(),
            "record_dir": str(record_dir), "weight_dir": str(weight_dir),
        }
        if args.run_kind == "formal":
            registry_path = ROOT / "runs" / "formal_run_registry.json"
            if registry_path.is_file():
                raise RuntimeError("the one authorized R98 formal run already exists")
            write_json(registry_path, {
                "experiment_id": DESIGN["experiment_id"], "formal_run_limit": 1,
                "formal_runs": [{
                    **metadata, "status": "starting", "completed_epoch": 0,
                    "trainer_pid": os.getpid(), "resume_count": 0,
                }],
            })
        write_json(active_path, {
            **metadata, "status": "starting", "completed_epoch": 0,
            "planned_epochs": total_epochs, "trainer_pid": os.getpid(),
            "same_run_continuation": False,
        })
    log_path = record_dir / "training_log.csv"
    if same_run_continuation:
        if not log_path.is_file():
            raise RuntimeError("same-run continuation is missing its training log")
    else:
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fields).writeheader()
        if args.run_kind == "formal":
            save_checkpoint(weight_dir / "latest.pth.tar", {
                "experiment_id": DESIGN["experiment_id"], "epoch": 0,
                "model_state_dict": model.state_dict(), "ema_state_dict": ema.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(), "optimizer_updates": 0,
                "metrics": {"train": {}, "validation": {}}, "metadata": metadata,
            })
    try:
        last_completed_epoch = start_epoch - 1
        for epoch in range(start_epoch, total_epochs + 1):
            epoch_started = time.perf_counter()
            phase = phase_for_epoch(epoch)
            stage = stage_for_epoch(epoch, args.run_kind == "smoke")
            patch, core = stage["patch_size"], stage["core_size"]
            scene_batch, accumulation = stage["scene_batch"], stage["accumulation"]
            fraction = 1.0 if args.run_kind == "smoke" else stage_truth_fraction(epoch)
            lr = learning_rate(epoch)
            geometry_trainable = epoch <= int(DESIGN["training"]["geometry_train_until_epoch"])
            for parameter in model.parameter_groups()["geometry"]:
                parameter.requires_grad_(geometry_trainable)
            for group in optimizer.param_groups:
                group["lr"] = lr
            dataset = DATA.R98SceneDataset(package, manifest, "train", patch, core, epoch, master_seed=seed)
            sampler = DATA.RoleBalancedBatchSampler(dataset, scene_batch, seed + epoch * 101)
            loader = DataLoader(dataset, batch_sampler=sampler, num_workers=0, pin_memory=device.type == "cuda")
            batch_limit = len(loader)
            if args.run_kind == "formal":
                target_exposures = next(
                    int(row["target_scene_exposures_per_epoch"])
                    for row in DESIGN["training"]["patch_schedule"]
                    if int(row["epoch_start"]) <= epoch <= int(row["epoch_end"])
                )
                batch_limit = min(
                    batch_limit,
                    math.ceil(target_exposures / max(scene_batch, 1)),
                    int(DESIGN["training"]["batches_per_epoch"]),
                )
            if args.max_train_batches:
                batch_limit = min(batch_limit, args.max_train_batches)
            focus_batches = 0 if args.run_kind == "smoke" else int(DESIGN["training"]["texture_focus_batches_per_epoch"])
            if args.max_train_batches:
                focus_batches = min(focus_batches, max(0, args.max_train_batches // 2))
            focus_dataset = DATA.R98SceneDataset(
                package, manifest, "train", patch, core, epoch,
                master_seed=seed + 170003,
            )
            focus_sampler = DATA.TextureFocusBatchSampler(
                focus_dataset,
                scene_batch,
                seed + epoch * 1009,
                list(DESIGN["data"]["texture_focus_roles"]),
                focus_batches,
            )
            focus_loader = DataLoader(
                focus_dataset,
                batch_sampler=focus_sampler,
                num_workers=0,
                pin_memory=device.type == "cuda",
            )
            total_batch_count = batch_limit + focus_batches
            if device.type == "cuda":
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats(device)
                free_before = torch.cuda.mem_get_info(device)[0]
                reserved_before = torch.cuda.memory_reserved(device)
            else:
                free_before = reserved_before = 0
            model.train()
            optimizer.zero_grad(set_to_none=True)
            sums = {name: 0.0 for name in ("total", "geometry", "branch", "output", "motion", "periodic", "phase_anchor", "periodic_margin")}
            count = 0
            for batch_index, raw in combined_epoch_batches(
                loader, dataset, batch_limit, focus_loader, focus_dataset,
            ):
                batch, scenes, views = flatten_batch(raw, device)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=device.type == "cuda"):
                    calibration_every = int(DESIGN["training"]["counterfactual_calibration_every_batches"])
                    focus_batch = batch_index > batch_limit
                    calibration_batch = (batch_index - 1) % calibration_every == 0 and not focus_batch
                    geometry = batch["source"].new_zeros(())
                    branches = batch["source"].new_zeros(())
                    output = batch["source"].new_zeros(())
                    triplet = batch["source"].new_zeros(())
                    motion = batch["source"].new_zeros(())
                    translate = batch["source"].new_zeros(())
                    phase_anchor = batch["source"].new_zeros(())
                    if calibration_batch:
                        calibration, calibration_patch, calibration_core = calibration_crop(
                            batch, scenes, views, patch, epoch, batch_index,
                        )
                        # One combined S/B/T forward teaches the actual applied
                        # branch values.  Composition batches stay separate so
                        # a large patch never retains four full graphs at once.
                        triplet, triplet_metrics = direct_triplet_loss(
                            model, calibration, calibration_patch,
                            calibration_core, fraction,
                        )
                        branches = sum(
                            triplet_metrics[f"s_{name}"]
                            for name in BRANCH_DETAILS
                        )
                        geometry = triplet_metrics["geometry"] if geometry_trainable else geometry
                        total = 0.30 * geometry + 1.10 * triplet
                    else:
                        details = model(
                            batch["source"], return_details=True,
                            stage_truth=stage_truth(batch, "s"),
                            stage_truth_fraction=fraction,
                        )
                        branches, _ = branch_loss(details, batch, patch, core, "s")
                        output, output_metrics = output_loss(details, batch, patch, core)
                        phase_anchor = output_metrics["phase"]
                        motion = motion_centroid_loss(details, batch, patch, core, scenes, views)
                        if epoch >= 17 and batch_index % 16 == 0:
                            translation_core = min(core, 256)
                            translation_source = core_crop(
                                batch["source"][:1], patch, translation_core,
                            )
                            translate = translation_loss(model, translation_source)
                        total = (
                            1.00 * branches
                            + (0.85 if epoch >= 9 else 0.25) * output
                            + (float(DESIGN["training"]["loss_weights"]["motion"]) if epoch >= 17 else 0.0) * motion
                            + (float(DESIGN["training"]["loss_weights"]["translation"]) if epoch >= 17 else 0.0) * translate
                        )

                    periodic_loss = batch["source"].new_zeros(())
                    periodic_margin = batch["source"].new_zeros(())
                    periodic_every = int(DESIGN["training"]["periodic_every_batches"])
                    if (
                        epoch >= 17 and not calibration_batch
                        and (batch_index - 2) % periodic_every == 0
                    ):
                        periodic_batch = PERIODIC.make_periodic_batch(
                            int(DESIGN["training"]["periodic_scene_batch"]),
                            int(DESIGN["training"]["periodic_patch_size"]),
                            seed + epoch * 1009 + batch_index,
                            device=device,
                        )
                        periodic_output = model(periodic_batch.source)
                        periodic_loss, periodic_values = PERIODIC.wrong_period_margin_loss(
                            periodic_output, periodic_batch.shift_xy, periodic_batch.period_xy,
                        )
                        # Position discrimination is not enough: these scenes
                        # also train the same restoration objective so the new
                        # periodic role cannot become a no-op side exercise.
                        periodic_truth = periodic_batch.target
                        periodic_pixel = F.smooth_l1_loss(
                            periodic_output, periodic_truth, beta=1.0 / 255.0,
                        )
                        periodic_gradient = sum(
                            F.l1_loss(predicted, truth)
                            for predicted, truth in zip(
                                gradients(periodic_output), gradients(periodic_truth)
                            )
                        )
                        periodic_texture = F.l1_loss(
                            periodic_output - lowpass(periodic_output, 7),
                            periodic_truth - lowpass(periodic_truth, 7),
                        )
                        periodic_loss = (
                            periodic_loss + 0.75 * periodic_pixel
                            + 0.45 * periodic_gradient + 0.55 * periodic_texture
                        )
                        periodic_margin = periodic_values["match_margin"]
                    total = total + (float(DESIGN["training"]["loss_weights"]["periodic"]) if epoch >= 17 else 0.0) * periodic_loss
                if not torch.isfinite(total):
                    raise FloatingPointError("non-finite R98 loss")
                (total / accumulation).backward()
                if batch_index % accumulation == 0 or batch_index == total_batch_count:
                    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    if not torch.isfinite(norm):
                        raise FloatingPointError("non-finite R98 gradient")
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    optimizer_updates += 1
                    ema_decay = update_ema(model, ema, optimizer_updates, float(DESIGN["training"]["ema_decay"]))
                local = {
                    "total": total, "geometry": geometry, "branch": branches,
                    "output": output, "motion": motion, "periodic": periodic_loss,
                    "phase_anchor": phase_anchor, "periodic_margin": periodic_margin,
                }
                for name, value in local.items():
                    sums[name] += float(value.detach()) * scenes
                count += scenes
                if batch_index == 1 or batch_index % 8 == 0 or batch_index == total_batch_count:
                    write_json(record_dir / "batch_progress.json", {
                        **metadata, "status": "training", "epoch": epoch,
                        "last_completed_batch": batch_index, "batches_in_epoch": total_batch_count,
                        "epoch_elapsed_seconds": time.perf_counter() - epoch_started,
                        "patch_size": patch, "core_size": core, "at": datetime.now().isoformat(),
                    })
            train_seconds = time.perf_counter() - epoch_started
            validation_started = time.perf_counter()
            validate_now = epoch == 1 or epoch % int(DESIGN["training"]["validation_every_epochs"]) == 0 or epoch == total_epochs
            validation = validate(ema, package, manifest, device, seed, args.run_kind == "smoke", args.max_validation_batches) if validate_now else {}
            previews = save_previews(ema, device, epoch) if epoch % int(DESIGN["training"]["live_real_preview_every_epochs"]) == 0 or epoch == total_epochs else []
            validation_seconds = time.perf_counter() - validation_started if validate_now or previews else 0.0
            elapsed = time.perf_counter() - epoch_started
            peak = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
            incremental = max(0, torch.cuda.max_memory_reserved(device) - reserved_before) if device.type == "cuda" else 0
            peak_free = max(0.0, (free_before - incremental) / 2**30) if device.type == "cuda" else 0.0
            train = {name: value / max(count, 1) for name, value in sums.items()}
            row = {
                "epoch": epoch, "phase": phase["name"], "lr": lr, "seconds": elapsed,
                "train_seconds": train_seconds, "validation_seconds": validation_seconds,
                "patch": patch, "core": core, "scene_batch": scene_batch, "accumulation": accumulation,
                "stage_truth_fraction": fraction, "optimizer_updates": optimizer_updates, "ema_decay": ema_decay,
                "gpu_peak_gib": peak, "gpu_peak_free_gib": peak_free,
                **{f"train_{name}": train[name] for name in train},
                "val_texture": validation.get("texture", ""), "val_contour": validation.get("contour", ""),
                "val_identity_gray": validation.get("identity_gray", ""), "val_motion": validation.get("motion", ""),
                "val_periodic_margin": validation.get("periodic_match_margin", ""),
                "val_wrong_pitch_rate": validation.get("periodic_wrong_pitch_rate", ""),
            }
            with log_path.open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fields).writerow(row)
            checkpoint = {
                "experiment_id": DESIGN["experiment_id"], "epoch": epoch,
                "model_state_dict": model.state_dict(), "ema_state_dict": ema.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(), "optimizer_updates": optimizer_updates,
                "metrics": {"train": train, "validation": validation}, "metadata": metadata,
            }
            save_checkpoint(weight_dir / "latest.pth.tar", checkpoint)
            if epoch == 1 or epoch % int(DESIGN["training"]["checkpoint_every_epochs"]) == 0 or epoch == total_epochs:
                save_checkpoint(weight_dir / f"epoch_{epoch:03d}.pth.tar", checkpoint)
            last_completed_epoch = epoch
            progress = {
                **metadata, "status": "active", "planned_epochs": total_epochs, "completed_epoch": epoch,
                "latest_metrics": checkpoint["metrics"], "preview_paths": previews,
                "training_log": str(log_path), "training_log_segments": [str(log_path)],
                "trainer_pid": os.getpid(), "same_run_continuation": same_run_continuation,
            }
            write_json(active_path, progress)
            write_json(record_dir / "run_progress.json", progress)
            if args.run_kind == "formal":
                registry_path = ROOT / "runs" / "formal_run_registry.json"
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                registry["formal_runs"][0].update(
                    status="active", completed_epoch=epoch, trainer_pid=os.getpid(),
                )
                write_json(registry_path, registry)
            print(json.dumps({"epoch": epoch, "phase": phase["name"], "train": train, "validation": validation, "seconds": elapsed, "gpu_peak_gib": peak}, ensure_ascii=False), flush=True)
        status = "complete" if args.run_kind == "formal" else "smoke_complete"
        summary = {
            **metadata, "status": status, "planned_epochs": total_epochs, "completed_epoch": total_epochs,
            "final_validation": validation, "training_log": str(log_path), "training_log_segments": [str(log_path)],
            "gpu_peak_gib": peak, "gpu_peak_free_gib": peak_free,
            "finished_at": datetime.now().isoformat(), "trainer_pid": os.getpid(),
            "same_run_continuation": same_run_continuation,
        }
        write_json(active_path, summary)
        write_json(record_dir / "run_summary.json", summary)
        if args.run_kind == "formal":
            registry_path = ROOT / "runs" / "formal_run_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["formal_runs"][0].update(status=status, completed_epoch=total_epochs, finished_at=summary["finished_at"])
            write_json(registry_path, registry)
        return 0
    except BaseException as exc:
        failure = {
            **metadata, "status": "failed", "error": repr(exc),
            "completed_epoch": last_completed_epoch, "trainer_pid": os.getpid(),
            "same_run_continuation": same_run_continuation,
            "failed_at": datetime.now().isoformat(),
        }
        write_json(active_path, failure)
        write_json(record_dir / "failure.json", failure)
        if args.run_kind == "formal" and (ROOT / "runs" / "formal_run_registry.json").is_file():
            registry_path = ROOT / "runs" / "formal_run_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["formal_runs"][0].update(
                status="failed", completed_epoch=last_completed_epoch,
                trainer_pid=os.getpid(), error=repr(exc),
            )
            write_json(registry_path, registry)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
