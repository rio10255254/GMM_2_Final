"""Verify and seal the prepared R116 architecture design without authorizing training."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.r116_model import build_model, count_parameters


CORE_FILES = (
    "README.md",
    "config/experiment.json",
    "reports/R116_ARCHITECTURE_DECISION_ZH.md",
    "model/__init__.py",
    "model/r116_model.py",
    "inference/__init__.py",
    "inference/tiled.py",
    "training/__init__.py",
    "training/dataset.py",
    "training/profile_targets.py",
    "training/losses.py",
    "training/smoke_train.py",
    "data/prepare_dataset.py",
    "probes/README.md",
    "probes/r109_counterfactuals.py",
    "tests/test_model.py",
    "tests/test_losses.py",
    "tests/test_dataset.py",
    "tests/test_profile_targets.py",
    "scripts/validate_architecture.ps1",
    "scripts/finalize_design.py",
    "weights/README.md",
    "runs/README.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    config = read_json(ROOT / "config" / "experiment.json")
    data = read_json(ROOT / "data" / "preparation_result.json")
    cpu = read_json(ROOT / "results" / "architecture_smoke_cpu.json")
    gpu_path = ROOT / "results" / "architecture_smoke_gpu_full.json"
    gpu = read_json(gpu_path) if gpu_path.is_file() else {"status": "missing"}
    counterfactual = read_json(
        ROOT / "results" / "counterfactual_smoke" / "counterfactual_state.json"
    )
    missing = [name for name in CORE_FILES if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing core files: {missing}")
    model = build_model().eval()
    torch.manual_seed(int(config["seed"]))
    sample = torch.rand(1, 1, 64, 72)
    with torch.inference_mode():
        details = model.forward_details(sample)
    groups = model.parameter_groups()
    identifiers = {name: {id(parameter) for parameter in values} for name, values in groups.items()}
    disjoint = all(
        not identifiers[left] & identifiers[right]
        for index, left in enumerate(identifiers)
        for right in tuple(identifiers)[index + 1:]
    )
    exhaustive = set().union(*identifiers.values()) == {id(parameter) for parameter in model.parameters()}
    checks = {
        "formal_training_blocked": config["training_plan"]["formal_training_authorized"] is False,
        "scratch_only": config["source_isolation"]["scratch_only"] is True,
        "data_prepared": data.get("status") == "complete",
        "data_manifest_matches": data.get("source_manifest_sha256") == data.get("destination_manifest_sha256") == config["data"]["source_manifest_sha256"],
        "data_counts_match": data.get("train_scenes") == 5000 and data.get("validation_scenes") == 512,
        "no_group_overlap": data.get("group_overlap_count") == 0,
        "no_real_training_pixels": data.get("training_uses_real_pixels") is False,
        "cpu_smoke_passed": cpu.get("status") == "passed",
        "gpu_full_smoke_passed": gpu.get("status") == "passed" and gpu.get("config") == "full",
        "counterfactual_smoke_passed": counterfactual.get("status") == "complete" and counterfactual.get("images") == 1,
        "initial_output_exact_identity": bool(torch.equal(details.output, sample)),
        "initial_width_exact_identity": bool(torch.equal(details.width_gain, torch.ones_like(details.width_gain))),
        "initial_shift_exact_zero": int(torch.count_nonzero(details.normal_shift)) == 0,
        "parameter_groups_disjoint": disjoint,
        "parameter_groups_exhaustive": exhaustive,
        "output_finite": bool(torch.isfinite(details.output).all()),
        "output_bounded": float(details.output.min()) >= 0.0 and float(details.output.max()) <= 1.0,
        "forbidden_global_flags_false": all(
            config["model"][key] is False
            for key in ("global_pooling", "global_fft", "free_image_residual", "learned_global_gate", "shared_trainable_action_backbone")
        ),
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "experiment": config["experiment_id"],
        "checks": checks,
        "parameter_count": count_parameters(model),
        "parameter_groups": {name: sum(parameter.numel() for parameter in values) for name, values in groups.items()},
        "data": data,
        "cpu_smoke": cpu,
        "gpu_full_smoke": gpu,
        "counterfactual_smoke": counterfactual,
        "formal_training_authorized": False,
        "next_required_evidence": [
            "full 101-frame R109 counterfactual reconstruction package",
            "locked internal ACM/LSC/tile checks for surviving counterfactuals",
            "external GMF scores with unchanged template and flow",
            "matched short scratch architecture ablation before a 48-epoch run"
        ],
    }
    write_json(ROOT / "results" / "design_validation.json", report)
    write_json(
        ROOT / "PREPARED_STATE.json",
        {
            "status": "ready_for_counterfactual_and_short_ablation",
            "experiment": config["experiment_id"],
            "architecture_validated": report["status"] == "passed",
            "data_prepared": checks["data_prepared"] and checks["data_manifest_matches"],
            "parameter_count": report["parameter_count"],
            "formal_training_authorized": False,
            "design_validation": "results/design_validation.json",
            "cpu_smoke": "results/architecture_smoke_cpu.json",
            "gpu_full_smoke": "results/architecture_smoke_gpu_full.json",
            "counterfactual_smoke": "results/counterfactual_smoke/counterfactual_state.json",
            "next_step": "generate the full 101-frame counterfactual package and obtain unchanged-flow external GMF scores before finalizing the formal trainer"
        },
    )
    with (ROOT / "FILE_MANIFEST_SHA256.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=("relative_path", "bytes", "sha256"))
        writer.writeheader()
        for name in CORE_FILES:
            path = ROOT / name
            writer.writerow({"relative_path": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
