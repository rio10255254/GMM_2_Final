"""Measure all R116 optimization paths at a requested scene batch size."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import build_model
from training.dataset import R116Dataset
from training.train import Stage, flatten_batch, make_loader, objective_for_batch, set_trainable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size-scenes", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    dataset = R116Dataset("train", epoch=23, limit=max(32, args.batch_size_scenes * 2))
    raw_batch = next(iter(make_loader(dataset, args.batch_size_scenes, 0, False, 116)))
    batch = flatten_batch(raw_batch, device)
    rows = []
    for group in ("detector", "width", "shift", "detail"):
        model = build_model().to(device).train()
        active = set_trainable(model, group)
        paired = group in {"width", "shift"}
        stage = Stage(f"benchmark_{group}", group, paired)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
        started = time.perf_counter()
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            loss, _components = objective_for_batch(model, stage, batch, 23, "probe")
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(active, 5.0)
        torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - started
        rows.append({
            "group": group,
            "paired": paired,
            "loss": float(loss.detach().cpu()),
            "gradient_norm": float(norm.detach().cpu()),
            "seconds": elapsed,
            "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
            "peak_reserved_gib": torch.cuda.max_memory_reserved(device) / 2**30,
        })
        del model, active, loss, norm
        torch.cuda.empty_cache()
    free_bytes, total_bytes = torch.cuda.mem_get_info(device)
    result = {
        "status": "passed",
        "batch_size_scenes": args.batch_size_scenes,
        "images_per_step": args.batch_size_scenes * 3,
        "device": torch.cuda.get_device_name(0),
        "paths": rows,
        "gpu_free_gib_after": free_bytes / 2**30,
        "gpu_total_gib": total_bytes / 2**30,
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
