"""Single formal scratch trainer for R104. No prior-model input is accepted."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training"):
    sys.path.insert(0, str(folder))

from r104_model import build_model, count_parameters  # noqa: E402
from r104_dataset import R104Dataset  # noqa: E402
from losses import central_crop, highpass, loss_components  # noqa: E402

CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
RUNS, WEIGHTS, LOGS, REPORTS = ROOT / "runs", ROOT / "weights", ROOT / "logs", ROOT / "reports"
for directory in (RUNS, WEIGHTS, LOGS, REPORTS, ROOT / "previews"):
    directory.mkdir(parents=True, exist_ok=True)


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def worker_seed(worker_id: int) -> None:
    seed = torch.initial_seed() % (2**32 - 1)
    np.random.seed(seed + worker_id)
    random.seed(seed + worker_id)


def acquire_lock():
    import msvcrt

    path = RUNS / "formal_trainer.lock"
    handle = path.open("a+")
    handle.seek(0)
    if path.stat().st_size == 0:
        handle.write(" ")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        raise RuntimeError("Another R104 formal trainer owns the lock") from exc
    return handle


def verify_sources() -> dict[str, Any]:
    if not bool(CONFIG["training"].get("formal_training_authorized")):
        raise RuntimeError("Formal training is not authorized in experiment.json")
    reference = json.loads((ROOT / "data" / "TRAINING_DATA_REFERENCE.json").read_text(encoding="utf-8"))
    package = Path(CONFIG["data"]["base_package"])
    audit_path = package / "audit.json"
    manifest_path = package / "manifest.json"
    if not audit_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("The verified procedural package is incomplete")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    expected = str(CONFIG["data"]["base_content_sha256"])
    if reference.get("content_sha256") != expected or audit.get("content_sha256") != expected:
        raise RuntimeError("Procedural training data identity changed")
    if not audit.get("passed") or not audit.get("source_isolation_pass"):
        raise RuntimeError("Procedural source isolation audit failed")
    if bool(CONFIG["source_isolation"].get("real_pixels_in_training")):
        raise RuntimeError("Real pixels are forbidden in R104 training")
    for report_name in ("design_preflight.json", "micro_overfit.json", "batch_autotune.json"):
        report = json.loads((REPORTS / report_name).read_text(encoding="utf-8"))
        if report.get("status") not in {"passed", "completed"} and not report.get("passed"):
            raise RuntimeError(f"Required preflight did not pass: {report_name}")
    return {"audit": audit, "reference": reference}


def batch_map() -> dict[str, int]:
    report = json.loads((REPORTS / "batch_autotune.json").read_text(encoding="utf-8"))
    return {str(k): int(v) for k, v in report["selected_scene_batches"].items()}


def stage_for_epoch(epoch: int) -> dict[str, Any]:
    batches = batch_map()
    for row in CONFIG["training"]["stages"]:
        if int(row["start"]) <= epoch <= int(row["end"]):
            return {
                "patch_size": int(row["patch_size"]),
                "core_size": int(row["core_size"]),
                "batch_size": int(batches[str(row["patch_size"])]),
                "focus": str(row["focus"]),
            }
    raise RuntimeError(f"No training stage for epoch {epoch}")


def learning_rate(epoch: int, total_epochs: int) -> float:
    peak = float(CONFIG["training"]["learning_rate"])
    floor = float(CONFIG["training"]["minimum_learning_rate"])
    if epoch <= 3:
        return peak * (0.35 + 0.65 * epoch / 3.0)
    progress = (epoch - 3) / max(total_epochs - 3, 1)
    return floor + 0.5 * (peak - floor) * (1.0 + math.cos(math.pi * progress))


def make_loader(dataset: R104Dataset, batch_size: int, workers: int, seed: int, shuffle: bool) -> DataLoader:
    generator = torch.Generator().manual_seed(seed)
    options: dict[str, Any] = {
        "dataset": dataset,
        "batch_size": int(batch_size),
        "shuffle": bool(shuffle),
        "num_workers": int(workers),
        "pin_memory": True,
        "drop_last": bool(shuffle),
        "worker_init_fn": worker_seed,
        "generator": generator,
    }
    if workers > 0:
        options.update({"prefetch_factor": 3, "persistent_workers": True})
    return DataLoader(**options)


def flatten_batch(batch: dict[str, Any], device: torch.device) -> dict[str, torch.Tensor]:
    source = batch["source"].to(device, non_blocking=True)
    b, v, c, h, w = source.shape
    return {
        "source": source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last),
        "target": batch["target"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "mask": batch["mask"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "sdf": batch["sdf"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "illumination_target": batch["illumination_target"].to(device, non_blocking=True).reshape(b * v, c, h, w),
        "identity": batch["identity"].to(device, non_blocking=True).reshape(-1),
        "mode": batch["mode"].to(device, non_blocking=True).repeat_interleave(v),
        "pair_type": batch["pair_type"].to(device, non_blocking=True).repeat_interleave(v),
        "motion": batch["motion"].to(device, non_blocking=True).reshape(-1, 2),
    }


def combine_objectives(components: dict[str, torch.Tensor]) -> torch.Tensor:
    total = next(iter(components.values())).new_zeros(())
    for key, value in components.items():
        total = total + float(CONFIG["training"]["loss_weights"].get(key, 0.0)) * value
    return total


@torch.no_grad()
def update_ema(model: nn.Module, ema: nn.Module, decay: float) -> None:
    live_parameters = dict(model.named_parameters())
    for name, parameter in ema.named_parameters():
        parameter.lerp_(live_parameters[name].detach(), 1.0 - decay)
    live_buffers = dict(model.named_buffers())
    for name, buffer in ema.named_buffers():
        buffer.copy_(live_buffers[name])


def register_formal(run_id: str, metadata: dict[str, Any]) -> None:
    path = RUNS / "formal_run_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "experiment_id": CONFIG["experiment_id"], "formal_run_limit": 1, "formal_runs": []
    }
    if registry.get("formal_runs"):
        raise RuntimeError("The one authorized R104 formal run is already registered")
    registry["formal_runs"].append({"run_id": run_id, "registered_at": datetime.now().isoformat(), "status": "starting", **metadata})
    atomic_json(path, registry)


def update_registry(run_id: str, status: str, **fields: Any) -> None:
    path = RUNS / "formal_run_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    row = next(item for item in registry["formal_runs"] if item["run_id"] == run_id)
    row.update({"status": status, "updated_at": datetime.now().isoformat(), **fields})
    atomic_json(path, registry)


def build_r104() -> nn.Module:
    bounds = CONFIG["model"]["branch_bounds"]
    return build_model(
        base=int(CONFIG["model"]["base_channels"]),
        low_bound=float(bounds["radiometry"]),
        illumination_bound=float(bounds["illumination"]),
        contour_bound=float(bounds["contour_proposal"]),
        texture_bound=float(bounds["texture_proposal"]),
        combined_bound=float(bounds["combined"]),
        gate_initial_probability=float(CONFIG["model"]["gate_initial_probability"]),
    )


@torch.no_grad()
def evaluate(model: nn.Module, device: torch.device, amp_enabled: bool) -> dict[str, Any]:
    dataset = R104Dataset("validation", 256, 0, validation_limit=24)
    loader = make_loader(dataset, 4, 2, int(CONFIG["training"]["seed"]) + 800001, False)
    model.eval()
    totals: dict[str, float] = {}
    samples = 0
    for batch in loader:
        data = flatten_batch(batch, device)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            details = model.forward_details(data["source"])
            components = loss_components(details, **data, core_size=192)
        prediction = central_crop(details.output.float(), 192)
        source = central_crop(data["source"].float(), 192)
        target = central_crop(data["target"].float(), 192)
        sdf = central_crop(data["sdf"].float(), 192)
        mask = central_crop(data["mask"].float(), 192)
        predicted_sdf = central_crop(details.signed_distance.float(), 192)
        count = prediction.shape[0]
        samples += count
        error = (prediction - target).abs()
        raw_error = (source - target).abs()
        boundary_weight = torch.exp(-sdf.abs() / 4.0)
        intersection = ((predicted_sdf > 0) & (mask > 0.5)).float().sum()
        union = ((predicted_sdf > 0) | (mask > 0.5)).float().sum().clamp_min(1.0)
        gates = torch.stack([
            central_crop(details.low_gate.float(), 192),
            central_crop(details.illumination_gate.float(), 192),
            central_crop(details.contour_gate.float(), 192),
            central_crop(details.texture_gate.float(), 192),
        ]).mean(0)
        identity = data["identity"]
        active = ~identity
        values = {
            "mae": error.mean(),
            "raw_mae": raw_error.mean(),
            "psnr_db": -10.0 * torch.log10((prediction - target).square().mean().clamp_min(1e-12)),
            "boundary_mae": (error * boundary_weight).sum() / boundary_weight.sum().clamp_min(1.0),
            "texture_mae": (highpass(prediction, 3) - highpass(target, 3)).abs().mean(),
            "shape_iou": intersection / union,
            "identity_change": (prediction[identity] - source[identity]).abs().mean() if bool(identity.any()) else error.new_zeros(()),
            "illumination_mae": (central_crop(details.illumination_delta.float(), 192) - central_crop(data["illumination_target"].float(), 192)).abs().mean(),
            "active_gate_mean": gates[active].mean() if bool(active.any()) else gates.new_zeros(()),
            "identity_gate_mean": gates[identity].mean() if bool(identity.any()) else gates.new_zeros(()),
        }
        values.update({f"objective_{key}": value.float() for key, value in components.items()})
        for key, value in values.items():
            totals[key] = totals.get(key, 0.0) + float(value) * count
    metrics = {key: value / max(samples, 1) for key, value in totals.items()}
    metrics["gate_separation"] = metrics["active_gate_mean"] - metrics["identity_gate_mean"]
    axes = {
        "reconstruction": metrics["mae"],
        "boundary_position": metrics["boundary_mae"],
        "texture": metrics["texture_mae"],
        "clean_identity": metrics["identity_change"],
        "exposure_consistency": metrics["objective_exposure_shape_consistency"],
        "illumination_invariance": metrics["illumination_mae"],
        "motion": metrics["objective_translation"],
        "tile_consistency": metrics["objective_tile"],
    }
    return {"sample_views": samples, "metrics": metrics, "axes": axes}


def _write_image(path: Path, image: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"Could not encode preview: {path}")
    encoded.tofile(path)
    return str(path)


def _gray8(value: np.ndarray) -> np.ndarray:
    return np.clip(value * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _labeled(image: np.ndarray, label: str) -> np.ndarray:
    panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image.copy()
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 30), (20, 20, 20), -1)
    cv2.putText(panel, label, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (245, 245, 245), 1, cv2.LINE_AA)
    return panel


@torch.no_grad()
def save_synthetic_preview(model: nn.Module, device: torch.device, epoch: int, run_dir: Path, amp_enabled: bool) -> str:
    dataset = R104Dataset("validation", 256, 0, validation_limit=4)
    rows = []
    model.eval()
    for index in range(4):
        item = dataset[index]
        source = item["source"][:1].to(device).contiguous(memory_format=torch.channels_last)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            details = model.forward_details(source)
        raw = source[0, 0].float().cpu().numpy()
        output = details.output[0, 0].float().cpu().numpy()
        target = item["target"][0, 0].numpy()
        delta = np.abs(output - raw)
        delta_view = np.clip(delta / max(float(np.quantile(delta, 0.995)), 1.0 / 255.0), 0, 1)
        row = np.concatenate([
            _labeled(_gray8(raw), "Raw"), _labeled(_gray8(output), "R104"),
            _labeled(_gray8(target), "Truth"), _labeled(_gray8(delta_view), "Change x auto"),
        ], axis=1)
        rows.append(row)
    grid = np.concatenate(rows, axis=0)
    return _write_image(run_dir / "previews" / "synthetic" / f"epoch_{epoch:03d}.png", grid)


def _read_gray(path: Path) -> np.ndarray:
    encoded = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Could not read real preview: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = 65535.0 if image.dtype == np.uint16 else 255.0
    return image.astype(np.float32) / scale


@torch.no_grad()
def save_real_previews(model: nn.Module, device: torch.device, epoch: int, run_dir: Path, amp_enabled: bool) -> list[str]:
    manifest = json.loads((ROOT / "data" / "fixed_real_preview.json").read_text(encoding="utf-8"))
    outputs = []
    model.eval()
    for row in manifest["images"]:
        path = Path(row["path"])
        image = _read_gray(path)
        size = min(768, image.shape[0] // 8 * 8, image.shape[1] // 8 * 8)
        size = max(256, size // 8 * 8)
        y = max((image.shape[0] - size) // 2, 0)
        x = max((image.shape[1] - size) // 2, 0)
        crop = image[y:y + size, x:x + size]
        tensor = torch.from_numpy(crop).view(1, 1, size, size).to(device).contiguous(memory_format=torch.channels_last)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp_enabled):
            prediction = model(tensor)
        output = prediction[0, 0].float().cpu().numpy()
        delta = np.abs(output - crop)
        delta_view = np.clip(delta / max(float(np.quantile(delta, 0.995)), 1.0 / 255.0), 0, 1)
        panel = np.concatenate([
            _labeled(_gray8(crop), f"{row['label']} Raw"),
            _labeled(_gray8(output), f"{row['label']} R104"),
            _labeled(_gray8(delta_view), "Change x auto"),
        ], axis=1)
        target = run_dir / "previews" / "real" / f"epoch_{epoch:03d}_{row['label']}.png"
        outputs.append(_write_image(target, panel))
    return outputs


def save_checkpoint(path: Path, model: nn.Module, ema: nn.Module, epoch: int, metadata: dict[str, Any], validation: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save({
        "experiment_id": CONFIG["experiment_id"], "epoch": int(epoch),
        "model_state_dict": model.state_dict(), "ema_state_dict": ema.state_dict(),
        "metadata": metadata, "validation": validation,
        "checkpoint_loaded": False, "resume_source": None, "teacher_used": False,
    }, temporary)
    os.replace(temporary, path)


def run(args: argparse.Namespace) -> int:
    forbidden = ("checkpoint", "resume", "pretrain", "teacher", "pseudo")
    if any(token in " ".join(sys.argv).lower() for token in forbidden):
        raise RuntimeError("R104 accepts no prior-model input")
    lock = acquire_lock() if args.run_kind == "formal" else None
    run_id, run_dir, completed_epoch = "", None, 0
    try:
        source_proof = verify_sources()
        seed = int(args.seed)
        set_seed(seed)
        torch.set_num_threads(int(args.cpu_threads))
        torch.set_float32_matmul_precision("high")
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        device = torch.device(args.device)
        if device.type != "cuda" or not torch.cuda.is_available():
            raise RuntimeError("The formal R104 trainer requires CUDA")

        model = build_r104()
        initial_hash = state_sha256(model)
        parameter_count = count_parameters(model)
        model = model.to(device).to(memory_format=torch.channels_last)
        ema = copy.deepcopy(model).eval()
        for parameter in ema.parameters():
            parameter.requires_grad_(False)
        optimizer_kwargs = {
            "lr": float(CONFIG["training"]["learning_rate"]), "weight_decay": float(CONFIG["training"]["weight_decay"]),
            "betas": (0.9, 0.99),
        }
        try:
            optimizer = torch.optim.AdamW(model.parameters(), fused=True, **optimizer_kwargs)
            fused_optimizer = True
        except TypeError:
            optimizer = torch.optim.AdamW(model.parameters(), **optimizer_kwargs)
            fused_optimizer = False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{'training' if args.run_kind == 'formal' else 'smoke'}_R104_scratch_seed{seed}_{timestamp}"
        run_dir = RUNS / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        weight_dir = WEIGHTS / args.run_kind / f"seed_{seed}" / run_id
        weight_dir.mkdir(parents=True, exist_ok=False)
        total_epochs = int(args.epochs or CONFIG["training"]["epochs"])
        if args.run_kind == "smoke":
            total_epochs = min(total_epochs, 1)
        metadata = {
            "experiment_id": CONFIG["experiment_id"], "run_id": run_id, "run_kind": args.run_kind,
            "seed": seed, "started_at": datetime.now().isoformat(), "trainer_pid": os.getpid(),
            "device": str(device), "gpu": torch.cuda.get_device_name(device), "parameter_count": parameter_count,
            "initial_parameter_sha256": initial_hash, "config_sha256": sha256_file(CONFIG_PATH),
            "dataset_content_sha256": CONFIG["data"]["base_content_sha256"], "source_proof": source_proof,
            "checkpoint_loaded": False, "resume_source": None, "teacher_used": False,
            "real_training_pixels": False, "optimizer_fresh": True, "fused_optimizer": fused_optimizer,
            "batch_autotune": batch_map(),
        }
        if args.run_kind == "formal":
            register_formal(run_id, metadata)
        active_path = RUNS / ("active_run.json" if args.run_kind == "formal" else "active_smoke_run.json")
        atomic_json(active_path, {**metadata, "status": "active", "planned_epochs": total_epochs, "completed_epoch": 0})
        atomic_json(run_dir / "run_provenance.json", metadata)
        (run_dir / "scratch_proof.txt").write_text(
            "Random initialization only. No checkpoint, resume, teacher, pseudo-label, SEM pixel, or optical pixel was loaded for training.\n",
            encoding="utf-8",
        )

        loss_names = list(CONFIG["training"]["loss_weights"])
        fieldnames = [
            "epoch", "seconds", "learning_rate", "patch_size", "core_size", "batch_size", "steps", "train_total",
            *[f"train_{name}" for name in loss_names], "grad_norm", "gpu_peak_allocated_gib", "gpu_free_end_gib",
            "validation_psnr_db", "validation_mae", "validation_raw_mae", "validation_boundary_mae",
            "validation_texture_mae", "validation_shape_iou", "validation_identity_change",
            "validation_active_gate", "validation_identity_gate", "validation_gate_separation",
            "validation_motion", "validation_tile",
        ]
        log_path = run_dir / "training_log.csv"
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fieldnames).writeheader()

        latest_validation: dict[str, Any] = {}
        global_step = 0
        training_started = time.perf_counter()
        epoch_durations: list[float] = []
        for epoch in range(1, total_epochs + 1):
            epoch_started = time.perf_counter()
            torch.cuda.reset_peak_memory_stats(device)
            stage = stage_for_epoch(epoch)
            if args.run_kind == "smoke":
                stage = {"patch_size": 192, "core_size": 128, "batch_size": 4, "focus": "runtime smoke"}
            dataset = R104Dataset("train", stage["patch_size"], epoch)
            loader = make_loader(dataset, stage["batch_size"], int(args.num_workers), seed + epoch * 1009, True)
            epoch_steps = min(len(loader), int(args.max_train_batches)) if args.max_train_batches else len(loader)
            lr = learning_rate(epoch, total_epochs)
            for group in optimizer.param_groups:
                group["lr"] = lr
            model.train()
            totals: dict[str, float] = {}
            sample_count, last_grad_norm, local_step = 0, 0.0, 0
            for local_step, batch in enumerate(loader, start=1):
                if args.max_train_batches and local_step > int(args.max_train_batches):
                    local_step -= 1
                    break
                global_step += 1
                data = flatten_batch(batch, device)
                optimizer.zero_grad(set_to_none=True)
                amp_enabled = not args.no_amp
                with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp_enabled):
                    details = model.forward_details(data["source"])
                    components = loss_components(details, **data, core_size=stage["core_size"])
                    loss = combine_objectives(components)
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError(f"Non-finite loss at epoch {epoch}, step {local_step}")
                loss.backward()
                last_grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0))
                if not math.isfinite(last_grad_norm):
                    raise FloatingPointError(f"Non-finite gradient at epoch {epoch}, step {local_step}")
                optimizer.step()
                update_ema(model, ema, float(CONFIG["training"]["ema_decay"]))
                count = data["source"].shape[0]
                sample_count += count
                totals["total"] = totals.get("total", 0.0) + float(loss.detach()) * count
                for key, value in components.items():
                    totals[key] = totals.get(key, 0.0) + float(value.detach()) * count
                if local_step == 1 or local_step % 10 == 0:
                    elapsed_epoch = time.perf_counter() - epoch_started
                    seconds_per_step = elapsed_epoch / local_step
                    completed_times = epoch_durations[-8:]
                    epoch_estimate = float(np.median(completed_times)) if completed_times else seconds_per_step * epoch_steps
                    remaining = max(epoch_steps - local_step, 0) * seconds_per_step + max(total_epochs - epoch, 0) * epoch_estimate
                    atomic_json(active_path, {
                        **metadata, "status": "active", "planned_epochs": total_epochs, "completed_epoch": epoch - 1,
                        "current_epoch": epoch, "current_step": local_step, "epoch_steps": epoch_steps,
                        "seconds_per_step": seconds_per_step, "epoch_remaining_seconds": max(epoch_steps - local_step, 0) * seconds_per_step,
                        "overall_remaining_seconds": remaining, "overall_elapsed_seconds": time.perf_counter() - training_started,
                        "updated_at": datetime.now().isoformat(),
                    })

            train_metrics = {key: value / max(sample_count, 1) for key, value in totals.items()}
            validate_now = epoch == 1 or epoch % 2 == 0 or epoch == total_epochs
            synthetic_preview, real_previews = None, []
            if validate_now:
                latest_validation = evaluate(ema, device, amp_enabled=not args.no_amp)
                synthetic_preview = save_synthetic_preview(ema, device, epoch, run_dir, amp_enabled=not args.no_amp)
                real_previews = save_real_previews(ema, device, epoch, run_dir, amp_enabled=not args.no_amp)
            torch.cuda.synchronize(device)
            epoch_seconds = time.perf_counter() - epoch_started
            epoch_durations.append(epoch_seconds)
            peak = torch.cuda.max_memory_allocated(device) / 1024**3
            free = torch.cuda.mem_get_info(device)[0] / 1024**3
            metrics = latest_validation.get("metrics", {})
            row = {
                "epoch": epoch, "seconds": epoch_seconds, "learning_rate": lr,
                "patch_size": stage["patch_size"], "core_size": stage["core_size"], "batch_size": stage["batch_size"],
                "steps": local_step, "train_total": train_metrics.get("total", 0.0),
                **{f"train_{name}": train_metrics.get(name, 0.0) for name in loss_names},
                "grad_norm": last_grad_norm, "gpu_peak_allocated_gib": peak, "gpu_free_end_gib": free,
                "validation_psnr_db": metrics.get("psnr_db", ""), "validation_mae": metrics.get("mae", ""),
                "validation_raw_mae": metrics.get("raw_mae", ""), "validation_boundary_mae": metrics.get("boundary_mae", ""),
                "validation_texture_mae": metrics.get("texture_mae", ""), "validation_shape_iou": metrics.get("shape_iou", ""),
                "validation_identity_change": metrics.get("identity_change", ""),
                "validation_active_gate": metrics.get("active_gate_mean", ""), "validation_identity_gate": metrics.get("identity_gate_mean", ""),
                "validation_gate_separation": metrics.get("gate_separation", ""),
                "validation_motion": metrics.get("objective_translation", ""), "validation_tile": metrics.get("objective_tile", ""),
            }
            with log_path.open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fieldnames).writerow(row)

            checkpoint_path = weight_dir / f"epoch_{epoch:03d}.pth.tar"
            save_checkpoint(checkpoint_path, model, ema, epoch, metadata, latest_validation)
            atomic_json(weight_dir / "latest.json", {"epoch": epoch, "checkpoint": str(checkpoint_path), "sha256": sha256_file(checkpoint_path)})
            completed_epoch = epoch
            remaining_epochs = max(total_epochs - epoch, 0)
            robust_epoch_seconds = float(np.median(epoch_durations[-8:]))
            epoch_record = {
                **metadata, "status": "active" if epoch < total_epochs else "completed", "planned_epochs": total_epochs,
                "completed_epoch": epoch, "latest_epoch_seconds": epoch_seconds,
                "estimated_remaining_seconds": remaining_epochs * robust_epoch_seconds,
                "eta_method": "median_of_last_up_to_8_completed_epochs",
                "latest_train_metrics": train_metrics, "latest_validation": latest_validation,
                "latest_checkpoint": str(checkpoint_path), "synthetic_preview": synthetic_preview, "real_previews": real_previews,
                "gpu_peak_allocated_gib": peak, "gpu_free_end_gib": free, "updated_at": datetime.now().isoformat(),
            }
            atomic_json(run_dir / "run_progress.json", epoch_record)
            atomic_json(active_path, epoch_record)
            if args.run_kind == "formal":
                update_registry(run_id, "active" if epoch < total_epochs else "completed", completed_epoch=epoch, latest_checkpoint=str(checkpoint_path))
            print(json.dumps({"epoch": epoch, "seconds": round(epoch_seconds, 2), "train_total": train_metrics.get("total"), "gate_separation": metrics.get("gate_separation"), "gpu_free_gib": round(free, 2)}, ensure_ascii=False), flush=True)

        summary = {
            **metadata, "status": "completed", "planned_epochs": total_epochs, "completed_epoch": completed_epoch,
            "finished_at": datetime.now().isoformat(), "elapsed_seconds": time.perf_counter() - training_started,
            "final_validation": latest_validation, "weights_dir": str(weight_dir), "training_log": str(log_path),
        }
        atomic_json(run_dir / "run_summary.json", summary)
        atomic_json(active_path, summary)
        if args.run_kind == "formal":
            update_registry(run_id, "completed", completed_epoch=completed_epoch, summary=str(run_dir / "run_summary.json"))
        return 0
    except BaseException as exc:
        failure = {
            "experiment_id": CONFIG["experiment_id"], "run_id": run_id or None, "status": "failed",
            "completed_epoch": completed_epoch, "failed_at": datetime.now().isoformat(),
            "exception_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(),
        }
        target = run_dir / "failure.json" if run_dir is not None else RUNS / "startup_failure.json"
        atomic_json(target, failure)
        if run_id and args.run_kind == "formal":
            update_registry(run_id, "failed", completed_epoch=completed_epoch, failure=str(target))
        raise
    finally:
        if lock is not None:
            lock.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("formal", "smoke"), default="smoke")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=int(CONFIG["training"]["seed"]))
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--num-workers", type=int, default=int(CONFIG["training"]["num_workers"]))
    parser.add_argument("--cpu-threads", type=int, default=int(CONFIG["training"]["cpu_threads"]))
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--no-amp", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
