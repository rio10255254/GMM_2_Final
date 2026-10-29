"""Open the sealed R92 holdout exactly once after the E80 checkpoint was frozen."""
from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import pandas as pd
import torch
from torch.utils.data import DataLoader
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"
TRAINING = ROOT / "training" / "train_r92.py"
INFERENCE = ROOT / "inference" / "reconstruct.py"
EPOCH = 80


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    results = Path(PROJECT_ROOT / protocol["output_root"])
    output = results / "sealed_holdout_e80"
    checkpoint = Path(PROJECT_ROOT / protocol["checkpoint_root"]) / f"epoch_{EPOCH:03d}.pth.tar"
    if sha256_file(checkpoint) != str(protocol["checkpoint_sha256"]).lower():
        raise RuntimeError("Checkpoint hash mismatch before holdout access")
    if sha256_file(Path(PROJECT_ROOT / protocol["model_file"])) != str(protocol["model_file_sha256"]).lower():
        raise RuntimeError("Model hash mismatch before holdout access")
    if sha256_file(Path(PROJECT_ROOT / protocol["training_summary"])) != str(protocol["training_summary_sha256"]).lower():
        raise RuntimeError("Training summary hash mismatch before holdout access")

    access_time = datetime.now().astimezone().isoformat()
    access_record = {
        "protocol_id": protocol["protocol_id"],
        "first_holdout_access_at": access_time,
        "selected_checkpoint_epoch": EPOCH,
        "selected_checkpoint": str(checkpoint),
        "selected_checkpoint_sha256": sha256_file(checkpoint),
        "selection_source": protocol["selected_checkpoint_policy"]["selection_source"],
        "selection_locked_before_access": True,
        "external_results_may_reject_but_not_replace_checkpoint": True,
        "nearby_checkpoints_will_not_be_read": True,
    }
    if (output / "holdout_access_record.json").exists():
        previous = json.loads((output / "holdout_access_record.json").read_text(encoding="utf-8"))
        if previous.get("selected_checkpoint_sha256") != access_record["selected_checkpoint_sha256"]:
            raise RuntimeError("Prior holdout access used a different checkpoint")
        access_record = previous
    else:
        write_json(output / "holdout_access_record.json", access_record)

    arm = protocol["arms"]["sealed_holdout"]
    package = Path(PROJECT_ROOT / arm["package"])
    seal_path = package / "SEALED.json"
    manifest_path = package / "manifest.json"
    audit_path = package / "audit.json"
    if sha256_file(seal_path) != str(arm["seal_sha256"]).lower():
        raise RuntimeError("Holdout seal hash mismatch")
    if sha256_file(manifest_path) != str(arm["manifest_sha256"]).lower():
        raise RuntimeError("Holdout manifest hash mismatch")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if not bool(audit.get("passed")) or not bool(audit.get("full_array_hash_audit")):
        raise RuntimeError("Holdout package audit is not valid")
    if int(manifest.get("scene_count", -1)) != int(arm["expected_scenes"]):
        raise RuntimeError("Holdout scene count mismatch")
    if int(manifest.get("total_observations", -1)) != int(arm["expected_observations"]):
        raise RuntimeError("Holdout observation count mismatch")
    if seal.get("manifest_sha256") != sha256_file(manifest_path):
        raise RuntimeError("Seal-to-manifest link mismatch")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    free_before, total_memory = torch.cuda.mem_get_info(device)
    if free_before < 7 * 2**30:
        raise RuntimeError(f"Only {free_before / 2**30:.2f} GiB GPU memory is free")
    training = load_module("r92_holdout_training", TRAINING)
    inference = load_module("r92_holdout_inference", INFERENCE)
    model, payload = inference.load_model(checkpoint, device)
    if int(payload.get("epoch", -1)) != EPOCH:
        raise RuntimeError("Checkpoint epoch mismatch")

    patch_size, core_size = 768, 384
    dataset = training.R92SceneDataset(package, manifest, "locked_holdout", patch_size, core_size, 0, all_observations=True)
    sampler = training.HomogeneousViewBatchSampler(dataset, batch_size=2)
    # A dynamically loaded Dataset class cannot be safely re-imported by
    # Windows spawn workers. Keep the sealed evaluation single-reader and
    # deterministic; inference still runs on CUDA.
    loader = DataLoader(dataset, batch_sampler=sampler, num_workers=0, pin_memory=True, persistent_workers=False)
    print(json.dumps({
        "status": "holdout_evaluation_started",
        "selected_epoch": EPOCH,
        "scenes": len(dataset.records),
        "evaluation_cases": len(dataset),
        "observations": int(manifest["total_observations"]),
    }), flush=True)
    started = time.perf_counter()
    metrics = training.evaluate(model, loader, device, patch_size, core_size, EPOCH, False, max_batches=0)
    elapsed = time.perf_counter() - started
    free_after, _ = torch.cuda.mem_get_info(device)

    payload_out = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "selected_checkpoint_epoch": EPOCH,
        "selected_checkpoint_sha256": sha256_file(checkpoint),
        "weight_source": "ema_state_dict",
        "precision": "fp32",
        "patch_size": patch_size,
        "core_size": core_size,
        "access_record": access_record,
        "seal": seal,
        "holdout_audit": audit,
        "metrics": metrics,
        "elapsed_seconds": elapsed,
        "gpu": {
            "name": torch.cuda.get_device_name(device),
            "free_before_gib": free_before / 2**30,
            "total_gib": total_memory / 2**30,
            "free_after_gib": free_after / 2**30,
        },
        "checkpoint_selection_changed_after_holdout": False,
    }
    write_json(output / "holdout_metrics.json", payload_out)

    role_rows: list[dict[str, Any]] = []
    for role, values in metrics["roles"].items():
        role_rows.append({"role": role, **values})
    pd.DataFrame(role_rows).to_csv(output / "holdout_metrics_by_role.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([
        {"domain": name, "model_to_raw_error_ratio": value}
        for name, value in metrics["normalized_domain_ratios"].items()
    ]).to_csv(output / "holdout_domain_ratios.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({
        "status": "complete",
        "elapsed_seconds": round(elapsed, 1),
        "balanced_score": metrics["balanced_score"],
        "worst_normalized_domain_error": metrics["worst_normalized_domain_error"],
        "output": str(output),
    }), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
