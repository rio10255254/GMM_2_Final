import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from r45b_teacher_diagnostics import (  # noqa: E402
    compute_residual_advantage,
    family_oracle_rows,
    frame_oracle_rows,
    summarize_teacher_transferability,
)


def test_compute_residual_advantage_positive_when_teacher_lower_error():
    stats = compute_residual_advantage(
        base_abs_error=[0.5, 0.4, 0.2, 0.2],
        teacher_abs_error=[0.2, 0.3, 0.2, 0.5],
    )
    assert round(stats["mean_error_reduction"], 4) == 0.025
    assert round(stats["teacher_better_fraction"], 4) == 0.5


def test_frame_oracle_picks_best_model_per_case():
    rows = [
        {"model": "base", "case_id": "a", "feature_family": "large_regions", "shape_error_score": 0.4},
        {"model": "teacher", "case_id": "a", "feature_family": "large_regions", "shape_error_score": 0.2},
        {"model": "base", "case_id": "b", "feature_family": "mixed_fields", "shape_error_score": 0.1},
        {"model": "teacher", "case_id": "b", "feature_family": "mixed_fields", "shape_error_score": 0.3},
    ]
    oracle = frame_oracle_rows(rows)
    assert [row["oracle_model"] for row in oracle] == ["teacher", "base"]
    assert [row["oracle_shape_error_score"] for row in oracle] == [0.2, 0.1]


def test_family_oracle_picks_best_average_model_per_family():
    rows = [
        {"model": "a", "feature_family": "large_regions", "shape_error_score": 0.5},
        {"model": "a", "feature_family": "large_regions", "shape_error_score": 0.3},
        {"model": "b", "feature_family": "large_regions", "shape_error_score": 0.2},
        {"model": "b", "feature_family": "large_regions", "shape_error_score": 0.4},
        {"model": "a", "feature_family": "mixed_fields", "shape_error_score": 0.6},
        {"model": "b", "feature_family": "mixed_fields", "shape_error_score": 0.7},
    ]
    oracle = family_oracle_rows(rows)
    by_family = {row["feature_family"]: row for row in oracle}
    assert by_family["large_regions"]["oracle_model"] == "b"
    assert by_family["mixed_fields"]["oracle_model"] == "a"


def test_transferability_requires_shape_and_residual_advantage():
    verdict = summarize_teacher_transferability(
        teacher_name="teacher",
        target_shape_delta_pct=8.0,
        mean_error_reduction=0.02,
        teacher_better_fraction=0.62,
        motion_regression_pct=4.0,
    )
    assert verdict["transferable"] is True

    bad = summarize_teacher_transferability(
        teacher_name="bad",
        target_shape_delta_pct=8.0,
        mean_error_reduction=-0.01,
        teacher_better_fraction=0.45,
        motion_regression_pct=4.0,
    )
    assert bad["transferable"] is False
    assert "殘差方向不穩" in bad["reason"]
