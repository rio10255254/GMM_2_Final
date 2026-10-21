from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from run_v42_local_edge_validation import CASES, select_case_symmetric_steps, total_uncertainty_nm


def test_selection_keeps_identical_step_keys_for_every_case() -> None:
    rows = pd.DataFrame(
        [
            {"dataset": "d", "group": "g", "step_index": step, "case": case}
            for step in [1, 2, 3]
            for case in ["raw", "v41_standalone", "v42_e120"]
        ]
        + [{"dataset": "d", "group": "g", "step_index": 4, "case": "raw"}]
    )

    selected = select_case_symmetric_steps(
        rows,
        cases=["raw", "v41_standalone", "v42_e120"],
        chosen_keys=pd.DataFrame([{"dataset": "d", "group": "g", "step_index": 2}]),
    )

    assert set(selected["step_index"]) == {2}
    assert set(selected["case"]) == {"raw", "v41_standalone", "v42_e120"}
    assert len(selected) == 3


def test_total_uncertainty_uses_repeatability_and_localization_terms() -> None:
    assert total_uncertainty_nm(3.0, 4.0) == 5.0


def test_selection_allows_equal_case_repeats_from_multiple_edge_modes() -> None:
    rows = pd.DataFrame(
        [
            {
                "dataset": "d",
                "group": "g",
                "step_index": 1,
                "case": case,
                "edge_mode": edge_mode,
            }
            for edge_mode in ["self", "guided"]
            for case in ["raw", "v41_standalone", "v42_e120"]
        ]
    )

    selected = select_case_symmetric_steps(rows, CASES, chosen_keys=None)

    assert len(selected) == 6
    assert selected.groupby("case").size().nunique() == 1
