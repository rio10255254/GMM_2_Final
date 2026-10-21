from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "docs" / "operations" / "PROJECT_STORAGE_POLICY.json"
DEFAULT_REGISTRY = REPO_ROOT / "docs" / "operations" / "PROJECT_STORAGE_REGISTRY.json"
GIB = 1024**3


@dataclass
class TreeSize:
    bytes: int = 0
    files: int = 0
    errors: int = 0

    @property
    def gib(self) -> float:
        return self.bytes / GIB


def load_policy(path: Path = DEFAULT_POLICY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_with_retry(path: Path, attempts: int = 3, delay_seconds: float = 0.05) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds)
    assert last_error is not None
    raise last_error


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_free_space(free_gib: float, warning: float, critical: float) -> str:
    if free_gib < critical:
        return "CRITICAL"
    if free_gib < warning:
        return "WARN"
    return "OK"


def resolve_inside(root: Path, value: str | Path) -> Path:
    root = root.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository: {candidate}") from exc
    return candidate


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def status_starts_with(status: str, prefixes: Iterable[str]) -> bool:
    normalized = status.strip().lower()
    return any(normalized.startswith(str(prefix).strip().lower()) for prefix in prefixes)


def classify_run_marker(status: str, pid: int, process_alive: bool, policy: dict) -> str:
    """Classify a marker conservatively for storage operations.

    A marker that still declares work active but has no usable PID is not proof
    of a live process.  It is nevertheless a blocker until the process and
    outputs are reconciled.  Failed/stopped and unreadable markers are also
    unresolved rather than cleanup authorization.
    """

    if process_alive:
        return "ACTIVE"

    active_prefixes = policy.get("active_status_prefixes") or [
        "active",
        "running",
        "resuming",
        "continuing",
        "started",
        "in_progress",
    ]
    incomplete_prefixes = policy.get("incomplete_status_prefixes") or [
        "failed",
        "stopped",
        "cancelled",
        "canceled",
        "interrupted",
        "aborted",
    ]
    complete_prefixes = policy.get("complete_status_prefixes") or [
        "complete",
        "completed",
        "closed",
        "inactive",
    ]

    if status_starts_with(status, active_prefixes):
        return "STALE" if pid > 0 else "UNVERIFIED_ACTIVE"
    if status_starts_with(status, incomplete_prefixes):
        return "INCOMPLETE"
    if status_starts_with(status, complete_prefixes):
        return "INACTIVE"
    return "UNKNOWN"


def is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


def iter_files(root: Path, skip: Path | None = None) -> Iterable[Path]:
    skip_resolved = skip.resolve() if skip else None
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        dirnames[:] = [name for name in dirnames if not is_link_like(base / name)]
        for name in filenames:
            path = base / name
            if is_link_like(path):
                continue
            if skip_resolved and path.resolve() == skip_resolved:
                continue
            yield path


def measure_tree(root: Path) -> TreeSize:
    result = TreeSize()
    if not root.exists():
        return result
    if root.is_file():
        try:
            stat = root.stat()
            return TreeSize(bytes=stat.st_size, files=1)
        except OSError:
            return TreeSize(errors=1)
    for path in iter_files(root):
        try:
            result.bytes += path.stat().st_size
            result.files += 1
        except OSError:
            result.errors += 1
    return result


