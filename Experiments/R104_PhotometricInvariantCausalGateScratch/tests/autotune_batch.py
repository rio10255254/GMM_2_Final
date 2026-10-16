"""Measure real R104 forward/backward memory and select one batch per patch size."""
from __future__ import annotations

import argparse
import gc
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "model", ROOT / "training"):
    sys.path.insert(0, str(folder))

from r104_model import build_model  # noqa: E402
from r104_dataset import R104Dataset  # noqa: E402
from losses import loss_components  # noqa: E402

CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def flatten(batch: dict[str, torch.Tensor], device: torch.device) -> dict[str, torch.Tensor]:
    source = batch["source"].to(device)
    b, v, c, h, w = source.shape
    return {
        "source": source.reshape(b * v, c, h, w).contiguous(memory_format=torch.channels_last),
        "target": batch["target"].to(device).reshape(b * v, c, h, w),
        "mask": batch["mask"].to(device).reshape(b * v, c, h, w),
        "sdf": batch["sdf"].to(device).reshape(b * v, c, h, w),
        "illumination_target": batch["illumination_target"].to(device).reshape(b * v, c, h, w),
        "identity": batch["identity"].to(device).reshape(-1),
        "mode": batch["mode"].to(device).repeat_interleave(v),
        "pair_type": batch["pair_type"].to(device).repeat_interleave(v),
        "motion": batch["motion"].to(device).reshape(-1, 2),
    }


def attempt(patch: int, core: int, batch_size: int, device: torch.device) -> dict[str, float | int | bool | str]:
    model = optimizer = data = details = components = total = None
    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        dataset = R104Dataset("train", patch, 1)
        samples = [dataset[index] for index in range(batch_size)]
        batch = torch.utils.data.default_collate(samples)
        data = flatten(batch, device)
        bounds = CONFIG["model"]["branch_bounds"]
        model = build_model(
            base=int(CONFIG["model"]["base_channels"]),
            low_bound=float(bounds["radiometry"]),
            illumination_bound=float(bounds["illumination"]),
            contour_bound=float(bounds["contour_proposal"]),
            texture_bound=float(bounds["texture_proposal"]),
            combined_bound=float(bounds["combined"]),
            gate_initial_probability=float(CONFIG["model"]["gate_initial_probability"]),
        ).to(device).to(memory_format=torch.channels_last)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, fused=True)
        started = time.perf_counter()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            details = model.forward_details(data["source"])
            components = loss_components(details, **data, core_size=core)
            total = sum(float(CONFIG["training"]["loss_weights"].get(k, 0.0)) * v for k, v in components.items())
        total.backward()
        optimizer.step()
        torch.cuda.synchronize(device)
        peak = torch.cuda.max_memory_allocated(device) / 1024**3
        free = torch.cuda.mem_get_info(device)[0] / 1024**3
        return {"passed": True, "batch_size": batch_size, "peak_allocated_gib": peak, "free_gib": free, "seconds": time.perf_counter() - started}
    except torch.cuda.OutOfMemoryError as exc:
        return {"passed": False, "batch_size": batch_size, "reason": "cuda_out_of_memory", "message": str(exc)[:300]}
    finally:
        del total, components, details, data, optimizer, model
        gc.collect()
        torch.cuda.empty_cache()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Test only the smallest configured candidate for each patch.")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    # Exhaustive cuDNN search at an intentionally oversized batch can take
    # minutes and is not representative of steady-state training throughput.
    torch.backends.cudnn.benchmark = False
    torch.backends.cuda.matmul.allow_tf32 = True
    stages = {int(row["patch_size"]): int(row["core_size"]) for row in CONFIG["training"]["stages"]}
    candidates = CONFIG["training"]["batch_autotune"]["candidate_scene_batches"]
    reserve = float(CONFIG["training"]["batch_autotune"]["minimum_free_gpu_gib"])
    report = {
        "status": "running",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "gpu": torch.cuda.get_device_name(device),
        "minimum_free_gpu_gib": reserve,
        "precision": "bfloat16",
        "attempts": {},
        "selected_scene_batches": {},
    }
    for patch, core in sorted(stages.items()):
        rows = []
        values = [int(v) for v in candidates[str(patch)]]
        if args.quick:
            values = values[-1:]
        selected = None
        fallback = None
        for value in values:
            row = attempt(patch, core, value, device)
            rows.append(row)
            if row.get("passed"):
                fallback = value
                if float(row["free_gib"]) >= reserve:
                    selected = value
                    break
        if selected is None:
            selected = fallback
        if selected is None:
            raise RuntimeError(f"No usable batch for patch {patch}: {rows}")
        report["attempts"][str(patch)] = rows
        report["selected_scene_batches"][str(patch)] = int(selected)
        print(json.dumps({"patch": patch, "selected": selected, "attempts": rows}, ensure_ascii=False), flush=True)
    report["status"] = "passed"
    target = ROOT / "reports" / "batch_autotune.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
