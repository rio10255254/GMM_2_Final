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


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_project_structure", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_legacy_operations_docs_contract():
    assert (REPO / "docs" / "index" / "LEGACY_ROUNDS_OPERATIONS.md").exists()
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


def test_legacy_gitignore_only_allows_whitelisted_governance_docs():
    allowed = [
        REPO / "Traing_Progress" / "organized_20260313" / "round18" / "README.md",
        REPO / "Traing_Progress" / "organized_20260314" / "round20" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260315" / "pairwise_delta_probe" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round23" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "external_compare_r18_r22_r25" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260316" / "tta_experiment" / "r26_tta_cross5" / "README.md",
    ]
    blocked = [
        REPO / "Traing_Progress" / "organized_20260313" / "round18" / "external_validation" / "future_note" / "README.md",
        REPO / "Traing_Progress" / "organized_20260314" / "branch_e" / "archive" / "future_note" / "MANIFEST.md",
        REPO / "Traing_Progress" / "organized_20260315" / "round22" / "selected" / "reports" / "extra" / "README.md",
        REPO / "Traing_Progress" / "organized_20260316" / "round23" / "archive" / "future_note" / "README.md",
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
