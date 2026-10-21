"""Run every R98 prerequisite and authorize one formal run only on success."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

import torch


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"C:\Users\Rio\anaconda3\python.exe")
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


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    design_path = ROOT / "config" / "experiment_design.json"
    calibration_path = ROOT / "config" / "gpu_batch_calibration.json"
    design = json.loads(design_path.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    execution = json.loads((ROOT / "config" / "execution_policy.json").read_text(encoding="utf-8"))
    acceleration_path = ROOT / "reports" / "acceleration_benchmark.json"
    acceleration = json.loads(acceleration_path.read_text(encoding="utf-8")) if acceleration_path.is_file() else {}
    # Preflight evidence is disposable and must never be mistaken for a formal
    # continuation.  Remove only this experiment's prior smoke outputs.
    for path in sorted((ROOT / "runs").glob("smoke_R98_*")):
        if path.is_dir():
            shutil.rmtree(path)
    smoke_weight_root = ROOT / "weights" / "smoke"
    if smoke_weight_root.is_dir():
        shutil.rmtree(smoke_weight_root)
    for path in (ROOT / "runs" / "active_run.json", ROOT / "reports" / "preflight_report.json"):
        if path.is_file():
            path.unlink()
    model_module = load("r98_preflight_model", ROOT / "model" / "r98_model.py")
    model = model_module.build_model(int(design["architecture"]["model_width"]))
    contract = model_module.architecture_contract(model)
    checks = {
        "parameter_count_matches": int(contract["parameter_count"]) == int(design["architecture"]["parameter_count"]),
        "no_learned_amplitude_gate": contract["learned_amplitude_gate_present"] is False,
        "source_phase_locked_texture": contract["texture_is_source_phase_locked"] is True,
        "six_source_texture_bands": contract["texture_source_band_count"] == 6,
        "source_texture_energy_features": contract["source_texture_energy_features_present"] is True,
        "private_groups_do_not_overlap": contract["learned_parameter_group_overlap"] is False,
        "no_formal_registry_exists": not (ROOT / "runs" / "formal_run_registry.json").exists(),
        "guarded_acceleration_passed": acceleration.get("passed") is True,
        "acceleration_evidence_current": acceleration.get("source_hashes") == source_hashes(),
        "selected_batches_consistent": (
            acceleration.get("selected_scene_batches")
            == calibration.get("selected_scene_batches")
            == execution.get("scene_batch_overrides")
        ),
    }
    selected = acceleration.get("selected_scene_batches", {})
    selected_rows = {
        str(row.get("patch")): row
        for row in acceleration.get("measurements", [])
        if not row.get("failed") and int(row.get("scene_batch", -1)) == int(selected.get(str(row.get("patch")), -2))
    }
    guard_mib = int(acceleration.get("minimum_free_vram_guard_mib", 0))
    checks["selected_batches_have_finite_loss_and_gradient"] = (
        set(selected_rows) == set(selected)
        and all(row.get("loss_finite") is True and row.get("gradient_finite") is True for row in selected_rows.values())
    )
    checks["selected_batches_preserve_vram_guard"] = (
        guard_mib >= 2048
        and all(int(row.get("minimum_free_mib_seen", 0)) >= guard_mib for row in selected_rows.values())
    )
    checks["crash_candidate_is_forbidden"] = 8 in execution.get("forbidden_scene_batches", {}).get("512", [])
    checks["same_run_recovery_contract_present"] = (
        "--continue-formal" in (ROOT / "training" / "train_r98_core.py").read_text(encoding="utf-8")
        and "same-run checkpoint identity" in (ROOT / "training" / "train_r98_core.py").read_text(encoding="utf-8")
    )
    test = subprocess.run(
        [str(PYTHON), "-m", "pytest", "-q", str(ROOT / "tests")],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    checks["pytest_passed"] = test.returncode == 0
    stage_benchmark = subprocess.run(
        [str(PYTHON), "-u", str(ROOT / "scripts" / "benchmark_patch_stages.py")],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    checks["all_patch_stages_backward_passed"] = stage_benchmark.returncode == 0
    smoke = subprocess.run(
        [str(PYTHON), "-u", str(ROOT / "training" / "train_r98.py"),
         "--run-kind", "smoke", "--device", "cuda:0", "--cpu-threads", "4",
         "--max-train-batches", "2", "--max-validation-batches", "2"],
        cwd=ROOT, check=False, capture_output=True, text=True,
    )
    checks["end_to_end_smoke_passed"] = smoke.returncode == 0
    active_path = ROOT / "runs" / "active_run.json"
    active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.is_file() else {}
    checks["smoke_checkpoint_written"] = bool(active.get("weight_dir")) and (Path(active["weight_dir"]) / "latest.pth.tar").is_file()
    checks["smoke_completed_one_epoch"] = int(active.get("completed_epoch", 0)) == 1 and active.get("status") == "smoke_complete"
    validation = active.get("final_validation", {})
    checks["periodic_validation_present"] = "periodic_match_margin" in validation and "periodic_wrong_pitch_rate" in validation
    checks["all_smoke_values_finite"] = all(
        isinstance(value, (int, float)) and float("-inf") < float(value) < float("inf")
        for value in validation.values()
    )
    passed = all(checks.values())
    report = {
        "experiment_id": design["experiment_id"], "passed": passed,
        "source_hashes": source_hashes(),
        "checks": checks, "architecture_contract": contract,
        "pytest_stdout": test.stdout[-4000:], "pytest_stderr": test.stderr[-4000:],
        "patch_benchmark_stdout": stage_benchmark.stdout[-8000:],
        "patch_benchmark_stderr": stage_benchmark.stderr[-4000:],
        "smoke_stdout": smoke.stdout[-8000:], "smoke_stderr": smoke.stderr[-8000:],
        "smoke_validation": validation,
        "smoke_gpu_peak_gib": active.get("gpu_peak_gib"),
    }
    write_json(ROOT / "reports" / "preflight_report.json", report)
    if passed:
        design["status"] = "preflight_passed_formal_training_authorized"
        design["formal_training_authorized"] = True
        design["formal_training_blocker"] = None
        write_json(design_path, design)
        calibration["status"] = "r98_end_to_end_smoke_passed"
        calibration["passed"] = True
        calibration["smoke_gpu_peak_gib"] = active.get("gpu_peak_gib")
        write_json(calibration_path, calibration)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
