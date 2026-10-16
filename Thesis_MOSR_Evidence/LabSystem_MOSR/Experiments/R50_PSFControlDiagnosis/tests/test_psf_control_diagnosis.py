from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "psf_control_diagnosis.py"


def load_module():
    spec = importlib.util.spec_from_file_location("psf_control_diagnosis", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _edge_image(blur_sigma: float) -> np.ndarray:
    image = np.zeros((128, 128), dtype=np.uint8)
    image[:, 64:] = 255
    if blur_sigma > 0:
        image = cv2.GaussianBlur(image, (0, 0), blur_sigma)
    return image


def test_edge_width_proxy_ranks_blur_strength():
    module = load_module()

    sharp = module.measure_image(_edge_image(0.0), "sharp", "sharp.bmp")
    medium = module.measure_image(_edge_image(2.0), "medium", "medium.bmp")
    wide = module.measure_image(_edge_image(4.0), "wide", "wide.bmp")

    assert sharp.transition_width_median_px < medium.transition_width_median_px
    assert medium.transition_width_median_px < wide.transition_width_median_px
    assert sharp.gradient_p99 > medium.gradient_p99 > wide.gradient_p99


def test_blend_with_clean_reduces_bads_strength():
    module = load_module()
    clean = _edge_image(0.0)
    bads_like = _edge_image(4.0)

    weak = module.blend_with_clean(clean, bads_like, alpha=0.5)
    weak_metrics = module.measure_image(weak, "weak", "weak.bmp")
    bads_metrics = module.measure_image(bads_like, "bads", "bads.bmp")

    assert weak_metrics.transition_width_median_px < bads_metrics.transition_width_median_px
    assert weak_metrics.gradient_p99 > bads_metrics.gradient_p99
