"""Editable one-click entry point for the single formal R100 scratch run.

The values below are intentionally plain Python defaults so the file can be
opened in an IDE, adjusted, and run directly.  The trainer itself still owns
all scratch, dataset, locking and single-run safeguards.
"""
from __future__ import annotations

import argparse

from train_r100 import run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=1000053)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--no-amp", action="store_true")
    args = parser.parse_args()
    args.run_kind = "formal"
    args.max_train_batches = 0
    args.max_validation_batches = 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
