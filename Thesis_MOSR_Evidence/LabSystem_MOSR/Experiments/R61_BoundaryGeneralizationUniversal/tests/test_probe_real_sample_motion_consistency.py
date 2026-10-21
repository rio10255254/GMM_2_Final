from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "probe_real_sample_motion_consistency.py"


def load_module():
    spec = importlib.util.spec_from_file_location("probe_real_sample_motion_consistency", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _texture(size: int = 96) -> np.ndarray:
    img = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(img, (30, 28), 10, 180, -1)
    cv2.rectangle(img, (52, 44), (74, 62), 230, -1)
    cv2.line(img, (12, 80), (84, 70), 130, 3)
    return img


def test_estimate_pair_shift_detects_vertical_translation():
    module = load_module()
    img0 = _texture()
    matrix = np.float32([[1, 0, 1.5], [0, 1, 3.0]])
    img1 = cv2.warpAffine(img0, matrix, img0.shape[::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    shift = module.estimate_pair_shift(img0, img1)

    assert abs(shift["dx"] - 1.5) < 0.25
    assert abs(shift["dy"] - 3.0) < 0.25
    assert shift["response"] > 0.2


def test_compute_case_motion_stats_reports_all_and_tail_steps(tmp_path: Path):
    module = load_module()
    folder = tmp_path / "case" / "bmp"
    folder.mkdir(parents=True)
    base = _texture()
    for idx, dy in enumerate([0.0, 2.0, 4.0, 6.0]):
        matrix = np.float32([[1, 0, 0.0], [0, 1, dy]])
        img = cv2.warpAffine(base, matrix, base.shape[::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        assert cv2.imwrite(str(folder / f"frame_{idx:02d}.bmp"), img)

    stats = module.compute_case_motion_stats("case", folder)

    assert stats["n_frames"] == 4
    assert stats["n_steps"] == 3
    assert abs(stats["median_dy_px"] - 2.0) < 0.25
    assert stats["tail_n_steps"] == 2
    assert abs(stats["tail_median_dy_px"] - 2.0) < 0.25


def test_load_cases_from_tsv_keeps_image_folder_and_case_name(tmp_path: Path):
    module = load_module()
    image_folder = tmp_path / "images"
    image_folder.mkdir()
    table = tmp_path / "paths_for_gmf_tool.tsv"
    table.write_text(
        "case\trole\timage_folder\tscore_folder\timage_count\tnote\n"
        f"00_raw\trole\t{image_folder}\tscore\t2\tnote\n",
        encoding="utf-8",
    )

    cases = module.load_cases_from_tsv(table)

    assert len(cases) == 1
    assert cases[0]["case"] == "00_raw"
    assert cases[0]["image_folder"] == str(image_folder)
