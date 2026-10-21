from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


R81_ROOT = Path(__file__).resolve().parents[1]
TRAIN_SCRIPT = Path(__file__).resolve().parent / "train_model.py"
DEFAULT_ORDER = (
    "srcnn", "vdsr", "dncnn", "unet", "edsr", "rdn",
    "rcan", "swinir", "nafnet", "restormer", "pft", "ucan",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_ORDER))
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    log_root = R81_ROOT / "results" / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    for model_key in arguments.models:
        output = R81_ROOT / "results" / "training" / model_key
        if (output / "training_summary.json").exists():
            print(f"skip completed model: {model_key}", flush=True)
            continue
        command = [
            sys.executable,
            str(TRAIN_SCRIPT),
            "--model",
            model_key,
            "--epochs",
            str(arguments.epochs),
            "--output",
            str(output),
        ]
        if arguments.resume or (output / "last_checkpoint.pth.tar").exists():
            command.append("--resume")
        environment = dict(os.environ)
        print(f"start model: {model_key}", flush=True)
        with (log_root / f"{model_key}.out.log").open("a", encoding="utf-8") as stdout_handle, (
            log_root / f"{model_key}.err.log"
        ).open("a", encoding="utf-8") as stderr_handle:
            completed = subprocess.run(
                command,
                cwd=R81_ROOT,
                env=environment,
                stdout=stdout_handle,
                stderr=stderr_handle,
                check=False,
            )
        if completed.returncode != 0:
            raise SystemExit(f"training failed for {model_key}: {completed.returncode}")
        print(f"completed model: {model_key}", flush=True)


if __name__ == "__main__":
    main()
