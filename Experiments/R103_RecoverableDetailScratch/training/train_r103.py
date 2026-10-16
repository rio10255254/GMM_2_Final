"""Single-run scratch trainer for R103.

There is intentionally no checkpoint, resume, teacher, or pseudo-label input.
"""
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

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training", ROOT / "evaluation", ROOT / "inference"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from r103_model import build_model, count_parameters  # noqa: E402
from r103_dataset import R103Dataset  # noqa: E402
from losses import central_crop, loss_components, warp_tensor  # noqa: E402
from validate import evaluate, save_real_previews, save_synthetic_preview  # noqa: E402


CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
RUNS = ROOT / "runs"
WEIGHTS = ROOT / "weights"
LOGS = ROOT / "logs"
REPORTS = ROOT / "reports"
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
        raise RuntimeError("Another R103 formal trainer owns the lock") from exc
    return handle


def verify_sources() -> dict[str, Any]:
    reference_path = ROOT / "data" / "TRAINING_DATA_REFERENCE.json"
    audit_path = ROOT / "data" / "source_audit.json"
    if not reference_path.is_file() or not audit_path.is_file():
        raise RuntimeError("Run data/prepare_data.py before training")
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    expected = CONFIG["data"]["base_content_sha256"]
    if reference.get("content_sha256") != expected or audit.get("content_sha256") != expected:
        raise RuntimeError("Training data reference changed")
    if not audit.get("passed") or not audit.get("source_isolation_pass"):
        raise RuntimeError("Source isolation audit failed")
    if reference.get("real_pixels_used_for_training") or reference.get("checkpoint_or_teacher_used"):
        raise RuntimeError("Scratch isolation contract was violated")
    return audit


def stage_for_epoch(epoch: int) -> dict[str, int]:
    for stage in CONFIG["training"]["stages"]:
        if int(stage["start"]) <= epoch <= int(stage["end"]):
            return {key: int(stage[key]) for key in ("patch_size", "core_size", "batch_size")}
    raise RuntimeError(f"No stage for epoch {epoch}")


def learning_rate(epoch: int, total_epochs: int) -> float:
    peak = float(CONFIG["training"]["learning_rate"])
    floor = float(CONFIG["training"]["minimum_learning_rate"])
    if epoch <= 3:
        return peak * (0.35 + 0.65 * epoch / 3.0)
    progress = (epoch - 3) / max(total_epochs - 3, 1)
    return floor + 0.5 * (peak - floor) * (1.0 + math.cos(math.pi * progress))


def make_loader(dataset: R103Dataset, batch_size: int, workers: int, seed: int, shuffle: bool) -> DataLoader:
    generator = torch.Generator()
    generator.manual_seed(seed)
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
        options.update({"prefetch_factor": 2, "persistent_workers": False})
    return DataLoader(**options)


class ObjectiveBalancer:
    """Continuous scale equalization; it never disables an objective."""

    def __init__(self, weights: dict[str, float]):
        self.weights = {str(key): float(value) for key, value in weights.items()}
        self.ema: dict[str, float] = {}
        self.factors: dict[str, float] = {}

    def combine(self, components: dict[str, torch.Tensor]) -> torch.Tensor:
        active = {key: value for key, value in components.items() if key in self.weights and self.weights[key] > 0}
        weighted_values: dict[str, float] = {}
        for key, value in active.items():
            current = self.weights[key] * float(value.detach().clamp_min(0.0).item())
            previous = self.ema.get(key, current)
            self.ema[key] = 0.96 * previous + 0.04 * current
            if self.ema[key] > 1e-10:
                weighted_values[key] = self.ema[key]
        median = float(np.median(list(weighted_values.values()))) if weighted_values else 1.0
        total = next(iter(active.values())).new_zeros(())
        for key, value in active.items():
            if key == "reconstruction":
                factor = 1.0
            else:
                factor = float(np.clip(median / max(self.ema.get(key, median), 1e-10), 0.45, 2.20))
            self.factors[key] = factor
            total = total + self.weights[key] * factor * value
        return total


def combine_objectives(components: dict[str, torch.Tensor]) -> torch.Tensor:
    """Fixed causal weights; scalar loss magnitude is not a gradient proxy."""
    weights = CONFIG["training"]["loss_weights"]
    total = next(iter(components.values())).new_zeros(())
    for key, value in components.items():
        weight = float(weights.get(key, 0.0))
        if weight > 0.0:
            total = total + weight * value
    return total


