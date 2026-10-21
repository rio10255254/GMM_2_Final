from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r52_corner_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r52_corner_gate", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_corner_gate_rejects_median_only_improvement_when_large_error_rate_worsens():
    module = load_module()
    control = module.CornerMetrics(case="lab_r40_best_tradeoff", median_px=4.243, p90_px=12.728, over_5px_pct=24.581)
    r51_like = module.CornerMetrics(case="lab_r51_mixed_psf_best_tradeoff", median_px=2.828, p90_px=11.314, over_5px_pct=36.872)

    decision = module.evaluate_candidate(r51_like, control)

    assert decision["pass"] is False
    assert "large_error_rate_regressed" in decision["failed_rules"]
    assert "median_improved" in decision["passed_rules"]


def test_corner_gate_accepts_candidate_that_improves_median_and_large_error_rate():
    module = load_module()
    control = module.CornerMetrics(case="lab_r40_best_tradeoff", median_px=4.243, p90_px=12.728, over_5px_pct=24.581)
    good = module.CornerMetrics(case="lab_r52_stability_best_tradeoff", median_px=2.7, p90_px=9.8, over_5px_pct=18.0)

    decision = module.evaluate_candidate(good, control)

    assert decision["pass"] is True
    assert decision["failed_rules"] == []
    assert {"median_improved", "large_error_rate_not_worse", "tail_not_worse"} <= set(decision["passed_rules"])
