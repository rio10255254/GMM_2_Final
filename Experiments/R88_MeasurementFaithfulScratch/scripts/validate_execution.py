"""Preflight checks for the authorized R88 implementation and single formal run."""
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
    if auth.get("authorization_status") != "authorized":
        errors.append("Execution authorization is not active.")
    if int(auth.get("formal_run_limit", 0)) != 1:
        errors.append("The formal run limit must remain exactly one.")
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
            ROOT / "model" / "r88_model.py",
            ROOT / "scripts" / "generate_dataset.py",
            ROOT / "training" / "train_r88.py",
            ROOT / "inference" / "reconstruct.py",
            ROOT / "scripts" / "launch_r88.py",
        ]
        for path in required:
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"Implementation file is missing: {path.relative_to(ROOT)}")
        trainer = ROOT / "training" / "train_r88.py"
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
        for package_name in ("r88_formal", "r88_locked_holdout"):
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
                if not isolation.get("procedural_only") or any(bool(value) for key, value in isolation.items() if key != "procedural_only"):
                    errors.append(f"Source isolation contract failed: {manifest_path.relative_to(ROOT)}")
                if audit_path.is_file() and load_json(audit_path).get("content_sha256") != manifest.get("content_sha256"):
                    errors.append(f"Manifest/audit content hash mismatch: {package_name}")
        seal_path = ROOT / "data" / "r88_locked_holdout" / "SEALED.json"
        if not seal_path.is_file():
            errors.append("Locked holdout seal is missing.")
        else:
            seal = load_json(seal_path)
            if seal.get("status") != "sealed_unread_until_checkpoint_frozen" or seal.get("training_access_allowed") or seal.get("checkpoint_selection_access_allowed"):
                errors.append("Locked holdout seal policy is invalid.")
            manifest_path = ROOT / "data" / "r88_locked_holdout" / "manifest.json"
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
        "branch": current_branch() if not errors else None,
        "authorization": str(AUTH_PATH),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
