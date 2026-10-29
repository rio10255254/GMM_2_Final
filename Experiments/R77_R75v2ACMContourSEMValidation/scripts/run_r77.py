from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
MODEL = CONFIG["model"]
EVIDENCE = CONFIG["paired_evidence"]
INFERENCE = CONFIG["inference"]
CONTOUR = CONFIG["contour"]
R69 = Path(PROJECT_ROOT / EVIDENCE["r69_root"])
RAW_DIR = Path(PROJECT_ROOT / EVIDENCE["raw_input_dir"])
BEST_RECON = Path(PROJECT_ROOT / INFERENCE["best_reconstruction_dir"])
E100_RECON = Path(PROJECT_ROOT / INFERENCE["epoch100_reconstruction_dir"])
PYTHON = Path(INFERENCE["python"])
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = R69 / "scripts" / "run_acm_extraction.m"
R76_RUNNER = Path(PROJECT_ROOT / EVIDENCE["r76_root"]) / "scripts" / "run_r76.py"


def load_shared_runner():
    spec = importlib.util.spec_from_file_location("r76_shared_runner", R76_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(R76_RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    module.CONFIG = CONFIG
    module.MODEL = MODEL
    module.EVIDENCE = EVIDENCE
    module.INFERENCE = {
        **INFERENCE,
        "reconstruction_dir": str(BEST_RECON),
        "overlap": INFERENCE["tile_overlap"],
    }
    module.R69 = R69
    module.RAW_DIR = RAW_DIR
    module.RECON_DIR = BEST_RECON
    module.PYTHON = PYTHON
    module.AUDIT_PATH = ROOT / "results" / "input_audit.json"
    return module


SHARED = load_shared_runner()


def run(command: list[str]) -> None:
    print("RUN:", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def reconstruction_complete(directory: Path, checkpoint_hash: str) -> bool:
    manifest_path = directory / "inference_manifest.json"
    expected = [directory / f"{value}.bmp" for value in EVIDENCE["optical_exposures"]]
    if not manifest_path.is_file() or not all(path.is_file() for path in expected):
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("checkpoint_sha256") != checkpoint_hash or int(manifest.get("image_count", -1)) != 12:
        return False
    return all(Image.open(path).size == (821, 821) for path in expected)


def reconstruct(checkpoint: Path, directory: Path) -> None:
    checkpoint_hash = SHARED.sha256(checkpoint)
    if reconstruction_complete(directory, checkpoint_hash):
        print(f"已確認重建影像：{directory.name}")
        return
    run(
        [
            str(PYTHON),
            str(PROJECT_ROOT / MODEL["inference_script"]),
            "--checkpoint",
            str(checkpoint),
            "--input",
            str(RAW_DIR),
            "--output",
            str(directory),
            "--device",
            INFERENCE["device"],
            "--tile-size",
            str(INFERENCE["tile_size"]),
            "--overlap",
            str(INFERENCE["tile_overlap"]),
        ]
    )
    if not reconstruction_complete(directory, checkpoint_hash):
        raise RuntimeError(f"重建輸出不完整：{directory}")


def contour_complete(validation_root: Path, method_label: str) -> bool:
    table_dir = validation_root / "results" / "tables"
    primary_path = table_dir / "primary_contour_metrics.csv"
    sensitivity_path = table_dir / "acm_sensitivity_metrics.csv"
    mask_path = validation_root / "results" / "masks" / "acm_primary_masks.mat"
    if not (primary_path.is_file() and sensitivity_path.is_file() and mask_path.is_file()):
        return False
    primary = pd.read_csv(primary_path)
    sensitivity = pd.read_csv(sensitivity_path)
    return (
        len(primary) == 864
        and len(sensitivity) == 648
        and set(primary["method"]) == {"Raw", method_label}
        and set(sensitivity["method"]) == {"Raw", method_label}
        and not primary.isna().any().any()
        and not sensitivity.isna().any().any()
    )


def contours(validation_root: Path, reconstruction: Path, method_label: str, force: bool) -> None:
    if contour_complete(validation_root, method_label) and not force:
        print(f"已確認 ACM：{method_label}")
        return
    expression = (
        f"addpath('{SHARED_ACM.parent.as_posix()}'); "
        f"run_acm_extraction('{validation_root.as_posix()}',"
        f"'{RAW_DIR.as_posix()}',"
        f"'{reconstruction.as_posix()}',"
        f"'{method_label}');"
    )
    run([str(MATLAB), "-batch", expression])
    if not contour_complete(validation_root, method_label):
        raise RuntimeError(f"ACM 輸出不完整：{method_label}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run R75-v2 paired SEM ACM validation")
    parser.add_argument("--stage", choices=["audit", "reconstruct", "contours", "analysis", "test", "all"], default="all")
    parser.add_argument("--force-contours", action="store_true")
    args = parser.parse_args()

    for path in [ROOT / "results" / "tables", ROOT / "results" / "figures", ROOT / "reports", ROOT / "tests"]:
        path.mkdir(parents=True, exist_ok=True)

    best_checkpoint, export_manifest = SHARED.find_checkpoint(0.0)
    audit = SHARED.audit_sources(best_checkpoint, export_manifest)
    if int(audit["selected_checkpoint_epoch"]) != 84:
        raise RuntimeError(f"預期第 84 輪，實際為 {audit['selected_checkpoint_epoch']}")
    final_checkpoint = Path(audit["final_epoch_checkpoint"])

    if args.stage in {"reconstruct", "all"}:
        reconstruct(best_checkpoint, BEST_RECON)
        reconstruct(final_checkpoint, E100_RECON)
    if args.stage in {"contours", "all"}:
        if not reconstruction_complete(BEST_RECON, audit["checkpoint_sha256"]):
            raise RuntimeError("第 84 輪尚未完成重建。")
        if not reconstruction_complete(E100_RECON, audit["final_epoch_checkpoint_sha256"]):
            raise RuntimeError("第 100 輪尚未完成重建。")
        contours(ROOT, BEST_RECON, CONTOUR["best_method_label"], args.force_contours)
        contours(ROOT / "results" / "epoch100_audit", E100_RECON, CONTOUR["epoch100_method_label"], args.force_contours)
    if args.stage in {"analysis", "all"}:
        run([str(PYTHON), str(ROOT / "scripts" / "analyze_r77.py")])
    if args.stage in {"test", "all"}:
        run([str(PYTHON), "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-p", "test_*.py", "-v"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