@torch.no_grad()
def update_ema(model: nn.Module, ema: nn.Module, decay: float) -> None:
    model_parameters = dict(model.named_parameters())
    for name, target in ema.named_parameters():
        target.lerp_(model_parameters[name].detach(), 1.0 - decay)
    model_buffers = dict(model.named_buffers())
    for name, target in ema.named_buffers():
        target.copy_(model_buffers[name])


def register_formal(run_id: str, metadata: dict[str, Any]) -> None:
    path = RUNS / "formal_run_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "experiment_id": CONFIG["experiment_id"], "formal_run_limit": 1, "formal_runs": []
    }
    if registry.get("formal_runs"):
        raise RuntimeError("The one authorized R103 formal run is already registered")
    registry["formal_runs"].append({"run_id": run_id, "registered_at": datetime.now().isoformat(), "status": "starting", **metadata})
    atomic_json(path, registry)


def update_registry(run_id: str, status: str, **fields: Any) -> None:
    path = RUNS / "formal_run_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    row = next(item for item in registry["formal_runs"] if item["run_id"] == run_id)
    row.update({"status": status, "updated_at": datetime.now().isoformat(), **fields})
    atomic_json(path, registry)


def save_checkpoint(path: Path, model: nn.Module, ema: nn.Module, epoch: int, metadata: dict[str, Any], validation: dict[str, Any]) -> None:
    payload = {
        "experiment_id": CONFIG["experiment_id"],
        "epoch": int(epoch),
        "model_state_dict": model.state_dict(),
        "ema_state_dict": ema.state_dict(),
        "metadata": metadata,
        "validation": validation,
        "checkpoint_loaded": False,
        "resume_source": None,
        "teacher_used": False,
    }
    torch.save(payload, path)


def _aux_translation(model: nn.Module, source: torch.Tensor, reference: torch.Tensor, step: int) -> torch.Tensor:
    count = min(2, source.shape[0])
    dx_value = (-0.75, 0.50, 0.875, -0.375)[step % 4]
    dy_value = (0.50, -0.875, -0.25, 0.75)[step % 4]
    dx = source.new_full((count,), dx_value)
    dy = source.new_full((count,), dy_value)
    shifted_source = warp_tensor(source[:count], dx, dy)
    shifted_prediction = model(shifted_source).float()
    target = warp_tensor(reference[:count].detach().float(), dx, dy)
    margin = 24
    return (shifted_prediction[..., margin:-margin, margin:-margin] - target[..., margin:-margin, margin:-margin]).abs().mean()


def _aux_tile(model: nn.Module, source: torch.Tensor, reference: torch.Tensor) -> torch.Tensor:
    full = reference[:1].float()
    crop_source = source[:1, :, 16:-16, 16:-16]
    crop_prediction = model(crop_source).float()
    margin = 56
    full_core = full[..., 16 + margin:-16 - margin, 16 + margin:-16 - margin]
    crop_core = crop_prediction[..., margin:-margin, margin:-margin]
    if not full_core.numel() or full_core.shape != crop_core.shape:
        return full.new_zeros(())
    return (full_core - crop_core).abs().mean()


