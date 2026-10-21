"""Editable one-click entry for the single formal R102 scratch training."""
from __future__ import annotations

import argparse

from train_r102 import CONFIG, run


def main() -> int:
    args = argparse.Namespace(
        run_kind="formal",
        device="cuda:0",
        seed=int(CONFIG["training"]["seed"]),
        epochs=0,
        num_workers=int(CONFIG["training"]["num_workers"]),
        cpu_threads=int(CONFIG["training"]["cpu_threads"]),
        max_train_batches=0,
        no_amp=False,
    )
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
