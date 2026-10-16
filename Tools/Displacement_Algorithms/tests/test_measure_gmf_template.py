from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPTS_DIR = Path(r"D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts")
sys.path.insert(0, str(SCRIPTS_DIR))


def make_blob_frame(
    center_x: float,
    center_y: float,
    *,
    shape: tuple[int, int] = (96, 128),
    sigma: float = 4.2,
    polarity: str = "dark",
) -> np.ndarray:
    yy, xx = np.indices(shape, dtype=np.float32)
    blob = np.exp(-(((xx - center_x) ** 2) + ((yy - center_y) ** 2)) / (2.0 * sigma * sigma))
    if polarity == "dark":
        image = 190.0 - 120.0 * blob
    else:
        image = 45.0 + 170.0 * blob
    return np.clip(image, 0, 255).astype(np.uint8)


def test_single_gaussian_fit_recovers_subpixel_center() -> None:
    from measure_gmf_template import estimate_single_center

    image = make_blob_frame(42.35, 51.80, polarity="dark")

    center, quality = estimate_single_center(image, polarity="dark")

    assert abs(center[0] - 42.35) < 0.08
    assert abs(center[1] - 51.80) < 0.08
    assert quality["total_weight"] > 100.0


def test_multi_gmf_sequence_reports_known_consecutive_motion(tmp_path: Path) -> None:
    from measure_gmf_template import measure_sequence

    centers = [(32.2 + i * 1.35, 45.5 - i * 0.42) for i in range(6)]
    for index, (cx, cy) in enumerate(centers):
        image = make_blob_frame(cx, cy, polarity="bright")
        ok, encoded = cv2.imencode(".png", image)
        assert ok
        (tmp_path / f"frame_{index:03d}.png").write_bytes(encoded.tobytes())

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        polarity="bright",
        mode="single",
        pattern="*.png",
    )

    dx = np.array([row["dx_px"] for row in rows if row["status"] == "ok"], dtype=float)
    dy = np.array([row["dy_px"] for row in rows if row["status"] == "ok"], dtype=float)
    assert len(dx) == 5
    assert abs(float(np.median(dx)) - 1.35) < 0.08
    assert abs(float(np.median(dy)) + 0.42) < 0.08
    assert summary["valid_step_count"] == 5
    assert summary["std_dx_px"] < 0.04


def test_robust_shift_uses_largest_consistent_component_group() -> None:
    from measure_gmf_template import robust_shift_from_components

    shifts = [
        (1.02, 0.04),
        (0.98, -0.03),
        (1.08, 0.02),
        (0.95, -0.01),
        (-7.5, 3.2),
        (12.0, -4.0),
    ]

    dx, dy, inliers = robust_shift_from_components(shifts, cluster_radius=0.25)

    assert inliers == 4
    assert abs(dx - 1.0) < 0.08
    assert abs(dy) < 0.05


def test_robust_shift_cluster_indices_identify_inliers() -> None:
    from measure_gmf_template import robust_shift_cluster_indices

    shifts = [
        (2.0, 0.0),
        (2.1, 0.1),
        (1.9, -0.1),
        (-5.0, 4.0),
        (8.0, -3.0),
    ]

    indices = robust_shift_cluster_indices(shifts, cluster_radius=0.35)

    assert indices == [0, 1, 2]


