"""Audit the completed R116 chain and select non-aggregated validation candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
PARENT = ROOT / "runs" / "r116_formal_scratch_20260903_202052"
CONTINUATION = ROOT / "runs" / "r116_calibration_from_e42_20260903_235500"
OUTPUT = ROOT / "results" / "detailed_validation" / "00_audit"
CLASSES = tuple(CONFIG["validation_plan"]["classes"])
SHORTLIST = (24, 28, 40, 42, 48)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validation_path(epoch: int) -> Path:
    root = PARENT if epoch <= 42 else CONTINUATION
    return root / "validation" / f"epoch_{epoch:03d}.json"


def checkpoint_path(epoch: int) -> Path:
    if epoch == 42:
        return PARENT / "failure_snapshot.pth"
    root = PARENT if epoch <= 40 else CONTINUATION
    return root / "weights" / f"epoch_{epoch:03d}.pth"


def load_history() -> list[dict[str, Any]]:
    chain = json.loads((CONTINUATION / "complete_chain_history.json").read_text(encoding="utf-8"))
    if [int(row["epoch"]) for row in chain] != list(range(1, 49)):
        raise RuntimeError("Training chain is not exactly epochs 1 through 48")
    return chain


def audit_data() -> dict[str, Any]:
    package = ROOT / CONFIG["data"]["package_root"]
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest["records"]
    scene_indices = [int(row["scene_index"]) for row in records]
    scene_ids = [str(row["scene_id"]) for row in records]
    referenced = []
    missing = []
    for row in records:
        for key in ("target", "mask", "sdf"):
            path = package / row[key]
            referenced.append(path)
            if not path.is_file() or path.stat().st_size <= 0:
                missing.append(str(path))
    selected_indices = {0, len(records) - 1}
    seen_groups: set[tuple[str, str, str]] = set()
    for index, row in enumerate(records):
        key = (str(row["split"]), str(row["role"]), str(row["family"]))
        if key not in seen_groups:
            selected_indices.add(index)
            seen_groups.add(key)
    stride = max(1, len(records) // 128)
    selected_indices.update(range(0, len(records), stride))
    array_checks = []
    antialiased_targets = 0
    for index in sorted(selected_indices):
        row = records[index]
        arrays = {key: np.load(package / row[key]) for key in ("target", "mask", "sdf")}
        target = arrays["target"]
        if np.unique(target).size > 2:
            antialiased_targets += 1
        array_checks.append({
            "scene_index": int(row["scene_index"]),
            "split": row["split"],
            "role": row["role"],
            "family": row["family"],
            "shapes_valid": all(tuple(value.shape) == (256, 256) for value in arrays.values()),
            "finite": all(bool(np.isfinite(value).all()) for value in arrays.values()),
            "target_range_valid": int(target.min()) >= 0 and int(target.max()) <= 255,
            "mask_range_valid": int(arrays["mask"].min()) >= 0 and int(arrays["mask"].max()) <= 255,
        })
    text = json.dumps(manifest).lower()
    forbidden_tokens = ("sem_data", "hs100mg", "20260702_100mg", "20260704_5x", "20260704_20x")
    return {
        "manifest": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "manifest_hash_matches_config": sha256(manifest_path) == CONFIG["data"]["source_manifest_sha256"],
        "records": len(records),
        "train_records": sum(row["split"] == "train" for row in records),
        "validation_records": sum(row["split"] == "validation" for row in records),
        "unique_scene_indices": len(set(scene_indices)),
        "unique_scene_ids": len(set(scene_ids)),
        "duplicate_scene_indices": len(scene_indices) - len(set(scene_indices)),
        "duplicate_scene_ids": len(scene_ids) - len(set(scene_ids)),
        "referenced_arrays": len(referenced),
        "missing_or_empty_arrays": missing,
        "group_overlap_count": int(manifest["group_overlap_count"]),
        "training_uses_real_pixels": bool(manifest["training_uses_real_pixels"]),
        "forbidden_real_source_tokens_present": [token for token in forbidden_tokens if token in text],
        "canvas_size": int(manifest["canvas_size"]),
        "supersample_factor": int(manifest["supersample_factor"]),
        "sampled_array_records": len(array_checks),
        "sampled_array_checks_pass": all(
            row["shapes_valid"] and row["finite"] and row["target_range_valid"] and row["mask_range_valid"]
            for row in array_checks
        ),
        "sampled_antialiased_target_records": antialiased_targets,
    }


def audit_validations() -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    paths = sorted((PARENT / "validation").glob("epoch_*.json")) + sorted(
        (CONTINUATION / "validation").glob("epoch_*.json")
    )
    values: dict[int, dict[str, Any]] = {}
    baseline_reference: dict[str, tuple[float, float, float]] = {}
    baseline_max_delta = 0.0
    issues = []
    for path in paths:
        epoch = int(path.stem.split("_")[-1])
        payload = json.loads(path.read_text(encoding="utf-8"))
        values[epoch] = payload
        if tuple(payload["classes"].keys()) != CLASSES:
            issues.append(f"epoch {epoch}: class order/population mismatch")
        for name, row in payload["classes"].items():
            numeric = [value for value in row.values() if isinstance(value, (int, float))]
            if not all(math.isfinite(float(value)) for value in numeric):
                issues.append(f"epoch {epoch} {name}: non-finite metric")
            if int(row["samples"]) != 96:
                issues.append(f"epoch {epoch} {name}: samples={row['samples']}")
            baseline = (
                float(row["raw_mae"]), float(row["raw_contour_dice"]),
                float(row["raw_centroid_error"]),
            )
            if name not in baseline_reference:
                baseline_reference[name] = baseline
            baseline_max_delta = max(
                baseline_max_delta,
                max(abs(left - right) for left, right in zip(baseline, baseline_reference[name])),
            )
    expected_epochs = list(range(2, 43, 2)) + list(range(43, 49))
    return ({
        "validation_files": len(paths),
        "epochs": sorted(values),
        "expected_epochs": expected_epochs,
        "expected_epochs_present": sorted(values) == expected_epochs,
        "classes": list(CLASSES),
        "samples_per_class_per_epoch": 96,
        "raw_baseline_max_absolute_delta_across_epochs": baseline_max_delta,
        "raw_baseline_exactly_stable": baseline_max_delta == 0.0,
        "issues": issues,
    }, values)


def audit_checkpoints() -> dict[str, Any]:
    rows = []
    for epoch in SHORTLIST:
        path = checkpoint_path(epoch)
        saved = torch.load(path, map_location="cpu", weights_only=False)
        state = saved["model"]
        rows.append({
            "epoch": epoch,
            "path": str(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "state_tensors": len(state),
            "all_parameters_finite": all(bool(torch.isfinite(value).all()) for value in state.values()),
            "scratch": saved.get("scratch") is True,
            "other_model_weights_loaded": saved.get("other_model_weights_loaded", False),
        })
    return {"shortlist": rows, "all_pass": all(
        row["all_parameters_finite"] and row["scratch"] and not row["other_model_weights_loaded"]
        for row in rows
    )}


def candidate_rows(validations: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for epoch in SHORTLIST:
        payload = validations[epoch]
        rows.append({
            "epoch": epoch,
            "role": {
                24: "geometry-centroid",
                28: "geometry-balanced",
                40: "detail-checkpoint",
                42: "detail-end-snapshot",
                48: "calibrated-final",
            }[epoch],
            "checkpoint": str(checkpoint_path(epoch)),
            "worst_contour_gain": float(payload["worst_degraded_contour_gain"]),
            "worst_centroid_gain": float(payload["worst_degraded_centroid_gain"]),
            "mean_mae_gain": float(payload["mean_degraded_mae_gain"]),
            "identity_change": float(payload["identity_change"]),
            "flat_change": float(payload["flat_change"]),
            "mean_normal_shift_abs": float(payload["mean_normal_shift_abs"]),
            "mean_detail_abs": float(payload["mean_detail_abs"]),
        })
    maximize = ("worst_contour_gain", "worst_centroid_gain", "mean_mae_gain")
    minimize = ("identity_change", "flat_change")
    for candidate in rows:
        dominated = False
        for other in rows:
            if other is candidate:
                continue
            no_worse = all(other[key] >= candidate[key] for key in maximize) and all(
                other[key] <= candidate[key] for key in minimize
            )
            strictly_better = any(other[key] > candidate[key] for key in maximize) or any(
                other[key] < candidate[key] for key in minimize
            )
            if no_worse and strictly_better:
                dominated = True
                break
        candidate["pareto_nondominated"] = not dominated
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    history = load_history()
    data = audit_data()
    validation_audit, validations = audit_validations()
    checkpoints = audit_checkpoints()
    candidates = candidate_rows(validations)
    data_pass = all((
        data["manifest_hash_matches_config"], data["records"] == 5512,
        data["train_records"] == 5000, data["validation_records"] == 512,
        data["duplicate_scene_indices"] == 0, data["duplicate_scene_ids"] == 0,
        not data["missing_or_empty_arrays"], data["group_overlap_count"] == 0,
        not data["training_uses_real_pixels"], not data["forbidden_real_source_tokens_present"],
        data["canvas_size"] == 256, data["supersample_factor"] == 8,
        data["sampled_array_checks_pass"], data["sampled_antialiased_target_records"] > 0,
    ))
    validation_pass = (
        validation_audit["expected_epochs_present"]
        and validation_audit["raw_baseline_exactly_stable"]
        and not validation_audit["issues"]
    )
    result = {
        "status": "passed" if data_pass and validation_pass and checkpoints["all_pass"] else "failed",
        "as_of_local": "2026-09-04",
        "question": "Which completed R116 checkpoints deserve expensive physical validation?",
        "training_chain": {
            "epochs": len(history),
            "epoch_sequence_exact": [int(row["epoch"]) for row in history] == list(range(1, 49)),
            "parent": str(PARENT),
            "continuation": str(CONTINUATION),
        },
        "data_quality": {**data, "pass": data_pass},
        "validation_quality": {**validation_audit, "pass": validation_pass},
        "checkpoint_quality": checkpoints,
        "shortlist": candidates,
        "selection_policy": {
            "single_aggregate_score_used": False,
            "roles_preserved": True,
            "expensive_validation_shortlist": list(SHORTLIST),
            "reason": "E24/E28 preserve geometry, E40/E42 expose detail tradeoffs, and E48 tests whether calibration repairs them."
        },
        "claim_boundary": "This audit verifies comparability and selects candidates; it does not establish ACM, real-motion, SEM, tile, or external-GMF superiority."
    }
    (OUTPUT / "audit.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    write_csv(OUTPUT / "candidate_metrics.csv", candidates)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
