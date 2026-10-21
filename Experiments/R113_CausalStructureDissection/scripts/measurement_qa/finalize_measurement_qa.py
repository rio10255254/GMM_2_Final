"""Aggregate all corrected-measurement QA evidence into one final record."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "results" / "measurement_qa"
TEST = ROOT / "tests" / "test_corrected_ring_measurements.py"
OUTPUT = RESULT / "final_validation.json"


def load_json(name: str) -> dict[str, object]:
    return json.loads((RESULT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    test_run = subprocess.run(
        [sys.executable, "-m", "pytest", str(TEST), "-q"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    integrity = load_json("validation.json")
    convergence = load_json("sampling_convergence.json")
    isolation = load_json("output_isolation_validation.json")
    comparison = load_json("r112_correction_comparison.json")
    frame = pd.read_csv(RESULT / "corrected_frame_metrics.csv", encoding="utf-8-sig")
    required_scopes = {
        "full_crop_high_frequency_rms_gray",
        "full_crop_low_frequency_std_gray",
        "annulus_high_frequency_rms_gray",
        "annulus_low_frequency_std_gray",
        "ring_halfmax_center_radius_px",
    }
    checks = {
        "integrity_pass": integrity.get("status") == "pass",
        "sampling_convergence_pass": convergence.get("status") == "pass",
        "partial_output_isolation_pass": isolation.get("status") == "pass",
        "r112_comparison_complete": comparison.get("status") == "complete" and comparison.get("matched_rows") == 300,
        "unit_tests_pass": test_run.returncode == 0 and "5 passed" in test_run.stdout,
        "canonical_rows_300": len(frame) == 300,
        "spatial_scopes_explicit": required_scopes.issubset(frame.columns),
    }
    artifacts = {}
    for name in (
        "analysis_summary.json",
        "corrected_arm_summary.csv",
        "corrected_frame_metrics.csv",
        "corrected_radial_profiles.csv.gz",
        "r112_correction_comparison.json",
        "sampling_convergence.json",
        "source_manifest.json",
        "validation.json",
    ):
        path = RESULT / name
        artifacts[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    passed = all(checks.values())
    result = {
        "status": "pass" if passed else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "pytest_stdout": test_run.stdout.strip(),
        "canonical_rows": int(len(frame)),
        "arms": frame.groupby("arm").size().to_dict(),
        "primary_radius": "ring_halfmax_center_radius_px",
        "retired_from_decision": "ring_peak_radius_px (diagnostic only because of tied local maxima)",
        "artifacts": artifacts,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
