from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from search_common_stable_roi import (  # noqa: E402
    build_candidate_grid,
    candidate_fold_summary,
    candidate_group_summary,
    choose_common_candidate,
    choose_strict_common_candidate,
    candidate_id_for_roi,
    classify_final_roi_status,
    roi_inside_bounds,
)


def test_candidate_grid_stays_inside_image_and_is_deterministic() -> None:
    grid = build_candidate_grid(
        image_width=1000,
        image_height=800,
        roi_width=300,
        roi_height=240,
        stride_x=250,
        stride_y=200,
        margin=20,
    )

    assert grid[0] == (20, 20, 300, 240)
    assert len(grid) == len(set(grid))
    assert all(x >= 20 and y >= 20 for x, y, _, _ in grid)
    assert all(x + width <= 980 for x, y, width, height in grid)
    assert all(y + height <= 780 for x, y, width, height in grid)


def test_fold_summary_requires_v42_to_improve_every_group_and_fold() -> None:
    rows = []
    for group in ["x_0p5um", "x_1um"]:
        for fold in range(4):
            for case, values in {
                "raw": [0.49, 0.51, 0.50, 0.52],
                "v42_e120": [0.495, 0.505, 0.500, 0.507],
            }.items():
                for index, value in enumerate(values):
                    rows.append(
                        {
                            "candidate_id": "roi_001",
                            "group": group,
                            "fold": fold,
                            "case": case,
                            "x_step_um": value + index * 0.0001,
                            "common_valid": True,
                        }
                    )

    summary = candidate_fold_summary(pd.DataFrame(rows), min_valid_per_fold=3)

    assert len(summary) == 8
    assert summary["passes_fold"].all()
    assert (summary["improvement_pct"] > 0).all()


def test_strict_candidate_rejects_one_bad_fold_and_selects_robust_one() -> None:
    rows = []
    for candidate, improvements in {
        "roi_bad": [10.0, 9.0, -1.0, 12.0, 8.0, 7.0, 6.0, 5.0],
        "roi_good": [4.0, 5.0, 6.0, 7.0, 4.5, 5.5, 6.5, 7.5],
    }.items():
        for index, improvement in enumerate(improvements):
            rows.append(
                {
                    "candidate_id": candidate,
                    "group": "x_0p5um" if index < 4 else "x_1um",
                    "fold": index % 4,
                    "raw_sd_nm": 10.0,
                    "v42_sd_nm": 10.0 * (1.0 - improvement / 100.0),
                    "improvement_pct": improvement,
                    "n_common_valid": 7,
                    "passes_fold": improvement > 0,
                }
            )

    selected, ranking = choose_strict_common_candidate(pd.DataFrame(rows), expected_cells=8)

    assert selected == "roi_good"
    bad = ranking[ranking.candidate_id == "roi_bad"].iloc[0]
    good = ranking[ranking.candidate_id == "roi_good"].iloc[0]
    assert not bool(bad.strict_pass)
    assert bool(good.strict_pass)
    assert good.min_improvement_pct == 4.0


def test_strict_candidate_returns_none_when_no_roi_improves_every_cell() -> None:
    summary = pd.DataFrame(
        [
            {
                "candidate_id": "roi_001",
                "group": "x_0p5um",
                "fold": fold,
                "raw_sd_nm": 10.0,
                "v42_sd_nm": 11.0 if fold == 3 else 9.0,
                "improvement_pct": -10.0 if fold == 3 else 10.0,
                "n_common_valid": 7,
                "passes_fold": fold != 3,
            }
            for fold in range(4)
        ]
    )

    selected, ranking = choose_strict_common_candidate(summary, expected_cells=4)

    assert selected is None
    assert not ranking.strict_pass.any()


def test_common_candidate_must_improve_both_step_sizes() -> None:
    rows = []
    for candidate, group_values in {
        "roi_one_sided": {
            "x_0p5um": ([0.48, 0.52, 0.50, 0.54], [0.49, 0.51, 0.50, 0.51]),
            "x_1um": ([0.98, 1.02, 1.00, 1.01], [0.96, 1.04, 1.00, 1.03]),
        },
        "roi_common": {
            "x_0p5um": ([0.48, 0.52, 0.50, 0.54], [0.49, 0.51, 0.50, 0.51]),
            "x_1um": ([0.96, 1.04, 1.00, 1.03], [0.98, 1.02, 1.00, 1.01]),
        },
    }.items():
        for group, (raw_values, v42_values) in group_values.items():
            for case, values in {"raw": raw_values, "v42_e120": v42_values}.items():
                for step_index, value in enumerate(values):
                    rows.append(
                        {
                            "candidate_id": candidate,
                            "group": group,
                            "step_index": step_index,
                            "case": case,
                            "x_step_um": value,
                            "common_valid": True,
                        }
                    )

    summary = candidate_group_summary(pd.DataFrame(rows), min_valid_per_group=4)
    selected, ranking = choose_common_candidate(summary, expected_groups=2)

    assert selected == "roi_common"
    assert bool(ranking[ranking.candidate_id == "roi_common"].iloc[0].common_pass)
    assert not bool(ranking[ranking.candidate_id == "roi_one_sided"].iloc[0].common_pass)


def test_roi_must_be_fully_inside_sample_bounds() -> None:
    bounds = (500, 80, 1500, 1400)

    assert roi_inside_bounds((600, 100, 300, 240), bounds)
    assert not roi_inside_bounds((300, 100, 300, 240), bounds)
    assert not roi_inside_bounds((1800, 100, 300, 240), bounds)


def test_candidate_id_is_coordinate_stable() -> None:
    assert (
        candidate_id_for_roi("5x", (872, 272, 360, 320))
        == "5x_x0872_y0272_w0360_h0320"
    )


def test_final_roi_status_requires_search_holdout_and_full_sequence() -> None:
    assert classify_final_roi_status(True, [5.0, 2.0], [4.0, 1.0], [18, 18]) == "robust_common"
    assert classify_final_roi_status(True, [5.0, -0.1], [4.0, 1.0], [18, 18]) == "not_common"
    assert classify_final_roi_status(True, [5.0, 2.0], [4.0, 1.0], [18, 10]) == "not_common"
