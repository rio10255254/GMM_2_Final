"""Atomically register the authorized epoch-32 R95 memory-path continuation."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "R95_scratch_seed950041_20260813_003125"
CHECKPOINT = (
    ROOT / "weights" / "formal" / "seed_950041" / RUN_ID / "weights" / "latest.pth.tar"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    registry_path = ROOT / "runs" / "formal_run_registry.json"
    active_path = ROOT / "runs" / "active_run.json"
    recovery_path = ROOT / "config" / "interruption_recovery.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    active = json.loads(active_path.read_text(encoding="utf-8"))
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    if len(registry.get("formal_runs", [])) != 1:
        raise RuntimeError("Expected exactly one formal run")
    entry = registry["formal_runs"][0]
    if str(entry.get("run_id")) != RUN_ID or str(active.get("run_id")) != RUN_ID:
        raise RuntimeError("Run id mismatch")
    if int(entry.get("completed_epoch", 0)) != 32 or int(active.get("completed_epoch", 0)) != 32:
        raise RuntimeError("The last committed epoch is not 32")
    checkpoint_hash = sha256(CHECKPOINT)
    now = datetime.now().isoformat()
    reason = (
        "Authorized execution-only large-patch memory repair after epoch 33 "
        "entered WDDM shared-memory paging; epoch 32 remained fully committed"
    )
    entry.update(
        status="interrupted_for_authorized_acceleration",
        completed_epoch=32,
        interrupted_at=now,
        interruption_reason=reason,
        last_safe_checkpoint_sha256=checkpoint_hash,
    )
    active.update(
        status="interrupted_for_authorized_acceleration",
        completed_epoch=32,
        interrupted_at=now,
        interruption_reason=reason,
        last_safe_checkpoint_sha256=checkpoint_hash,
    )
    statuses = recovery.setdefault("authorized_interruption_statuses", [])
    if "interrupted_for_authorized_acceleration" not in statuses:
        statuses.append("interrupted_for_authorized_acceleration")
    recovery.update(
        authorized_continuation_checkpoint_sha256=checkpoint_hash,
        authorized_continuation_epoch=32,
        memory_repair_authorized_at=now,
        memory_repair_reason=reason,
        memory_repair_equivalence_max_abs=0.0,
        memory_repair_benchmark_peak_reserved_gib=19.76953125,
        memory_repair_benchmark_seconds_per_batch=2.938843399984762,
    )
    write(registry_path, registry)
    write(active_path, active)
    write(recovery_path, recovery)
    print(json.dumps({
        "prepared": True,
        "run_id": RUN_ID,
        "epoch": 32,
        "checkpoint_sha256": checkpoint_hash,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
