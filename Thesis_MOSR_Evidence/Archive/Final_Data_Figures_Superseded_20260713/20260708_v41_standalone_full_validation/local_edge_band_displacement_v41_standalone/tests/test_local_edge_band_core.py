import sys
from pathlib import Path

import numpy as np
from scipy import ndimage


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from local_edge_band_core import measure_pair_local_edge_displacement


def make_vertical_edge_image(shift_px=0.0, blur_sigma=0.8, height=160, width=220):
    x = np.arange(width, dtype=np.float64)[None, :]
    profile = np.full((1, width), 0.35, dtype=np.float64)
    for edge, direction in [(45.0, 1), (82.0, -1), (112.0, 1), (150.0, -1), (178.0, 1)]:
        profile += direction * 0.28 / (1.0 + np.exp(-(x - edge - shift_px) / 1.2))
    image = np.repeat(profile, height, axis=0)
    image += 0.035 * np.sin(np.arange(height, dtype=np.float64)[:, None] / 7.0)
    return ndimage.gaussian_filter(image, sigma=blur_sigma)


def test_recovers_known_subpixel_shift_from_local_vertical_edge():
    ref = make_vertical_edge_image(shift_px=0.0, blur_sigma=0.7)
    mov = make_vertical_edge_image(shift_px=-2.35, blur_sigma=0.7)

    result = measure_pair_local_edge_displacement(
        ref,
        mov,
        expected_signed_dx_px=-2.35,
        roi=(20, 15, 180, 130),
        max_edges=8,
    )

    assert result.usable_edges >= 3
    assert abs(result.signed_dx_px + 2.35) < 0.12
    assert result.boundary_confidence > 0


def test_sharper_edge_has_higher_confidence_and_lower_uncertainty():
    sharp_ref = make_vertical_edge_image(shift_px=0.0, blur_sigma=0.45)
    sharp_mov = make_vertical_edge_image(shift_px=-1.75, blur_sigma=0.45)
    blur_ref = make_vertical_edge_image(shift_px=0.0, blur_sigma=2.4)
    blur_mov = make_vertical_edge_image(shift_px=-1.75, blur_sigma=2.4)

    sharp = measure_pair_local_edge_displacement(
        sharp_ref,
        sharp_mov,
        expected_signed_dx_px=-1.75,
        roi=(20, 15, 180, 130),
        max_edges=8,
    )
    blurred = measure_pair_local_edge_displacement(
        blur_ref,
        blur_mov,
        expected_signed_dx_px=-1.75,
        roi=(20, 15, 180, 130),
        max_edges=8,
    )

    assert sharp.boundary_confidence > blurred.boundary_confidence
    assert sharp.localization_uncertainty_px < blurred.localization_uncertainty_px


def test_can_use_external_edge_centers_for_shared_measurement():
    ref = make_vertical_edge_image(shift_px=0.0, blur_sigma=0.7)
    mov = make_vertical_edge_image(shift_px=-2.1, blur_sigma=0.7)

    result = measure_pair_local_edge_displacement(
        ref,
        mov,
        expected_signed_dx_px=-2.1,
        roi=(20, 15, 180, 130),
        max_edges=8,
        edge_centers=(25, 62, 92, 130, 158),
    )

    assert result.usable_edges >= 3
    assert abs(result.signed_dx_px + 2.1) < 0.12
