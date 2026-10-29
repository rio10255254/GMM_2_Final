"""Reconstruct the fixed 100-image R74 hard-microscopy suite with R92 E80."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260812.json"
INFERENCE = ROOT / "inference" / "reconstruct.py"
R74_CONFIG = Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/config/experiment.json'))
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


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    arm = protocol["arms"]["hard_microscopy"]
    dataset_manifest_path = Path(PROJECT_ROOT / arm["manifest"])
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    records = dataset_manifest["records"]
    if len(records) != int(arm["expected_images"]):
        raise RuntimeError("Hard-microscopy population mismatch")
    if sorted({row["family"] for row in records}) != sorted(arm["challenge_families"]):
        raise RuntimeError("Hard-microscopy family mismatch")

    checkpoint = Path(PROJECT_ROOT / protocol["checkpoint_root"]) / f"epoch_{EPOCH:03d}.pth.tar"
    if sha256_file(checkpoint) != str(protocol["checkpoint_sha256"]).lower():
        raise RuntimeError("Checkpoint hash mismatch")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    device = torch.device("cuda:0")
    free_before, total_memory = torch.cuda.mem_get_info(device)
    if free_before < 7 * 2**30:
        raise RuntimeError(f"Only {free_before / 2**30:.2f} GiB GPU memory is free")
    inference = load_module("r92_hard_microscopy_inference", INFERENCE)
    model, payload = inference.load_model(checkpoint, device)
    if int(payload.get("epoch", -1)) != EPOCH:
        raise RuntimeError("Checkpoint epoch mismatch")

    results = Path(PROJECT_ROOT / protocol["output_root"]) / "hard_microscopy"
    reconstruction_root = results / "reconstructions_fp32" / "E080"
    output_dirs: dict[str, str] = {}
    inventory: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, row in enumerate(records, start=1):
        source = Path(row["src"])
        truth = Path(row["mask"])
        if not source.is_file() or not truth.is_file():
            raise FileNotFoundError(source if not source.is_file() else truth)
        family_dir = reconstruction_root / str(row["stage"])
        destination = family_dir / str(row["filename"])
        output_dirs[str(row["family"])] = str(family_dir)
        raw, dtype = inference.read_gray(source)
        prediction = inference.reconstruct_tensor(
            model,
            inference.image_tensor(raw, device),
            core_size=512,
            halo=192,
            tile_batch=1,
            amp=False,
        )
        output = inference.output_array(prediction, dtype)
        inference.write_image(destination, output)
        inventory.append({
            "image_id": row["image_id"],
            "family": row["family"],
            "shape_family": row["shape_family"],
            "source": str(source),
            "source_sha256": sha256_file(source),
            "truth_mask": str(truth),
            "truth_mask_sha256": sha256_file(truth),
            "output": str(destination),
            "output_sha256": sha256_file(destination),
        })
        if index % 10 == 0 or index == len(records):
            print(json.dumps({"completed": index, "total": len(records), "family": row["family"]}), flush=True)

    runner = results / "matlab_runner"
    runner_config = json.loads(R74_CONFIG.read_text(encoding="utf-8"))
    runner_config["experiment_id"] = "R92_E80_HardMicroscopy_ACM"
    runner_config["created_date"] = "2026-08-12"
    runner_config["scientific_question"] = "Does locked R92 E80 improve exact contours on the frozen R74 hard-microscopy population?"
    runner_config["model"] = {
        "name": "R92_E80",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "weight_source": "ema_state_dict",
        "precision": "fp32",
    }
    runner_config["pipeline"]["output_prefix"] = "r92_e80_fp32_r74"
    runner_config["statistics"]["random_seed"] = 920041
    write_json(runner / "config" / "experiment.json", runner_config)
    write_json(runner / "results" / "inference_manifest.json", {
        "experiment_id": runner_config["experiment_id"],
        "actual_model": "R92_E80",
        "legacy_matlab_method_label": "R61v16",
        "method_label_alias": {"R61v16": "R92_E80"},
        "output_dirs": output_dirs,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "dataset_manifest": str(dataset_manifest_path),
        "dataset_manifest_sha256": sha256_file(dataset_manifest_path),
        "records": inventory,
    })
    write_json(results / "reconstruction_state.json", {
        "status": "reconstruction_complete_matlab_pending",
        "protocol_id": protocol["protocol_id"],
        "images": len(inventory),
        "families": output_dirs,
        "elapsed_seconds": time.perf_counter() - started,
        "runner_root": str(runner),
        "matlab_script": str(Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/scripts/run_acm_extraction.m'))),
    })
    print(json.dumps({"status": "reconstruction_complete_matlab_pending", "images": len(inventory), "runner_root": str(runner)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
