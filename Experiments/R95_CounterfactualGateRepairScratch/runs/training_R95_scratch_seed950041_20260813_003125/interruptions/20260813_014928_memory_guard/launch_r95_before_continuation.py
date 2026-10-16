"""Fail-closed launcher for the one R95 formal scratch run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=4)
    args = parser.parse_args()
    design = json.loads((ROOT / "config" / "experiment_design.json").read_text(encoding="utf-8"))
    calibration = json.loads((ROOT / "config" / "gpu_batch_calibration.json").read_text(encoding="utf-8"))
    if design.get("formal_training_authorized") is not True or calibration.get("passed") is not True:
        raise RuntimeError("R95 formal launch prerequisites are not complete")
    audit = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_locked_design.py")],
        cwd=ROOT, check=False,
    )
    if audit.returncode:
        raise RuntimeError("R95 design audit failed")
    command = [
        sys.executable, "-u", str(ROOT / "training" / "train_r95.py"),
        "--run-kind", "formal", "--device", args.device,
        "--num-workers", str(args.num_workers),
    ]
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())

