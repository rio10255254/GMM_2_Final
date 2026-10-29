from __future__ import annotations

import numpy as np
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


SCRIPTS_DIR = Path(str(PROJECT_ROOT / 'Tools/Displacement_Algorithms/scripts'))
sys.path.insert(0, str(SCRIPTS_DIR))

from motion_preserving_fusion import (
    blend_with_raw,
    motion_preserving_detail,
)


def test_motion_preserving_detail_keeps_raw_low_frequency_position() -> None:
    yy, xx = np.mgrid[0:96, 0:96].astype(np.float32)
    raw = 80.0 + 0.35 * xx + 0.15 * yy
    shifted_recon = 80.0 + 0.35 * (xx - 8.0) + 0.15 * yy
    shifted_recon[:, 48:] += 35.0

    fused = motion_preserving_detail(raw, shifted_recon, sigma=3.0, detail_gain=1.0)

    assert fused.shape == raw.shape
    assert abs(float(np.mean(fused)) - float(np.mean(raw))) < 0.25
    left_mean = float(np.mean(fused[:, :24]))
    raw_left_mean = float(np.mean(raw[:, :24]))
    assert abs(left_mean - raw_left_mean) < 0.50
    assert float(np.std(fused - raw)) > 1.0


def test_blend_with_raw_uses_declared_fraction() -> None:
    raw = np.full((8, 8), 10.0, dtype=np.float32)
    recon = np.full((8, 8), 30.0, dtype=np.float32)

    fused = blend_with_raw(raw, recon, alpha=0.25)

    assert np.allclose(fused, 15.0)


def test_motion_preserving_detail_gain_zero_returns_raw() -> None:
    raw = np.arange(64, dtype=np.float32).reshape(8, 8)
    recon = np.flipud(raw) + 25.0

    fused = motion_preserving_detail(raw, recon, sigma=2.0, detail_gain=0.0)

    assert np.allclose(fused, raw)


def test_motion_preserving_detail_does_not_erase_raw_texture_when_recon_is_smooth() -> None:
    yy, xx = np.mgrid[0:32, 0:32]
    raw = (120.0 + 12.0 * ((xx + yy) % 2)).astype(np.float32)
    recon = np.full_like(raw, 128.0)

    fused = motion_preserving_detail(raw, recon, sigma=2.0, detail_gain=1.0)

    assert float(np.mean(np.abs(fused - raw))) < 0.25
