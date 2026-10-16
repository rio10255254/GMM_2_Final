from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "launch_r62.py"


def load_module():
    spec = importlib.util.spec_from_file_location("launch_r62", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_v4_candidate_uses_selfshift_profile_and_clean_motion_stage():
    module = load_module()
    module.patch_r61_registry()
    settings = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V4]

    assert settings["profile"] == module.SELFSHIFT_PROFILE
    assert module.SELF_SHIFT_STAGE in settings["motion_include_subdirs"]
    assert module.REAL_MOTION_STAGE not in settings["motion_include_subdirs"]
    assert module.SELF_SHIFT_STAGE in settings["train_include_subdirs"]
    assert module.REAL_MOTION_STAGE in settings["train_include_subdirs"]
    assert "target_real_selfshift_motion_pair" in settings["required_roles"]
    assert settings["region_kd_weight"] >= 4.0
    assert settings["motion_loss_weight"] > settings["motion_recon_weight"]


def test_v5_candidate_is_adapter_only_motion_guarded():
    module = load_module()
    module.patch_r61_registry()
    settings = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V5]

    assert settings["profile"] == module.SELFSHIFT_PROFILE
    assert settings["trainable_name_patterns"] == ("boundary_adapter",)
    assert module.SELF_SHIFT_STAGE in settings["motion_include_subdirs"]
    assert module.REAL_MOTION_STAGE not in settings["motion_include_subdirs"]
    assert settings["motion_loss_weight"] > module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V4]["motion_loss_weight"]
    assert settings["motion_recon_weight"] == 0.0
    assert settings["region_kd_weight"] > module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V4]["region_kd_weight"]


def test_v6_candidate_routes_existing_sequence_geometry_to_selfshift_data():
    module = load_module()
    module.patch_r61_registry()
    settings = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V6]

    assert settings["profile"] == module.SELFSHIFT_PROFILE
    assert settings["seq_use_train_dirs"] is True
    assert settings["seq_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert settings["seq_loss_weight"] > module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V4]["seq_loss_weight"]
    assert settings["seq_grad_weight"] > 0.0
    assert settings["seq_geom_center_weight"] > 0.0
    assert settings["seq_step_mag_weight"] > 0.0
    assert settings["seq_abs_center_weight"] > 0.0
    assert settings["seq_single_abs_center_weight"] > 0.0
    assert module.REAL_MOTION_STAGE not in settings["motion_include_subdirs"]
    assert module.SELF_SHIFT_STAGE in settings["motion_include_subdirs"]


def test_v7_candidate_keeps_v6_sequence_route_but_increases_main_update_mobility():
    module = load_module()
    module.patch_r61_registry()
    v6 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V6]
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]

    assert v7["profile"] == module.SELFSHIFT_PROFILE
    assert v7["seq_use_train_dirs"] is True
    assert v7["seq_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert v7["motion_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert v7["lr"] > v6["lr"]
    assert v7["boundary"] < v6["boundary"]
    assert set(v7["trainable_name_patterns"]) == {"boundary_adapter", "p1", "p2", "out"}
    assert v7["motion_recon_weight"] == 0.0
    assert v7["use_amp"] is False


def test_v8_candidate_targets_gmf_localization_by_preserving_raw_motion_features():
    module = load_module()
    module.patch_r61_registry()
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]
    v8 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V8]

    assert v8["profile"] == module.SELFSHIFT_PROFILE
    assert v8["seq_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert v8["motion_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert set(v8["trainable_name_patterns"]) == {"boundary_adapter", "p1", "p2", "out"}
    assert 0.0 < v8["motion_recon_weight"] < v8["motion_loss_weight"]
    assert v8["motion_loss_weight"] > v7["motion_loss_weight"]
    assert v8["region_kd_weight"] < v7["region_kd_weight"]
    assert v8["identity_guard_position_weight"] >= v7["identity_guard_position_weight"]
    assert v8["use_amp"] is False


def test_v9_candidate_is_pairwise_gmf_selection_guarded_without_v8_overpush():
    module = load_module()
    module.patch_r61_registry()
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]
    v8 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V8]
    v9 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V9]

    assert v9["profile"] == module.SELFSHIFT_PROFILE
    assert v9["external_selection_gate"] == "pairwise_gmf_thesis_guard"
    assert v9["seq_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert v9["motion_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert set(v9["trainable_name_patterns"]) == {"boundary_adapter", "p1", "p2", "out"}
    assert v7["motion_loss_weight"] < v9["motion_loss_weight"] < v8["motion_loss_weight"]
    assert v9["region_kd_weight"] >= v7["region_kd_weight"]
    assert v9["identity_guard_kd_weight"] >= v7["identity_guard_kd_weight"]
    assert v9["motion_recon_weight"] <= v8["motion_recon_weight"]
    assert v9["use_amp"] is False


def test_v10_candidate_keeps_v7_route_but_uses_stable_core_micro_updates():
    module = load_module()
    module.patch_r61_registry()
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]
    v9 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V9]
    v10 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V10]

    assert v10["profile"] == module.SELFSHIFT_PROFILE
    assert v10["external_selection_gate"] == "pairwise_gmf_stable_core_guard"
    assert v10["seq_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert v10["motion_include_subdirs"] == (module.SELF_SHIFT_STAGE,)
    assert set(v10["trainable_name_patterns"]) == {"boundary_adapter", "p1", "p2", "out"}
    assert v10["lr"] < v7["lr"]
    assert v10["motion_loss_weight"] < v7["motion_loss_weight"]
    assert v10["motion_loss_weight"] < v9["motion_loss_weight"]
    assert v10["region_kd_weight"] > v7["region_kd_weight"]
    assert v10["identity_guard_kd_weight"] > v9["identity_guard_kd_weight"]
    assert v10["boundary_residual_adapter_max"] < v7["boundary_residual_adapter_max"]
    assert v10["motion_recon_weight"] == 0.0
    assert v10["use_amp"] is False


def test_v11_candidate_keeps_v7_strategy_but_uses_motion_clean_package():
    module = load_module()
    module.patch_r61_registry()
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]
    v11 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V11]

    assert v11["profile"] == module.CLEAN_MOTION_PROFILE
    assert v11["external_selection_gate"] == "pairwise_gmf_motion_clean_guard"
    assert v11["seq_include_subdirs"] == v7["seq_include_subdirs"]
    assert v11["motion_include_subdirs"] == v7["motion_include_subdirs"]
    assert v11["train_include_subdirs"] == v7["train_include_subdirs"]
    assert v11["required_roles"] == v7["required_roles"]
    assert v11["motion_loss_weight"] == v7["motion_loss_weight"]
    assert v11["region_kd_weight"] == v7["region_kd_weight"]
    assert v11["identity_guard_kd_weight"] == v7["identity_guard_kd_weight"]
    assert v11["use_amp"] is False


