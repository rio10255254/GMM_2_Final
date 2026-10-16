"""Unit tests for the corrected native-resolution ring measurement."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "measurement_qa"
    / "corrected_ring_measurements.py"
)
SPEC = importlib.util.spec_from_file_location("corrected_ring_measurements", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def synthetic_ring(
    size: int,
    radius_px: float,
    sigma_px: float,
    center_dx_px: float = 0.0,
    center_dy_px: float = 0.0,
) -> np.ndarray:
    yy, xx = np.indices((size, size), dtype=np.float32)
    center = (size - 1) / 2.0
    radius = np.sqrt((xx - center - center_dx_px) ** 2 + (yy - center - center_dy_px) ** 2)
    image = 30.0 + 180.0 * np.exp(-0.5 * ((radius - radius_px) / sigma_px) ** 2)
    return image.astype(np.float32)


def local_features(image: np.ndarray, radial_step: float = 0.05):
    size = image.shape[0]
    radii, map_x, map_y = module.build_polar_maps(
        crop_size=size,
        radial_step_px=radial_step,
        angle_samples=1440,
        max_radius_px=size / 2.0 - 3.0,
    )
    profile = module.radial_profile_subpixel(image, map_x, map_y)
    old_ranges = (
        module.PEAK_SEARCH_RANGE_PX,
        module.INNER_BASELINE_RANGE_PX,
        module.OUTER_BASELINE_RANGE_PX,
    )
    try:
        module.PEAK_SEARCH_RANGE_PX = (20.0, size / 2.0 - 12.0)
        module.INNER_BASELINE_RANGE_PX = (2.0, 18.0)
        module.OUTER_BASELINE_RANGE_PX = (size / 2.0 - 10.0, size / 2.0 - 4.0)
        return module.radial_features_subpixel(radii, profile)
    finally:
        (
            module.PEAK_SEARCH_RANGE_PX,
            module.INNER_BASELINE_RANGE_PX,
            module.OUTER_BASELINE_RANGE_PX,
        ) = old_ranges


def test_subpixel_peak_and_width_recover_known_gaussian_ring():
    radius = 50.37
    sigma = 4.2
    image = synthetic_ring(160, radius, sigma)
    features = local_features(image)
    expected_fwhm = 2.0 * math.sqrt(2.0 * math.log(2.0)) * sigma
    assert abs(features.peak_radius_px - radius) < 0.08
    assert abs(features.halfmax_width_px - expected_fwhm) < 0.18
    # Proves the result is not constrained to an integer or old 4-pixel grid.
    assert abs(features.peak_radius_px - round(features.peak_radius_px)) > 0.15
    assert abs(features.halfmax_width_px / 4.0 - round(features.halfmax_width_px / 4.0)) > 0.1


def test_float_center_alignment_removes_subpixel_translation_bias():
    base = synthetic_ring(180, 57.42, 4.8)
    transform = np.float32([[1.0, 0.0, 0.37], [0.0, 1.0, -0.28]])
    shifted = cv2.warpAffine(base, transform, (180, 180), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    crop = cv2.getRectSubPix(shifted, (160, 160), ((179.0 / 2.0) + 0.37, (179.0 / 2.0) - 0.28))
    reference = cv2.getRectSubPix(base, (160, 160), (179.0 / 2.0, 179.0 / 2.0))
    shifted_features = local_features(crop)
    reference_features = local_features(reference)
    assert abs(shifted_features.peak_radius_px - reference_features.peak_radius_px) < 0.08
    assert abs(shifted_features.halfmax_width_px - reference_features.halfmax_width_px) < 0.12


def test_annulus_statistics_are_not_full_crop_statistics():
    image = synthetic_ring(180, 55.2, 4.5)
    weights = module.annulus_weights(image.shape, 50.0, 60.0)
    annulus_mean = module.weighted_mean(image, weights)
    full_mean = float(image.mean())
    assert float(weights.sum()) > 1000
    assert annulus_mean > full_mean + 80.0
    assert not np.isclose(annulus_mean, full_mean)


def test_annulus_soft_area_matches_geometric_area():
    size = 220
    inner, outer = 60.25, 72.65
    weights = module.annulus_weights((size, size), inner, outer)
    expected = math.pi * (outer**2 - inner**2)
    assert abs(float(weights.sum()) - expected) / expected < 0.004


def test_partial_cli_isolated_from_canonical_output():
    args = module.parse_args(["--arm", "Raw", "--limit", "1"])
    arms = tuple(args.arm) if args.arm else module.ARM_ORDER
    selected = module.resolve_output_dir(args, arms)
    assert selected == module.ROOT / "results" / "measurement_qa_dev"
    assert selected != module.ROOT / "results" / "measurement_qa"
