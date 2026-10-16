from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from run_v42_roi_sensitivity import (  # noqa: E402
    CASES,
    build_roi_catalog,
    build_cross_roi_consistency,
    classify_roi_sensitivity,
    error_aware_total_nm,
    enforce_common_analysis_validity,
    is_search_boundary_saturated,
    select_case_symmetric_steps,
)


def test_each_group_has_three_named_in_bounds_rois() -> None:
    source_rois = {
        "x_0p5um": (690, 460, 739, 744),
        "x_1um": (685, 453, 746, 758),
        "20x_0p5um": (259, 607, 494, 473),
        "20x_1um": (260, 607, 504, 528),
        "5x_0p5um": (964, 454, 725, 725),
        "5x_1um": (960, 454, 721, 725),
    }

    for group, legacy_roi in source_rois.items():
        catalog = build_roi_catalog(group, legacy_roi, image_size=(2048, 1536))
        assert len(catalog) == 3
        assert "legacy_cross" in catalog
        assert catalog["legacy_cross"] == legacy_roi
        for x, y, width, height in catalog.values():
            assert x >= 0 and y >= 0
            assert width > 100 and height > 100
            assert x + width <= 2048
            assert y + height <= 1536


def test_step_selection_is_case_symmetric() -> None:
    rows = pd.DataFrame(
        [
            {"dataset": "d", "group": "g", "step_index": step, "case": case}
            for step in [1, 2]
            for case in CASES
        ]
        + [{"dataset": "d", "group": "g", "step_index": 3, "case": "raw"}]
    )
    chosen = pd.DataFrame(
        [
            {"dataset": "d", "group": "g", "step_index": 1},
            {"dataset": "d", "group": "g", "step_index": 3},
        ]
    )

    selected = select_case_symmetric_steps(rows, CASES, chosen)

    assert set(selected.step_index) == {1}
    assert set(selected.case) == set(CASES)


def test_roi_sensitivity_classification_detects_sign_reversal() -> None:
    assert classify_roi_sensitivity([20.0, 12.0, 5.0]) == "robust_improvement"
    assert classify_roi_sensitivity([-8.0, -2.0, -15.0]) == "robust_degradation"
    assert classify_roi_sensitivity([20.0, -4.0, 8.0]) == "roi_sensitive"
    assert classify_roi_sensitivity([20.0, float("nan"), 8.0]) == "incomplete"


def test_search_boundary_saturation_is_not_counted_as_subpixel_stability() -> None:
    expected = -7.246377
    assert is_search_boundary_saturated(-5.796377, expected)
    assert not is_search_boundary_saturated(-7.20, expected)


def test_common_analysis_validity_rejects_the_step_for_all_cases() -> None:
    rows = pd.DataFrame(
        [
            {
                "selection": "common_best30",
                "dataset": "d",
                "group": "g",
                "roi_name": "r",
                "step_index": 1,
                "case": case,
                "analysis_valid": case != "v42_e120",
            }
            for case in CASES
        ]
    )

    checked = enforce_common_analysis_validity(rows)

    assert not checked.common_analysis_valid.any()


def test_error_aware_total_includes_accuracy_and_localization() -> None:
    assert error_aware_total_nm(3.0, 4.0) == 5.0


def test_cross_roi_consistency_rewards_smaller_structure_disagreement() -> None:
    rows = []
    for case, values in {
        "raw": [0.49, 0.51],
        "v41_standalone": [0.495, 0.505],
        "v42_e120": [0.499, 0.501],
    }.items():
        for roi_name, value in zip(["a", "b"], values):
            rows.append(
                {
                    "selection": "common_best30",
                    "dataset": "d",
                    "group": "g",
                    "step_index": 1,
                    "case": case,
                    "roi_name": roi_name,
                    "x_step_um": value,
                    "common_analysis_valid": True,
                }
            )

    _, comparison = build_cross_roi_consistency(pd.DataFrame(rows))

    assert comparison.iloc[0].v42_improvement_vs_raw_pct > 0
