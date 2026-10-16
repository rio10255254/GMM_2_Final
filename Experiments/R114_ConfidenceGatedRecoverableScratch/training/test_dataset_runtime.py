from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from training.dataset import degrade


def test_all_dynamic_degradations_are_finite_and_deterministic() -> None:
    side = 64
    yy, xx = np.mgrid[0:side, 0:side]
    mask = (((xx - 32) ** 2 + (yy - 32) ** 2) < 18 ** 2).astype(np.float32)
    target = 0.2 + 0.6 * mask
    challenges = [
        "standard", "low_contrast", "uneven_illumination", "asymmetric_blur_halo",
        "boundary_fade", "mixed_hard", "colored_noise", "band_limited_noise",
        "fixed_pattern", "five_x_dense", "nonuniform_psf", "identity",
    ]
    for challenge in challenges:
        first, meta_first = degrade(target, mask, np.random.default_rng(114), challenge, flat=False)
        second, meta_second = degrade(target, mask, np.random.default_rng(114), challenge, flat=False)
        assert first.shape == target.shape
        assert np.isfinite(first).all()
        assert float(first.min()) >= 0 and float(first.max()) <= 1
        assert np.array_equal(first, second), challenge
        assert meta_first == meta_second
