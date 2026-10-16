"""Scratch-only staged trainer for R117."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
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
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT))
from inference.tiled import forward_tiled
from model.r117_model import build_model, count_parameters
from training.dataset import R117Dataset
from training.losses import detector_loss, detail_loss, paired_loss, shift_loss, soft_object, width_loss


@dataclass(frozen=True)
class Stage:
    name: str
    group: str
    paired: bool = False


def stage_for_epoch(epoch: int) -> Stage:
    if epoch <= 6:
        return Stage("subpixel_geometry", "detector")
    if epoch <= 20:
        group = "width" if (epoch - 7) % 2 == 0 else "shift"
        return Stage("independent_geometry_action", group)
    if epoch <= 30:
        group = "width" if (epoch - 21) % 2 == 0 else "shift"
        return Stage("paired_coordinate_consistency", group, True)
    return Stage("geometry_protected_detail", "detail")


def stage_for_run(mode: str, epoch: int) -> Stage:
    if mode == "formal":
        return stage_for_epoch(epoch)
    smoke = (
        Stage("smoke_subpixel_geometry", "detector"),
        Stage("smoke_width", "width"),
        Stage("smoke_shift", "shift"),
        Stage("smoke_paired_width", "width", True),
        Stage("smoke_detail", "detail"),
    )
    return smoke[epoch - 1]


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
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.set_float32_matmul_precision("high")


def worker_seed(worker_id: int) -> None:
    seed = torch.initial_seed() % (2**32)
    random.seed(seed + worker_id); np.random.seed(seed + worker_id)


def loader(dataset, batch_size: int, workers: int, shuffle: bool, seed: int) -> DataLoader:
    options = dict(
        dataset=dataset, batch_size=batch_size, shuffle=shuffle, num_workers=workers,
        pin_memory=True, drop_last=shuffle, worker_init_fn=worker_seed,
        generator=torch.Generator().manual_seed(seed),
    )
    if workers > 0:
        options.update(persistent_workers=True, prefetch_factor=3)
    return DataLoader(**options)


def flatten(raw: dict[str, Any], device: torch.device) -> dict[str, Any]:
    result = {}
    for name in ("source", "target", "mask", "sdf", "edge", "mask_2x", "sdf_2x", "known_width_gain", "known_width_reliability"):
        tensor = raw[name].reshape(-1, *raw[name].shape[2:]).to(device, non_blocking=True)
        result[name] = tensor.contiguous(memory_format=torch.channels_last)
    for name in ("identity", "flat", "midpoint", "polarity"):
        result[name] = raw[name].reshape(-1).to(device, non_blocking=True)
    result["pair_shift_px"] = raw["pair_shift_px"].to(device, non_blocking=True)
    result["scene_index"] = raw["scene_index"].tolist()
    result["scenes"] = int(raw["source"].shape[0])
    return result


def learning_rate(group: str, epoch: int) -> float:
    cfg = CONFIG["training"]
    base = float(cfg["learning_rates"][group])
    minimum = min(base, float(cfg["minimum_learning_rate"]))
    ranges = {"detector": (1, 6), "width": (7, 30), "shift": (7, 30), "detail": (31, 42)}
    first, last = ranges[group]
    progress = (epoch - first) / max(last - first, 1)
    return minimum + 0.5 * (base - minimum) * (1 + math.cos(math.pi * progress))


def set_trainable(model, group: str) -> list[torch.nn.Parameter]:
    groups = model.parameter_groups()
    for name, parameters in groups.items():
        for parameter in parameters:
            parameter.requires_grad_(name == group)
    return groups[group]


def finite(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(name)


def per_image_dice(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    numerator = 2 * (prediction * target).flatten(1).sum(1) + 1.0e-6
    denominator = prediction.flatten(1).sum(1) + target.flatten(1).sum(1) + 1.0e-6
    return numerator / denominator


@torch.inference_mode()
def validate_class(model, device, name: str, limit: int) -> dict[str, float]:
    role = "identity" if name == "identity" else "flat_negative" if name == "flat_negative" else "degraded"
    challenge = "identity" if name == "identity" else "mixed_hard" if name == "flat_negative" else name
    dataset = R117Dataset("validation", epoch=0, limit=limit, challenge_override=challenge, role_filter=role)
    totals, count = {}, 0
    for raw in loader(dataset, min(4, limit), 0, False, int(CONFIG["seed"]) + 991):
        batch = flatten(raw, device)
        # One observation per scene is sufficient for the validation readout;
        # paired consistency is measured explicitly during paired stages.
        select = slice(0, batch["scenes"] * 3, 3)
        source, target, mask = batch["source"][select], batch["target"][select], batch["mask"][select]
        details = model.forward_details(source)
        midpoint, polarity = batch["midpoint"][select], batch["polarity"][select]
        out_soft = soft_object(details.output, midpoint, polarity)
        raw_soft = soft_object(source, midpoint, polarity)
        ogx = details.output[..., 1:] - details.output[..., :-1]
        rgx = source[..., 1:] - source[..., :-1]
        values = {
            "output_mae": torch.abs(details.output - target).flatten(1).mean(1),
            "raw_mae": torch.abs(source - target).flatten(1).mean(1),
            "output_change": torch.abs(details.output - source).flatten(1).mean(1),
            "output_contour_dice": per_image_dice(out_soft, mask),
            "raw_contour_dice": per_image_dice(raw_soft, mask),
            "gradient_gain": ogx.abs().flatten(1).mean(1) - rgx.abs().flatten(1).mean(1),
            "detail_abs": details.bounded_detail.abs().flatten(1).mean(1),
            "low_frequency_leakage": details.low_frequency_leakage.abs().flatten(1).mean(1),
        }
        count += int(source.shape[0])
        for key, tensor in values.items():
            totals[key] = totals.get(key, 0.0) + float(tensor.sum().cpu())
    result = {key: value / max(count, 1) for key, value in totals.items()}
    result["samples"] = count
    result["contour_gain"] = result["output_contour_dice"] - result["raw_contour_dice"]
    result["mae_gain"] = result["raw_mae"] - result["output_mae"]
    return result


@torch.inference_mode()
def validate_all(model, device, limit: int) -> dict:
    model.eval()
    classes = {name: validate_class(model, device, name, limit) for name in CONFIG["validation"]["classes"]}
    degraded = [classes[name] for name in CONFIG["validation"]["classes"][:6]]
    return {
        "classes": classes,
        "worst_contour_gain": min(item["contour_gain"] for item in degraded),
        "mean_contour_gain": statistics.fmean(item["contour_gain"] for item in degraded),
        "mean_mae_gain": statistics.fmean(item["mae_gain"] for item in degraded),
        "mean_gradient_gain": statistics.fmean(item["gradient_gain"] for item in degraded),
        "identity_change": classes["identity"]["output_change"],
        "flat_change": classes["flat_negative"]["output_change"],
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    temporary.replace(path)


def encode(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(str(path))


@torch.inference_mode()
def save_previews(model, device, run_dir: Path, epoch: int) -> None:
    dataset = R117Dataset("validation", epoch=0, limit=4, challenge_override="mixed_hard", role_filter="degraded")
    rows = []
    for index in range(min(4, len(dataset))):
        item = dataset[index]
        source, target = item["source"][0:1].to(device), item["target"][0:1].to(device)
        output = model(source)
        panels = [source[0, 0].cpu().numpy(), output[0, 0].cpu().numpy(), target[0, 0].cpu().numpy(), np.clip(0.5 + 5 * (output[0, 0].cpu().numpy() - source[0, 0].cpu().numpy()), 0, 1)]
        rows.append(np.concatenate([cv2.resize(panel, (192, 192), interpolation=cv2.INTER_AREA) for panel in panels], 1))
    encode(run_dir / "previews" / f"epoch_{epoch:03d}_synthetic.png", np.rint(np.clip(np.concatenate(rows, 0), 0, 1) * 255).astype(np.uint8))
    real_rows = []
    for value in CONFIG["validation"]["real_preview_inputs"]:
        path = Path(value)
        if not path.is_file():
            continue
        raw = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        tensor = torch.from_numpy(raw)[None, None].to(device)
        output = forward_tiled(model, tensor, core_size=512, halo=224)[0, 0].cpu().numpy()
        panels = [raw, output, np.clip(0.5 + 5 * (output - raw), 0, 1)]
        real_rows.append(np.concatenate([cv2.resize(panel, (224, 224), interpolation=cv2.INTER_AREA) for panel in panels], 1))
    if real_rows:
        encode(run_dir / "previews" / f"epoch_{epoch:03d}_real.png", np.rint(np.clip(np.concatenate(real_rows, 0), 0, 1) * 255).astype(np.uint8))


def estimate_remaining(history: list[dict], epoch: int, epochs: int, mode: str) -> float | None:
    if not history:
        return None
    by_stage = {}
    for row in history:
        by_stage.setdefault(row["stage"], []).append(float(row["duration_seconds"]))
    fallback = statistics.median(float(row["duration_seconds"]) for row in history[-6:])
    return sum(statistics.median(by_stage.get(stage_for_run(mode, future).name, [fallback])[-3:]) for future in range(epoch + 1, epochs + 1))


def run(args) -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    cfg = CONFIG["training"]
    formal = args.mode == "formal"
    epochs = int(cfg["formal_epochs"]) if formal else 5
    if formal and args.epochs not in (0, epochs):
        raise RuntimeError("formal R117 must run the complete configured schedule")
    package_manifest = ROOT / CONFIG["data"]["package_root"] / "manifest.json"
    manifest = json.loads(package_manifest.read_text(encoding="utf-8"))
    if formal and (manifest["status"] != "complete" or manifest["counts"] != {"train": 5000, "validation": 512}):
        raise RuntimeError("formal data package is incomplete")
    run_id = args.run_id or f"r117_{args.mode}_{time.strftime('%Y%m%d_%H%M%S')}"
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    lock = ROOT / "runs" / "active_run.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(descriptor, run_id.encode()); os.close(descriptor)
    except FileExistsError as error:
        raise RuntimeError(f"another R117 run is active: {lock.read_text()}") from error
    seed_all(int(CONFIG["seed"]))
    device = torch.device("cuda:0")
    model = build_model().to(device, memory_format=torch.channels_last)
    groups = model.parameter_groups()
    optimizers = {}
    for name, parameters in groups.items():
        try:
            optimizers[name] = torch.optim.AdamW(parameters, lr=float(cfg["learning_rates"][name]), weight_decay=float(cfg["weight_decay"]), fused=True)
        except TypeError:
            optimizers[name] = torch.optim.AdamW(parameters, lr=float(cfg["learning_rates"][name]), weight_decay=float(cfg["weight_decay"]))
    group_steps = {name: 0 for name in groups}
    history, global_step = [], 0
    state = {
        "status": "running", "run_id": run_id, "mode": args.mode, "scratch": True,
        "checkpoint_loaded": False, "epochs": epochs, "parameters": count_parameters(model),
        "batch_size_scenes": int(args.batch_size_scenes), "device": torch.cuda.get_device_name(0),
        "config_sha256": sha256(CONFIG_PATH), "dataset_manifest_sha256": sha256(package_manifest),
    }
    atomic_json(run_dir / "run_state.json", state)
    atomic_json(ROOT / "runs" / "active_run.json", {"run_id": run_id, "run_dir": str(run_dir), "status": "running"})
    started = time.perf_counter()
    current = {}
    try:
        for epoch in range(1, epochs + 1):
            stage = stage_for_run(args.mode, epoch)
            parameters = set_trainable(model, stage.group)
            optimizer = optimizers[stage.group]
            target_lr = learning_rate(stage.group, epoch)
            dataset = R117Dataset("train", epoch=epoch, limit=int(args.data_limit))
            train_loader = loader(dataset, int(args.batch_size_scenes), int(args.workers), True, int(CONFIG["seed"]) + epoch)
            model.train(); torch.cuda.reset_peak_memory_stats(device)
            epoch_started = time.perf_counter(); totals = {}; batches = 0
            for raw in train_loader:
                batches += 1; global_step += 1; group_steps[stage.group] += 1
                batch = flatten(raw, device)
                warmup = min(1.0, group_steps[stage.group] / max(int(cfg["warmup_steps_per_group"]), 1))
                current_lr = target_lr * warmup
                for item in optimizer.param_groups:
                    item["lr"] = current_lr
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=not args.no_amp):
                    if stage.group == "detector":
                        details = model.forward_detection(batch["source"])
                        total, components = detector_loss(details, batch["sdf_2x"], cfg["loss_weights"])
                    else:
                        details = model.forward_details(batch["source"])
                        if stage.group == "width":
                            total, components = width_loss(details, batch, cfg["loss_weights"])
                        elif stage.group == "shift":
                            total, components = shift_loss(details, batch, cfg["loss_weights"])
                        else:
                            total, components = detail_loss(details, batch, cfg["loss_weights"])
                        if stage.paired:
                            pair_total, pair_components = paired_loss(details, batch, batch["scenes"], cfg["loss_weights"])
                            total = total + pair_total; components.update(pair_components)
                finite("loss", total); total.backward()
                norm = torch.nn.utils.clip_grad_norm_(parameters, float(cfg["gradient_clip"])); finite("gradient", norm)
                optimizer.step()
                totals["loss"] = totals.get("loss", 0.0) + float(total.detach().cpu())
                for key, value in components.items():
                    finite(key, value); totals[key] = totals.get(key, 0.0) + float(value.detach().cpu())
                current = {"epoch": epoch, "batch": batches, "batches": len(train_loader), "stage": stage.name, "group": stage.group}
                if global_step == 1 or global_step % 20 == 0:
                    free, total_memory = torch.cuda.mem_get_info(device)
                    live = {"status": "running", "run_id": run_id, "epochs": epochs, **current, "loss": float(total.detach().cpu()), "gradient_norm": float(norm.detach().cpu()), "learning_rate": current_lr, "gpu_free_gib": free / 2**30, "gpu_total_gib": total_memory / 2**30}
                    atomic_json(run_dir / "live_state.json", live); print(json.dumps({"progress": live}), flush=True)
                if args.smoke_steps > 0 and batches >= int(args.smoke_steps):
                    break
            row = {"epoch": epoch, "stage": stage.name, "active_group": stage.group, "paired": stage.paired, "global_step": global_step, "batches": batches, "learning_rate": current_lr, "duration_seconds": time.perf_counter() - epoch_started, "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30, "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30}
            row.update({f"train_{key}": value / max(batches, 1) for key, value in totals.items()})
            should_validate = args.smoke_steps > 0 or epoch % int(cfg["validation_every_epochs"]) == 0 or epoch == epochs
            validation = validate_all(model, device, min(2, int(cfg["validation_per_class"]))) if args.smoke_steps > 0 else validate_all(model, device, int(cfg["validation_per_class"])) if should_validate else None
            if validation is not None:
                atomic_json(run_dir / "validation" / f"epoch_{epoch:03d}.json", validation)
                for key in ("worst_contour_gain", "mean_contour_gain", "mean_mae_gain", "mean_gradient_gain", "identity_change", "flat_change"):
                    row[f"validation_{key}"] = validation[key]
            history.append(row); row["estimated_remaining_seconds"] = estimate_remaining(history, epoch, epochs, args.mode)
            atomic_json(run_dir / "training_history.json", history); write_csv(run_dir / "training_log.csv", history)
            print(json.dumps({"epoch_complete": row}), flush=True)
            if epoch % int(cfg["preview_every_epochs"]) == 0 or epoch == epochs:
                model.eval(); save_previews(model, device, run_dir, epoch)
            if args.smoke_steps > 0 or epoch % int(cfg["save_every_epochs"]) == 0 or epoch == epochs:
                path = run_dir / "weights" / f"epoch_{epoch:03d}.pth"; path.parent.mkdir(parents=True, exist_ok=True)
                torch.save({"model": model.state_dict(), "epoch": epoch, "scratch": True, "checkpoint_loaded": False, "run_id": run_id, "config": CONFIG, "validation": validation}, path)
        completed = {**state, "status": "complete", "epochs_completed": len(history), "global_step": global_step, "elapsed_seconds": time.perf_counter() - started, "last_validation": validation}
        atomic_json(run_dir / "run_state.json", completed); atomic_json(run_dir / "SUMMARY.json", completed)
        atomic_json(ROOT / "runs" / "active_run.json", {"run_id": run_id, "run_dir": str(run_dir), "status": "complete"})
        print(json.dumps({"run_complete": completed}), flush=True)
    except BaseException as error:
        failure = {**state, "status": "failed", "epochs_completed": len(history), "global_step": global_step, "error_type": type(error).__name__, "error": repr(error), "context": current}
        atomic_json(run_dir / "failure.json", failure); atomic_json(run_dir / "run_state.json", failure)
        atomic_json(ROOT / "runs" / "active_run.json", {"run_id": run_id, "run_dir": str(run_dir), "status": "failed", "error": repr(error)})
        raise
    finally:
        if lock.is_file() and lock.read_text(encoding="utf-8") == run_id:
            lock.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--batch-size-scenes", type=int, default=int(CONFIG["training"]["batch_size_scenes"]))
    parser.add_argument("--workers", type=int, default=int(CONFIG["training"]["workers"]))
    parser.add_argument("--data-limit", type=int, default=0)
    parser.add_argument("--smoke-steps", type=int, default=0)
    parser.add_argument("--no-amp", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
