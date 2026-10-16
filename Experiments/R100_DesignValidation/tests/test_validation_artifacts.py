from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def assert_finite(value):
    if isinstance(value, dict):
        for child in value.values():
            assert_finite(child)
    elif isinstance(value, list):
        for child in value:
            assert_finite(child)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_core_results_are_complete_and_finite():
    data = read_json("results/core_validation.json")
    assert data["status"] == "complete"
    assert data["synthetic_operator_audit"]["evaluation_view_count"] >= 100
    assert data["synthetic_motion_audit"]["pair_count"] >= 20
    assert data["real_probe"]["sampling"]["patches_per_set"] == 60
    assert data["x1um_motion_audit"]["frame_count"] == 50
    assert_finite(data)


def test_geometry_difference_target_has_identity_invariant():
    data = read_json("results/core_validation.json")["geometry_target_audit"]
    current = data["identity"]["current_target_abs_px"]["mean"]
    difference = data["identity"]["difference_target_abs_px"]["mean"]
    assert difference < 1e-6
    assert current > 0.25


def test_local_operator_has_exact_tiling_contract():
    data = read_json("results/core_validation.json")["tiling_audit"]
    assert data["symmetric_operator_max_abs_gray"] < 1e-3


def test_acm_audit_is_complete():
    data = read_json("results/acm_photometric_audit.json")
    assert data["status"] == "complete"
    assert data["image_count"] == 48
    assert data["measurement_count"] == 144
    assert_finite(data)


def test_integrated_decision_has_evidence_not_a_training_launch():
    data = read_json("reports/design_evidence.json")
    assert data["status"] == "complete"
    assert data["training_authorized_or_started"] is False
    assert len(data["verified_findings"]) >= 5
    assert len(data["design_implications"]) >= 5

