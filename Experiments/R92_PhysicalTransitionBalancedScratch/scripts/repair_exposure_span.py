"""Rerender rare R92 exposure bundles whose realized path span is too short."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
LOCK_PATH = ROOT / "config" / "implementation_lock.json"
PROFILE_DIRS = {
    "formal": ROOT / "data" / "r92_formal",
    "holdout": ROOT / "data" / "r92_locked_holdout",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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
    if not candidate.is_relative_to(package.resolve()):
        raise RuntimeError(f"Path escapes dataset package: {relative}")
    return candidate


def normalized_exposures(observations: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, float]:
    by_label = {str(row["degradation"]["exposure_coherent_profile"]): row for row in observations}
    labels = [str(label) for label in config["labels"]]
    if set(by_label) != set(labels):
        raise RuntimeError("Exposure bundle labels are incomplete")
    low = float(by_label[labels[0]]["degradation"]["exposure"])
    high = float(by_label[labels[-1]]["degradation"]["exposure"])
    midpoint = 0.5 * (low + high)
    target_span = float(config["span_repair_target"])
    new_low, new_high = midpoint - 0.5 * target_span, midpoint + 0.5 * target_span
    if not float(config["dark_exposure_range"][0]) <= new_low <= float(config["dark_exposure_range"][1]):
        raise RuntimeError(f"Repaired dark endpoint is outside its declared range: {new_low}")
    if not float(config["bright_exposure_range"][0]) <= new_high <= float(config["bright_exposure_range"][1]):
        raise RuntimeError(f"Repaired bright endpoint is outside its declared range: {new_high}")
    return {
        label: new_low + float(by_label[label]["degradation"]["exposure_path_position"]) * target_span
        for label in labels
    }


def repair(profile: str) -> dict[str, Any]:
    package = PROFILE_DIRS[profile]
    manifest_path, audit_path = package / "manifest.json", package / "audit.json"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError(f"Generated package is incomplete: {package}")
    design = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    exposure_config = design["dataset"]["continuous_exposure_path"]
    contract = design["dataset"]["recoverability_contract"]
    if not exposure_config.get("post_generation_span_rerender_allowed"):
        raise RuntimeError("Exposure-span rerender is not authorized")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing = manifest.get("exposure_span_repair")
    if isinstance(existing, dict) and existing.get("status") == "complete_pending_full_audit":
        return existing

    generator = load_module("r92_generator_span_repair", ROOT / "scripts" / "generate_dataset.py")
    recoverability = load_module("r92_recoverability_span_repair", ROOT / "scripts" / "repair_recoverability.py")
    exposure_records = [row for row in manifest["records"] if row["role"] == "exposure_coherent_bundle"]
    affected = []
    for record in exposure_records:
        values = [float(row["degradation"]["exposure"]) for row in record["observations"]]
        if max(values) - min(values) < float(exposure_config["minimum_exposure_span"]):
            affected.append(record)
    affected_fraction = len(affected) / max(len(exposure_records), 1)
    if affected_fraction > float(exposure_config["maximum_bundle_fraction_requiring_span_rerender"]):
        raise RuntimeError(f"Too many exposure bundles require rerender: {affected_fraction:.6f}")

    plans: list[dict[str, Any]] = []
    additional_projections = []
    for record in affected:
        target = np.asarray(np.load(exact_package_path(package, record["target"]), mmap_mode="r", allow_pickle=False))
        mask = np.asarray(np.load(exact_package_path(package, record["mask"]), mmap_mode="r", allow_pickle=False))
        exposures = normalized_exposures(record["observations"], exposure_config)
        original_values = [float(row["degradation"]["exposure"]) for row in record["observations"]]
        for observation_index, observation in enumerate(record["observations"]):
            degradation = observation["degradation"]
            label = str(degradation["exposure_coherent_profile"])
            override = {
                "label": label,
                "exposure": float(exposures[label]),
                "gamma": float(degradation["gamma"]),
                "path_position": float(degradation["exposure_path_position"]),
                "source_contrast_gray": float(degradation["requested_source_contrast_gray"]),
            }
            aligned_target = generator.warp_u8(
                target,
                float(observation["motion_dx_px"]),
                float(observation["motion_dy_px"]),
                interpolation=generator.cv2.INTER_LANCZOS4,
            )
            aligned_mask = generator.warp_u8(
                mask,
                float(observation["motion_dx_px"]),
                float(observation["motion_dy_px"]),
                interpolation=generator.cv2.INTER_LINEAR,
            )
            source, metadata = generator.degrade(
                aligned_target,
                aligned_mask,
                str(observation["degradation_family"]),
                int(observation["degradation_parameter_seed"]),
                int(observation["independent_noise_seed"]),
                photometric_override=override,
            )
            before_projection = recoverability.recoverability_metrics(source, aligned_target, contract)
            projection_details = None
            if not recoverability.metrics_pass(before_projection, contract):
                projected = recoverability.project_candidate(source, aligned_target, metadata, contract)
                if projected is None:
                    raise RuntimeError(
                        f"Rerendered exposure remains unrecoverable: scene {record['scene_index']} observation {observation_index}"
                    )
                rerender_hash = recoverability.array_sha256(source)
                source, projection_details = projected
                metadata.update(
                    recoverability_projection_applied=True,
                    recoverability_projection_method=str(contract["projection_method"]),
                    recoverability_rerender_source_sha256=rerender_hash,
                    recoverability_robust_gap_before_projection=before_projection[0],
                    recoverability_fraction_above_bound_before_projection=before_projection[1],
                    recoverability_projection_fraction=projection_details["projection_fraction"],
                    recoverability_affine_scale=projection_details["affine_scale"],
                    recoverability_affine_offset_normalized=projection_details["affine_offset_normalized"],
                    recoverability_robust_gap_after_projection=projection_details["robust_gap_after"],
                    recoverability_fraction_above_model_bound=projection_details["fraction_above_bound_after"],
                    recoverability_projection_mean_absolute_gray=projection_details["mean_absolute_projection_gray"],
                    p95_p5_contrast=projection_details["p95_p5_contrast_gray_after"] / 255.0,
                )
                additional_projections.append(projection_details)
            final_metrics = recoverability.recoverability_metrics(source, aligned_target, contract)
            if not recoverability.metrics_pass(final_metrics, contract):
                raise RuntimeError("Exposure rerender did not meet the recoverability contract")
            requested = float(metadata["requested_source_contrast_gray"])
            measured = 255.0 * float(metadata["p95_p5_contrast"])
            if abs(measured - requested) > 12.0:
                raise RuntimeError("Exposure rerender left its declared contrast band")
            plans.append({
                "scene_index": int(record["scene_index"]),
                "observation_index": observation_index,
                "source_relative": str(observation["source"]),
                "original_source_sha256": str(observation["source_sha256"]),
                "source": source,
                "metadata": metadata,
                "old_span": max(original_values) - min(original_values),
                "new_exposure": float(exposures[label]),
                "projection": projection_details,
            })

    backup = package / "exposure_span_repair_backup"
    if backup.exists():
        raise FileExistsError(f"Refusing to overwrite exposure-span backup: {backup}")
    backup.mkdir(parents=True)
    backup_relatives = ["manifest.json", "audit.json"]
    shutil.copy2(manifest_path, backup / "manifest.json")
    shutil.copy2(audit_path, backup / "audit.json")
    for record in affected:
        relative = f"arrays/scene_{int(record['scene_index']):04d}/scene.json"
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
            raise RuntimeError(f"Exposure backup hash mismatch: {relative}")
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
            source = plan.pop("source")
            recoverability.save_npy_atomic(exact_package_path(package, plan["source_relative"]), source)
            observation["source_sha256"] = recoverability.array_sha256(source)
            observation["degradation"] = plan["metadata"]
        for record in affected:
            write_json(package / f"arrays/scene_{int(record['scene_index']):04d}/scene.json", record)
        original_content = str(manifest["content_sha256"])
        manifest["content_sha256"] = recoverability.content_sha256(manifest)
        summary = {
            "status": "complete_pending_full_audit",
            "completed_at": datetime.now().isoformat(),
            "rerendered_bundle_count": len(affected),
            "rerendered_bundle_fraction": affected_fraction,
            "rerendered_observation_count": len(plans),
            "additional_global_projection_count": len(additional_projections),
            "minimum_new_span": min((float(exposure_config["span_repair_target"]) for _ in affected), default=0.0),
            "original_content_sha256": original_content,
            "rerendered_content_sha256": manifest["content_sha256"],
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "implementation_lock_sha256": sha256_file(LOCK_PATH),
            "backup": str(backup.relative_to(ROOT)).replace("\\", "/"),
            "backup_manifest_sha256": sha256_file(backup / "backup_manifest.json"),
            "source_target_pixel_blending": False,
            "geometry_or_label_changed": False,
        }
        manifest["exposure_span_repair"] = summary
        if additional_projections and isinstance(manifest.get("recoverability_projection"), dict):
            prior = manifest["recoverability_projection"]
            prior_count = int(prior.get("projected_observation_count", 0))
            new_count = prior_count + len(additional_projections)
            prior_mean = float(prior.get("mean_absolute_projection_gray", 0.0))
            added_sum = sum(float(row["mean_absolute_projection_gray"]) for row in additional_projections)
            prior["projected_observation_count"] = new_count
            prior["projected_observation_fraction"] = new_count / max(int(manifest["total_observations"]), 1)
            prior["mean_absolute_projection_gray"] = (prior_mean * prior_count + added_sum) / max(new_count, 1)
            prior["maximum_absolute_projection_gray"] = max(
                float(prior.get("maximum_absolute_projection_gray", 0.0)),
                max(float(row["mean_absolute_projection_gray"]) for row in additional_projections),
            )
            prior["additional_projection_from_exposure_span_rerender"] = len(additional_projections)
            prior["additional_projection_backup"] = summary["backup"]
        write_json(manifest_path, manifest)
        for plan in plans:
            observation = manifest["records"][plan["scene_index"]]["observations"][plan["observation_index"]]
            current = np.asarray(np.load(exact_package_path(package, plan["source_relative"]), mmap_mode="r", allow_pickle=False))
            if recoverability.array_sha256(current) != observation["source_sha256"]:
                raise RuntimeError(f"Rerendered source hash mismatch: {plan['source_relative']}")
    except BaseException:
        recoverability.restore_backup(package, backup, sorted(set(backup_relatives)))
        raise

    report = {
        **manifest["exposure_span_repair"],
        "profile": profile,
        "audit_required": True,
        "affected_scenes": [int(row["scene_index"]) for row in affected],
        "observations": [
            {
                "scene_index": plan["scene_index"],
                "observation_index": plan["observation_index"],
                "old_span": plan["old_span"],
                "new_exposure": plan["new_exposure"],
                "projection": plan["projection"],
            }
            for plan in plans
        ],
    }
    output = ROOT / "reports" / f"{profile}_exposure_span_repair.json"
    write_json(output, report)
    print(json.dumps({"passed": True, "profile": profile, "bundles": len(affected), "report": str(output)}, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILE_DIRS), required=True)
    args = parser.parse_args()
    repair(args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
