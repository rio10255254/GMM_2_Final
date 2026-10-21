from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import cv2


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_center9_displacement import (  # noqa: E402
    build_expected_filenames,
    build_common_pillar_comparison,
    apply_common_valid_population,
    assert_complete_step_schedule,
    evaluate_subpixel_validation,
    _plot_subpixel_validation,
    load_locked_config,
    prediction_mode_comparable,
    run_locked_sequence,
    summarize_case_steps,
    validate_real_crop_subpixel,
    write_sequence_outputs,
)


CONFIG = PACKAGE / "config" / "sequence_center9.json"
EXPECTED_IDS = {22, 23, 24, 28, 29, 30, 34, 35, 36}


def test_locked_config_contains_all_six_sequences_and_exact_sem_ids() -> None:
    config = load_locked_config(CONFIG, verify_files=True)

    assert set(config["sequences"]) == {
        "50x_x_0p5um",
        "50x_x_1um",
        "20x_0p5um",
        "20x_1um",
        "5x_0p5um",
        "5x_1um",
    }
    for sequence in config["sequences"].values():
        assert {int(row[0]) for row in sequence["centers"]} == EXPECTED_IDS
        assert abs(float(sequence["expected_signed_dx_px"])) < float(
            sequence["pitch_px"]
        ) * 0.5
        assert float(sequence["search_radius_px"]) < float(sequence["pitch_px"]) * 0.5


def test_expected_filenames_match_prelocked_frame_range() -> None:
    config = load_locked_config(CONFIG, verify_files=False)

    names_51 = build_expected_filenames(config["sequences"]["50x_x_0p5um"])
    names_50 = build_expected_filenames(config["sequences"]["20x_1um"])

    assert len(names_51) == 51
    assert names_51[0] == "frame_0000.bmp"
    assert names_51[-1] == "frame_0050.bmp"
    assert len(names_50) == 50
    assert names_50[-1] == "frame_0049.bmp"


@pytest.mark.parametrize(
    ("sequence_key", "maximum_error_px"),
    [
        ("50x_x_1um", 0.08),
        ("20x_1um", 0.10),
        ("5x_1um", 0.16),
    ],
)
def test_real_raw_crop_recovers_known_subpixel_shifts(
    sequence_key: str, maximum_error_px: float
) -> None:
    config = load_locked_config(CONFIG, verify_files=True)
    result = validate_real_crop_subpixel(
        sequence_key,
        config["sequences"][sequence_key],
        known_shifts_px=(-0.37, 0.29),
    )

    assert result["analysis_valid"].all()
    assert result["abs_error_px"].max() <= maximum_error_px
    assert set(result["prediction_factor"]) == {0.0, -0.7, 0.7}


def test_summary_retains_scheduled_invalid_steps_in_coverage() -> None:
    steps = pd.DataFrame(
        {
            "step_index": [1, 2, 3],
            "analysis_valid": [True, False, True],
            "consensus_dx_px": [-2.0, np.nan, -2.2],
            "within_grid_disagreement_px": [0.1, np.nan, 0.2],
        }
    )

    summary = summarize_case_steps(
        steps,
        case="raw",
        object_um_per_px=0.1,
        nominal_step_um=0.2,
        expected_signed_dx_px=-2.0,
        scheduled_steps=3,
    )

    assert summary["scheduled_steps"] == 3
    assert summary["valid_steps"] == 2
    assert summary["rejected_steps"] == 1
    assert summary["coverage_pct"] == pytest.approx(200.0 / 3.0)
    assert summary["mean_step_magnitude_um"] == pytest.approx(0.21)


def test_summary_exposes_direction_reversals_in_signed_metrics() -> None:
    steps = pd.DataFrame(
        {
            "step_index": [1, 2, 3, 4],
            "analysis_valid": [True, True, True, True],
            "consensus_dx_px": [-5.0, 5.0, -5.0, 5.0],
            "within_grid_disagreement_px": [0.1, 0.1, 0.1, 0.1],
        }
    )

    summary = summarize_case_steps(
        steps,
        case="raw",
        object_um_per_px=0.1,
        nominal_step_um=0.5,
        expected_signed_dx_px=-5.0,
        scheduled_steps=4,
    )

    assert summary["step_magnitude_sd_nm"] == pytest.approx(0.0)
    assert summary["signed_step_sd_nm"] > 500.0
    assert summary["wrong_direction_steps"] == 2
    assert summary["wrong_direction_pct"] == pytest.approx(50.0)


