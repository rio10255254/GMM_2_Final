from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

PSF_FITTING_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PSF_FITTING_ROOT))

from quick_recalibration.validation_experiments.l0_newdata_tools import (
    build_circle_edge_mask,
    make_circle_only_gt,
    old_standard_positions,
    split_position_repeats,
)
from quick_recalibration.validation_experiments.l0_newdata_analysis import (
    build_l0_summary_payload,
    fov_label,
)
from quick_recalibration.validation_experiments.paired_frame_analysis import (
    build_paired_summary_payload,
    compute_pair_metrics,
    paired_output_paths,
    summarize_pair_rows,
)
from quick_recalibration.validation_experiments.l1_newdata_analysis import (
    compute_l1_capture_stats,
    decide_l1_status,
    l1_output_paths,
)


def test_old_standard_positions_for_11_by_11_grid() -> None:
    assert old_standard_positions(grid_rows=11, grid_cols=11) == [
        1,
        6,
        11,
        56,
        61,
        66,
        111,
        116,
        121,
    ]


def test_split_position_repeats_keeps_three_capture_repeats_separate() -> None:
    files = [Path(f"VisionTop_20260615_{idx:03d}.bmp") for idx in range(242)]

    records = split_position_repeats(files, grid_rows=11, grid_cols=11, repeats_per_position=2)

    assert len(records) == 121
    assert records[0].position_index == 1
    assert records[0].row == 1
    assert records[0].col == 1
    assert records[0].frames == (files[0], files[1])
    assert records[60].position_index == 61
    assert records[60].row == 6
    assert records[60].col == 6
    assert records[60].frames == (files[120], files[121])
    assert records[-1].position_index == 121
    assert records[-1].row == 11
    assert records[-1].col == 11
    assert records[-1].frames == (files[240], files[241])


def test_circle_only_gt_fills_center_blocks_but_keeps_outer_circle() -> None:
    gt = Image.new("L", (101, 101), 20)
    draw = ImageDraw.Draw(gt)
    draw.ellipse((10, 10, 90, 90), fill=210)
    draw.rectangle((38, 38, 49, 49), fill=20)
    draw.rectangle((51, 51, 62, 62), fill=20)

    circle_only = make_circle_only_gt(np.asarray(gt))
    edge_mask = build_circle_edge_mask(np.asarray(gt), edge_width=3)

    assert circle_only[50, 50] > 150
    assert circle_only[5, 50] < 80
    assert edge_mask[10, 50]
    assert edge_mask[50, 10]
    assert not edge_mask[50, 50]
    assert not edge_mask[42, 42]


def test_l0_newdata_runner_declares_correct_rounds_and_mask_policy() -> None:
    runner = (
        PSF_FITTING_ROOT
        / "quick_recalibration"
        / "validation_experiments"
        / "L0_newdata"
        / "run_L0_newdata_rounds.m"
    )

    text = runner.read_text(encoding="utf-8")

    assert "Circle_Round1" in text
    assert "Circle_Round2" in text
    assert "Circle_Round3" in text
    assert "fov_indices = [1, 6, 11, 56, 61, 66, 111, 116, 121]" in text
    assert "'grid_rows', 11" in text
    assert "'grid_cols', 11" in text
    assert "circle_edge_mask.bmp" in text
    assert "center_block_policy" in text


def test_l0_newdata_analysis_labels_fov_with_11_column_grid() -> None:
    assert fov_label(1, grid_cols=11) == "#1 (row 1, col 1)"
    assert fov_label(61, grid_cols=11) == "#61 (row 6, col 6)"
    assert fov_label(121, grid_cols=11) == "#121 (row 11, col 11)"


def test_l1_capture_stats_use_rounds_as_the_repeat_axis() -> None:
    round_tensors = np.array(
        [
            [[[10.0, 20.0]], [[12.0, 18.0]]],
            [[[30.0, 40.0]], [[32.0, 42.0]]],
            [[[50.0, 60.0]], [[52.0, 62.0]]],
        ]
    )
    l0_floor = np.ones((1, 2))

    stats = compute_l1_capture_stats(round_tensors, l0_floor)

    np.testing.assert_allclose(stats["capture_representatives"], [[[11.0, 19.0]], [[31.0, 41.0]], [[51.0, 61.0]]])
    np.testing.assert_allclose(stats["capture_center"], [[31.0, 41.0]])
    np.testing.assert_allclose(stats["capture_delta"][0], [[-20.0, -22.0]])
    assert stats["n_capture_rounds"] == 3
    assert stats["n_trials_per_round"] == 2


