from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
PYTHON = Path(r"C:\Users\Rio\anaconda3\python.exe")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bmp_names(directory: Path) -> list[str]:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    return sorted(p.name for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".bmp")


def audit_inputs() -> dict:
    expected_names = [f"{image_id:04d}.bmp" for image_id in CONFIG["sources"]["image_ids"]]
    source_counts: dict[str, int] = {}
    for key in ("truth_dir", "raw_dir", "combo_dir", "r61_dir"):
        names = bmp_names(Path(CONFIG["sources"][key]))
        if names != expected_names:
            missing = sorted(set(expected_names) - set(names))
            extra = sorted(set(names) - set(expected_names))
            raise RuntimeError(f"{key} file mismatch; missing={missing}, extra={extra}")
        source_counts[key] = len(names)

    upstream_path = Path(CONFIG["upstream_experiment"]) / "results" / "input_audit.json"
    upstream = json.loads(upstream_path.read_text(encoding="utf-8"))
    if not upstream.get("independent_of_r61_training"):
        raise RuntimeError("Upstream R71 independence audit did not pass")
    if upstream.get("checkpoint_sha256") != CONFIG["model"]["checkpoint_sha256"]:
        raise RuntimeError("Frozen checkpoint identity differs from R71")
    checkpoint = Path(upstream["checkpoint"])
    current_hash = sha256(checkpoint)
    if current_hash != CONFIG["model"]["checkpoint_sha256"]:
        raise RuntimeError("Checkpoint file hash changed")

    audit = {
        "experiment_id": CONFIG["experiment_id"],
        "feature_family": CONFIG["sources"]["feature_family"],
        "image_ids": CONFIG["sources"]["image_ids"],
        "independent_image_count": len(expected_names),
        "source_counts": source_counts,
        "source_filenames_match": True,
        "upstream_r71_audit": str(upstream_path),
        "independent_of_r61_training": True,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": current_hash,
        "acm_initialization_uses_truth_shape": CONFIG["acm"]["initialization_uses_truth_shape"],
        "scale_fitting": CONFIG["acm"]["scale_fitting"],
        "rotation_fitting": CONFIG["acm"]["rotation_fitting"],
        "primary_alignment": CONFIG["acm"]["primary_alignment"],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "input_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def run_acm(force: bool) -> None:
    required = [
        TABLES / "primary_contour_metrics.csv",
        TABLES / "acm_sensitivity_metrics.csv",
        RESULTS / "masks" / "acm_primary_masks.mat",
    ]
    if not force and all(path.exists() and path.stat().st_size > 0 for path in required):
        print("Reusing frozen ACM masks and measurements")
        return
    if not MATLAB.exists():
        raise FileNotFoundError(MATLAB)
    script_dir = str(ROOT / "scripts").replace("'", "''")
    experiment_root = str(ROOT).replace("'", "''")
    expression = f"addpath('{script_dir}'); run_acm_extraction('{experiment_root}')"
    subprocess.run([str(MATLAB), "-batch", expression], check=True, cwd=ROOT)


def run_analysis() -> None:
    subprocess.run([str(PYTHON), str(ROOT / "scripts" / "analyze_r72.py")], check=True, cwd=ROOT)


def run_tests() -> None:
    subprocess.run(
        [str(PYTHON), "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        check=True,
        cwd=ROOT,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen R72 ACM contour validation")
    parser.add_argument("--stage", choices=("audit", "acm", "analysis", "test", "all"), default="all")
    parser.add_argument("--force-acm", action="store_true", help="Re-extract every ACM mask")
    args = parser.parse_args()

    if args.stage in ("audit", "all"):
        audit_inputs()
    if args.stage in ("acm", "all"):
        run_acm(args.force_acm)
    if args.stage in ("analysis", "all"):
        run_analysis()
    if args.stage in ("test", "all"):
        run_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
