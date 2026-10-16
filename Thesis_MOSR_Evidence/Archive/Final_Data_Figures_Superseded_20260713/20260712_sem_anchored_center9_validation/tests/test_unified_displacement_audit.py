from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from audit_all_displacement_sequences import (  # noqa: E402
    APPROVED_SEQUENCES,
    run_unified_audit,
)
from displacement_audit_core import (  # noqa: E402
    apply_raw_eligibility,
    classify_nm_difference,
    detect_sessions,
    robust_disagreement_nm,
    subpixel_axis_peak,
    summarize_paired_population,
)


CONFIG = PACKAGE / "config" / "sequence_center9.json"
MAPPING_50X = Path(r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\input_mapping.csv")
MAPPING_20X = Path(r"D:\GMM_2_Final\20260704_20x_5x_analysis\input_mapping.csv")


def _mapping(path: Path, group: str) -> pd.DataFrame:
    table = pd.read_csv(path)
    table = table.loc[table["group"] == group].copy()
    table["frame_index"] = pd.to_numeric(table["index"]).astype(int)
    table["timestamp"] = pd.to_datetime(table["timestamp"])
    return table.sort_values("frame_index").reset_index(drop=True)


def test_scope_and_sem_identities_are_exactly_locked() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))["sequences"]
    assert APPROVED_SEQUENCES == (
        "50x_x_0p5um",
        "50x_x_1um",
        "20x_0p5um",
        "20x_1um",
    )
    expected_ids = {22, 23, 24, 28, 29, 30, 34, 35, 36}
    for sequence in APPROVED_SEQUENCES:
        assert {int(row[0]) for row in config[sequence]["centers"]} == expected_ids


@pytest.mark.parametrize(
    ("path", "group", "starts"),
    [
        (MAPPING_50X, "x_0p5um", [0, 27, 31]),
        (MAPPING_50X, "x_1um", [0, 1]),
        (MAPPING_20X, "20x_0p5um", [0]),
        (MAPPING_20X, "20x_1um", [0]),
    ],
)
def test_timestamp_only_session_boundaries(path: Path, group: str, starts: list[int]) -> None:
    sessions = detect_sessions(_mapping(path, group), threshold_seconds=60.0)
    assert sessions.loc[sessions["session_start"], "frame_index"].tolist() == starts


def test_subpixel_axis_rule_and_fallbacks_are_frozen() -> None:
    assert subpixel_axis_peak(np.asarray([1.0, 4.0, 2.0]), 1) == pytest.approx(1.1)
    assert subpixel_axis_peak(np.asarray([1.0, 2.0, 3.0]), 1) == 1.0
    assert subpixel_axis_peak(np.asarray([1.0, 2.0, 1.0]), 0) is None


def test_raw_eligibility_is_independent_of_every_v42_field() -> None:
    raw = pd.DataFrame(
        {
            "cross_session": [False, False, False],
            "anchor_success": [True, True, True],
            "raw_boundary_valid": [True, True, True],
            "raw_boundary_valid_pillars": [9, 9, 9],
            "raw_local_valid_pillars": [9, 9, 9],
            "raw_local_min_match_score": [0.99, 0.99, 0.99],
            "raw_local_dx_um": [-0.50, -0.20, -0.49],
            "raw_local_dy_um": [0.01, 0.01, 0.20],
            "raw_boundary_dx_um": [-0.51, -0.21, -0.48],
            "nominal_step_um": [0.5, 0.5, 0.5],
            "expected_signed_step_um": [-0.5, -0.5, -0.5],
        }
    )
    baseline = apply_raw_eligibility(raw, tolerance_fraction=0.25)
    changed = raw.assign(
        v42_boundary_dx_um=[999.0, np.nan, -999.0],
        v42_evaluable=[False, True, False],
        v42_valid_pillars=[0, 9, 1],
    )
    after = apply_raw_eligibility(changed, tolerance_fraction=0.25)
    assert baseline[["raw_eligible", "raw_exclusion_reasons"]].equals(
        after[["raw_eligible", "raw_exclusion_reasons"]]
    )
    assert baseline["raw_eligible"].tolist() == [True, False, False]


@pytest.mark.parametrize(
    ("raw_nm", "v42_nm", "expected"),
    [
        (10.0, 9.0, "tie"),
        (10.0, 8.999, "improved"),
        (10.0, 11.0, "tie"),
        (10.0, 11.001, "worse"),
    ],
)
def test_one_nm_direction_margin(raw_nm: float, v42_nm: float, expected: str) -> None:
    assert classify_nm_difference(raw_nm, v42_nm, tie_margin_nm=1.0) == expected


def test_metric_formulas_are_independently_recomputable() -> None:
    disagreement = robust_disagreement_nm(
        np.asarray([-3.0, -2.0, -1.0]), object_um_per_px=0.1
    )
    assert disagreement == pytest.approx(148.26)
    paired = pd.DataFrame(
        {
            "raw_boundary_dx_um": [-0.4, -0.5, -0.6],
            "v42_boundary_dx_um": [-0.45, -0.50, -0.55],
            "raw_within_grid_nm": [10.0, 20.0, 30.0],
            "v42_within_grid_nm": [5.0, 10.0, 15.0],
            "v42_evaluable": [True, True, True],
        }
    )
    summary = summarize_paired_population(paired)
    assert summary["raw_signed_step_sd_nm"] == pytest.approx(100.0)
    assert summary["v42_signed_step_sd_nm"] == pytest.approx(50.0)
    assert summary["raw_mean_within_grid_nm"] == pytest.approx(20.0)
    assert summary["v42_mean_within_grid_nm"] == pytest.approx(10.0)


def test_real_audit_reconciles_pairs_and_predeclared_events(tmp_path: Path) -> None:
    outputs = run_unified_audit(output_root=tmp_path)
    pairs = pd.read_csv(outputs["pairs"])
    candidate = pd.read_csv(outputs["candidate"])
    sensitivity = pd.read_csv(outputs["sensitivity"])

    expected_pair_counts = {
        "50x_x_0p5um": 50,
        "50x_x_1um": 49,
        "20x_0p5um": 49,
        "20x_1um": 49,
    }
    assert pairs.groupby("sequence").size().to_dict() == expected_pair_counts
    assert set(candidate["sequence"]) == set(APPROVED_SEQUENCES)
    assert set(candidate["population"]) == {"platform_valid_25pct"}
    assert set(sensitivity["tolerance_fraction"]) == {0.20, 0.25, 0.30}

    keyed = pairs.set_index(["sequence", "end_frame_index"])
    assert keyed.loc[("50x_x_0p5um", 27), "raw_exclusion_reasons_25pct"] == "cross_acquisition_session"
    assert keyed.loc[("50x_x_0p5um", 31), "raw_exclusion_reasons_25pct"] == "cross_acquisition_session"
    assert keyed.loc[("50x_x_1um", 1), "raw_exclusion_reasons_25pct"] == "cross_acquisition_session"
    for frame in (15, 45, 46):
        reasons = keyed.loc[("20x_0p5um", frame), "raw_exclusion_reasons_25pct"]
        assert "raw_x_command_incomplete" in reasons or "raw_y_cross_axis_excess" in reasons

    locked = pd.read_csv(outputs["raw_lock"])
    assert "v42_boundary_dx_um" not in locked.columns
    assert "v42_evaluable" not in locked.columns
    assert outputs["raw_lock_hash"].is_file()

