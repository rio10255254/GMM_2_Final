"""Editable one-click entry for the unique R104 formal scratch run."""
from __future__ import annotations

import argparse

from train_r104 import CONFIG, run


if __name__ == "__main__":
    raise SystemExit(run(argparse.Namespace(
        run_kind="formal", device="cuda:0", seed=int(CONFIG["training"]["seed"]), epochs=0,
        num_workers=int(CONFIG["training"]["num_workers"]), cpu_threads=int(CONFIG["training"]["cpu_threads"]),
        max_train_batches=0, no_amp=False,
    )))