def run(args: argparse.Namespace) -> int:
    if any(token in " ".join(sys.argv).lower() for token in ("checkpoint", "resume", "pretrain", "teacher", "pseudo")):
        raise RuntimeError("R103 accepts no prior-model input")
    if args.run_kind not in {"formal", "smoke"}:
        raise ValueError("run_kind must be formal or smoke")
    lock = acquire_lock() if args.run_kind == "formal" else None
    completed_epoch = 0
    run_id = ""
    run_dir: Path | None = None
    try:
        audit = verify_sources()
        seed = int(args.seed)
        set_seed(seed)
        torch.set_num_threads(int(args.cpu_threads))
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")

        model_cfg = CONFIG["model"]
        bounds = model_cfg["branch_bounds"]
        model = build_model(
            base=int(model_cfg["base_channels"]),
            low_bound=float(bounds["radiometry"]),
            contour_bound=float(bounds["contour"]),
            texture_bound=float(bounds["texture"]),
            combined_bound=float(bounds["combined"]),
        )
        initial_hash = state_sha256(model)
        parameter_count = count_parameters(model)
        model = model.to(device).to(memory_format=torch.channels_last)
        ema = copy.deepcopy(model).eval()
        for parameter in ema.parameters():
            parameter.requires_grad_(False)

        optimizer_kwargs = {
            "lr": float(CONFIG["training"]["learning_rate"]),
            "weight_decay": float(CONFIG["training"]["weight_decay"]),
            "betas": (0.9, 0.99),
        }
        fused_optimizer = False
        try:
            optimizer = torch.optim.AdamW(model.parameters(), fused=(device.type == "cuda"), **optimizer_kwargs)
            fused_optimizer = device.type == "cuda"
        except TypeError:
            optimizer = torch.optim.AdamW(model.parameters(), **optimizer_kwargs)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{'training' if args.run_kind == 'formal' else 'smoke'}_R103_scratch_seed{seed}_{timestamp}"
        run_dir = RUNS / run_id
        if run_dir.exists():
            raise RuntimeError(f"Run directory already exists: {run_dir}")
        run_dir.mkdir(parents=True)
        weight_dir = WEIGHTS / args.run_kind / f"seed_{seed}" / run_id
        weight_dir.mkdir(parents=True, exist_ok=False)
        total_epochs = int(args.epochs or CONFIG["training"]["epochs"])
        if args.run_kind == "smoke":
            total_epochs = min(total_epochs, 2)

        metadata = {
            "experiment_id": CONFIG["experiment_id"],
            "run_id": run_id,
            "run_kind": args.run_kind,
            "seed": seed,
            "started_at": datetime.now().isoformat(),
            "trainer_pid": os.getpid(),
            "device": str(device),
            "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
            "parameter_count": parameter_count,
            "initial_parameter_sha256": initial_hash,
            "config_sha256": sha256_file(CONFIG_PATH),
            "dataset_content_sha256": CONFIG["data"]["base_content_sha256"],
            "source_audit": audit,
            "checkpoint_loaded": False,
            "resume_source": None,
            "teacher_used": False,
            "real_training_pixels": False,
            "optimizer_fresh": True,
            "fused_optimizer": fused_optimizer,
        }
        if args.run_kind == "formal":
            register_formal(run_id, metadata)
        active_path = RUNS / ("active_run.json" if args.run_kind == "formal" else "active_smoke_run.json")
        atomic_json(active_path, {**metadata, "status": "active", "planned_epochs": total_epochs, "completed_epoch": 0})
        atomic_json(run_dir / "run_provenance.json", metadata)
        (run_dir / "scratch_proof.txt").write_text(
            "Random initialization only. No checkpoint, resume, teacher, pseudo-label, SEM pixel, or HS100MG structure was loaded.\n",
            encoding="utf-8",
        )

        log_path = run_dir / "training_log.csv"
        fieldnames = [
            "epoch", "seconds", "learning_rate", "patch_size", "core_size", "batch_size", "steps",
            "train_total", "train_reconstruction", "train_contour", "train_high_frequency",
            "train_identity", "train_flat_negative", "train_paired_observation", "train_translation", "train_tile",
            "grad_norm", "gpu_peak_allocated_gib", "gpu_free_end_gib", "validation_psnr_db",
            "validation_contour", "validation_texture", "validation_identity", "validation_flat_negative",
            "validation_paired_observation", "validation_displacement", "validation_tile_consistency",
        ]
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=fieldnames).writeheader()

        latest_validation: dict[str, Any] = {}
        global_step = 0
        training_started = time.perf_counter()
        for epoch in range(1, total_epochs + 1):
            epoch_started = time.perf_counter()
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
            stage = stage_for_epoch(epoch)
            if args.run_kind == "smoke":
                stage = {"patch_size": 192, "core_size": 128, "batch_size": min(4, stage["batch_size"])}
            dataset = R103Dataset("train", stage["patch_size"], epoch)
            loader = make_loader(dataset, stage["batch_size"], int(args.num_workers), seed + epoch * 1009, True)
            lr = learning_rate(epoch, total_epochs)
            for group in optimizer.param_groups:
                group["lr"] = lr
            model.train()
            totals: dict[str, float] = {}
            sample_count = 0
            last_grad_norm = 0.0
            for local_step, batch in enumerate(loader, start=1):
                if args.max_train_batches and local_step > int(args.max_train_batches):
                    break
                global_step += 1
                source = batch["source"].to(device, non_blocking=True)
                target = batch["target"].to(device, non_blocking=True)
                mask = batch["mask"].to(device, non_blocking=True)
                b, v, c, h, w = source.shape
                flat_source = source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last)
                flat_target = target.reshape(b * v, c, h, w)
                flat_mask = mask.reshape(b * v, c, h, w)
                flat_midpoint = batch["midpoint"].to(device).repeat_interleave(v)
                flat_polarity = batch["polarity"].to(device).repeat_interleave(v)
                flat_mode = batch["mode"].to(device).repeat_interleave(v)
                flat_identity = batch["identity"].to(device).reshape(-1)
                flat_motion = batch["motion"].to(device).reshape(-1, 2)
                optimizer.zero_grad(set_to_none=True)
                amp_enabled = device.type == "cuda" and not args.no_amp
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=amp_enabled):
                    details = model.forward_details(flat_source)
                    components = loss_components(
                        details, flat_source, flat_target, flat_mask, flat_midpoint, flat_polarity,
                        flat_mode, flat_identity, flat_motion, stage["core_size"],
                    )
                    if global_step % int(CONFIG["training"]["auxiliary_frequency"]["translation_every_steps"]) == 0:
                        components["translation"] = _aux_translation(model, flat_source, details.output, global_step)
                    else:
                        components["translation"] = details.output.new_zeros(())
                    if global_step % int(CONFIG["training"]["auxiliary_frequency"]["tile_every_steps"]) == 0:
                        components["tile"] = _aux_tile(model, flat_source, details.output)
                    else:
                        components["tile"] = details.output.new_zeros(())
                    loss = combine_objectives(components)
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError(f"Non-finite loss at epoch {epoch}, step {local_step}")
                loss.backward()
                last_grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0))
                if not math.isfinite(last_grad_norm):
                    raise FloatingPointError(f"Non-finite gradient at epoch {epoch}, step {local_step}")
                optimizer.step()
                update_ema(model, ema, float(CONFIG["training"]["ema_decay"]))

                count = b * v
                sample_count += count
                totals["total"] = totals.get("total", 0.0) + float(loss.detach()) * count
                for key, value in components.items():
                    totals[key] = totals.get(key, 0.0) + float(value.detach()) * count

                if local_step == 1 or local_step % 10 == 0:
                    elapsed_epoch = time.perf_counter() - epoch_started
                    epoch_steps = min(len(loader), int(args.max_train_batches)) if args.max_train_batches else len(loader)
                    seconds_per_step = elapsed_epoch / local_step
                    progress = {
                        **metadata,
                        "status": "active",
                        "planned_epochs": total_epochs,
                        "completed_epoch": epoch - 1,
                        "current_epoch": epoch,
                        "current_step": local_step,
                        "epoch_steps": epoch_steps,
                        "seconds_per_step": seconds_per_step,
                        "epoch_remaining_seconds": max(epoch_steps - local_step, 0) * seconds_per_step,
                        "overall_elapsed_seconds": time.perf_counter() - training_started,
                        "updated_at": datetime.now().isoformat(),
                    }
                    atomic_json(active_path, progress)

            train_metrics = {key: value / max(sample_count, 1) for key, value in totals.items()}
            validation_now = epoch == 1 or epoch % int(CONFIG["training"]["validation_every_epochs"]) == 0 or epoch == total_epochs
            synthetic_preview = None
            real_previews: list[str] = []
            if validation_now:
                validation_dataset = R103Dataset(
                    "validation", 256, 0, validation_limit=int(CONFIG["validation"]["synthetic_samples"])
                )
                validation_loader = make_loader(validation_dataset, 8, min(int(args.num_workers), 2), seed + 900000, False)
                latest_validation = evaluate(ema, validation_loader, device, 192, amp_enabled=False)
                if epoch == 1 or epoch % int(CONFIG["training"]["preview_every_epochs"]) == 0 or epoch == total_epochs:
                    synthetic_preview = save_synthetic_preview(ema, validation_dataset, device, epoch, amp_enabled=False)
                    real_previews = save_real_previews(ema, device, epoch, amp_enabled=False)

            epoch_seconds = time.perf_counter() - epoch_started
            if device.type == "cuda":
                peak_allocated = torch.cuda.max_memory_allocated(device) / (1024**3)
                free_end = torch.cuda.mem_get_info(device)[0] / (1024**3)
            else:
                peak_allocated = free_end = 0.0
            axes = latest_validation.get("axes", {})
            raw_metrics = latest_validation.get("metrics", {})
            row = {
                "epoch": epoch,
                "seconds": epoch_seconds,
                "learning_rate": lr,
                **stage,
                "steps": local_step,
                "train_total": train_metrics.get("total", 0.0),
                "train_reconstruction": train_metrics.get("reconstruction", 0.0),
                "train_contour": train_metrics.get("contour", 0.0),
                "train_high_frequency": train_metrics.get("high_frequency", 0.0),
                "train_identity": train_metrics.get("identity", 0.0),
                "train_flat_negative": train_metrics.get("flat_negative", 0.0),
                "train_paired_observation": train_metrics.get("paired_observation", 0.0),
                "train_translation": train_metrics.get("translation", 0.0),
                "train_tile": train_metrics.get("tile", 0.0),
                "grad_norm": last_grad_norm,
                "gpu_peak_allocated_gib": peak_allocated,
                "gpu_free_end_gib": free_end,
                "validation_psnr_db": raw_metrics.get("psnr_db", ""),
                "validation_contour": axes.get("contour", ""),
                "validation_texture": axes.get("texture", ""),
                "validation_identity": axes.get("identity", ""),
                "validation_flat_negative": axes.get("flat_negative", ""),
                "validation_paired_observation": axes.get("paired_observation", ""),
                "validation_displacement": axes.get("displacement", ""),
                "validation_tile_consistency": axes.get("tile_consistency", ""),
            }
            with log_path.open("a", newline="", encoding="utf-8") as handle:
                csv.DictWriter(handle, fieldnames=fieldnames).writerow(row)

            checkpoint_now = epoch == 1 or epoch % int(CONFIG["training"]["checkpoint_every_epochs"]) == 0 or epoch == total_epochs
            checkpoint_path = None
            if checkpoint_now:
                checkpoint_path = weight_dir / f"epoch_{epoch:03d}.pth.tar"
                save_checkpoint(checkpoint_path, model, ema, epoch, metadata, latest_validation)
                save_checkpoint(weight_dir / "latest.pth.tar", model, ema, epoch, metadata, latest_validation)
            completed_epoch = epoch
            epoch_record = {
                **metadata,
                "status": "active" if epoch < total_epochs else "completed",
                "planned_epochs": total_epochs,
                "completed_epoch": epoch,
                "latest_epoch_seconds": epoch_seconds,
                "latest_train_metrics": train_metrics,
                "latest_validation": latest_validation,
                "objective_balance_factors": {key: 1.0 for key, value in CONFIG["training"]["loss_weights"].items() if float(value) > 0.0},
                "latest_checkpoint": str(checkpoint_path) if checkpoint_path else None,
                "synthetic_preview": synthetic_preview,
                "real_previews": real_previews,
                "gpu_peak_allocated_gib": peak_allocated,
                "gpu_free_end_gib": free_end,
                "updated_at": datetime.now().isoformat(),
            }
            atomic_json(run_dir / "run_progress.json", epoch_record)
            atomic_json(active_path, epoch_record)
            if args.run_kind == "formal":
                update_registry(run_id, "active" if epoch < total_epochs else "completed", completed_epoch=epoch, latest_checkpoint=epoch_record["latest_checkpoint"])
            print(json.dumps({"epoch": epoch, "seconds": round(epoch_seconds, 2), "train_total": train_metrics.get("total"), "axes": axes, "gpu_free_gib": round(free_end, 2)}, ensure_ascii=False), flush=True)

        summary = {
            **metadata,
            "status": "completed",
            "planned_epochs": total_epochs,
            "completed_epoch": completed_epoch,
            "finished_at": datetime.now().isoformat(),
            "elapsed_seconds": time.perf_counter() - training_started,
            "final_validation": latest_validation,
            "weights_dir": str(weight_dir),
            "training_log": str(log_path),
        }
        atomic_json(run_dir / "run_summary.json", summary)
        atomic_json(active_path, summary)
        if args.run_kind == "formal":
            update_registry(run_id, "completed", completed_epoch=completed_epoch, summary=str(run_dir / "run_summary.json"))
        return 0
    except BaseException as exc:
        failure = {
            "experiment_id": CONFIG["experiment_id"],
            "run_id": run_id or None,
            "status": "failed",
            "completed_epoch": completed_epoch,
            "failed_at": datetime.now().isoformat(),
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
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
