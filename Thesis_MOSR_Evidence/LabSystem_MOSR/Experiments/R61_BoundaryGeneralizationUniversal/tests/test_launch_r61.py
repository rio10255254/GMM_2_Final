from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r61.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r61", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_manifest_package(package: Path, *, include_all_roles: bool = True) -> None:
    roles = [
        "stage_34_r61_legacy_shape",
        "stage_35_r61_sequence_guard",
        "stage_36_r61_sem_truth_anchor",
        "stage_37_r61_universal_synthetic",
    ]
    if not include_all_roles:
        roles = ["stage_34_r61_legacy_shape", "stage_36_r61_sem_truth_anchor"]
    pairs = []
    for idx, role in enumerate(roles):
        src_rel = f"src/{role}/a_{idx}.bmp"
        lbl_rel = f"lbl/{role}/a_{idx}.bmp"
        (package / src_rel).parent.mkdir(parents=True, exist_ok=True)
        (package / lbl_rel).parent.mkdir(parents=True, exist_ok=True)
        (package / src_rel).write_bytes(b"src")
        (package / lbl_rel).write_bytes(b"lbl")
        (package / "geom" / "boundary" / role).mkdir(parents=True, exist_ok=True)
        (package / "geom" / "centerline" / role).mkdir(parents=True, exist_ok=True)
        (package / "geom" / "distance" / role).mkdir(parents=True, exist_ok=True)
        (package / "geom" / "boundary" / role / f"a_{idx}.bmp").write_bytes(b"boundary")
        (package / "geom" / "centerline" / role / f"a_{idx}.bmp").write_bytes(b"centerline")
        (package / "geom" / "distance" / role / f"a_{idx}.npy").write_bytes(b"distance")
        role_map = {
            "stage_34_r61_legacy_shape": "legacy_shape",
            "stage_35_r61_sequence_guard": "sequence_guard",
            "stage_36_r61_sem_truth_anchor": "sem_truth_anchor",
            "stage_37_r61_universal_synthetic": "universal_synthetic",
        }
        manifest_role = role_map[role]
        pairs.append(
            {
                "package_src": src_rel,
                "package_lbl": lbl_rel,
                "role": manifest_role,
                "source_group": manifest_role,
                "polarity": "bright" if idx % 2 == 0 else "dark",
                "feature": "circle",
                "geometry_boundary": f"geom/boundary/{role}/a_{idx}.bmp",
                "geometry_centerline": f"geom/centerline/{role}/a_{idx}.bmp",
                "geometry_distance": f"geom/distance/{role}/a_{idx}.npy",
            }
        )
    manifest = {
        "profile": package.name,
        "r61_universal_boundary_training": True,
        "anti_answer_leakage_design": True,
        "total_pairs": len(pairs),
        "role_counts": {
            "legacy_shape": 1,
            "sequence_guard": 1 if include_all_roles else 0,
            "sem_truth_anchor": 1,
            "universal_synthetic": 1 if include_all_roles else 0,
        },
        "polarity_counts": {"bright": 2, "dark": 2},
        "geometry_sidecars": True,
        "geometry_count": len(pairs),
        "pairs": pairs,
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_dry_run_reports_missing_r61_data_without_checkpoint_requirement(tmp_path: Path, capsys):
    module = load_module()

    rc = module.main(
        [
            "--candidate",
            "r61_universal_balanced",
            "--data-root",
            str(tmp_path / "missing"),
            "--scratch",
            "--dry-run",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert '"training_ready": false' in out
    assert '"r61_universal_boundary_training": true' in out
    assert '"anti_answer_leakage_required": true' in out
    assert '"scratch_training": true' in out


def test_ensure_data_package_requires_universal_and_guard_roles(tmp_path: Path):
    module = load_module()
    package = tmp_path / "r61_universal_boundary_train"
    _write_manifest_package(package, include_all_roles=False)

    try:
        module.ensure_data_package("r61_universal_boundary_train", tmp_path)
    except RuntimeError as exc:
        assert "missing required R61 roles" in str(exc)
    else:
        raise AssertionError("ensure_data_package accepted incomplete R61 role mix")


def test_hybrid_candidate_uses_hybrid_profile():
    module = load_module()

    assert module.PROFILE_BY_CANDIDATE["r61_polarity_hybrid_boundary_focus"] == "r61_universal_boundary_train_polarity_hybrid"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_hybrid_aligned_boundary_focus"] == "r61_universal_boundary_train_polarity_hybrid_aligned"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_adaptive_boundary_focus"] == "r61_universal_boundary_train_polarity_adaptive"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_identity_guard_boundary_focus"] == "r61_universal_boundary_train_polarity_identity_guard_v2"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_small_bias_dark_thin_boundary_focus"] == "r61_universal_boundary_train_polarity_small_bias_dark_thin_v3"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_small_bias_dark_thin_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_small_bias_dark_thin_v3"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_small_bias_guard_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_small_bias_guard_v4"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_small_bias_replay_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_small_bias_replay_v5"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_small_bias_replay_head_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_small_bias_replay_v5"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_small_bias_guard_head_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_small_bias_guard_v4"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_failure_balanced_replay_head_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_failure_balanced_replay_v6"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_failure_balanced_shape_neutral_head_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_bright_curve_replay_head_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_bright_curve_replay_v8"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_identityguard_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    assert module.PROFILE_BY_CANDIDATE["r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_identityposguard_region_kd_boundary_focus"] == "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"


def test_configure_trainer_uses_all_r61_roles_and_disables_posthoc_correction(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_universal_balanced",
            "--base-checkpoint",
            str(base_checkpoint),
            "--num-epoch",
            "5",
            "--batch-size",
            "3",
            "--val-batch-size",
            "2",
            "--num-workers",
            "0",
            "--run-suffix",
            "test",
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train"
    split_dir = data_dir / "splits" / "grouped_seed1337_val100"
    module.configure_trainer(Trainer, args, data_dir, fixed_split_dir=split_dir)

    assert Trainer.CFG.LOAD_MODEL is True
    assert Trainer.CFG.RESUME_CHECKPOINT == str(lab_checkpoint)
    assert Trainer.CFG.MODEL_NAME == "LAB_GESR_v1_v5_ST0p8_SWP_r61_universal_balanced_test"
    assert Trainer.CFG.R61_UNIVERSAL_BOUNDARY is True
    assert Trainer.CFG.R61_ANTI_ANSWER_LEAKAGE_REQUIRED is True
    assert Trainer.CFG.PHYS_FORWARD_ENABLE is False
    assert Trainer.CFG.W_PHYS_MAX == 0.0
    assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == (
        "stage_34_r61_legacy_shape",
        "stage_35_r61_sequence_guard",
        "stage_36_r61_sem_truth_anchor",
        "stage_37_r61_universal_synthetic",
    )
    assert not hasattr(Trainer.CFG, "R59_POSTHOC_CALIBRATION")
    assert Trainer.TRAIN_SRC_DIR == str(data_dir / "src")
    assert Trainer.TRAIN_LBL_DIR == str(data_dir / "lbl")
    assert Trainer.TRAIN_GEOM_DIR == str(data_dir / "geom")


def test_configure_trainer_forwards_raw_anchor_output_settings(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    candidate = "raw_anchor_probe_candidate"
    module.CANDIDATE_SETTINGS[candidate] = dict(module.CANDIDATE_SETTINGS["r61_universal_balanced"])
    module.CANDIDATE_SETTINGS[candidate].update(
        {
            "raw_anchor_output_mode": "detail",
            "raw_anchor_output_alpha": 0.17,
            "raw_anchor_output_sigma": 3.5,
            "raw_anchor_output_detail_gain": 0.42,
        }
    )
    module.PROFILE_BY_CANDIDATE[candidate] = module.PROFILE_BY_CANDIDATE["r61_universal_balanced"]

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

        @staticmethod
        def _set_training_progress_root(path: str) -> None:
            Trainer.TRAINING_PROGRESS_ROOT_SET = path

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            candidate,
            "--base-checkpoint",
            str(base_checkpoint),
            "--num-epoch",
            "1",
            "--batch-size",
            "1",
            "--val-batch-size",
            "1",
            "--num-workers",
            "0",
        ]
    )

    module.configure_trainer(Trainer, args, tmp_path / "r61_universal_boundary_train")

    assert Trainer.CFG.RAW_ANCHOR_OUTPUT_MODE == "detail"
    assert Trainer.CFG.RAW_ANCHOR_OUTPUT_ALPHA == 0.17
    assert Trainer.CFG.RAW_ANCHOR_OUTPUT_SIGMA == 3.5
    assert Trainer.CFG.RAW_ANCHOR_OUTPUT_DETAIL_GAIN == 0.42


def test_main_can_skip_external_fixed_split_for_filtered_training_package(tmp_path: Path, monkeypatch, capsys):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)
    package = tmp_path / "r61_universal_boundary_train"
    _write_manifest_package(package)

    candidate = "internal_split_candidate"
    module.CANDIDATE_SETTINGS[candidate] = dict(module.CANDIDATE_SETTINGS["r61_universal_balanced"])
    module.CANDIDATE_SETTINGS[candidate]["disable_external_fixed_split"] = True
    module.PROFILE_BY_CANDIDATE[candidate] = "r61_universal_boundary_train"
    module.REQUIRED_ROLES_BY_CANDIDATE[candidate] = tuple(sorted(module.REQUIRED_R61_ROLES))

    def fail_prepare_grouped_fixed_split(**_kwargs):
        raise AssertionError("external grouped split should be skipped")

    monkeypatch.setattr(module, "prepare_grouped_fixed_split", fail_prepare_grouped_fixed_split)

    trainer = types.SimpleNamespace(CFG=type("CFG", (), {})())
    trainer._set_training_progress_root = lambda _path: None
    trainer.main = lambda: None
    monkeypatch.setitem(sys.modules, "GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest", trainer)

    rc = module.main(
        [
            "--candidate",
            candidate,
            "--data-root",
            str(tmp_path),
            "--scratch",
            "--dry-run",
        ]
    )

    assert rc == 0
    assert trainer.CFG.FIXED_SPLIT_DIR == ""
    out = capsys.readouterr().out
    assert '"fixed_split_dir": ""' in out
    assert '"fixed_split_train_count": 0' in out


