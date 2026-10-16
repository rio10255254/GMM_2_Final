"""Stress the repaired R116 width loss past the original failure point."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import build_model
from training.dataset import R116Dataset
from training.train import (
    CONFIG,
    Stage,
    finite,
    flatten_batch,
    learning_rate,
    make_loader,
    objective_for_batch,
    set_trainable,
)


CHECKPOINT = ROOT / "runs" / "r116_formal_scratch_20260903_193330" / "weights" / "epoch_004.pth"


def main() -> int:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    saved = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = build_model().to(device)
    model.load_state_dict(saved["model"], strict=True)
    active = set_trainable(model, "width")
    plan = CONFIG["training_plan"]
    optimizer = torch.optim.AdamW(
        active,
        lr=float(plan["width_learning_rate"]),
        weight_decay=float(plan["weight_decay"]),
    )
    dataset = R116Dataset("train", epoch=7, limit=0)
    loader = make_loader(dataset, 36, 4, True, int(CONFIG["seed"]) + 7)
    stage = Stage("stress_independent_width", "width", False)
    target_lr = learning_rate("width", 7, 48, "formal", 36)
    losses = []
    gradients = []
    batch_59_scenes = None
    started = time.perf_counter()
    torch.cuda.reset_peak_memory_stats(device)
    model.train()
    for step, raw_batch in enumerate(loader, start=1):
        batch = flatten_batch(raw_batch, device)
        if step == 59:
            batch_59_scenes = batch["scene_index"]
        warmup = min(1.0, step / int(plan["warmup_steps_per_group"]))
        for group in optimizer.param_groups:
            group["lr"] = target_lr * warmup
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            total, components = objective_for_batch(model, stage, batch, 7, "formal")
        for name, value in components.items():
            finite(f"component.{name}", value)
        finite("loss", total)
        total.backward()
        norm = torch.nn.utils.clip_grad_norm_(active, float(plan["gradient_clip"]))
        finite("gradient", norm)
        optimizer.step()
        losses.append(float(total.detach().cpu()))
        gradients.append(float(norm.detach().cpu()))
        if step in {1, 59, len(loader)}:
            print(json.dumps({"step": step, "steps": len(loader), "loss": losses[-1], "gradient": gradients[-1]}), flush=True)

    # Force the exact BF16 endpoint that broke run 1, then exercise loss and
    # backward on the original batch position once more.
    raw_batch = next(iter(make_loader(dataset, 36, 0, False, 116)))
    batch = flatten_batch(raw_batch, device)
    with torch.no_grad():
        model.width_head.bias[1] = 20.0
    optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        saturated_total, saturated_components = objective_for_batch(
            model, stage, batch, 7, "formal",
        )
    for name, value in saturated_components.items():
        finite(f"saturated_component.{name}", value)
    finite("saturated_loss", saturated_total)
    saturated_total.backward()
    saturated_norm = torch.nn.utils.clip_grad_norm_(active, float(plan["gradient_clip"]))
    finite("saturated_gradient", saturated_norm)
    with torch.inference_mode(), torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        confidence = model.forward_details(batch["source"]).width_confidence
    result = {
        "status": "passed",
        "diagnostic_only_checkpoint_load": str(CHECKPOINT),
        "formal_weights_reused": False,
        "steps_completed": len(losses),
        "original_failure_step_within_width_epoch": 59,
        "passed_original_failure_point": len(losses) > 59,
        "batch_59_scene_indices": batch_59_scenes,
        "loss_first": losses[0],
        "loss_at_59": losses[58],
        "loss_last": losses[-1],
        "loss_all_finite": all(torch.isfinite(torch.tensor(losses)).tolist()),
        "gradient_max": max(gradients),
        "saturated_confidence_min": float(confidence.min().cpu()),
        "saturated_confidence_max": float(confidence.max().cpu()),
        "saturated_loss": float(saturated_total.detach().cpu()),
        "saturated_gradient": float(saturated_norm.detach().cpu()),
        "saturated_case_finite": bool(torch.isfinite(saturated_total) and torch.isfinite(saturated_norm)),
        "elapsed_seconds": time.perf_counter() - started,
        "gpu_peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
        "gpu_peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30,
    }
    output = ROOT / "results" / "failure_analysis" / "width_numeric_stress.json"
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
