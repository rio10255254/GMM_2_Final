"""Deterministically repair only failed R93 formal exposure bundles.

The formal generator deliberately fails closed.  If a small number of
exposure bundles miss an already-declared recoverability, contrast, or span
contract, this tool re-renders only those complete four-view bundles using the
same degradation family.  Clean targets, masks, geometry, scene membership,
splits, and every passing scene remain unchanged.

The first deterministic candidate satisfying the predeclared contracts is
accepted.  Original observation arrays and metadata are backed up before any
replacement, then the complete 5,000-observation package is re-hashed and
fully audited.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

import generate_dataset as gen


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "r93_formal"
REPORT_ROOT = ROOT / "reports" / "formal_data_local_repair"
MAX_ATTEMPTS = int(gen.DESIGN["dataset"]["recoverability_contract"]["maximum_same_family_rerender_attempts"])
SEED_STRIDE = int(gen.DESIGN["dataset"]["recoverability_contract"]["same_family_parameter_seed_stride"])
NOISE_STRIDE = int(gen.DESIGN["dataset"]["recoverability_contract"]["same_family_noise_seed_stride"])


def _sha256_bytes(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_contract_failure(source: np.ndarray, shifted_target: np.ndarray) -> bool:
    cfg = gen.DESIGN["dataset"]["recoverability_contract"]
    gap = np.abs(source.astype(np.float32) - shifted_target.astype(np.float32)) / 255.0
    robust = float(np.percentile(gap, float(cfg["robust_gap_percentile"])))
    fraction = float(np.mean(gap > float(cfg["maximum_source_target_gap"])))
    allowed = float(cfg["maximum_source_target_gap"]) + 1.5 / 255.0
    return robust > allowed or fraction > float(cfg["maximum_fraction_above_model_bound"]) + 1e-9


def _exposure_bundle_failure(record: dict[str, Any]) -> bool:
    cfg = gen.DESIGN["dataset"]["continuous_exposure_path"]
    observations = record["observations"]
    families = {str(obs["degradation_family"]) for obs in observations}
    parameter_seeds = {int(obs["degradation_parameter_seed"]) for obs in observations}
    noise_seeds = {int(obs["independent_noise_seed"]) for obs in observations}
    labels = {str(obs["degradation"].get("exposure_coherent_profile")) for obs in observations}
    expected_labels = {str(label) for label in cfg["labels"]}
    exposures = [float(obs["degradation"].get("exposure", 1.0)) for obs in observations]
    positions = {float(obs["degradation"].get("exposure_path_position", -1.0)) for obs in observations}
    contrast_ok = True
    for obs in observations:
        measured = 255.0 * float(obs["degradation"].get("p95_p5_contrast", -1.0))
        requested = float(obs["degradation"].get("requested_source_contrast_gray", -1.0))
        contrast_ok = contrast_ok and requested > 0.0 and abs(measured - requested) <= 12.0
    span_ok = max(exposures) - min(exposures) >= float(cfg["minimum_exposure_span"])
    transition_ok = any(0.82 <= exposure <= 1.16 for exposure in exposures)
    return not (
        len(families) == 1
        and len(parameter_seeds) == 1
        and len(noise_seeds) == 4
        and labels == expected_labels
        and len(positions) == 4
        and span_ok
        and transition_ok
        and contrast_ok
    )


def _discover_failed_scenes(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    cfg = gen.DESIGN["dataset"]["recoverability_contract"]
    allowed = float(cfg["maximum_source_target_gap"]) + 1.5 / 255.0
    maximum_fraction = float(cfg["maximum_fraction_above_model_bound"])
    for record in manifest["records"]:
        # Locate candidates from immutable generation metadata.  The final
        # package audit below independently reloads and remeasures every array,
        # so discovery does not trust metadata as proof of acceptance.
        source_failure = any(
            float(observation["degradation"].get("recoverability_robust_gap_before_scale", 1.0)) > allowed
            or float(observation["degradation"].get("recoverability_fraction_above_model_bound", 1.0)) > maximum_fraction + 1e-9
            for observation in record["observations"]
        )
        bundle_failure = record["role"] == "exposure_coherent_bundle" and _exposure_bundle_failure(record)
        if source_failure or bundle_failure:
            if record["role"] != "exposure_coherent_bundle":
                raise RuntimeError(f"Local repair is restricted to exposure bundles, found {record['scene_id']}")
            failed.append(record)
    return failed


def _candidate(record: dict[str, Any], attempt: int) -> tuple[list[tuple[np.ndarray, np.ndarray, dict[str, Any]]], list[dict[str, Any]]] | None:
    target = np.asarray(np.load(PACKAGE / record["target"], allow_pickle=False))
    mask = np.asarray(np.load(PACKAGE / record["mask"], allow_pickle=False))
    original_parameter_seed = int(record["observations"][0]["degradation_parameter_seed"])
    original_scene_seed = original_parameter_seed - 600000
    candidate_parameter_seed = original_parameter_seed + attempt * SEED_STRIDE
    profiles = gen.coherent_exposure_profiles(original_scene_seed + attempt * SEED_STRIDE)
    rendered: list[tuple[np.ndarray, np.ndarray, dict[str, Any]]] = []
    candidate_observations: list[dict[str, Any]] = []
    for index, (observation, profile) in enumerate(zip(record["observations"], profiles)):
        dx = float(observation["motion_dx_px"])
        dy = float(observation["motion_dy_px"])
        shifted_target = gen.warp_u8(target, dx, dy, interpolation=cv2.INTER_LANCZOS4)
        shifted_mask = gen.warp_u8(mask, dx, dy, interpolation=cv2.INTER_LINEAR)
        candidate_noise_seed = int(observation["independent_noise_seed"]) + attempt * NOISE_STRIDE
        source, noise_free, degradation = gen.degrade(
            shifted_target,
            shifted_mask,
            str(observation["degradation_family"]),
            candidate_parameter_seed,
            candidate_noise_seed,
            photometric_override=profile,
        )
        if _source_contract_failure(source, shifted_target):
            return None
        replacement = dict(observation)
        replacement.update(
            source_sha256=gen.array_sha256(source),
            noise_free_source_sha256=gen.array_sha256(noise_free),
            detail_recoverability=float(degradation["recoverability_score"]),
            degradation=degradation,
            degradation_parameter_seed=candidate_parameter_seed,
            independent_noise_seed=candidate_noise_seed,
        )
        rendered.append((source, noise_free, degradation))
        candidate_observations.append(replacement)
    candidate_record = dict(record)
    candidate_record["observations"] = candidate_observations
    if _exposure_bundle_failure(candidate_record):
        return None
    return rendered, candidate_observations


def _content_hash(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["scene_id"].encode("utf-8"))
        for key in ("target_sha256", "mask_sha256", "sdf_q4_sha256"):
            digest.update(record[key].encode("ascii"))
        for observation in record["observations"]:
            digest.update(observation["source_sha256"].encode("ascii"))
            digest.update(observation["noise_free_source_sha256"].encode("ascii"))
    return digest.hexdigest()


def main() -> int:
    manifest_path = PACKAGE / "manifest.json"
    audit_path = PACKAGE / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError("Formal manifest and failed audit are required")
    original_manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(original_manifest_bytes.decode("utf-8"))
    prior_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if prior_audit.get("passed"):
        raise RuntimeError("Refusing to modify an already passing formal dataset")
    registry_path = ROOT / "runs" / "formal_run_registry.json"
    if registry_path.is_file() and json.loads(registry_path.read_text(encoding="utf-8")):
        raise RuntimeError("Refusing local data repair after formal training registration")

    failed = _discover_failed_scenes(manifest)
    if not failed:
        raise RuntimeError("No locally repairable scene was discovered")
    maximum_fraction = float(gen.DESIGN["dataset"]["recoverability_contract"]["maximum_observation_fraction_requiring_same_family_rerender"])
    affected_observations = 4 * len(failed)
    if affected_observations / int(manifest["total_observations"]) > maximum_fraction + 1e-12:
        raise RuntimeError("Predeclared local rerender fraction would be exceeded")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_ROOT / f"backup_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    (backup / "manifest_before.json").write_bytes(original_manifest_bytes)
    shutil.copy2(audit_path, backup / "audit_before.json")
    immutable_before: dict[str, Any] = {}
    affected_ids = {record["scene_id"] for record in failed}
    for record in manifest["records"]:
        if record["scene_id"] not in affected_ids:
            immutable_before[record["scene_id"]] = {
                "target": record["target_sha256"],
                "mask": record["mask_sha256"],
                "sdf_q4": record["sdf_q4_sha256"],
                "observations": [
                    [obs["source_sha256"], obs["noise_free_source_sha256"]]
                    for obs in record["observations"]
                ],
            }
            continue
        scene_backup = backup / f"scene_{int(record['scene_index']):04d}"
        scene_backup.mkdir(parents=True, exist_ok=False)
        scene_json = PACKAGE / "arrays" / f"scene_{int(record['scene_index']):04d}" / "scene.json"
        shutil.copy2(scene_json, scene_backup / "scene_before.json")
        for observation in record["observations"]:
            for key in ("source", "noise_free_source"):
                source_path = PACKAGE / observation[key]
                shutil.copy2(source_path, scene_backup / source_path.name)

    repair_rows: list[dict[str, Any]] = []
    for record in failed:
        accepted = None
        accepted_attempt = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            accepted = _candidate(record, attempt)
            if accepted is not None:
                accepted_attempt = attempt
                break
        if accepted is None or accepted_attempt is None:
            raise RuntimeError(f"No deterministic repair candidate found for {record['scene_id']}")
        rendered, observations = accepted
        original_hashes = [[obs["source_sha256"], obs["noise_free_source_sha256"]] for obs in record["observations"]]
        for observation, (source, noise_free, _degradation) in zip(observations, rendered):
            gen.save_npy_atomic(PACKAGE / observation["source"], source)
            gen.save_npy_atomic(PACKAGE / observation["noise_free_source"], noise_free)
        record["observations"] = observations
        record["local_repair"] = {
            "method": "first_deterministic_same_family_full_bundle_rerender",
            "attempt": accepted_attempt,
            "clean_target_changed": False,
            "geometry_changed": False,
            "family_changed": False,
        }
        scene_json = PACKAGE / "arrays" / f"scene_{int(record['scene_index']):04d}" / "scene.json"
        gen.json_dump(scene_json, record)
        repair_rows.append({
            "scene_id": record["scene_id"],
            "scene_index": int(record["scene_index"]),
            "attempt": accepted_attempt,
            "original_observation_hashes": original_hashes,
            "replacement_observation_hashes": [[obs["source_sha256"], obs["noise_free_source_sha256"]] for obs in observations],
        })

    immutable_after: dict[str, Any] = {}
    for record in manifest["records"]:
        if record["scene_id"] in affected_ids:
            continue
        immutable_after[record["scene_id"]] = {
            "target": record["target_sha256"],
            "mask": record["mask_sha256"],
            "sdf_q4": record["sdf_q4_sha256"],
            "observations": [
                [obs["source_sha256"], obs["noise_free_source_sha256"]]
                for obs in record["observations"]
            ],
        }
    if immutable_before != immutable_after:
        raise RuntimeError("An unaffected manifest record changed during local repair")

    repair_tool_sha = _sha256_bytes(Path(__file__).resolve())
    manifest["content_sha256"] = _content_hash(manifest["records"])
    manifest["local_repair_history"] = [{
        "repaired_at": datetime.now().isoformat(),
        "repair_tool_sha256": repair_tool_sha,
        "original_manifest_sha256": hashlib.sha256(original_manifest_bytes).hexdigest(),
        "original_content_sha256": json.loads(original_manifest_bytes.decode("utf-8"))["content_sha256"],
        "affected_scene_count": len(failed),
        "affected_observation_count": affected_observations,
        "untouched_scene_count": len(manifest["records"]) - len(failed),
        "untouched_observation_count": int(manifest["total_observations"]) - affected_observations,
        "backup": str(backup),
        "strategy": "first deterministic same-family four-view rerender satisfying predeclared contracts",
    }]
    gen.json_dump(manifest_path, manifest)
    report = gen.audit(PACKAGE, manifest, full_hash=True)
    final_manifest_sha = _sha256_bytes(manifest_path)
    repair_report = {
        "passed": bool(report["passed"]),
        "formal_full_audit_passed": bool(report["passed"]),
        "affected_scene_count": len(failed),
        "affected_observation_count": affected_observations,
        "untouched_scene_count": len(manifest["records"]) - len(failed),
        "untouched_observation_count": int(manifest["total_observations"]) - affected_observations,
        "unaffected_manifest_hashes_identical": immutable_before == immutable_after,
        "clean_targets_changed": False,
        "geometry_changed": False,
        "degradation_family_changed": False,
        "backup": str(backup),
        "repair_tool_sha256": repair_tool_sha,
        "manifest_after_sha256": final_manifest_sha,
        "content_after_sha256": manifest["content_sha256"],
        "scenes": repair_rows,
        "audit": report,
    }
    gen.json_dump(REPORT_ROOT / "latest_repair_report.json", repair_report)
    gen.json_dump(backup / "repair_report.json", repair_report)
    print(json.dumps(repair_report, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
