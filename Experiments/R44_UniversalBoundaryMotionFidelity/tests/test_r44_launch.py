from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r44_launch_candidate_matrix_is_research_first_and_motion_enabled():
    import launch_r44

    assert sorted(launch_r44.PROFILE_BY_CANDIDATE) == [
        "r44_motion_from_combo",
        "r44_motion_from_r40_a045",
        "r44_motion_from_r42_best",
    ]
    assert launch_r44.BASE_CHECKPOINT_BY_CANDIDATE["r44_motion_from_combo"].exists()
    assert launch_r44.BASE_CHECKPOINT_BY_CANDIDATE["r44_motion_from_r40_a045"].exists()
    assert launch_r44.BASE_CHECKPOINT_BY_CANDIDATE["r44_motion_from_r42_best"].exists()
    assert launch_r44.BASE_OVERRIDES["MOTION_ENABLE"] is True
    assert launch_r44.BASE_OVERRIDES["MOTION_LOSS_WEIGHT"] > 0.0
    assert launch_r44.BASE_OVERRIDES["SEQ_GEOM_ENABLE"] is False
