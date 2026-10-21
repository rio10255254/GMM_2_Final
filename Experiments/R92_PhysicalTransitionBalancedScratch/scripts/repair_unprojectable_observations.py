"""Rerender rare R92 observations that no permitted source projection can repair.

The rerender keeps the scene geometry, target, motion, degradation family and
split fixed.  It deterministically resamples only the optical/noise parameters
inside that same family, selects the first candidate that meets the already
declared recoverability contract, and retains hash-verified originals before
any atomic replacement.  It never blends target pixels into an existing
source image.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
from typing import Any

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
LOCK_PATH = ROOT / "config" / "implementation_lock.json"
PROFILE_DIRS = {
    "formal": ROOT / "data" / "r92_formal",
    "holdout": ROOT / "data" / "r92_locked_holdout",
}
GROUPED_ROLES = {"exposure_coherent_bundle", "signed_subpixel_motion"}


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
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


def exact_package_path(package: Path, relative: str) -> Path:
    candidate = (package / relative).resolve()
    package_root = package.resolve()
    if not candidate.is_relative_to(package_root):
        raise RuntimeError(f"Path escapes the dataset package: {relative}")
    return candidate


def exposure_override(observation: dict[str, Any]) -> dict[str, Any]:
    degradation = observation["degradation"]
    return {
        "exposure": float(degradation["exposure"]),
        "gamma": float(degradation["gamma"]),
        "source_contrast_gray": degradation.get("requested_source_contrast_gray"),
        "label": str(degradation["exposure_coherent_profile"]),
        "path_position": float(degradation["exposure_path_position"]),
    }


def aligned_pair(
    generator: Any,
    target: np.ndarray,
    mask: np.ndarray,
    observation: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    dx = float(observation["motion_dx_px"])
    dy = float(observation["motion_dy_px"])
    aligned_target = generator.warp_u8(target, dx, dy, interpolation=cv2.INTER_LANCZOS4)
    aligned_mask = generator.warp_u8(mask, dx, dy, interpolation=cv2.INTER_LINEAR)
    return aligned_target, aligned_mask


def deterministic_seed(original: int, attempt: int, stride: int) -> int:
    return int(original) + int(attempt) * int(stride)


def plan_rerender(
    generator: Any,
    recoverability: Any,
    record: dict[str, Any],
    trigger_indices: list[int],
    target: np.ndarray,
    mask: np.ndarray,
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    role = str(record["role"])
    observation_indices = list(range(len(record["observations"]))) if role in GROUPED_ROLES else trigger_indices
    maximum_attempts = int(contract["maximum_same_family_rerender_attempts"])
    parameter_stride = int(contract["same_family_parameter_seed_stride"])
    noise_stride = int(contract["same_family_noise_seed_stride"])
    shared_parameter_seed = int(record["observations"][0]["degradation_parameter_seed"])

    for attempt in range(1, maximum_attempts + 1):
        candidates: list[dict[str, Any]] = []
        all_pass = True
        for observation_index in observation_indices:
            observation = record["observations"][observation_index]
            aligned_target, aligned_mask = aligned_pair(generator, target, mask, observation)
            original_parameter_seed = shared_parameter_seed if role in GROUPED_ROLES else int(observation["degradation_parameter_seed"])
            parameter_seed = deterministic_seed(original_parameter_seed, attempt, parameter_stride)
            noise_seed = deterministic_seed(int(observation["independent_noise_seed"]), attempt, noise_stride)
            override = exposure_override(observation) if role == "exposure_coherent_bundle" else None
            candidate, degradation = generator.degrade(
                aligned_target,
                aligned_mask,
                str(observation["degradation_family"]),
                parameter_seed,
                noise_seed,
                photometric_override=override,
            )
            metrics = recoverability.recoverability_metrics(candidate, aligned_target, contract)
            requested_contrast = degradation.get("requested_source_contrast_gray")
            contrast_gray = float(np.percentile(candidate, 95) - np.percentile(candidate, 5))
            contrast_ok = requested_contrast is None or abs(contrast_gray - float(requested_contrast)) <= 12.0
            if not recoverability.metrics_pass(metrics, contract) or not contrast_ok:
                all_pass = False
                break
            candidates.append({
                "scene_index": int(record["scene_index"]),
                "observation_index": observation_index,
                "source_relative": str(observation["source"]),
                "original_source_sha256": str(observation["source_sha256"]),
                "original_parameter_seed": int(observation["degradation_parameter_seed"]),
                "original_noise_seed": int(observation["independent_noise_seed"]),
                "parameter_seed": parameter_seed,
                "noise_seed": noise_seed,
                "attempt": attempt,
                "candidate": candidate,
                "degradation": degradation,
                "robust_gap_after": metrics[0],
                "fraction_above_bound_after": metrics[1],
                "contrast_gray_after": contrast_gray,
            })
        if all_pass and len(candidates) == len(observation_indices):
            return candidates
    raise RuntimeError(
        f"No same-family rerender met the fixed contract after {maximum_attempts} attempts "
        f"for scene {record['scene_index']} observations {observation_indices}"
    )


def repair(profile: str) -> dict[str, Any]:
    package = PROFILE_DIRS[profile]
    manifest_path, audit_path = package / "manifest.json", package / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError(f"A generated and audited package is required: {package}")
    design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    contract = design["dataset"]["recoverability_contract"]
    if not contract.get("post_generation_same_family_parameter_rerender_allowed"):
        raise RuntimeError("Same-family optical-parameter rerender is not authorized by the design")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous = manifest.get("same_family_parameter_rerender")
    if isinstance(previous, dict) and previous.get("status") == "complete_pending_full_audit":
        return previous

    generator = load_module("r92_generator_same_family_rerender", ROOT / "scripts" / "generate_dataset.py")
    recoverability = load_module("r92_recoverability_same_family_rerender", ROOT / "scripts" / "repair_recoverability.py")
    trigger_by_scene: dict[int, list[int]] = {}
    trigger_metrics: dict[tuple[int, int], tuple[float, float]] = {}
    for record in manifest["records"]:
        target = np.asarray(np.load(exact_package_path(package, record["target"]), mmap_mode="r", allow_pickle=False))
        for observation_index, observation in enumerate(record["observations"]):
            source = np.asarray(np.load(exact_package_path(package, observation["source"]), mmap_mode="r", allow_pickle=False))
            aligned_target = recoverability.shifted_target(target, observation)
            metrics = recoverability.recoverability_metrics(source, aligned_target, contract)
            if recoverability.metrics_pass(metrics, contract):
                continue
            if recoverability.project_candidate(source, aligned_target, observation["degradation"], contract) is None:
                scene_index = int(record["scene_index"])
                trigger_by_scene.setdefault(scene_index, []).append(observation_index)
                trigger_metrics[(scene_index, observation_index)] = metrics

    if not trigger_by_scene:
        result = {"status": "not_required", "profile": profile, "rerendered_observation_count": 0}
        print(json.dumps(result, ensure_ascii=False))
        return result

    plans: list[dict[str, Any]] = []
    for scene_index, trigger_indices in sorted(trigger_by_scene.items()):
        record = manifest["records"][scene_index]
        target = np.asarray(np.load(exact_package_path(package, record["target"]), allow_pickle=False))
        mask = np.asarray(np.load(exact_package_path(package, record["mask"]), allow_pickle=False))
        plans.extend(plan_rerender(generator, recoverability, record, trigger_indices, target, mask, contract))

    total_observations = int(manifest["total_observations"])
    rerender_fraction = len(plans) / max(total_observations, 1)
    if rerender_fraction > float(contract["maximum_observation_fraction_requiring_same_family_rerender"]):
        raise RuntimeError(f"Same-family rerender share is too large: {rerender_fraction:.6f}")

    backup = package / "same_family_parameter_rerender_backup"
    if backup.exists():
        raise FileExistsError(f"Refusing to overwrite the same-family rerender backup: {backup}")
    backup.mkdir(parents=True)
    backup_relatives = ["manifest.json", "audit.json"]
    shutil.copy2(manifest_path, backup / "manifest.json")
    shutil.copy2(audit_path, backup / "audit.json")
    affected_scenes = sorted(trigger_by_scene)
    for scene_index in affected_scenes:
        relative = f"arrays/scene_{scene_index:04d}/scene.json"
        backup_relatives.append(relative)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exact_package_path(package, relative), destination)
    for plan in plans:
        relative = str(plan["source_relative"])
        backup_relatives.append(relative)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exact_package_path(package, relative), destination)
        original = np.asarray(np.load(destination, mmap_mode="r", allow_pickle=False))
        if recoverability.array_sha256(original) != plan["original_source_sha256"]:
            raise RuntimeError(f"Backup array hash mismatch: {relative}")
    backup_manifest = {
        "status": "complete_originals_hash_verified",
        "created_at": datetime.now().isoformat(),
        "profile": profile,
        "original_content_sha256": manifest["content_sha256"],
        "files": [
            {"relative": relative, "sha256": sha256_file(backup / relative)}
            for relative in sorted(set(backup_relatives))
        ],
    }
    write_json(backup / "backup_manifest.json", backup_manifest)

    try:
        for plan in plans:
            record = manifest["records"][plan["scene_index"]]
            observation = record["observations"][plan["observation_index"]]
            candidate = plan["candidate"]
            degradation = plan["degradation"]
            degradation.update(
                same_family_parameter_rerender_applied=True,
                same_family_parameter_rerender_reason="no_permitted_global_projection_met_fixed_recoverability_contract",
                same_family_original_source_sha256=plan["original_source_sha256"],
                same_family_original_parameter_seed=plan["original_parameter_seed"],
                same_family_original_noise_seed=plan["original_noise_seed"],
                same_family_rerender_attempt=plan["attempt"],
                recoverability_robust_gap_after_same_family_rerender=plan["robust_gap_after"],
                recoverability_fraction_above_bound_after_same_family_rerender=plan["fraction_above_bound_after"],
            )
            recoverability.save_npy_atomic(exact_package_path(package, plan["source_relative"]), candidate)
            observation["source_sha256"] = recoverability.array_sha256(candidate)
            observation["degradation_parameter_seed"] = plan["parameter_seed"]
            observation["independent_noise_seed"] = plan["noise_seed"]
            observation["degradation"] = degradation
        for scene_index in affected_scenes:
            write_json(package / f"arrays/scene_{scene_index:04d}/scene.json", manifest["records"][scene_index])
        original_content = str(manifest["content_sha256"])
        manifest["content_sha256"] = recoverability.content_sha256(manifest)
        summary = {
            "status": "complete_pending_full_audit",
            "completed_at": datetime.now().isoformat(),
            "method": "deterministic_same_family_full_forward_rerender",
            "full_forward_rerender": True,
            "same_degradation_family_retained": True,
            "source_target_pixel_blending": False,
            "geometry_or_label_changed": False,
            "split_or_role_changed": False,
            "unprojectable_trigger_count": sum(len(indices) for indices in trigger_by_scene.values()),
            "rerendered_observation_count": len(plans),
            "rerendered_observation_fraction": rerender_fraction,
            "affected_scene_count": len(affected_scenes),
            "maximum_attempt_used": max(plan["attempt"] for plan in plans),
            "original_content_sha256": original_content,
            "rerendered_content_sha256": manifest["content_sha256"],
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "implementation_lock_sha256": sha256_file(LOCK_PATH),
            "backup": str(backup.relative_to(ROOT)).replace("\\", "/"),
            "backup_manifest_sha256": sha256_file(backup / "backup_manifest.json"),
        }
        manifest["same_family_parameter_rerender"] = summary
        write_json(manifest_path, manifest)
        for plan in plans:
            observation = manifest["records"][plan["scene_index"]]["observations"][plan["observation_index"]]
            current = np.asarray(np.load(exact_package_path(package, plan["source_relative"]), mmap_mode="r", allow_pickle=False))
            if recoverability.array_sha256(current) != observation["source_sha256"]:
                raise RuntimeError(f"Rerendered array hash mismatch: {plan['source_relative']}")
    except BaseException:
        recoverability.restore_backup(package, backup, sorted(set(backup_relatives)))
        raise

    report = {
        **manifest["same_family_parameter_rerender"],
        "profile": profile,
        "audit_required": True,
        "triggered": [
            {
                "scene_index": scene_index,
                "observation_index": observation_index,
                "robust_gap_before": trigger_metrics[(scene_index, observation_index)][0],
                "fraction_above_bound_before": trigger_metrics[(scene_index, observation_index)][1],
            }
            for scene_index, indices in sorted(trigger_by_scene.items())
            for observation_index in indices
        ],
        "rerendered": [
            {
                "scene_index": plan["scene_index"],
                "observation_index": plan["observation_index"],
                "attempt": plan["attempt"],
                "robust_gap_after": plan["robust_gap_after"],
                "fraction_above_bound_after": plan["fraction_above_bound_after"],
            }
            for plan in plans
        ],
    }
    output = ROOT / "reports" / f"{profile}_same_family_parameter_rerender.json"
    write_json(output, report)
    print(json.dumps({"passed": True, "profile": profile, "rerendered": len(plans), "report": str(output)}, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILE_DIRS), required=True)
    args = parser.parse_args()
    repair(args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
