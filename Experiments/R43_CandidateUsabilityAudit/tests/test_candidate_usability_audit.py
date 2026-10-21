from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "candidate_usability_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("candidate_usability_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_external_gate_allows_r39_tradeoff_but_rejects_r40_8px_regression():
    audit = _load_module()

    r39 = {"8px": 0.143794, "0p8px": 0.140008, "0p08px": 0.083941}
    r40 = {"8px": 0.189750, "0p8px": 0.133314, "0p08px": 0.097048}

    assert audit.external_status(r39).label == "PASS_TRADEOFF"
    assert audit.external_status(r40).label == "FAIL_8PX_REGRESSION"


def test_local_ring_guard_uses_scale_specific_limits():
    audit = _load_module()

    near_combo = {"8px": 0.1384, "0p8px": 0.1507, "0p08px": 0.1114}
    r42_fail = {"8px": 0.1715, "0p8px": 0.2121, "0p08px": 0.1673}

    assert audit.local_ring_status(near_combo).pass_gate is True
    assert audit.local_ring_status(r42_fail).pass_gate is False


def test_candidate_classification_separates_formal_and_specialist_use():
    audit = _load_module()

    r39 = audit.Candidate(
        candidate_id="R39_a030",
        display_name="R39 a030",
        source_round="R39",
        role="shape_generalization",
        external={"8px": 0.143794, "0p8px": 0.140008, "0p08px": 0.083941},
        local_ring={"8px": 0.1384, "0p8px": 0.1507, "0p08px": 0.1114},
        shape={"psnr": 25.0326, "ssim": 0.8798},
    )
    r42 = audit.Candidate(
        candidate_id="R42_r41_latest",
        display_name="R42 r41 latest",
        source_round="R42",
        role="boundary_specialist",
        local_ring={"8px": 0.2442, "0p8px": 0.2513, "0p08px": 0.2154},
        boundary={"psnr": 34.18, "hf": 0.80, "distance": 3.60, "f1": 0.87},
    )
    low_alpha = audit.Candidate(
        candidate_id="R42_low_alpha_a003",
        display_name="R42 low alpha a003",
        source_round="R42",
        role="low_alpha_probe",
        local_ring={"8px": 0.1399, "0p8px": 0.1487, "0p08px": 0.1232},
        boundary={"psnr": 20.8252, "hf": 0.2127, "distance": 7.5293, "f1": 0.6420},
    )

    assert audit.classify_candidate(r39).category == "alternate_grade"
    assert audit.classify_candidate(r42).category == "specialist_research_use"
    assert audit.classify_candidate(low_alpha).category == "not_useful_tradeoff"


def test_overall_score_prefers_real_capability_over_guard_only():
    audit = _load_module()

    guarded_without_gain = audit.Candidate(
        candidate_id="guarded_without_gain",
        display_name="Guarded without gain",
        source_round="probe",
        role="diagnostic",
        local_ring={"8px": 0.1387, "0p8px": 0.1567, "0p08px": 0.1121},
        boundary={"psnr": 20.6423, "hf": 0.2048, "distance": 7.6609, "f1": 0.6310},
    )
    strong_boundary = audit.Candidate(
        candidate_id="strong_boundary",
        display_name="Strong boundary",
        source_round="probe",
        role="diagnostic",
        local_ring={"8px": 0.1715, "0p8px": 0.2121, "0p08px": 0.1673},
        boundary={"psnr": 32.89, "hf": 0.75, "distance": 3.48, "f1": 0.87},
    )

    assert audit.usability_score(strong_boundary) > audit.usability_score(guarded_without_gain)
