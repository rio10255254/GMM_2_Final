"""Evaluate the pre-frozen epoch-100 R89 checkpoint on the sealed holdout.

This is a post-training reporting tool.  It never selects a checkpoint and it
refuses to open the holdout unless the checkpoint and holdout hashes match the
pre-registered freeze record.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import torch
from torch.utils.data import DataLoader


ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "reports" / "final_validation" / "checkpoint_freeze.json"
HOLDOUT = ROOT / "data" / "r89_locked_holdout"
TRAINER_PATH = ROOT / "training" / "train_r89.py"
MODEL_PATH = ROOT / "model" / "r89_model.py"
OUTPUT_PATH = ROOT / "reports" / "final_validation" / "sealed_holdout_epoch100.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if freeze.get("status") != "frozen_before_holdout_access":
        raise RuntimeError("The final checkpoint was not frozen before holdout access")
    if not freeze.get("checkpoint_selection_from_holdout_forbidden"):
        raise RuntimeError("The holdout cannot be used for checkpoint selection")

    checkpoint_path = ROOT / freeze["checkpoint"]
    checkpoint_hash = sha256_file(checkpoint_path)
    if checkpoint_hash != freeze["checkpoint_sha256"]:
        raise RuntimeError("Frozen checkpoint hash mismatch")

    seal = json.loads((HOLDOUT / "SEALED.json").read_text(encoding="utf-8"))
    manifest_path = HOLDOUT / "manifest.json"
    if seal.get("status") != "sealed_unread_until_checkpoint_frozen":
        raise RuntimeError("Holdout seal status is invalid")
    if seal.get("training_access_allowed") or seal.get("checkpoint_selection_access_allowed"):
        raise RuntimeError("Holdout access policy is invalid")
    if sha256_file(manifest_path) != freeze["holdout_manifest_sha256"]:
        raise RuntimeError("Holdout manifest changed after sealing")
    if seal.get("content_sha256") != freeze["holdout_content_sha256"]:
        raise RuntimeError("Holdout content identity mismatch")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads((HOLDOUT / "audit.json").read_text(encoding="utf-8"))
    if not audit.get("passed") or not audit.get("full_array_hash_audit"):
        raise RuntimeError("Holdout audit is not valid")
    if int(manifest["scene_count"]) != int(freeze["holdout_scene_count"]):
        raise RuntimeError("Holdout scene count mismatch")
    if int(manifest["total_observations"]) != int(freeze["holdout_total_observations"]):
        raise RuntimeError("Holdout observation count mismatch")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True

    trainer = load_module("r89_posttraining_trainer", TRAINER_PATH)
    model_module = load_module("r89_posttraining_model", MODEL_PATH)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint.get("epoch", -1)) != int(freeze["checkpoint_epoch"]):
        raise RuntimeError("Checkpoint epoch mismatch")
    model = model_module.build_model(base=24).to(device)
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    model.eval().requires_grad_(False)

    patch_size, core_size = 768, 384
    dataset = trainer.R89SceneDataset(
        HOLDOUT,
        manifest,
        "locked_holdout",
        patch_size,
        core_size,
        0,
        all_observations=True,
    )
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=False,
    )
    started = time.perf_counter()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    metrics = trainer.evaluate(
        model,
        loader,
        device,
        patch_size,
        core_size,
        int(freeze["checkpoint_epoch"]),
        device.type == "cuda",
    )
    elapsed = time.perf_counter() - started
    peak_gib = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
    report = {
        "experiment_id": freeze["experiment_id"],
        "status": "complete",
        "reporting_only_no_checkpoint_selection": True,
        "checkpoint_epoch": freeze["checkpoint_epoch"],
        "checkpoint_sha256": checkpoint_hash,
        "holdout_manifest_sha256": freeze["holdout_manifest_sha256"],
        "holdout_content_sha256": freeze["holdout_content_sha256"],
        "holdout_audit_passed": True,
        "evaluated_at": datetime.now().isoformat(),
        "seconds": elapsed,
        "gpu_peak_gib": peak_gib,
        "metrics": metrics,
    }
    trainer.json_dump(OUTPUT_PATH, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
