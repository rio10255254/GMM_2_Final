from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_20x_0p5um_diagnostic import run_diagnostic  # noqa: E402


def test_diagnostic_identifies_the_pause_related_stage_event(tmp_path: Path) -> None:
    outputs = run_diagnostic(output_root=tmp_path)
    steps = pd.read_csv(outputs["steps"]).set_index("step_index")

    step_15 = steps.loc[15]
    assert step_15["gap_seconds"] == 48.0
    assert step_15["raw_locked_dx_um"] == pytest.approx(-0.03042, abs=0.005)
    assert step_15["v42_locked_dx_um"] == pytest.approx(-0.03480, abs=0.005)
    assert step_15["raw_local_dx_um"] == pytest.approx(-0.02600, abs=0.006)
    assert step_15["v42_local_dx_um"] == pytest.approx(-0.02422, abs=0.006)
    assert step_15["raw_local_dy_um"] == pytest.approx(-0.57952, abs=0.03)
    assert step_15["v42_local_dy_um"] == pytest.approx(-0.58254, abs=0.03)


def test_raw_and_v42_share_the_same_dominant_motion_error(tmp_path: Path) -> None:
    outputs = run_diagnostic(output_root=tmp_path)
    evidence = pd.read_csv(outputs["evidence"]).set_index("metric")["value"]

    assert evidence["locked_raw_v42_step_correlation"] > 0.98
    assert evidence["local_raw_v42_step_correlation"] > 0.98
    assert evidence["locked_vs_local_raw_correlation"] > 0.98
    assert evidence["locked_vs_local_v42_correlation"] > 0.98
    assert evidence["maximum_timestamp_gap_seconds"] == 48.0
    assert evidence["timestamp_sessions_at_60_seconds"] == 1.0


def test_population_summary_keeps_full_and_timing_defined_views(tmp_path: Path) -> None:
    outputs = run_diagnostic(output_root=tmp_path)
    summary = pd.read_csv(outputs["populations"]).set_index(["population", "case"])

    assert summary.loc[("all_49_steps", "Raw"), "step_count"] == 49
    assert summary.loc[("all_49_steps", "Raw"), "signed_step_sd_nm"] == pytest.approx(
        74.45083, abs=0.02
    )
    assert summary.loc[("all_49_steps", "V42 epoch 120"), "signed_step_sd_nm"] == pytest.approx(
        75.65882, abs=0.02
    )
    assert summary.loc[("gap_at_most_30_seconds", "Raw"), "step_count"] == 48
    assert summary.loc[("gap_at_most_30_seconds", "Raw"), "signed_step_sd_nm"] == pytest.approx(
        32.05179, abs=0.02
    )
    assert summary.loc[("regular_cadence_at_most_10_seconds", "Raw"), "step_count"] == 44
    assert summary.loc[
        ("regular_cadence_at_most_10_seconds", "V42 epoch 120"),
        "signed_step_sd_nm",
    ] == pytest.approx(20.78962, abs=0.02)


def test_diagnostic_exports_reviewable_figures_and_report(tmp_path: Path) -> None:
    outputs = run_diagnostic(output_root=tmp_path)
    for name in (
        "gap_motion_figure",
        "step_trace_figure",
        "correlation_figure",
        "population_figure",
        "event_figure",
        "report",
        "metadata",
    ):
        assert outputs[name].is_file(), name

