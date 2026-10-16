"""Run the frozen synthetic-shift, static-CD, and real-displacement metrics."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_MANIFEST = EXPERIMENT_ROOT / "results" / "training_manifest.json"
RECON_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "reconstructions"
METRIC_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "metrics"
SCRIPTS = EXPERIMENT_ROOT / "scripts"


def run_if_missing(command: list[str], sentinel: Path) -> None:
    if sentinel.is_file():
        print(f"[SKIP] {sentinel}")
        return
    subprocess.run(command, cwd=str(EXPERIMENT_ROOT), check=True)
    if not sentinel.is_file():
        raise RuntimeError(f"Metric command did not create {sentinel}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    manifest = json.loads(TRAINING_MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise RuntimeError("Training manifest is incomplete")
    records = manifest["records"]
    if args.variant:
        records = [record for record in records if record["variant"] == args.variant]
    if args.seed is not None:
        records = [record for record in records if int(record["seed"]) == args.seed]
    if not records:
        raise RuntimeError("No matching records")

    for record in records:
        variant = str(record["variant"])
        seed = int(record["seed"])
        recon = RECON_ROOT / variant / f"seed{seed}"
        output = METRIC_ROOT / variant / f"seed{seed}"
        synthetic_out = output / "synthetic_shift"
        run_if_missing(
            [
                sys.executable,
                str(SCRIPTS / "evaluate_synthetic_shifts.py"),
                "--recon-dir",
                str(recon / "synthetic_50x_unseen"),
                "--method",
                variant,
                "--output-dir",
                str(synthetic_out),
            ],
            synthetic_out / "synthetic_shift_summary.csv",
        )
        static_out = output / "static_cd"
        run_if_missing(
            [
                sys.executable,
                str(SCRIPTS / "evaluate_static_cd.py"),
                "--variant",
                variant,
                "--seed",
                str(seed),
                "--recon-root",
                str(recon),
                "--output-dir",
                str(static_out),
            ],
            static_out / "static_cd_summary.csv",
        )
        displacement_out = output / "displacement"
        run_if_missing(
            [
                sys.executable,
                str(SCRIPTS / "evaluate_displacement.py"),
                "--variant",
                variant,
                "--seed",
                str(seed),
                "--recon-root",
                str(recon),
                "--output-dir",
                str(displacement_out),
            ],
            displacement_out / "displacement_summary_top30.csv",
        )


if __name__ == "__main__":
    main()
