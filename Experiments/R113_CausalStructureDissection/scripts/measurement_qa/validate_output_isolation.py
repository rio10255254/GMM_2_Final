"""Behaviorally prove that partial runs cannot overwrite canonical results."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).with_name("corrected_ring_measurements.py")
CANONICAL = ROOT / "results" / "measurement_qa" / "corrected_frame_metrics.csv"
DEV = ROOT / "results" / "measurement_qa_dev" / "corrected_frame_metrics.csv"
OUTPUT = ROOT / "results" / "measurement_qa" / "output_isolation_validation.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    before = sha256(CANONICAL)
    subprocess.run(
        [sys.executable, str(SCRIPT), "--arm", "Raw", "--limit", "1"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    after = sha256(CANONICAL)
    canonical_rows = len(pd.read_csv(CANONICAL, encoding="utf-8-sig"))
    dev_rows = len(pd.read_csv(DEV, encoding="utf-8-sig"))
    passed = before == after and canonical_rows == 300 and dev_rows == 1
    result = {
        "status": "pass" if passed else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "canonical_sha256_before": before,
        "canonical_sha256_after": after,
        "canonical_unchanged": before == after,
        "canonical_rows": canonical_rows,
        "development_rows": dev_rows,
        "partial_run_destination": str(DEV.parent),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
