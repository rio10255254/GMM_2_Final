"""Recorded throughput-only continuation of frozen R125 generator v2.

Only unfinished procedural scene IDs are generated. Completed artifacts are
validated against their stored array hashes and reused byte-for-byte. Any
incomplete file is moved to an explicit retained partial-artifact directory.
This coordinator never edits the generator, v1 artifacts, or admission rules.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data.generator_v2 import CATEGORIES, MODEL_FACTOR, RENDER_FACTOR, _array_hash, _file_hash, _json_write, generate_scene

PACKAGE = ROOT / "data" / "package_v2"
GENERATOR = ROOT / "data" / "generator_v2.py"


def entry_for(index: int) -> dict:
    path = PACKAGE / "scenes" / f"scene_{index:03d}.npz"
    meta_path = PACKAGE / "scenes" / f"scene_{index:03d}.metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return {"scene_id": meta["scene_id"], "index": index, "category": meta["category"],
            "parent_latent_id": meta["parent_latent_id"],
            "arrays_path": path.relative_to(PACKAGE).as_posix(),
            "metadata_path": meta_path.relative_to(PACKAGE).as_posix(),
            "sha256": {"arrays": _file_hash(path), "metadata": _file_hash(meta_path)}}


def validate_completed(index: int) -> dict:
    path = PACKAGE / "scenes" / f"scene_{index:03d}.npz"
    meta_path = PACKAGE / "scenes" / f"scene_{index:03d}.metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["index"] != index or meta["category"] != CATEGORIES[index] or not meta["admission"]["passed"]:
        raise ValueError("Scene identity/category/admission mismatch")
    expected_names = {"source", "target", "latent_target", "sdf", "boundary", "noiseless"}
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != expected_names:
            raise ValueError("Array members differ")
        for key in expected_names:
            array = data[key]
            expected_shape = (2, 2560, 2560) if key == "latent_target" else (2, 640, 640)
            expected_dtype = np.uint8 if key == "source" else np.float32
            if array.shape != expected_shape or array.dtype != expected_dtype or not np.isfinite(array).all():
                raise ValueError(f"Invalid {key} shape/dtype/values")
            if _array_hash(array) != meta["array_sha256"][key]:
                raise ValueError(f"Stored array hash differs: {key}")
            if key == "source":
                if [_array_hash(array[view]) for view in range(2)] != meta["source_original_sha256"]:
                    raise ValueError("Original source hashes differ")
                core = array[:, 256:384, 256:384]
                if ((core == 0) | (core == 255)).any():
                    raise ValueError("Source core is saturated")
    return entry_for(index)


def preserve_partial(index: int, reason: str) -> list[dict]:
    retained = PACKAGE / "failed_partial"
    retained.mkdir(exist_ok=True)
    base = PACKAGE.resolve()
    records = []
    for suffix in ("npz", "metadata.json"):
        source = PACKAGE / "scenes" / f"scene_{index:03d}.{suffix}"
        if not source.exists():
            continue
        target = retained / source.name
        if not source.resolve().is_relative_to(base) or not target.resolve().is_relative_to(base):
            raise ValueError("Partial artifact move would leave exact package workspace")
        if target.exists():
            raise FileExistsError(target)
        record = {"source": str(source), "retained_as": str(target), "sha256": _file_hash(source),
                  "bytes": source.stat().st_size, "reason": reason}
        source.rename(target)
        records.append(record)
    return records


def write_scene(index: int, frozen_hash: str) -> dict:
    if _file_hash(GENERATOR) != frozen_hash:
        raise RuntimeError("Generator source changed; no scene will be generated")
    arrays, metadata = generate_scene(index)
    path = PACKAGE / "scenes" / f"scene_{index:03d}.npz"
    meta_path = PACKAGE / "scenes" / f"scene_{index:03d}.metadata.json"
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    _json_write(meta_path, metadata)
    return entry_for(index)


def main() -> None:
    started_at = time.time()
    if (PACKAGE / "manifest.json").exists():
        raise FileExistsError("Completed package manifest already exists")
    initial = json.loads((PACKAGE / "generation_started.json").read_text(encoding="utf-8"))
    frozen_hash = initial["generator_sha256"]
    if _file_hash(GENERATOR) != frozen_hash:
        raise RuntimeError("Frozen source changed since original generation start")
    entries = {}
    partials = []
    missing = []
    for index in range(64):
        path = PACKAGE / "scenes" / f"scene_{index:03d}.npz"
        meta_path = PACKAGE / "scenes" / f"scene_{index:03d}.metadata.json"
        if path.exists() and meta_path.exists():
            # A completed hash mismatch is not auto-repaired or accepted.
            entries[index] = validate_completed(index)
        elif path.exists() or meta_path.exists():
            partials.extend(preserve_partial(index, "incomplete_when_known_single_worker_was_stopped_for_throughput"))
            missing.append(index)
        else:
            missing.append(index)
    reused = list(entries.values())
    _json_write(PACKAGE / "resume_started.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "reason": "throughput_only_two_workers",
        "data_failure": False, "workers": 2, "generator_sha256": frozen_hash,
        "coordinator_sha256": _file_hash(Path(__file__)), "reused_completed_entries": reused,
        "remaining_ids": missing, "retained_partial_artifacts": partials,
    })
    print(json.dumps({"resume_reused": len(reused), "remaining": len(missing), "workers": 2}), flush=True)
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(write_scene, index, frozen_hash): index for index in missing}
        for future in as_completed(futures):
            index = futures[future]
            entries[index] = future.result()
            print(json.dumps({"scene_id": index, "total_complete": len(entries), "count": 64,
                              "category": entries[index]["category"]}), flush=True)
    if _file_hash(GENERATOR) != frozen_hash:
        raise RuntimeError("Frozen generator changed before completion")
    for entry in entries.values():
        for label, field in (("arrays", "arrays_path"), ("metadata", "metadata_path")):
            if _file_hash(PACKAGE / entry[field]) != entry["sha256"][label]:
                raise RuntimeError(f"Completed artifact changed during continuation: {entry['scene_id']} {label}")
    ordered = [entries[index] for index in range(64)]
    manifest = {
        "schema_version": 2, "render_version": "v2_float64_8x_physical_to_4x_optical_state",
        "latent_sampling_factor": MODEL_FACTOR, "render_sampling_factor": RENDER_FACTOR,
        "status": "generated_not_model_or_real_world_validation", "scene_count": 64,
        "views_per_scene": 2, "native_size": 640, "supervised_size": 128, "context_native_px": 256,
        "category_counts": dict(Counter(entry["category"] for entry in ordered)),
        "scene_order": "deterministically_interleaved_categories", "source_kind": "new_procedural_only",
        "external_training_inputs": [], "generator_path": str(GENERATOR.resolve()),
        "generator_sha256": frozen_hash, "continuation_record": "resume_started.json", "scenes": ordered,
    }
    _json_write(PACKAGE / "manifest.json", manifest)
    _json_write(PACKAGE / "resume_finished.json", {
        "utc": datetime.now(timezone.utc).isoformat(), "scene_count": 64,
        "reused_completed_count": len(reused), "new_completed_count": len(missing),
        "all_completed_file_hashes_unchanged": True, "generator_sha256": frozen_hash,
        "elapsed_seconds": time.time() - started_at,
    })
    print(json.dumps({"complete": 64, "seconds": time.time() - started_at}), flush=True)


if __name__ == "__main__":
    main()
