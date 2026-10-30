from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "measure_r57_cd_from_template.py"


def load_module():
    spec = importlib.util.spec_from_file_location("measure_r57_cd_from_template", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_measure_candidate_reuses_template_centers_and_summarizes_radius(tmp_path: Path):
    module = load_module()
    img = np.full((128, 128), 40, np.uint8)
    cv2.circle(img, (64, 64), 20, 210, -1, lineType=cv2.LINE_AA)
    candidate = tmp_path / "candidate.bmp"
    _write_bmp(candidate, img)

    template = tmp_path / "template.csv"
    with template.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["image", "feature", "id", "x_px", "y_px", "radius_px", "clean_for_summary"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "image": "原圖",
                "feature": "圓柱",
                "id": 1,
                "x_px": 64.0,
                "y_px": 64.0,
                "radius_px": 20.0,
                "clean_for_summary": 1,
            }
        )

    reference = tmp_path / "summary.csv"
    with reference.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "image",
                "feature",
                "n",
                "radius_mean_nm",
                "sem_radius_mean_nm",
                "abs_radius_error_vs_sem_nm",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "image": "原圖",
                "feature": "圓柱",
                "n": 1,
                "radius_mean_nm": 1380.0,
                "sem_radius_mean_nm": 1380.0,
                "abs_radius_error_vs_sem_nm": 0.0,
            }
        )

    summary = module.measure_candidate(
        candidate_image=candidate,
        candidate_label="R57測試",
        template_csv=template,
        reference_summary_csv=reference,
        output_dir=tmp_path / "out",
        nm_per_px=69.0,
    )

    assert summary["candidate_label"] == "R57測試"
    assert summary["summary_rows"][0]["feature"] == "圓柱"
    assert abs(summary["summary_rows"][0]["radius_mean_nm"] - 1380.0) <= 69.0
    assert (tmp_path / "out" / "cd_measurement_summary.csv").exists()
    assert (tmp_path / "out" / "cd_measurement_per_feature.csv").exists()
    meta = json.loads((tmp_path / "out" / "measurement_meta.json").read_text(encoding="utf-8"))
    assert meta["template_csv"] == str(template)