def test_v12_candidate_adds_direct_motion_center_loss_on_clean_package():
    module = load_module()
    module.patch_r61_registry()
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]
    v12 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V12]

    assert v12["profile"] == module.CLEAN_MOTION_PROFILE
    assert v12["external_selection_gate"] == "pairwise_gmf_motion_center_guard"
    assert v12["seq_include_subdirs"] == v7["seq_include_subdirs"]
    assert v12["motion_include_subdirs"] == v7["motion_include_subdirs"]
    assert v12["train_include_subdirs"] == v7["train_include_subdirs"]
    assert v12["required_roles"] == v7["required_roles"]
    assert v12["motion_center_weight"] > 0.0
    assert v12["motion_center_weight"] < v12["motion_loss_weight"]
    assert v12["motion_recon_weight"] == 0.0
    assert v12["use_amp"] is False


def test_v13_candidate_targets_local_gmf_like_motion_centers():
    module = load_module()
    module.patch_r61_registry()
    v12 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V12]
    v13 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V13]

    assert v13["profile"] == module.CLEAN_MOTION_PROFILE
    assert v13["external_selection_gate"] == "pairwise_gmf_local_motion_center_guard"
    assert v13["motion_local_center_weight"] > 0.0
    assert v13["motion_local_center_grid"] >= 2
    assert v13["motion_center_weight"] <= v12["motion_center_weight"]
    assert v13["motion_recon_weight"] == 0.0
    assert v13["use_amp"] is False


def test_v14_candidate_adds_lowfrequency_motion_position_guard():
    module = load_module()
    module.patch_r61_registry()
    v7 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V7]
    v14 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V14]

    assert v14["profile"] == module.CLEAN_MOTION_PROFILE
    assert v14["external_selection_gate"] == "seeded_gmf_lowfreq_motion_guard"
    assert v14["seq_include_subdirs"] == v7["seq_include_subdirs"]
    assert v14["motion_include_subdirs"] == v7["motion_include_subdirs"]
    assert v14["motion_input_lowfreq_weight"] > 0.0
    assert v14["motion_input_lowfreq_sigma"] >= 1.0
    assert v14["motion_loss_weight"] <= v7["motion_loss_weight"]
    assert v14["motion_recon_weight"] == 0.0
    assert v14["use_amp"] is False