def test_l1_net_capture_std_never_goes_negative() -> None:
    round_tensors = np.array(
        [
            [[[10.0]]],
            [[[10.1]]],
            [[[9.9]]],
        ]
    )
    l0_floor = np.array([[1.0]])

    stats = compute_l1_capture_stats(round_tensors, l0_floor)

    assert stats["net_capture_std"][0, 0] == 0.0


def test_l1_status_uses_l0_floor_guardrails() -> None:
    assert decide_l1_status(1.5, 2.6) == "within_L0_floor"
    assert decide_l1_status(2.5, 3.6) == "mostly_within_L0_floor"
    assert decide_l1_status(3.5, 5.2) == "capture_variation_detected"


def test_l1_outputs_are_kept_separate_from_l0_summary() -> None:
    paths = l1_output_paths()

    assert paths["summary_dir"].name == "L1_newdata"
    assert paths["summary_md"].name == "L1_newdata_summary.md"
    assert paths["summary_json"].name == "L1_newdata_summary.json"


def test_l0_summary_payload_marks_only_round1_as_formal_l0() -> None:
    round_summaries = [
        {"round_number": 1, "round_name": "Circle_Round1", "clean_noise_floor_median": 0.03, "clean_noise_floor_mean": 0.04},
        {"round_number": 2, "round_name": "Circle_Round2", "clean_noise_floor_median": 0.02, "clean_noise_floor_mean": 0.03},
        {"round_number": 3, "round_name": "Circle_Round3", "clean_noise_floor_median": 0.025, "clean_noise_floor_mean": 0.035},
    ]

    payload = build_l0_summary_payload(round_summaries, formal_round_number=1)

    assert payload["experiment"] == "L0_newdata_formal_single_capture"
    assert payload["formal_l0"]["round_name"] == "Circle_Round1"
    assert payload["formal_l0"]["clean_noise_floor_median"] == 0.03
    assert [item["round_name"] for item in payload["l1_source_inventory"]] == [
        "Circle_Round2",
        "Circle_Round3",
    ]
    assert payload["definition"]["l0_rule"] == "one capture set repeated through the fitter"


def test_pair_metrics_use_edge_mask_and_report_center_shift() -> None:
    frame_a = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    frame_b = np.array([[2, 4], [6, 8]], dtype=np.uint8)
    edge_mask = np.array([[True, False], [False, True]])

    metrics = compute_pair_metrics(
        frame_a,
        frame_b,
        edge_mask=edge_mask,
        center_a=(10.0, 20.0),
        center_b=(13.0, 24.0),
    )

    assert metrics["full_mean_abs_diff"] == 2.5
    assert metrics["edge_mean_abs_diff"] == 2.5
    assert metrics["edge_signed_mean_diff"] == 2.5
    assert metrics["center_shift_px"] == 5.0


def test_paired_summary_payload_is_image_layer_only() -> None:
    def row(round_name: str, position_index: int, base: float) -> dict[str, float | int | str]:
        return {
            "round_name": round_name,
            "position_index": position_index,
            "row": 1,
            "col": position_index,
            "edge_mean_abs_diff": base,
            "edge_rms_diff": base + 1,
            "edge_p95_abs_diff": base + 2,
            "edge_signed_mean_diff": base + 3,
            "full_mean_abs_diff": base + 4,
            "full_rms_diff": base + 5,
            "full_p95_abs_diff": base + 6,
            "full_signed_mean_diff": base + 7,
            "center_shift_px": base + 0.5,
        }

    rows = [
        row("Circle_Round1", 1, 1.0),
        row("Circle_Round1", 2, 3.0),
        row("Circle_Round2", 1, 5.0),
    ]

    payload = build_paired_summary_payload(rows, old_standard_positions=[1])

    assert payload["experiment"] == "paired_frame_image_layer_check"
    assert payload["method"]["analysis_layer"] == "image_intensity_after_fit_style_crop"
    assert payload["method"]["psf_fit_status"] == "not_run_for_frame_2"
    assert payload["summary"]["all_positions"]["count"] == 3
    assert payload["summary"]["old_standard_positions"]["count"] == 2


def test_summarize_pair_rows_handles_empty_selection() -> None:
    summary = summarize_pair_rows([])

    assert summary["count"] == 0
    assert summary["edge_mean_abs_diff_median"] is None


def test_paired_outputs_are_kept_separate_from_l1_fit_report() -> None:
    paths = paired_output_paths()

    assert paths["summary_dir"].name == "L1_paired_frame_check"
    assert paths["summary_md"].name == "paired_frame_summary.md"
    assert paths["summary_json"].name == "paired_frame_summary.json"
