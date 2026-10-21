"""Fail-closed launcher for the sole R98 scratch training run."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
# Keep the repository-wide artifact identity contract explicit even though R98
# uses a self-contained trainer instead of the legacy shared CFG module.
CFG = SimpleNamespace(MODEL_NAME="R98_AggressiveTextureScratch")
trainer = SimpleNamespace()
trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
MEASURED_SOURCE_FILES = (
    Path("model/r98_model.py"),
    Path("training/r98_dataset.py"),
    Path("training/train_r98_core.py"),
    Path("training/periodic_disambiguation.py"),
    Path("training/counterfactual_targets.py"),
    Path("training/causal_stage_replay.py"),
)


def source_hashes() -> dict[str, str]:
    hashes = {
        path.as_posix(): hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in MEASURED_SOURCE_FILES
    }
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    if design.get("model_name") != trainer.MODEL_NAME_BASE:
        raise RuntimeError("R98 artifact identity does not match the locked model name")
    for mutable_key in ("status", "formal_training_authorized", "formal_training_blocker"):
        design.pop(mutable_key, None)
    contract = json.dumps(design, sort_keys=True, separators=(",", ":")).encode("utf-8")
    hashes["config/experiment_design.training_contract"] = hashlib.sha256(contract).hexdigest()
    return hashes


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def find_nvidia_smi() -> Path:
    matches = list(Path(r"C:\Windows\System32\DriverStore\FileRepository").glob("**/nvidia-smi.exe"))
    if not matches:
        raise FileNotFoundError("nvidia-smi.exe")
    return matches[0]


def gpu_free_mib(smi: Path) -> int:
    result = subprocess.run(
        [str(smi), "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True,
    )
    return int(result.stdout.strip().splitlines()[0])


def run_guarded(command: list[str], guard_mib: int, smi: Path) -> tuple[int, dict | None]:
    process = subprocess.Popen(command, cwd=ROOT)
    minimum_seen = gpu_free_mib(smi)
    while process.poll() is None:
        time.sleep(1.0)
        free = gpu_free_mib(smi)
        minimum_seen = min(minimum_seen, free)
        if free < guard_mib:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return int(process.returncode or 1), {
                "kind": "low_free_vram", "free_mib": free,
                "minimum_free_mib_seen": minimum_seen,
            }
    return int(process.returncode or 0), None


def formal_entry() -> dict | None:
    path = ROOT / "runs" / "formal_run_registry.json"
    if not path.is_file():
        return None
    registry = json.loads(path.read_text(encoding="utf-8"))
    runs = registry.get("formal_runs", [])
    if len(runs) != 1:
        raise RuntimeError("R98 formal registry must contain exactly one run")
    return runs[0]


def failed_patch(design: dict, entry: dict) -> int:
    record_dir = Path(entry.get("record_dir") or (ROOT / "runs" / f"training_{entry['run_id']}"))
    progress_path = record_dir / "batch_progress.json"
    if progress_path.is_file():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        if int(progress.get("patch_size", 0)):
            return int(progress["patch_size"])
    next_epoch = int(entry.get("completed_epoch", 0)) + 1
    for stage in design["training"]["patch_schedule"]:
        if int(stage["epoch_start"]) <= next_epoch <= int(stage["epoch_end"]):
            return int(stage["patch_size"])
    raise RuntimeError("cannot resolve the failed R98 patch stage")


def reduce_scene_batch(execution_path: Path, design: dict, entry: dict, reason: dict) -> bool:
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    patch = failed_patch(design, entry)
    current = int(execution["scene_batch_overrides"][str(patch)])
    choices = [
        int(value) for value in execution.get("oom_fallback_scene_batches", {}).get(str(patch), [])
        if int(value) < current
    ]
    if not choices:
        return False
    replacement = max(choices)
    execution["scene_batch_overrides"][str(patch)] = replacement
    write_json(execution_path, execution)
    history_path = ROOT / "logs" / "runtime_memory_fallbacks.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.is_file() else {"events": []}
    history["events"].append({
        "at": datetime.now().isoformat(), "run_id": entry["run_id"],
        "patch": patch, "from_scene_batch": current, "to_scene_batch": replacement,
        "reason": reason,
    })
    write_json(history_path, history)
    return True


def configured_batches_are_allowed(execution: dict, acceleration: dict, continuing: bool) -> bool:
    configured = execution.get("scene_batch_overrides", {})
    selected = acceleration.get("selected_scene_batches", {})
    if not continuing:
        return configured == selected
    for patch, measured in selected.items():
        allowed = {int(measured)} | {
            int(value) for value in execution.get("oom_fallback_scene_batches", {}).get(patch, [])
        }
        if int(configured.get(patch, -1)) not in allowed:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--cpu-threads", type=int, default=8)
    args = parser.parse_args()
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    calibration = json.loads((ROOT / "config" / "gpu_batch_calibration.json").read_text(encoding="utf-8"))
    preflight = json.loads((ROOT / "reports" / "preflight_report.json").read_text(encoding="utf-8"))
    execution_path = ROOT / "config" / "execution_policy.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    acceleration = json.loads((ROOT / "reports" / "acceleration_benchmark.json").read_text(encoding="utf-8"))
    entry = formal_entry()
    continuing = entry is not None
    if entry is not None and entry.get("status") == "complete":
        raise RuntimeError("the sole R98 formal run is already complete")
    if design.get("formal_training_authorized") is not True:
        raise RuntimeError("R98 design has not authorized formal training")
    if calibration.get("passed") is not True or preflight.get("passed") is not True:
        raise RuntimeError("R98 preflight or GPU smoke did not pass")
    if preflight.get("source_hashes") != source_hashes():
        raise RuntimeError("R98 preflight evidence is stale for the current sources")
    if acceleration.get("passed") is not True or acceleration.get("source_hashes") != source_hashes():
        raise RuntimeError("R98 acceleration evidence is absent or stale")
    if acceleration.get("selected_scene_batches") != calibration.get("selected_scene_batches"):
        raise RuntimeError("R98 measured and configured scene batches do not match")
    if not configured_batches_are_allowed(execution, acceleration, continuing):
        raise RuntimeError("R98 runtime scene batches are neither measured selections nor recorded fallbacks")
    if 8 not in execution.get("forbidden_scene_batches", {}).get("512", []):
        raise RuntimeError("R98 crash-inducing scene batch is not forbidden")
    command = [
        sys.executable, "-u", str(ROOT / "training" / "train_r98.py"),
        "--run-kind", "formal", "--device", args.device,
        "--cpu-threads", str(args.cpu_threads),
    ]
    if continuing:
        command.append("--continue-formal")
    smi = find_nvidia_smi()
    guard_mib = int(float(execution.get("minimum_free_vram_guard_gib", 6.0)) * 1024)
    for _attempt in range(4):
        return_code, memory_event = run_guarded(command, guard_mib, smi)
        if return_code == 0:
            return 0
        entry = formal_entry()
        active_path = ROOT / "runs" / "active_run.json"
        active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.is_file() else {}
        error_text = str(active.get("error", "")).lower()
        oom = "outofmemory" in error_text or "out of memory" in error_text
        reason = memory_event or ({"kind": "cuda_oom", "error": active.get("error")} if oom else None)
        if entry is None or reason is None or not reduce_scene_batch(execution_path, design, entry, reason):
            return return_code or 1
        command = [
            sys.executable, "-u", str(ROOT / "training" / "train_r98.py"),
            "--run-kind", "formal", "--device", args.device,
            "--cpu-threads", str(args.cpu_threads), "--continue-formal",
        ]
        time.sleep(3.0)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
