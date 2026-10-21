from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def _write_gray(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), img.astype(np.uint8))
    assert ok


def test_high_frequency_ratio_detects_grid_energy():
    import r40_micro_metrics as mm

    flat = np.full((128, 128), 128, dtype=np.uint8)
    grid = flat.copy()
    grid[:, ::8] = 230
    grid[::8, :] = 230

    assert mm.high_frequency_ratio(grid) > mm.high_frequency_ratio(flat) * 10.0


def test_summarize_reports_detail_retention_for_stage(tmp_path: Path):
    import r40_micro_metrics as mm

    data_root = tmp_path / "data"
    profile = "micro_val_unseen"
    stage = "stage_29_micro_lines_grid"
    profile_dir = data_root / profile
    manifest = {
        "profile": profile,
        "count_by_stage": {stage: 1},
        "micro_stage_families": {stage: "lines_grid"},
    }
    (profile_dir / "manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (profile_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    gt = np.full((128, 128), 40, dtype=np.uint8)
    gt[:, ::8] = 230
    pred = cv2.GaussianBlur(gt, (9, 9), 0)
    _write_gray(profile_dir / "lbl" / stage / "0000.bmp", gt)

    recon_root = tmp_path / "recon"
    out_dir = recon_root / f"reconstruct_progress_demo_in_{stage}_000000" / f"{profile}_{stage}_demo"
    _write_gray(out_dir / "0000.bmp", pred)

    summary = mm.summarize(profile, data_root, recon_root)

    row = summary["stages"][0]
    assert summary["total_count"] == 1
    assert row["stage"] == stage
    assert row["feature_family"] == "lines_grid"
    assert 0.0 < row["avg_high_frequency_retention"] < 1.0
    assert 0.0 < row["avg_edge_retention"] < 1.0
    assert row["avg_psnr"] > 0
    assert row["avg_ssim"] == pytest.approx(summary["overall_avg_ssim"])
