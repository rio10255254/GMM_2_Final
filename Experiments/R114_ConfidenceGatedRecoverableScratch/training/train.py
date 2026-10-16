"""Single entry point for all independent R114 scratch campaigns."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.full_model import R114Model, build_full_model, count_parameters
from model.r114_model import R114Controller, build_model as build_controller
from training.dataset import ManifestBatchSampler, R114Dataset, manifest_sha256
from training.losses import (
    controller_components,
    controller_objective,
    detail_components,
    detail_target,
    geometry_parameter_components,
    per_scene_mean,
    per_scene_weighted_mean,
    render_components,
)
from training.targets import build_spatial_targets


TRAINING_CONFIG = json.loads((ROOT / "config" / "training.json").read_text(encoding="utf-8"))
DATA_CONFIG = json.loads((ROOT / "config" / "data.json").read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_sha256(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")


def worker_seed(worker_id: int) -> None:
    seed = (torch.initial_seed() + worker_id) % (2 ** 32)
    np.random.seed(seed)
    random.seed(seed)


def move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    result = {}
    for key, value in batch.items():
        if isinstance(value, torch.Tensor):
            value = value.to(device, non_blocking=True)
            if bool(TRAINING_CONFIG.get("channels_last", False)) and value.ndim == 4 and value.is_floating_point():
                value = value.contiguous(memory_format=torch.channels_last)
        result[key] = value
    return result


def make_loader(dataset: R114Dataset, batch_size: int, workers: int, epoch: int,
                shuffle: bool, limited: bool = False) -> DataLoader:
    options: dict[str, Any] = {
        "dataset": dataset,
        "num_workers": workers,
        "pin_memory": bool(TRAINING_CONFIG["pin_memory"]),
        "worker_init_fn": worker_seed,
    }
    if limited:
        options.update(batch_size=batch_size, shuffle=shuffle, drop_last=False)
    else:
        options["batch_sampler"] = ManifestBatchSampler(dataset, batch_size, epoch, shuffle)
    if workers > 0:
        options["persistent_workers"] = False
        options["prefetch_factor"] = int(TRAINING_CONFIG["prefetch_factor"])
    return DataLoader(**options)


def finite(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(f"non-finite {name}")


def stage_for_epoch(stages: dict[str, int], epoch: int) -> tuple[str, int, int]:
    cursor = 0
    for name, length in stages.items():
        if epoch <= cursor + int(length):
            return name, epoch - cursor, int(length)
        cursor += int(length)
    raise ValueError(f"epoch {epoch} outside stage schedule")


def cosine_learning_rate(base: float, minimum: float, stage_epoch: int, stage_length: int) -> float:
    position = (stage_epoch - 1) / max(stage_length - 1, 1)
    return minimum + 0.5 * (base - minimum) * (1.0 + math.cos(math.pi * position))


def _constant_flow(value: torch.Tensor, dx: float, dy: float) -> torch.Tensor:
    batch, _channels, height, width = value.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, height, device=value.device, dtype=value.dtype),
        torch.linspace(-1, 1, width, device=value.device, dtype=value.dtype),
        indexing="ij",
    )
    grid = torch.stack([xx, yy], -1).unsqueeze(0).repeat(batch, 1, 1, 1)
    grid[..., 0] += 2.0 * dx / max(width - 1, 1)
    grid[..., 1] += 2.0 * dy / max(height - 1, 1)
    return grid


def shift_tensor(value: torch.Tensor, dx: float, dy: float) -> torch.Tensor:
    return F.grid_sample(value, _constant_flow(value, dx, dy), mode="bilinear", padding_mode="reflection", align_corners=True)


def translation_equivariance(model: R114Model, source: torch.Tensor, reference, step: int,
                             use_bf16: bool) -> torch.Tensor:
    dx = 0.65 if step % 2 == 0 else -0.85
    dy = -0.55 if step % 3 == 0 else 0.75
    subset = source[: min(2, source.shape[0])]
    shifted = shift_tensor(subset, dx, dy)
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
        candidate = model.forward_details(shifted)
    crop = 8
    losses = []
    for name, weight in (
        ("output", 0.35),
        ("normalized_sdf", 0.20),
        ("boundary_confidence", 0.20),
        ("correction_need", 0.10),
        ("width_gain", 0.10),
        ("normal_shift", 0.05),
    ):
        expected = shift_tensor(getattr(reference, name)[: len(subset)], dx, dy)
        observed = getattr(candidate, name)
        losses.append(weight * (observed[..., crop:-crop, crop:-crop] - expected[..., crop:-crop, crop:-crop]).abs().mean())
    return sum(losses)


def exposure_consistency(model: R114Model, source: torch.Tensor, reference, step: int,
                         use_bf16: bool) -> torch.Tensor:
    gain = 0.82 if step % 2 == 0 else 1.16
    bias = -0.035 if step % 3 == 0 else 0.028
    subset = source[: min(2, source.shape[0])]
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
        candidate = model.forward_details((gain * subset + bias).clamp(0, 1))
    losses = []
    for name, weight in (
        ("normalized_sdf", 0.20),
        ("boundary_confidence", 0.25),
        ("correction_need", 0.15),
        ("recoverability", 0.10),
        ("width_gain", 0.15),
        ("normal_shift", 0.15),
    ):
        losses.append(weight * (getattr(candidate, name) - getattr(reference, name)[: len(subset)]).abs().mean())
    return sum(losses)


def configure_trainable(model: torch.nn.Module, stage: str, detail_enabled: bool) -> None:
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    if isinstance(model, R114Controller):
        for parameter in model.parameters():
            parameter.requires_grad_(True)
        return
    if stage == "controller":
        for parameter in model.controller_parameters():
            parameter.requires_grad_(True)
    elif stage == "geometry":
        for parameter in [*model.controller_parameters(), *model.geometry_parameters()]:
            parameter.requires_grad_(True)
    elif stage == "detail":
        if detail_enabled:
            for parameter in model.detail_parameters():
                parameter.requires_grad_(True)
    elif stage == "joint_refinement":
        for parameter in [*model.controller_parameters(), *model.geometry_parameters()]:
            parameter.requires_grad_(True)
        if detail_enabled:
            for parameter in model.detail_parameters():
                parameter.requires_grad_(True)
    else:
        raise ValueError(stage)


def build_optimizers(model: torch.nn.Module) -> dict[str, torch.optim.Optimizer | None]:
    lr = TRAINING_CONFIG["learning_rates"]
    weight_decay = float(TRAINING_CONFIG["weight_decay"])
    if isinstance(model, R114Controller):
        return {
            "controller": torch.optim.AdamW(model.parameters(), lr=float(lr["controller"]), weight_decay=weight_decay),
        }
    return {
        "controller": torch.optim.AdamW(model.controller_parameters(), lr=float(lr["controller"]), weight_decay=weight_decay),
        "geometry": torch.optim.AdamW([
            {"params": model.controller_parameters(), "lr": float(lr["controller_during_geometry"])},
            {"params": model.geometry_parameters(), "lr": float(lr["geometry"])},
        ], weight_decay=weight_decay),
        "detail": torch.optim.AdamW(model.detail_parameters(), lr=float(lr["detail"]), weight_decay=weight_decay),
        "joint_refinement": torch.optim.AdamW(model.parameters(), lr=float(lr["joint_refinement"]), weight_decay=weight_decay),
    }


def set_optimizer_lr(optimizer: torch.optim.Optimizer, stage: str, learning_rate: float) -> None:
    if stage == "geometry" and len(optimizer.param_groups) == 2:
        ratio = float(TRAINING_CONFIG["learning_rates"]["controller_during_geometry"]) / float(TRAINING_CONFIG["learning_rates"]["geometry"])
        optimizer.param_groups[0]["lr"] = learning_rate * ratio
        optimizer.param_groups[1]["lr"] = learning_rate
    else:
        for group in optimizer.param_groups:
            group["lr"] = learning_rate


def _controller_view(details):
    return details


def compute_training_loss(model, details, batch, targets, stage: str, global_step: int,
                          detail_enabled: bool, use_bf16: bool) -> tuple[torch.Tensor | None, dict[str, torch.Tensor], str]:
    controller = controller_components(_controller_view(details), targets)
    if stage == "controller":
        objective = controller_objective(controller, global_step)
        if global_step % 3 == 2:
            count = min(2, batch["target"].shape[0])
            clear_details = (
                model(batch["target"][:count])
                if isinstance(model, R114Controller)
                else model.controller(batch["target"][:count])
            )
            clear_need = per_scene_weighted_mean(
                clear_details.correction_need.square(),
                targets.boundary[:count] + 0.01,
            )
            controller["counterfactual_clear_need"] = clear_need
            objective = objective + 0.55 * clear_need
        return objective, controller, f"controller_{global_step % 3}"

    geometry = geometry_parameter_components(details, targets)
    render = render_components(details, batch, targets)
    metrics = {**controller, **geometry, **render}
    if stage == "geometry":
        cycle = global_step % 5
        controller_maintenance = 0.12 * controller_objective(controller, global_step)
        if cycle == 0:
            objective = geometry["width"] + geometry["shift"] + 0.08 * geometry["tangent_coherence"]
            name = "spatial_width_shift"
        elif cycle == 1:
            objective = render["contour_dice"] + 0.25 * render["contour_bce"] + 0.85 * render["reconstruction"]
            name = "render_contour"
        elif cycle == 2:
            objective = render["gradient"] + 0.35 * render["reconstruction"]
            name = "render_gradient"
        elif cycle == 3:
            objective = translation_equivariance(model, batch["source"], details, global_step, use_bf16)
            metrics["translation_equivariance"] = objective
            name = "translation_equivariance"
        else:
            exposure = exposure_consistency(model, batch["source"], details, global_step, use_bf16)
            objective = exposure + 1.2 * render["identity"]
            metrics["exposure_consistency"] = exposure
            name = "exposure_identity"
        return objective + controller_maintenance, metrics, name

    if stage == "detail":
        if not detail_enabled:
            return None, metrics, "matched_geometry_only_control"
        target_detail = detail_target(model, details, batch["target"], targets, batch["identity"])
        detail = detail_components(model, details, target_detail, targets)
        metrics.update(detail)
        objective = detail["detail"] + 0.12 * detail["detail_zero_mean"] + 0.55 * detail["detail_geometry_guard"]
        return objective, metrics, "recoverable_detail"

    if stage == "joint_refinement":
        objective = 0.30 * controller_objective(controller, global_step)
        objective = objective + geometry["width"] + geometry["shift"]
        objective = objective + 0.60 * render["contour_dice"] + 0.45 * render["reconstruction"] + 0.60 * render["identity"]
        if detail_enabled:
            target_detail = detail_target(model, details, batch["target"], targets, batch["identity"])
            detail = detail_components(model, details, target_detail, targets)
            metrics.update(detail)
            objective = objective + 0.45 * detail["detail"] + 0.25 * detail["detail_geometry_guard"]
        return objective, metrics, "short_joint_refinement"
    raise ValueError(stage)


def safe_auc(truth: np.ndarray, prediction: np.ndarray) -> float | None:
    if np.unique(truth).size < 2:
        return None
    return float(roc_auc_score(truth, prediction))


@torch.no_grad()
def validate(model, device: torch.device, batch_size: int, workers: int, limit: int,
             controller_only: bool) -> tuple[dict[str, Any], list[dict[str, np.ndarray]]]:
    dataset = R114Dataset("validation", epoch=0, limit=limit)
    loader = make_loader(dataset, batch_size, workers, 0, False, limited=limit > 0)
    rows: list[dict[str, Any]] = []
    previews: list[dict[str, np.ndarray]] = []
    model.eval()
    for batch_data in loader:
        batch = move_batch(batch_data, device)
        targets = build_spatial_targets(batch["source"], batch["target"], batch["mask"], batch["sdf"], batch["identity"], batch["flat"])
        details = model(batch["source"]) if controller_only else model.forward_details(batch["source"])
        for index in range(batch["source"].shape[0]):
            truth = targets.boundary_binary[index, 0].detach().cpu().numpy().astype(np.uint8)
            pred = details.boundary_confidence[index, 0].detach().cpu().numpy()
            stride = max(1, truth.size // 12000)
            auc = safe_auc(truth.reshape(-1)[::stride], pred.reshape(-1)[::stride])
            row = {
                "record_id": batch["record_id"][index],
                "family": batch["family"][index],
                "role": batch["role"][index],
                "challenge": batch["challenge"][index],
                "boundary_auc": auc,
                "boundary_mean": float(pred.mean()),
                "boundary_std": float(pred.std()),
                "boundary_on_minus_off": float(pred[truth > 0].mean() - pred[truth == 0].mean()) if np.any(truth > 0) and np.any(truth == 0) else 0.0,
                "need_mean": float(details.correction_need[index].mean().cpu()),
                "recoverability_mean": float(details.recoverability[index].mean().cpu()),
            }
            if not controller_only:
                output = details.output[index, 0]
                row.update({
                    "output_l1": float((output - batch["target"][index, 0]).abs().mean().cpu()),
                    "output_change": float(details.delta[index].abs().mean().cpu()),
                    "identity_change": float(details.delta[index].abs().mean().cpu()) if bool(batch["identity"][index]) else None,
                    "width_mean": float(details.width_gain[index].mean().cpu()),
                    "shift_abs_mean": float(details.normal_shift[index].abs().mean().cpu()),
                    "detail_abs_mean_gray": float(details.detail[index].abs().mean().cpu()) * 255.0,
                })
            rows.append(row)
            if len(previews) < 9:
                preview = {
                    "source": batch["source"][index, 0].cpu().numpy(),
                    "target": batch["target"][index, 0].cpu().numpy(),
                    "boundary": pred,
                    "need": details.correction_need[index, 0].cpu().numpy(),
                    "recoverability": details.recoverability[index, 0].cpu().numpy(),
                }
                if not controller_only:
                    preview["output"] = details.output[index, 0].cpu().numpy()
                    preview["width"] = (details.width_gain[index, 0].cpu().numpy() - 1.0) / 2.5
                    preview["shift"] = (details.normal_shift[index, 0].cpu().numpy() + 1.5) / 3.0
                previews.append(preview)

    valid_auc = [row["boundary_auc"] for row in rows if row["boundary_auc"] is not None]
    family: dict[str, dict[str, float]] = {}
    for name in sorted({row["family"] for row in rows}):
        subset = [row for row in rows if row["family"] == name]
        aucs = [row["boundary_auc"] for row in subset if row["boundary_auc"] is not None]
        family[name] = {
            "count": len(subset),
            "boundary_auc_median": float(np.median(aucs)) if aucs else None,
            "boundary_std_median": float(np.median([row["boundary_std"] for row in subset])),
            "boundary_on_minus_off_median": float(np.median([row["boundary_on_minus_off"] for row in subset])),
        }
    roles = {}
    for role in sorted({row["role"] for row in rows}):
        subset = [row for row in rows if row["role"] == role]
        roles[role] = {
            "count": len(subset),
            "need_mean": float(np.mean([row["need_mean"] for row in subset])),
            "boundary_mean": float(np.mean([row["boundary_mean"] for row in subset])),
        }
    summary: dict[str, Any] = {
        "records": len(rows),
        "boundary_auc_median": float(np.median(valid_auc)) if valid_auc else 0.0,
        "boundary_auc_worst_family": min(
            (value["boundary_auc_median"] for value in family.values() if value["boundary_auc_median"] is not None),
            default=0.0,
        ),
        "boundary_std_median": float(np.median([row["boundary_std"] for row in rows])),
        "boundary_on_minus_off_median": float(np.median([row["boundary_on_minus_off"] for row in rows])),
        "families": family,
        "roles": roles,
    }
    if not controller_only:
        summary.update({
            "output_l1_mean": float(np.mean([row["output_l1"] for row in rows])),
            "output_change_mean": float(np.mean([row["output_change"] for row in rows])),
            "identity_change_mean": float(np.mean([row["identity_change"] for row in rows if row["identity_change"] is not None])),
            "detail_abs_mean_gray": float(np.mean([row["detail_abs_mean_gray"] for row in rows])),
        })
    return {"summary": summary, "rows": rows}, previews


def save_preview(path: Path, previews: list[dict[str, np.ndarray]]) -> None:
    if not previews:
        return
    keys = ["source", "output", "target", "boundary", "need", "recoverability", "width", "shift"]
    keys = [key for key in keys if any(key in row for row in previews)]
    tile = 160
    canvas = np.zeros((len(previews) * tile, len(keys) * tile), np.uint8)
    for row_index, row in enumerate(previews):
        for column, key in enumerate(keys):
            image = row.get(key, np.zeros_like(row["source"]))
            image = cv2.resize(np.clip(image, 0, 1), (tile, tile), interpolation=cv2.INTER_AREA)
            canvas[row_index * tile:(row_index + 1) * tile, column * tile:(column + 1) * tile] = np.round(image * 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), canvas):
        raise RuntimeError(f"failed to write preview {path}")


def write_history_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key, value in row.items() if not isinstance(value, (dict, list))})
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rows)
    os.replace(temporary, path)


def train(args: argparse.Namespace) -> int:
    campaign = TRAINING_CONFIG["campaigns"][args.campaign]
    controller_only = args.campaign == "controller_probe"
    epochs = int(args.epochs or campaign["epochs"])
    stages = dict(campaign["stages"])
    if args.epochs and epochs != sum(int(value) for value in stages.values()):
        if controller_only:
            stages = {"controller": epochs}
        else:
            raise ValueError("--epochs override is only supported for controller_probe")
    detail_enabled = bool(campaign.get("detail_enabled", args.campaign == "formal"))
    formal = bool(campaign.get("formal", False))
    batch_size = int(args.batch_size or TRAINING_CONFIG["default_batch_size"])
    workers = int(args.workers if args.workers is not None else TRAINING_CONFIG["workers"])
    seed = int(DATA_CONFIG["seed"])
    seed_all(seed)
    if not torch.cuda.is_available():
        raise RuntimeError("R114 training requires CUDA")
    device = torch.device("cuda:0")
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    if free_bytes / 2 ** 30 < float(TRAINING_CONFIG["minimum_gpu_free_gib"]):
        raise RuntimeError(f"only {free_bytes / 2**30:.2f} GiB GPU memory is free")

    run_id = args.run_id or f"r114_{args.campaign}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    if run_dir.exists():
        raise FileExistsError(run_dir)
    run_dir.mkdir(parents=True)
    model = (build_controller() if controller_only else build_full_model(detail_enabled=detail_enabled)).to(device)
    if bool(TRAINING_CONFIG.get("channels_last", False)):
        model = model.to(memory_format=torch.channels_last)
    initial_hash = state_sha256(model)
    optimizers = build_optimizers(model)
    history: list[dict[str, Any]] = []
    global_step = 0
    started = time.perf_counter()
    config_hashes = {name: sha256(ROOT / "config" / name) for name in ("data.json", "model.json", "training.json", "validation.json")}
    state = {
        "status": "running",
        "run_id": run_id,
        "campaign": args.campaign,
        "formal": formal,
        "scratch": True,
        "foreign_checkpoint_loaded": False,
        "initial_state_sha256": initial_hash,
        "device": torch.cuda.get_device_name(device),
        "parameters": count_parameters(model),
        "epochs": epochs,
        "batch_size": batch_size,
        "workers": workers,
        "detail_enabled": detail_enabled,
        "dataset_manifest_sha256": manifest_sha256(),
        "config_sha256": config_hashes,
        "started_at": now(),
    }
    atomic_json(run_dir / "run_state.json", state)
    print(json.dumps(state, ensure_ascii=False), flush=True)

    try:
        for epoch in range(1, epochs + 1):
            stage, stage_epoch, stage_length = stage_for_epoch(stages, epoch)
            configure_trainable(model, stage, detail_enabled)
            optimizer = optimizers.get(stage)
            base_name = "controller_during_geometry" if stage == "geometry" else stage
            base_lr = float(TRAINING_CONFIG["learning_rates"].get(base_name, TRAINING_CONFIG["learning_rates"].get(stage, TRAINING_CONFIG["learning_rates"]["minimum"])))
            if stage == "geometry":
                base_lr = float(TRAINING_CONFIG["learning_rates"]["geometry"])
            learning_rate = cosine_learning_rate(base_lr, float(TRAINING_CONFIG["learning_rates"]["minimum"]), stage_epoch, stage_length)
            if optimizer is not None:
                set_optimizer_lr(optimizer, stage, learning_rate)

            dataset = R114Dataset("train", epoch=epoch, limit=int(args.data_limit))
            limited = bool(args.data_limit)
            loader = make_loader(dataset, batch_size, workers, epoch, True, limited=limited)
            model.train()
            torch.cuda.reset_peak_memory_stats(device)
            epoch_started = time.perf_counter()
            totals: dict[str, float] = {}
            objective_counts: dict[str, int] = {}
            batches = 0
            for batch_data in loader:
                global_step += 1
                batches += 1
                batch = move_batch(batch_data, device)
                targets = build_spatial_targets(batch["source"], batch["target"], batch["mask"], batch["sdf"], batch["identity"], batch["flat"])
                if optimizer is not None:
                    optimizer.zero_grad(set_to_none=True)
                use_bf16 = (
                    not controller_only
                    and stage in {"geometry", "detail", "joint_refinement"}
                    and TRAINING_CONFIG.get("precision") == "stagewise_fp32_controller_bf16_renderer"
                )
                if controller_only:
                    details = model(batch["source"])
                elif stage == "controller":
                    details = model.controller(batch["source"])
                else:
                    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_bf16):
                        details = model.forward_details(batch["source"])
                objective, metrics, objective_name = compute_training_loss(
                    model, details, batch, targets, stage, global_step, detail_enabled, use_bf16
                )
                objective_counts[objective_name] = objective_counts.get(objective_name, 0) + 1
                if objective is not None:
                    finite("objective", objective)
                    objective.backward()
                    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
                    gradient_norm = torch.nn.utils.clip_grad_norm_(trainable, float(TRAINING_CONFIG["gradient_clip"]))
                    finite("gradient_norm", gradient_norm)
                    assert optimizer is not None
                    optimizer.step()
                    totals["objective"] = totals.get("objective", 0.0) + float(objective.detach().cpu())
                    totals["gradient_norm"] = totals.get("gradient_norm", 0.0) + float(gradient_norm.detach().cpu())
                for name, value in metrics.items():
                    finite(name, value)
                    totals[name] = totals.get(name, 0.0) + float(value.detach().cpu())
                if batches % 25 == 0:
                    progress = {
                        "status": "running",
                        "run_id": run_id,
                        "campaign": args.campaign,
                        "epoch": epoch,
                        "total_epochs": epochs,
                        "stage": stage,
                        "batch": batches,
                        "batches_in_epoch": len(loader),
                        "global_step": global_step,
                        "latest_objective": objective_name,
                        "elapsed_seconds": time.perf_counter() - started,
                        "updated_at": now(),
                    }
                    atomic_json(run_dir / "progress.json", progress)
                    print(json.dumps({"progress": progress}, ensure_ascii=False), flush=True)
                if args.smoke_steps and batches >= int(args.smoke_steps):
                    break

            requested_validation_limit = int(args.validation_limit)
            full_validation_epoch = (
                requested_validation_limit == 0
                and (epoch % int(TRAINING_CONFIG["validation_every_epochs"]) == 0 or epoch == epochs)
            )
            effective_validation_limit = 0 if full_validation_epoch else (requested_validation_limit or 128)
            validation, previews = validate(
                model, device, batch_size, min(workers, 2), effective_validation_limit, controller_only
            )
            duration = time.perf_counter() - epoch_started
            row: dict[str, Any] = {
                "epoch": epoch,
                "stage": stage,
                "stage_epoch": stage_epoch,
                "global_step": global_step,
                "learning_rate": learning_rate,
                "duration_seconds": duration,
                "batches": batches,
                "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2 ** 30,
                "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2 ** 30,
                "gpu_free_end_gib": torch.cuda.mem_get_info(device)[0] / 2 ** 30,
                **{f"train_{name}": value / max(batches, 1) for name, value in totals.items()},
                **{f"objective_count_{name}": count for name, count in objective_counts.items()},
                **{f"validation_{key}": value for key, value in validation["summary"].items() if not isinstance(value, dict)},
            }
            history.append(row)
            atomic_json(run_dir / "training_history.json", history)
            write_history_csv(run_dir / "training_log.csv", history)
            atomic_json(run_dir / "validation" / f"epoch_{epoch:03d}.json", validation)
            if epoch % int(TRAINING_CONFIG["preview_every_epochs"]) == 0 or args.smoke_steps or epoch == epochs:
                save_preview(run_dir / "previews" / f"epoch_{epoch:03d}.png", previews)
            checkpoint = ""
            if epoch % int(TRAINING_CONFIG["checkpoint_every_epochs"]) == 0 or epoch == epochs or args.smoke_steps:
                checkpoint_path = run_dir / "weights" / f"epoch_{epoch:03d}.pth"
                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save({
                    "model": model.state_dict(),
                    "epoch": epoch,
                    "stage": stage,
                    "campaign": args.campaign,
                    "run_id": run_id,
                    "scratch": True,
                    "foreign_checkpoint_loaded": False,
                    "initial_state_sha256": initial_hash,
                    "detail_enabled": detail_enabled,
                    "config_sha256": config_hashes,
                    "validation": validation["summary"],
                }, checkpoint_path)
                checkpoint = str(checkpoint_path)
            progress = {
                "status": "running",
                "run_id": run_id,
                "campaign": args.campaign,
                "epoch": epoch,
                "total_epochs": epochs,
                "stage": stage,
                "global_step": global_step,
                "latest_checkpoint": checkpoint,
                "elapsed_seconds": time.perf_counter() - started,
                "updated_at": now(),
            }
            atomic_json(run_dir / "progress.json", progress)
            print(json.dumps(row, ensure_ascii=False), flush=True)

        state.update({
            "status": "complete",
            "epochs_completed": epochs,
            "global_step": global_step,
            "elapsed_seconds": time.perf_counter() - started,
            "completed_at": now(),
            "final_state_sha256": state_sha256(model),
        })
        atomic_json(run_dir / "run_state.json", state)
        atomic_json(ROOT / "runs" / "latest_completed.json", state)
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
            "failed_at": now(),
        }
        atomic_json(run_dir / "failure.json", failure)
        state.update(failure)
        atomic_json(run_dir / "run_state.json", state)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", choices=tuple(TRAINING_CONFIG["campaigns"]), required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--batch-size", type=int, choices=(12, 16), default=0)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--smoke-steps", type=int, default=0)
    parser.add_argument("--data-limit", type=int, default=0)
    parser.add_argument("--validation-limit", type=int, default=128)
    parser.add_argument("--resume", default="")
    args = parser.parse_args()
    if args.resume:
        raise RuntimeError("R114 is scratch-only; checkpoint resume and weight inheritance are disabled")
    return train(args)


if __name__ == "__main__":
    raise SystemExit(main())
