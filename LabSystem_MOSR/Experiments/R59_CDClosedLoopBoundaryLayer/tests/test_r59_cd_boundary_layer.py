from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_r59_cd_closed_loop.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_r59_cd_closed_loop", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _synthetic_circle(*, feature: str, radius: float, size: int = 128) -> np.ndarray:
    if feature == "圓孔":
        img = np.full((size, size), 176, np.uint8)
        fg = 58
    else:
        img = np.full((size, size), 62, np.uint8)
        fg = 178
    cv2.circle(img, (size // 2, size // 2), int(round(radius)), fg, -1, lineType=cv2.LINE_AA)
    return cv2.GaussianBlur(img, (0, 0), 0.7)


def test_fit_class_radius_shifts_returns_sem_minus_measured_in_pixels():
    module = load_module()
    rows = [
        {"feature": "圓孔", "radius_nm_basler_50x": 1550.0, "sem_radius_mean_nm": 1619.0, "clean_for_summary": 1},
        {"feature": "圓孔", "radius_nm_basler_50x": 1560.0, "sem_radius_mean_nm": 1629.0, "clean_for_summary": 1},
        {"feature": "圓柱", "radius_nm_basler_50x": 1370.5, "sem_radius_mean_nm": 1336.0, "clean_for_summary": 1},
        {"feature": "圓柱", "radius_nm_basler_50x": 1380.5, "sem_radius_mean_nm": 1346.0, "clean_for_summary": 1},
    ]

    shifts = module.fit_class_radius_shifts(rows, nm_per_px=69.0)

    assert shifts["圓孔"]["shift_px"] == 1.0
    assert shifts["圓柱"]["shift_px"] == -0.5


def test_positive_shift_expands_dark_via_radius():
    module = load_module()
    img = _synthetic_circle(feature="圓孔", radius=20.0)

    before = module.estimate_radius_px(img, x_px=64.0, y_px=64.0, expected_radius_px=20.0)
    corrected = module.apply_radial_boundary_shift(
        img,
        x_px=64.0,
        y_px=64.0,
        current_radius_px=before,
        shift_px=2.0,
    )
    after = module.estimate_radius_px(corrected, x_px=64.0, y_px=64.0, expected_radius_px=20.0)

    assert after > before + 1.0


def test_negative_shift_shrinks_bright_pillar_radius():
    module = load_module()
    img = _synthetic_circle(feature="圓柱", radius=24.0)

    before = module.estimate_radius_px(img, x_px=64.0, y_px=64.0, expected_radius_px=24.0)
    corrected = module.apply_radial_boundary_shift(
        img,
        x_px=64.0,
        y_px=64.0,
        current_radius_px=before,
        shift_px=-2.0,
    )
    after = module.estimate_radius_px(corrected, x_px=64.0, y_px=64.0, expected_radius_px=24.0)

    assert after < before - 1.0


def test_run_r59_calibration_writes_outputs(tmp_path: Path):
    module = load_module()
    image_path = tmp_path / "candidate.bmp"
    img = _synthetic_circle(feature="圓孔", radius=20.0)
    cv2.imencode(".bmp", img)[1].tofile(str(image_path))
    template_rows = [
        {
            "image": "原圖",
            "feature": "圓孔",
            "id": 1,
            "x_px": 64.0,
            "y_px": 64.0,
            "radius_px": 20.0,
            "clean_for_summary": 1,
        }
    ]
    sem_refs = {"圓孔": 22.0 * 69.0}

    result = module.calibrate_image_from_rows(
        candidate_image=image_path,
        candidate_label="unit",
        template_rows=template_rows,
        sem_refs=sem_refs,
        output_dir=tmp_path / "out",
        nm_per_px=69.0,
    )

    assert Path(result["corrected_image"]).exists()
    model = json.loads(Path(result["calibration_json"]).read_text(encoding="utf-8"))
    assert model["class_shifts_px"]["圓孔"]["shift_px"] > 1.0
    assert Path(result["post_summary_csv"]).exists()
