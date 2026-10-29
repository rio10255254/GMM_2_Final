"""Scratch-only staged trainer for R116.

The probe and formal runs always create a new model.  The short probe compresses
all four independent paths into ten epochs; the formal schedule follows the
48-epoch contract in config/experiment.json.  No checkpoint loading exists in
this entry point by design.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, fields
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import sys
import time
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT))

from model.r116_model import R116Details, build_model, count_parameters
from training.dataset import R116Dataset
from training.losses import (
    combine,
    detector_components,
    detail_components,
    geometry_components,
    gradients,
    shift_action_components,
    translation_consistency,
    width_action_components,
)
from training.profile_targets import build_profile_targets
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Stage:
    name: str
    group: str
    paired: bool


PROBE_PLAN = (
    Stage("probe_boundary_map_a", "detector", False),
    Stage("probe_boundary_map_b", "detector", False),
    Stage("probe_boundary_coordinate_a", "detector", False),
    Stage("probe_boundary_coordinate_b", "detector", False),
    Stage("probe_width_a", "width", False),
    Stage("probe_shift_a", "shift", False),
    Stage("probe_pair_width", "width", True),
    Stage("probe_pair_shift", "shift", True),
    Stage("probe_detail_a", "detail", False),
    Stage("probe_detail_b", "detail", False),
    Stage("probe_calibration_width", "width", True),
    Stage("probe_calibration_detail", "detail", False),
)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")


def worker_seed(worker_id: int) -> None:
    seed = torch.initial_seed() % (2**32)
    np.random.seed(seed + worker_id)
    random.seed(seed + worker_id)


def make_loader(dataset: R116Dataset, batch_size: int, workers: int,
                shuffle: bool, seed: int) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    options: dict[str, Any] = {
        "dataset": dataset,
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": workers,
        "pin_memory": True,
        "drop_last": shuffle,
        "worker_init_fn": worker_seed,
        "generator": generator,
    }
    if workers > 0:
        options.update(persistent_workers=True, prefetch_factor=2)
    return DataLoader(**options)


def flatten_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in ("source", "target", "mask", "sdf", "edge"):
        result[name] = batch[name].reshape(-1, *batch[name].shape[2:]).to(
            device, non_blocking=True,
        )
    for name in ("identity", "flat", "midpoint", "polarity"):
        result[name] = batch[name].reshape(-1).to(device, non_blocking=True)
    result["pair_shift_px"] = batch["pair_shift_px"].to(device, non_blocking=True)
    result["scene_index"] = batch["scene_index"].reshape(-1).cpu().tolist()
    result["scenes"] = int(batch["source"].shape[0])
    return result


def take_details(details: R116Details, indices) -> R116Details:
    return R116Details(*[
        getattr(details, item.name)[indices] for item in fields(details)
    ])


def set_trainable(model: torch.nn.Module, active: str) -> list[torch.nn.Parameter]:
    groups = model.parameter_groups()
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == active)
    return groups[active]


def formal_stage(epoch: int) -> Stage:
    if 1 <= epoch <= 3:
        return Stage("boundary_map", "detector", False)
    if 4 <= epoch <= 6:
        return Stage("boundary_coordinate", "detector", False)
    if 7 <= epoch <= 20:
        group = "width" if (epoch - 7) % 2 == 0 else "shift"
        return Stage(f"independent_{group}", group, False)
    if 21 <= epoch <= 30:
        group = "width" if (epoch - 21) % 2 == 0 else "shift"
        return Stage(f"paired_{group}", group, True)
    if 31 <= epoch <= 42:
        return Stage("evidence_detail", "detail", False)
    calibration = ("detector", "width", "shift", "detail", "width", "shift")
    group = calibration[epoch - 43]
    return Stage(f"calibration_{group}", group, group in {"detector", "width", "shift"})


def stage_for_epoch(mode: str, epoch: int) -> Stage:
    if mode == "probe":
        if epoch < 1 or epoch > len(PROBE_PLAN):
            raise ValueError("probe epoch outside compressed plan")
        return PROBE_PLAN[epoch - 1]
    return formal_stage(epoch)


def learning_rate(group: str, epoch: int, epochs: int, mode: str,
                  batch_size_scenes: int) -> float:
    plan = CONFIG["training_plan"]
    key = {
        "detector": "detector_learning_rate",
        "width": "width_learning_rate",
        "shift": "shift_learning_rate",
        "detail": "detail_learning_rate",
    }[group]
    base = float(plan[key])
    reference_batch = float(plan["reference_batch_size_scenes"])
    scale = min(
        math.sqrt(float(batch_size_scenes) / reference_batch),
        float(plan["large_batch_lr_scale_cap"]),
    )
    base *= scale
    if mode == "formal" and epoch >= 43:
        base = float(plan["calibration_learning_rate"])
    minimum = min(float(plan["minimum_learning_rate"]), base)
    progress = (epoch - 1) / max(epochs - 1, 1)
    return minimum + 0.5 * (base - minimum) * (1.0 + math.cos(math.pi * progress))


def finite(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(name)


def objective_for_batch(model, stage: Stage, batch: dict[str, Any],
                        epoch: int, mode: str) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    weights = CONFIG["training_plan"]["loss_weights"]
    calibration_detector = stage.group == "detector" and mode == "formal" and epoch >= 43
    if stage.group == "detector" and not calibration_detector:
        detection = model.forward_detection(batch["source"])
        components = detector_components(
            detection, batch["sdf"], batch["edge"],
            maximum_sdf_px=float(model.config.maximum_predicted_sdf_px),
        )
        detector_weights = dict(weights["detector"])
        if "boundary_map" in stage.name:
            detector_weights["sdf"] = 0.0
        return combine(components, detector_weights), {
            f"detector_{name}": value for name, value in components.items()
        }

    details = model.forward_details(batch["source"])
    finite("output", details.output)
    geometry = geometry_components(
        details, batch["target"], batch["mask"], batch["midpoint"],
        batch["polarity"], batch["identity"],
    )
    logged: dict[str, torch.Tensor] = {
        f"geometry_{name}": value for name, value in geometry.items()
    }

    scenes = batch["scenes"]
    pair = None
    if stage.paired:
        shift = batch["pair_shift_px"]
        pair = translation_consistency(
            take_details(details, slice(0, scenes * 3, 3)),
            take_details(details, slice(1, scenes * 3, 3)),
            shift[:, 0], shift[:, 1], margin=20,
        )
        logged.update({f"pair_{name}": value for name, value in pair.items()})

    if stage.group == "detector":
        detector = detector_components(
            details, batch["sdf"], batch["edge"],
            maximum_sdf_px=float(model.config.maximum_predicted_sdf_px),
        )
        logged.update({f"detector_{name}": value for name, value in detector.items()})
        total = combine(detector, weights["detector"])
        total = total + float(weights["calibration_detector_geometry"]) * (
            geometry["contour"] + geometry["centroid"] + geometry["reconstruction"]
        )
        if pair is not None:
            total = total + float(weights["calibration_detector_pair_output"]) * pair["output"]
            total = total + float(weights["calibration_detector_pair_sdf"]) * pair["sdf"]
        return total, logged

    if stage.group in {"width", "shift"}:
        with torch.autocast(device_type="cuda", enabled=False):
            targets = build_profile_targets(
                batch["source"].float(), batch["target"].float(), batch["sdf"].float(),
                predicted_sdf_px=details.predicted_sdf_px.float(),
                normal_x=details.normal_x.float(), normal_y=details.normal_y.float(),
                identity=batch["identity"], flat=batch["flat"],
                offsets_px=tuple(model.config.profile_offsets_px),
                maximum_width_gain=float(model.config.maximum_width_gain),
                maximum_shift_px=float(model.config.maximum_normal_shift_px),
            )
        if stage.group == "width":
            action = width_action_components(
                details, targets.width_gain, targets.width_reliability,
                targets.boundary_band,
            )
            total = combine(action, weights["width_action"]) + combine(
                geometry, weights["width_geometry"],
            )
            if pair is not None:
                total = total + combine(pair, weights["pair_width"])
        else:
            action = shift_action_components(
                details, targets.normal_shift, targets.shift_reliability,
                targets.boundary_band,
            )
            total = combine(action, weights["shift_action"]) + combine(
                geometry, weights["shift_geometry"],
            )
            if pair is not None:
                total = total + combine(pair, weights["pair_shift"])
        logged.update({f"action_{name}": value for name, value in action.items()})
        logged["target_width_gain_mean"] = targets.width_gain.mean()
        logged["target_shift_abs_mean"] = targets.normal_shift.abs().mean()
        logged["target_reliability_mean"] = (
            targets.width_reliability.mean() if stage.group == "width"
            else targets.shift_reliability.mean()
        )
        return total, logged

    detail = detail_components(details, batch["target"], batch["identity"])
    logged.update({f"detail_{name}": value for name, value in detail.items()})
    return combine(detail, weights["detail"]), logged


def per_image_dice(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    numerator = 2.0 * (prediction * target).flatten(1).sum(1) + 1.0e-6
    denominator = prediction.flatten(1).sum(1) + target.flatten(1).sum(1) + 1.0e-6
    return numerator / denominator


def per_image_centroid_error(prediction: torch.Tensor,
                             target: torch.Tensor) -> torch.Tensor:
    height, width = prediction.shape[-2:]
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=prediction.device),
        torch.linspace(-1, 1, width, device=prediction.device), indexing="ij",
    )
    xx = xx.view(1, 1, height, width)
    yy = yy.view(1, 1, height, width)
    prediction_mass = prediction.flatten(2).sum(2).clamp_min(1.0e-6)
    target_mass = target.flatten(2).sum(2).clamp_min(1.0e-6)
    prediction_x = (prediction * xx).flatten(2).sum(2) / prediction_mass
    prediction_y = (prediction * yy).flatten(2).sum(2) / prediction_mass
    target_x = (target * xx).flatten(2).sum(2) / target_mass
    target_y = (target * yy).flatten(2).sum(2) / target_mass
    return 0.5 * (torch.abs(prediction_x - target_x) + torch.abs(prediction_y - target_y)).squeeze(1)


@torch.inference_mode()
def validate_one_class(model, device: torch.device, name: str,
                       limit: int, batch_size: int) -> dict[str, float]:
    if name == "identity":
        dataset = R116Dataset(
            "validation", epoch=0, limit=limit,
            challenge_override="identity", role_filter="identity",
        )
    elif name == "flat_negative":
        dataset = R116Dataset(
            "validation", epoch=0, limit=limit,
            challenge_override="mixed_hard", role_filter="flat_negative",
        )
    else:
        dataset = R116Dataset(
            "validation", epoch=0, limit=limit,
            challenge_override=name, role_filter="degraded",
        )
    totals: dict[str, float] = {}
    count = 0
    for raw_batch in make_loader(dataset, batch_size, 0, False, int(CONFIG["seed"]) + 991):
        batch = flatten_batch(raw_batch, device)
        details = model.forward_details(batch["source"])
        midpoint = batch["midpoint"][:, None, None, None]
        polarity = batch["polarity"][:, None, None, None]
        output_soft = torch.sigmoid(42.0 * polarity * (details.output - midpoint))
        raw_soft = torch.sigmoid(42.0 * polarity * (batch["source"] - midpoint))
        output_gx, output_gy = gradients(details.output)
        target_gx, target_gy = gradients(batch["target"])
        metrics = {
            "output_mae": torch.abs(details.output - batch["target"]).flatten(1).mean(1),
            "raw_mae": torch.abs(batch["source"] - batch["target"]).flatten(1).mean(1),
            "output_change": torch.abs(details.output - batch["source"]).flatten(1).mean(1),
            "output_contour_dice": per_image_dice(output_soft, batch["mask"]),
            "raw_contour_dice": per_image_dice(raw_soft, batch["mask"]),
            "output_centroid_error": per_image_centroid_error(output_soft, batch["mask"]),
            "raw_centroid_error": per_image_centroid_error(raw_soft, batch["mask"]),
            "gradient_mae": (
                torch.abs(output_gx - target_gx) + torch.abs(output_gy - target_gy)
            ).flatten(1).mean(1),
            "low_frequency_leakage": details.low_frequency_leakage.abs().flatten(1).mean(1),
            "width_gain_mean": details.width_gain.flatten(1).mean(1),
            "normal_shift_abs_mean": details.normal_shift.abs().flatten(1).mean(1),
            "detail_abs_mean": details.bounded_detail.abs().flatten(1).mean(1),
        }
        batch_count = int(details.output.shape[0])
        count += batch_count
        for key, values in metrics.items():
            totals[key] = totals.get(key, 0.0) + float(values.sum().cpu())
    result = {key: value / max(count, 1) for key, value in totals.items()}
    result["samples"] = count
    result["contour_gain"] = result["output_contour_dice"] - result["raw_contour_dice"]
    result["centroid_gain"] = result["raw_centroid_error"] - result["output_centroid_error"]
    result["mae_gain"] = result["raw_mae"] - result["output_mae"]
    return result


@torch.inference_mode()
def validate_all(model, device: torch.device, per_class: int,
                 batch_size: int) -> dict[str, Any]:
    model.eval()
    classes = {
        name: validate_one_class(model, device, name, per_class, batch_size)
        for name in CONFIG["validation_plan"]["classes"]
    }
    degraded = [classes[name] for name in CONFIG["validation_plan"]["classes"][:6]]
    return {
        "classes": classes,
        "worst_degraded_contour_dice": min(row["output_contour_dice"] for row in degraded),
        "worst_degraded_contour_gain": min(row["contour_gain"] for row in degraded),
        "worst_degraded_centroid_gain": min(row["centroid_gain"] for row in degraded),
        "mean_degraded_mae_gain": statistics.fmean(row["mae_gain"] for row in degraded),
        "identity_change": classes["identity"]["output_change"],
        "flat_change": classes["flat_negative"]["output_change"],
        "mean_normal_shift_abs": statistics.fmean(row["normal_shift_abs_mean"] for row in degraded),
        "mean_detail_abs": statistics.fmean(row["detail_abs_mean"] for row in degraded),
    }


def encode_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(path.suffix, image)
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


@torch.inference_mode()
def save_synthetic_preview(model, device: torch.device, path: Path) -> None:
    dataset = R116Dataset(
        "validation", epoch=0, limit=4,
        challenge_override="mixed_hard", role_filter="degraded",
    )
    sources = torch.stack([dataset[index]["source"][0] for index in range(len(dataset))]).to(device)
    targets = torch.stack([dataset[index]["target"][0] for index in range(len(dataset))]).to(device)
    outputs = model(sources)
    tile = 192
    canvas = np.zeros((len(dataset) * tile, 4 * tile), np.uint8)
    for row in range(len(dataset)):
        source = sources[row, 0].cpu().numpy()
        output = outputs[row, 0].cpu().numpy()
        target = targets[row, 0].cpu().numpy()
        panels = (source, output, target, np.clip(0.5 + 4.0 * (output - source), 0, 1))
        for column, panel in enumerate(panels):
            resized = cv2.resize(panel, (tile, tile), interpolation=cv2.INTER_AREA)
            canvas[row * tile:(row + 1) * tile, column * tile:(column + 1) * tile] = np.round(
                np.clip(resized, 0, 1) * 255,
            ).astype(np.uint8)
    encode_image(path, canvas)


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    return image.astype(np.float32) / 255.0


@torch.inference_mode()
def save_real_preview(model, device: torch.device, path: Path) -> None:
    inputs = [Path(PROJECT_ROOT / value) for value in CONFIG["validation_plan"]["real_preview_inputs"]]
    existing = [value for value in inputs if value.exists()]
    if not existing:
        return
    tile = 224
    canvas = np.zeros((len(existing) * tile, 3 * tile), np.uint8)
    for row, input_path in enumerate(existing):
        raw = read_gray(input_path)
        tensor = torch.from_numpy(raw)[None, None].to(device)
        output = model(tensor)[0, 0].cpu().numpy()
        panels = (raw, output, np.clip(0.5 + 5.0 * (output - raw), 0, 1))
        for column, panel in enumerate(panels):
            resized = cv2.resize(panel, (tile, tile), interpolation=cv2.INTER_AREA)
            canvas[row * tile:(row + 1) * tile, column * tile:(column + 1) * tile] = np.round(
                np.clip(resized, 0, 1) * 255,
            ).astype(np.uint8)
    encode_image(path, canvas)


def write_history(path: Path, history: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns: list[str] = []
    for row in history:
        for key in row:
            if key not in columns:
                columns.append(key)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(history)
    temporary.replace(path)


def estimate_remaining(history: list[dict[str, Any]], epoch: int,
                       epochs: int, mode: str) -> float | None:
    if not history:
        return None
    durations_by_group: dict[str, list[float]] = {}
    for row in history:
        durations_by_group.setdefault(str(row["active_group"]), []).append(
            float(row["duration_seconds"]),
        )
    overall = statistics.median(float(row["duration_seconds"]) for row in history[-6:])
    remaining = 0.0
    for future in range(epoch + 1, epochs + 1):
        group = stage_for_epoch(mode, future).group
        known = durations_by_group.get(group, [])
        remaining += statistics.median(known[-3:]) if known else overall
    return remaining


def run(args: argparse.Namespace) -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    plan = CONFIG["training_plan"]
    expected_epochs = int(plan["probe_epochs"] if args.mode == "probe" else plan["formal_epochs"])
    epochs = expected_epochs if args.epochs <= 0 else int(args.epochs)
    if args.mode == "probe" and epochs != len(PROBE_PLAN):
        raise RuntimeError(f"R116 probe must run exactly {len(PROBE_PLAN)} epochs")
    if args.mode == "formal":
        if not bool(plan["formal_training_authorized"]):
            raise RuntimeError("Formal training is not authorized in config/experiment.json")
        if epochs != int(plan["formal_epochs"]):
            raise RuntimeError("Formal training must follow the complete configured epoch count")
    manifest = ROOT / CONFIG["data"]["package_root"] / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError("Prepared dataset manifest is missing")
    if sha256(manifest) != CONFIG["data"]["source_manifest_sha256"]:
        raise RuntimeError("Dataset manifest hash mismatch")

    run_id = args.run_id or f"r116_{args.mode}_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    lock = ROOT / "runs" / "active_run.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, run_id.encode("utf-8"))
        os.close(descriptor)
    except FileExistsError as error:
        raise RuntimeError(f"Another R116 run is active: {lock.read_text(encoding='utf-8')}") from error

    seed_all(int(CONFIG["seed"]))
    device = torch.device("cuda:0")
    model = build_model().to(device)
    groups = model.parameter_groups()
    optimizers = {
        name: torch.optim.AdamW(
            parameters,
            lr=float(plan[f"{name}_learning_rate"]),
            weight_decay=float(plan["weight_decay"]),
        )
        for name, parameters in groups.items()
    }
    group_steps = {name: 0 for name in groups}
    data_limit = int(args.data_limit)
    if data_limit <= 0 and args.mode == "probe":
        data_limit = int(plan["probe_data_limit_scenes"])
    per_class = int(
        plan["probe_validation_per_class"] if args.mode == "probe"
        else CONFIG["validation_plan"]["formal_per_class"]
    )
    if args.smoke_steps > 0:
        per_class = min(per_class, 2)
    validation_every = int(CONFIG["validation_plan"]["run_every_epochs"])
    save_every = 2 if args.mode == "probe" else int(plan["save_every_epochs"])
    preview_every = 2 if args.mode == "probe" else int(plan["preview_every_epochs"])
    history: list[dict[str, Any]] = []
    global_step = 0
    current_context: dict[str, Any] = {"epoch": 0, "batch": 0, "stage": "not_started"}
    optimizer = None
    started = time.perf_counter()
    run_state = {
        "status": "running",
        "run_id": run_id,
        "mode": args.mode,
        "scratch": True,
        "checkpoint_loaded": False,
        "device": torch.cuda.get_device_name(0),
        "parameters": count_parameters(model),
        "epochs": epochs,
        "batch_size_scenes": int(args.batch_size_scenes),
        "views_per_scene": 3,
        "data_limit_scenes": data_limit,
        "dataset_manifest_sha256": sha256(manifest),
        "config_sha256": sha256(CONFIG_PATH),
    }
    atomic_json(run_dir / "run_state.json", run_state)
    print(json.dumps({"run_started": run_state}), flush=True)

    try:
        for epoch in range(1, epochs + 1):
            stage = stage_for_epoch(args.mode, epoch)
            active_parameters = set_trainable(model, stage.group)
            optimizer = optimizers[stage.group]
            target_lr = learning_rate(
                stage.group, epoch, epochs, args.mode, int(args.batch_size_scenes),
            )
            model.train()
            dataset = R116Dataset("train", epoch=epoch, limit=data_limit)
            train_loader = make_loader(
                dataset, int(args.batch_size_scenes), int(args.workers), True,
                int(CONFIG["seed"]) + epoch,
            )
            epoch_started = time.perf_counter()
            torch.cuda.reset_peak_memory_stats(device)
            totals: dict[str, float] = {}
            batches = 0
            for raw_batch in train_loader:
                global_step += 1
                group_steps[stage.group] += 1
                batches += 1
                batch = flatten_batch(raw_batch, device)
                current_context = {
                    "epoch": epoch,
                    "batch": batches,
                    "batches": len(train_loader),
                    "stage": stage.name,
                    "active_group": stage.group,
                    "global_step": global_step,
                    "scene_indices": batch["scene_index"],
                }
                warmup = min(
                    1.0,
                    group_steps[stage.group] / max(int(plan["warmup_steps_per_group"]), 1),
                )
                current_lr = target_lr * warmup
                for parameter_group in optimizer.param_groups:
                    parameter_group["lr"] = current_lr
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=not args.no_amp):
                    total, components = objective_for_batch(model, stage, batch, epoch, args.mode)
                for name, value in components.items():
                    finite(f"component.{name}", value)
                finite("loss", total)
                total.backward()
                norm = torch.nn.utils.clip_grad_norm_(active_parameters, float(plan["gradient_clip"]))
                finite("gradient", norm)
                optimizer.step()
                totals["total"] = totals.get("total", 0.0) + float(total.detach().cpu())
                for name, value in components.items():
                    finite(name, value)
                    totals[name] = totals.get(name, 0.0) + float(value.detach().cpu())
                if global_step == 1 or global_step % 50 == 0:
                    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
                    live = {
                        "status": "running",
                        "run_id": run_id,
                        "mode": args.mode,
                        "epoch": epoch,
                        "epochs": epochs,
                        "stage": stage.name,
                        "active_group": stage.group,
                        "paired": stage.paired,
                        "batch": batches,
                        "batches": len(train_loader),
                        "global_step": global_step,
                        "learning_rate": current_lr,
                        "loss": float(total.detach().cpu()),
                        "gradient_norm": float(norm.detach().cpu()),
                        "gpu_free_gib": free_bytes / 2**30,
                        "gpu_total_gib": total_bytes / 2**30,
                    }
                    atomic_json(run_dir / "live_state.json", live)
                    print(json.dumps({"step_progress": live}), flush=True)
                if args.smoke_steps > 0 and batches >= int(args.smoke_steps):
                    break

            duration = time.perf_counter() - epoch_started
            row: dict[str, Any] = {
                "epoch": epoch,
                "stage": stage.name,
                "active_group": stage.group,
                "paired": stage.paired,
                "global_step": global_step,
                "batches": batches,
                "learning_rate": current_lr,
                "target_learning_rate": target_lr,
                "duration_seconds": duration,
                "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
                "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30,
            }
            row.update({f"train_{name}": value / max(batches, 1) for name, value in totals.items()})
            validation = None
            if epoch % validation_every == 0 or epoch == epochs or args.smoke_steps > 0:
                validation = validate_all(
                    model, device, per_class,
                    max(1, min(int(args.batch_size_scenes), 4)),
                )
                atomic_json(run_dir / "validation" / f"epoch_{epoch:03d}.json", validation)
                for name in (
                    "worst_degraded_contour_dice", "worst_degraded_contour_gain",
                    "worst_degraded_centroid_gain", "mean_degraded_mae_gain",
                    "identity_change", "flat_change", "mean_normal_shift_abs",
                    "mean_detail_abs",
                ):
                    row[f"validation_{name}"] = validation[name]
            history.append(row)
            row["estimated_remaining_seconds"] = estimate_remaining(
                history, epoch, epochs, args.mode,
            )
            atomic_json(run_dir / "training_history.json", history)
            write_history(run_dir / "training_log.csv", history)
            print(json.dumps({"epoch_complete": row}), flush=True)

            if epoch % preview_every == 0 or epoch == epochs or args.smoke_steps > 0:
                model.eval()
                save_synthetic_preview(
                    model, device, run_dir / "previews" / f"epoch_{epoch:03d}_synthetic.png",
                )
                save_real_preview(
                    model, device, run_dir / "previews" / f"epoch_{epoch:03d}_real.png",
                )
            if epoch % save_every == 0 or epoch == epochs or args.smoke_steps > 0:
                checkpoint = run_dir / "weights" / f"epoch_{epoch:03d}.pth"
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                torch.save({
                    "model": model.state_dict(),
                    "epoch": epoch,
                    "stage": stage.name,
                    "active_group": stage.group,
                    "global_step": global_step,
                    "run_id": run_id,
                    "mode": args.mode,
                    "scratch": True,
                    "checkpoint_loaded": False,
                    "optimizer": optimizer.state_dict(),
                    "group_steps": group_steps,
                    "validation": validation,
                    "config": CONFIG,
                }, checkpoint)
            if args.smoke_steps > 0:
                break

        completed = {
            **run_state,
            "status": "complete",
            "epochs_completed": len(history),
            "global_step": global_step,
            "elapsed_seconds": time.perf_counter() - started,
            "last_validation": next(
                (json.loads(path.read_text(encoding="utf-8")) for path in sorted(
                    (run_dir / "validation").glob("epoch_*.json"), reverse=True,
                )), None,
            ),
        }
        atomic_json(run_dir / "run_state.json", completed)
        atomic_json(run_dir / "SUMMARY.json", completed)
        print(json.dumps({"run_complete": completed}), flush=True)
    except BaseException as error:
        failure = {
            "status": "failed",
            "run_id": run_id,
            "mode": args.mode,
            "global_step": global_step,
            "epochs_completed": len(history),
            "error_type": type(error).__name__,
            "error": repr(error),
            "context": current_context,
        }
        try:
            snapshot = run_dir / "failure_snapshot.pth"
            torch.save({
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict() if optimizer is not None else None,
                "group_steps": group_steps,
                "context": current_context,
                "scratch": True,
                "checkpoint_loaded": False,
                "error": repr(error),
                "config": CONFIG,
            }, snapshot)
            failure["failure_snapshot"] = str(snapshot)
            failure["failure_snapshot_sha256"] = sha256(snapshot)
        except BaseException as snapshot_error:
            failure["snapshot_error"] = repr(snapshot_error)
        atomic_json(run_dir / "failure.json", failure)
        atomic_json(run_dir / "run_state.json", failure)
        raise
    finally:
        if lock.exists() and lock.read_text(encoding="utf-8") == run_id:
            lock.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("probe", "formal"), default="probe")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--batch-size-scenes", type=int, default=int(CONFIG["training_plan"]["batch_size_scenes"]))
    parser.add_argument("--workers", type=int, default=int(CONFIG["training_plan"]["workers"]))
    parser.add_argument("--data-limit", type=int, default=0)
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--smoke-steps", type=int, default=0)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
