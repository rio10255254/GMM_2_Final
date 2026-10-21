from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r42_launch_candidate_matrix_points_to_existing_starting_checkpoints():
    import launch_r42

    assert sorted(launch_r42.PROFILE_BY_CANDIDATE) == [
        "r42_boundary_from_combo",
        "r42_boundary_from_r41",
        "r42_boundary_guarded_kd_probe",
    ]
    assert launch_r42.BASE_CHECKPOINT_BY_CANDIDATE["r42_boundary_from_combo"].exists()
    assert launch_r42.BASE_CHECKPOINT_BY_CANDIDATE["r42_boundary_from_r41"].exists()
    assert launch_r42.BASE_CHECKPOINT_BY_CANDIDATE["r42_boundary_guarded_kd_probe"].exists()
    assert launch_r42.BASE_OVERRIDES["BOUNDARY_GEOM_ENABLE"] is True
    assert launch_r42.BASE_OVERRIDES["BOUNDARY_LOSS_WEIGHT"] > 0.0
    guarded = launch_r42.CANDIDATE_OVERRIDES["r42_boundary_guarded_kd_probe"]
    assert guarded["KD_ENABLE"] is True
    assert guarded["KD_WEIGHT_COMBO"] > guarded["KD_WEIGHT_R40"]
