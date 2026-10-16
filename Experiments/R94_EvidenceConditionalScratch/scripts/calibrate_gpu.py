"""Calibrate R94 scene batches against measured A6000 headroom."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

import torch


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def make_batch(scene_batch: int, patch: int, device: torch.device) -> dict[str, torch.Tensor]:
    # One complete S path per scene is enough to measure the dominant memory
    # term; T/B use controls-only passes and are measured separately below.
    images = scene_batch
    generator = torch.Generator(device="cpu").manual_seed(940000 + patch + scene_batch)
    source = torch.rand((images, 1, patch, patch), generator=generator).to(device)
    target = (source * 0.90 + 0.05).clamp(0, 1)
    noise_free = (source * 0.97 + 0.015).clamp(0, 1)
    optical = (target * 0.96 + 0.02).clamp(0, 1)
    mask = (target > 0.5).float()
    support = torch.nn.functional.max_pool2d(mask, 15, stride=1, padding=7)
    return {
        "source": source, "target": target, "noise_free": noise_free,
        "optical": optical, "mask": mask, "support": support,
    }


def check(model_module, trainer, device: torch.device, patch: int, core: int, scene_batch: int, minimum_free: float) -> dict:
    torch.cuda.empty_cache()
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats()
    free_before, total = torch.cuda.mem_get_info()
    baseline = (total - free_before) / 2**30
    model = model_module.build_model(base=16).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    batch = make_batch(scene_batch, patch, device)
    images = scene_batch
    fake = {
        "source": batch["source"], "target": batch["target"],
        "noise_free_source": batch["noise_free"], "optical_source": batch["optical"],
        "mask": batch["mask"], "boundary_support_truth": batch["support"],
        "need_truth": torch.ones((images, 5, patch, patch), device=device) * 0.5,
        "evidence_truth": torch.ones((images, 3, patch, patch), device=device) * 0.7,
        "supervised_target": batch["target"],
        "nuisance_target": batch["noise_free"] - batch["source"],
        "radiometry_target": batch["optical"] - batch["noise_free"],
        "local_contrast_target": torch.zeros_like(batch["source"]),
        "boundary_target": 0.6 * (batch["target"] - batch["optical"]),
        "texture_target": 0.4 * (batch["target"] - batch["optical"]),
        "identity": torch.zeros(images, dtype=torch.bool, device=device),
        "boundary_level": torch.full((scene_batch,), 0.5, device=device),
        "polarity": torch.ones(scene_batch, device=device),
    }
    select = torch.arange(scene_batch, device=device)
    started = time.perf_counter()
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        controls = model.forward_controls(batch["source"])
        controls_total, _ = trainer.controls_loss(controls, fake, patch, core)
        clear_total, _ = trainer.clear_control_loss(
            model, batch["target"][select], batch["mask"][select], batch["support"][select], patch, core,
        )
        noise_free_total, _ = trainer.noise_free_counterfactual_loss(
            model, batch["noise_free"][select], batch["target"][select], batch["optical"][select],
            batch["mask"][select], batch["support"][select], patch, core, 0.0,
        )
        details = model(batch["source"], return_details=True)
        branches, _ = trainer.branch_losses(details, fake, patch, core)
        output, _ = trainer.full_output_losses(details, fake, patch, core)
        total_loss = controls_total + clear_total + noise_free_total + branches + output
    total_loss.backward()
    optimizer.step()
    torch.cuda.synchronize(device)
    peak = torch.cuda.max_memory_allocated(device) / 2**30
    reserved = torch.cuda.max_memory_reserved(device) / 2**30
    estimated_free = total / 2**30 - baseline - reserved
    result = {
        "patch": patch, "core": core, "scene_batch": scene_batch,
        "flattened_s_views": images, "seconds": time.perf_counter() - started,
        "peak_allocated_gib": peak, "peak_reserved_gib": reserved,
        "baseline_used_gib": baseline, "estimated_peak_free_gib": estimated_free,
        "minimum_required_free_gib": minimum_free,
        "safe": estimated_free >= minimum_free and bool(torch.isfinite(total_loss)),
    }
    del optimizer, model, batch, fake, details, total_loss
    torch.cuda.empty_cache()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--maximum-candidate", type=int, default=4)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device(args.device)
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    model_module = load("r94_cal_model", ROOT / "model" / "r94_model.py")
    trainer = load("r94_cal_trainer", ROOT / "training" / "train_r94.py")
    minimum_free = float(design["training"]["gpu_batch_calibration"]["minimum_memory_left_for_desktop_gib"])
    results = []
    selected: dict[str, int] = {}
    for row in design["training"]["patch_schedule"]:
        patch, core = int(row["patch_size"]), int(row["core_size"])
        candidate = min(int(row["candidate_scene_batch"]), int(args.maximum_candidate))
        chosen = None
        for batch in range(candidate, 0, -1):
            try:
                result = check(model_module, trainer, device, patch, core, batch, minimum_free)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                result = {"patch": patch, "core": core, "scene_batch": batch, "safe": False, "oom": True}
            results.append(result)
            print(json.dumps(result), flush=True)
            if result.get("safe"):
                chosen = batch
                break
        if chosen is None:
            raise RuntimeError(f"No safe batch for patch {patch}")
        selected[str(patch)] = chosen
    payload = {
        "experiment_id": design["experiment_id"], "device": torch.cuda.get_device_name(device),
        "total_memory_gib": torch.cuda.get_device_properties(device).total_memory / 2**30,
        "minimum_memory_left_for_desktop_gib": minimum_free,
        "selected_scene_batches": selected, "results": results, "passed": True,
    }
    json_write(ROOT / "config" / "gpu_batch_calibration.json", payload)
    json_write(ROOT / "reports" / "gpu_batch_calibration.json", payload)
    print(json.dumps(payload, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
