from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_50x_0p5um_sessions import (  # noqa: E402
    build_pair_audit,
    detect_timestamp_sessions,
    load_acquisition_mapping,
    run_session_analysis,
)


MAPPING = Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\input_mapping.csv")


def test_timestamp_sessions_are_stable_across_reasonable_thresholds() -> None:
    mapping = load_acquisition_mapping(MAPPING, group="x_0p5um")

    starts_by_threshold = {
        threshold: detect_timestamp_sessions(mapping, threshold_seconds=threshold)
        .loc[lambda table: table["session_start"], "frame_index"]
        .tolist()
        for threshold in (45, 60, 90, 120, 180)
    }

    assert all(starts == [0, 27, 31] for starts in starts_by_threshold.values())


def test_session_detection_depends_only_on_timestamps() -> None:
    mapping = load_acquisition_mapping(MAPPING, group="x_0p5um")
    baseline = detect_timestamp_sessions(mapping, threshold_seconds=60)
    modified = mapping.assign(
        model_score=list(reversed(range(len(mapping)))),
        image_quality=["bad" if index % 2 else "good" for index in range(len(mapping))],
    )
    changed = detect_timestamp_sessions(modified, threshold_seconds=60)

    assert baseline[["frame_index", "session_id", "session_start"]].equals(
        changed[["frame_index", "session_id", "session_start"]]
    )


def test_pair_audit_reconciles_all_50_pairs_and_two_session_breaks() -> None:
    mapping = load_acquisition_mapping(MAPPING, group="x_0p5um")
    sessions = detect_timestamp_sessions(mapping, threshold_seconds=60)

    pairs = build_pair_audit(sessions)

    assert len(pairs) == 50
    assert int(pairs["included_within_session"].sum()) == 48
    excluded = pairs.loc[~pairs["included_within_session"]]
    assert excluded["end_frame_index"].tolist() == [27, 31]
    assert excluded["gap_seconds"].tolist() == pytest.approx([1321.0, 283.0])
    assert set(excluded["exclusion_reason"]) == {"cross_acquisition_session"}


def test_real_session_analysis_recovers_all_48_within_session_steps(
    tmp_path: Path,
) -> None:
    outputs = run_session_analysis(output_root=tmp_path)
    steps = pd.read_csv(outputs["steps"])
    summary = pd.read_csv(outputs["summary"])
    pairs = pd.read_csv(outputs["pair_audit"])
    anchors = pd.read_csv(outputs["shifts"])

    assert len(pairs) == 50
    assert len(steps) == 48
    assert steps["common_valid"].all()
    assert (steps["common_pillars"] == 9).all()
    assert summary.set_index("case").loc["Raw", "signed_step_sd_nm"] == pytest.approx(
        8.03105, abs=0.02
    )
    assert summary.set_index("case").loc[
        "V42 epoch 120", "signed_step_sd_nm"
    ] == pytest.approx(6.18281, abs=0.02)
    assert anchors["frame_index"].tolist() == [0, 27, 31]
    assert anchors["absolute_y_px"].tolist() == pytest.approx(
        [0.0, 12.65615, 14.41309], abs=0.03
    )
    assert (anchors["anchor_match_score"] > 0.99).all()
    assert outputs["timestamp_figure"].is_file()
    assert outputs["shift_figure"].is_file()
    assert outputs["step_figure"].is_file()