def test_complete_schedule_rejects_missing_or_duplicate_step_indices() -> None:
    missing = pd.DataFrame({"step_index": [1, 3]})
    duplicate = pd.DataFrame({"step_index": [1, 2, 2, 3]})

    with pytest.raises(ValueError, match="complete scheduled step range"):
        assert_complete_step_schedule(missing, frame_count=4, label="missing")
    with pytest.raises(ValueError, match="duplicate"):
        assert_complete_step_schedule(duplicate, frame_count=4, label="duplicate")


def test_direct_execution_block_is_after_all_function_definitions() -> None:
    source = (SCRIPTS / "run_center9_displacement.py").read_text(encoding="utf-8")
    assert source.rfind("def summarize_case_steps") < source.rfind('if __name__ == "__main__"')


def test_subpixel_plot_aggregates_many_trials_to_one_bar_per_sequence(
    tmp_path: Path,
) -> None:
    validation = pd.DataFrame(
        {
            "sequence": ["a", "a", "a", "b", "b", "b"],
            "abs_error_px": [0.01, 0.02, 0.015, 0.03, 0.025, 0.02],
            "allowed_error_px": [0.08, 0.08, 0.08, 0.10, 0.10, 0.10],
            "trial_passed": [True, True, True, True, True, True],
        }
    )
    output = tmp_path / "subpixel.png"

    _plot_subpixel_validation(validation, output)

    assert output.is_file()
    assert output.stat().st_size > 0


def test_prediction_mode_with_four_of_49_steps_is_not_comparable() -> None:
    assert prediction_mode_comparable(40, 50)
    assert not prediction_mode_comparable(4, 49)


def test_subpixel_validation_fails_when_any_required_shift_is_invalid() -> None:
    validation = pd.DataFrame(
        {
            "analysis_valid": [True, False],
            "abs_error_px": [0.02, np.nan],
        }
    )
    status = evaluate_subpixel_validation(validation, maximum_error_px=0.1)

    assert not status["available"]
    assert status["required_trials"] == 2
    assert status["passed_trials"] == 1


def test_common_population_keeps_full_schedule_and_marks_noncommon_invalid() -> None:
    raw = pd.DataFrame(
        {
            "step_index": [1, 2, 3],
            "analysis_valid": [True, True, True],
            "consensus_dx_px": [-2.0, -2.1, -2.2],
        }
    )
    comparison = pd.DataFrame(
        {"step_index": [1, 2, 3], "common_valid": [True, False, True]}
    )

    common = apply_common_valid_population(raw, comparison)

    assert len(common) == 3
    assert common["analysis_valid"].tolist() == [True, False, True]
    assert np.isnan(common.loc[common["step_index"] == 2, "consensus_dx_px"]).all()


def test_common_pillar_comparison_rejects_when_case_valid_sets_overlap_by_only_five() -> None:
    ids = [22, 23, 24, 28, 29, 30, 34, 35, 36]
    raw = pd.DataFrame(
        {
            "step_index": [1] * 9,
            "pillar_id": [str(value) for value in ids],
            "pillar_valid": [True] * 7 + [False] * 2,
            "pillar_dx_px": [-2.0] * 9,
        }
    )
    v42 = pd.DataFrame(
        {
            "step_index": [1] * 9,
            "pillar_id": [str(value) for value in ids],
            "pillar_valid": [False] * 2 + [True] * 7,
            "pillar_dx_px": [-2.0] * 9,
        }
    )

    comparison = build_common_pillar_comparison(
        raw,
        v42,
        frame_count=2,
        min_common_pillars=7,
        object_um_per_px=0.1,
    )

    assert comparison.loc[0, "common_pillars"] == 5
    assert not comparison.loc[0, "common_valid"]
    assert np.isnan(comparison.loc[0, "consensus_dx_px_raw"])


