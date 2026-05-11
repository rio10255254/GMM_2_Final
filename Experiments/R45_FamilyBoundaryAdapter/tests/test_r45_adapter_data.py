import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from r45_adapter_data import (  # noqa: E402
    R45_TARGET_STAGES,
    iter_target_motion_frames,
    stage_from_package_path,
)


def test_stage_from_package_path_extracts_stage():
    assert stage_from_package_path("src/stage_45_motion_regions/0080_seq0080_f00.bmp") == "stage_45_motion_regions"
    assert stage_from_package_path("lbl/stage_47_motion_mixed/0080_seq0080_f00.bmp") == "stage_47_motion_mixed"


def test_target_stages_are_only_large_and_mixed():
    assert R45_TARGET_STAGES == ("stage_45_motion_regions", "stage_47_motion_mixed")


def test_iter_target_motion_frames_reads_expected_manifest():
    data_root = REPO_ROOT / "Training_Data" / "r44_universal_boundary_motion"
    rows = list(iter_target_motion_frames(data_root / "motion_val_unseen" / "manifest.json"))
    assert rows
    assert {row["stage"] for row in rows} == set(R45_TARGET_STAGES)
    assert {row["feature_family"] for row in rows} == {"large_regions", "mixed_fields"}
