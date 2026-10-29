from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
AUDIT_ROOT = RESULTS / "epoch100_audit"
RAW_DIR = Path(PROJECT_ROOT / CONFIG["paired_evidence"]["raw_input_dir"])
RECON_DIR = RESULTS / "reconstruction_epoch100"
R69 = Path(PROJECT_ROOT / CONFIG["paired_evidence"]["r69_root"])
PYTHON = Path(CONFIG["inference"]["python"])
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = R69 / "scripts" / "run_acm_extraction.m"


def run(command: list[str]) -> None:
    print("RUN:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def verify_reconstruction() -> None:
    audit = json.loads((RESULTS / "input_audit.json").read_text(encoding="utf-8"))
    manifest = json.loads((RECON_DIR / "inference_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("checkpoint_sha256") != audit.get("final_epoch_checkpoint_sha256"):
        raise RuntimeError("Epoch 100 重建影像不是由已鎖定的 epoch_100 權重產生。")
    if manifest.get("state_key") != "ema_state_dict" or int(manifest.get("image_count", -1)) != 12:
        raise RuntimeError("Epoch 100 推論紀錄不完整。")
    for exposure in range(13, 25):
        path = RECON_DIR / f"{exposure}.bmp"
        if not path.is_file():
            raise FileNotFoundError(path)
        with Image.open(path) as image:
            if image.size != (821, 821):
                raise RuntimeError(f"Epoch 100 重建尺寸不正確：{path}")


def outputs_complete() -> bool:
    table_dir = AUDIT_ROOT / "results" / "tables"
    primary_path = table_dir / "primary_contour_metrics.csv"
    sensitivity_path = table_dir / "acm_sensitivity_metrics.csv"
    masks = AUDIT_ROOT / "results" / "masks" / "acm_primary_masks.mat"
    if not (primary_path.is_file() and sensitivity_path.is_file() and masks.is_file()):
        return False
    primary = pd.read_csv(primary_path)
    sensitivity = pd.read_csv(sensitivity_path)
    return (
        len(primary) == 864
        and len(sensitivity) == 648
        and set(primary["method"]) == {"Raw", "R75E100"}
        and set(sensitivity["method"]) == {"Raw", "R75E100"}
        and not primary.isna().any().any()
        and not sensitivity.isna().any().any()
    )


def main() -> None:
    verify_reconstruction()
    if not outputs_complete():
        expression = (
            f"addpath('{SHARED_ACM.parent.as_posix()}'); "
            f"run_acm_extraction('{AUDIT_ROOT.as_posix()}',"
            f"'{RAW_DIR.as_posix()}',"
            f"'{RECON_DIR.as_posix()}',"
            "'R75E100');"
        )
        run([str(MATLAB), "-batch", expression])
    if not outputs_complete():
        raise RuntimeError("Epoch 100 ACM 輸出不完整。")
    run([str(PYTHON), str(ROOT / "scripts" / "analyze_epoch100_audit.py")])
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


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
