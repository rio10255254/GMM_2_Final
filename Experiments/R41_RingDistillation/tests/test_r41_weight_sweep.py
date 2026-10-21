from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R41_RingDistillation" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r41_alpha_grid_and_thresholds():
    import r41_weight_sweep

    assert r41_weight_sweep.default_alpha_grid() == [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
    t = r41_weight_sweep.DEFAULT_THRESHOLDS
    assert t.min_micro_psnr == 26.0
    assert t.min_high_frequency_retention == 0.30
    assert t.max_8px == 0.159
    assert t.max_0p8px == 0.141
    assert t.max_0p08px == 0.107


def test_r41_tradeoff_picker_prefers_best_guarded_capacity():
    import r41_weight_sweep

    rows = [
        {
            "alpha": 0.10,
            "micro_overall_psnr": 26.2,
            "micro_high_frequency_retention": 0.31,
            "ring_8px_step_std": 0.158,
            "ring_0p8px_step_std": 0.140,
            "ring_0p08px_step_std": 0.106,
        },
        {
            "alpha": 0.15,
            "micro_overall_psnr": 27.0,
            "micro_high_frequency_retention": 0.36,
            "ring_8px_step_std": 0.170,
            "ring_0p8px_step_std": 0.140,
            "ring_0p08px_step_std": 0.106,
        },
    ]

    result = r41_weight_sweep.evaluate_capacity_tradeoff(rows, r41_weight_sweep.DEFAULT_THRESHOLDS)
    assert result["found"] is True
    assert result["best"]["alpha"] == 0.10