def test_v15_candidate_applies_lowfrequency_position_guard_to_main_training_images():
    module = load_module()
    module.patch_r61_registry()
    v14 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V14]
    v15 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V15]

    assert v15["profile"] == module.CLEAN_MOTION_PROFILE
    assert v15["external_selection_gate"] == "seeded_gmf_main_lowfreq_guard"
    assert v15["input_lowfreq_weight"] > 0.0
    assert v15["input_lowfreq_sigma"] == v14["motion_input_lowfreq_sigma"]
    assert v15["motion_input_lowfreq_weight"] >= v14["motion_input_lowfreq_weight"]
    assert v15["motion_loss_weight"] <= v14["motion_loss_weight"]
    assert v15["motion_recon_weight"] == 0.0
    assert v15["use_amp"] is False


def test_v16_candidate_strongly_locks_lowfrequency_position_before_long_training():
    module = load_module()
    module.patch_r61_registry()
    v15 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V15]
    v16 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V16]

    assert v16["profile"] == module.CLEAN_MOTION_PROFILE
    assert v16["external_selection_gate"] == "seeded_gmf_strong_lowfreq_guard"
    assert v16["input_lowfreq_weight"] >= v15["input_lowfreq_weight"] * 8.0
    assert v16["motion_input_lowfreq_weight"] > v15["motion_input_lowfreq_weight"]
    assert v16["boundary_residual_adapter_max"] < v15["boundary_residual_adapter_max"]
    assert v16["motion_loss_weight"] <= v15["motion_loss_weight"]
    assert v16["use_amp"] is False


def test_v17_candidate_uses_model_native_raw_anchor_detail_output():
    module = load_module()
    module.patch_r61_registry()
    v16 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V16]
    v17 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V17]

    assert v17["profile"] == module.CLEAN_MOTION_PROFILE
    assert v17["external_selection_gate"] == "native_raw_anchor_detail_guard"
    assert v17["raw_anchor_output_mode"] == "detail"
    assert v17["raw_anchor_output_sigma"] == 2.0
    assert 0.0 < v17["raw_anchor_output_detail_gain"] <= 0.50
    assert v17["input_lowfreq_weight"] < v16["input_lowfreq_weight"]
    assert v17["motion_input_lowfreq_weight"] >= v16["motion_input_lowfreq_weight"]
    assert v17["motion_recon_weight"] == 0.0
    assert v17["use_amp"] is False


def test_v18_candidate_is_more_conservative_native_raw_anchor_detail():
    module = load_module()
    module.patch_r61_registry()
    v17 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V17]
    v18 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V18]

    assert v18["profile"] == module.CLEAN_MOTION_PROFILE
    assert v18["external_selection_gate"] == "native_raw_anchor_conservative_detail_guard"
    assert v18["raw_anchor_output_mode"] == "detail"
    assert 0.0 < v18["raw_anchor_output_detail_gain"] < v17["raw_anchor_output_detail_gain"]
    assert v18["input_lowfreq_weight"] <= v17["input_lowfreq_weight"]
    assert v18["lr"] < v17["lr"]
    assert v18["motion_input_lowfreq_weight"] >= v17["motion_input_lowfreq_weight"]
    assert v18["motion_recon_weight"] == 0.0
    assert v18["use_amp"] is False


def test_v19_candidate_continues_from_v17_with_gmf_selection_guard():
    module = load_module()
    module.patch_r61_registry()
    v17 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V17]
    v19 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V19]

    assert v19["profile"] == module.CLEAN_MOTION_PROFILE
    assert v19["base_checkpoint"] == module.V17_NATIVE_ANCHOR_E3_CHECKPOINT
    assert v19["region_kd_teacher_checkpoint"] == module.V17_NATIVE_ANCHOR_E3_CHECKPOINT
    assert v19["external_selection_gate"] == "open_gmf_like_primary_plus_guardrail_gate"
    assert v19["raw_anchor_output_mode"] == "detail"
    assert v19["raw_anchor_output_detail_gain"] == v17["raw_anchor_output_detail_gain"]
    assert v19["lr"] < v17["lr"]
    assert v19["motion_loss_weight"] >= v17["motion_loss_weight"]
    assert v19["motion_input_lowfreq_weight"] >= v17["motion_input_lowfreq_weight"]
    assert v19["input_lowfreq_weight"] >= v17["input_lowfreq_weight"]
    assert v19["boundary_residual_adapter_max"] <= v17["boundary_residual_adapter_max"]
    assert v19["motion_recon_weight"] == 0.0
    assert v19["use_amp"] is False


