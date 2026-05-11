from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_r44e_probe_matrix_stays_targeted_to_region_and_mixed_families():
    import launch_r44e_probe

    assert sorted(launch_r44e_probe.PROBES) == [
        "r44e_mixed_prior_from_r44b_r40",
        "r44e_region_mix_repair_from_r44b_r42",
        "r44e_region_prior_from_r41",
    ]
    assert launch_r44e_probe.TARGET_STATIC_STAGES == (
        "stage_38_boundary_regions",
        "stage_40_boundary_mixed",
    )
    assert launch_r44e_probe.TARGET_MOTION_STAGES == (
        "stage_45_motion_regions",
        "stage_47_motion_mixed",
    )

    for probe in launch_r44e_probe.PROBES.values():
        overrides = probe["overrides"]
        assert overrides["TRAIN_INCLUDE_SUBDIRS"] == launch_r44e_probe.TARGET_STATIC_STAGES
        assert overrides["MOTION_INCLUDE_SUBDIRS"] == launch_r44e_probe.TARGET_MOTION_STAGES
        assert overrides["LR"] <= 2.0e-6
        assert overrides["MOTION_LOSS_WEIGHT"] <= 0.14


def test_r44e_probe_base_checkpoints_exist_and_cover_three_hypotheses():
    import launch_r44e_probe

    base_ids = {probe["base_id"] for probe in launch_r44e_probe.PROBES.values()}
    assert base_ids == {"r44b_from_r42", "r41_direct", "r44b_from_r40"}

    for base_id in base_ids:
        assert launch_r44e_probe.BASE_CHECKPOINTS[base_id].exists()
