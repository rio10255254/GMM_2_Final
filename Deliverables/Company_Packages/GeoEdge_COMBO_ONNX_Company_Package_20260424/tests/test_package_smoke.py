from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_company_package_runs_sample_inference(tmp_path: Path) -> None:
    model_path = PACKAGE_ROOT / "model" / "geoedge_combo_body.onnx"
    config_path = PACKAGE_ROOT / "assets" / "preprocess_config.json"
    psf_path = PACKAGE_ROOT / "assets" / "psf_mean.npy"
    sample_path = PACKAGE_ROOT / "samples" / "sample_input.bmp"
    runner_path = PACKAGE_ROOT / "run_combo_onnx.py"

    assert model_path.exists()
    assert config_path.exists()
    assert psf_path.exists()
    assert sample_path.exists()
    assert runner_path.exists()

    out_dir = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            str(runner_path),
            "--input",
            str(sample_path),
            "--output",
            str(out_dir),
        ],
        cwd=str(PACKAGE_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    out_path = out_dir / sample_path.name
    assert out_path.exists()
    src = cv2.imread(str(sample_path), cv2.IMREAD_UNCHANGED)
    out = cv2.imread(str(out_path), cv2.IMREAD_UNCHANGED)
    assert src is not None
    assert out is not None
    assert out.shape == src.shape
    assert out.dtype == src.dtype
