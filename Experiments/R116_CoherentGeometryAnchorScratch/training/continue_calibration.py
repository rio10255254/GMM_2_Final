"""Finish R116 epochs 43-48 from the exact epoch-42 interruption snapshot.

This is recovery of one interrupted scratch run, not inheritance from another
experiment.  The detector calibration uses three 12-scene microbatches per
optimizer update so its effective batch remains 36 without exceeding VRAM.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PARENT_RUN_ID = "r116_formal_scratch_20260903_202052"
PARENT_RUN = ROOT / "runs" / PARENT_RUN_ID
SNAPSHOT = PARENT_RUN / "failure_snapshot.pth"
SNAPSHOT_SHA256 = "08166d7c57c5ddbc6d7ea18c6f6c1843876873786e0efb678c8c16635f389b8c"

from model.r116_model import build_model, count_parameters
from training.dataset import R116Dataset
from training.train import (
    CONFIG,
    CONFIG_PATH,
    atomic_json,
    finite,
    flatten_batch,
    formal_stage,
    learning_rate,
    make_loader,
    objective_for_batch,
    save_real_preview,
    save_synthetic_preview,
    seed_all,
    set_trainable,
    sha256,
    validate_all,
    write_history,
)


def calibration_batch_plan(group: str) -> tuple[int, int]:
    return (12, 3) if group == "detector" else (36, 1)


def build_optimizers(model, snapshot: dict[str, Any]):
    plan = CONFIG["training_plan"]
    groups = model.parameter_groups()
    optimizers = {
        name: torch.optim.AdamW(
            parameters,
            lr=float(plan[f"{name}_learning_rate"]),
            weight_decay=float(plan["weight_decay"]),
        )
        for name, parameters in groups.items()
    }
    # The interruption occurred at the detector calibration stage, so the
    # saved optimizer belongs to the detector and can be restored exactly.
    optimizers["detector"].load_state_dict(snapshot["optimizer"])
    return groups, optimizers


def run(args: argparse.Namespace) -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    if not SNAPSHOT.is_file() or sha256(SNAPSHOT) != SNAPSHOT_SHA256:
        raise RuntimeError("The sealed epoch-42 recovery snapshot is missing or changed")
    saved = torch.load(SNAPSHOT, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True or saved.get("checkpoint_loaded") is not False:
        raise RuntimeError("Recovery source is not the clean R116 scratch chain")
    if saved.get("context", {}).get("epoch") != 43 or saved.get("context", {}).get("batch") != 1:
        raise RuntimeError("Recovery snapshot is not the untouched epoch-42 boundary")
    if not all(bool(torch.isfinite(value).all()) for value in saved["model"].values()):
        raise FloatingPointError("Recovery snapshot contains a non-finite parameter")

    run_id = args.run_id or (
        f"r116_calibration_smoke_{time.strftime('%Y%m%d_%H%M%S')}"
        if args.smoke else f"r116_calibration_from_e42_{time.strftime('%Y%m%d_%H%M%S')}"
    )
    run_dir = ROOT / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    lock = ROOT / "runs" / "active_run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(descriptor, run_id.encode("utf-8"))
        os.close(descriptor)
    except FileExistsError as error:
        raise RuntimeError(f"Another R116 run is active: {lock.read_text(encoding='utf-8')}") from error

    seed_all(int(CONFIG["seed"]))
    device = torch.device("cuda:0")
    model = build_model().to(device)
    model.load_state_dict(saved["model"], strict=True)
    groups, optimizers = build_optimizers(model, saved)
    group_steps = {name: int(value) for name, value in saved["group_steps"].items()}
    # The failed batch incremented telemetry before the forward pass but made
    # no optimizer update.  Restore the last successful detector count.
    group_steps["detector"] = 828
    parent_successful_steps = 42 * (5000 // 36)
    global_step = parent_successful_steps
    current_context: dict[str, Any] = {"epoch": 42, "batch": 138, "stage": "recovery_loaded"}
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    epochs = list(range(43, 47)) if args.smoke else list(range(43, 49))
    run_state = {
        "status": "running",
        "run_id": run_id,
        "mode": "calibration_recovery_smoke" if args.smoke else "calibration_continuation",
        "parent_run_id": PARENT_RUN_ID,
        "parent_epochs_complete": 42,
        "parent_snapshot": str(SNAPSHOT),
        "parent_snapshot_sha256": SNAPSHOT_SHA256,
        "same_scratch_chain": True,
        "other_model_weights_loaded": False,
        "device": torch.cuda.get_device_name(0),
        "parameters": count_parameters(model),
        "epochs": epochs,
        "effective_batch_size_scenes": 36,
        "detector_microbatch_scenes": 12,
        "detector_accumulation": 3,
        "config_sha256": sha256(CONFIG_PATH),
    }
    atomic_json(run_dir / "run_state.json", run_state)
    print(json.dumps({"run_started": run_state}), flush=True)

    try:
        for epoch in epochs:
            stage = formal_stage(epoch)
            active_parameters = set_trainable(model, stage.group)
            optimizer = optimizers[stage.group]
            microbatch, accumulation = calibration_batch_plan(stage.group)
            target_updates = 1 if args.smoke else 5000 // 36
            maximum_microbatches = target_updates * accumulation
            target_lr = learning_rate(stage.group, epoch, 48, "formal", 36)
            for parameter_group in optimizer.param_groups:
                parameter_group["lr"] = target_lr
            dataset = R116Dataset("train", epoch=epoch, limit=0)
            loader = make_loader(
                dataset, microbatch, int(args.workers), True,
                int(CONFIG["seed"]) + epoch,
            )
            model.train()
            optimizer.zero_grad(set_to_none=True)
            torch.cuda.reset_peak_memory_stats(device)
            epoch_started = time.perf_counter()
            totals: dict[str, float] = {}
            microbatches = 0
            updates = 0
            for raw_batch in loader:
                if microbatches >= maximum_microbatches:
                    break
                microbatches += 1
                batch = flatten_batch(raw_batch, device)
                current_context = {
                    "epoch": epoch,
                    "microbatch": microbatches,
                    "maximum_microbatches": maximum_microbatches,
                    "optimizer_update": updates,
                    "target_updates": target_updates,
                    "stage": stage.name,
                    "active_group": stage.group,
                    "scene_indices": batch["scene_index"],
                }
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    total, components = objective_for_batch(model, stage, batch, epoch, "formal")
                for name, value in components.items():
                    finite(f"component.{name}", value)
                finite("loss", total)
                (total / accumulation).backward()
                totals["total"] = totals.get("total", 0.0) + float(total.detach().cpu())
                for name, value in components.items():
                    totals[name] = totals.get(name, 0.0) + float(value.detach().cpu())
                if microbatches % accumulation == 0:
                    norm = torch.nn.utils.clip_grad_norm_(
                        active_parameters, float(CONFIG["training_plan"]["gradient_clip"]),
                    )
                    finite("gradient", norm)
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                    updates += 1
                    global_step += 1
                    group_steps[stage.group] += 1
                    if updates == 1 or updates % 25 == 0:
                        free_bytes, total_bytes = torch.cuda.mem_get_info(device)
                        live = {
                            "status": "running",
                            "run_id": run_id,
                            "epoch": epoch,
                            "epochs": epochs,
                            "stage": stage.name,
                            "active_group": stage.group,
                            "microbatch": microbatches,
                            "microbatches": maximum_microbatches,
                            "optimizer_update": updates,
                            "optimizer_updates": target_updates,
                            "effective_batch_size_scenes": 36,
                            "microbatch_size_scenes": microbatch,
                            "accumulation": accumulation,
                            "global_step": global_step,
                            "learning_rate": target_lr,
                            "loss": float(total.detach().cpu()),
                            "gradient_norm": float(norm.detach().cpu()),
                            "gpu_free_gib": free_bytes / 2**30,
                            "gpu_total_gib": total_bytes / 2**30,
                        }
                        atomic_json(run_dir / "live_state.json", live)
                        print(json.dumps({"step_progress": live}), flush=True)
            if microbatches != maximum_microbatches or updates != target_updates:
                raise RuntimeError(
                    f"Incomplete calibration epoch: microbatches={microbatches}, updates={updates}"
                )
            duration = time.perf_counter() - epoch_started
            row: dict[str, Any] = {
                "epoch": epoch,
                "stage": stage.name,
                "active_group": stage.group,
                "microbatch_size_scenes": microbatch,
                "accumulation": accumulation,
                "effective_batch_size_scenes": 36,
                "microbatches": microbatches,
                "optimizer_updates": updates,
                "global_step": global_step,
                "learning_rate": target_lr,
                "duration_seconds": duration,
                "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
                "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30,
            }
            row.update({f"train_{name}": value / microbatches for name, value in totals.items()})
            validation = None
            if not args.smoke:
                validation = validate_all(model, device, 32, 4)
                atomic_json(run_dir / "validation" / f"epoch_{epoch:03d}.json", validation)
                for name in (
                    "worst_degraded_contour_dice", "worst_degraded_contour_gain",
                    "worst_degraded_centroid_gain", "mean_degraded_mae_gain",
                    "identity_change", "flat_change", "mean_normal_shift_abs",
                    "mean_detail_abs",
                ):
                    row[f"validation_{name}"] = validation[name]
                model.eval()
                save_synthetic_preview(
                    model, device, run_dir / "previews" / f"epoch_{epoch:03d}_synthetic.png",
                )
                save_real_preview(
                    model, device, run_dir / "previews" / f"epoch_{epoch:03d}_real.png",
                )
                checkpoint = run_dir / "weights" / f"epoch_{epoch:03d}.pth"
                checkpoint.parent.mkdir(parents=True, exist_ok=True)
                torch.save({
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "group_steps": group_steps,
                    "epoch": epoch,
                    "stage": stage.name,
                    "run_id": run_id,
                    "mode": "calibration_continuation",
                    "scratch": True,
                    "checkpoint_loaded": False,
                    "same_scratch_chain": True,
                    "parent_run_id": PARENT_RUN_ID,
                    "parent_snapshot_sha256": SNAPSHOT_SHA256,
                    "validation": validation,
                    "config": CONFIG,
                }, checkpoint)
            history.append(row)
            atomic_json(run_dir / "training_history.json", history)
            write_history(run_dir / "training_log.csv", history)
            print(json.dumps({"epoch_complete": row}), flush=True)

        completed = {
            **run_state,
            "status": "complete",
            "epochs_completed": epochs,
            "global_step": global_step,
            "elapsed_seconds": time.perf_counter() - started,
        }
        if not args.smoke:
            parent_history = json.loads((PARENT_RUN / "training_history.json").read_text(encoding="utf-8"))
            chain = parent_history + history
            epoch_numbers = [int(row["epoch"]) for row in chain]
            if epoch_numbers != list(range(1, 49)):
                raise RuntimeError("Recovered chain is not exactly epochs 1 through 48")
            completed.update({
                "complete_chain_epochs": 48,
                "complete_chain_valid": True,
                "final_checkpoint": str(run_dir / "weights" / "epoch_048.pth"),
                "final_checkpoint_sha256": sha256(run_dir / "weights" / "epoch_048.pth"),
                "optimizer_recovery": {
                    "detector": "restored from interruption snapshot",
                    "width": "fresh low-rate calibration optimizer; earlier optimizer state was not stored",
                    "shift": "fresh low-rate calibration optimizer; earlier optimizer state was not stored",
                    "detail": "fresh low-rate calibration optimizer; earlier optimizer state was not stored"
                }
            })
            atomic_json(run_dir / "complete_chain_history.json", chain)
            atomic_json(run_dir / "CHAIN_SUMMARY.json", completed)
        atomic_json(run_dir / "run_state.json", completed)
        atomic_json(run_dir / "SUMMARY.json", completed)
        print(json.dumps({"run_complete": completed}), flush=True)
    except BaseException as error:
        failure = {
            "status": "failed",
            "run_id": run_id,
            "error_type": type(error).__name__,
            "error": repr(error),
            "context": current_context,
        }
        try:
            failure_snapshot = run_dir / "failure_snapshot.pth"
            torch.save({
                "model": model.state_dict(),
                "context": current_context,
                "scratch": True,
                "same_scratch_chain": True,
                "parent_snapshot_sha256": SNAPSHOT_SHA256,
                "error": repr(error),
            }, failure_snapshot)
            failure["failure_snapshot"] = str(failure_snapshot)
            failure["failure_snapshot_sha256"] = sha256(failure_snapshot)
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
    parser.add_argument("--run-id", default="")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