def parse_git_count_objects(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value.isdigit():
            result[key.strip()] = int(value)
    return result


def git_storage(root: Path) -> dict:
    proc = subprocess.run(
        ["git", "count-objects", "-v"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    parsed = parse_git_count_objects(proc.stdout)
    return {
        "ok": proc.returncode == 0,
        "loose_gib": parsed.get("size", 0) * 1024 / GIB,
        "packed_gib": parsed.get("size-pack", 0) * 1024 / GIB,
        "garbage_gib": parsed.get("size-garbage", 0) * 1024 / GIB,
        "garbage_count": parsed.get("garbage", 0),
        "stderr": proc.stderr.strip(),
    }


def find_active_runs(root: Path, policy: dict) -> list[dict]:
    root = root.resolve()
    runs: list[dict] = []
    seen_markers: set[Path] = set()
    for pattern in policy.get("active_marker_globs", []):
        for marker in root.glob(pattern):
            logical_marker = marker.absolute()
            marker = marker.resolve()
            if marker in seen_markers:
                continue
            seen_markers.add(marker)
            marker_location = {
                "marker": str(logical_marker.relative_to(root)),
                "physical_marker": str(marker),
                "external_marker": not marker.is_relative_to(root),
            }
            try:
                payload = load_json_with_retry(marker)
            except (OSError, json.JSONDecodeError) as exc:
                runs.append(
                    {
                        **marker_location,
                        "error": str(exc),
                        "marker_state": "ERROR",
                    }
                )
                continue
            try:
                pid = int(payload.get("process_id") or 0)
            except (TypeError, ValueError):
                pid = 0
            declared_status = str(payload.get("status") or "")
            alive = process_exists(pid)
            marker_state = classify_run_marker(declared_status, pid, alive, policy)
            runs.append(
                {
                    **marker_location,
                    "experiment_id": payload.get("experiment_id"),
                    "declared_status": declared_status,
                    "process_id": pid,
                    "process_alive": alive,
                    "marker_state": marker_state,
                }
            )
    return runs


def archive_storage(root: Path, policy: dict) -> dict:
    config = policy.get("archive") or {}
    archive_root_value = config.get("root")
    if not archive_root_value:
        return {"configured": False}

    archive_root = Path(archive_root_value)
    exists = archive_root.is_dir()
    usage_target = archive_root if exists else Path(archive_root.anchor)
    try:
        usage = shutil.disk_usage(usage_target)
        free_gib = usage.free / GIB
        total_gib = usage.total / GIB
    except OSError as exc:
        return {
            "configured": True,
            "root": str(archive_root),
            "exists": exists,
            "ready": False,
            "error": str(exc),
        }

    minimum_free_gib = float(config.get("minimum_free_gib") or 0)
    same_device = False
    if exists:
        try:
            same_device = archive_root.stat().st_dev == root.stat().st_dev
        except OSError:
            pass
    return {
        "configured": True,
        "root": str(archive_root),
        "exists": exists,
        "ready": exists and free_gib >= minimum_free_gib and not same_device,
        "free_gib": free_gib,
        "total_gib": total_gib,
        "minimum_free_gib": minimum_free_gib,
        "same_device_as_repository": same_device,
    }


def build_status(root: Path, policy: dict) -> dict:
    usage = shutil.disk_usage(root)
    free_gib = usage.free / GIB
    thresholds = policy["space_thresholds_gib"]
    protected = []
    for item in policy.get("protected_paths", []):
        path = resolve_inside(root, item["path"])
        protected.append(
            {
                "path": item["path"],
                "exists": path.exists(),
                "reason": item["reason"],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(root),
        "disk": {
            "free_gib": free_gib,
            "total_gib": usage.total / GIB,
            "state": classify_free_space(
                free_gib,
                float(thresholds["warning"]),
                float(thresholds["critical"]),
            ),
            "warning_gib": thresholds["warning"],
            "critical_gib": thresholds["critical"],
        },
        "git": git_storage(root),
        "archive": archive_storage(root, policy),
        "active_runs": find_active_runs(root, policy),
        "protected_paths": protected,
    }


def print_status(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    disk = payload["disk"]
    print(f"Storage state: {disk['state']}")
    print(f"D drive free: {disk['free_gib']:.2f} GiB")
    git = payload["git"]
    print(
        "Git storage: "
        f"loose={git['loose_gib']:.2f} GiB, "
        f"packed={git['packed_gib']:.2f} GiB, "
        f"garbage={git['garbage_gib']:.2f} GiB"
    )
    archive = payload.get("archive", {"configured": False})
    if archive.get("configured"):
        state = "READY" if archive.get("ready") else "NOT_READY"
        free_text = f" free={archive['free_gib']:.2f} GiB" if "free_gib" in archive else ""
        print(f"Archive root: {state} {archive['root']}{free_text}")
    else:
        print("Archive root: NOT_CONFIGURED")
    for run in payload["active_runs"]:
        print(
            "Run marker: "
            f"{run.get('experiment_id') or run['marker']} "
            f"state={run.get('marker_state', 'ERROR')} "
            f"declared={run.get('declared_status')} alive={run.get('process_alive')}"
        )
    missing = [item["path"] for item in payload["protected_paths"] if not item["exists"]]
    print(f"Protected paths: {len(payload['protected_paths']) - len(missing)} present, {len(missing)} missing")
    for path in missing:
        print(f"  MISSING: {path}")


def active_run_ids(runs: list[dict]) -> list[str]:
    return sorted(
        {
            str(run.get("experiment_id") or run.get("marker"))
            for run in runs
            if run.get("marker_state") == "ACTIVE"
        }
    )


def blocking_run_ids(runs: list[dict]) -> list[str]:
    return sorted(
        {
            str(run.get("experiment_id") or run.get("marker"))
            for run in runs
            if run.get("marker_state") != "INACTIVE"
        }
    )


def cleanup_plan(root: Path, policy: dict, runs: list[dict] | None = None) -> list[dict]:
    rows = []
    discovered_runs = runs if runs is not None else find_active_runs(root, policy)
    active_ids = active_run_ids(discovered_runs)
    blocker_ids = blocking_run_ids(discovered_runs)
    guard = policy.get("bulk_action_guard") or {}
    blocked_actions = set(guard.get("blocked_actions") or [])
    block_active = bool(guard.get("block_when_active_run", False) and blocker_ids)
    for item in policy.get("cleanup_candidates", []):
        matches = list(root.glob(item["pattern"]))
        for path in matches:
            size = measure_tree(path)
            action = item.get("action", "bulk_cleanup")
            rows.append(
                {
                    "path": str(path.relative_to(root)),
                    "kind": item["kind"],
                    "action": action,
                    "size_gib": size.gib,
                    "files": size.files,
                    "errors": size.errors,
                    "requirements": item["requirements"],
                    "blocked_by_active_run": bool(block_active and action in blocked_actions),
                    "active_runs": active_ids if block_active and action in blocked_actions else [],
                    "run_blockers": blocker_ids if block_active and action in blocked_actions else [],
                }
            )
    return rows


def validate_registry(registry: dict) -> list[str]:
    errors: list[str] = []
    allowed_tiers = set(registry.get("allowed_tiers") or [])
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, item in enumerate(registry.get("entries") or []):
        item_id = str(item.get("id") or "")
        path = str(item.get("path") or "")
        tier = str(item.get("tier") or "")
        if not item_id:
            errors.append(f"entry {index} has no id")
        elif item_id in seen_ids:
            errors.append(f"duplicate id: {item_id}")
        seen_ids.add(item_id)
        if not path:
            errors.append(f"entry {item_id or index} has no path")
        elif path in seen_paths:
            errors.append(f"duplicate path: {path}")
        seen_paths.add(path)
        if tier not in allowed_tiers:
            errors.append(f"entry {item_id or index} has invalid tier: {tier}")
    return errors


def lifecycle_audit(root: Path, policy: dict, registry: dict, measure: bool = False) -> dict:
    errors = validate_registry(registry)
    runs = find_active_runs(root, policy)
    active_ids = active_run_ids(runs)
    blocker_ids = blocking_run_ids(runs)
    guard = policy.get("bulk_action_guard") or {}
    blocked_actions = set(guard.get("blocked_actions") or [])
    block_active = bool(guard.get("block_when_active_run", False) and blocker_ids)
    rows: list[dict] = []
    for item in registry.get("entries") or []:
        external_storage = False
        try:
            path = resolve_inside(root, item["path"])
        except (KeyError, ValueError) as exc:
            # Read-only audit may inspect an explicitly registered archive
            # junction. Mutation commands retain the strict resolve_inside gate.
            try:
                logical_path = Path(os.path.abspath(root / item["path"]))
                logical_path.relative_to(root.absolute())
                physical_path = logical_path.resolve()
                declared_path = Path(item["physical_path"]).resolve()
                archive_root = Path(policy["archive"]["root"]).resolve()
                if physical_path != declared_path or not physical_path.is_relative_to(archive_root):
                    raise ValueError("Archive junction differs from registered physical_path")
                path = physical_path
                external_storage = True
            except (KeyError, ValueError, OSError):
                errors.append(str(exc))
                continue
        action = str(item.get("action") or "review")
        exists = path.exists()
        expected_exists = bool(item.get("expected_exists", True))
        row = {
            **item,
            "external_storage": external_storage,
            "exists": exists,
            "expected_exists": expected_exists,
            "presence_state": (
                "present" if exists else "removed_as_planned" if not expected_exists else "missing"
            ),
            "blocked_by_active_run": bool(block_active and action in blocked_actions),
        }
        if measure:
            size = measure_tree(path)
            row["measured_gib"] = size.gib
            row["measured_files"] = size.files
            row["measure_errors"] = size.errors
        rows.append(row)
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "active_runs": active_ids,
        "run_blockers": blocker_ids,
        "bulk_actions_blocked": block_active,
        "entries": rows,
    }


def print_lifecycle_audit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    guard_state = "BLOCKED" if payload["bulk_actions_blocked"] else "READY"
    active_text = ", ".join(payload["active_runs"]) if payload["active_runs"] else "none"
    blocker_text = ", ".join(payload["run_blockers"]) if payload["run_blockers"] else "none"
    print(f"Lifecycle registry: {payload['status']}")
    print(f"Bulk actions: {guard_state}; confirmed active runs: {active_text}")
    print(f"Run blockers requiring reconciliation: {blocker_text}")
    for error in payload["errors"]:
        print(f"ERROR: {error}")
    for row in payload["entries"]:
        size = row.get("measured_gib", row.get("size_gib_snapshot", 0.0))
        size_label = "measured" if "measured_gib" in row else "snapshot"
        state = "BLOCKED" if row["blocked_by_active_run"] else "READY"
        exists = row["presence_state"]
        print(
            f"{float(size):8.2f} GiB  {row['tier']:<11} {state:<7} {exists:<7} "
            f"{row['id']} -> {row['action']} [{size_label}]"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_manifest(source: Path, output: Path, use_hash: bool) -> int:
    source = source.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["relative_path", "size_bytes", "mtime_ns", "sha256"])
        writer.writeheader()
        for path in iter_files(source, skip=output):
            stat = path.stat()
            writer.writerow(
                {
                    "relative_path": path.relative_to(source).as_posix(),
                    "size_bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": sha256_file(path) if use_hash else "",
                }
            )
            count += 1
    return count


def verify_manifest(manifest: Path, root: Path) -> dict:
    checked = 0
    missing: list[str] = []
    mismatched: list[str] = []
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            checked += 1
            path = root / Path(row["relative_path"])
            if not path.is_file():
                missing.append(row["relative_path"])
                continue
            if path.stat().st_size != int(row["size_bytes"]):
                mismatched.append(row["relative_path"])
                continue
            expected_hash = row.get("sha256", "")
            if expected_hash and sha256_file(path) != expected_hash:
                mismatched.append(row["relative_path"])
    return {
        "status": "PASS" if not missing and not mismatched else "FAIL",
        "checked": checked,
        "missing": missing,
        "mismatched": mismatched,
    }


def scan_children(root: Path) -> list[dict]:
    rows = []
    for child in root.iterdir():
        if child.is_symlink():
            continue
        size = measure_tree(child)
        rows.append({"name": child.name, **asdict(size), "gib": size.gib})
    return sorted(rows, key=lambda item: item["bytes"], reverse=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only project storage and archive guard")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status", help="show disk, git, active-run, and protected-path status")
    status_parser.add_argument("--json", action="store_true")

    plan_parser = sub.add_parser("cleanup-plan", help="list known cleanup candidates without deleting")
    plan_parser.add_argument("--json", action="store_true")

    lifecycle_parser = sub.add_parser(
        "lifecycle-audit",
        help="show registered large paths, lifecycle tier, and active-run blockers",
    )
    lifecycle_parser.add_argument("--measure", action="store_true")
    lifecycle_parser.add_argument("--json", action="store_true")

    scan_parser = sub.add_parser("scan", help="measure each immediate child of a directory")
    scan_parser.add_argument("--root", type=Path, default=Path("."))
    scan_parser.add_argument("--json", action="store_true")

    manifest_parser = sub.add_parser("manifest", help="create an archive manifest")
    manifest_parser.add_argument("--source", type=Path, required=True)
    manifest_parser.add_argument("--output", type=Path, required=True)
    manifest_parser.add_argument("--hash", action="store_true")

    verify_parser = sub.add_parser("verify-manifest", help="verify an archive copy")
    verify_parser.add_argument("--manifest", type=Path, required=True)
    verify_parser.add_argument("--root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    policy = load_policy(args.policy.resolve())

    if args.command == "status":
        payload = build_status(repo, policy)
        print_status(payload, args.json)
        return 2 if payload["disk"]["state"] == "CRITICAL" else 0

    if args.command == "cleanup-plan":
        runs = find_active_runs(repo, policy)
        rows = cleanup_plan(repo, policy, runs)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                state = "BLOCKED" if row["blocked_by_active_run"] else "READY"
                print(
                    f"{row['size_gib']:.2f} GiB  {row['files']:>8} files  "
                    f"{row['path']}  [{row['kind']}] {state}"
                )
        return 0

    if args.command == "lifecycle-audit":
        registry = load_registry(args.registry.resolve())
        payload = lifecycle_audit(repo, policy, registry, measure=args.measure)
        print_lifecycle_audit(payload, args.json)
        return 0 if payload["status"] == "PASS" else 1

    if args.command == "scan":
        scan_root = resolve_inside(repo, args.root)
        rows = scan_children(scan_root)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(f"{row['gib']:.2f} GiB  {row['files']:>8} files  {row['name']}")
        return 0

    if args.command == "manifest":
        source = resolve_inside(repo, args.source)
        count = create_manifest(source, args.output, args.hash)
        print(f"Manifest created: {args.output.resolve()} ({count} files)")
        return 0

    if args.command == "verify-manifest":
        result = verify_manifest(args.manifest.resolve(), args.root.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 1

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
