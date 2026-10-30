from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_step_sequence_motion.py"


def load_module():
    spec = importlib.util.spec_from_file_location("probe_step_sequence_motion", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _texture(size: int = 128) -> np.ndarray:
    img = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(img, (36, 34), 12, 180, -1)
    cv2.rectangle(img, (70, 62), (96, 86), 230, -1)
    cv2.line(img, (15, 104), (110, 92), 130, 3)
    return img


def _shift(img: np.ndarray, dx: float, dy: float = 0.0) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, matrix, img.shape[::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def _write_manifest(path: Path, image_dir: Path, positions: list[int]) -> None:
    fieldnames = [
        "selected_step_index",
        "position_index",
        "commanded_um_from_start",
        "rep0_index",
        "rep0_file",
        "rep0_path",
        "rep1_index",
        "rep1_file",
        "rep1_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for step_index, position in enumerate(positions):
            writer.writerow(
                {
                    "selected_step_index": step_index,
                    "position_index": position,
                    "commanded_um_from_start": float(step_index),
                    "rep0_index": step_index * 2,
                    "rep0_file": f"pos_{position:03d}_a.bmp",
                    "rep0_path": str(image_dir / f"pos_{position:03d}_a.bmp"),
                    "rep1_index": step_index * 2 + 1,
                    "rep1_file": f"pos_{position:03d}_b.bmp",
                    "rep1_path": str(image_dir / f"pos_{position:03d}_b.bmp"),
                }
            )


def test_compute_step_case_stats_reports_repeatability_and_one_um_steps(tmp_path: Path):
    module = load_module()
    image_dir = tmp_path / "raw"
    image_dir.mkdir()
    manifest = tmp_path / "selected_1um_positions.csv"
    positions = [0, 10, 20]
    _write_manifest(manifest, image_dir, positions)
    base = _texture()
    for step_index, position in enumerate(positions):
        img = _shift(base, dx=2.0 * step_index)
        assert cv2.imwrite(str(image_dir / f"pos_{position:03d}_a.bmp"), img)
        assert cv2.imwrite(str(image_dir / f"pos_{position:03d}_b.bmp"), img)

    stats = module.compute_step_case_stats("raw", image_dir, manifest)

    assert stats["selected_position_count"] == 3
    assert stats["repeat_pair_count"] == 3
    assert stats["step_pair_count"] == 4
    assert stats["repeat_median_mag_px"] < 0.2
    assert abs(stats["step_median_dx_px"] - 2.0) < 0.25
    assert stats["step_std_dx_px"] < 0.25
    assert stats["replicate_stats"]["0"]["step_pair_count"] == 2
    assert stats["replicate_stats"]["1"]["step_pair_count"] == 2


def test_step_gate_fails_when_candidate_worsens_step_std(tmp_path: Path):
    module = load_module()
    summary = {
        "cases": [
            {"case": "raw", "step_std_dx_px": 0.05, "repeat_median_mag_px": 0.02},
            {"case": "candidate", "step_std_dx_px": 0.08, "repeat_median_mag_px": 0.02},
        ]
    }

    gate = module.evaluate_step_gate(
        summary,
        baseline_case="raw",
        candidate_case="candidate",
        metric="step_std_dx_px",
        tolerance_px=0.0,
    )

    assert gate["pass"] is False
    assert gate["delta"] > 0
