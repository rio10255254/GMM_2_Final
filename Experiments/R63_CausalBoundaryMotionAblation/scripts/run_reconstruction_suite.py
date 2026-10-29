"""Reconstruct all frozen R63 evaluation populations from the collected checkpoints."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
INFER = EXPERIMENT_ROOT / "scripts" / "infer_r63.py"
TRAINING_MANIFEST = EXPERIMENT_ROOT / "results" / "training_manifest.json"
RECON_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "reconstructions"
SYNTH_INPUT = EXPERIMENT_ROOT / "results" / "synthetic_shift_inputs" / "50x_unseen"
STATIC_50X_INPUT = REPO_ROOT / "Thesis_MOSR_Evidence" / "20260618_100MG"

REAL_SEQUENCES = {
    "50x_x_0p5um": (
        REPO_ROOT / "Analyses" / "20260702_100MG_displacement_analysis" / "raw_inputs" / "x_0p5um" / "bmp",
        51,
    ),
    "50x_x_1um": (
        REPO_ROOT / "Analyses" / "20260702_100MG_displacement_analysis" / "raw_inputs" / "x_1um" / "bmp",
        50,
    ),
    "20x_0p5um": (
        REPO_ROOT / "Analyses" / "20260704_20x_5x_analysis" / "raw_inputs" / "20x_0p5um" / "bmp",
        50,
    ),
    "20x_1um": (
        REPO_ROOT / "Analyses" / "20260704_20x_5x_analysis" / "raw_inputs" / "20x_1um" / "bmp",
        50,
    ),
}


def count_bmp(path: Path) -> int:
    return sum(1 for _ in path.glob("*.bmp"))


def run_inference(
    *, variant: str, checkpoint: Path, input_dir: Path, output_dir: Path,
    expected: int, device: str, protection: str = "full",
) -> None:
    if count_bmp(output_dir) == expected:
        print(f"[SKIP] {output_dir} ({expected} BMP)")
        return
    if not input_dir.is_dir():
        raise FileNotFoundError(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(INFER),
        "--variant",
        variant,
        "--output-protection",
        protection,
        "--exact-output-dir",
        str(output_dir),
        "--weights",
        str(checkpoint),
        "--input-dir",
        str(input_dir),
        "--device",
        device,
        "--exts",
        ".bmp",
    ]
    subprocess.run(command, check=True, cwd=str(EXPERIMENT_ROOT))
    actual = count_bmp(output_dir)
    if actual != expected:
        raise RuntimeError(f"{output_dir}: expected {expected} BMP, found {actual}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--targets",
        default="synthetic,real,static50",
        help="Comma-separated subset of synthetic,real,static50",
    )
    parser.add_argument("--variant", default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    targets = {part.strip() for part in args.targets.split(",") if part.strip()}
    unknown = targets - {"synthetic", "real", "static50"}
    if unknown:
        raise ValueError(f"Unknown targets: {sorted(unknown)}")

    manifest = json.loads(TRAINING_MANIFEST.read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise RuntimeError("Training manifest is incomplete; collect all runs first")
    records = manifest["records"]
    if args.variant:
        records = [record for record in records if record["variant"] == args.variant]
    if args.seed is not None:
        records = [record for record in records if int(record["seed"]) == args.seed]
    if not records:
        raise RuntimeError("No matching training records")

    inventory: list[dict[str, object]] = []
    synth_expected = count_bmp(SYNTH_INPUT)
    static_expected = count_bmp(STATIC_50X_INPUT)
    for record in records:
        variant = str(record["variant"])
        seed = int(record["seed"])
        checkpoint = Path(REPO_ROOT / record["checkpoint"])
        base = RECON_ROOT / variant / f"seed{seed}"
        if "synthetic" in targets:
            out = base / "synthetic_50x_unseen"
            run_inference(
                variant=variant,
                checkpoint=checkpoint,
                input_dir=SYNTH_INPUT,
                output_dir=out,
                expected=synth_expected,
                device=args.device,
            )
            inventory.append({"variant": variant, "seed": seed, "population": "synthetic_50x_unseen", "dir": str(out), "count": synth_expected})
        if "static50" in targets:
            out = base / "static_50x_sem"
            run_inference(
                variant=variant,
                checkpoint=checkpoint,
                input_dir=STATIC_50X_INPUT,
                output_dir=out,
                expected=static_expected,
                device=args.device,
            )
            inventory.append({"variant": variant, "seed": seed, "population": "static_50x_sem", "dir": str(out), "count": static_expected})
        if "real" in targets:
            for sequence, (input_dir, expected) in REAL_SEQUENCES.items():
                out = base / sequence
                run_inference(
                    variant=variant,
                    checkpoint=checkpoint,
                    input_dir=input_dir,
                    output_dir=out,
                    expected=expected,
                    device=args.device,
                )
                inventory.append({"variant": variant, "seed": seed, "population": sequence, "dir": str(out), "count": expected})

    output = EXPERIMENT_ROOT / "results" / "evaluation" / "reconstruction_inventory.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = []
    if output.is_file():
        previous = json.loads(output.read_text(encoding="utf-8")).get("records", [])
    keyed = {
        (row["variant"], int(row["seed"]), row["population"]): row
        for row in [*previous, *inventory]
    }
    output.write_text(
        json.dumps({"records": list(keyed.values())}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
