"""Fail-closed launcher for the one R95 formal scratch run."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def lower_failed_epoch_batch(policy: dict) -> tuple[dict, str]:
    registry = json.loads((ROOT / "runs" / "formal_run_registry.json").read_text(encoding="utf-8"))
    run_id = str(registry["formal_runs"][0]["run_id"])
    trace_path = ROOT / "runs" / ("training_" + run_id) / "startup_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    epoch = int(trace.get("epoch", 0))
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    patch = None
    for row in design["training"]["patch_schedule"]:
        if int(row["epoch_start"]) <= epoch <= int(row["epoch_end"]):
            patch = str(int(row["patch_size"]))
            break
    if patch is None:
        return policy, f"could not resolve patch for failed epoch {epoch}"
    overrides = policy.setdefault("scene_batch_overrides", {})
    current = int(overrides[patch])
    fallbacks = [int(value) for value in policy.get("oom_fallback_scene_batches", {}).get(patch, [])]
    smaller = [value for value in fallbacks if value < current]
    if smaller:
        selected = max(smaller)
        overrides[patch] = selected
        action = f"epoch {epoch}: patch {patch} scene batch {current} -> {selected}"
    else:
        action = f"epoch {epoch}: patch {patch} already at minimum scene batch {current}; retrying in a clean process"
    policy.setdefault("automatic_oom_adjustments", []).append({
        "at": datetime.now().isoformat(), "action": action,
    })
    return policy, action


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--continue-interrupted-formal", action="store_true")
    args = parser.parse_args()
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    calibration = json.loads((ROOT / "config" / "gpu_batch_calibration.json").read_text(encoding="utf-8"))
    if design.get("formal_training_authorized") is not True or calibration.get("passed") is not True:
        raise RuntimeError("R95 formal launch prerequisites are not complete")
    audit = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_locked_design.py")],
        cwd=ROOT, check=False,
    )
    if audit.returncode:
        raise RuntimeError("R95 design audit failed")
    command = [
        sys.executable, "-u", str(ROOT / "training" / "train_r95.py"),
        "--run-kind", "formal", "--device", args.device,
        "--num-workers", str(args.num_workers),
        "--cpu-threads", str(args.cpu_threads),
    ]
    if args.continue_interrupted_formal:
        command.append("--continue-interrupted-formal")
    maximum_restarts = int(calibration.get("maximum_automatic_oom_restarts", 0))
    if args.continue_interrupted_formal:
        recovery_path = ROOT / "config" / "interruption_recovery.json"
        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
        maximum_restarts = int(recovery.get("maximum_automatic_oom_restarts", 0))
    restarts = 0
    while True:
        result = subprocess.call(command, cwd=ROOT)
        if result != 75 or not args.continue_interrupted_formal:
            return result
        if restarts >= maximum_restarts:
            return result
        restarts += 1
        recovery_path = ROOT / "config" / "interruption_recovery.json"
        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
        recovery, action = lower_failed_epoch_batch(recovery)
        write_json_atomic(recovery_path, recovery)
        print(f"R95 automatic CUDA-memory recovery {restarts}/{maximum_restarts}: {action}", flush=True)
        time.sleep(2.0)


if __name__ == "__main__":
    raise SystemExit(main())

