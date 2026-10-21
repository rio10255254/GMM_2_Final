from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_boundary_metrics_detect_known_two_pixel_shift():
    import r42_boundary_metrics

    gt = np.zeros((64, 64), dtype=np.uint8)
    pred = np.zeros_like(gt)
    gt[:, 24] = 255
    pred[:, 26] = 255

    metrics = r42_boundary_metrics.binary_boundary_metrics(pred, gt, tolerances=(1.0, 2.0, 3.0))

    assert 1.9 <= metrics["mean_symmetric_boundary_distance_px"] <= 2.1
    assert metrics["fscore_t1p0"] < 0.05
    assert metrics["fscore_t2p0"] > 0.95
    assert metrics["fscore_t3p0"] > 0.95


def test_grid_pitch_phase_error_separates_spacing_from_phase():
    import r42_boundary_metrics

    gt = np.zeros((64, 64), dtype=np.uint8)
    pred = np.zeros_like(gt)
    gt[:, 2::8] = 255
    pred[:, 4::8] = 255

    metrics = r42_boundary_metrics.grid_pitch_phase_error(pred, gt, axis=1)

    assert metrics["grid_pitch_error_px"] <= 0.25
    assert 1.5 <= metrics["grid_phase_error_px"] <= 2.5


def test_component_metrics_report_missing_defect():
    import r42_boundary_metrics

    gt = np.zeros((64, 64), dtype=np.uint8)
    pred = np.zeros_like(gt)
    gt[20:25, 20:25] = 255

    metrics = r42_boundary_metrics.component_detection_metrics(pred, gt)

    assert metrics["gt_component_count"] == 1
    assert metrics["pred_component_count"] == 0
    assert metrics["component_recall"] == 0.0


def test_image_metric_matches_sparse_boundary_density():
    import r42_boundary_metrics

    gt = np.zeros((64, 64), dtype=np.uint8)
    pred = np.zeros_like(gt)
    boundary = np.zeros_like(gt)
    gt[:, 31:] = 220
    pred[:, 31:] = 220
    boundary[:, 30:32] = 255

    metrics = r42_boundary_metrics.image_metric_row(pred, gt, boundary=boundary)

    assert metrics["pred_boundary_px"] <= metrics["gt_boundary_px"] * 2
    assert metrics["fscore_t1p0"] > 0.90