def test_motion_guard_candidate_enables_sequence_validation_as_best_model_signal(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_guard_dualgate_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    module.configure_trainer(Trainer, args, data_dir)

    assert module.PROFILE_BY_CANDIDATE["r61_motion_guard_dualgate_boundary_focus"] == data_dir.name
    assert Trainer.CFG.TRAIN_INCLUDE_SUBDIRS == module.R61_INCLUDE_SUBDIRS
    assert Trainer.CFG.SEQ_ENABLE is True
    assert Trainer.CFG.SEQ_GEOM_ENABLE is True
    assert Trainer.CFG.SEQ_VAL_ENABLE is True
    assert Trainer.CFG.SEQ_VAL_INCLUDE_SUBDIRS == ("stage_35_r61_sequence_guard",)
    assert Trainer.CFG.SEQ_VAL_MAX_PAIRS >= 120
    assert Trainer.CFG.GMF_VALIDATE_SOURCE == "seq_val"
    assert Trainer.CFG.GMF_VALIDATE_EVERY_N == 1
    assert Trainer.CFG.BEST_EPOCH_MIN == 1
    assert Trainer.CFG.GMF_OBJ_J > 0.0
    assert Trainer.CFG.GMF_OBJ_K > 0.0
    assert Trainer.CFG.GMF_OBJ_L > 0.0
    assert Trainer.CFG.GMF_OBJ_O > 0.0
    assert Trainer.CFG.GMF_OBJ_Q > 0.0
    assert Trainer.CFG.GMF_OBJ_R > 0.0
    assert Trainer.CFG.TRAIN_GROUP_BALANCED_SAMPLER is True


def test_motion_guard_candidate_defaults_to_r39_a970_base_checkpoint():
    module = load_module()
    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_guard_dualgate_boundary_focus",
        ]
    )

    checkpoint = module._resolve_base_checkpoint(args)

    assert checkpoint == module.R39_A970_BASE_CHECKPOINT
    assert checkpoint.name == "r39_best_latest_a970.pth.tar"