def test_v20_candidate_trains_on_exact_gmf_roi_motion_package():
    module = load_module()
    module.patch_r61_registry()
    v19 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V19]
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]

    assert v20["profile"] == module.GMF_ROI_PROFILE
    assert v20["base_checkpoint"] == module.V17_NATIVE_ANCHOR_E3_CHECKPOINT
    assert v20["region_kd_teacher_checkpoint"] == module.V17_NATIVE_ANCHOR_E3_CHECKPOINT
    assert v20["external_selection_gate"] == "gmf_roi_primary_plus_guardrail_gate"
    assert module.GMF_ROI_STAGE in v20["train_include_subdirs"]
    assert module.GMF_ROI_STAGE in v20["motion_include_subdirs"]
    assert module.GMF_ROI_STAGE in v20["seq_include_subdirs"]
    assert "target_real_gmf_roi_selfshift_motion_pair" in v20["required_roles"]
    assert v20["motion_loss_weight"] >= v19["motion_loss_weight"]
    assert v20["motion_input_lowfreq_weight"] >= v19["motion_input_lowfreq_weight"]
    assert v20["boundary_residual_adapter_max"] <= v19["boundary_residual_adapter_max"]
    assert v20["motion_recon_weight"] == 0.0
    assert v20["use_amp"] is False


def test_v21_candidate_uses_r61_teacher_for_lowmag_gmf_preservation():
    module = load_module()
    module.patch_r61_registry()
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]
    v21 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V21]

    assert v21["profile"] == module.GMF_ROI_PROFILE
    assert v21["base_checkpoint"] == module.R61_V16_CHECKPOINT
    assert v21["region_kd_teacher_checkpoint"] == module.R61_V16_CHECKPOINT
    assert v21["external_selection_gate"] == "r61_lowmag_gmf_roi_preservation_gate"
    assert module.GMF_ROI_STAGE in v21["train_include_subdirs"]
    assert module.GMF_ROI_STAGE in v21["motion_include_subdirs"]
    assert module.GMF_ROI_STAGE in v21["seq_include_subdirs"]
    assert "target_real_gmf_roi_selfshift_motion_pair" in v21["required_roles"]
    assert "raw_anchor_output_mode" not in v21
    assert v21["region_kd_weight"] >= v20["region_kd_weight"]
    assert v21["identity_guard_kd_weight"] >= v20["identity_guard_kd_weight"]
    assert v21["boundary_residual_adapter_max"] <= v20["boundary_residual_adapter_max"]
    assert v21["motion_recon_weight"] == 0.0
    assert v21["use_amp"] is False


def test_v22_candidate_uses_dualroi_data_for_square_shape_and_dot_gmf():
    module = load_module()
    module.patch_r61_registry()
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]
    v22 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V22]

    assert v22["profile"] == module.LOWMAG_DUALROI_PROFILE
    assert v22["base_checkpoint"] == module.V17_NATIVE_ANCHOR_E3_CHECKPOINT
    assert v22["region_kd_teacher_checkpoint"] == module.V17_NATIVE_ANCHOR_E3_CHECKPOINT
    assert v22["external_selection_gate"] == "dualroi_square_shape_plus_dot_gmf_gate"
    assert module.LOWMAG_DUALROI_STAGE in v22["train_include_subdirs"]
    assert module.LOWMAG_DUALROI_STAGE in v22["motion_include_subdirs"]
    assert module.LOWMAG_DUALROI_STAGE in v22["seq_include_subdirs"]
    assert "target_real_lowmag_gmf_dot_r61_motion_pair" in v22["required_roles"]
    assert "target_real_lowmag_square_raw_shape_pair" in v22["required_roles"]
    assert v22["raw_anchor_output_mode"] == "detail"
    assert v22["region_kd_weight"] < v20["region_kd_weight"]
    assert v22["motion_loss_weight"] > v20["motion_loss_weight"]
    assert v22["motion_grad_weight"] > v20["motion_grad_weight"]
    assert v22["boundary_residual_adapter_max"] <= v20["boundary_residual_adapter_max"]
    assert v22["motion_recon_weight"] == 0.0
    assert v22["use_amp"] is False


