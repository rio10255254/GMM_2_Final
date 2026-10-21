"""R87 manual launcher.

Edit the values in MANUAL SETTINGS and press Run.  This launcher can build the
formal dataset and start one scratch run, but it cannot load or resume weights.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


# MANUAL SETTINGS
ACTION = "train"  # "build_data", "smoke", or "train"
DEVICE = "cuda:0"
SEED = 870031
EPOCHS = 100
NUM_WORKERS = 4


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
GENERATOR = EXPERIMENT_DIR / "scripts" / "generate_dataset.py"
TRAINER = EXPERIMENT_DIR / "training" / "train_r87.py"


def load_trainer():
    spec = importlib.util.spec_from_file_location("r87_trainer_launcher", TRAINER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load trainer: {TRAINER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    python = sys.executable
    if ACTION == "build_data":
        return subprocess.call([python, str(GENERATOR), "--profile", "formal", "--full-hash-audit"])
    trainer = load_trainer()
    trainer.CFG.MODEL_NAME = f"TileNativeMOSR_R87_scratch_seed{SEED}"
    trainer.MODEL_NAME_BASE = trainer.CFG.MODEL_NAME  # ensure artifact identity
    arguments = [
        str(TRAINER), "--device", DEVICE, "--seed", str(SEED), "--epochs", str(EPOCHS),
        "--num-workers", str(NUM_WORKERS),
    ]
    if ACTION == "smoke":
        arguments.extend([
            "--epochs", "1", "--max-train-batches", "1",
            "--max-validation-batches", "1", "--run-kind", "smoke",
        ])
    elif ACTION != "train":
        raise ValueError("ACTION must be build_data, smoke, or train")
    old_argv = sys.argv
    try:
        sys.argv = arguments
        return int(trainer.main())
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    raise SystemExit(main())
