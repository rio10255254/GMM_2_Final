from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


SCRIPTS_DIR = Path(str(PROJECT_ROOT / 'Tools/Displacement_Algorithms/scripts'))
sys.path.insert(0, str(SCRIPTS_DIR))


def make_soft_square(
    shift_x: float,
    shift_y: float,
    *,
    shape: tuple[int, int] = (120, 140),
) -> np.ndarray:
    image = np.full(shape, 210.0, dtype=np.float32)
    yy, xx = np.indices(shape, dtype=np.float32)
    cx = 66.0 + shift_x
    cy = 58.0 + shift_y
    half = 18.0
    dist = np.maximum(np.abs(xx - cx), np.abs(yy - cy)) - half
    square = 1.0 / (1.0 + np.exp(np.clip(dist / 0.9, -30.0, 30.0)))
    image -= 145.0 * square
    image = cv2.GaussianBlur(image, (0, 0), 0.65)
    return np.clip(image, 0, 255).astype(np.uint8)


def make_repeated_soft_disks(
    shift_x: float,
    *,
    shape: tuple[int, int] = (96, 190),
) -> np.ndarray:
    image = np.full(shape, 215.0, dtype=np.float32)
    yy, xx = np.indices(shape, dtype=np.float32)
    for cx in (36.0, 78.0, 120.0, 162.0):
        radius = np.sqrt((xx - (cx + shift_x)) ** 2 + (yy - 48.0) ** 2)
        disk = 1.0 / (1.0 + np.exp(np.clip((radius - 9.5) / 0.8, -30.0, 30.0)))
        image -= 135.0 * disk
    image = cv2.GaussianBlur(image, (0, 0), 0.75)
    return np.clip(image, 0, 255).astype(np.uint8)


def write_png(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_chamfer_anchor_recovers_subpixel_square_motion(tmp_path: Path) -> None:
    from measure_shape_edge_anchor import measure_sequence

    step_x = 0.72
    step_y = 0.18
    for index in range(8):
        write_png(tmp_path / f"frame_{index:03d}.png", make_soft_square(index * step_x, index * step_y))

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        pattern="*.png",
        expected_dx_px=step_x,
        expected_dy_px=step_y,
        search_radius_px=1.5,
        edge_quantile=0.72,
        subpixel_step=0.05,
        max_edge_points=5000,
    )

    dx = np.array([row["dx_px"] for row in rows if row["status"] == "ok"], dtype=float)
    dy = np.array([row["dy_px"] for row in rows if row["status"] == "ok"], dtype=float)
    assert len(dx) == 7
    assert abs(float(np.median(dx)) - step_x) < 0.08
    assert abs(float(np.median(dy)) - step_y) < 0.08
    assert summary["valid_step_count"] == 7
    assert summary["std_dx_px"] < 0.06


def test_expected_search_window_prevents_repeated_feature_jump(tmp_path: Path) -> None:
    from measure_shape_edge_anchor import measure_sequence

    step_x = 1.25
    for index in range(7):
        write_png(tmp_path / f"frame_{index:03d}.png", make_repeated_soft_disks(index * step_x))

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        pattern="*.png",
        expected_dx_px=step_x,
        expected_dy_px=0.0,
        search_radius_px=2.0,
        edge_quantile=0.76,
        subpixel_step=0.05,
        max_edge_points=4500,
    )

    dx = np.array([row["dx_px"] for row in rows if row["status"] == "ok"], dtype=float)
    assert len(dx) == 6
    assert abs(float(np.median(dx)) - step_x) < 0.10
    assert abs(float(summary["mean_dx_px"]) - step_x) < 0.10
    assert summary["failed_step_count"] == 0


def test_blank_edge_anchor_reports_failed_step(tmp_path: Path) -> None:
    from measure_shape_edge_anchor import measure_sequence

    for index in range(3):
        write_png(tmp_path / f"frame_{index:03d}.png", np.full((64, 72), 128, dtype=np.uint8))

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        pattern="*.png",
        expected_dx_px=0.0,
        expected_dy_px=0.0,
        search_radius_px=1.0,
    )

    statuses = [row["status"] for row in rows]
    assert statuses == ["reference", "failed", "failed"]
    assert summary["valid_step_count"] == 0
    assert summary["failed_step_count"] == 2


def test_rejected_steps_still_count_in_attempted_all_step_summary(tmp_path: Path) -> None:
    from measure_shape_edge_anchor import measure_sequence

    for index in range(4):
        write_png(tmp_path / f"frame_{index:03d}.png", make_soft_square(index * 0.72, 0.0))

    rows, summary = measure_sequence(
        tmp_path,
        crop=None,
        pattern="*.png",
        expected_dx_px=0.72,
        expected_dy_px=0.0,
        search_radius_px=1.5,
        edge_quantile=0.72,
        subpixel_step=0.05,
        max_edge_points=5000,
        edge_phase_refine=False,
        require_edge_phase_refine=True,
    )

    measured_rows = rows[1:]
    assert all(row["status"] == "failed" for row in measured_rows)
    assert all("attempted_dx_px" in row for row in measured_rows)
    assert any(abs(float(row["attempted_dx_px"])) > 0.1 for row in measured_rows)
    assert summary["valid_step_count"] == 0
    assert summary["attempted_step_count"] == 3
    assert summary["attempted_mean_dx_px"] is not None
    assert summary["attempted_std_dx_px"] is not None
