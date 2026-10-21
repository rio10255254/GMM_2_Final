from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def runner():
    path = ROOT / "scripts" / "run_r68.py"
    spec = importlib.util.spec_from_file_location("r68_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_external_r61_inputs_are_complete():
    module = runner()
    config = module.read_json(module.CONFIG_PATH)
    audit = module.validate_inputs(config)
    assert audit["total_frames"] == 301
    assert len(audit["sequences"]) == 6


def test_gate_requires_every_check():
    module = runner()
    gates = module.read_json(module.CONFIG_PATH)["gates"]
    good = {
        "sequence": "good", "valid_fraction": 1.0, "direction_agreement_fraction": 1.0,
        "median_scale_error_fraction": 0.01, "median_difference_of_step": 0.02,
        "p95_difference_of_step": 0.05, "median_response_ratio": 0.9, "median_r61_ecc": 0.98,
    }
    bad = dict(good, sequence="bad", median_response_ratio=0.1)
    output = module.apply_gates(pd.DataFrame([good, bad]), gates)
    assert bool(output.loc[output["sequence"].eq("good"), "sequence_pass"].iloc[0])
    assert not bool(output.loc[output["sequence"].eq("bad"), "sequence_pass"].iloc[0])
