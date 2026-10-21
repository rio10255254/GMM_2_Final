import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validation"))
from sequence_metrics import estimate_position, summarize_sequence


def shape():
    y, x = np.mgrid[:128, :128].astype(np.float32)
    return np.exp(-3 * (((x - 68) / 25) ** 2 + ((y - 61) / 17) ** 2))


def shifted(ref, dx, dy):
    return cv2.warpAffine(ref, np.float32([[1, 0, dx], [0, 1, dy]]), ref.shape[::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def test_known_subpixel_translation():
    ref = shape()
    got = estimate_position(shifted(ref, .5, -.5), ref, (8, 8, 120, 120))
    assert got.valid
    assert np.hypot(got.x_px - .5, got.y_px + .5) < .08


def test_flat_and_shape_mismatch_are_invalid():
    ref = shape()
    flat = estimate_position(np.full_like(ref, .5), ref)
    assert not flat.valid and flat.reason == "rank_deficient_or_flat"
    mismatch = estimate_position(ref[:-1], ref)
    assert not mismatch.valid and mismatch.reason == "shape_mismatch"


def test_width_and_photometry_do_not_invent_motion():
    ref = shape()
    gain = estimate_position(np.clip(ref * 1.2 + .1, 0, 1), ref)
    width = estimate_position(cv2.GaussianBlur(ref, (0, 0), 1.2), ref)
    assert gain.valid and np.hypot(gain.x_px, gain.y_px) < .08
    assert width.valid and np.hypot(width.x_px, width.y_px) < .08


def test_sequence_summary_does_not_pool_scene_bias_as_repeatability():
    rows = [{"valid": True, "true_x_px": 0, "true_y_px": 0, "estimated_x_px": x,
             "estimated_y_px": 0, "protocol": "static_repeat", "frame_index": i}
            for i, x in enumerate([1.0, 1.1, .9])]
    summary = summarize_sequence(rows)
    assert abs(summary["bias_x_px"] - 1.0) < 1e-8
    assert summary["repeat_sd_x_px"] > 0
    rows2 = [{"valid": True, "true_x_px": 100, "true_y_px": 0, "estimated_x_px": 101,
              "estimated_y_px": 0, "protocol": "static_repeat", "frame_index": i} for i in range(3)]
    assert summarize_sequence(rows2)["repeat_sd_x_px"] == 0
