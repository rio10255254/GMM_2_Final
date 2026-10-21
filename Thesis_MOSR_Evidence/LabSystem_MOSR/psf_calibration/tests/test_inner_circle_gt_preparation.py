import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "prepare_inner_circle_roi_gt.py"
CONFIG_PATH = ROOT / "configs" / "lab_optical_setup_20250605.json"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_inner_circle_roi_gt", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lab_optical_setup_records_real_image_scale():
    module = load_module()
    setup = module.load_optical_setup(CONFIG_PATH)

    assert setup["camera"]["model"] == "Basler acA2040-120um"
    assert setup["camera"]["pixel_size_um"] == 3.45
    assert setup["objective"]["magnification"] == 20
    assert setup["optical_path"]["relay_lens_magnification"] == 1.0
    assert setup["acquisition"]["binning"] == 1
    assert setup["acquisition"]["software_scaling"] == 1.0
    assert module.effective_pixel_size_um(setup) == pytest.approx(0.1725)
    assert module.target_diameter_px(setup) == pytest.approx(100.0 / 0.1725)


def test_generated_gt_uses_phi_0p1mm_inner_circle_scale(tmp_path):
    module = load_module()
    setup = module.load_optical_setup(CONFIG_PATH)
    gt = module.build_inner_circle_gt(setup)

    assert gt.shape == (901, 901)
    assert gt.dtype == np.uint8

    white_mask = gt > 200
    ys, xs = np.where(white_mask)
    width = xs.max() - xs.min() + 1
    height = ys.max() - ys.min() + 1

    assert 579 <= width <= 581
    assert 579 <= height <= 581
    assert abs(width - module.target_diameter_px(setup)) < 1.0
    assert len(np.unique(gt)) >= 2


def test_prepare_outputs_record_25_inner_circle_centers():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    centers_csv = ROOT / config["target"]["detected_inner_circle_csv"]

    rows = centers_csv.read_text(encoding="ascii").strip().splitlines()
    assert len(rows) == 26
    assert rows[0] == "index,file,x_px,y_px,r_px,bbox_w_px,bbox_h_px"


def test_generated_gt_file_matches_config_when_present():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    gt_path = ROOT / config["outputs"]["gt_path"]

    if not gt_path.exists():
        return

    img = cv2.imread(str(gt_path), cv2.IMREAD_GRAYSCALE)
    assert img is not None
    assert img.shape == (901, 901)
