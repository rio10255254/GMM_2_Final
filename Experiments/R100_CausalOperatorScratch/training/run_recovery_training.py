"""One-time, traceable recovery of the interrupted R100 formal run.

This does not register a second formal experiment. It reopens the exact run at
its last committed E36 checkpoint, records the missing legacy optimizer state,
and completes E37-E40 with the repaired epoch-boundary memory cleanup.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from train_r100 import run


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "R100_scratch_seed1000053_20260814_180143"
SOURCE = ROOT / "weights" / "formal" / "seed_1000053" / RUN_ID / "weights" / "epoch_036.pth.tar"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--no-amp", action="store_true")
    args = parser.parse_args()
    args.seed = 1000053
    args.run_kind = "formal"
    args.max_train_batches = 0
    args.max_validation_batches = 0
    args.recovery_source = str(SOURCE)
    args.recovery_reason = "E36 896px to E37 768px transition retained the prior epoch tensors, exhausted local VRAM, and stalled the first E37 forward pass"
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
