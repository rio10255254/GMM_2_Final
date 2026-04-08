from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO / "Tools" / "validate_project_structure.py"

LEGACY_ROUND_DIRS = [
    "round23",
    "round24",
    "round25",
    "round26",
    "round27",
    "round28",
    "round29",
    "round30",
]

LEGACY_COMPARE_DIRS = [
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
]

LEGACY_SIDE_DIRS = [
    "analysis",
    "tta_experiment",
    "tta_experiment/r26_tta_cross5",
]


def load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_project_structure", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_legacy_operations_docs_contract():
    legacy_root = REPO / "Traing_Progress" / "organized_20260316"

    assert (REPO / "docs" / "index" / "LEGACY_ROUNDS_OPERATIONS.md").exists()
    assert (legacy_root / "MANIFEST.md").exists()

    for dirname in LEGACY_ROUND_DIRS + LEGACY_COMPARE_DIRS + LEGACY_SIDE_DIRS:
        surface = legacy_root / dirname
        assert surface.is_dir(), f"Missing legacy surface: {dirname}"
        assert (surface / "README.md").exists(), f"{dirname} missing README.md"
        assert (surface / "MANIFEST.md").exists(), f"{dirname} missing MANIFEST.md"


def test_validator_declares_legacy_surfaces():
    module = load_validator_module()

    assert hasattr(module, "LEGACY_BATCH_DIR")
    assert module.LEGACY_BATCH_DIR == Path("Traing_Progress") / "organized_20260316"
    assert hasattr(module, "LEGACY_ROUND_DIRS")
    assert module.LEGACY_ROUND_DIRS == LEGACY_ROUND_DIRS
    assert hasattr(module, "LEGACY_COMPARE_DIRS")
    assert module.LEGACY_COMPARE_DIRS == LEGACY_COMPARE_DIRS
    assert hasattr(module, "LEGACY_SIDE_DIRS")
    assert module.LEGACY_SIDE_DIRS == LEGACY_SIDE_DIRS
