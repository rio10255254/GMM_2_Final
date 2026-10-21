from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage


R80_SCRIPTS = Path(
    r"D:\GMM_2_Final\Experiments\R80_InflectionReferenceCircleSEMValidation\scripts"
)
if str(R80_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(R80_SCRIPTS))

from reference_circle_core import measure_boundary_and_circles  # noqa: E402


def test_reference_circle_backend_recovers_a_subpixel_dark_disk() -> None:
    height = width = 129
    center_x, center_y = 63.4, 65.2
    radius = 22.7
    yy, xx = np.mgrid[:height, :width]
    disk = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= radius**2
    image = np.where(disk, 0.15, 0.90)
    image = ndimage.gaussian_filter(image.astype(np.float64), sigma=1.25)

    result = measure_boundary_and_circles(
        image,
        (center_x, center_y),
        radius,
        sample_count=144,
        acm_iterations=24,
        polarity="dark",
    )

    circles = (
        result.circles.lsc,
        result.circles.mzc,
        result.circles.mic,
        result.circles.mcc,
    )
    for circle in circles:
        assert np.isfinite([circle.cx, circle.cy, circle.radius]).all()
        assert abs(circle.cx - center_x) < 0.35
        assert abs(circle.cy - center_y) < 0.35
        assert abs(circle.radius - radius) < 0.45

    assert result.circles.center_spread < 0.20
    assert np.median(result.signed_gradient_strength) > 0.0