def test_v23_candidate_learns_anchor_blend_teacher_without_output_fusion():
    module = load_module()
    module.patch_r61_registry()
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]
    v23 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V23]

    assert v23["profile"] == module.ANCHOR_BLEND_TEACHER_PROFILE
    assert v23["base_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert module.ANCHOR_BLEND_TEACHER_STAGE in v23["train_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE in v23["motion_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE in v23["seq_include_subdirs"]
    assert "target_real_anchor_blend10_teacher_pair" in v23["required_roles"]
    assert v23["raw_anchor_output_mode"] == "none"
    assert v23["region_kd_weight"] == 0.0
    assert v23["identity_guard_kd_weight"] == 0.0
    assert v23["motion_loss_weight"] >= v20["motion_loss_weight"]
    assert v23["input_lowfreq_weight"] >= v20["input_lowfreq_weight"]
    assert v23["boundary_residual_adapter_max"] <= v20["boundary_residual_adapter_max"]
    assert v23["motion_recon_weight"] == 0.0
    assert v23["use_amp"] is False


def test_v25_candidate_keeps_v24_shape_anchor_while_training_anchor_teacher_data():
    module = load_module()
    module.patch_r61_registry()
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]
    v23 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V23]
    v25 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V25]

    assert v25["profile"] == module.ANCHOR_BLEND_TEACHER_PROFILE
    assert v25["base_checkpoint"] == module.V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT
    assert v25["region_kd_teacher_checkpoint"] == module.V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT
    assert module.ANCHOR_BLEND_TEACHER_STAGE in v25["train_include_subdirs"]
    assert module.LOWMAG_DUALROI_STAGE in v25["train_include_subdirs"]
    assert "target_real_anchor_blend10_teacher_pair" in v25["required_roles"]
    assert "target_real_lowmag_square_raw_shape_pair" in v25["required_roles"]
    assert v25["raw_anchor_output_mode"] == "blend"
    assert v25["raw_anchor_output_alpha"] == 0.10
    assert v25["raw_anchor_output_sigma"] == 2.0
    assert v25["raw_anchor_output_detail_gain"] == 0.35
    assert v25["raw_anchor_output_mode"] != v23["raw_anchor_output_mode"]
    assert v25["region_kd_weight"] > v23["region_kd_weight"]
    assert v25["identity_guard_kd_weight"] > v23["identity_guard_kd_weight"]
    assert v25["motion_loss_weight"] <= v23["motion_loss_weight"]
    assert v25["motion_input_lowfreq_weight"] >= v20["motion_input_lowfreq_weight"]
    assert v25["boundary_residual_adapter_max"] <= v23["boundary_residual_adapter_max"]
    assert v25["motion_recon_weight"] == 0.0
    assert v25["use_amp"] is False


