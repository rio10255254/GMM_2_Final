from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(r"D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts")
sys.path.insert(0, str(SCRIPTS_DIR))


def test_summarize_step_series_separates_outlier_from_stable_core() -> None:
    from analyze_gmf_step_residuals import summarize_step_series

    summary = summarize_step_series([1.00, 1.01, 0.99, 1.00, 1.80], trim_fraction=0.2, window_size=3)

    assert summary["count"] == 5
    assert float(summary["all_std_um"]) > 0.30
    assert summary["trimmed_count"] == 4
    assert float(summary["trimmed_std_um"]) < 0.01
    assert float(summary["best_window_std_um"]) < 0.011
    assert summary["best_window_start_step"] == 1


def test_best_contiguous_window_uses_sample_std_and_reports_step_numbers() -> None:
    from analyze_gmf_step_residuals import best_contiguous_window

    result = best_contiguous_window([1.0, 1.5, 2.0, 4.0, 4.0, 4.0], 3)

    assert result["best_window_count"] == 3
    assert result["best_window_start_step"] == 4
    assert result["best_window_end_step"] == 6
    assert result["best_window_std_um"] == 0.0


def test_build_case_comparison_reports_improvement_for_each_metric() -> None:
    from analyze_gmf_step_residuals import build_case_comparison

    rows = [
        {
            "dataset": "toy",
            "group": "g",
            "case": "raw",
            "all_std_um": 0.10,
            "trimmed_std_um": 0.08,
            "best_window_std_um": 0.05,
        },
        {
            "dataset": "toy",
            "group": "g",
            "case": "model",
            "all_std_um": 0.06,
            "trimmed_std_um": 0.04,
            "best_window_std_um": 0.05,
        },
    ]

    comparison = build_case_comparison(rows, baseline_case="raw")

    assert comparison == [
        {
            "dataset": "toy",
            "group": "g",
            "case": "model",
            "all_improvement_pct": 40.0,
            "trimmed_improvement_pct": 50.0,
            "best_window_improvement_pct": 0.0,
            "all_std_um": 0.06,
            "trimmed_std_um": 0.04,
            "best_window_std_um": 0.05,
            "baseline_all_std_um": 0.10,
            "baseline_trimmed_std_um": 0.08,
            "baseline_best_window_std_um": 0.05,
        }
    ]
