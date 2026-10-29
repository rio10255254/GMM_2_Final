"""R119 setup checker. It never launches a trainer or evaluates a model."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT = Path(__file__).resolve().parents[1]
R118 = Path(str(PROJECT_ROOT / 'Experiments/R118_PhysicalCoordinateRepairScratch'))
PLAN_ID = "r118-next-single-image-sequence-geometry-v1"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check() -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    required_dirs = ["config", "model", "training", "inference", "validation", "scripts", "reports", "results", "tests", "runs/launcher_logs", "runs/probe", "runs/formal", "data"]
    for rel in required_dirs:
        if not (ROOT / rel).is_dir():
            errors.append(f"missing directory: {rel}")

    link = ROOT / "data/package"
    expected = R118 / "data/package"
    if not link.exists():
        errors.append("data/package reference is missing")
    else:
        try:
            resolved = link.resolve()
            if resolved != expected.resolve():
                errors.append(f"data/package points to {resolved}, expected {expected}")
        except OSError as exc:
            errors.append(f"cannot resolve data/package: {exc}")

    config_path = ROOT / "config/experiment.json"
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
        if cfg.get("experiment_id") != "R119_SequenceGeometryValidation":
            errors.append("experiment_id is not R119_SequenceGeometryValidation")
        if cfg.get("data", {}).get("package_root") != "data/package":
            errors.append("package_root must remain data/package")
        if cfg.get("provenance", {}).get("teacher_weights") is not False:
            errors.append("teacher weights must be false")
        if cfg.get("provenance", {}).get("real_pixels_in_training") is not False:
            errors.append("real pixels in training must be false")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid experiment config: {exc}")

    selected_path = ROOT / "config/selected_scene_ids.json"
    try:
        selected = json.loads(selected_path.read_text(encoding="utf-8-sig"))
        if selected.get("purpose") != "metadata_only_preselection_no_model_evaluation":
            errors.append("scene selection is not metadata-only")
        for key, count in (("probe_scene_ids", 512), ("development_bank_scene_ids", 48), ("short_sequence_enrichment_ids", 96), ("full_sequence_enrichment_ids", 960)):
            ids = selected.get(key, [])
            if len(ids) != count or len(ids) != len(set(ids)):
                errors.append(f"{key} has wrong count or duplicates")
        if not set(selected["short_sequence_enrichment_ids"]).issubset(selected["probe_scene_ids"]):
            errors.append("short enrichment is not nested in probe IDs")
        if not set(selected["short_sequence_enrichment_ids"]).issubset(selected["full_sequence_enrichment_ids"]):
            errors.append("short enrichment is not nested in full IDs")
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        errors.append(f"invalid selected scene IDs: {exc}")

    # These are the immutable R118 numerical sources. The R119 executor entry
    # and dataset policy are intentionally changed in P06 and are checked by
    # audit_executor.py instead of being compared to the old trainer.
    source_files = ["model/network.py", "model/ops.py", "training/dataset.py", "training/objectives.py", "inference/run.py", "validation/preflight.py"]
    source_hashes = {}
    for rel in source_files:
        path = ROOT / rel
        source_hashes[rel] = digest(path) if path.is_file() else None
        if source_hashes[rel] is None:
            errors.append(f"missing copied source: {rel}")
        elif (R118 / rel).is_file() and source_hashes[rel] != digest(R118 / rel):
            errors.append(f"copied source differs from R118: {rel}")

    raw_hashes = {}
    for path in sorted((ROOT / "validation/inputs/Raw").glob("*.bmp")):
        raw_hashes[path.name] = digest(path)
    if set(raw_hashes) != {"5x_dense_raw.bmp", "20x_mixed_raw.bmp", "50x_array_raw.bmp", "pillar_center9_50x_raw.bmp"}:
        errors.append("Raw preview inventory is incomplete")
    if not (ROOT / "training/train_r119.py").is_file() or not (ROOT / "training/train.py").is_file():
        errors.append("R119 executor source/entry is missing")

    package_manifest = R118 / "data/package/manifest.json"
    try:
        records = json.loads(package_manifest.read_text(encoding="utf-8-sig"))["records"]
        counts = {split: sum(r.get("split") == split for r in records) for split in ("train", "validation")}
        if counts != {"train": 5000, "validation": 512}:
            errors.append(f"base counts changed: {counts}")
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        errors.append(f"base manifest unavailable: {exc}")
        counts = {}

    # The active marker is checked, never removed. At setup it must not identify R119.
    active = ROOT / "runs/launcher_logs/active_formal_run.json"
    if active.exists():
        try:
            marker = json.loads(active.read_text(encoding="utf-8-sig"))
            if marker.get("status") == "running":
                warnings.append("a formal trainer is marked running; inspect its run identity before any launch")
            elif marker.get("status") != "complete":
                warnings.append("formal marker is not complete; inspect its run identity before any launch")
        except (OSError, json.JSONDecodeError):
            errors.append("formal marker is not valid JSON")
    selected = ROOT / "results/design_decision.json"
    if selected.exists():
        warnings.append("a design decision already exists; do not overwrite it")
    return {
        "schema_version": 1,
        "status": "pass" if not errors else "blocked",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "plan_id": PLAN_ID,
        "root": str(ROOT),
        "errors": errors,
        "warnings": warnings,
        "source_hashes": source_hashes,
        "raw_hashes": raw_hashes,
        "base_counts": counts,
        "training_started": (ROOT / "runs/formal").exists() and any((ROOT / "runs/formal").iterdir()),
        "meaning": "R119 setup integrity only; no model was evaluated or trained.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="read-only setup check (default)")
    parser.add_argument("--output", type=Path, help="optional new receipt path; never overwrites")
    args = parser.parse_args()
    result = check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.output:
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
