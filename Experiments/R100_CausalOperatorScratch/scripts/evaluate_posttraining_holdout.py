"""Evaluate fixed R100 checkpoints on the untouched internal-test scene split."""
from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r100_model.py"
TRAINER_PATH = ROOT / "training" / "train_r100.py"
OUTPUT = ROOT / "results" / "posttraining_validation" / "internal_test"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r100_post_holdout_model", MODEL_PATH)
TRAINER = load_module("r100_post_holdout_trainer", TRAINER_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite internal-test output: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("locked_before_new_posttraining_outputs"):
        raise RuntimeError("Posttraining protocol is not locked")
    design = read_json(DESIGN_PATH)
    arm = protocol["internal_test_arm"]
    package = Path(PROJECT_ROOT / arm["source_package"])
    manifest_path = package / "manifest.json"
    audit_path = package / "audit.json"
    manifest = read_json(manifest_path)
    audit = read_json(audit_path)
    if not audit.get("passed") or manifest["content_sha256"] != design["dataset"]["source_content_sha256"]:
        raise RuntimeError("Locked procedural package audit or hash failed")

    device = torch.device(arm["device"] if torch.cuda.is_available() else "cpu")
    patch_size = int(arm["patch_size"])
    core_size = int(arm["core_size"])
    dataset = TRAINER.R100SceneDataset(
        package,
        manifest,
        str(arm["split"]),
        patch_size,
        core_size,
        0,
        all_observations=bool(arm["all_observations"]),
    )
    sampler = TRAINER.HomogeneousViewBatchSampler(dataset, batch_size=int(arm["scene_batch_size"]))
    loader = TRAINER.make_loader(dataset, sampler, 4, device.type == "cuda")
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for epoch in arm["checkpoints"]:
        checkpoint_path = Path(PROJECT_ROOT / protocol["diagnostic_checkpoints"][str(epoch)])
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if int(checkpoint["epoch"]) != int(epoch):
            raise RuntimeError(f"Checkpoint epoch mismatch: {checkpoint_path}")
        model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
        model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
        model.eval().to(device)
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        epoch_started = time.perf_counter()
        metrics = TRAINER.evaluate(
            model,
            loader,
            device,
            patch_size,
            core_size,
            int(epoch),
            False,
        )
        axes = TRAINER.validation_axes(metrics)
        elapsed = time.perf_counter() - epoch_started
        peak = torch.cuda.max_memory_allocated(device) / 2**30 if device.type == "cuda" else 0.0
        records.append({
            "epoch": int(epoch),
            "checkpoint": str(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "checkpoint_state": protocol["checkpoint_state"],
            "elapsed_seconds": elapsed,
            "gpu_peak_gib": peak,
            "axes": axes,
            "metrics": metrics,
        })
        print(json.dumps({"epoch": epoch, "axes": axes, "elapsed_seconds": elapsed}, ensure_ascii=False), flush=True)
        del checkpoint, model
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

    axes = ["detail", "contour", "identity", "motion", "exposure", "tile"]
    best_by_axis = {
        name: min(({"epoch": row["epoch"], "value": row["axes"][name]} for row in records), key=lambda item: item["value"])
        for name in axes
    }
    result = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "split": arm["split"],
        "unique_scene_count": int(design["dataset"]["split_counts"]["internal_test_scenes"]),
        "evaluation_case_count": len(dataset),
        "evaluated_checkpoints": [row["epoch"] for row in records],
        "primary_endpoint": int(protocol["primary_checkpoint_epoch"]),
        "primary_endpoint_remains_fixed": True,
        "dataset_manifest_sha256": sha256_file(manifest_path),
        "dataset_content_sha256": manifest["content_sha256"],
        "records": records,
        "best_by_axis_diagnostic_only": best_by_axis,
        "elapsed_seconds": time.perf_counter() - started,
        "notes": [
            "The internal-test scenes are disjoint from train and validation by scene ID.",
            "This is the existing 125-scene internal-test split, not the separately proposed 256-scene new-generator holdout.",
            "Epochs 32 and 36 are trajectory diagnostics; external results cannot replace the fixed Epoch 40 endpoint.",
        ],
    }
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps({"status": "complete", "unique_scene_count": int(design["dataset"]["split_counts"]["internal_test_scenes"]), "evaluation_case_count": len(dataset), "best_by_axis": best_by_axis}, indent=2), flush=True)


if __name__ == "__main__":
    main()
