from __future__ import annotations

import sys
from pathlib import Path

import pytest
import torch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def _f(values: dict) -> dict:
    return {k: torch.tensor(v, dtype=torch.float32) for k, v in values.items()}


def test_interpolate_state_dicts_is_linear():
    import r40_weight_sweep as ws

    sd_a = _f({"w": [0.0, 4.0]})
    sd_b = _f({"w": [10.0, 0.0]})
    out = ws.interpolate_state_dicts(sd_a, sd_b, 0.25)
    assert torch.allclose(out["w"], torch.tensor([2.5, 3.0]))


def test_parse_micro_summary_extracts_feature_retention():
    import r40_weight_sweep as ws

    parsed = ws.parse_micro_summary({
        "overall_avg_psnr": 24.0,
        "overall_avg_ssim": 0.7,
        "overall_high_frequency_retention": 0.42,
        "overall_edge_retention": 0.55,
        "stages": [
            {
                "stage": "stage_29_micro_lines_grid",
                "feature_family": "lines_grid",
                "avg_psnr": 23.0,
                "avg_ssim": 0.6,
                "avg_high_frequency_retention": 0.35,
                "avg_edge_retention": 0.44,
                "count": 20,
            }
        ],
    })

    assert parsed["overall_psnr"] == pytest.approx(24.0)
    assert parsed["overall_high_frequency_retention"] == pytest.approx(0.42)
    assert parsed["per_stage"]["stage_29_micro_lines_grid"]["feature_family"] == "lines_grid"


def test_evaluate_capacity_tradeoff_finds_best_guarded_alpha():
    import r40_weight_sweep as ws

    rows = [
        {
            "alpha": 0.0,
            "alpha_tag": "a000",
            "micro_overall_psnr": 20.0,
            "micro_high_frequency_retention": 0.10,
            "ring_8px_step_std": 0.140,
            "ring_0p8px_step_std": 0.150,
            "ring_0p08px_step_std": 0.120,
        },
        {
            "alpha": 0.4,
            "alpha_tag": "a040",
            "micro_overall_psnr": 24.0,
            "micro_high_frequency_retention": 0.45,
            "ring_8px_step_std": 0.150,
            "ring_0p8px_step_std": 0.154,
            "ring_0p08px_step_std": 0.130,
        },
        {
            "alpha": 1.0,
            "alpha_tag": "a100",
            "micro_overall_psnr": 28.0,
            "micro_high_frequency_retention": 0.70,
            "ring_8px_step_std": 0.260,
            "ring_0p8px_step_std": 0.210,
            "ring_0p08px_step_std": 0.190,
        },
    ]
    thresholds = ws.CapacityTradeoffThresholds(
        min_micro_psnr=23.0,
        min_high_frequency_retention=0.30,
        max_8px=0.155,
        max_0p8px=0.155,
        max_0p08px=0.135,
    )

    result = ws.evaluate_capacity_tradeoff(rows, thresholds)

    assert result["found"] is True
    assert result["best"]["alpha"] == pytest.approx(0.4)


def test_evaluate_capacity_tradeoff_marks_capacity_only_when_ring_guard_fails():
    import r40_weight_sweep as ws

    rows = [
        {
            "alpha": 1.0,
            "alpha_tag": "a100",
            "micro_overall_psnr": 28.0,
            "micro_high_frequency_retention": 0.70,
            "ring_8px_step_std": 0.260,
            "ring_0p8px_step_std": 0.210,
            "ring_0p08px_step_std": 0.190,
        },
    ]
    thresholds = ws.CapacityTradeoffThresholds(
        min_micro_psnr=23.0,
        min_high_frequency_retention=0.30,
        max_8px=0.155,
        max_0p8px=0.155,
        max_0p08px=0.135,
    )

    result = ws.evaluate_capacity_tradeoff(rows, thresholds)

    assert result["found"] is False
    assert result["capacity_only_best"]["alpha"] == pytest.approx(1.0)
