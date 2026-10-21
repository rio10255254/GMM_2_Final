"""Create the small R102 reference/audit package without copying 16.9 GiB."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
OUT = ROOT / "data"


def dump(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    package = Path(config["data"]["base_package"])
    manifest_path = package / "manifest.json"
    audit_path = package / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError("The verified procedural package is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if manifest.get("content_sha256") != config["data"]["base_content_sha256"]:
        raise RuntimeError("Base procedural package hash does not match the locked design")
    if not audit.get("passed") or not audit.get("source_isolation_pass") or not audit.get("full_array_hash_audit"):
        raise RuntimeError("Base procedural package audit is not valid")
    if int(manifest.get("scene_count", -1)) != int(config["data"]["scene_count"]):
        raise RuntimeError("Scene count changed")
    if int(manifest.get("total_observations", -1)) != int(config["data"]["observations"]):
        raise RuntimeError("Observation count changed")

    # Cheap live verification: hash a fixed set of arrays from every split.
    sample_rows = []
    for split in ("train", "validation", "internal_test"):
        rows = [row for row in manifest["records"] if row["split"] == split]
        for row in (rows[0], rows[len(rows) // 2], rows[-1]):
            for key, expected in (("target", row["target_sha256"]), ("mask", row["mask_sha256"])):
                path = package / row[key]
                array = np.load(path, mmap_mode="r", allow_pickle=False)
                actual = hashlib.sha256(memoryview(np.ascontiguousarray(array)).cast("B")).hexdigest()
                if actual != expected:
                    raise RuntimeError(f"Array hash mismatch: {path}")
                if array.shape != (1536, 1536) or array.dtype != np.uint8:
                    raise RuntimeError(f"Unexpected array contract: {path}")
                sample_rows.append({"split": split, "scene_id": row["scene_id"], "kind": key, "sha256": actual})

    validation = [row for row in manifest["records"] if row["split"] == "validation"]
    locked_validation = [
        {"scene_id": row["scene_id"], "scene_index": row["scene_index"], "role": row["role"]}
        for row in validation[:96]
    ]
    dump(OUT / "TRAINING_DATA_REFERENCE.json", {
        "schema_version": 1,
        "policy": "read_only_verified_reference_plus_deterministic_analytic_augmentation",
        "package": str(package),
        "content_sha256": manifest["content_sha256"],
        "scene_count": manifest["scene_count"],
        "observations": manifest["total_observations"],
        "label_supersample_factor": 8,
        "copied_payload_bytes": 0,
        "real_pixels_used_for_training": False,
        "sem_or_hs100mg_structure_used": False,
        "checkpoint_or_teacher_used": False,
    })
    dump(OUT / "locked_validation.json", {
        "schema_version": 1,
        "augmentation_seed": config["data"]["augmentation_seed"],
        "records": locked_validation,
    })
    dump(OUT / "source_audit.json", {
        "schema_version": 1,
        "passed": True,
        "created_at": datetime.now().isoformat(),
        "base_audit_passed": True,
        "base_full_array_hash_audit": True,
        "live_sample_hashes_passed": True,
        "live_sample_count": len(sample_rows),
        "live_samples": sample_rows,
        "source_isolation_pass": True,
        "procedural_only": True,
        "real_training_pixels": False,
        "checkpoints_or_teachers": False,
        "content_sha256": manifest["content_sha256"],
    })
    print(json.dumps({"passed": True, "sample_hashes": len(sample_rows), "validation_records": len(locked_validation)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
