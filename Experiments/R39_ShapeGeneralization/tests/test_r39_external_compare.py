"""Unit tests for R39 external GMF comparison (parse + step_std + outlier filter)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import r39_external_compare as ec


# ----------------------------------------------------------------------------
# parse_gmf_score
# ----------------------------------------------------------------------------

def test_parse_returns_filename_to_posy(tmp_path):
    f = tmp_path / "GMF_score.txt"
    f.write_text(
        "FileName, A.bmp, Time(ms), 16, PosX, 100.0, PosY, 200.0, Angle, 0, Scale, 1.0, Score0, 90, Score1, 0, Score Diff, 90\n"
        "FileName, B.bmp, Time(ms), 17, PosX, 100.0, PosY, 192.0, Angle, 0, Scale, 1.0, Score0, 91, Score1, 0, Score Diff, 91\n"
        "FileName, C.bmp, Time(ms), 16, PosX, 100.0, PosY, 184.0, Angle, 0, Scale, 1.0, Score0, 92, Score1, 0, Score Diff, 92\n",
        encoding="utf-8",
    )
    parsed = ec.parse_gmf_score(f)
    assert sorted(parsed.keys()) == ["A.bmp", "B.bmp", "C.bmp"]
    assert parsed["A.bmp"]["pos_y"] == pytest.approx(200.0)
    assert parsed["B.bmp"]["pos_y"] == pytest.approx(192.0)


def test_parse_skips_blank_and_malformed_lines(tmp_path):
    f = tmp_path / "GMF_score.txt"
    f.write_text(
        "\n"
        "FileName, A.bmp, PosY, 200.0, PosX, 1, Score0, 90\n"
        "garbage\n"
        "FileName, B.bmp, PosY, 192.0, PosX, 1, Score0, 91\n",
        encoding="utf-8",
    )
    parsed = ec.parse_gmf_score(f)
    assert set(parsed.keys()) == {"A.bmp", "B.bmp"}


def test_parse_raises_when_file_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        ec.parse_gmf_score(tmp_path / "nope.txt")


# ----------------------------------------------------------------------------
# pos_y_series_sorted
# ----------------------------------------------------------------------------

def test_pos_y_series_is_sorted_by_filename():
    parsed = {
        "C.bmp": {"pos_y": 5.0},
        "A.bmp": {"pos_y": 1.0},
        "B.bmp": {"pos_y": 3.0},
    }
    series = ec.pos_y_series_sorted(parsed)
    assert series == [1.0, 3.0, 5.0]


# ----------------------------------------------------------------------------
# compute_step_stats
# ----------------------------------------------------------------------------

def test_step_stats_no_outliers_keeps_all_steps():
    pos_y = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0]
    stats = ec.compute_step_stats(pos_y, z_threshold=5.0)
    assert stats["n_steps"] == 5
    assert stats["n_outliers"] == 0
    assert stats["raw_std"] == pytest.approx(0.0)
    assert stats["filtered_std"] == pytest.approx(0.0)


def test_step_stats_normal_noise_no_outlier_removed():
    pos_y = [0.0, -8.0, -15.9, -24.1, -32.0, -40.05]
    stats = ec.compute_step_stats(pos_y, z_threshold=5.0)
    assert stats["n_steps"] == 5
    assert stats["n_outliers"] == 0
    assert stats["raw_std"] == pytest.approx(stats["filtered_std"])
    assert stats["raw_std"] > 0


def test_step_stats_extreme_outlier_is_removed_and_lowers_std():
    # Reproduces the R33 8px scenario: many clean ~-8 steps, two opposite extreme outliers
    # cancelling each other (GMF detection failure). With N >= 99 and step magnitude
    # an order beyond the typical step, |z| > 5 and the methodology removes them.
    pos_y = [0.0]
    for i in range(99):
        pos_y.append(pos_y[-1] - 8.0)
    # Inject the R33-style cancelling outlier pair near the middle
    pos_y[51] = pos_y[50] - 1.520        # tiny step (z > 5 below median)
    pos_y[52] = pos_y[51] - 14.470       # huge step (z > 5 above median)
    stats = ec.compute_step_stats(pos_y, z_threshold=5.0)
    assert stats["n_steps"] == 99
    assert stats["n_outliers"] == 2
    assert stats["raw_std"] > 0.5
    assert stats["filtered_std"] < 0.2
    assert stats["filtered_std"] < stats["raw_std"]


def test_step_stats_returns_outlier_indices_filenames():
    pos_y = [0.0]
    for i in range(99):
        pos_y.append(pos_y[-1] - 8.0)
    pos_y[51] = pos_y[50] - 1.520
    pos_y[52] = pos_y[51] - 14.470
    filenames = [f"f{i:03d}" for i in range(len(pos_y))]
    stats = ec.compute_step_stats(pos_y, z_threshold=5.0, filenames=filenames)
    flagged_frames = {o["frame"] for o in stats["outliers"]}
    assert any("f051" in f for f in flagged_frames)
    assert any("f052" in f for f in flagged_frames)


def test_step_stats_handles_short_series():
    with pytest.raises(ValueError):
        ec.compute_step_stats([1.0], z_threshold=5.0)


# ----------------------------------------------------------------------------
# verdict_against_combo
# ----------------------------------------------------------------------------

def test_verdict_pass_improved_when_all_three_below_combo():
    a030 = {"8px": 0.140, "0p8px": 0.120, "0p08px": 0.090}
    combo = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
    v = ec.verdict_against_combo(a030, combo)
    assert v["overall"] == "PASS_IMPROVED"
    assert all(s["status"] == "IMPROVED" for s in v["per_scale"].values())


def test_verdict_pass_tradeoff_when_two_improved_one_within_alternate_band():
    # a030 actual: 8px improved, 0.8px regressed +6.4% (within R38v2 alternate band), 0.08px improved
    a030 = {"8px": 0.143794, "0p8px": 0.140008, "0p08px": 0.083941}
    combo = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
    v = ec.verdict_against_combo(a030, combo, tradeoff_max_pct=7.0)
    assert v["overall"] == "PASS_TRADEOFF"
    assert v["per_scale"]["8px"]["status"] == "IMPROVED"
    assert v["per_scale"]["0p8px"]["status"] == "TRADEOFF_OK"
    assert v["per_scale"]["0p08px"]["status"] == "IMPROVED"


def test_verdict_fail_when_one_scale_exceeds_tradeoff_cap():
    a030 = {"8px": 0.143794, "0p8px": 0.180, "0p08px": 0.083941}
    combo = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
    v = ec.verdict_against_combo(a030, combo, tradeoff_max_pct=7.0)
    assert v["overall"] == "FAIL"
    assert v["per_scale"]["0p8px"]["status"] == "REGRESSED"


def test_verdict_mixed_when_only_one_improved_two_within_band():
    a030 = {"8px": 0.143794, "0p8px": 0.140, "0p08px": 0.105}
    combo = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
    v = ec.verdict_against_combo(a030, combo, tradeoff_max_pct=7.0)
    assert v["overall"] == "MIXED"


def test_verdict_uses_default_tradeoff_max_pct_around_seven_percent():
    # 7% is anchored to R38v2's max regression vs COMBO (+6.6% on 0.08px) plus a small slack.
    a030 = {"8px": 0.144, "0p8px": 0.140, "0p08px": 0.084}
    combo = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
    v_default = ec.verdict_against_combo(a030, combo)
    v_explicit = ec.verdict_against_combo(a030, combo, tradeoff_max_pct=7.0)
    assert v_default["overall"] == v_explicit["overall"]
