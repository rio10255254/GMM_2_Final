"""Inference-only audit of the final checkpoint's three output-protection stages."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
PACKAGE_ROOT = (
    REPO_ROOT
    / "Deliverables"
    / "Standalone_Models"
    / "V42_SoftLabelSNR_FullStandalone_20260709"
)
FINAL_CHECKPOINT = (
    PACKAGE_ROOT
    / "results"
    / "training_results"
    / "training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713"
    / "epoch_120.pth.tar"
)
INFER = EXPERIMENT_ROOT / "scripts" / "infer_r63.py"
EVALUATION_ROOT = EXPERIMENT_ROOT / "results" / "evaluation" / "output_protection"
SYNTH_INPUT = EXPERIMENT_ROOT / "results" / "synthetic_shift_inputs" / "50x_unseen"
STATIC_INPUT = REPO_ROOT / "Thesis_MOSR_Evidence" / "20260618_100MG"
MODES = ("full", "no_boundary", "no_anchor", "no_gate", "no_all")
REAL = {
    "50x_x_0p5um": (REPO_ROOT / "20260702_100MG_displacement_analysis" / "raw_inputs" / "x_0p5um" / "bmp", 51),
    "50x_x_1um": (REPO_ROOT / "20260702_100MG_displacement_analysis" / "raw_inputs" / "x_1um" / "bmp", 50),
    "20x_0p5um": (REPO_ROOT / "20260704_20x_5x_analysis" / "raw_inputs" / "20x_0p5um" / "bmp", 50),
    "20x_1um": (REPO_ROOT / "20260704_20x_5x_analysis" / "raw_inputs" / "20x_1um" / "bmp", 50),
}


def count_bmp(path: Path) -> int:
    return sum(1 for _ in path.glob("*.bmp"))


def infer(mode: str, input_dir: Path, output_dir: Path, expected: int, device: str) -> None:
    if count_bmp(output_dir) == expected:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(INFER),
            "--variant",
            "final_reference",
            "--output-protection",
            mode,
            "--exact-output-dir",
            str(output_dir),
            "--weights",
            str(FINAL_CHECKPOINT),
            "--input-dir",
            str(input_dir),
            "--device",
            device,
            "--exts",
            ".bmp",
        ],
        cwd=str(EXPERIMENT_ROOT),
        check=True,
    )
    if count_bmp(output_dir) != expected:
        raise RuntimeError(f"{output_dir}: incomplete inference")


def metric(command: list[str], sentinel: Path) -> dict[str, object]:
    if sentinel.is_file():
        return {"status": "complete", "sentinel": str(sentinel), "exit_code": 0}
    try:
        subprocess.run(command, cwd=str(EXPERIMENT_ROOT), check=True)
    except subprocess.CalledProcessError as exc:
        return {
            "status": "invalid",
            "sentinel": str(sentinel),
            "exit_code": int(exc.returncode),
            "reason": "locked evaluator rejected this inference-only output",
        }
    if not sentinel.is_file():
        raise RuntimeError(f"Missing metric output: {sentinel}")
    return {"status": "complete", "sentinel": str(sentinel), "exit_code": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    if not FINAL_CHECKPOINT.is_file():
        raise FileNotFoundError(FINAL_CHECKPOINT)
    inventory: list[dict[str, object]] = []
    for mode in MODES:
        root = EVALUATION_ROOT / mode
        recon = root / "reconstructions"
        infer(mode, SYNTH_INPUT, recon / "synthetic_50x_unseen", count_bmp(SYNTH_INPUT), args.device)
        infer(mode, STATIC_INPUT, recon / "static_50x_sem", count_bmp(STATIC_INPUT), args.device)
        for sequence, (input_dir, expected) in REAL.items():
            infer(mode, input_dir, recon / sequence, expected, args.device)

        metrics = root / "metrics"
        synthetic_out = metrics / "synthetic_shift"
        statuses: dict[str, dict[str, object]] = {}
        statuses["synthetic_shift"] = metric(
            [sys.executable, str(EXPERIMENT_ROOT / "scripts" / "evaluate_synthetic_shifts.py"), "--recon-dir", str(recon / "synthetic_50x_unseen"), "--method", mode, "--output-dir", str(synthetic_out)],
            synthetic_out / "synthetic_shift_summary.csv",
        )
        static_out = metrics / "static_cd"
        statuses["static_cd"] = metric(
            [sys.executable, str(EXPERIMENT_ROOT / "scripts" / "evaluate_static_cd.py"), "--variant", mode, "--seed", "0", "--recon-root", str(recon), "--output-dir", str(static_out)],
            static_out / "static_cd_summary.csv",
        )
        displacement_out = metrics / "displacement"
        statuses["displacement"] = metric(
            [sys.executable, str(EXPERIMENT_ROOT / "scripts" / "evaluate_displacement.py"), "--variant", mode, "--seed", "0", "--recon-root", str(recon), "--output-dir", str(displacement_out)],
            displacement_out / "displacement_summary_top30.csv",
        )
        inventory.append({
            "mode": mode,
            "reconstruction_root": str(recon),
            "metric_root": str(metrics),
            "metric_status": statuses,
        })
    (EVALUATION_ROOT / "inventory.json").write_text(
        json.dumps({"checkpoint": str(FINAL_CHECKPOINT), "records": inventory}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
