from __future__ import annotations

import json
import sys
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = EXPERIMENT_DIR / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import launch_v41_standalone as v41  # noqa: E402


def test_standalone_has_one_clean_candidate() -> None:
    assert v41.STANDALONE_CANDIDATE == "v41_standalone_long"
    assert set(v41.PROFILE_BY_CANDIDATE) == {v41.STANDALONE_CANDIDATE}

    settings = v41.STANDALONE_SETTINGS
    assert settings["profile"] == v41.STANDALONE_PROFILE
    assert "r62_target_selfshift" not in v41.STANDALONE_CANDIDATE

    base_checkpoint = str(settings["base_checkpoint"]).lower()
    assert "v20" not in base_checkpoint
    assert "v35" not in base_checkpoint
    assert "v41" not in base_checkpoint


def test_standalone_uses_complete_final_training_package() -> None:
    include = set(v41.STANDALONE_INCLUDE_SUBDIRS)
    for stage in [
        "stage_36_r61_sem_truth_anchor",
        "stage_38_r61_motion_synthetic",
        "stage_40_r61_step_guard_motion_texture_synthetic",
        "stage_40_r62_target_real_pseudo",
        "stage_40_r62_real_motion_pair",
        "stage_40_r62_gmf_roi_selfshift_motion_pair",
        "stage_40_r62_multimag_raw_motion_guard_pair",
        "stage_40_r62_stability_shape_teacher_pair",
    ]:
        assert stage in include

    required = set(v41.STANDALONE_REQUIRED_ROLES)
    for role in [
        "sem_truth_anchor",
        "motion_synthetic",
        "target_real_motion_pair",
        "target_real_multimag_raw_motion_guard_pair",
        "target_real_stability_shape_teacher_pair",
    ]:
        assert role in required


def test_manifest_supports_required_roles() -> None:
    manifest = v41.load_manifest()
    assert int(manifest["total_pairs"]) >= 10000
    role_counts = manifest.get("role_counts", {})
    missing = sorted(set(v41.STANDALONE_REQUIRED_ROLES) - set(role_counts))
    assert missing == []
    assert role_counts["target_real_stability_shape_teacher_pair"] >= 800


def test_default_args_are_full_length_training() -> None:
    parser = v41.build_arg_parser()
    args = parser.parse_args([])
    assert args.candidate == v41.STANDALONE_CANDIDATE
    assert args.num_epoch >= 12
    assert args.batch_size == 4
    assert args.val_batch_size == 2
    assert args.num_workers == 2
    assert args.max_train_batches is None
    assert not args.scratch


def test_dry_run_summary_is_thesis_clean_json() -> None:
    summary = v41.build_standalone_summary()
    json.dumps(summary)
    assert summary["candidate"] == v41.STANDALONE_CANDIDATE
    assert summary["profile"] == v41.STANDALONE_PROFILE
    assert summary["training_story"] == "standalone_full_final_training"
    assert summary["uses_version_chain_checkpoint"] is False
