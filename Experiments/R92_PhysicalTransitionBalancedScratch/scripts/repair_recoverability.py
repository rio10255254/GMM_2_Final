"""Project rare over-strength R92 observations back into the recoverable range.

This is a source-only global affine photometric projection. It never blends a
source with target pixels, never changes geometry, and never changes the
degradation family. Every original file is copied and hash-verified before an
atomic replacement, and the complete dataset must be re-audited afterwards.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(memoryview(np.ascontiguousarray(array)).cast("B")).hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def save_npy_atomic(path: Path, array: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, array, allow_pickle=False)
    os.replace(temporary, path)


def shifted_target(target: np.ndarray, observation: dict[str, Any]) -> np.ndarray:
    dx, dy = float(observation["motion_dx_px"]), float(observation["motion_dy_px"])
    if abs(dx) + abs(dy) == 0.0:
        return target
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(
        target,
        matrix,
        (target.shape[1], target.shape[0]),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def recoverability_metrics(source_u8: np.ndarray, target_u8: np.ndarray, contract: dict[str, Any]) -> tuple[float, float]:
    difference = np.abs(source_u8.astype(np.float32) - target_u8.astype(np.float32)) / 255.0
    robust_gap = float(np.percentile(difference, float(contract["robust_gap_percentile"])))
    fraction_above = float(np.mean(difference > float(contract["maximum_source_target_gap"])))
    return robust_gap, fraction_above


def metrics_pass(metrics: tuple[float, float], contract: dict[str, Any]) -> bool:
    robust_gap, fraction_above = metrics
    allowed_gap = float(contract["maximum_source_target_gap"]) + 1.5 / 255.0
    return bool(
        robust_gap <= allowed_gap
        and fraction_above <= float(contract["maximum_fraction_above_model_bound"]) + 1e-9
    )


def project_candidate(
    source_u8: np.ndarray,
    target_u8: np.ndarray,
    degradation: dict[str, Any],
    contract: dict[str, Any],
) -> tuple[np.ndarray, dict[str, float]] | None:
    """Return the smallest passing global affine projection, if one exists."""
    source = source_u8.astype(np.float32) / 255.0
    target = target_u8.astype(np.float32) / 255.0
    source_mean, target_mean = float(source.mean()), float(target.mean())
    centered_source = source - source_mean
    variance = float(np.mean(np.square(centered_source)))
    optimal_scale = float(np.mean(centered_source * (target - target_mean)) / max(variance, 1e-8))
    optimal_offset = float(target_mean - optimal_scale * source_mean)
    optimal_scale = float(np.clip(optimal_scale, 0.25, 6.00))
    optimal_offset = float(np.clip(optimal_offset, -2.00, 2.00))
    step = float(contract["projection_fraction_step"])
    maximum = float(contract["maximum_projection_fraction"])
    requested_contrast = degradation.get("requested_source_contrast_gray")
    for fraction in np.arange(step, maximum + 0.5 * step, step):
        scale = 1.0 + float(fraction) * (optimal_scale - 1.0)
        offset = float(fraction) * optimal_offset
        candidate = np.rint(np.clip(scale * source + offset, 0.0, 1.0) * 255.0).astype(np.uint8)
        after = recoverability_metrics(candidate, target_u8, contract)
        contrast_gray = float(np.percentile(candidate, 95) - np.percentile(candidate, 5))
        contrast_ok = requested_contrast is None or abs(contrast_gray - float(requested_contrast)) <= 12.0
        adjustment_gray = float(np.mean(np.abs(candidate.astype(np.float32) - source_u8.astype(np.float32))))
        if (
            metrics_pass(after, contract)
            and contrast_ok
            and adjustment_gray <= float(contract["maximum_mean_absolute_projection_gray"])
        ):
            return candidate, {
                "projection_fraction": float(fraction),
                "affine_scale": scale,
                "affine_offset_normalized": offset,
                "robust_gap_after": after[0],
                "fraction_above_bound_after": after[1],
                "mean_absolute_projection_gray": adjustment_gray,
                "p95_p5_contrast_gray_after": contrast_gray,
            }
    return None


def content_sha256(manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for record in manifest["records"]:
        digest.update(str(record["scene_id"]).encode("utf-8"))
        for key in ("target_sha256", "mask_sha256", "sdf_q4_sha256"):
            digest.update(str(record[key]).encode("ascii"))
        for observation in record["observations"]:
            digest.update(str(observation["source_sha256"]).encode("ascii"))
    return digest.hexdigest()


def exact_package_path(package: Path, relative: str) -> Path:
    candidate = (package / relative).resolve()
    package_root = package.resolve()
    if not candidate.is_relative_to(package_root):
        raise RuntimeError(f"Path escapes the dataset package: {relative}")
    return candidate


def restore_backup(package: Path, backup: Path, relative_paths: list[str]) -> None:
    for relative in relative_paths:
        source = backup / relative
        destination = exact_package_path(package, relative)
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def repair(profile: str) -> dict[str, Any]:
    package = PROFILE_DIRS[profile]
    manifest_path, audit_path = package / "manifest.json", package / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError(f"A generated and audited package is required: {package}")
    design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    contract = design["dataset"]["recoverability_contract"]
    if not contract.get("post_generation_global_photometric_projection_allowed"):
        raise RuntimeError("Global photometric projection is not authorized by the design")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous = manifest.get("recoverability_projection")
    if isinstance(previous, dict) and previous.get("status") == "complete_pending_full_audit":
        return previous

    plans: list[dict[str, Any]] = []
    for record in manifest["records"]:
        target = np.asarray(np.load(exact_package_path(package, record["target"]), mmap_mode="r", allow_pickle=False))
        for observation_index, observation in enumerate(record["observations"]):
            source_path = exact_package_path(package, observation["source"])
            source = np.asarray(np.load(source_path, mmap_mode="r", allow_pickle=False))
            aligned_target = shifted_target(target, observation)
            before = recoverability_metrics(source, aligned_target, contract)
            if metrics_pass(before, contract):
                continue
            projected = project_candidate(source, aligned_target, observation["degradation"], contract)
            if projected is None:
                raise RuntimeError(
                    f"No permitted global projection repairs scene {record['scene_index']} observation {observation_index}: {before}"
                )
            candidate, details = projected
            plans.append({
                "scene_index": int(record["scene_index"]),
                "observation_index": observation_index,
                "source_relative": str(observation["source"]),
                "original_source_sha256": str(observation["source_sha256"]),
                "before_robust_gap": before[0],
                "before_fraction_above_bound": before[1],
                "candidate": candidate,
                "details": details,
            })

    observation_count = int(manifest["total_observations"])
    projected_fraction = len(plans) / max(observation_count, 1)
    if projected_fraction > float(contract["maximum_observation_fraction_requiring_strength_projection"]):
        raise RuntimeError(f"Projection share is too large: {projected_fraction:.6f}")

    backup = package / "recoverability_projection_backup"
    if backup.exists():
        raise FileExistsError(f"Refusing to overwrite the recoverability backup: {backup}")
    backup.mkdir(parents=True)
    backup_relatives = ["manifest.json", "audit.json"]
    shutil.copy2(manifest_path, backup / "manifest.json")
    shutil.copy2(audit_path, backup / "audit.json")
    affected_scenes = sorted({int(plan["scene_index"]) for plan in plans})
    for scene_index in affected_scenes:
        relative = f"arrays/scene_{scene_index:04d}/scene.json"
        backup_relatives.append(relative)
        source = exact_package_path(package, relative)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for plan in plans:
        relative = str(plan["source_relative"])
        backup_relatives.append(relative)
        source = exact_package_path(package, relative)
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        original = np.asarray(np.load(destination, mmap_mode="r", allow_pickle=False))
        if array_sha256(original) != plan["original_source_sha256"]:
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
            record = manifest["records"][int(plan["scene_index"])]
            observation = record["observations"][int(plan["observation_index"])]
            candidate = plan.pop("candidate")
            new_hash = array_sha256(candidate)
            save_npy_atomic(exact_package_path(package, plan["source_relative"]), candidate)
            observation["source_sha256"] = new_hash
            degradation = observation["degradation"]
            degradation.update(
                recoverability_projection_applied=True,
                recoverability_projection_method=str(contract["projection_method"]),
                recoverability_original_source_sha256=plan["original_source_sha256"],
                recoverability_robust_gap_before_projection=plan["before_robust_gap"],
                recoverability_fraction_above_bound_before_projection=plan["before_fraction_above_bound"],
                recoverability_projection_fraction=plan["details"]["projection_fraction"],
                recoverability_affine_scale=plan["details"]["affine_scale"],
                recoverability_affine_offset_normalized=plan["details"]["affine_offset_normalized"],
                recoverability_robust_gap_after_projection=plan["details"]["robust_gap_after"],
                recoverability_fraction_above_bound=plan["details"]["fraction_above_bound_after"],
                recoverability_projection_mean_absolute_gray=plan["details"]["mean_absolute_projection_gray"],
                p95_p5_contrast=plan["details"]["p95_p5_contrast_gray_after"] / 255.0,
            )
        for scene_index in affected_scenes:
            write_json(package / f"arrays/scene_{scene_index:04d}/scene.json", manifest["records"][scene_index])
        original_content = str(manifest["content_sha256"])
        manifest["content_sha256"] = content_sha256(manifest)
        summary = {
            "status": "complete_pending_full_audit",
            "completed_at": datetime.now().isoformat(),
            "method": str(contract["projection_method"]),
            "source_target_pixel_blending": False,
            "geometry_or_label_changed": False,
            "projected_observation_count": len(plans),
            "projected_observation_fraction": projected_fraction,
            "affected_scene_count": len(affected_scenes),
            "mean_absolute_projection_gray": float(np.mean([plan["details"]["mean_absolute_projection_gray"] for plan in plans])) if plans else 0.0,
            "maximum_absolute_projection_gray": float(max((plan["details"]["mean_absolute_projection_gray"] for plan in plans), default=0.0)),
            "original_content_sha256": original_content,
            "projected_content_sha256": manifest["content_sha256"],
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "implementation_lock_sha256": sha256_file(LOCK_PATH),
            "backup": str(backup.relative_to(ROOT)).replace("\\", "/"),
            "backup_manifest_sha256": sha256_file(backup / "backup_manifest.json"),
        }
        manifest["recoverability_projection"] = summary
        write_json(manifest_path, manifest)
        for plan in plans:
            observation = manifest["records"][plan["scene_index"]]["observations"][plan["observation_index"]]
            current = np.asarray(np.load(exact_package_path(package, plan["source_relative"]), mmap_mode="r", allow_pickle=False))
            if array_sha256(current) != observation["source_sha256"]:
                raise RuntimeError(f"Projected array hash mismatch: {plan['source_relative']}")
    except BaseException:
        restore_backup(package, backup, sorted(set(backup_relatives)))
        raise

    report = {
        **manifest["recoverability_projection"],
        "profile": profile,
        "audit_required": True,
        "affected": [
            {
                "scene_index": plan["scene_index"],
                "observation_index": plan["observation_index"],
                "source": plan["source_relative"],
                "before_robust_gap": plan["before_robust_gap"],
                "before_fraction_above_bound": plan["before_fraction_above_bound"],
                **plan["details"],
            }
            for plan in plans
        ],
    }
    output = ROOT / "reports" / f"{profile}_recoverability_projection.json"
    write_json(output, report)
    print(json.dumps({"passed": True, "profile": profile, "projected": len(plans), "report": str(output)}, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILE_DIRS), required=True)
    args = parser.parse_args()
    repair(args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
