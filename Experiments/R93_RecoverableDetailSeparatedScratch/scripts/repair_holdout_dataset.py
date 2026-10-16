"""Locally repair invalid R93 holdout observations before sealing.

This tool never reads a model output.  It only enforces the already-declared
synthetic data contracts.  Exposure failures are replaced as complete
four-view bundles; an isolated non-exposure failure replaces only that one
observation.  All replacements use the same clean target and degradation
family, with deterministic candidate seeds.  The full holdout is re-hashed,
audited, and sealed after repair.
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
PACKAGE = ROOT / "data" / "r93_locked_holdout"
REPORT_ROOT = ROOT / "reports" / "holdout_data_local_repair"
MAX_ATTEMPTS = int(gen.DESIGN["dataset"]["recoverability_contract"]["maximum_same_family_rerender_attempts"])
SEED_STRIDE = int(gen.DESIGN["dataset"]["recoverability_contract"]["same_family_parameter_seed_stride"])
NOISE_STRIDE = int(gen.DESIGN["dataset"]["recoverability_contract"]["same_family_noise_seed_stride"])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_contract_failure(source: np.ndarray, shifted_target: np.ndarray) -> bool:
    cfg = gen.DESIGN["dataset"]["recoverability_contract"]
    gap = np.abs(source.astype(np.float32) - shifted_target.astype(np.float32)) / 255.0
    robust = float(np.percentile(gap, float(cfg["robust_gap_percentile"])))
    fraction = float(np.mean(gap > float(cfg["maximum_source_target_gap"])))
    allowed = float(cfg["maximum_source_target_gap"]) + 1.5 / 255.0
    return robust > allowed or fraction > float(cfg["maximum_fraction_above_model_bound"]) + 1e-9


def metadata_source_failure(observation: dict[str, Any]) -> bool:
    cfg = gen.DESIGN["dataset"]["recoverability_contract"]
    allowed = float(cfg["maximum_source_target_gap"]) + 1.5 / 255.0
    return (
        float(observation["degradation"].get("recoverability_robust_gap_before_scale", 1.0)) > allowed
        or float(observation["degradation"].get("recoverability_fraction_above_model_bound", 1.0))
        > float(cfg["maximum_fraction_above_model_bound"]) + 1e-9
    )


def exposure_bundle_failure(observations: list[dict[str, Any]]) -> bool:
    cfg = gen.DESIGN["dataset"]["continuous_exposure_path"]
    families = {str(obs["degradation_family"]) for obs in observations}
    parameter_seeds = {int(obs["degradation_parameter_seed"]) for obs in observations}
    noise_seeds = {int(obs["independent_noise_seed"]) for obs in observations}
    labels = {str(obs["degradation"].get("exposure_coherent_profile")) for obs in observations}
    expected_labels = {str(label) for label in cfg["labels"]}
    exposures = [float(obs["degradation"].get("exposure", 1.0)) for obs in observations]
    positions = {float(obs["degradation"].get("exposure_path_position", -1.0)) for obs in observations}
    contrast_ok = all(
        float(obs["degradation"].get("requested_source_contrast_gray", -1.0)) > 0.0
        and abs(
            255.0 * float(obs["degradation"].get("p95_p5_contrast", -1.0))
            - float(obs["degradation"].get("requested_source_contrast_gray", -1.0))
        ) <= 12.0
        for obs in observations
    )
    return not (
        len(families) == 1
        and len(parameter_seeds) == 1
        and len(noise_seeds) == 4
        and labels == expected_labels
        and len(positions) == 4
        and max(exposures) - min(exposures) >= float(cfg["minimum_exposure_span"])
        and any(0.82 <= exposure <= 1.16 for exposure in exposures)
        and contrast_ok
    )


def render_one(
    record: dict[str, Any], observation: dict[str, Any], attempt: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any], dict[str, Any]] | None:
    target = np.asarray(np.load(PACKAGE / record["target"], allow_pickle=False))
    mask = np.asarray(np.load(PACKAGE / record["mask"], allow_pickle=False))
    dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
    shifted_target = gen.warp_u8(target, dx, dy, interpolation=cv2.INTER_LANCZOS4)
    shifted_mask = gen.warp_u8(mask, dx, dy, interpolation=cv2.INTER_LINEAR)
    parameter_seed = int(observation["degradation_parameter_seed"]) + attempt * SEED_STRIDE
    noise_seed = int(observation["independent_noise_seed"]) + attempt * NOISE_STRIDE
    source, noise_free, degradation = gen.degrade(
        shifted_target,
        shifted_mask,
        str(observation["degradation_family"]),
        parameter_seed,
        noise_seed,
    )
    if source_contract_failure(source, shifted_target):
        return None
    replacement = dict(observation)
    replacement.update(
        source_sha256=gen.array_sha256(source),
        noise_free_source_sha256=gen.array_sha256(noise_free),
        detail_recoverability=float(degradation["recoverability_score"]),
        degradation=degradation,
        degradation_parameter_seed=parameter_seed,
        independent_noise_seed=noise_seed,
    )
    return source, noise_free, degradation, replacement


def render_exposure_bundle(
    record: dict[str, Any], attempt: int,
) -> tuple[list[tuple[np.ndarray, np.ndarray]], list[dict[str, Any]]] | None:
    target = np.asarray(np.load(PACKAGE / record["target"], allow_pickle=False))
    mask = np.asarray(np.load(PACKAGE / record["mask"], allow_pickle=False))
    original_parameter_seed = int(record["observations"][0]["degradation_parameter_seed"])
    original_scene_seed = original_parameter_seed - 600000
    parameter_seed = original_parameter_seed + attempt * SEED_STRIDE
    profiles = gen.coherent_exposure_profiles(original_scene_seed + attempt * SEED_STRIDE)
    arrays: list[tuple[np.ndarray, np.ndarray]] = []
    observations: list[dict[str, Any]] = []
    for original, profile in zip(record["observations"], profiles):
        dx, dy = float(original["motion_dx_px"]), float(original["motion_dy_px"])
        shifted_target = gen.warp_u8(target, dx, dy, interpolation=cv2.INTER_LANCZOS4)
        shifted_mask = gen.warp_u8(mask, dx, dy, interpolation=cv2.INTER_LINEAR)
        noise_seed = int(original["independent_noise_seed"]) + attempt * NOISE_STRIDE
        source, noise_free, degradation = gen.degrade(
            shifted_target,
            shifted_mask,
            str(original["degradation_family"]),
            parameter_seed,
            noise_seed,
            photometric_override=profile,
        )
        if source_contract_failure(source, shifted_target):
            return None
        replacement = dict(original)
        replacement.update(
            source_sha256=gen.array_sha256(source),
            noise_free_source_sha256=gen.array_sha256(noise_free),
            detail_recoverability=float(degradation["recoverability_score"]),
            degradation=degradation,
            degradation_parameter_seed=parameter_seed,
            independent_noise_seed=noise_seed,
        )
        arrays.append((source, noise_free))
        observations.append(replacement)
    if exposure_bundle_failure(observations):
        return None
    return arrays, observations


def content_hash(records: list[dict[str, Any]]) -> str:
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
    manifest_path, audit_path = PACKAGE / "manifest.json", PACKAGE / "audit.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    prior_audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if prior_audit.get("passed") or (PACKAGE / "SEALED.json").exists():
        raise RuntimeError("Refusing to modify a passing or sealed holdout")
    registry_path = ROOT / "runs" / "formal_run_registry.json"
    if registry_path.is_file() and json.loads(registry_path.read_text(encoding="utf-8")):
        raise RuntimeError("Refusing holdout repair after formal training registration")

    affected: dict[str, set[int]] = {}
    for record in manifest["records"]:
        source_failures = {
            int(obs["observation"]) for obs in record["observations"] if metadata_source_failure(obs)
        }
        if record["role"] == "exposure_coherent_bundle" and exposure_bundle_failure(record["observations"]):
            source_failures = {0, 1, 2, 3}
        if source_failures:
            affected[record["scene_id"]] = source_failures
    affected_observations = sum(len(indices) for indices in affected.values())
    allowed_fraction = float(gen.DESIGN["dataset"]["recoverability_contract"]["maximum_observation_fraction_requiring_same_family_rerender"])
    if not affected or affected_observations / int(manifest["total_observations"]) > allowed_fraction + 1e-12:
        raise RuntimeError("Local repair scope is empty or exceeds the predeclared limit")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = REPORT_ROOT / f"backup_{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    (backup / "manifest_before.json").write_bytes(manifest_bytes)
    shutil.copy2(audit_path, backup / "audit_before.json")
    untouched_hashes_before: dict[str, tuple[str, str]] = {}
    for record in manifest["records"]:
        indices = affected.get(record["scene_id"], set())
        for observation in record["observations"]:
            key = f"{record['scene_id']}:{int(observation['observation'])}"
            if int(observation["observation"]) not in indices:
                untouched_hashes_before[key] = (observation["source_sha256"], observation["noise_free_source_sha256"])
        if indices:
            scene_backup = backup / f"scene_{int(record['scene_index']):04d}"
            scene_backup.mkdir(parents=True, exist_ok=False)
            scene_json = PACKAGE / "arrays" / f"scene_{int(record['scene_index']):04d}" / "scene.json"
            shutil.copy2(scene_json, scene_backup / "scene_before.json")
            for observation in record["observations"]:
                if int(observation["observation"]) in indices:
                    for key in ("source", "noise_free_source"):
                        path = PACKAGE / observation[key]
                        shutil.copy2(path, scene_backup / path.name)

    repair_rows: list[dict[str, Any]] = []
    for record in manifest["records"]:
        indices = affected.get(record["scene_id"])
        if not indices:
            continue
        if indices == {0, 1, 2, 3} and record["role"] == "exposure_coherent_bundle":
            accepted = None
            for attempt in range(1, MAX_ATTEMPTS + 1):
                accepted = render_exposure_bundle(record, attempt)
                if accepted is not None:
                    break
            if accepted is None:
                raise RuntimeError(f"No valid exposure candidate for {record['scene_id']}")
            arrays, replacements = accepted
            for replacement, (source, noise_free) in zip(replacements, arrays):
                gen.save_npy_atomic(PACKAGE / replacement["source"], source)
                gen.save_npy_atomic(PACKAGE / replacement["noise_free_source"], noise_free)
            record["observations"] = replacements
            attempts = {index: attempt for index in sorted(indices)}
        else:
            attempts: dict[int, int] = {}
            for index in sorted(indices):
                original = record["observations"][index]
                accepted_one = None
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    accepted_one = render_one(record, original, attempt)
                    if accepted_one is not None:
                        break
                if accepted_one is None:
                    raise RuntimeError(f"No valid candidate for {record['scene_id']} observation {index}")
                source, noise_free, _degradation, replacement = accepted_one
                gen.save_npy_atomic(PACKAGE / replacement["source"], source)
                gen.save_npy_atomic(PACKAGE / replacement["noise_free_source"], noise_free)
                record["observations"][index] = replacement
                attempts[index] = attempt
        record["local_repair"] = {
            "method": "first_deterministic_same_family_rerender",
            "observation_indices": sorted(indices),
            "attempts": {str(key): value for key, value in attempts.items()},
            "clean_target_changed": False,
            "geometry_changed": False,
            "family_changed": False,
            "model_output_read": False,
        }
        scene_json = PACKAGE / "arrays" / f"scene_{int(record['scene_index']):04d}" / "scene.json"
        gen.json_dump(scene_json, record)
        repair_rows.append({"scene_id": record["scene_id"], "scene_index": int(record["scene_index"]), "observation_indices": sorted(indices), "attempts": attempts})

    untouched_hashes_after: dict[str, tuple[str, str]] = {}
    for record in manifest["records"]:
        indices = affected.get(record["scene_id"], set())
        for observation in record["observations"]:
            if int(observation["observation"]) not in indices:
                untouched_hashes_after[f"{record['scene_id']}:{int(observation['observation'])}"] = (
                    observation["source_sha256"], observation["noise_free_source_sha256"]
                )
    if untouched_hashes_before != untouched_hashes_after:
        raise RuntimeError("An unaffected holdout observation changed")

    tool_hash = file_sha256(Path(__file__).resolve())
    manifest["content_sha256"] = content_hash(manifest["records"])
    manifest["local_repair_history"] = [{
        "repaired_at": datetime.now().isoformat(),
        "repair_tool_sha256": tool_hash,
        "original_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "affected_scene_count": len(affected),
        "affected_observation_count": affected_observations,
        "untouched_observation_count": int(manifest["total_observations"]) - affected_observations,
        "model_output_read": False,
        "backup": str(backup),
    }]
    gen.json_dump(manifest_path, manifest)
    audit = gen.audit(PACKAGE, manifest, full_hash=True)
    seal = gen.seal_holdout(PACKAGE, manifest, audit)
    report = {
        "passed": bool(audit["passed"]),
        "affected_scene_count": len(affected),
        "affected_observation_count": affected_observations,
        "untouched_observation_count": int(manifest["total_observations"]) - affected_observations,
        "untouched_observation_hashes_identical": untouched_hashes_before == untouched_hashes_after,
        "clean_targets_changed": False,
        "geometry_changed": False,
        "degradation_family_changed": False,
        "model_output_read": False,
        "backup": str(backup),
        "scenes": repair_rows,
        "audit": audit,
        "seal": seal,
    }
    gen.json_dump(REPORT_ROOT / "latest_repair_report.json", report)
    gen.json_dump(backup / "repair_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
