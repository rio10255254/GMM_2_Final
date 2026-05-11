from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO / "ESTIMATOR_POLICY.json"
ACCESSOR_PATH = REPO / "Model" / "GeoEdgeAlignSR_v1_PolicyAccess.py"


def load_policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def load_accessor_module():
    spec = importlib.util.spec_from_file_location("GeoEdgeAlignSR_v1_PolicyAccess", ACCESSOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_policy_uses_truth_plane_schema():
    policy = load_policy()

    assert set(policy) >= {
        "meta",
        "formal_baseline",
        "approved_alternates",
        "research_state",
        "open_side_tracks",
        "closed_lines",
        "measurement_policy",
        "sources",
        "notes",
    }
    assert "active_baseline_policy" not in policy
    assert "latest_internal_frontier" not in policy
    assert "latest_falsified_branch" not in policy
    assert "active_experiment" not in policy

    formal = policy["formal_baseline"]
    assert formal["candidate_id"] == "COMBO"
    assert formal["status"] == "formal_production_baseline"
    assert formal["decision_effective_date"] == "2026-04-08"

    approved = policy["approved_alternates"]
    assert [item["candidate_id"] for item in approved] == ["R33", "R38v2", "R39R40_avg_a025"]

    side_tracks = policy["open_side_tracks"]
    side_track_by_id = {item["candidate_id"]: item for item in side_tracks}
    assert "R26NewPSFCheck" in side_track_by_id
    assert side_track_by_id["R26NewPSFCheck"]["mainline_status"] == "open_side_track"
    assert "R45_family_boundary_adapter" in side_track_by_id
    assert "R44_motion_fidelity" in side_track_by_id

    research_state = policy["research_state"]
    assert research_state["baseline_challenger_status"] == "none_open"
    assert research_state["current_mainline_status"] == "promoted"
    assert research_state["next_round_policy"] == "new_mechanism_or_deployment_specific_need_only"


def test_policy_accessor_contract():
    module = load_accessor_module()
    policy = load_policy()

    loaded = module.load_estimator_policy(POLICY_PATH)
    assert loaded["formal_baseline"]["candidate_id"] == "COMBO"

    baseline = module.get_formal_baseline(loaded)
    assert baseline["candidate_id"] == "COMBO"
    assert baseline["estimators"]["macro_8px"] == "edge_band_refine"

    guardrails = module.get_measurement_guardrails(loaded)
    assert set(guardrails) >= {"mid_0p8", "macro_8px"}
    assert guardrails["mid_0p8"]["center_improvement_ratio_min"] == 0.25

    sources = module.get_legacy_sources(loaded)
    assert set(sources) >= {"phase2_reevaluation_json", "round26_decision_md"}

    control_center_ref = module.resolve_control_center_ref(loaded)
    assert isinstance(control_center_ref, float)
    assert control_center_ref > 0.0


def _extract_quick_handoff(state_text: str) -> str:
    """Return the QUICK_HANDOFF region (between markers) of PROJECT_STATE.md."""
    start_marker = "<!-- QUICK_HANDOFF_START -->"
    end_marker = "<!-- QUICK_HANDOFF_END -->"
    start = state_text.find(start_marker)
    end = state_text.find(end_marker)
    assert start != -1 and end != -1 and start < end, \
        "PROJECT_STATE.md missing QUICK_HANDOFF markers"
    return state_text[start:end]


def test_root_truth_docs_reflect_combo_promotion():
    state = (REPO / "PROJECT_STATE.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    architecture = (REPO / "PROJECT_ARCHITECTURE.md").read_text(encoding="utf-8")

    for text in [state, readme, architecture]:
        assert "pending R33 promotion" not in text
        assert "360→720+" not in text

    # Quick Handoff 區必須含 COMBO + approved alternates + sandbox branch；
    # 且不能以 mainline 語氣描述 R26NewPSFCheck 或 active sandbox overview。
    quick = _extract_quick_handoff(state)
    assert "COMBO" in quick
    assert (
        "approved alternates" in quick
        or "特化候選" in quick
        or "Approved Alternates" in quick
    )
    assert "sandbox/r38v2" in quick
    assert "active sandbox overview" not in quick
    assert "Experiments\\R26NewPSFCheck\\" not in quick

    # Full current state 必須保留 formal production baseline 字樣
    assert "formal production baseline" in state
    assert "目前 active 沙盒：`R26NewPSFCheck`" not in state
    assert "沒有可直接挑戰 baseline 的 current winning line" not in state

    # README 保留一句話 stub
    assert "COMBO" in readme
    assert "historical former baseline" in readme or "歷史前任 baseline" in readme
