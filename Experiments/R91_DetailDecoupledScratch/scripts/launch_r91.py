"""Guarded launcher for R91 smoke or the single authorized formal run."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime


ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "training" / "train_r91.py"
VALIDATOR = ROOT / "scripts" / "validate_execution.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-kind", choices=("smoke", "formal"), default="smoke")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--max-train-batches", type=int, default=0)
    parser.add_argument("--max-validation-batches", type=int, default=0)
    args = parser.parse_args()
    if args.run_kind == "formal" and (args.max_train_batches or args.max_validation_batches):
        raise RuntimeError("The formal run cannot be shortened or partially validated")

    validation = [sys.executable, str(VALIDATOR), "--require-implementation"]
    if args.run_kind == "formal":
        validation.append("--require-formal-data")
    subprocess.run(validation, cwd=ROOT, check=True)

    lock_path = ROOT / "runs" / "launcher_logs" / f"{args.run_kind}.lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = None
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        os.write(descriptor, json.dumps({"pid": os.getpid(), "started_at": datetime.now().isoformat(), "run_kind": args.run_kind}).encode("utf-8"))
        os.close(descriptor); descriptor = None
        command = [sys.executable, "-u", str(TRAINER), "--run-kind", args.run_kind, "--device", args.device, "--num-workers", str(args.num_workers)]
        if args.max_train_batches:
            command += ["--max-train-batches", str(args.max_train_batches)]
        if args.max_validation_batches:
            command += ["--max-validation-batches", str(args.max_validation_batches)]
        return subprocess.run(command, cwd=ROOT, check=False).returncode
    finally:
        if descriptor is not None:
            os.close(descriptor)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
