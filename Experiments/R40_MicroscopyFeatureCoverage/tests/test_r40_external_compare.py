from __future__ import annotations

import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def test_compute_step_stats_removes_only_extreme_gmf_failures():
    import r40_external_compare as ec

    pos_y = [0.0]
    for _ in range(99):
        pos_y.append(pos_y[-1] - 8.0)
    pos_y[51] = pos_y[50] - 1.5
    pos_y[52] = pos_y[51] - 14.5

    stats = ec.compute_step_stats(pos_y, z_threshold=5.0)

    assert stats["n_outliers"] == 2
    assert stats["filtered_std"] < stats["raw_std"]


def test_verdict_distinguishes_upgrade_guard_from_capacity_only():
    import r40_external_compare as ec

    combo = {"8px": 0.154515, "0p8px": 0.131560, "0p08px": 0.099891}
    guarded = {"8px": 0.150, "0p8px": 0.132, "0p08px": 0.096}
    capacity_only = {"8px": 0.180, "0p8px": 0.150, "0p08px": 0.110}

    guarded_v = ec.verdict_against_combo(guarded, combo, upgrade_cap_pct=3.0)
    capacity_v = ec.verdict_against_combo(capacity_only, combo, upgrade_cap_pct=3.0)

    assert guarded_v["overall"] == "PASS_UPGRADE_GUARD"
    assert capacity_v["overall"] == "RESEARCH_CAPACITY_ONLY"
    assert capacity_v["per_scale"]["8px"]["status"] == "REGRESSED"


def test_parse_gmf_score_reads_posy_sorted(tmp_path: Path):
    import r40_external_compare as ec

    f = tmp_path / "GMF_score.txt"
    f.write_text(
        "FileName, B.bmp, PosY, 92.0, PosX, 1, Score0, 91\n"
        "FileName, A.bmp, PosY, 100.0, PosX, 1, Score0, 90\n",
        encoding="utf-8",
    )

    parsed = ec.parse_gmf_score(f)

    assert ec.pos_y_series_sorted(parsed) == [100.0, 92.0]
