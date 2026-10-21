"""Write one compact R75-v2 pre-training readiness record."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "r75v2_formal_diverse_primitives"
REPORTS = ROOT / "reports"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    audit = read_json(PACKAGE / "source_audit.json")
    manifest = read_json(PACKAGE / "manifest.json")
    architecture = read_json(REPORTS / "architecture_audit_formal.json")
    smoke = read_json(REPORTS / "smoke_pipeline_verification.json")
    tests = read_json(REPORTS / "unit_test_verification.json")
    files = [path for path in PACKAGE.rglob("*") if path.is_file()]
    size_bytes = sum(path.stat().st_size for path in files)
    payload = {
        "passed": bool(
            audit["passed"]
            and architecture["passed"]
            and smoke["passed"]
            and tests["passed"]
        ),
        "experiment_id": manifest["experiment_id"],
        "status": "ready_for_formal_training",
        "formal_dataset": {
            "package": str(PACKAGE),
            "total_pairs": audit["total_pairs"],
            "geometry_count": audit["geometry_count"],
            "split_counts": audit["split_counts"],
            "training_role_counts": audit["training_role_counts"],
            "identity_mode_counts": audit["identity_mode_counts"],
            "dark_object_dark_background_count": audit[
                "dark_object_dark_background_count"
            ],
            "very_low_contrast_count": audit["very_low_contrast_count"],
            "source_mean_distribution": audit["source_mean_distribution"],
            "source_std_distribution": audit["source_std_distribution"],
            "source_clipped_fraction_distribution": audit[
                "source_clipped_fraction_distribution"
            ],
            "geometry_split_overlap_count": audit["geometry_split_overlap_count"],
            "real_image_pixels_used": audit["real_image_pixels_used"],
            "measured_shape_templates_used": audit[
                "measured_shape_templates_used"
            ],
            "pseudo_labels_used": audit["pseudo_labels_used"],
            "content_sha256": manifest["content_sha256"],
            "manifest_sha256": sha256(PACKAGE / "manifest.json"),
            "file_count": len(files),
            "size_bytes": size_bytes,
            "size_gib": round(size_bytes / (1024**3), 3),
        },
        "architecture": {
            "passed": architecture["passed"],
            "class_name": architecture["class_name"],
            "parameter_count": architecture["parameter_count"],
            "trainable_parameter_count": architecture[
                "trainable_parameter_count"
            ],
            "checkpoint_loaded": architecture["checkpoint_loaded"],
            "teacher_loaded": architecture["teacher_loaded"],
            "boundary_adapter_max_residual": architecture[
                "boundary_adapter_max_residual"
            ],
            "architecture_source_sha256": architecture[
                "architecture_source_sha256"
            ],
        },
        "smoke_pipeline": smoke,
        "unit_tests": tests,
        "formal_training_settings": {
            "epochs": 100,
            "seed": 752031,
            "batch_size": 8,
            "learning_rate": 0.00002,
            "amp_enabled": False,
            "live_validation_every_n_epochs": 5,
        },
    }
    target = REPORTS / "package_readiness.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(target), "passed": payload["passed"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
