from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _shift_integer(img: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(img)
    h, w = img.shape
    src_x0 = max(0, -dx)
    src_x1 = min(w, w - dx)
    dst_x0 = max(0, dx)
    dst_x1 = min(w, w + dx)
    src_y0 = max(0, -dy)
    src_y1 = min(h, h - dy)
    dst_y0 = max(0, dy)
    dst_y1 = min(h, h + dy)
    out[dst_y0:dst_y1, dst_x0:dst_x1] = img[src_y0:src_y1, src_x0:src_x1]
    return out


def test_motion_pair_metrics_rewards_correct_known_shift():
    import r44_motion_metrics

    base = np.zeros((64, 64), dtype=np.uint8)
    base[20:32, 18:30] = 255
    correct = _shift_integer(base, dx=2, dy=1)
    wrong = base.copy()

    ok = r44_motion_metrics.motion_pair_metrics(base, correct, expected_dx=2.0, expected_dy=1.0)
    bad = r44_motion_metrics.motion_pair_metrics(base, wrong, expected_dx=2.0, expected_dy=1.0)

    assert ok["motion_vector_error_px"] < 0.35
    assert bad["motion_vector_error_px"] > 1.5
    assert ok["estimated_dx_px"] > 1.7
    assert ok["estimated_dy_px"] > 0.7


def test_boundary_shift_error_detects_pixel_drift():
    import r44_motion_metrics

    gt_a = np.zeros((64, 64), dtype=np.uint8)
    gt_a[:, 24] = 255
    gt_b = _shift_integer(gt_a, dx=3, dy=0)
    pred_b = _shift_integer(gt_a, dx=1, dy=0)

    metrics = r44_motion_metrics.boundary_motion_error(gt_a, pred_b, expected_dx=3.0, expected_dy=0.0)

    assert 1.5 <= metrics["boundary_motion_distance_px"] <= 2.5


def test_grid_phase_motion_error_reports_wrong_phase_shift():
    import r44_motion_metrics

    grid_a = np.zeros((64, 64), dtype=np.uint8)
    grid_a[:, 4::8] = 255
    grid_b_wrong = np.zeros_like(grid_a)
    grid_b_wrong[:, 5::8] = 255

    metrics = r44_motion_metrics.grid_phase_motion_error(grid_a, grid_b_wrong, expected_dx=3.0)

    assert 1.5 <= metrics["grid_phase_motion_error_px"] <= 2.5


def test_matched_gradient_boundary_keeps_sparse_edge_density_for_region_image():
    import r44_motion_metrics

    img = np.zeros((64, 64), dtype=np.uint8)
    img[:, 31:] = 220
    gt_boundary = np.zeros_like(img)
    gt_boundary[:, 30:32] = 255

    pred_boundary = r44_motion_metrics.matched_gradient_boundary(img, target_count=int((gt_boundary > 0).sum()))
    metrics = r44_motion_metrics.boundary_motion_error(gt_boundary, pred_boundary, expected_dx=0.0, expected_dy=0.0)

    assert int((pred_boundary > 0).sum()) <= int((gt_boundary > 0).sum()) * 2
    assert metrics["boundary_motion_distance_px"] <= 1.5
