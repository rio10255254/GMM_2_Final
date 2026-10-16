"""Atomic single-formal-run registry for R114.

This module never launches a trainer.  Launchers and trainers call it to reserve,
attach, heartbeat, and close exactly one formal run.  The exclusive lock file is
the race-proof source of truth; JSON files are the human/monitoring view.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ACTIVE_STATUSES = {"reserved", "running", "stopping"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def paths(root: Path) -> dict[str, Path]:
    run_root = root / "runs"
    return {
        "runs": run_root,
        "lock": run_root / "formal_run.lock",
        "active": run_root / "active_run.json",
        "registry": run_root / "formal_run_registry.json",
    }


def empty_registry() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "active_run_id": None, "formal_runs": []}


def load_registry(path: Path) -> dict[str, Any]:
    registry = read_json(path, empty_registry())
    if int(registry.get("schema_version", -1)) != SCHEMA_VERSION:
        raise RuntimeError("Unsupported formal run registry schema")
    registry.setdefault("formal_runs", [])
    registry.setdefault("active_run_id", None)
    return registry


def locate(registry: dict[str, Any], run_id: str) -> dict[str, Any]:
    matches = [item for item in registry["formal_runs"] if item.get("run_id") == run_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one registry entry for {run_id}, found {len(matches)}")
    return matches[0]


def reserve(root: Path, run_id: str, total_epochs: int, owner_pid: int) -> dict[str, Any]:
    if not run_id or any(character in run_id for character in "\\/:*?\"<>|"):
        raise ValueError("run_id is empty or contains a Windows-invalid character")
    target = paths(root)
    target["runs"].mkdir(parents=True, exist_ok=True)
    lock_payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "owner_pid": int(owner_pid),
        "host": socket.gethostname(),
        "reserved_at": now(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(target["lock"], flags)
    except FileExistsError as error:
        existing = read_json(target["lock"], {"run_id": "unknown"})
        raise RuntimeError(f"A formal run is already reserved: {existing.get('run_id')}") from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(lock_payload, handle, ensure_ascii=False, indent=2)
        registry = load_registry(target["registry"])
        if registry.get("active_run_id") is not None:
            raise RuntimeError(f"Registry already names an active run: {registry['active_run_id']}")
        if any(item.get("run_id") == run_id for item in registry["formal_runs"]):
            raise RuntimeError(f"run_id has already been used: {run_id}")
        run_dir = target["runs"] / run_id
        run_dir.mkdir(parents=False, exist_ok=False)
        record = {
            **lock_payload,
            "formal": True,
            "scratch": True,
            "status": "reserved",
            "trainer_pid": None,
            "total_epochs": int(total_epochs),
            "latest_epoch": 0,
            "run_dir": str(run_dir.resolve()),
            "updated_at": now(),
        }
        registry["active_run_id"] = run_id
        registry["formal_runs"].append(record)
        atomic_json(target["registry"], registry)
        atomic_json(target["active"], record)
        return record
    except Exception:
        target["lock"].unlink(missing_ok=True)
        raise


def update_active(root: Path, run_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    target = paths(root)
    lock = read_json(target["lock"])
    if not lock or lock.get("run_id") != run_id:
        raise RuntimeError(f"Formal lock does not belong to {run_id}")
    registry = load_registry(target["registry"])
    if registry.get("active_run_id") != run_id:
        raise RuntimeError(f"Registry active run is not {run_id}")
    record = locate(registry, run_id)
    record.update(changes)
    record["updated_at"] = now()
    atomic_json(target["registry"], registry)
    atomic_json(target["active"], record)
    return record


def close(root: Path, run_id: str, status: str, message: str | None) -> dict[str, Any]:
    if status not in {"complete", "failed", "cancelled"}:
        raise ValueError(status)
    target = paths(root)
    record = update_active(root, run_id, {
        "status": status,
        "finished_at": now(),
        "message": message,
    })
    registry = load_registry(target["registry"])
    registry["active_run_id"] = None
    atomic_json(target["registry"], registry)
    atomic_json(target["active"], record)
    lock = read_json(target["lock"])
    if not lock or lock.get("run_id") != run_id:
        raise RuntimeError("Lock changed while closing formal run")
    target["lock"].unlink()
    return record


def inspect(root: Path) -> dict[str, Any]:
    target = paths(root)
    registry = load_registry(target["registry"])
    active = read_json(target["active"])
    lock = read_json(target["lock"])
    active_records = [item for item in registry["formal_runs"] if item.get("status") in ACTIVE_STATUSES]
    checks = {
        "at_most_one_active_registry_record": len(active_records) <= 1,
        "registry_active_matches_record": (
            registry.get("active_run_id") is None and not active_records
        ) or (
            len(active_records) == 1 and registry.get("active_run_id") == active_records[0].get("run_id")
        ),
        "lock_matches_registry": (
            registry.get("active_run_id") is None and lock is None
        ) or (
            lock is not None and lock.get("run_id") == registry.get("active_run_id")
        ),
        "active_view_matches_registry": active is None or active.get("run_id") in {
            registry.get("active_run_id"),
            *(item.get("run_id") for item in registry["formal_runs"] if item.get("status") not in ACTIVE_STATUSES),
        },
        "all_formal_runs_are_scratch": all(bool(item.get("scratch")) for item in registry["formal_runs"]),
        "run_ids_unique": len({item.get("run_id") for item in registry["formal_runs"]}) == len(registry["formal_runs"]),
    }
    return {
        "status": "complete" if all(checks.values()) else "failed",
        "checks": checks,
        "active_run_id": registry.get("active_run_id"),
        "formal_run_count": len(registry["formal_runs"]),
        "lock": lock,
        "active": active,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="R114 exclusive formal-run registry")
    parser.add_argument("--root", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    reserve_parser = subparsers.add_parser("reserve")
    reserve_parser.add_argument("--run-id", required=True)
    reserve_parser.add_argument("--total-epochs", type=int, required=True)
    reserve_parser.add_argument("--pid", type=int, default=os.getpid())

    attach_parser = subparsers.add_parser("attach")
    attach_parser.add_argument("--run-id", required=True)
    attach_parser.add_argument("--trainer-pid", type=int, required=True)

    heartbeat_parser = subparsers.add_parser("heartbeat")
    heartbeat_parser.add_argument("--run-id", required=True)
    heartbeat_parser.add_argument("--epoch", type=int, required=True)
    heartbeat_parser.add_argument("--checkpoint", default="")

    for name in ("complete", "fail", "cancel"):
        close_parser = subparsers.add_parser(name)
        close_parser.add_argument("--run-id", required=True)
        close_parser.add_argument("--message", default="")
    subparsers.add_parser("inspect")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    try:
        if args.command == "reserve":
            payload = reserve(root, args.run_id, args.total_epochs, args.pid)
        elif args.command == "attach":
            payload = update_active(root, args.run_id, {"status": "running", "trainer_pid": args.trainer_pid, "started_at": now()})
        elif args.command == "heartbeat":
            payload = update_active(root, args.run_id, {"status": "running", "latest_epoch": args.epoch, "latest_checkpoint": args.checkpoint or None})
        elif args.command in {"complete", "fail", "cancel"}:
            final_status = {"complete": "complete", "fail": "failed", "cancel": "cancelled"}[args.command]
            payload = close(root, args.run_id, final_status, args.message or None)
        else:
            payload = inspect(root)
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
        return 0 if payload.get("status") != "failed" or args.command == "fail" else 1
    except Exception as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False), file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
