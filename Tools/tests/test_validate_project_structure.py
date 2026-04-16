from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO / "Tools" / "validate_project_structure.py"

LEGACY_BATCH_SPECS = {
    "organized_20260313": [
        "root_status_legacy",
        "round16",
        "round17",
        "round18",
        "round19",
    ],
    "organized_20260314": [
        "round20",
        "diagnostics",
        "branch_e",
    ],
    "organized_20260315": [
        "round21",
        "round22",
        "pairwise_delta_probe",
        "branch_e_followup",
        "estimator_formula_probe",
    ],
    "organized_20260316": [
        "round23",
        "round24",
        "round25",
        "round26",
        "round27",
        "round28",
        "round29",
        "round30",
        "round31",
        "external_compare_round18_round22",
        "external_compare_r18_r22_r25",
        "external_compare_r18_r22_r25_r26",
        "external_compare_r18_r22_r25_r26_r27",
        "external_compare_r18_r22_r25_r26_r27_r28",
        "external_compare_r18_r22_r25_r26_r27_r28_r29",
        "external_compare_r18_r22_r25_r26r18_highcenter",
        "external_compare_r18_r22_r25_r26r22_hold",
        "external_compare_r18_r22_r25_r26r25_sw010",
        "external_compare_r18_r22_r25_r26r26_sm035",
        "analysis",
        "tta_experiment",
        "tta_experiment/r26_tta_cross5",
    ],
}
TRUTH_PLANE_DOCS = [
    "PROJECT_STATE.md",
    "README.md",
    "PROJECT_ARCHITECTURE.md",
]
LEGACY_RUNTIME_OLD_ROOT = "docs/runtime/legacy/root_status/"
LEGACY_RUNTIME_ARCHIVE_ROOT = "docs/archive/legacy_runtime_status/"
LEGACY_RUNTIME_FORMAL_DOCS = [
    "PROJECT_STATE.md",
    "README.md",
    "REPO_GOVERNANCE.md",
    "docs/README.md",
    "docs/operations/SOURCE_OF_TRUTH_POLICY.md",
]
REQUIRED_TRUTH_PLANE_KEYS = {
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
FORBIDDEN_TRUTH_PLANE_KEYS = {
    "active_baseline_policy",
    "latest_internal_frontier",
    "latest_falsified_branch",
    "active_experiment",
}
TRUTH_PLANE_FORBIDDEN_PHRASES = [
    "pending R33 promotion",
    "active sandbox overview",
    "360→720+",
    "目前 active 沙盒：`R26NewPSFCheck`",
    "current winning line",
]
CANONICAL_INFERENCE_SCRIPTS = [
    "Model/GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py",
    "Model/GeoEdgeAlignSR_v1_Infer_TTA.py",
]
CANONICAL_SEQUENCE_ANALYSIS_SCRIPT = "AnalysisLab/r26/sequence/scripts/run_sequence_analysis.py"
REQUIRED_SEQUENCE_ANALYSIS_ANGLE_COUNT = 720
OFFICIAL_STANDARD_HEALTH_COMMAND = "python Tools/project_control_center.py --view health --health-level standard"


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_project_structure", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_legacy_operations_docs_contract():
    assert (REPO / "docs" / "operations" / "LEGACY_ROUNDS_OPERATIONS.md").exists()
    for batch_name, surfaces in LEGACY_BATCH_SPECS.items():
        legacy_root = REPO / "Traing_Progress" / batch_name
        assert legacy_root.is_dir(), f"Missing legacy batch: {batch_name}"
        assert (legacy_root / "README.md").exists(), f"{batch_name} missing README.md"
        assert (legacy_root / "MANIFEST.md").exists(), f"{batch_name} missing MANIFEST.md"

        for dirname in surfaces:
            surface = legacy_root / dirname
            assert surface.is_dir(), f"Missing legacy surface: {batch_name}/{dirname}"
            assert (surface / "README.md").exists(), f"{batch_name}/{dirname} missing README.md"
            assert (surface / "MANIFEST.md").exists(), f"{batch_name}/{dirname} missing MANIFEST.md"


def test_validator_declares_legacy_surfaces():
    module = load_validator_module()

    assert hasattr(module, "LEGACY_BATCH_SPECS")
    assert module.LEGACY_BATCH_SPECS == LEGACY_BATCH_SPECS
    assert module.CANONICAL_INFERENCE_SCRIPTS == CANONICAL_INFERENCE_SCRIPTS
    assert module.CANONICAL_SEQUENCE_ANALYSIS_SCRIPT == CANONICAL_SEQUENCE_ANALYSIS_SCRIPT
    assert module.REQUIRED_SEQUENCE_ANALYSIS_ANGLE_COUNT == REQUIRED_SEQUENCE_ANALYSIS_ANGLE_COUNT
    assert module.TRUTH_PLANE_DOCS == TRUTH_PLANE_DOCS
    assert module.LEGACY_RUNTIME_OLD_ROOT == LEGACY_RUNTIME_OLD_ROOT
    assert module.LEGACY_RUNTIME_ARCHIVE_ROOT == LEGACY_RUNTIME_ARCHIVE_ROOT
    assert module.LEGACY_RUNTIME_FORMAL_DOCS == LEGACY_RUNTIME_FORMAL_DOCS
    assert module.REQUIRED_TRUTH_PLANE_KEYS == REQUIRED_TRUTH_PLANE_KEYS
    assert module.FORBIDDEN_TRUTH_PLANE_KEYS == FORBIDDEN_TRUTH_PLANE_KEYS
    assert module.TRUTH_PLANE_FORBIDDEN_PHRASES == TRUTH_PLANE_FORBIDDEN_PHRASES


def test_legacy_gitignore_only_allows_whitelisted_governance_docs():
    allowed = [
        REPO / "Traing_Progress" / "organized_20260313" / "round18" / "README.md",
        REPO / "Traing_Progress" / "organized_20260314" / "round20" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260315" / "pairwise_delta_probe" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round23" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round31" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260316" / "external_compare_r18_r22_r25" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260316" / "tta_experiment" / "r26_tta_cross5" / "README.md",
    ]
    blocked = [
        REPO / "Traing_Progress" / "organized_20260313" / "round18" / "external_validation" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260314" / "branch_e" / "archive" / "future_note" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260315" / "round22" / "selected" / "reports" / "extra" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round23" / "archive" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round31" / "archive" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round30" / "gmf_results" / "raw" / "r30_b1_dironly" / "pitch8px" / "MANIFEST.md",
    ]

    for path in allowed:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1, f"Expected tracked governance doc, but gitignore still hides {path}"

    for path in blocked:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Expected ignored artifact-side doc, but gitignore re-opened {path}"


def test_truth_plane_docs_and_policy_contract():
    policy = (REPO / "ESTIMATOR_POLICY.json").read_text(encoding="utf-8")
    for key in REQUIRED_TRUTH_PLANE_KEYS:
        assert f"\"{key}\"" in policy
    for key in FORBIDDEN_TRUTH_PLANE_KEYS:
        assert f"\"{key}\"" not in policy

    for doc_name in TRUTH_PLANE_DOCS:
        text = (REPO / doc_name).read_text(encoding="utf-8")
        assert "COMBO" in text, f"{doc_name} should mention COMBO"
        for phrase in TRUTH_PLANE_FORBIDDEN_PHRASES:
            assert phrase not in text, f"{doc_name} still contains stale phrase: {phrase}"


def test_sequence_analysis_contract():
    script = REPO / CANONICAL_SEQUENCE_ANALYSIS_SCRIPT
    text = script.read_text(encoding="utf-8")
    assert f"n_angles={REQUIRED_SEQUENCE_ANALYSIS_ANGLE_COUNT}" in text


def test_pre_commit_template_runs_official_standard_health():
    hook = (REPO / "Tools" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert OFFICIAL_STANDARD_HEALTH_COMMAND in hook


def _load_validator_module(repo_dir: Path):
    spec = importlib.util.spec_from_file_location("vps", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO = repo_dir
    module.ERRORS.clear()
    module.WARNINGS.clear()
    return module


def test_quick_handoff_region_within_limit(tmp_path):
    (tmp_path / "PROJECT_STATE.md").write_text(
        "# state\n"
        "<!-- QUICK_HANDOFF_START -->\n"
        + "line\n" * 30
        + "<!-- QUICK_HANDOFF_END -->\n"
        "rest\n",
        encoding="utf-8",
    )
    module = _load_validator_module(tmp_path)
    module.check_quick_handoff_length()
    assert not module.ERRORS, f"30 lines should pass, got errors: {module.ERRORS}"


def test_quick_handoff_region_exceeds_limit(tmp_path):
    (tmp_path / "PROJECT_STATE.md").write_text(
        "# state\n"
        "<!-- QUICK_HANDOFF_START -->\n"
        + "line\n" * 70
        + "<!-- QUICK_HANDOFF_END -->\n",
        encoding="utf-8",
    )
    module = _load_validator_module(tmp_path)
    module.check_quick_handoff_length()
    assert any("Quick Handoff" in err for err in module.ERRORS), \
        f"Expected Quick Handoff error, got: {module.ERRORS}"
