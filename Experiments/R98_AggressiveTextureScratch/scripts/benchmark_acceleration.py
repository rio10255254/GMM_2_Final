"""Choose the fastest safe scene batch at each R98 formal patch stage."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import subprocess as process_api


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\Rio\anaconda3\python.exe")
MINIMUM_FREE_MIB = 2048
MAXIMUM_CANDIDATE_SECONDS = 120.0
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
    for mutable_key in ("status", "formal_training_authorized", "formal_training_blocker"):
        design.pop(mutable_key, None)
    contract = json.dumps(design, sort_keys=True, separators=(",", ":")).encode("utf-8")
    hashes["config/experiment_design.training_contract"] = hashlib.sha256(contract).hexdigest()
    return hashes


def find_nvidia_smi() -> Path:
    known = Path(r"C:\Windows\System32\DriverStore\FileRepository\nv_dispwi.inf_amd64_9d6b008f0a7ed9e5\nvidia-smi.exe")
    if known.is_file():
        return known
    matches = list(Path(r"C:\Windows\System32\DriverStore\FileRepository").glob("**/nvidia-smi.exe"))
    if not matches:
        raise FileNotFoundError("nvidia-smi.exe")
    return matches[0]


def gpu_free_mib() -> int:
    result = subprocess.run(
        [str(find_nvidia_smi()), "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True,
    )
    return int(result.stdout.strip().splitlines()[0])


def run_candidate(patch: int, core: int, scene_batch: int) -> dict:
    command = [str(PYTHON), str(Path(__file__)), "--child", str(patch), str(core), str(scene_batch)]
    child_process = process_api.Popen(
        command, cwd=ROOT, stdout=process_api.PIPE, stderr=process_api.PIPE,
        text=True,
    )
    started = time.perf_counter()
    minimum_seen = gpu_free_mib()
    stop_reason = None
    while child_process.poll() is None:
        time.sleep(0.75)
        free = gpu_free_mib()
        minimum_seen = min(minimum_seen, free)
        if free < MINIMUM_FREE_MIB:
            stop_reason = f"free VRAM {free} MiB below {MINIMUM_FREE_MIB} MiB guard"
            child_process.terminate()
            break
        if time.perf_counter() - started > MAXIMUM_CANDIDATE_SECONDS:
            stop_reason = f"candidate exceeded {MAXIMUM_CANDIDATE_SECONDS:.0f}s timeout"
            child_process.terminate()
            break
    try:
        stdout, stderr = child_process.communicate(timeout=10)
    except process_api.TimeoutExpired:
        child_process.kill()
        stdout, stderr = child_process.communicate()
    if stop_reason is not None or child_process.returncode:
        return {
            "patch": patch, "core": core, "scene_batch": scene_batch,
            "failed": True, "guard_triggered": stop_reason is not None,
            "reason": stop_reason or f"child exit {child_process.returncode}",
            "minimum_free_mib_seen": minimum_seen,
            "stderr": stderr[-2000:],
        }
    row = json.loads(stdout.strip().splitlines()[-1])
    row["minimum_free_mib_seen"] = minimum_seen
    return row


def load_trainer():
    spec = importlib.util.spec_from_file_location("r98_speed_trainer", ROOT / "training" / "train_r98_core.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["r98_speed_trainer"] = module
    spec.loader.exec_module(module)
    return module


def child(patch: int, core: int, scene_batch: int) -> dict:
    import torch
    module = load_trainer()
    device = torch.device("cuda:0")
    seed = int(module.DESIGN["independence"]["seed"])
    module.seed_all(seed)
    package = Path(module.DESIGN["data"]["source_package"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    dataset = module.DATA.R98SceneDataset(package, manifest, "train", patch, core, 17, master_seed=seed)
    sampler = module.DATA.RoleBalancedBatchSampler(dataset, scene_batch, seed + 17 * 101)
    loader = torch.utils.data.DataLoader(dataset, batch_sampler=sampler, num_workers=0, pin_memory=True)
    model = module.MODEL.build_model(int(module.DESIGN["architecture"]["model_width"])).to(device, memory_format=torch.channels_last).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, fused=True)
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats(device)
    free_before = torch.cuda.mem_get_info(device)[0]
    reserved_before = torch.cuda.memory_reserved(device)
    timings = []
    scenes_processed = 0
    gradient_finite = True
    loss_finite = True
    for batch_index, raw in enumerate(loader, start=1):
        if batch_index > 2:
            break
        started = time.perf_counter()
        batch, scenes, views = module.flatten_batch(raw, device)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            details = model(batch["source"], return_details=True, stage_truth=module.stage_truth(batch, "s"), stage_truth_fraction=0.4)
            branches, _ = module.branch_loss(details, batch, patch, core, "s")
            output, _ = module.output_loss(details, batch, patch, core)
            total = branches + 0.85 * output
        loss_finite = loss_finite and bool(torch.isfinite(total).item())
        if not loss_finite:
            break
        total.backward()
        gradient_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        gradient_finite = gradient_finite and bool(torch.isfinite(gradient_norm).item())
        if not gradient_finite:
            break
        optimizer.step(); optimizer.zero_grad(set_to_none=True)
        torch.cuda.synchronize(device)
        timings.append(time.perf_counter() - started)
        scenes_processed += scenes
    incremental = max(0, torch.cuda.max_memory_reserved(device) - reserved_before)
    steady_seconds = timings[-1]
    return {
        "patch": patch, "core": core, "scene_batch": scene_batch,
        "seconds_per_batch": steady_seconds,
        "scenes_per_second": scene_batch / steady_seconds,
        "megapixels_per_second": scene_batch * patch * patch / steady_seconds / 1e6,
        "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
        "estimated_peak_free_gib": max(0.0, (free_before - incremental) / 2**30),
        "loss_finite": loss_finite,
        "gradient_finite": gradient_finite,
        "finite": loss_finite and gradient_finite,
    }


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    if "--child" in sys.argv:
        index = sys.argv.index("--child")
        print(json.dumps(child(int(sys.argv[index + 1]), int(sys.argv[index + 2]), int(sys.argv[index + 3]))))
        return 0
    candidates = {
        (512, 256): [4, 6],
        (768, 384): [2, 3],
        (896, 512): [1, 2],
    }
    rows = []
    selected = {}
    for (patch, core), batches in candidates.items():
        stage_rows = []
        for scene_batch in batches:
            stage_rows.append(run_candidate(patch, core, scene_batch))
        rows.extend(stage_rows)
        eligible = [
            row for row in stage_rows
            if not row.get("failed") and row["finite"]
            and row["estimated_peak_free_gib"] >= MINIMUM_FREE_MIB / 1024.0
        ]
        if not eligible:
            report = {
                "passed": False, "source_hashes": source_hashes(),
                "measurements": rows, "error": f"no safe batch for patch {patch}",
            }
            write_json(ROOT / "reports" / "acceleration_benchmark.json", report)
            print(json.dumps(report, indent=2))
            return 1
        best = max(eligible, key=lambda row: (row["megapixels_per_second"], row["estimated_peak_free_gib"]))
        selected[str(patch)] = int(best["scene_batch"])
    report = {
        "passed": True, "selected_scene_batches": selected,
        "source_hashes": source_hashes(),
        "minimum_free_vram_guard_mib": MINIMUM_FREE_MIB,
        "forbidden_candidates": {"512": [8], "reason": "2026-08-13 VIDEO_TDR_FAILURE at 84 MiB free"},
        "measurements": rows,
    }
    write_json(ROOT / "reports" / "acceleration_benchmark.json", report)
    execution_path = ROOT / "config" / "execution_policy.json"
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["scene_batch_overrides"] = selected
    execution["acceleration_benchmark"] = str(ROOT / "reports" / "acceleration_benchmark.json")
    write_json(execution_path, execution)
    calibration_path = ROOT / "config" / "gpu_batch_calibration.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    calibration["selected_scene_batches"] = selected
    calibration["acceleration_benchmark_passed"] = True
    write_json(calibration_path, calibration)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