def test_pairwise_gmf_mode_recovers_motion_when_features_enter_and_leave_roi(tmp_path: Path) -> None:
    from measure_gmf_template import measure_sequence

    base_centers = [
        (18.0, 22.0),
        (47.0, 28.0),
        (79.0, 20.0),
        (112.0, 31.0),
        (148.0, 24.0),
        (181.0, 29.0),
        (216.0, 21.0),
    ]
    dx_per_frame = -8.0
    for index in range(12):
        image = np.full((64, 180), 205, dtype=np.float32)
        yy, xx = np.indices(image.shape, dtype=np.float32)
        for cx, cy in base_centers:
            shifted_x = cx + index * dx_per_frame
            if -8.0 <= shifted_x <= image.shape[1] + 8.0:
                blob = np.exp(-(((xx - shifted_x) ** 2) + ((yy - cy) ** 2)) / (2.0 * 3.2 * 3.2))
                image -= 125.0 * blob
        image = np.clip(image, 0, 255).astype(np.uint8)
        ok, encoded = cv2.imencode(".png", image)
        assert ok
        (tmp_path / f"frame_{index:03d}.png").write_bytes(encoded.tobytes())

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        polarity="dark",
        mode="pairwise",
        pattern="*.png",
        local_radius=18,
        cluster_radius=1.25,
    )

    dx = np.array([row["dx_px"] for row in rows if row["status"] == "ok"], dtype=float)
    assert len(dx) == 11
    assert abs(float(np.median(dx)) - dx_per_frame) < 0.35
    assert summary["failed_step_count"] == 0
    assert summary["std_dx_px"] < 0.35


def test_seeded_gmf_tracks_requested_feature_instead_of_largest_distractor(tmp_path: Path) -> None:
    from measure_gmf_template import measure_sequence

    yy, xx = np.indices((96, 160), dtype=np.float32)
    target_start = (48.0, 54.0)
    target_step = 1.25
    distractor_start = (112.0, 38.0)
    for index in range(7):
        image = np.full((96, 160), 205.0, dtype=np.float32)
        target = np.exp(
            -(
                ((xx - (target_start[0] + index * target_step)) ** 2)
                + ((yy - target_start[1]) ** 2)
            )
            / (2.0 * 3.8 * 3.8)
        )
        # A larger stationary distractor would be chosen first without an explicit seed.
        distractor = np.exp(
            -(
                ((xx - distractor_start[0]) ** 2)
                + ((yy - distractor_start[1]) ** 2)
            )
            / (2.0 * 7.0 * 7.0)
        )
        image -= 125.0 * target
        image -= 145.0 * distractor
        ok, encoded = cv2.imencode(".png", np.clip(image, 0, 255).astype(np.uint8))
        assert ok
        (tmp_path / f"frame_{index:03d}.png").write_bytes(encoded.tobytes())

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        polarity="dark",
        mode="multi",
        pattern="*.png",
        seed_centers=[target_start],
        local_radius=18,
        cluster_radius=0.8,
    )

    dx = np.array([row["dx_px"] for row in rows if row["status"] == "ok"], dtype=float)
    assert len(dx) == 6
    assert abs(float(np.median(dx)) - target_step) < 0.10
    assert summary["seed_centers"] == [list(target_start)]
    assert summary["std_dx_px"] < 0.05


def test_edge_signal_mode_tracks_boundary_motion_for_flat_top_features(tmp_path: Path) -> None:
    from measure_gmf_template import measure_sequence

    yy, xx = np.indices((96, 128), dtype=np.float32)
    for index in range(8):
        center_x = 44 + index * 1.4
        center_y = 48
        radius = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
        edge_arg = np.clip((radius - 16.0) / 0.8, -30.0, 30.0)
        disk = 1.0 / (1.0 + np.exp(edge_arg))
        image = np.clip(210.0 - 145.0 * disk, 0, 255).astype(np.uint8)
        ok, encoded = cv2.imencode(".png", image)
        assert ok
        (tmp_path / f"frame_{index:03d}.png").write_bytes(encoded.tobytes())

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        polarity="dark",
        mode="single",
        pattern="*.png",
        signal_mode="edge",
        threshold_quantile=0.72,
    )

    dx = np.array([row["dx_px"] for row in rows if row["status"] == "ok"], dtype=float)
    assert len(dx) == 7
    assert abs(float(np.median(dx)) - 1.4) < 0.20
    assert summary["signal_mode"] == "edge"
    assert summary["std_dx_px"] < 0.20
