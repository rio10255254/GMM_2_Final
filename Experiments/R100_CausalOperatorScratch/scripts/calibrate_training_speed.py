"""Measure real R100 training steps and verify the frozen scene batches.

The calibration uses the exact audited arrays, model, loss, BF16 path,
channels-last layout and fused optimizer used by the formal trainer.  CUDA OOM
is recoverable here: a failing candidate is recorded, memory is released, and
the next smaller candidate is tried.  No checkpoint is loaded or written.
"""
from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TRAINER = load_module("r100_calibration_trainer", ROOT / "training" / "train_r100.py")
MODEL_MODULE = load_module("r100_calibration_model", ROOT / "model" / "r100_model.py")
DESIGN = TRAINER.DESIGN


PATCH_PLAN: dict[int, tuple[int, list[int]]] = {
    512: (256, [18]),
    768: (384, [7]),
    896: (512, [5]),
}


def make_batch(dataset: Any, scene_batch: int) -> dict[str, Any]:
    regular = [
        index
        for index in range(len(dataset))
        if dataset.role_at(index) != "exposure_coherent_bundle" and dataset.view_count_at(index) == 2
    ]
    # The exact sampler always includes motion and identity in regular batches.
    motion = next(index for index in regular if dataset.role_at(index) == "signed_subpixel_motion")
    identity = next(index for index in regular if dataset.role_at(index) == "identity_and_detail_guard")
    selected = [motion, identity]
    selected.extend(index for index in regular if index not in {motion, identity})
    selected = selected[:scene_batch]
    loader = DataLoader(dataset, batch_sampler=[selected], num_workers=0, pin_memory=True)
    return next(iter(loader))


def release(*values: Any) -> None:
    del values
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


def measure_candidate(
    package: Path,
    manifest: dict[str, Any],
    patch: int,
    core: int,
    scene_batch: int,
    external_used_gib: float,
    total_gib: float,
) -> dict[str, Any]:
    dataset = TRAINER.R100SceneDataset(package, manifest, "train", patch, core, 7)
    batch = make_batch(dataset, scene_batch)
    device = torch.device("cuda:0")
    model = MODEL_MODULE.build_model(base=int(DESIGN["architecture"]["model_width"])).to(device)
    model = model.to(memory_format=torch.channels_last).train()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(DESIGN["training"]["learning_rate"]),
        weight_decay=float(DESIGN["training"]["weight_decay"]),
        fused=True,
    )
    scenes, views = int(batch["source"].shape[0]), int(batch["source"].shape[1])

    def step() -> float:
        source = batch["source"].to(device, non_blocking=True)
        flat = source.reshape(scenes * views, 1, patch, patch).contiguous(memory_format=torch.channels_last)
        optimizer.zero_grad(set_to_none=True)
        started = time.perf_counter()
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model(flat, return_details=True)
            total, _parts, _aux = TRAINER.loss_components(
                details, batch, patch, core, 7, enable_topology=True,
            )
        total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        torch.cuda.synchronize()
        if not bool(torch.isfinite(total)):
            raise FloatingPointError("non-finite calibration loss")
        return time.perf_counter() - started

    # First pass establishes convolution plans and optimizer state.  Only the
    # second pass is used for throughput; memory is measured across both.
    torch.cuda.reset_peak_memory_stats(device)
    step()
    measured_seconds = step()
    peak_allocated = torch.cuda.max_memory_allocated(device) / 2**30
    peak_reserved = torch.cuda.max_memory_reserved(device) / 2**30
    estimated_free = total_gib - external_used_gib - peak_reserved
    result = {
        "patch_size": patch,
        "core_size": core,
        "scene_batch": scene_batch,
        "views": scenes * views,
        "seconds_per_step": measured_seconds,
        "scenes_per_second": scene_batch / measured_seconds,
        "megapixels_per_second": scenes * views * patch * patch / measured_seconds / 1e6,
        "peak_allocated_gib": peak_allocated,
        "peak_reserved_gib": peak_reserved,
        "estimated_free_gib": estimated_free,
        "status": "passed",
    }
    del optimizer, model, batch, dataset
    release()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leave-free-gib", type=float, default=2.0)
    parser.add_argument("--verify-policy", action="store_true")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for R100 calibration")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    torch.set_float32_matmul_precision("high")
    package, manifest, audit = TRAINER.preflight("smoke")
    if not audit.get("passed"):
        raise RuntimeError("dataset audit failed")
    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    total_gib = total_bytes / 2**30
    external_used_gib = (total_bytes - free_bytes) / 2**30
    plan = PATCH_PLAN
    if args.verify_policy:
        existing_policy = json.loads((ROOT / "config" / "execution_policy.json").read_text(encoding="utf-8"))
        plan = {
            patch: (core, [int(existing_policy["scene_batch_overrides"][str(patch)])])
            for patch, (core, _candidates) in PATCH_PLAN.items()
        }
    rows: list[dict[str, Any]] = []
    selected: dict[str, int] = {}
    for patch, (core, candidates) in plan.items():
        patch_rows: list[dict[str, Any]] = []
        for scene_batch in candidates:
            try:
                row = measure_candidate(
                    package, manifest, patch, core, scene_batch, external_used_gib, total_gib,
                )
            except torch.cuda.OutOfMemoryError as exc:
                row = {
                    "patch_size": patch,
                    "core_size": core,
                    "scene_batch": scene_batch,
                    "status": "cuda_oom",
                    "error": str(exc).splitlines()[0],
                }
                release()
            rows.append(row)
            patch_rows.append(row)
            print(json.dumps(row), flush=True)
        eligible = [
            row for row in patch_rows
            if row["status"] == "passed" and float(row["estimated_free_gib"]) >= float(args.leave_free_gib)
        ]
        if not eligible:
            raise RuntimeError(f"No safe batch found for patch {patch}")
        winner = max(eligible, key=lambda row: float(row["megapixels_per_second"]))
        selected[str(patch)] = int(winner["scene_batch"])
    policy = {
        "schema_version": 1,
        "experiment_id": DESIGN["experiment_id"],
        "created_at": datetime.now().isoformat(),
        "selection_method": "highest measured training throughput while retaining requested free VRAM",
        "leave_free_gib": float(args.leave_free_gib),
        "external_gpu_used_gib_at_calibration": external_used_gib,
        "scene_batch_overrides": selected,
        "gradient_accumulation_from_design": True,
        "channels_last": True,
        "fused_adamw": True,
        "bfloat16": True,
        "crop_before_warp_data_path": True,
    }
    report = {
        "policy": policy,
        "measurements": rows,
        "architecture_sha256": TRAINER.sha256_file(ROOT / "model" / "r100_model.py"),
        "trainer_sha256": TRAINER.sha256_file(ROOT / "training" / "train_r100.py"),
        "verification_only": bool(args.verify_policy),
    }
    if args.verify_policy:
        TRAINER.json_dump(ROOT / "reports" / "final_execution_verification.json", report)
    else:
        TRAINER.json_dump(ROOT / "reports" / "acceleration_benchmark.json", report)
        TRAINER.json_dump(ROOT / "config" / "execution_policy.json", policy)
    print(json.dumps(policy, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
