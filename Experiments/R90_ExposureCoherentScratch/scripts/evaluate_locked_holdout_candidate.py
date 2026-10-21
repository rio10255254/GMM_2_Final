"""Evaluate a protocol-locked checkpoint on the sealed R90 holdout."""
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
PROTOCOL = ROOT / "reports" / "full_validation_epoch055" / "validation_protocol.json"
FREEZE = ROOT / "reports" / "full_validation_epoch055" / "checkpoint_freeze.json"
HOLDOUT = ROOT / "data" / "r90_locked_holdout"
TRAINER_PATH = ROOT / "training" / "train_r90.py"
OUTPUT_ROOT = ROOT / "reports" / "full_validation_epoch055"


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
    parser.add_argument("--label", choices=["R90E55", "R89E100"], required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if protocol.get("status") != "locked_before_new_full_validation_outputs":
        raise RuntimeError("Validation protocol is not locked")
    if freeze.get("status") != "frozen_before_holdout_access":
        raise RuntimeError("R90 checkpoint was not frozen before holdout access")
    if not freeze.get("checkpoint_selection_from_holdout_forbidden"):
        raise RuntimeError("Holdout must not select checkpoints")

    model_record = protocol["comparison_models"][args.label]
    checkpoint_path = Path(model_record["checkpoint"])
    model_path = Path(model_record["model_file"])
    if sha256_file(checkpoint_path) != model_record["checkpoint_sha256"]:
        raise RuntimeError("Checkpoint hash mismatch")
    if sha256_file(model_path) != model_record["model_file_sha256"]:
        raise RuntimeError("Model implementation hash mismatch")

    seal = json.loads((HOLDOUT / "SEALED.json").read_text(encoding="utf-8"))
    manifest_path = HOLDOUT / "manifest.json"
    holdout_record = protocol["sealed_synthetic_holdout"]
    if seal.get("status") != "sealed_unread_until_checkpoint_frozen":
        raise RuntimeError("Holdout seal is invalid")
    if seal.get("training_access_allowed") or seal.get("checkpoint_selection_access_allowed"):
        raise RuntimeError("Holdout access policy is invalid")
    if sha256_file(manifest_path) != holdout_record["manifest_sha256"]:
        raise RuntimeError("Holdout manifest hash mismatch")
    if seal.get("content_sha256") != holdout_record["content_sha256"]:
        raise RuntimeError("Holdout content identity mismatch")
    audit = json.loads((HOLDOUT / "audit.json").read_text(encoding="utf-8"))
    if not audit.get("passed") or not audit.get("full_array_hash_audit"):
        raise RuntimeError("Holdout audit failed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
    trainer = load_module("r90_locked_holdout_trainer", TRAINER_PATH)
    model_module = load_module(f"{args.label.lower()}_locked_model", model_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint.get("epoch", -1)) != int(model_record["checkpoint_epoch"]):
        raise RuntimeError("Checkpoint epoch mismatch")
    model = model_module.build_model(base=24).to(device)
    model.load_state_dict(checkpoint["ema_state_dict"], strict=True)
    model.eval().requires_grad_(False)

    patch_size, core_size = 768, 384
    dataset = trainer.R90SceneDataset(
        HOLDOUT, manifest, "locked_holdout", patch_size, core_size, 0,
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
        model, loader, device, patch_size, core_size,
        int(model_record["checkpoint_epoch"]), device.type == "cuda",
    )
    elapsed = time.perf_counter() - started
    peak_gib = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
    report = {
        "protocol_id": protocol["protocol_id"],
        "status": "complete",
        "label": args.label,
        "reporting_only_no_checkpoint_selection": True,
        "checkpoint_epoch": model_record["checkpoint_epoch"],
        "checkpoint_sha256": model_record["checkpoint_sha256"],
        "holdout_manifest_sha256": holdout_record["manifest_sha256"],
        "holdout_content_sha256": holdout_record["content_sha256"],
        "holdout_audit_passed": True,
        "evaluated_at": datetime.now().isoformat(),
        "seconds": elapsed,
        "gpu_peak_gib": peak_gib,
        "metrics": metrics,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_ROOT / f"sealed_holdout_{args.label.lower()}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
