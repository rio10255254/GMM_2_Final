from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from test_analysis_core import default_config, make_ring_image  # type: ignore
import run_single_image_analysis  # type: ignore
import refine_single_image_outputs_v2  # type: ignore


def write_bmp(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".bmp", image)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_run_analysis_writes_expected_artifacts(tmp_path):
    raw = make_ring_image(blur_sigma=3.5, noise_sigma=3.0, seed=20, gap=True)
    recon = make_ring_image(blur_sigma=1.1, noise_sigma=1.0, seed=21, gap=False)

    raw_path = tmp_path / "raw.bmp"
    recon_path = tmp_path / "r26.bmp"
    write_bmp(raw_path, raw)
    write_bmp(recon_path, recon)

    config = default_config()
    config["paths"] = {
        "raw": str(raw_path),
        "r26": str(recon_path),
    }
    config_path = tmp_path / "analysis_config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    out_dir = tmp_path / "analysis_single_image_recon"
    result = run_single_image_analysis.run_analysis(raw_path, recon_path, out_dir, config)

    assert result["tables"]["csv"].exists()
    assert result["tables"]["markdown"].exists()
    assert result["plan"].exists()
    assert result["draft"].exists()
    assert result["figures"]["overall"].exists()
    assert result["figures"]["roi"].exists()
    assert result["figures"]["profiles"].exists()
    assert result["figures"]["frequency"].exists()
    assert result["logs"]["source_selection"].exists()
    assert result["logs"]["run_summary"].exists()

    with open(result["tables"]["csv"], encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["image"] for row in rows] == ["RAW", "R26"]
    for column in [
        "edge_width_main_px",
        "edge_width_weak_px",
        "max_slope_main",
        "CNR_main",
        "CNR_weak",
        "background_std",
        "HF_ratio",
        "checkerboard_ratio",
        "edge_continuity_ratio",
        "ring_thickness_std_px",
    ]:
        assert column in rows[0]


def test_generate_v2_artifacts_rewrites_language_and_outputs_v2_files(tmp_path):
    raw = make_ring_image(blur_sigma=3.5, noise_sigma=3.0, seed=31, gap=True)
    recon = make_ring_image(blur_sigma=1.1, noise_sigma=1.0, seed=32, gap=False)

    raw_path = tmp_path / "raw.bmp"
    recon_path = tmp_path / "r26.bmp"
    write_bmp(raw_path, raw)
    write_bmp(recon_path, recon)

    config = default_config()
    config["paths"] = {"raw": str(raw_path), "r26": str(recon_path)}

    out_dir = tmp_path / "analysis_single_image_recon"
    run_single_image_analysis.run_analysis(raw_path, recon_path, out_dir, config)
    outputs = refine_single_image_outputs_v2.generate_v2_artifacts(out_dir, config)

    assert outputs["figures"]["overall_v2"].exists()
    assert outputs["figures"]["roi_v2"].exists()
    assert outputs["figures"]["profiles_v2"].exists()
    assert outputs["figures"]["frequency_v2"].exists()
    assert outputs["report_v2"].exists()
    assert outputs["draft_v2"].exists()
    assert outputs["revision_notes"].exists()

    report_text = outputs["report_v2"].read_text(encoding="utf-8")
    draft_text = outputs["draft_v2"].read_text(encoding="utf-8")
    notes_text = outputs["revision_notes"].read_text(encoding="utf-8")

    assert "邊界集中化是主證據" in report_text
    assert "CNR 提升需結合背景抑噪一起解讀" in report_text
    assert "頻域主要用來排除假高頻與說明頻帶集中" in report_text
    assert "幾何 proxy 僅保守支持應用價值" in report_text
    assert "高頻提升" not in report_text

    assert "未見明顯 checkerboard 或不自然高頻污染" in draft_text
    assert "背景高頻與噪聲成分受抑" in draft_text
    assert "ring_thickness_std_px" in draft_text
    assert "edge_continuity_ratio" in draft_text
    assert "已直接證明量測精度提升" not in draft_text

    assert "HF_ratio 在本報告中最終應被如何定位" in notes_text
    assert "edge_continuity_ratio 在本報告中最終應被如何定位" in notes_text
