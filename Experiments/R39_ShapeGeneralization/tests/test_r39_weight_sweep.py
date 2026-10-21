"""Unit tests for R39 weight-averaging sweep pure logic."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import r39_weight_sweep as ws


def _f(values: dict) -> dict:
    return {k: torch.tensor(v, dtype=torch.float32) for k, v in values.items()}


# ----------------------------------------------------------------------------
# validate_state_dicts_compatible
# ----------------------------------------------------------------------------

def test_validate_passes_for_identical_keys_and_shapes():
    sd_a = _f({"a": [1.0, 2.0], "b": [3.0]})
    sd_b = _f({"a": [4.0, 5.0], "b": [6.0]})
    ws.validate_state_dicts_compatible(sd_a, sd_b)


def test_validate_raises_when_keys_differ():
    sd_a = _f({"a": [1.0]})
    sd_b = _f({"a": [1.0], "extra": [2.0]})
    with pytest.raises(ValueError, match="key"):
        ws.validate_state_dicts_compatible(sd_a, sd_b)


def test_validate_raises_when_shapes_differ():
    sd_a = _f({"a": [1.0, 2.0]})
    sd_b = _f({"a": [1.0, 2.0, 3.0]})
    with pytest.raises(ValueError, match="shape"):
        ws.validate_state_dicts_compatible(sd_a, sd_b)


# ----------------------------------------------------------------------------
# interpolate_state_dicts
# ----------------------------------------------------------------------------

def test_interpolate_alpha_zero_returns_first_endpoint():
    sd_a = _f({"w": [1.0, 2.0]})
    sd_b = _f({"w": [10.0, 20.0]})
    out = ws.interpolate_state_dicts(sd_a, sd_b, 0.0)
    assert torch.allclose(out["w"], sd_a["w"])


def test_interpolate_alpha_one_returns_second_endpoint():
    sd_a = _f({"w": [1.0]})
    sd_b = _f({"w": [99.0]})
    out = ws.interpolate_state_dicts(sd_a, sd_b, 1.0)
    assert torch.allclose(out["w"], sd_b["w"])


def test_interpolate_midpoint_is_linear():
    sd_a = _f({"w": [0.0, 4.0]})
    sd_b = _f({"w": [10.0, 0.0]})
    out = ws.interpolate_state_dicts(sd_a, sd_b, 0.5)
    assert torch.allclose(out["w"], torch.tensor([5.0, 2.0]))


def test_interpolate_preserves_dtype_for_float64():
    sd_a = {"w": torch.tensor([1.0, 2.0], dtype=torch.float64)}
    sd_b = {"w": torch.tensor([3.0, 4.0], dtype=torch.float64)}
    out = ws.interpolate_state_dicts(sd_a, sd_b, 0.5)
    assert out["w"].dtype == torch.float64


def test_interpolate_takes_second_for_non_floating_types():
    sd_a = {"counter": torch.tensor(100, dtype=torch.long)}
    sd_b = {"counter": torch.tensor(200, dtype=torch.long)}
    out = ws.interpolate_state_dicts(sd_a, sd_b, 0.3)
    assert out["counter"].dtype == torch.long
    assert int(out["counter"].item()) == 200


# ----------------------------------------------------------------------------
# alpha_tag
# ----------------------------------------------------------------------------

def test_alpha_tag_zero_padded_three_digits():
    assert ws.alpha_tag(0.0) == "a000"
    assert ws.alpha_tag(0.1) == "a010"
    assert ws.alpha_tag(0.5) == "a050"
    assert ws.alpha_tag(1.0) == "a100"


def test_alpha_tag_rounds_to_two_decimals():
    assert ws.alpha_tag(0.333) == "a033"
    assert ws.alpha_tag(0.666) == "a067"


# ----------------------------------------------------------------------------
# default_alpha_grid
# ----------------------------------------------------------------------------

def test_default_alpha_grid_has_eleven_points_from_zero_to_one():
    grid = ws.default_alpha_grid()
    assert len(grid) == 11
    assert grid[0] == pytest.approx(0.0)
    assert grid[-1] == pytest.approx(1.0)


def test_default_alpha_grid_is_strictly_increasing():
    grid = ws.default_alpha_grid()
    for prev, nxt in zip(grid, grid[1:]):
        assert prev < nxt


# ----------------------------------------------------------------------------
# parse_shape_summary
# ----------------------------------------------------------------------------

def test_parse_shape_summary_extracts_overall_and_per_stage():
    summary = {
        "profile": "shape_val_unseen",
        "total_count": 60,
        "overall_avg_psnr": 26.5,
        "overall_avg_ssim": 0.901,
        "stages": [
            {"stage": "stage_01_triangles", "avg_psnr": 26.0, "avg_ssim": 0.85, "count": 30},
            {"stage": "stage_02_circles", "avg_psnr": 27.0, "avg_ssim": 0.93, "count": 30},
        ],
    }
    parsed = ws.parse_shape_summary(summary)
    assert parsed["overall_psnr"] == pytest.approx(26.5)
    assert parsed["overall_ssim"] == pytest.approx(0.901)
    assert parsed["per_stage"]["stage_01_triangles"]["psnr"] == pytest.approx(26.0)
    assert parsed["per_stage"]["stage_02_circles"]["ssim"] == pytest.approx(0.93)


# ----------------------------------------------------------------------------
# parse_ring_guard_summary
# ----------------------------------------------------------------------------

def _ring_summary_template() -> dict:
    return {
        "candidate": "avg_a050",
        "datasets": [
            {
                "short_name": "pitch1um_y_100",
                "expected_step_px": 8.0,
                "r39_internal_step_std_y": 0.20,
                "combo_internal_step_std_y": 0.14,
                "delta_internal_step_std_y": 0.06,
                "r39_outer_residual_mean": 3.0,
                "r39_inner_residual_mean": 2.7,
            },
            {
                "short_name": "pitch0p1um_y_60",
                "expected_step_px": 0.8,
                "r39_internal_step_std_y": 0.17,
                "combo_internal_step_std_y": 0.15,
                "delta_internal_step_std_y": 0.02,
                "r39_outer_residual_mean": 2.7,
                "r39_inner_residual_mean": 2.6,
            },
            {
                "short_name": "pitch0p01um_y_40",
                "expected_step_px": 0.08,
                "r39_internal_step_std_y": 0.18,
                "combo_internal_step_std_y": 0.12,
                "delta_internal_step_std_y": 0.06,
                "r39_outer_residual_mean": 2.7,
                "r39_inner_residual_mean": 2.6,
            },
        ],
    }


def test_parse_ring_guard_summary_extracts_three_scales():
    parsed = ws.parse_ring_guard_summary(_ring_summary_template())
    assert parsed["scales"]["pitch1um_y_100"]["step_std"] == pytest.approx(0.20)
    assert parsed["scales"]["pitch1um_y_100"]["delta_vs_combo"] == pytest.approx(0.06)
    assert parsed["scales"]["pitch0p1um_y_60"]["step_std"] == pytest.approx(0.17)
    assert parsed["scales"]["pitch0p01um_y_40"]["outer_residual_mean"] == pytest.approx(2.7)
    assert parsed["scales"]["pitch0p01um_y_40"]["inner_residual_mean"] == pytest.approx(2.6)


# ----------------------------------------------------------------------------
# combine_sweep_row
# ----------------------------------------------------------------------------

def test_combine_sweep_row_includes_alpha_and_both_metrics():
    shape = ws.parse_shape_summary({
        "profile": "shape_val_unseen",
        "total_count": 30,
        "overall_avg_psnr": 26.5,
        "overall_avg_ssim": 0.9,
        "stages": [{"stage": "stage_01_triangles", "avg_psnr": 26.0, "avg_ssim": 0.9, "count": 30}],
    })
    ring = ws.parse_ring_guard_summary(_ring_summary_template())
    row = ws.combine_sweep_row(0.5, shape, ring)
    assert row["alpha"] == pytest.approx(0.5)
    assert row["alpha_tag"] == "a050"
    assert row["shape_overall_psnr"] == pytest.approx(26.5)
    assert row["shape_overall_ssim"] == pytest.approx(0.9)
    assert row["ring_8px_step_std"] == pytest.approx(0.20)
    assert row["ring_0p8px_step_std"] == pytest.approx(0.17)
    assert row["ring_0p08px_step_std"] == pytest.approx(0.18)


# ----------------------------------------------------------------------------
# evaluate_sweet_spot
# ----------------------------------------------------------------------------

def _row(alpha: float, psnr: float, s8: float, s08: float, s008: float) -> dict:
    return {
        "alpha": alpha,
        "alpha_tag": ws.alpha_tag(alpha),
        "shape_overall_psnr": psnr,
        "ring_8px_step_std": s8,
        "ring_0p8px_step_std": s08,
        "ring_0p08px_step_std": s008,
    }


def test_evaluate_sweet_spot_finds_satisfying_alpha():
    rows = [
        _row(0.0, 22.84, 0.1389, 0.1509, 0.1185),
        _row(0.3, 24.9,  0.150,  0.155,  0.130),
        _row(1.0, 30.07, 0.2044, 0.1711, 0.1811),
    ]
    thr = ws.SweetSpotThresholds(
        min_shape_psnr=24.84, max_8px=0.155, max_0p8px=0.155, max_0p08px=0.135
    )
    result = ws.evaluate_sweet_spot(rows, thr)
    assert result["found"] is True
    assert result["best"]["alpha"] == pytest.approx(0.3)


def test_evaluate_sweet_spot_returns_no_match_with_reason():
    rows = [
        _row(0.0, 22.84, 0.1389, 0.1509, 0.1185),
        _row(1.0, 30.07, 0.2044, 0.1711, 0.1811),
    ]
    thr = ws.SweetSpotThresholds(
        min_shape_psnr=24.84, max_8px=0.150, max_0p8px=0.150, max_0p08px=0.130
    )
    result = ws.evaluate_sweet_spot(rows, thr)
    assert result["found"] is False
    assert isinstance(result["reason"], str) and len(result["reason"]) > 0


def test_evaluate_sweet_spot_picks_highest_psnr_when_multiple_match():
    rows = [
        _row(0.2, 24.5, 0.150, 0.150, 0.125),
        _row(0.4, 25.5, 0.152, 0.151, 0.130),
    ]
    thr = ws.SweetSpotThresholds(
        min_shape_psnr=24.0, max_8px=0.155, max_0p8px=0.155, max_0p08px=0.135
    )
    result = ws.evaluate_sweet_spot(rows, thr)
    assert result["found"] is True
    assert result["best"]["alpha"] == pytest.approx(0.4)
