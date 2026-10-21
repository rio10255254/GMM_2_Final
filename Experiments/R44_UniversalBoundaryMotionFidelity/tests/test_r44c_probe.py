from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r44c_probe_matrix_uses_r42_start_and_three_distinct_hypotheses():
    import launch_r44c_probe

    assert launch_r44c_probe.R42_BASE_CANDIDATE == "r44_motion_from_r42_best"
    assert launch_r44c_probe.BASE_CHECKPOINT_BY_CANDIDATE[launch_r44c_probe.R42_BASE_CANDIDATE].exists()
    assert sorted(launch_r44c_probe.PROBES) == [
        "r44c_family_holdout_motion",
        "r44c_low_motion_static_guard",
        "r44c_static_heavy_all_motion",
    ]

    low_motion = launch_r44c_probe.PROBES["r44c_low_motion_static_guard"]["overrides"]
    holdout = launch_r44c_probe.PROBES["r44c_family_holdout_motion"]["overrides"]
    static_heavy = launch_r44c_probe.PROBES["r44c_static_heavy_all_motion"]["overrides"]

    assert low_motion["MOTION_LOSS_WEIGHT"] < 0.20
    assert "stage_45_motion_regions" not in holdout["MOTION_INCLUDE_SUBDIRS"]
    assert "stage_47_motion_mixed" not in holdout["MOTION_INCLUDE_SUBDIRS"]
    assert static_heavy["BOUNDARY_LOSS_WEIGHT"] > low_motion["BOUNDARY_LOSS_WEIGHT"]
    assert static_heavy["MOTION_INCLUDE_SUBDIRS"] == launch_r44c_probe.MOTION_STAGES
