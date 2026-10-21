"""Freeze the unchanged measurement references and this round's evaluator."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


SCRIPTS = (
    "scripts/evaluate_real.py", "scripts/compare_measurements.py",
    "scripts/final_audit.py", "scripts/evaluation_lock.py",
)


def inventory() -> dict[str, str]:
    paths = [ROOT / x for x in SCRIPTS]
    paths.extend(p for p in (ROOT / "evaluation").rglob("*") if p.is_file() and p.suffix != ".pyc")
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in sorted(paths)}


def verify() -> dict:
    lock = load(ROOT / "config/EVALUATION_LOCK.json")
    current = inventory()
    if current != lock["files"]:
        mismatch = [key for key in set(current) | set(lock["files"]) if current.get(key) != lock["files"].get(key)]
        raise RuntimeError("Evaluation source changed: " + repr(mismatch[:10]))
    return lock


def main() -> None:
    dest = ROOT / "config/EVALUATION_LOCK.json"
    if dest.exists():
        raise FileExistsError("Evaluation lock already exists")
    files = inventory()
    save(dest, dict(created_utc=now(), method="fixed 30-scan reader and matched historical comparison for R148v2",
                    files=files))
    print("EVALUATION_LOCKED", len(files), "files", sha(dest))


if __name__ == "__main__":
    main()
