from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_r67.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("r67_runner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inputs_exist_and_counts_match():
    runner = load_runner()
    roster, scenes = runner.validate_inputs()
    assert len(roster["models"]) == 6
    assert sum(int(item["frame_count"]) for item in scenes["sequences"].values()) == 201


def test_worst_case_rule_penalizes_hidden_failure():
    rows = []
    table = pd.DataFrame(
        [
            {"scene": "easy", "method": "average_star", "error": 1.0},
            {"scene": "hard", "method": "average_star", "error": 100.0},
            {"scene": "easy", "method": "robust", "error": 2.0},
            {"scene": "hard", "method": "robust", "error": 2.0},
        ]
    )
    runner = load_runner()
    runner.add_cells(rows, table, "synthetic", ["scene"], ["error"], ["average_star", "robust"])
    cells = pd.DataFrame(rows)
    worst = cells.groupby("model")["regret"].max()
    assert worst["robust"] < worst["average_star"]