def test_motion_synthetic_candidate_enables_motion_loader_and_requires_motion_role(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_synthetic_dualgate_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_motion_guard_v11"
    module.configure_trainer(Trainer, args, data_dir)

    assert module.PROFILE_BY_CANDIDATE["r61_motion_synthetic_dualgate_boundary_focus"] == data_dir.name
    assert "motion_synthetic" in module.REQUIRED_ROLES_BY_CANDIDATE["r61_motion_synthetic_dualgate_boundary_focus"]
    assert "stage_38_r61_motion_synthetic" in Trainer.CFG.TRAIN_INCLUDE_SUBDIRS
    assert Trainer.CFG.MOTION_ENABLE is True
    assert Trainer.CFG.MOTION_SRC_DIR == str(data_dir / "src")
    assert Trainer.CFG.MOTION_LBL_DIR == str(data_dir / "lbl")
    assert Trainer.CFG.MOTION_GEOM_DIR == str(data_dir / "geom")
    assert Trainer.CFG.MOTION_INCLUDE_SUBDIRS == ("stage_38_r61_motion_synthetic",)
    assert Trainer.CFG.MOTION_LOSS_WEIGHT > 0.0
    assert Trainer.CFG.MOTION_RECON_WEIGHT > 0.0
    assert Trainer.CFG.MOTION_BOUNDARY_WEIGHT > 1.0
    assert Trainer.CFG.SEQ_VAL_ENABLE is True
    assert Trainer.CFG.GMF_VALIDATE_SOURCE == "seq_val"


def test_motion_gradient_candidate_enables_gradient_motion_and_teacher_guard(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_gradient_dualgate_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_motion_guard_v11"
    module.configure_trainer(Trainer, args, data_dir)

    assert module.PROFILE_BY_CANDIDATE["r61_motion_gradient_dualgate_boundary_focus"] == data_dir.name
    assert "motion_synthetic" in module.REQUIRED_ROLES_BY_CANDIDATE["r61_motion_gradient_dualgate_boundary_focus"]
    assert Trainer.CFG.MOTION_ENABLE is True
    assert Trainer.CFG.MOTION_GRAD_WEIGHT > 0.0
    assert Trainer.CFG.MOTION_RECON_WEIGHT > 0.0
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_TEACHER_PATH == str(lab_checkpoint)
    assert Trainer.CFG.GMF_VALIDATE_SOURCE == "seq_val"


def test_motion_gradient_v11base_candidate_is_single_variable_probe(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_gradient_v11base_dualgate_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_motion_guard_v11"
    module.configure_trainer(Trainer, args, data_dir)

    settings = module.CANDIDATE_SETTINGS["r61_motion_gradient_v11base_dualgate_boundary_focus"]
    v11_settings = module.CANDIDATE_SETTINGS["r61_motion_synthetic_dualgate_boundary_focus"]
    assert module.PROFILE_BY_CANDIDATE["r61_motion_gradient_v11base_dualgate_boundary_focus"] == data_dir.name
    assert settings["lr"] == v11_settings["lr"]
    assert settings["motion_loss_weight"] == v11_settings["motion_loss_weight"]
    assert settings["motion_recon_weight"] == v11_settings["motion_recon_weight"]
    assert Trainer.CFG.MOTION_ENABLE is True
    assert Trainer.CFG.MOTION_GRAD_WEIGHT == 0.25
    assert Trainer.CFG.MOTION_INCLUDE_SUBDIRS == ("stage_38_r61_motion_synthetic",)
    assert Trainer.CFG.REGION_KD_WEIGHT == v11_settings["region_kd_weight"]
    assert Trainer.CFG.GMF_VALIDATE_SOURCE == "seq_val"


def test_motion_texture_candidate_uses_real_like_motion_role_with_old_data(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_texture_v11base_dualgate_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_motion_texture_guard_v14"
    module.configure_trainer(Trainer, args, data_dir)

    assert module.PROFILE_BY_CANDIDATE["r61_motion_texture_v11base_dualgate_boundary_focus"] == data_dir.name
    required = set(module.REQUIRED_ROLES_BY_CANDIDATE["r61_motion_texture_v11base_dualgate_boundary_focus"])
    assert {"motion_synthetic", "motion_texture_synthetic"}.issubset(required)
    assert "stage_38_r61_motion_synthetic" in Trainer.CFG.TRAIN_INCLUDE_SUBDIRS
    assert "stage_39_r61_motion_texture_synthetic" in Trainer.CFG.TRAIN_INCLUDE_SUBDIRS
    assert Trainer.CFG.MOTION_INCLUDE_SUBDIRS == (
        "stage_38_r61_motion_synthetic",
        "stage_39_r61_motion_texture_synthetic",
    )
    assert Trainer.CFG.MOTION_GRAD_WEIGHT == 0.25
    assert Trainer.CFG.MOTION_MAX_PAIRS >= 960
    assert Trainer.CFG.GMF_VALIDATE_SOURCE == "seq_val"


def test_motion_texture_stepguard_v16_candidate_adds_step_guard_without_dropping_old_motion_data(
    tmp_path: Path, monkeypatch
):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "v14_best.pth.tar"
    teacher_checkpoint = tmp_path / "r39_teacher.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    teacher_checkpoint.write_bytes(b"fake")

    lab_base = tmp_path / "lab_base.pth.tar"
    lab_teacher = tmp_path / "lab_teacher.pth.tar"
    lab_base.write_bytes(b"fake")
    lab_teacher.write_bytes(b"fake")

    def fake_prepare_lab_checkpoint(path: Path) -> Path:
        if Path(path) == base_checkpoint:
            return lab_base
        if Path(path) == teacher_checkpoint:
            return lab_teacher
        raise AssertionError(f"unexpected checkpoint prepared: {path}")

    monkeypatch.setattr(module, "prepare_lab_checkpoint", fake_prepare_lab_checkpoint)
    settings = dict(module.CANDIDATE_SETTINGS["r61_motion_texture_stepguard_v16_dualgate_boundary_focus"])
    settings["region_kd_teacher_checkpoint"] = teacher_checkpoint
    monkeypatch.setitem(
        module.CANDIDATE_SETTINGS,
        "r61_motion_texture_stepguard_v16_dualgate_boundary_focus",
        settings,
    )

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_texture_stepguard_v16_dualgate_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_motion_texture_step_guard_v16"
    module.configure_trainer(Trainer, args, data_dir)

    assert module.PROFILE_BY_CANDIDATE["r61_motion_texture_stepguard_v16_dualgate_boundary_focus"] == data_dir.name
    required = set(module.REQUIRED_ROLES_BY_CANDIDATE["r61_motion_texture_stepguard_v16_dualgate_boundary_focus"])
    assert {"motion_synthetic", "motion_texture_synthetic", "step_guard_motion_texture_synthetic"}.issubset(required)
    assert "stage_38_r61_motion_synthetic" in Trainer.CFG.TRAIN_INCLUDE_SUBDIRS
    assert "stage_39_r61_motion_texture_synthetic" in Trainer.CFG.TRAIN_INCLUDE_SUBDIRS
    assert "stage_40_r61_step_guard_motion_texture_synthetic" in Trainer.CFG.TRAIN_INCLUDE_SUBDIRS
    assert Trainer.CFG.MOTION_INCLUDE_SUBDIRS == (
        "stage_38_r61_motion_synthetic",
        "stage_39_r61_motion_texture_synthetic",
        "stage_40_r61_step_guard_motion_texture_synthetic",
    )
    assert Trainer.CFG.RESUME_CHECKPOINT == str(lab_base)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_TEACHER_PATH == str(lab_teacher)
    assert Trainer.CFG.MOTION_GRAD_WEIGHT > 0.0
    assert Trainer.CFG.MOTION_MAX_PAIRS >= 1600
    assert Trainer.CFG.GMF_VALIDATE_SOURCE == "seq_val"


def test_motion_texture_stepguard_v16_defaults_to_v14_best_checkpoint():
    module = load_module()
    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_motion_texture_stepguard_v16_dualgate_boundary_focus",
        ]
    )

    checkpoint = module._resolve_base_checkpoint(args)

    assert checkpoint == module.V14_MOTION_TEXTURE_BASE_CHECKPOINT
    assert checkpoint.name == "best_tradeoff.pth.tar"


def test_region_kd_candidate_preserves_base_boundary_teacher(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_small_bias_dark_thin_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_small_bias_dark_thin_v3"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.KD_ENABLE is False
    assert Trainer.CFG.KD_WEIGHT_COMBO == 0.0
    assert Trainer.CFG.KD_WEIGHT_R40 == 0.0
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_TEACHER_PATH == str(lab_checkpoint)
    assert Trainer.CFG.REGION_KD_WEIGHT == 0.25
    assert Trainer.CFG.REGION_KD_BAND_PX == 8.0


def test_small_bias_guard_region_kd_candidate_uses_stronger_teacher_preserve(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_small_bias_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_small_bias_guard_v4"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 2.0e-8
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.08
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_TEACHER_PATH == str(lab_checkpoint)
    assert Trainer.CFG.REGION_KD_WEIGHT == 1.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 8.0


def test_small_bias_replay_region_kd_candidate_uses_conservative_replay_update(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_small_bias_replay_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_small_bias_replay_v5"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.0e-8
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.06
    assert Trainer.CFG.CENTERLINE_LOSS_WEIGHT == 0.035
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT == 0.035
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_TEACHER_PATH == str(lab_checkpoint)
    assert Trainer.CFG.REGION_KD_WEIGHT == 2.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_small_bias_replay_head_region_kd_candidate_trains_only_tail_layers(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_small_bias_replay_head_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_small_bias_replay_v5"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 2.0e-7
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("p1", "out")
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 3.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_small_bias_guard_head_region_kd_candidate_is_short_tail_repair(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_small_bias_guard_head_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_small_bias_guard_v4"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 5.0e-8
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("p1", "out")
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.04
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 4.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_failure_balanced_replay_head_region_kd_candidate_targets_guarded_tail_update(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_failure_balanced_replay_head_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_failure_balanced_replay_v6"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.5e-7
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("p1", "out")
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.045
    assert Trainer.CFG.CENTERLINE_LOSS_WEIGHT == 0.028
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT == 0.028
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 4.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_failure_balanced_shape_neutral_head_region_kd_candidate_uses_smaller_tail_update(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_failure_balanced_shape_neutral_head_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.0e-7
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("p1", "out")
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.040
    assert Trainer.CFG.CENTERLINE_LOSS_WEIGHT == 0.024
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT == 0.024
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 4.5
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_bright_curve_replay_head_region_kd_candidate_uses_tiny_tail_repair(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_bright_curve_replay_head_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_bright_curve_replay_v8"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 4.0e-8
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("p1", "out")
    assert Trainer.CFG.BOUNDARY_LOSS_WEIGHT == 0.030
    assert Trainer.CFG.CENTERLINE_LOSS_WEIGHT == 0.020
    assert Trainer.CFG.DISTANCE_EDGE_LOSS_WEIGHT == 0.020
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 5.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_boundary_adapter_shape_neutral_candidate_trains_only_zero_init_adapter(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_shape_neutral_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 2.0e-4
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_HIDDEN == 16
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX == 0.025
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 8.0
    assert Trainer.CFG.REGION_KD_BAND_PX == 10.0


def test_edge_limited_boundary_adapter_candidate_prevents_global_adapter_shift(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_edgezero_shape_neutral_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 3.0e-4
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_DELTA_BIAS is False
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ZERO_MEAN is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_EDGE_GATE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX == 0.035
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 8.0


def test_failure_balanced_boundary_adapter_candidate_targets_curve_failures(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_failure_balanced_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_failure_balanced_replay_v6"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.0e-4
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_DELTA_BIAS is True
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 3.0


def test_position_boundary_adapter_candidate_enables_direct_boundary_position_loss(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_position_shape_neutral_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 5.0e-5
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 3.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.015
    assert Trainer.CFG.BOUNDARY_POSITION_COVERAGE_WEIGHT == 0.20
    assert Trainer.CFG.BOUNDARY_POSITION_DISTANCE_CLIP == 8.0


def test_position_bright_guard_candidate_uses_lower_position_loss_with_v8_replay(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_position_bright_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_bright_curve_replay_v8"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.5e-5
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 5.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.006
    assert Trainer.CFG.BOUNDARY_POSITION_COVERAGE_WEIGHT == 0.15


def test_position_bright_ellipse_guard_candidate_uses_v9_guard_replay(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_position_bright_ellipse_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_bright_ellipse_guard_v9"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 8.0e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_ENABLE is True
    assert Trainer.CFG.REGION_KD_WEIGHT == 6.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.004
    assert Trainer.CFG.BOUNDARY_POSITION_COVERAGE_WEIGHT == 0.12


def test_polarity_split_adapter_candidate_enables_split_delta_modes(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_polarity_split_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_bright_curve_replay_v8"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 6.0e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT is True
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_WEIGHT == 6.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.003


def test_polarity_split_preserve_candidate_keeps_r31_scale_and_uses_gentle_update(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_polarity_split_preserve_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_bright_curve_replay_v8"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 4.0e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX == 0.025
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_WEIGHT == 8.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.002


def test_rotated_rect_guard_candidate_uses_v10_rect_replay_and_conservative_adapter_update(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_position_rotated_rect_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 3.0e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT is False
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX == 0.025
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_WEIGHT == 10.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.0015


def test_orientation_adapter_candidate_enables_direction_inputs_for_rect_repair(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_orientation_rotated_rect_guard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 2.0e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX == 0.025
    assert Trainer.CFG.TRAINABLE_NAME_PATTERNS == ("boundary_adapter",)
    assert Trainer.CFG.REGION_KD_WEIGHT == 12.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.001


def test_groupbalanced_orientation_candidate_reuses_v10_with_manifest_group_sampler(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.5e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE is True
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS is True
    assert Trainer.CFG.TRAIN_GROUP_BALANCED_SAMPLER is True
    assert Trainer.CFG.TRAIN_GROUP_BALANCE_MANIFEST == str(data_dir / "manifest.json")
    assert Trainer.CFG.TRAIN_GROUP_BALANCE_KEYS == ("role", "polarity", "shape_family", "bias_px")
    assert Trainer.CFG.TRAIN_GROUP_BALANCE_NUM_SAMPLES_MULT == 1.0
    assert Trainer.CFG.REGION_KD_WEIGHT == 12.0
    assert Trainer.CFG.BOUNDARY_POSITION_LOSS_WEIGHT == 0.0008


def test_groupbalanced_identityguard_candidate_protects_small_bias_cases(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_identityguard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.2e-6
    assert Trainer.CFG.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS is True
    assert Trainer.CFG.TRAIN_GROUP_BALANCED_SAMPLER is True
    assert Trainer.CFG.IDENTITY_GUARD_ENABLE is True
    assert Trainer.CFG.IDENTITY_GUARD_KD_WEIGHT == 30.0
    assert Trainer.CFG.IDENTITY_GUARD_BIAS_MAX == 0.5
    assert Trainer.CFG.IDENTITY_GUARD_BAND_PX == 10.0
    assert Trainer.CFG.TRAIN_GROUP_BALANCE_MANIFEST == str(data_dir / "manifest.json")


def test_groupbalanced_identityposguard_candidate_adds_small_bias_position_guard(tmp_path: Path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "_require_assets", lambda: None)

    base_checkpoint = tmp_path / "base.pth.tar"
    base_checkpoint.write_bytes(b"fake")
    lab_checkpoint = tmp_path / "lab_ready.pth.tar"
    lab_checkpoint.write_bytes(b"fake")
    monkeypatch.setattr(module, "prepare_lab_checkpoint", lambda path: lab_checkpoint)

    cfg = type("CFG", (), {})()

    class Trainer:
        CFG = cfg

    args = module.build_arg_parser().parse_args(
        [
            "--candidate",
            "r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_identityposguard_region_kd_boundary_focus",
            "--base-checkpoint",
            str(base_checkpoint),
        ]
    )

    data_dir = tmp_path / "r61_universal_boundary_train_polarity_rotated_rect_guard_v10"
    module.configure_trainer(Trainer, args, data_dir)

    assert Trainer.CFG.LR == 1.0e-6
    assert Trainer.CFG.TRAIN_GROUP_BALANCED_SAMPLER is True
    assert Trainer.CFG.IDENTITY_GUARD_ENABLE is True
    assert Trainer.CFG.IDENTITY_GUARD_KD_WEIGHT == 30.0
    assert Trainer.CFG.IDENTITY_GUARD_POSITION_WEIGHT == 0.012
    assert Trainer.CFG.IDENTITY_GUARD_BIAS_MAX == 0.5
