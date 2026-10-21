from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\LabSystem_MOSR\Experiments\R62_TargetSampleBoost\scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))


def _row(dataset: str, group: str, case: str, std_um: float, step_error_um: float = 0.0) -> dict[str, object]:
    return {
        "dataset": dataset,
        "group": group,
        "case": case,
        "std_um": std_um,
        "step_error_um": step_error_um,
        "status": "ok",
    }


def test_score_cases_separates_primary_and_guardrail_penalties() -> None:
    from score_external_displacement_candidates import score_cases

    rows = [
        _row("20260702_100MG", "x_1um", "raw", 0.10),
        _row("20260702_100MG", "x_1um", "candidate_good", 0.08),
        _row("20260702_100MG", "x_1um", "candidate_bad", 0.09),
        _row("20260702_100MG", "x_0p5um", "raw", 0.20),
        _row("20260702_100MG", "x_0p5um", "candidate_good", 0.18),
        _row("20260702_100MG", "x_0p5um", "candidate_bad", 0.40),
        _row("20260704_20x_5x", "20x_1um", "raw", 0.10),
        _row("20260704_20x_5x", "20x_1um", "candidate_good", 0.20),
        _row("20260704_20x_5x", "20x_1um", "candidate_bad", 0.09),
        _row("20260704_20x_5x", "20x_0p5um", "raw", 0.10),
        _row("20260704_20x_5x", "20x_0p5um", "candidate_good", 0.10),
        _row("20260704_20x_5x", "20x_0p5um", "candidate_bad", 0.08),
    ]

    scored = score_cases(rows, candidate_cases=["candidate_good", "candidate_bad"])
    by_case = {row["case"]: row for row in scored}

    assert by_case["candidate_good"]["primary_mean_improvement_pct"] == 15.0
    assert by_case["candidate_good"]["guardrail_worse_count"] == 1
    assert by_case["candidate_good"]["guardrail_worst_regression_pct"] == -100.0
    assert by_case["candidate_good"]["selection_score_pct"] == -115.0

    assert by_case["candidate_bad"]["primary_mean_improvement_pct"] == -45.0
    assert by_case["candidate_bad"]["guardrail_worse_count"] == 0
    assert by_case["candidate_bad"]["primary_worse_count"] == 1
    assert by_case["candidate_bad"]["selection_score_pct"] == -245.0
    assert scored[0]["case"] == "candidate_good"


def test_score_cases_allows_tiny_primary_noise_but_penalizes_real_primary_regression() -> None:
    from score_external_displacement_candidates import score_cases

    rows = [
        _row("20260702_100MG", "x_1um", "raw", 1.0),
        _row("20260702_100MG", "x_1um", "tiny_noise", 1.0001),
        _row("20260702_100MG", "x_1um", "real_regression", 1.01),
        _row("20260702_100MG", "x_0p5um", "raw", 1.0),
        _row("20260702_100MG", "x_0p5um", "tiny_noise", 0.99),
        _row("20260702_100MG", "x_0p5um", "real_regression", 0.99),
    ]

    scored = score_cases(
        rows,
        candidate_cases=["tiny_noise", "real_regression"],
        primary_regression_tolerance_pct=0.02,
    )
    by_case = {row["case"]: row for row in scored}

    assert by_case["tiny_noise"]["primary_worse_count"] == 0
    assert by_case["real_regression"]["primary_worse_count"] == 1
    assert by_case["real_regression"]["primary_worst_regression_pct"] == -1.0
    assert by_case["tiny_noise"]["selection_score_pct"] > by_case["real_regression"]["selection_score_pct"]


def test_score_cases_penalizes_low_std_candidate_with_bad_step_accuracy() -> None:
    from score_external_displacement_candidates import score_cases

    rows = [
        _row("20260702_100MG", "x_1um", "raw", 0.10, 0.01),
        _row("20260702_100MG", "x_1um", "low_std_bad_step", 0.05, 0.50),
        _row("20260702_100MG", "x_1um", "balanced_step", 0.08, 0.02),
        _row("20260702_100MG", "x_0p5um", "raw", 0.10, 0.01),
        _row("20260702_100MG", "x_0p5um", "low_std_bad_step", 0.05, 0.50),
        _row("20260702_100MG", "x_0p5um", "balanced_step", 0.08, 0.02),
    ]

    scored = score_cases(rows, candidate_cases=["low_std_bad_step", "balanced_step"])
    by_case = {row["case"]: row for row in scored}

    assert by_case["low_std_bad_step"]["primary_mean_improvement_pct"] == 50.0
    assert by_case["low_std_bad_step"]["primary_mean_step_error_um"] == 0.5
    assert by_case["low_std_bad_step"]["step_error_penalty_pct"] > 0.0
    assert by_case["balanced_step"]["selection_score_pct"] > by_case["low_std_bad_step"]["selection_score_pct"]
    assert scored[0]["case"] == "balanced_step"


def test_build_group_rows_marks_best_case_and_raw_improvement() -> None:
    from score_external_displacement_candidates import build_group_rows

    rows = [
        _row("20260702_100MG", "x_1um", "raw", 0.10, 0.01),
        _row("20260702_100MG", "x_1um", "candidate_a", 0.08, 0.02),
        _row("20260702_100MG", "x_1um", "candidate_b", 0.12, 0.03),
    ]

    group_rows = build_group_rows(rows)
    by_case = {row["case"]: row for row in group_rows}

    assert by_case["raw"]["tier"] == "primary"
    assert by_case["candidate_a"]["best_case"] == "candidate_a"
    assert by_case["candidate_a"]["improvement_vs_raw_pct"] == 20.0
    assert by_case["candidate_b"]["improvement_vs_raw_pct"] == -20.0