def test_v26_candidate_prioritizes_primary_safety_and_raw_square_shape_over_r61_teacher():
    module = load_module()
    module.patch_r61_registry()
    v25 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V25]
    v26 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V26]

    assert v26["profile"] == module.ANCHOR_BLEND_TEACHER_PROFILE
    assert v26["base_checkpoint"] == module.V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT
    assert v26["region_kd_teacher_checkpoint"] == module.V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT
    assert v26["region_kd_teacher_checkpoint"] != module.R61_V16_CHECKPOINT
    assert module.LOWMAG_DUALROI_STAGE in v26["train_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE in v26["train_include_subdirs"]
    assert "target_real_lowmag_square_raw_shape_pair" in v26["required_roles"]
    assert "target_real_anchor_blend10_teacher_pair" in v26["required_roles"]
    assert v26["raw_anchor_output_mode"] == "blend"
    assert v26["raw_anchor_output_alpha"] == 0.10
    assert v26["external_selection_gate"] == "primarysafe_raw_square_shape_motion_gate"
    assert v26["lr"] < v25["lr"]
    assert v26["motion_loss_weight"] < v25["motion_loss_weight"]
    assert v26["motion_grad_weight"] < v25["motion_grad_weight"]
    assert v26["input_lowfreq_weight"] > v25["input_lowfreq_weight"]
    assert v26["region_kd_weight"] > v25["region_kd_weight"]
    assert v26["identity_guard_kd_weight"] > v25["identity_guard_kd_weight"]
    assert v26["identity_guard_position_weight"] > v25["identity_guard_position_weight"]
    assert v26["boundary_residual_adapter_max"] < v25["boundary_residual_adapter_max"]
    assert v26["motion_max_pairs"] < v25["motion_max_pairs"]
    assert v26["motion_recon_weight"] == 0.0
    assert v26["use_amp"] is False


def test_v27_candidate_keeps_v20_gmf_strength_while_safely_tuning_lowmag_shape():
    module = load_module()
    module.patch_r61_registry()
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]
    v22 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V22]
    v27 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V27]

    assert v27["profile"] == module.LOWMAG_DUALROI_PROFILE
    assert v27["base_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert v27["region_kd_teacher_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert module.GMF_ROI_STAGE in v27["train_include_subdirs"]
    assert module.LOWMAG_DUALROI_STAGE in v27["train_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE not in v27["train_include_subdirs"]
    assert "target_real_gmf_roi_selfshift_motion_pair" in v27["required_roles"]
    assert "target_real_lowmag_square_raw_shape_pair" in v27["required_roles"]
    assert "target_real_lowmag_gmf_dot_r61_motion_pair" in v27["required_roles"]
    assert v27["external_selection_gate"] == "v20_lowmag_square_safety_gmf_gate"
    assert v27["raw_anchor_output_mode"] == v20["raw_anchor_output_mode"]
    assert v27["lr"] < v20["lr"]
    assert v27["lr"] < v22["lr"]
    assert v27["motion_loss_weight"] < v20["motion_loss_weight"]
    assert v27["motion_loss_weight"] < v22["motion_loss_weight"]
    assert v27["region_kd_weight"] > v20["region_kd_weight"]
    assert v27["identity_guard_kd_weight"] > v20["identity_guard_kd_weight"]
    assert v27["boundary_residual_adapter_max"] < v20["boundary_residual_adapter_max"]
    assert v27["boundary_residual_adapter_max"] < v22["boundary_residual_adapter_max"]
    assert v27["motion_recon_weight"] == 0.0
    assert v27["use_amp"] is False


def test_v28_candidate_adds_multimag_raw_motion_guard_without_anchor_teacher():
    module = load_module()
    module.patch_r61_registry()
    v20 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V20]
    v27 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V27]
    v28 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V28]

    assert v28["profile"] == module.MULTIMAG_RAW_GUARD_PROFILE
    assert v28["base_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert v28["region_kd_teacher_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert module.GMF_ROI_STAGE in v28["train_include_subdirs"]
    assert module.LOWMAG_DUALROI_STAGE in v28["train_include_subdirs"]
    assert module.MULTIMAG_RAW_GUARD_STAGE in v28["train_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE not in v28["train_include_subdirs"]
    assert "target_real_multimag_raw_motion_guard_pair" in v28["required_roles"]
    assert "target_real_lowmag_square_raw_shape_pair" in v28["required_roles"]
    assert v28["external_selection_gate"] == "v20_multimag_raw_motion_guard_gmf_gate"
    assert v28["lr"] > v27["lr"]
    assert v28["lr"] < v20["lr"]
    assert v28["motion_loss_weight"] >= v27["motion_loss_weight"]
    assert v28["region_kd_weight"] >= v27["region_kd_weight"]
    assert v28["identity_guard_kd_weight"] >= v27["identity_guard_kd_weight"]
    assert v28["boundary_residual_adapter_max"] <= v20["boundary_residual_adapter_max"]
    assert v28["motion_recon_weight"] == 0.0
    assert v28["use_amp"] is False


def test_v32_candidate_uses_hybrid_readout_teacher_from_v28():
    module = load_module()
    module.patch_r61_registry()
    v28 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V28]
    v32 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V32]

    assert v32["profile"] == module.HYBRID_READOUT_TEACHER_PROFILE
    assert v32["base_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert v32["region_kd_teacher_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert module.HYBRID_READOUT_TEACHER_STAGE in v32["train_include_subdirs"]
    assert module.MULTIMAG_RAW_GUARD_STAGE in v32["train_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE not in v32["train_include_subdirs"]
    assert "target_real_hybrid_readout_teacher_pair" in v32["required_roles"]
    assert "target_real_multimag_raw_motion_guard_pair" in v32["required_roles"]
    assert v32["external_selection_gate"] == "hybrid_readout_teacher_shape_motion_gate"
    assert v32["lr"] < v28["lr"]
    assert v32["region_kd_weight"] >= v28["region_kd_weight"]
    assert v32["identity_guard_kd_weight"] >= v28["identity_guard_kd_weight"]
    assert v32["boundary_residual_adapter_max"] <= v28["boundary_residual_adapter_max"]


def test_v33_candidate_focuses_hybrid_teacher_without_old_r61_shape_mix():
    module = load_module()
    module.patch_r61_registry()
    v32 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V32]
    v33 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V33]

    assert v33["profile"] == module.HYBRID_READOUT_TEACHER_PROFILE
    assert v33["base_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert v33["region_kd_teacher_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert v33["train_include_subdirs"] == module.R62_HYBRID_READOUT_TEACHER_FOCUSED_SUBDIRS
    assert module.HYBRID_READOUT_TEACHER_STAGE in v33["train_include_subdirs"]
    assert module.TARGET_STAGE not in v33["train_include_subdirs"]
    assert module.ANCHOR_BLEND_TEACHER_STAGE not in v33["train_include_subdirs"]
    assert "target_real_hybrid_readout_teacher_pair" in v33["required_roles"]
    assert "target_real_pseudo_boundary" not in v33["required_roles"]
    assert v33["disable_external_fixed_split"] is True
    assert v33["trainable_name_patterns"] == ("boundary_adapter",)
    assert v33["lr"] < v32["lr"]
    assert v33["region_kd_weight"] > v32["region_kd_weight"]
    assert v33["identity_guard_kd_weight"] > v32["identity_guard_kd_weight"]
    assert v33["boundary_residual_adapter_max"] < v32["boundary_residual_adapter_max"]
    assert v33["motion_recon_weight"] == 0.0
    assert v33["use_amp"] is False


def test_v34_candidate_uses_stability_shape_teacher_without_untrusted_lowmag_1um():
    module = load_module()
    module.patch_r61_registry()
    v28 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V28]
    v34 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V34]

    assert v34["profile"] == module.STABILITY_SHAPE_TEACHER_PROFILE
    assert v34["base_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert v34["region_kd_teacher_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert module.STABILITY_SHAPE_TEACHER_STAGE in v34["train_include_subdirs"]
    assert module.HYBRID_READOUT_TEACHER_STAGE not in v34["train_include_subdirs"]
    assert "target_real_stability_shape_teacher_pair" in v34["required_roles"]
    assert "target_real_hybrid_readout_teacher_pair" not in v34["required_roles"]
    assert v34["disable_external_fixed_split"] is True
    assert v34["trainable_name_patterns"] == ("boundary_adapter", "out")
    assert v34["lr"] < v28["lr"]
    assert v34["boundary_residual_adapter_max"] < v28["boundary_residual_adapter_max"]
    assert v34["external_selection_guardrail_cases"] == (
        "20260702_100MG/x_1um",
        "20260702_100MG/x_0p5um",
        "20260704_20x_5x/20x_1um",
        "20260704_20x_5x/20x_0p5um",
        "20260704_20x_5x/5x_0p5um",
    )
    assert v34["motion_recon_weight"] == 0.0
    assert v34["use_amp"] is False


def test_v35_candidate_is_aggressive_stability_teacher_probe():
    module = load_module()
    module.patch_r61_registry()
    v34 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V34]
    v35 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V35]

    assert v35["profile"] == module.STABILITY_SHAPE_TEACHER_PROFILE
    assert v35["base_checkpoint"] == module.V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT
    assert v35["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v35["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert v35["trainable_name_patterns"] == ("boundary_adapter", "p1", "out")
    assert v35["lr"] > v34["lr"]
    assert v35["region_kd_weight"] < v34["region_kd_weight"]
    assert v35["identity_guard_kd_weight"] < v34["identity_guard_kd_weight"]
    assert v35["input_lowfreq_weight"] < v34["input_lowfreq_weight"]
    assert v35["external_selection_gate"] == "aggressive_stability_teacher_probe_gate"
    assert "20260704_20x_5x/5x_1um" not in v35["external_selection_guardrail_cases"]
    assert v35["motion_recon_weight"] == 0.0
    assert v35["use_amp"] is False


def test_v36_candidate_restarts_stability_shape_probe_from_v20():
    module = load_module()
    module.patch_r61_registry()
    v35 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V35]
    v36 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V36]

    assert v36["profile"] == module.V20_STABILITY_SHAPE_TEACHER_PROFILE
    assert v36["base_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert v36["region_kd_teacher_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert v36["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v36["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert v36["trainable_name_patterns"] == ("boundary_adapter", "p1", "out")
    assert v36["lr"] < v35["lr"]
    assert v36["region_kd_weight"] > v35["region_kd_weight"]
    assert v36["identity_guard_kd_weight"] > v35["identity_guard_kd_weight"]
    assert v36["boundary_residual_adapter_max"] < v35["boundary_residual_adapter_max"]
    assert v36["external_selection_gate"] == "v20_stability_shape_teacher_probe_gate"
    assert v36["motion_recon_weight"] == 0.0
    assert v36["use_amp"] is False


def test_v37_candidate_uses_measurement_view_teacher_from_v35():
    module = load_module()
    module.patch_r61_registry()
    v35 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V35]
    v37 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V37]

    assert v37["profile"] == module.MEASUREMENT_VIEW_TEACHER_PROFILE
    assert v37["base_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v37["region_kd_teacher_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v37["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v37["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert v37["trainable_name_patterns"] == ("boundary_adapter", "p1", "out")
    assert v37["lr"] >= v35["lr"]
    assert v37["motion_loss_weight"] > v35["motion_loss_weight"]
    assert v37["region_kd_weight"] < v35["region_kd_weight"]
    assert v37["identity_guard_kd_weight"] < v35["identity_guard_kd_weight"]
    assert v37["external_selection_gate"] == "measurement_view_teacher_probe_gate"
    assert v37["motion_recon_weight"] == 0.0
    assert v37["use_amp"] is False


def test_v38_candidate_widens_measurement_view_learning_from_v35():
    module = load_module()
    module.patch_r61_registry()
    v37 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V37]
    v38 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V38]

    assert v38["profile"] == module.MEASUREMENT_VIEW_TEACHER_PROFILE
    assert v38["base_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v38["region_kd_teacher_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v38["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v38["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert set(v38["trainable_name_patterns"]) == {
        "boundary_adapter",
        "p1",
        "p2",
        "p3",
        "u1",
        "u2",
        "u3",
        "out",
    }
    assert v38["lr"] > v37["lr"]
    assert v38["motion_loss_weight"] >= v37["motion_loss_weight"]
    assert v38["region_kd_weight"] < v37["region_kd_weight"]
    assert v38["identity_guard_kd_weight"] < v37["identity_guard_kd_weight"]
    assert v38["boundary_residual_adapter_max"] > v37["boundary_residual_adapter_max"]
    assert v38["external_selection_gate"] == "wide_measurement_view_teacher_probe_gate"
    assert v38["motion_recon_weight"] == 0.0
    assert v38["use_amp"] is False


def test_v39_candidate_is_middle_measurement_view_guard_after_v38_tail_failure():
    module = load_module()
    module.patch_r61_registry()
    v37 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V37]
    v38 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V38]
    v39 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V39]

    assert v39["profile"] == module.MEASUREMENT_VIEW_TEACHER_PROFILE
    assert v39["base_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v39["region_kd_teacher_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v39["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v39["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert set(v39["trainable_name_patterns"]) == {"boundary_adapter", "p1", "p2", "out"}
    assert v37["lr"] < v39["lr"] < v38["lr"]
    assert v39["motion_loss_weight"] >= v37["motion_loss_weight"]
    assert v39["region_kd_weight"] >= v37["region_kd_weight"]
    assert v39["identity_guard_kd_weight"] >= v37["identity_guard_kd_weight"]
    assert v37["boundary_residual_adapter_max"] < v39["boundary_residual_adapter_max"] < v38["boundary_residual_adapter_max"]
    assert v39["external_selection_gate"] == "middle_measurement_view_tail_guard_gate"
    assert v39["motion_recon_weight"] == 0.0
    assert v39["use_amp"] is False


def test_v40_candidate_uses_safe_measurement_teacher_to_protect_100mg_1um():
    module = load_module()
    module.patch_r61_registry()
    v39 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V39]
    v40 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V40]

    assert v40["profile"] == module.SAFE_MEASUREMENT_VIEW_TEACHER_PROFILE
    assert v40["base_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v40["region_kd_teacher_checkpoint"] == module.V35_AGGRESSIVE_MTB500_CHECKPOINT
    assert v40["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v40["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert v40["trainable_name_patterns"] == v39["trainable_name_patterns"]
    assert v40["lr"] == v39["lr"]
    assert v40["region_kd_weight"] >= v39["region_kd_weight"]
    assert v40["identity_guard_kd_weight"] >= v39["identity_guard_kd_weight"]
    assert v40["external_selection_gate"] == "safe_measurement_view_tail_guard_gate"
    assert v40["motion_recon_weight"] == 0.0
    assert v40["use_amp"] is False


def test_v41_candidate_reanchors_safe_measurement_to_v20_shape():
    module = load_module()
    module.patch_r61_registry()
    v36 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V36]
    v37 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V37]
    v40 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V40]
    v41 = module.r61.CANDIDATE_SETTINGS[module.R62_CANDIDATE_V41]

    assert v41["profile"] == module.SAFE_MEASUREMENT_VIEW_TEACHER_PROFILE
    assert v41["base_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert v41["region_kd_teacher_checkpoint"] == module.V20_GMF_ROI_E1_CHECKPOINT
    assert v41["train_include_subdirs"] == (module.STABILITY_SHAPE_TEACHER_STAGE,)
    assert v41["required_roles"] == ("target_real_stability_shape_teacher_pair",)
    assert v41["trainable_name_patterns"] == ("boundary_adapter", "p1", "out")
    assert "p2" not in v41["trainable_name_patterns"]
    assert v36["lr"] < v41["lr"] < v40["lr"]
    assert v37["motion_loss_weight"] <= v41["motion_loss_weight"] < v40["motion_loss_weight"]
    assert v37["region_kd_weight"] < v41["region_kd_weight"] < v36["region_kd_weight"]
    assert v37["identity_guard_kd_weight"] < v41["identity_guard_kd_weight"] < v36["identity_guard_kd_weight"]
    assert v36["boundary_residual_adapter_max"] < v41["boundary_residual_adapter_max"] < v40["boundary_residual_adapter_max"]
    assert v41["external_selection_gate"] == "v20_safe_measurement_outer_guard_gate"
    assert v41["motion_recon_weight"] == 0.0
    assert v41["use_amp"] is False


def test_parser_allows_candidate_specific_base_checkpoint_for_v19():
    module = load_module()
    parser = module.build_arg_parser()

    args = parser.parse_args(["--candidate", module.R62_CANDIDATE_V19])

    assert args.base_checkpoint is None


def test_main_does_not_force_r61_checkpoint_when_candidate_has_own_base(monkeypatch):
    module = load_module()
    captured: dict[str, list[str]] = {}

    def fake_r61_main(argv):
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module.r61, "main", fake_r61_main)

    rc = module.main(["--candidate", module.R62_CANDIDATE_V19, "--dry-run"])

    assert rc == 0
    assert "--base-checkpoint" not in captured["argv"]
