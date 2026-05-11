from pathlib import Path
import sys

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _rect_boundary(size: int = 64) -> np.ndarray:
    mask = np.zeros((size, size), dtype=np.uint8)
    mask[14:50, 14] = 255
    mask[14:50, 49] = 255
    mask[14, 14:50] = 255
    mask[49, 14:50] = 255
    return mask


def test_boundary_shape_metrics_penalize_thick_edges():
    import r44g_boundary_shape_metrics as r44g

    gt = _rect_boundary()
    thick = cv2.dilate(gt, np.ones((3, 3), dtype=np.uint8), iterations=1)

    exact = r44g.boundary_shape_metrics(gt, gt)
    thick_score = r44g.boundary_shape_metrics(gt, thick)

    assert 0.95 <= exact["boundary_density_ratio"] <= 1.05
    assert thick_score["boundary_density_ratio"] > 2.0
    assert thick_score["shape_error_score"] > exact["shape_error_score"]


def test_boundary_shape_metrics_penalize_fragmentation():
    import r44g_boundary_shape_metrics as r44g

    gt = _rect_boundary()
    fragmented = gt.copy()
    fragmented[14:50:8, 14] = 0
    fragmented[14:50:8, 49] = 0
    fragmented[14, 14:50:8] = 0
    fragmented[49, 14:50:8] = 0
    fragmented[14:20, 14:20] = 0
    fragmented[44:50, 44:50] = 0

    exact = r44g.boundary_shape_metrics(gt, gt)
    broken = r44g.boundary_shape_metrics(gt, fragmented)

    assert exact["pred_component_count"] == exact["gt_component_count"]
    assert broken["pred_component_count"] > exact["pred_component_count"]
    assert broken["fragmentation_ratio"] > exact["fragmentation_ratio"]


def test_straight_edge_coverage_detects_missing_side():
    import r44g_boundary_shape_metrics as r44g

    gt = _rect_boundary()
    missing_top = gt.copy()
    missing_top[14, 14:50] = 0

    exact = r44g.boundary_shape_metrics(gt, gt)
    missing = r44g.boundary_shape_metrics(gt, missing_top)

    assert exact["straight_edge_coverage"] >= 0.95
    assert missing["straight_edge_coverage"] < 0.85


def test_corner_retention_detects_missing_corners():
    import r44g_boundary_shape_metrics as r44g

    gt = _rect_boundary()
    missing_corners = gt.copy()
    missing_corners[10:20, 10:20] = 0
    missing_corners[10:20, 44:54] = 0
    missing_corners[44:54, 10:20] = 0
    missing_corners[44:54, 44:54] = 0

    exact = r44g.boundary_shape_metrics(gt, gt)
    missing = r44g.boundary_shape_metrics(gt, missing_corners)

    assert exact["corner_retention"] == 1.0
    assert missing["corner_retention"] == 0.0
    assert missing["shape_error_score"] > exact["shape_error_score"]
