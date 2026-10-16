from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R69_ROOT = Path(CONFIG["shared_reference"]["r69_root"])
RAW_DIR = Path(CONFIG["shared_reference"]["raw_input_dir"])
RECON_DIR = Path(CONFIG["inference"]["reconstruction_dir"])
RECON_ROOT = ROOT / "results" / "inference_runs"
PYTHON = Path(CONFIG["inference"]["python"])
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = R69_ROOT / "scripts" / "run_acm_extraction.m"


def run(command: list[str]) -> None:
    print("RUN:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def reconstruction_complete() -> bool:
    expected = [RECON_DIR / f"{exposure}.bmp" for exposure in range(13, 25)]
    if not all(path.is_file() for path in expected):
        return False
    for path in expected:
        with Image.open(path) as image:
            if image.size != (821, 821):
                return False
    return True


def reconstruct() -> None:
    if reconstruction_complete():
        print("Verified 12 existing V42E120 reconstructions; inference skipped.")
        return
    model = CONFIG["model"]
    inference = CONFIG["inference"]
    run(
        [
            str(PYTHON),
            model["inference_script"],
            "--weights",
            model["checkpoint"],
            "--input-dir",
            str(RAW_DIR),
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
        ]
    )
    if not reconstruction_complete():
        raise RuntimeError("V42 inference finished without the 12 expected 821x821 reconstructions.")


def contour_outputs_complete() -> bool:
    primary = ROOT / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity = ROOT / "results" / "tables" / "acm_sensitivity_metrics.csv"
    masks = ROOT / "results" / "masks" / "acm_primary_masks.mat"
    if not (primary.is_file() and sensitivity.is_file() and masks.is_file()):
        return False
    p = pd.read_csv(primary)
    s = pd.read_csv(sensitivity)
    return (
        len(p) == 864
        and len(s) == 648
        and set(p["method"]) == {"Raw", "V42E120"}
        and not p.isna().any().any()
        and not s.isna().any().any()
    )


def contours(force: bool = False) -> None:
    if contour_outputs_complete() and not force:
        print("Verified existing V42 contour tables; extraction skipped.")
        return
    expression = (
        f"addpath('{SHARED_ACM.parent.as_posix()}'); "
        f"run_acm_extraction('{ROOT.as_posix()}',"
        f"'{RAW_DIR.as_posix()}',"
        f"'{RECON_DIR.as_posix()}',"
        "'V42E120');"
    )
    run([str(MATLAB), "-batch", expression])
    if not contour_outputs_complete():
        raise RuntimeError("ACM extraction finished without the expected complete tables.")


def analyze() -> None:
    run([str(PYTHON), str(ROOT / "scripts" / "analyze_r70.py")])


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
    parser = argparse.ArgumentParser(description="Run the V42E120 SEM contour validation.")
    parser.add_argument(
        "--stage",
        choices=["reconstruct", "contours", "analysis", "test", "all"],
        default="all",
    )
    parser.add_argument("--force-contours", action="store_true")
    args = parser.parse_args()

    if args.stage in {"reconstruct", "all"}:
        reconstruct()
    if args.stage in {"contours", "all"}:
        contours(force=args.force_contours)
    if args.stage in {"analysis", "all"}:
        analyze()
    if args.stage in {"test", "all"}:
        test()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
