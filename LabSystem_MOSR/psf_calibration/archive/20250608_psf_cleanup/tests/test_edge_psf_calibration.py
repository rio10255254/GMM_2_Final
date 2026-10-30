import math
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from calibrate_edge_psf import (  # noqa: E402
    build_gaussian_psf_grid,
    estimate_sigma_from_edge_profile,
    sample_edge_profiles,
)


def test_estimate_sigma_from_erf_edge_profile():
    true_sigma = 2.4
    offsets = np.linspace(-12.0, 12.0, 121)
    profile = 0.5 * (
        1.0
        + np.vectorize(math.erf)(offsets / (math.sqrt(2.0) * true_sigma))
    )

    result = estimate_sigma_from_edge_profile(offsets, profile)

    assert result["sigma_px"] == pytest_approx(true_sigma, abs=0.18)
    assert result["fwhm_px"] == pytest_approx(2.35482 * true_sigma, abs=0.45)


def test_sample_edge_profiles_recovers_blurred_vertical_edge():
    true_sigma = 2.0
    image = np.zeros((96, 128), dtype=np.float64)
    image[:, 64:] = 1.0
    image = gaussian_filter1d(image, sigma=true_sigma, axis=1, mode="nearest")

    profiles = sample_edge_profiles(
        image,
        radius=10,
        edge_percentile=99.0,
        max_profiles=80,
        random_seed=7,
    )
    sigmas = [estimate_sigma_from_edge_profile(p.offsets, p.values)["sigma_px"] for p in profiles]

    assert len(sigmas) >= 20
    assert float(np.median(sigmas)) == pytest_approx(true_sigma, abs=0.35)


def test_build_gaussian_psf_grid_matches_runtime_shape_and_normalizes():
    sigma_grid = np.array([[1.5, 2.0], [2.5, 3.0]], dtype=np.float64)

    psf_grid = build_gaussian_psf_grid(sigma_grid, kernel_size=21)

    assert psf_grid.shape == (21, 21, 1, 4)
    sums = psf_grid.sum(axis=(0, 1, 2))
    assert np.allclose(sums, 1.0, atol=1e-9)
    center = psf_grid[10, 10, 0, :]
    assert np.all(center == psf_grid[:, :, 0, :].max(axis=(0, 1)))


def pytest_approx(value, *, abs):
    import pytest

    return pytest.approx(value, abs=abs)
