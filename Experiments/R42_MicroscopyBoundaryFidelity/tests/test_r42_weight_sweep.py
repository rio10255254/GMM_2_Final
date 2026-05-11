from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r42_low_alpha_grid_and_thresholds():
    import r42_weight_sweep

    assert r42_weight_sweep.default_alpha_grid() == [0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20]
    t = r42_weight_sweep.DEFAULT_THRESHOLDS
    assert t.min_boundary_psnr == 23.0
    assert t.min_high_frequency_retention == 0.30
    assert t.max_boundary_distance_px == 7.0
    assert t.min_boundary_fscore_t1p0 == 0.70


def test_r42_boundary_tradeoff_picker_prefers_best_guarded_boundary():
    import r42_weight_sweep

    rows = [
        {
            "alpha": 0.01,
            "boundary_overall_psnr": 23.5,
            "boundary_high_frequency_retention": 0.35,
            "boundary_distance_px": 6.8,
            "boundary_fscore_t1p0": 0.71,
            "ring_8px_step_std": 0.142,
            "ring_0p8px_step_std": 0.160,
            "ring_0p08px_step_std": 0.126,
        },
        {
            "alpha": 0.02,
            "boundary_overall_psnr": 25.0,
            "boundary_high_frequency_retention": 0.40,
            "boundary_distance_px": 6.0,
            "boundary_fscore_t1p0": 0.75,
            "ring_8px_step_std": 0.150,
            "ring_0p8px_step_std": 0.160,
            "ring_0p08px_step_std": 0.126,
        },
    ]

    result = r42_weight_sweep.evaluate_boundary_tradeoff(rows, r42_weight_sweep.DEFAULT_THRESHOLDS)
    assert result["found"] is True
    assert result["best"]["alpha"] == 0.01


def test_r42_parse_ring_guard_summary_uses_r42_keys():
    import r42_weight_sweep

    parsed = r42_weight_sweep.parse_ring_guard_summary(
        {
            "local_ring_guard_pass": True,
            "datasets": [
                {
                    "short_name": "pitch1um_y_100",
                    "expected_step_px": 8.0,
                    "r42_internal_step_std_y": 0.14,
                    "combo_internal_step_std_y": 0.1389,
                    "relative_delta_vs_combo_pct": 0.8,
                    "local_guard_pass": True,
                }
            ],
        }
    )

    assert parsed["local_ring_guard_pass"] is True
    assert parsed["scales"]["pitch1um_y_100"]["step_std"] == 0.14
