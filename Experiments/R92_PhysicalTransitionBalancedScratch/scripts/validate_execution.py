"""Preflight checks for the authorized R92 implementation and single formal run."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = ROOT / "config" / "execution_authorization.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate(*, require_implementation: bool = False, require_formal_data: bool = False) -> list[str]:
    errors: list[str] = []
    auth = load_json(AUTH_PATH)
    if auth.get("experiment_id") != "R92_PhysicalTransitionBalancedScratch":
        errors.append("Execution authorization does not belong to R92.")
    if auth.get("authorization_status") not in {"setup_and_smoke_authorized", "formal_authorized"}:
        errors.append("Execution authorization is not active.")
    expected_limit = 1 if auth.get("formal_training_authorized") else 0
    if int(auth.get("formal_run_limit", -1)) != expected_limit:
        errors.append("Formal run limit does not match the explicit authorization state.")
    for key in (
        "checkpoint_inheritance_allowed",
        "resume_allowed",
        "teacher_or_pseudo_label_allowed",
        "sem_or_real_sample_training_pixels_allowed",
        "formal_baseline_promotion_authorized",
        "external_gmf_waiver_authorized",
    ):
        if auth.get(key):
            errors.append(f"Forbidden authorization switch is enabled: {key}")
    for relative, expected in auth.get("locked_files", {}).items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"Locked file is missing: {relative}")
        elif sha256_file(path).lower() != str(expected).lower():
            errors.append(f"Locked file changed after authorization: {relative}")
    if auth.get("branch"):
        try:
            branch = current_branch()
            if branch != auth.get("branch"):
                errors.append(f"Wrong branch: {branch!r} != {auth.get('branch')!r}")
        except Exception as exc:  # pragma: no cover - environment diagnostic
            errors.append(f"Could not verify git branch: {exc}")

    registry_path = ROOT / auth["run_registry"]
    if registry_path.is_file():
        registry = load_json(registry_path)
        formal_runs = registry.get("formal_runs", [])
        if len(formal_runs) > int(auth["formal_run_limit"]):
            errors.append("Formal run registry exceeds the authorized limit.")

    if require_implementation:
        required = [
            ROOT / "model" / "r92_model.py",
            ROOT / "scripts" / "generate_dataset.py",
            ROOT / "training" / "train_r92.py",
            ROOT / "inference" / "reconstruct.py",
            ROOT / "scripts" / "repair_unprojectable_observations.py",
            ROOT / "scripts" / "repair_recoverability.py",
            ROOT / "scripts" / "repair_exposure_span.py",
            ROOT / "scripts" / "launch_r92.py",
            ROOT / "config" / "optical_statistics.json",
        ]
        for path in required:
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"Implementation file is missing: {path.relative_to(ROOT)}")
        trainer = ROOT / "training" / "train_r92.py"
        if trainer.is_file():
            source = trainer.read_text(encoding="utf-8").lower()
            for forbidden in ('add_argument("--checkpoint"', 'add_argument("--resume"', "torch.load("):
                if forbidden in source:
                    errors.append(f"Scratch trainer exposes forbidden surface: {forbidden}")
        lock_path = ROOT / "config" / "implementation_lock.json"
        if not lock_path.is_file():
            errors.append("Implementation lock is missing.")
        else:
            implementation_lock = load_json(lock_path)
            if implementation_lock.get("status") != "frozen_before_formal_data":
                errors.append("Implementation lock status is invalid.")
            for relative, expected in implementation_lock.get("files", {}).items():
                path = ROOT / relative
                if not path.is_file() or sha256_file(path) != expected:
                    errors.append(f"Frozen implementation changed: {relative}")

    if require_formal_data:
        if auth.get("authorization_status") != "formal_authorized" or not auth.get("formal_training_authorized"):
            errors.append("Formal training is not explicitly authorized.")
        if not auth.get("formal_dataset_generation_authorized") or not auth.get("locked_holdout_generation_authorized"):
            errors.append("Formal and locked-holdout dataset generation are not authorized.")
        gpu_benchmark_path = ROOT / "results" / "preformal_benchmark.json"
        if not gpu_benchmark_path.is_file():
            errors.append("The full GPU pre-formal benchmark is missing.")
        else:
            gpu_benchmark = load_json(gpu_benchmark_path)
            if gpu_benchmark.get("benchmark_scope") != "formal_gpu" or not gpu_benchmark.get("formal_gpu_benchmark_complete"):
                errors.append("The full GPU pre-formal benchmark is incomplete.")
            expected_hashes = {
                "architecture_sha256": sha256_file(ROOT / "model" / "r92_model.py"),
                "trainer_sha256": sha256_file(ROOT / "training" / "train_r92.py"),
                "inference_sha256": sha256_file(ROOT / "inference" / "reconstruct.py"),
            }
            for key, expected in expected_hashes.items():
                if gpu_benchmark.get(key) != expected:
                    errors.append(f"The full GPU benchmark is stale: {key}")
        for package_name in ("r92_formal", "r92_locked_holdout"):
            package = ROOT / "data" / package_name
            for name in ("manifest.json", "audit.json"):
                path = package / name
                if not path.is_file():
                    errors.append(f"Required data artifact is missing: {path.relative_to(ROOT)}")
            audit_path = package / "audit.json"
            if audit_path.is_file():
                audit = load_json(audit_path)
                if not audit.get("passed"):
                    errors.append(f"Data audit failed: {audit_path.relative_to(ROOT)}")
                if not audit.get("full_array_hash_audit"):
                    errors.append(f"Full array hash audit is missing: {audit_path.relative_to(ROOT)}")
            manifest_path = package / "manifest.json"
            if manifest_path.is_file():
                manifest = load_json(manifest_path)
                isolation = manifest.get("source_isolation", {})
                isolation_pass = bool(
                    isolation.get("procedural_only")
                    and isolation.get("real_optical_aggregate_statistics")
                    and not isolation.get("real_microscope_pixels")
                    and not isolation.get("sem_pixels_or_structure")
                    and not isolation.get("hs100mg_pixels_or_structure")
                    and not isolation.get("measured_psf")
                    and not isolation.get("legacy_training_pairs")
                    and not isolation.get("checkpoint_or_teacher_output")
                )
                if not isolation_pass:
                    errors.append(f"Source isolation contract failed: {manifest_path.relative_to(ROOT)}")
                if audit_path.is_file() and load_json(audit_path).get("content_sha256") != manifest.get("content_sha256"):
                    errors.append(f"Manifest/audit content hash mismatch: {package_name}")
                same_family_rerender = manifest.get("same_family_parameter_rerender")
                if same_family_rerender is not None:
                    lock_path = ROOT / "config" / "implementation_lock.json"
                    implementation_lock = load_json(lock_path) if lock_path.is_file() else {}
                    locked_rerender_hash = implementation_lock.get("files", {}).get("scripts/repair_unprojectable_observations.py")
                    if (
                        same_family_rerender.get("status") != "complete_pending_full_audit"
                        or same_family_rerender.get("method") != "deterministic_same_family_full_forward_rerender"
                        or not same_family_rerender.get("full_forward_rerender")
                        or not same_family_rerender.get("same_degradation_family_retained")
                        or same_family_rerender.get("source_target_pixel_blending")
                        or same_family_rerender.get("geometry_or_label_changed")
                        or same_family_rerender.get("split_or_role_changed")
                        or float(same_family_rerender.get("rerendered_observation_fraction", 1.0)) > 0.02
                    ):
                        errors.append(f"Same-family rerender policy failed: {package_name}")
                    if same_family_rerender.get("script_sha256") != locked_rerender_hash:
                        errors.append(f"Same-family rerender script is not the frozen implementation: {package_name}")
                    rerender_backup_manifest = ROOT / str(same_family_rerender.get("backup", "")) / "backup_manifest.json"
                    if not rerender_backup_manifest.is_file() or sha256_file(rerender_backup_manifest) != same_family_rerender.get("backup_manifest_sha256"):
                        errors.append(f"Same-family rerender backup is missing or changed: {package_name}")
                projection = manifest.get("recoverability_projection")
                if projection is not None:
                    lock_path = ROOT / "config" / "implementation_lock.json"
                    implementation_lock = load_json(lock_path) if lock_path.is_file() else {}
                    locked_repair_hash = implementation_lock.get("files", {}).get("scripts/repair_recoverability.py")
                    if (
                        projection.get("status") != "complete_pending_full_audit"
                        or projection.get("method") != "global_affine_source_only_no_target_pixel_mix"
                        or projection.get("source_target_pixel_blending")
                        or projection.get("geometry_or_label_changed")
                    ):
                        errors.append(f"Recoverability projection policy failed: {package_name}")
                    if projection.get("script_sha256") != locked_repair_hash:
                        errors.append(f"Recoverability projection script is not the frozen implementation: {package_name}")
                    if float(projection.get("projected_observation_fraction", 1.0)) > 0.10:
                        errors.append(f"Recoverability projection share is too large: {package_name}")
                    backup_manifest = ROOT / str(projection.get("backup", "")) / "backup_manifest.json"
                    if not backup_manifest.is_file() or sha256_file(backup_manifest) != projection.get("backup_manifest_sha256"):
                        errors.append(f"Recoverability backup is missing or changed: {package_name}")
                span_repair = manifest.get("exposure_span_repair")
                if span_repair is not None:
                    lock_path = ROOT / "config" / "implementation_lock.json"
                    implementation_lock = load_json(lock_path) if lock_path.is_file() else {}
                    locked_span_hash = implementation_lock.get("files", {}).get("scripts/repair_exposure_span.py")
                    if (
                        span_repair.get("status") != "complete_pending_full_audit"
                        or span_repair.get("source_target_pixel_blending")
                        or span_repair.get("geometry_or_label_changed")
                        or float(span_repair.get("rerendered_bundle_fraction", 1.0)) > 0.05
                        or float(span_repair.get("minimum_new_span", 0.0)) < 0.30
                    ):
                        errors.append(f"Exposure-span rerender policy failed: {package_name}")
                    if span_repair.get("script_sha256") != locked_span_hash:
                        errors.append(f"Exposure-span repair script is not the frozen implementation: {package_name}")
                    span_backup_manifest = ROOT / str(span_repair.get("backup", "")) / "backup_manifest.json"
                    if not span_backup_manifest.is_file() or sha256_file(span_backup_manifest) != span_repair.get("backup_manifest_sha256"):
                        errors.append(f"Exposure-span backup is missing or changed: {package_name}")
        seal_path = ROOT / "data" / "r92_locked_holdout" / "SEALED.json"
        if not seal_path.is_file():
            errors.append("Locked holdout seal is missing.")
        else:
            seal = load_json(seal_path)
            if seal.get("status") != "sealed_unread_until_checkpoint_frozen" or seal.get("training_access_allowed") or seal.get("checkpoint_selection_access_allowed"):
                errors.append("Locked holdout seal policy is invalid.")
            manifest_path = ROOT / "data" / "r92_locked_holdout" / "manifest.json"
            if manifest_path.is_file() and seal.get("manifest_sha256") != sha256_file(manifest_path):
                errors.append("Locked holdout manifest changed after sealing.")

    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--require-implementation", action="store_true")
    parser.add_argument("--require-formal-data", action="store_true")
    args = parser.parse_args()
    errors = validate(
        require_implementation=args.require_implementation,
        require_formal_data=args.require_formal_data,
    )
    payload = {
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "branch": current_branch() if not errors and load_json(AUTH_PATH).get("branch") else None,
        "authorization": str(AUTH_PATH),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
