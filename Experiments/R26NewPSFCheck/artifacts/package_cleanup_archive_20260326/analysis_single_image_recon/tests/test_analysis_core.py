from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import analysis_core  # type: ignore


def default_config() -> dict:
    return {
        "gray_display": [0, 255],
        "roi_size": 64,
        "profile": {
            "avg_lines": 11,
            "smooth_window": 5,
            "transition_levels": [0.1, 0.9],
            "half_length_px": 36,
            "foreground_offsets_px": [8, 18],
            "background_offsets_px": [8, 18],
        },
        "fft": {
            "use_hann": True,
            "crop_margin_px": 28,
            "radial_hf_band": [0.35, 0.60],
            "radial_total_band": [0.05, 0.60],
            "checkerboard_corner_threshold": 0.80,
            "checkerboard_total_hf_band": [0.35, 0.70],
        },
        "geometry": {
            "num_angles": 180,
            "edge_search_half_window_px": 10,
            "gradient_valid_quantile": 0.35,
            "sampling_padding_px": 18,
        },
        "roi_override": {
            "main_edge": None,
            "defect": None,
            "weak_edge": None,
            "background": None,
        },
    }


def make_ring_image(
    *,
    shape: tuple[int, int] = (256, 256),
    center: tuple[int, int] = (128, 150),
    inner_r: int = 56,
    outer_r: int = 76,
    blur_sigma: float = 3.2,
    noise_sigma: float = 3.0,
    gap: bool = False,
    checkerboard: bool = False,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.indices(shape)
    cx, cy = center
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    theta = np.arctan2(yy - cy, xx - cx)

    img = np.full(shape, 132.0, dtype=np.float32)
    img[rr < inner_r] = 136.0
    annulus = (rr >= inner_r) & (rr <= outer_r)
    img[annulus] = 225.0

    defect_mask = annulus & (theta > 0.55) & (theta < 0.82)
    img[defect_mask] = 176.0

    weak_zone = annulus & (theta < -2.2) & (theta > -2.7)
    img[weak_zone] = 206.0

    background_blob = ((xx - 40) ** 2 + (yy - 24) ** 2) < 14**2
    img[background_blob] = 88.0

    if gap:
        gap_mask = annulus & (theta > -0.45) & (theta < -0.1)
        img[gap_mask] = 140.0

    if blur_sigma > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur_sigma)

    if checkerboard:
        board = ((xx + yy) % 2).astype(np.float32)
        img = img + (board * 2.0 - 1.0) * 9.0

    if noise_sigma > 0:
        img = img + rng.normal(0.0, noise_sigma, size=shape).astype(np.float32)

    return np.clip(img, 0, 255).astype(np.uint8)


@pytest.fixture()
def synthetic_pair() -> tuple[np.ndarray, np.ndarray, dict]:
    raw = make_ring_image(blur_sigma=3.6, noise_sigma=3.6, seed=4, gap=True)
    recon = make_ring_image(blur_sigma=1.2, noise_sigma=1.2, seed=5, gap=False)
    return raw, recon, default_config()


def test_detect_ring_reference_estimates_annulus_geometry(synthetic_pair):
    raw, _, config = synthetic_pair

    ref = analysis_core.detect_ring_reference(raw, config)

    assert abs(ref["cx"] - 128) <= 4
    assert abs(ref["cy"] - 150) <= 4
    assert abs(ref["inner_edge_r"] - 56) <= 5
    assert abs(ref["outer_edge_r"] - 76) <= 5
    assert ref["outer_edge_r"] > ref["inner_edge_r"]


def test_select_rois_returns_required_regions_and_background_stays_off_ring(synthetic_pair):
    raw, recon, config = synthetic_pair
    ref = analysis_core.detect_ring_reference(raw, config)

    rois, roi_log = analysis_core.select_rois(raw, recon, ref, config)

    assert set(rois) == {"main_edge", "defect", "weak_edge", "background"}
    assert set(roi_log["scores"]) == {"main_edge", "defect", "weak_edge", "background"}
    for rect in rois.values():
        x, y, w, h = rect
        assert w == config["roi_size"]
        assert h == config["roi_size"]
        assert x >= 0 and y >= 0
        assert x + w <= raw.shape[1]
        assert y + h <= raw.shape[0]

    bg_x, bg_y, bg_w, bg_h = rois["background"]
    bg_cx = bg_x + bg_w / 2.0
    bg_cy = bg_y + bg_h / 2.0
    dist = np.hypot(bg_cx - ref["cx"], bg_cy - ref["cy"])
    assert dist > ref["outer_edge_r"] + 10
    assert bg_cy < ref["cy"] - ref["outer_edge_r"] / 2.0


def test_compute_spatial_metrics_reports_sharper_reconstruction(synthetic_pair):
    raw, recon, config = synthetic_pair
    ref = analysis_core.detect_ring_reference(raw, config)
    rois, _ = analysis_core.select_rois(raw, recon, ref, config)

    metrics, _, profile_log = analysis_core.compute_spatial_metrics(raw, recon, ref, rois, config)

    assert metrics["RAW"]["edge_width_main_px"] > metrics["R26"]["edge_width_main_px"]
    assert metrics["RAW"]["edge_width_weak_px"] > metrics["R26"]["edge_width_weak_px"]
    assert metrics["RAW"]["max_slope_main"] < metrics["R26"]["max_slope_main"]
    assert metrics["RAW"]["CNR_main"] < metrics["R26"]["CNR_main"]
    assert "main_edge" in profile_log
    assert "weak_edge" in profile_log


def test_fft_features_raise_checkerboard_ratio_for_checkerboard_artifact(synthetic_pair):
    raw, recon, config = synthetic_pair
    ref = analysis_core.detect_ring_reference(raw, config)
    recon_checker = make_ring_image(
        blur_sigma=1.2,
        noise_sigma=1.2,
        seed=6,
        gap=False,
        checkerboard=True,
    )

    clean = analysis_core.compute_fft_features(recon, ref, config)
    artifact = analysis_core.compute_fft_features(recon_checker, ref, config)

    assert artifact["checkerboard_ratio"] > clean["checkerboard_ratio"]
    assert artifact["hf_ratio"] >= 0.0


def test_geometry_proxy_improves_when_gap_is_filled(synthetic_pair):
    raw, recon, config = synthetic_pair
    ref = analysis_core.detect_ring_reference(raw, config)

    metrics, geo_log = analysis_core.compute_geometry_proxy(raw, recon, ref, config)

    assert metrics["RAW"]["edge_continuity_ratio"] < metrics["R26"]["edge_continuity_ratio"]
    assert metrics["RAW"]["ring_thickness_std_px"] >= metrics["R26"]["ring_thickness_std_px"]
    assert "valid_angle_counts" in geo_log
