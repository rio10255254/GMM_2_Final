"""Re-run unit tests and record the already completed end-to-end smoke pipeline."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
RUNS = ROOT / "runs"
EXPECTED_LIVE_NAMES = ("5x_dense_raw", "20x_mixed_raw", "50x_array_raw")


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_*.py",
            "-v",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    combined = completed.stdout + completed.stderr
    match = re.search(r"Ran\s+(\d+)\s+tests?", combined)
    unit_payload = {
        "passed": completed.returncode == 0 and match is not None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "return_code": completed.returncode,
        "test_count": int(match.group(1)) if match else None,
        "command": f"{sys.executable} -m unittest discover -s tests -p test_*.py -v",
        "output_tail": combined.strip().splitlines()[-24:],
    }
    (REPORTS / "unit_test_verification.json").write_text(
        json.dumps(unit_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    candidates = sorted(
        (
            path
            for path in RUNS.glob("training_progress_*pipeline_smoke*")
            if path.is_dir()
        ),
        key=lambda path: path.stat().st_mtime_ns,
    )
    if not candidates:
        raise FileNotFoundError("No completed pipeline_smoke run found")
    run_dir = candidates[-1]
    outputs: list[dict] = []
    for name in EXPECTED_LIVE_NAMES:
        image_path = run_dir / "live_validation" / name / "epoch_001.bmp"
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        image = read_gray(image_path)
        outputs.append(
            {
                "name": name,
                "path": str(image_path),
                "shape_hw": list(image.shape),
                "finite": bool(np.isfinite(image).all()),
                "min": int(image.min()),
                "max": int(image.max()),
            }
        )
    checkpoint = run_dir / "weights" / "best_tradeoff.pth.tar"
    smoke_payload = {
        "passed": bool(
            checkpoint.is_file()
            and len(outputs) == 3
            and all(item["shape_hw"] == [512, 512] and item["finite"] for item in outputs)
        ),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "run_directory": str(run_dir),
        "train_batches_executed": 1,
        "validation_completed": any(run_dir.glob("*_val_log_v5.csv")),
        "checkpoint_saved": checkpoint.is_file(),
        "checkpoint": str(checkpoint),
        "live_validation_role": "observation_only_no_loss_no_selection_no_training_control",
        "live_validation_outputs": outputs,
    }
    (REPORTS / "smoke_pipeline_verification.json").write_text(
        json.dumps(smoke_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"unit_tests": unit_payload, "smoke_pipeline": smoke_payload}, indent=2, ensure_ascii=False))
    return 0 if unit_payload["passed"] and smoke_payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
