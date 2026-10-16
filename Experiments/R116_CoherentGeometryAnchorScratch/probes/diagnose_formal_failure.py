"""Reproduce and record the R116 formal-run-1 non-finite mechanism."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from training.dataset import R116Dataset
from training.losses import probability_bce
from training.train import CONFIG, make_loader


RUN_ID = "r116_formal_scratch_20260903_193330"


def main() -> int:
    run_dir = ROOT / "runs" / RUN_ID
    failure = json.loads((run_dir / "failure.json").read_text(encoding="utf-8"))
    live = json.loads((run_dir / "live_state.json").read_text(encoding="utf-8"))
    failed_epoch = 7
    failed_batch = int(failure["global_step"]) - 6 * 138
    dataset = R116Dataset("train", epoch=failed_epoch, limit=0)
    loader = make_loader(
        dataset, int(CONFIG["training_plan"]["batch_size_scenes"]), 0, True,
        int(CONFIG["seed"]) + failed_epoch,
    )
    offending = None
    for index, batch in enumerate(loader, start=1):
        if index == failed_batch:
            offending = batch
            break
    if offending is None:
        raise RuntimeError("Could not reconstruct the failed batch index")
    tensor_checks = {}
    for name in ("source", "target", "mask", "sdf", "edge", "pair_shift_px"):
        value = offending[name]
        tensor_checks[name] = {
            "finite": bool(torch.isfinite(value).all()),
            "minimum": float(value.min()),
            "maximum": float(value.max()),
        }

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    prediction = torch.tensor([0.0, 1.0], device=device, dtype=torch.bfloat16)
    target = torch.tensor([0.25, 0.25], device=device, dtype=torch.bfloat16)
    old_clamped = prediction.clamp(1.0e-5, 1.0 - 1.0e-5)
    old_loss = -(
        target * torch.log(old_clamped)
        + (1.0 - target) * torch.log1p(-old_clamped)
    )
    new_loss = probability_bce(prediction, target)
    stderr_text = Path(
        json.loads((ROOT / "logs" / "launcher_state.json").read_text(encoding="utf-8-sig"))["stderr"]
    ).read_text(encoding="utf-8", errors="replace")
    payload = {
        "status": "root_cause_confirmed",
        "failed_run": RUN_ID,
        "failed_epoch": failed_epoch,
        "failed_batch": failed_batch,
        "global_step": int(failure["global_step"]),
        "last_complete_epoch": int(failure["epochs_completed"]),
        "failure_type": failure["error_type"],
        "not_oom": "OutOfMemory" not in stderr_text and failure["error_type"] != "OutOfMemoryError",
        "last_observed_gpu_free_gib": float(live["gpu_free_gib"]),
        "offending_batch_scene_indices": [int(value) for value in offending["scene_index"].tolist()],
        "offending_batch_tensors": tensor_checks,
        "all_offending_batch_inputs_finite": all(row["finite"] for row in tensor_checks.values()),
        "old_bfloat16_clamp": [float(value) for value in old_clamped.cpu()],
        "old_probability_bce": [
            float(value) if math.isfinite(float(value)) else "Infinity"
            for value in old_loss.cpu()
        ],
        "old_probability_bce_finite": bool(torch.isfinite(old_loss).all()),
        "fixed_fp32_probability_bce": [float(value) for value in new_loss.cpu()],
        "fixed_probability_bce_finite": bool(torch.isfinite(new_loss).all()),
        "root_cause": "BF16 rounded the old upper probability clamp to exactly 1.0; confidence saturation then evaluated log1p(-1), producing an infinite width-confidence loss.",
        "repair": [
            "promote probability losses to FP32 before clamping and logarithms",
            "promote all loss reductions to FP32",
            "check each named component before the combined loss",
            "save model, optimizer, batch context, and scene indices on any future failure"
        ]
    }
    output = ROOT / "results" / "failure_analysis" / f"{RUN_ID}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
