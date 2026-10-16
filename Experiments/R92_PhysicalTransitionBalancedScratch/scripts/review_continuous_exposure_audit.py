"""Reconcile the legacy fixed-window exposure check with R92's continuous path.

This script never edits image arrays or manifest records.  It is intentionally
separate from the frozen generator so the pre-formal implementation hash stays
unchanged.  A correction is allowed only when the original full audit has no
failure other than bundles that miss the obsolete fixed mid-exposure window,
and every such bundle satisfies the declared continuous-path contract.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIRS = {
    "formal": ROOT / "data" / "r92_formal",
    "holdout": ROOT / "data" / "r92_locked_holdout",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def evaluate_bundle(record: dict[str, Any], config: dict[str, Any]) -> tuple[list[str], bool]:
    observations = record["observations"]
    families = {str(row["degradation_family"]) for row in observations}
    parameter_seeds = {int(row["degradation_parameter_seed"]) for row in observations}
    noise_seeds = {int(row["independent_noise_seed"]) for row in observations}
    by_label = {
        str(row["degradation"].get("exposure_coherent_profile")): row["degradation"]
        for row in observations
    }
    expected_labels = [str(label) for label in config["labels"]]
    reasons: list[str] = []
    if len(observations) != 4:
        reasons.append("observation_count")
    if len(families) != 1:
        reasons.append("shared_degradation_family")
    if len(parameter_seeds) != 1:
        reasons.append("shared_optical_parameters")
    if len(noise_seeds) != 4:
        reasons.append("independent_noise")
    if set(by_label) != set(expected_labels):
        reasons.append("profile_labels")
        return reasons, False

    ordered = [by_label[label] for label in expected_labels]
    positions = [float(row.get("exposure_path_position", -1.0)) for row in ordered]
    exposures = [float(row.get("exposure", 1.0)) for row in ordered]
    gammas = [float(row.get("gamma", 1.0)) for row in ordered]
    inner_ranges = config["inner_path_position_ranges"]
    if abs(positions[0]) > 1e-12 or abs(positions[-1] - 1.0) > 1e-12:
        reasons.append("path_endpoints")
    for position, bounds in zip(positions[1:-1], inner_ranges):
        if not float(bounds[0]) <= position <= float(bounds[1]):
            reasons.append("inner_path_position")
    if not all(left < right for left, right in zip(positions, positions[1:])):
        reasons.append("path_position_order")
    if max(exposures) - min(exposures) < float(config["minimum_exposure_span"]):
        reasons.append("exposure_span")
    if not (min(exposures) < 1.0 < max(exposures)):
        reasons.append("nominal_exposure_bracketing")
    if not all(left < right for left, right in zip(exposures, exposures[1:])):
        reasons.append("exposure_order")
    if not all(left > right for left, right in zip(gammas, gammas[1:])):
        reasons.append("gamma_order")

    legacy_window_hit = any(0.82 <= value <= 1.16 for value in exposures)
    return sorted(set(reasons)), legacy_window_hit


def reconcile(profile: str) -> dict[str, Any]:
    package = PROFILE_DIRS[profile]
    manifest_path = package / "manifest.json"
    audit_path = package / "audit.json"
    legacy_path = package / "audit_legacy_fixed_window.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError(f"Dataset package is incomplete: {package}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    if not legacy_path.exists():
        shutil.copy2(audit_path, legacy_path)
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))

    required_zero = (
        "missing_count",
        "shape_failure_count",
        "hash_failure_count",
        "scene_split_overlap_count",
        "motion_pair_failure_count",
        "generator_record_failure_count",
        "recoverability_failure_count",
        "recoverability_metadata_failure_count",
    )
    non_exposure_failures = {key: int(legacy.get(key, -1)) for key in required_zero if int(legacy.get(key, -1)) != 0}
    if non_exposure_failures:
        raise RuntimeError(f"Refusing correction because other audit failures exist: {non_exposure_failures}")
    if not bool(legacy.get("full_array_hash_audit")):
        raise RuntimeError("Refusing correction without a full array hash audit")
    if not bool(legacy.get("source_isolation_pass")) or not bool(legacy.get("generator_hash_pass")):
        raise RuntimeError("Refusing correction because source isolation or generator integrity failed")
    if str(legacy.get("content_sha256")) != str(manifest.get("content_sha256")):
        raise RuntimeError("Refusing correction because audit and manifest content hashes disagree")

    continuous_failures: list[dict[str, Any]] = []
    legacy_window_misses: list[str] = []
    bundle_count = 0
    exposure_config = design["dataset"]["continuous_exposure_path"]
    for record in manifest["records"]:
        if record["role"] != "exposure_coherent_bundle":
            continue
        bundle_count += 1
        reasons, legacy_window_hit = evaluate_bundle(record, exposure_config)
        if reasons:
            continuous_failures.append({"scene_id": record["scene_id"], "reasons": reasons})
        if not legacy_window_hit:
            legacy_window_misses.append(str(record["scene_id"]))

    legacy_failure_count = int(legacy.get("exposure_bundle_failure_count", -1))
    if legacy_failure_count != len(legacy_window_misses):
        raise RuntimeError(
            "Refusing correction because legacy failures are not explained exactly by the fixed exposure window: "
            f"reported={legacy_failure_count}, reproduced={len(legacy_window_misses)}"
        )
    if continuous_failures:
        raise RuntimeError(f"Continuous-path audit failed: {continuous_failures[:8]}")

    corrected = dict(legacy)
    corrected.update(
        passed=True,
        exposure_bundle_failure_count=0,
        exposure_audit_policy="continuous_path_contract_v2",
        exposure_bundle_count=bundle_count,
        continuous_path_failure_count=0,
        legacy_fixed_window_miss_count=len(legacy_window_misses),
        legacy_fixed_window_miss_scene_ids=legacy_window_misses,
        original_audit_sha256=sha256_file(legacy_path),
        arrays_or_manifest_modified=False,
        reconciled_at=datetime.now().isoformat(),
        reconciliation_script=str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
    )
    write_json(audit_path, corrected)

    report = {
        "passed": True,
        "profile": profile,
        "dataset_content_sha256": manifest["content_sha256"],
        "full_array_hash_audit": True,
        "bundle_count": bundle_count,
        "continuous_path_failure_count": 0,
        "legacy_fixed_window_miss_count": len(legacy_window_misses),
        "legacy_fixed_window_miss_scene_ids": legacy_window_misses,
        "arrays_or_manifest_modified": False,
        "legacy_audit": str(legacy_path),
        "corrected_audit": str(audit_path),
    }
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    write_json(reports / f"{profile}_continuous_exposure_audit_reconciliation.json", report)

    if profile == "holdout":
        seal = {
            "experiment_id": design["experiment_id"],
            "status": "sealed_unread_until_checkpoint_frozen",
            "sealed_at": datetime.now().isoformat(),
            "manifest_sha256": sha256_file(manifest_path),
            "content_sha256": manifest["content_sha256"],
            "scene_count": manifest["scene_count"],
            "total_observations": manifest["total_observations"],
            "audit_passed": True,
            "training_access_allowed": False,
            "checkpoint_selection_access_allowed": False,
            "exposure_audit_policy": "continuous_path_contract_v2",
        }
        write_json(package / "SEALED.json", seal)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILE_DIRS), required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.profile), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
