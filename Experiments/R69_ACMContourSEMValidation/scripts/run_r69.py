from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
INPUT_DIR = ROOT / "inputs" / "sem_paired_50x_exposure_stack"
RECON_ROOT = ROOT / "results" / "inference_runs"
RECON_DIR = (
    RECON_ROOT
    / "reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020"
    / CONFIG["inference"]["output_name"]
)
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
PYTHON = Path(CONFIG["inference"]["python"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print("RUN:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def prepare_inputs() -> None:
    source_dir = Path(CONFIG["sources"]["paired_optical_dir"])
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    for exposure in CONFIG["sources"]["optical_exposures"]:
        source = source_dir / f"{exposure}.bmp"
        destination = INPUT_DIR / source.name
        if not source.is_file():
            raise FileNotFoundError(source)
        if destination.exists():
            if sha256(source) != sha256(destination):
                raise RuntimeError(f"Existing input copy differs from source: {destination}")
        else:
            shutil.copy2(source, destination)
    print("Verified 12 byte-identical paired optical inputs.")


def reconstruction_complete() -> bool:
    return all((RECON_DIR / f"{exposure}.bmp").is_file() for exposure in range(13, 25))


def reconstruct() -> None:
    if reconstruction_complete():
        print("Verified 12 existing R61v16 reconstructions; inference skipped.")
        return
    model = CONFIG["model"]
    inference = CONFIG["inference"]
    command = [
        str(PYTHON),
        inference["script"],
        "--weights",
        model["checkpoint"],
        "--input-dir",
        str(INPUT_DIR),
        "--recon-root",
        str(RECON_ROOT),
        "--output-name",
        inference["output_name"],
        "--select-mode",
        "all",
        "--device",
        inference["device"],
        "--exts",
        ".bmp",
        "--psf-fitted-path",
        model["psf_fitted_path"],
        "--no-psf-from-ckpt",
        "--weak-psf-disable",
        "--psf-deconv-reg",
        str(model["psf_deconv_reg"]),
        "--psf-phys-alpha",
        str(model["psf_phys_alpha"]),
    ]
    run(command)
    if not reconstruction_complete():
        raise RuntimeError("Inference finished without all 12 expected reconstructions.")


def acm_outputs_valid() -> bool:
    summary_path = ROOT / "results" / "tables" / "acm_extraction_summary.json"
    primary_path = ROOT / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity_path = ROOT / "results" / "tables" / "acm_sensitivity_metrics.csv"
    if not (summary_path.is_file() and primary_path.is_file() and sensitivity_path.is_file()):
        return False
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("primary_record_count") != 864 or summary.get("sensitivity_record_count") != 648:
        return False
    if summary.get("seed_radius_px") != 40 or summary.get("support_radius_px") != 45:
        return False
    primary = pd.read_csv(primary_path, usecols=["truth_circularity", "pred_circularity"])
    return bool(primary.to_numpy().min() >= 0 and primary.to_numpy().max() <= 1)


def run_acm() -> None:
    run(
        [
            str(MATLAB),
            "-batch",
            f"run('{(ROOT / 'scripts' / 'run_acm_extraction.m').as_posix()}')",
        ]
    )


def run_qa() -> None:
    run(
        [
            str(MATLAB),
            "-batch",
            f"run('{(ROOT / 'scripts' / 'run_acm_qa.m').as_posix()}')",
        ]
    )
    run([str(PYTHON), str(ROOT / "scripts" / "render_acm_qa.py")])


def analyze() -> None:
    run([str(PYTHON), str(ROOT / "scripts" / "analyze_r69.py")])


def test() -> None:
    run(
        [
            str(PYTHON),
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ROOT / "tests"),
            "-p",
            "test_*.py",
            "-v",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the complete R69 SEM-ACM validation.")
    parser.add_argument(
        "--stage",
        choices=["inputs", "reconstruct", "qa", "acm", "analysis", "test", "all"],
        default="all",
    )
    parser.add_argument(
        "--force-acm",
        action="store_true",
        help="Recompute all ACM masks and sensitivity presets even when validated outputs exist.",
    )
    args = parser.parse_args()

    if args.stage in {"inputs", "all"}:
        prepare_inputs()
    if args.stage in {"reconstruct", "all"}:
        reconstruct()
    if args.stage == "qa":
        run_qa()
    if args.stage == "acm":
        run_acm()
    if args.stage == "analysis":
        analyze()
    if args.stage == "test":
        test()
    if args.stage == "all":
        if args.force_acm or not acm_outputs_valid():
            run_acm()
        else:
            print("Validated ACM tables already exist; heavy extraction skipped.")
        analyze()
        test()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