def test_common_pillar_comparison_recomputes_both_cases_from_same_seven_ids() -> None:
    ids = [22, 23, 24, 28, 29, 30, 34, 35, 36]
    raw_dx = np.arange(9, dtype=float) - 10.0
    v42_dx = raw_dx + 0.5
    raw = pd.DataFrame(
        {
            "step_index": [1] * 9,
            "pillar_id": [str(value) for value in ids],
            "pillar_valid": [True] * 8 + [False],
            "pillar_dx_px": raw_dx,
        }
    )
    v42 = pd.DataFrame(
        {
            "step_index": [1] * 9,
            "pillar_id": [str(value) for value in ids],
            "pillar_valid": [False] + [True] * 8,
            "pillar_dx_px": v42_dx,
        }
    )

    comparison = build_common_pillar_comparison(
        raw,
        v42,
        frame_count=2,
        min_common_pillars=7,
        object_um_per_px=0.1,
    )

    expected_common = ids[1:8]
    assert comparison.loc[0, "common_valid"]
    assert comparison.loc[0, "common_pillars"] == 7
    assert comparison.loc[0, "common_pillar_ids"] == ";".join(map(str, expected_common))
    assert comparison.loc[0, "consensus_dx_px_raw"] == pytest.approx(
        np.median(raw_dx[1:8])
    )
    assert comparison.loc[0, "consensus_dx_px_v42"] == pytest.approx(
        np.median(v42_dx[1:8])
    )


def _write_synthetic_grid(path: Path, centers: list[list[float]], shift_px: float) -> None:
    image = np.full((240, 360), 220, dtype=np.uint8)
    for _, x_px, y_px in centers:
        cv2.circle(
            image,
            (int(round(x_px + shift_px)), int(round(y_px))),
            12,
            35,
            -1,
            lineType=cv2.LINE_AA,
        )
    image = cv2.GaussianBlur(image, (0, 0), 1.2)
    success, encoded = cv2.imencode(".bmp", image)
    assert success
    encoded.tofile(path)


def test_locked_sequence_keeps_every_step_and_shares_raw_predictions(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "raw"
    v42_dir = tmp_path / "v42"
    raw_dir.mkdir()
    v42_dir.mkdir()
    ids = [24, 23, 22, 30, 29, 28, 36, 35, 34]
    centers = [
        [pillar_id, 120.0 + column * 45.0, 70.0 + row * 45.0]
        for row in range(3)
        for column, pillar_id in enumerate(ids[row * 3 : row * 3 + 3])
    ]
    for frame_index, shift in enumerate((0.0, -3.0, -6.0)):
        name = f"frame_{frame_index:04d}.bmp"
        _write_synthetic_grid(raw_dir / name, centers, shift)
        _write_synthetic_grid(v42_dir / name, centers, shift)

    sequence = {
        "raw_dir": str(raw_dir),
        "v42_dir": str(v42_dir),
        "frame_count": 3,
        "first_frame": "frame_0000.bmp",
        "last_frame": "frame_0002.bmp",
        "object_um_per_px": 0.1,
        "nominal_step_um": 0.3,
        "expected_signed_dx_px": -3.0,
        "polarity": "dark",
        "radius_px": 12.0,
        "pitch_px": 45.0,
        "search_radius_px": 5.0,
        "min_valid_pillars": 7,
        "min_edge_strength": 2.0,
        "centers": centers,
    }

    result = run_locked_sequence("synthetic", sequence)

    assert result["raw_steps"]["step_index"].tolist() == [1, 2]
    assert result["v42_steps"]["step_index"].tolist() == [1, 2]
    assert result["comparison"]["step_index"].tolist() == [1, 2]
    assert result["raw_steps"]["analysis_valid"].all()
    assert result["v42_steps"]["analysis_valid"].all()
    assert result["comparison"]["common_valid"].all()
    assert result["raw_prediction_shifts"] == result["v42_prediction_shifts"]

    for prediction_mode in ("raw_guided", "fixed_nominal", "v42_guided"):
        sensitivity = run_locked_sequence(
            "synthetic",
            sequence,
            prediction_mode=prediction_mode,
        )
        assert sensitivity["prediction_mode"] == prediction_mode
        assert sensitivity["raw_prediction_shifts"] == sensitivity["v42_prediction_shifts"]
        assert sensitivity["comparison"]["common_valid"].all()

    outputs = write_sequence_outputs(
        "synthetic",
        sequence,
        result,
        output_root=tmp_path / "outputs",
    )
    assert pd.read_csv(outputs["steps_csv"]).shape[0] == 4
    assert pd.read_csv(outputs["pillar_steps_csv"]).shape[0] == 36
    assert pd.read_csv(outputs["comparison_csv"]).shape[0] == 2
    assert outputs["identity_overlay"].is_file()
    assert outputs["step_trace"].is_file()
    assert outputs["residual_figure"].is_file()
