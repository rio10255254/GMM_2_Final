"""R62 target-sample boost launcher.

This is a thin wrapper around the validated R61 LabSystem_MOSR launcher.  It
adds one thesis-candidate profile that starts from R61 v16 and trains on the
R62 target-sample package.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
R61_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts"
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
DEFAULT_PROFILE = "r62_target_sample_boost_v1"
REAL_MOTION_PROFILE = "r62_target_sample_boost_v2_real_motion"
SELFSHIFT_PROFILE = "r62_target_sample_boost_v3_selfshift_motion"
CLEAN_MOTION_PROFILE = "r62_target_sample_boost_v4_motion_clean"
GMF_ROI_PROFILE = "r62_target_sample_boost_v5_gmf_roi_motion_clean"
LOWMAG_DUALROI_PROFILE = "r62_target_sample_boost_v6_lowmag_dualroi_gmf_shape"
ANCHOR_BLEND_TEACHER_PROFILE = "r62_target_sample_boost_v7_anchor_blend10_teacher"
MULTIMAG_RAW_GUARD_PROFILE = "r62_target_sample_boost_v8_multimag_raw_motion_guard"
HYBRID_READOUT_TEACHER_PROFILE = "r62_target_sample_boost_v9_hybrid_readout_teacher"
STABILITY_SHAPE_TEACHER_PROFILE = "r62_target_sample_boost_v10_stability_shape_teacher"
V20_STABILITY_SHAPE_TEACHER_PROFILE = "r62_target_sample_boost_v11_v20_stability_shape_teacher"
MEASUREMENT_VIEW_TEACHER_PROFILE = "r62_target_sample_boost_v12_measurement_view_teacher"
SAFE_MEASUREMENT_VIEW_TEACHER_PROFILE = "r62_target_sample_boost_v13_measurement_view_safe_teacher"
R61_V16_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020"
    / "weights"
    / "best_tradeoff.pth.tar"
)
V17_NATIVE_ANCHOR_E3_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_native_raw_anchor_detail_v17_native_anchor_probe_e3_mtb300_20260706_20260706_071035"
    / "weights"
    / "best_tradeoff.pth.tar"
)
V20_GMF_ROI_E1_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_gmf_roi_guard_v20_v20_gmfroi_e1_mtb200_20260706_20260706_085102"
    / "weights"
    / "best_tradeoff.pth.tar"
)
V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "packaged_checkpoints"
    / "r62_v24_v7_anchor_blend10_builtin"
    / "r62_v24_v7_anchor_blend10_builtin.pth.tar"
)
V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_v20_multimag_raw_guard_v28_v28_multimagraw_e1_mtb300_20260706_20260706_122650"
    / "weights"
    / "latest.pth.tar"
)
V35_AGGRESSIVE_MTB500_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_aggressive_stability_teacher_v35_v35_aggressive_mtb500_20260706_20260706_143407"
    / "weights"
    / "best_tradeoff.pth.tar"
)
# The underlying trainer recognizes stage_34..stage_40 as boundary-domain data.
TARGET_STAGE = "stage_40_r62_target_real_pseudo"
REAL_MOTION_STAGE = "stage_40_r62_real_motion_pair"
SELF_SHIFT_STAGE = "stage_40_r62_target_selfshift_motion_pair"
GMF_ROI_STAGE = "stage_40_r62_gmf_roi_selfshift_motion_pair"
LOWMAG_DUALROI_STAGE = "stage_40_r62_lowmag_dualroi_selfshift_pair"
ANCHOR_BLEND_TEACHER_STAGE = "stage_40_r62_anchor_blend10_teacher_pair"
MULTIMAG_RAW_GUARD_STAGE = "stage_40_r62_multimag_raw_motion_guard_pair"
HYBRID_READOUT_TEACHER_STAGE = "stage_40_r62_hybrid_readout_teacher_pair"
STABILITY_SHAPE_TEACHER_STAGE = "stage_40_r62_stability_shape_teacher_pair"
R62_CANDIDATE = "r62_target_real_pseudo_stepguard_v1"
R62_CANDIDATE_V2 = "r62_target_real_pseudo_stepguard_v2_stronger"
R62_CANDIDATE_V3 = "r62_target_real_motion_v3"
R62_CANDIDATE_V4 = "r62_target_selfshift_motion_v4"
R62_CANDIDATE_V5 = "r62_target_selfshift_adapterguard_v5"
R62_CANDIDATE_V6 = "r62_target_selfshift_seqgeom_v6"
R62_CANDIDATE_V7 = "r62_target_selfshift_seqgeom_mobility_v7"
R62_CANDIDATE_V8 = "r62_target_selfshift_gmfgate_v8"
R62_CANDIDATE_V9 = "r62_target_selfshift_pairwise_gmf_guard_v9"
R62_CANDIDATE_V10 = "r62_target_selfshift_stablecore_micro_v10"
R62_CANDIDATE_V11 = "r62_target_selfshift_motion_clean_v11"
R62_CANDIDATE_V12 = "r62_target_selfshift_motion_center_v12"
R62_CANDIDATE_V13 = "r62_target_selfshift_local_motion_center_v13"
R62_CANDIDATE_V14 = "r62_target_selfshift_lowfreq_motion_guard_v14"
R62_CANDIDATE_V15 = "r62_target_selfshift_main_lowfreq_guard_v15"
R62_CANDIDATE_V16 = "r62_target_selfshift_strong_lowfreq_guard_v16"
R62_CANDIDATE_V17 = "r62_target_selfshift_native_raw_anchor_detail_v17"
R62_CANDIDATE_V18 = "r62_target_selfshift_native_raw_anchor_conservative_detail_v18"
R62_CANDIDATE_V19 = "r62_target_selfshift_v17_continue_open_gmf_guard_v19"
R62_CANDIDATE_V20 = "r62_target_selfshift_gmf_roi_guard_v20"
R62_CANDIDATE_V21 = "r62_target_selfshift_r61_lowmag_gmf_guard_v21"
R62_CANDIDATE_V22 = "r62_target_selfshift_dualroi_square_dot_v22"
R62_CANDIDATE_V23 = "r62_target_selfshift_anchor_blend_teacher_v23"
R62_CANDIDATE_V25 = "r62_target_selfshift_anchor_blend_safe_v25"
R62_CANDIDATE_V26 = "r62_target_selfshift_primarysafe_raw_square_v26"
R62_CANDIDATE_V27 = "r62_target_selfshift_v20_lowmag_square_safety_v27"
R62_CANDIDATE_V28 = "r62_target_selfshift_v20_multimag_raw_guard_v28"
R62_CANDIDATE_V32 = "r62_target_selfshift_hybrid_readout_teacher_v32"
R62_CANDIDATE_V33 = "r62_target_selfshift_focused_hybrid_teacher_v33"
R62_CANDIDATE_V34 = "r62_target_selfshift_stability_shape_teacher_v34"
R62_CANDIDATE_V35 = "r62_target_selfshift_aggressive_stability_teacher_v35"
R62_CANDIDATE_V36 = "r62_target_selfshift_v20_stability_shape_teacher_v36"
R62_CANDIDATE_V37 = "r62_target_selfshift_measurement_view_teacher_v37"
R62_CANDIDATE_V38 = "r62_target_selfshift_wide_measurement_view_teacher_v38"
R62_CANDIDATE_V39 = "r62_target_selfshift_middle_measurement_view_guard_v39"
R62_CANDIDATE_V40 = "r62_target_selfshift_safe_measurement_view_guard_v40"
R62_CANDIDATE_V41 = "r62_target_selfshift_v20_safe_measurement_outer_guard_v41"


sys.path.insert(0, str(R61_SCRIPT_DIR))

import launch_r61 as r61  # noqa: E402


R62_INCLUDE_SUBDIRS = r61.R61_STEP_GUARD_MOTION_TEXTURE_INCLUDE_SUBDIRS + (TARGET_STAGE,)
R62_REAL_MOTION_INCLUDE_SUBDIRS = R62_INCLUDE_SUBDIRS + (REAL_MOTION_STAGE,)
R62_SELFSHIFT_INCLUDE_SUBDIRS = R62_REAL_MOTION_INCLUDE_SUBDIRS + (SELF_SHIFT_STAGE,)
R62_GMF_ROI_INCLUDE_SUBDIRS = R62_SELFSHIFT_INCLUDE_SUBDIRS + (GMF_ROI_STAGE,)
R62_LOWMAG_DUALROI_INCLUDE_SUBDIRS = R62_GMF_ROI_INCLUDE_SUBDIRS + (LOWMAG_DUALROI_STAGE,)
R62_ANCHOR_BLEND_TEACHER_INCLUDE_SUBDIRS = R62_LOWMAG_DUALROI_INCLUDE_SUBDIRS + (ANCHOR_BLEND_TEACHER_STAGE,)
R62_MULTIMAG_RAW_GUARD_INCLUDE_SUBDIRS = R62_LOWMAG_DUALROI_INCLUDE_SUBDIRS + (MULTIMAG_RAW_GUARD_STAGE,)
R62_HYBRID_READOUT_TEACHER_INCLUDE_SUBDIRS = R62_MULTIMAG_RAW_GUARD_INCLUDE_SUBDIRS + (
    HYBRID_READOUT_TEACHER_STAGE,
)
R62_HYBRID_READOUT_TEACHER_FOCUSED_SUBDIRS = (
    GMF_ROI_STAGE,
    LOWMAG_DUALROI_STAGE,
    MULTIMAG_RAW_GUARD_STAGE,
    HYBRID_READOUT_TEACHER_STAGE,
)
R62_STABILITY_SHAPE_TEACHER_FOCUSED_SUBDIRS = (
    GMF_ROI_STAGE,
    LOWMAG_DUALROI_STAGE,
    MULTIMAG_RAW_GUARD_STAGE,
    STABILITY_SHAPE_TEACHER_STAGE,
)
R62_STABILITY_SHAPE_TEACHER_ONLY_SUBDIRS = (STABILITY_SHAPE_TEACHER_STAGE,)
R62_REQUIRED_ROLES = tuple(
    sorted(
        set(r61.REQUIRED_R61_ROLES)
        | {
            "motion_synthetic",
            "motion_texture_synthetic",
            "step_guard_motion_texture_synthetic",
            "target_real_pseudo_boundary",
        }
    )
)
R62_REAL_MOTION_REQUIRED_ROLES = tuple(sorted(set(R62_REQUIRED_ROLES) | {"target_real_motion_pair"}))
R62_SELFSHIFT_REQUIRED_ROLES = tuple(sorted(set(R62_REQUIRED_ROLES) | {"target_real_selfshift_motion_pair"}))
R62_GMF_ROI_REQUIRED_ROLES = tuple(
    sorted(set(R62_SELFSHIFT_REQUIRED_ROLES) | {"target_real_gmf_roi_selfshift_motion_pair"})
)
R62_LOWMAG_DUALROI_REQUIRED_ROLES = tuple(
    sorted(
        set(R62_GMF_ROI_REQUIRED_ROLES)
        | {
            "target_real_lowmag_gmf_dot_r61_motion_pair",
            "target_real_lowmag_square_raw_shape_pair",
        }
    )
)
R62_ANCHOR_BLEND_TEACHER_REQUIRED_ROLES = tuple(
    sorted(set(R62_LOWMAG_DUALROI_REQUIRED_ROLES) | {"target_real_anchor_blend10_teacher_pair"})
)
R62_MULTIMAG_RAW_GUARD_REQUIRED_ROLES = tuple(
    sorted(set(R62_LOWMAG_DUALROI_REQUIRED_ROLES) | {"target_real_multimag_raw_motion_guard_pair"})
)
R62_HYBRID_READOUT_TEACHER_REQUIRED_ROLES = tuple(
    sorted(set(R62_MULTIMAG_RAW_GUARD_REQUIRED_ROLES) | {"target_real_hybrid_readout_teacher_pair"})
)
R62_HYBRID_READOUT_TEACHER_FOCUSED_REQUIRED_ROLES = tuple(
    sorted(
        {
            "target_real_gmf_roi_selfshift_motion_pair",
            "target_real_lowmag_gmf_dot_r61_motion_pair",
            "target_real_lowmag_square_raw_shape_pair",
            "target_real_multimag_raw_motion_guard_pair",
            "target_real_hybrid_readout_teacher_pair",
        }
    )
)
R62_STABILITY_SHAPE_TEACHER_REQUIRED_ROLES = tuple(
    sorted(set(R62_MULTIMAG_RAW_GUARD_REQUIRED_ROLES) | {"target_real_stability_shape_teacher_pair"})
)
R62_STABILITY_SHAPE_TEACHER_ONLY_REQUIRED_ROLES = ("target_real_stability_shape_teacher_pair",)


def patch_r61_registry() -> None:
    r61.DEFAULT_DATA_ROOT = DEFAULT_DATA_ROOT
    base_settings = {
        "profile": DEFAULT_PROFILE,
        "base_checkpoint": R61_V16_CHECKPOINT,
        "region_kd_teacher_checkpoint": R61_V16_CHECKPOINT,
        "lr": 1.2e-7,
        "boundary": 0.012,
        "centerline": 0.007,
        "distance": 0.007,
        "seq_loss_weight": 0.10,
        "region_kd_weight": 8.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter", "p1", "out"),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.015,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0008,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_include_subdirs": R62_INCLUDE_SUBDIRS,
        "required_roles": R62_REQUIRED_ROLES,
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "target_dataset", "magnification_hint", "shape_family"),
        "train_group_balance_num_samples_mult": 1.25,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 24.0,
        "identity_guard_position_weight": 0.010,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "motion_enable": True,
        "motion_include_subdirs": (
            "stage_38_r61_motion_synthetic",
            "stage_39_r61_motion_texture_synthetic",
            "stage_40_r61_step_guard_motion_texture_synthetic",
        ),
        "motion_loss_weight": 0.06,
        "motion_recon_weight": 0.025,
        "motion_grad_weight": 0.20,
        "motion_boundary_weight": 4.0,
        "motion_every_n_batch": 1,
        "motion_batch_size": 2,
        "motion_max_pairs": 960,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard", TARGET_STAGE),
        "seq_val_max_pairs": 240,
        "seq_val_batch_size": 2,
        "gmf_validate_source": "seq_val",
        "gmf_validate_every_n": 1,
        "best_epoch_min": 1,
        "gmf_obj_j": 12.0,
        "gmf_obj_k": 4.0,
        "gmf_obj_l": 8.0,
        "gmf_obj_m": 4.0,
        "gmf_obj_n": 2.0,
        "gmf_obj_o": 8.0,
        "gmf_obj_p": 3.0,
        "gmf_obj_q": 10.0,
        "gmf_obj_r": 4.0,
        "gmf_obj_u": 2.0,
        "gmf_obj_v": 2.0,
    }
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE] = dict(base_settings)
    stronger_settings = dict(base_settings)
    stronger_settings.update(
        {
            "lr": 8.0e-7,
            "boundary": 0.018,
            "centerline": 0.010,
            "distance": 0.010,
            "seq_loss_weight": 0.08,
            "region_kd_weight": 1.5,
            "boundary_residual_adapter_max": 0.035,
            "train_group_balance_num_samples_mult": 1.6,
            "identity_guard_kd_weight": 6.0,
            "identity_guard_position_weight": 0.003,
            "motion_loss_weight": 0.035,
            "motion_recon_weight": 0.012,
            "motion_grad_weight": 0.12,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V2] = stronger_settings
    real_motion_settings = dict(stronger_settings)
    real_motion_settings.update(
        {
            "profile": REAL_MOTION_PROFILE,
            "lr": 2.0e-6,
            "boundary": 0.028,
            "centerline": 0.014,
            "distance": 0.014,
            "seq_loss_weight": 0.06,
            "region_kd_weight": 0.20,
            "region_kd_band_px": 8.0,
            "trainable_name_patterns": ("boundary_adapter", "p1", "p2", "p3", "u1", "u2", "u3", "out"),
            "boundary_residual_adapter_max": 0.060,
            "train_include_subdirs": R62_REAL_MOTION_INCLUDE_SUBDIRS,
            "required_roles": R62_REAL_MOTION_REQUIRED_ROLES,
            "train_group_balance_num_samples_mult": 1.9,
            "identity_guard_kd_weight": 0.50,
            "identity_guard_position_weight": 0.001,
            "motion_include_subdirs": (
                "stage_38_r61_motion_synthetic",
                "stage_39_r61_motion_texture_synthetic",
                "stage_40_r61_step_guard_motion_texture_synthetic",
                REAL_MOTION_STAGE,
            ),
            "motion_loss_weight": 0.22,
            "motion_recon_weight": 0.018,
            "motion_grad_weight": 0.35,
            "motion_boundary_weight": 5.0,
            "motion_max_pairs": 1600,
            "seq_val_include_subdirs": ("stage_35_r61_sequence_guard", TARGET_STAGE, REAL_MOTION_STAGE),
            "seq_val_max_pairs": 320,
            "gmf_obj_j": 10.0,
            "gmf_obj_k": 3.0,
            "gmf_obj_l": 6.0,
            "gmf_obj_m": 3.0,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V3] = real_motion_settings
    selfshift_settings = dict(stronger_settings)
    selfshift_settings.update(
        {
            "profile": SELFSHIFT_PROFILE,
            "lr": 6.0e-7,
            "boundary": 0.018,
            "centerline": 0.009,
            "distance": 0.009,
            "seq_loss_weight": 0.08,
            "region_kd_weight": 6.0,
            "region_kd_band_px": 10.0,
            "trainable_name_patterns": ("boundary_adapter", "p1", "p2", "out"),
            "boundary_residual_adapter_max": 0.030,
            "train_include_subdirs": R62_SELFSHIFT_INCLUDE_SUBDIRS,
            "required_roles": R62_SELFSHIFT_REQUIRED_ROLES,
            "train_group_balance_num_samples_mult": 1.7,
            "identity_guard_kd_weight": 10.0,
            "identity_guard_position_weight": 0.006,
            "motion_include_subdirs": (
                "stage_38_r61_motion_synthetic",
                "stage_39_r61_motion_texture_synthetic",
                "stage_40_r61_step_guard_motion_texture_synthetic",
                SELF_SHIFT_STAGE,
            ),
            "motion_loss_weight": 0.38,
            "motion_recon_weight": 0.006,
            "motion_grad_weight": 0.50,
            "motion_boundary_weight": 6.0,
            "motion_max_pairs": 2200,
            "seq_val_include_subdirs": ("stage_35_r61_sequence_guard", TARGET_STAGE, SELF_SHIFT_STAGE),
            "seq_val_max_pairs": 360,
            "gmf_obj_j": 12.0,
            "gmf_obj_k": 4.0,
            "gmf_obj_l": 8.0,
            "gmf_obj_m": 4.0,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V4] = selfshift_settings
    adapter_guard_settings = dict(selfshift_settings)
    adapter_guard_settings.update(
        {
            "lr": 3.0e-7,
            "boundary": 0.006,
            "centerline": 0.003,
            "distance": 0.003,
            "seq_loss_weight": 0.12,
            "region_kd_weight": 18.0,
            "region_kd_band_px": 12.0,
            "trainable_name_patterns": ("boundary_adapter",),
            "boundary_residual_adapter_max": 0.015,
            "train_group_balance_num_samples_mult": 1.4,
            "identity_guard_kd_weight": 35.0,
            "identity_guard_position_weight": 0.014,
            "motion_loss_weight": 0.85,
            "motion_recon_weight": 0.0,
            "motion_grad_weight": 0.18,
            "motion_boundary_weight": 8.0,
            "motion_max_pairs": 2200,
            "gmf_obj_j": 14.0,
            "gmf_obj_k": 4.0,
            "gmf_obj_l": 10.0,
            "gmf_obj_m": 5.0,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V5] = adapter_guard_settings
    seqgeom_settings = dict(selfshift_settings)
    seqgeom_settings.update(
        {
            "lr": 2.5e-7,
            "boundary": 0.010,
            "centerline": 0.005,
            "distance": 0.005,
            "seq_loss_weight": 0.20,
            "seq_grad_weight": 0.08,
            "seq_use_train_dirs": True,
            "seq_include_subdirs": (SELF_SHIFT_STAGE,),
            "seq_geom_method": "soft_band_stepmix_sharp",
            "seq_geom_center_weight": 0.028,
            "seq_geom_radius_weight": 0.012,
            "seq_geom_thick_weight": 0.004,
            "seq_geom_drift_weight": 0.006,
            "seq_step_mag_weight": 0.030,
            "seq_abs_center_weight": 0.018,
            "seq_single_abs_center_weight": 0.012,
            "seq_every_n_batch": 1,
            "seq_max_pairs": 720,
            "seq_min_delta_threshold": 0.0,
            "seq_warmup_epoch": 0,
            "region_kd_weight": 14.0,
            "region_kd_band_px": 12.0,
            "trainable_name_patterns": ("boundary_adapter", "p1", "p2", "out"),
            "boundary_residual_adapter_max": 0.020,
            "train_group_balance_num_samples_mult": 1.55,
            "identity_guard_kd_weight": 28.0,
            "identity_guard_position_weight": 0.012,
            "motion_include_subdirs": (SELF_SHIFT_STAGE,),
            "motion_loss_weight": 0.45,
            "motion_recon_weight": 0.0,
            "motion_grad_weight": 0.25,
            "motion_boundary_weight": 8.0,
            "motion_max_pairs": 720,
            "seq_val_include_subdirs": (SELF_SHIFT_STAGE,),
            "seq_val_max_pairs": 360,
            "gmf_obj_j": 16.0,
            "gmf_obj_k": 5.0,
            "gmf_obj_l": 12.0,
            "gmf_obj_m": 6.0,
            "gmf_obj_u": 3.0,
            "gmf_obj_v": 3.0,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V6] = seqgeom_settings
    seqgeom_mobility_settings = dict(seqgeom_settings)
    seqgeom_mobility_settings.update(
        {
            "lr": 1.2e-6,
            "boundary": 0.004,
            "centerline": 0.002,
            "distance": 0.002,
            "seq_loss_weight": 0.24,
            "seq_grad_weight": 0.06,
            "seq_geom_center_weight": 0.034,
            "seq_step_mag_weight": 0.040,
            "seq_abs_center_weight": 0.024,
            "seq_single_abs_center_weight": 0.018,
            "region_kd_weight": 18.0,
            "identity_guard_kd_weight": 34.0,
            "identity_guard_position_weight": 0.014,
            "boundary_residual_adapter_max": 0.018,
            "motion_loss_weight": 0.35,
            "motion_grad_weight": 0.18,
            "gmf_obj_j": 18.0,
            "gmf_obj_l": 14.0,
            "gmf_obj_m": 7.0,
            "use_amp": False,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V7] = seqgeom_mobility_settings
    gmf_gate_settings = dict(seqgeom_mobility_settings)
    gmf_gate_settings.update(
        {
            "lr": 3.0e-7,
            "boundary": 0.005,
            "centerline": 0.0025,
            "distance": 0.0025,
            "seq_loss_weight": 0.22,
            "seq_grad_weight": 0.08,
            "seq_geom_center_weight": 0.040,
            "seq_step_mag_weight": 0.055,
            "seq_abs_center_weight": 0.030,
            "seq_single_abs_center_weight": 0.022,
            "region_kd_weight": 7.0,
            "identity_guard_kd_weight": 42.0,
            "identity_guard_position_weight": 0.024,
            "boundary_residual_adapter_max": 0.014,
            "motion_loss_weight": 0.82,
            "motion_recon_weight": 0.018,
            "motion_grad_weight": 0.30,
            "motion_boundary_weight": 10.0,
            "gmf_obj_j": 20.0,
            "gmf_obj_l": 16.0,
            "gmf_obj_m": 8.0,
            "gmf_obj_u": 4.0,
            "gmf_obj_v": 4.0,
            "use_amp": False,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V8] = gmf_gate_settings
    pairwise_gmf_guard_settings = dict(seqgeom_mobility_settings)
    pairwise_gmf_guard_settings.update(
        {
            "lr": 4.0e-7,
            "boundary": 0.0045,
            "centerline": 0.0022,
            "distance": 0.0022,
            "seq_loss_weight": 0.23,
            "seq_grad_weight": 0.075,
            "seq_geom_center_weight": 0.038,
            "seq_step_mag_weight": 0.048,
            "seq_abs_center_weight": 0.028,
            "seq_single_abs_center_weight": 0.020,
            "region_kd_weight": 18.0,
            "identity_guard_kd_weight": 44.0,
            "identity_guard_position_weight": 0.020,
            "boundary_residual_adapter_max": 0.016,
            "motion_loss_weight": 0.52,
            "motion_recon_weight": 0.010,
            "motion_grad_weight": 0.24,
            "motion_boundary_weight": 9.0,
            "gmf_obj_j": 19.0,
            "gmf_obj_l": 15.0,
            "gmf_obj_m": 7.0,
            "gmf_obj_u": 4.0,
            "gmf_obj_v": 4.0,
            "external_selection_gate": "pairwise_gmf_thesis_guard",
            "external_selection_primary_cases": (
                "20260702_100MG/x_1um",
                "20260702_100MG/x_0p5um",
            ),
            "external_selection_guardrail_cases": (
                "20260704_20x_5x/20x_1um",
                "20260704_20x_5x/20x_0p5um",
                "20260704_20x_5x/5x_1um",
                "20260704_20x_5x/5x_0p5um",
            ),
            "use_amp": False,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V9] = pairwise_gmf_guard_settings
    stable_core_micro_settings = dict(seqgeom_mobility_settings)
    stable_core_micro_settings.update(
        {
            "lr": 1.0e-7,
            "boundary": 0.0035,
            "centerline": 0.0018,
            "distance": 0.0018,
            "seq_loss_weight": 0.20,
            "seq_grad_weight": 0.045,
            "seq_geom_center_weight": 0.030,
            "seq_step_mag_weight": 0.032,
            "seq_abs_center_weight": 0.022,
            "seq_single_abs_center_weight": 0.016,
            "region_kd_weight": 24.0,
            "identity_guard_kd_weight": 50.0,
            "identity_guard_position_weight": 0.018,
            "boundary_residual_adapter_max": 0.010,
            "motion_loss_weight": 0.22,
            "motion_recon_weight": 0.0,
            "motion_grad_weight": 0.12,
            "motion_boundary_weight": 6.0,
            "gmf_obj_j": 16.0,
            "gmf_obj_l": 12.0,
            "gmf_obj_m": 6.0,
            "gmf_obj_u": 3.0,
            "gmf_obj_v": 3.0,
            "external_selection_gate": "pairwise_gmf_stable_core_guard",
            "external_selection_primary_cases": (
                "20260702_100MG/x_1um",
                "20260702_100MG/x_0p5um",
            ),
            "external_selection_guardrail_cases": (
                "20260704_20x_5x/20x_1um",
                "20260704_20x_5x/20x_0p5um",
                "20260704_20x_5x/5x_1um",
                "20260704_20x_5x/5x_0p5um",
            ),
            "use_amp": False,
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V10] = stable_core_micro_settings
    motion_clean_settings = dict(seqgeom_mobility_settings)
    motion_clean_settings.update(
        {
            "profile": CLEAN_MOTION_PROFILE,
            "external_selection_gate": "pairwise_gmf_motion_clean_guard",
            "external_selection_primary_cases": (
                "20260702_100MG/x_1um",
                "20260702_100MG/x_0p5um",
            ),
            "external_selection_guardrail_cases": (
                "20260704_20x_5x/20x_1um",
                "20260704_20x_5x/20x_0p5um",
                "20260704_20x_5x/5x_1um",
                "20260704_20x_5x/5x_0p5um",
            ),
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V11] = motion_clean_settings
    motion_center_settings = dict(seqgeom_mobility_settings)
    motion_center_settings.update(
        {
            "profile": CLEAN_MOTION_PROFILE,
            "lr": 8.0e-7,
            "motion_loss_weight": 0.32,
            "motion_recon_weight": 0.0,
            "motion_grad_weight": 0.18,
            "motion_boundary_weight": 8.0,
            "motion_center_weight": 0.060,
            "motion_center_mask_dilate": 7,
            "motion_center_intensity_weight": 0.10,
            "external_selection_gate": "pairwise_gmf_motion_center_guard",
            "external_selection_primary_cases": (
                "20260702_100MG/x_1um",
                "20260702_100MG/x_0p5um",
            ),
            "external_selection_guardrail_cases": (
                "20260704_20x_5x/20x_1um",
                "20260704_20x_5x/20x_0p5um",
                "20260704_20x_5x/5x_1um",
                "20260704_20x_5x/5x_0p5um",
            ),
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V12] = motion_center_settings
    local_motion_center_settings = dict(motion_center_settings)
    local_motion_center_settings.update(
        {
            "motion_loss_weight": 0.30,
            "motion_center_weight": 0.015,
            "motion_local_center_weight": 0.050,
            "motion_local_center_grid": 4,
            "motion_center_mask_dilate": 9,
            "motion_center_intensity_weight": 0.10,
            "external_selection_gate": "pairwise_gmf_local_motion_center_guard",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V13] = local_motion_center_settings
    lowfreq_motion_guard_settings = dict(seqgeom_mobility_settings)
    lowfreq_motion_guard_settings.update(
        {
            "profile": CLEAN_MOTION_PROFILE,
            "lr": 5.0e-7,
            "motion_loss_weight": 0.28,
            "motion_recon_weight": 0.0,
            "motion_grad_weight": 0.16,
            "motion_boundary_weight": 7.0,
            "motion_input_lowfreq_weight": 0.80,
            "motion_input_lowfreq_sigma": 2.0,
            "region_kd_weight": 24.0,
            "identity_guard_kd_weight": 52.0,
            "identity_guard_position_weight": 0.022,
            "boundary_residual_adapter_max": 0.012,
            "external_selection_gate": "seeded_gmf_lowfreq_motion_guard",
            "external_selection_primary_cases": (
                "20260702_100MG/x_1um",
                "20260702_100MG/x_0p5um",
            ),
            "external_selection_guardrail_cases": (
                "20260704_20x_5x/20x_1um",
                "20260704_20x_5x/20x_0p5um",
                "20260704_20x_5x/5x_1um",
                "20260704_20x_5x/5x_0p5um",
            ),
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V14] = lowfreq_motion_guard_settings
    main_lowfreq_guard_settings = dict(lowfreq_motion_guard_settings)
    main_lowfreq_guard_settings.update(
        {
            "motion_loss_weight": 0.24,
            "motion_grad_weight": 0.14,
            "motion_input_lowfreq_weight": 1.20,
            "input_lowfreq_weight": 12.0,
            "input_lowfreq_sigma": 2.0,
            "region_kd_weight": 28.0,
            "identity_guard_kd_weight": 58.0,
            "identity_guard_position_weight": 0.026,
            "boundary_residual_adapter_max": 0.010,
            "external_selection_gate": "seeded_gmf_main_lowfreq_guard",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V15] = main_lowfreq_guard_settings
    strong_lowfreq_guard_settings = dict(main_lowfreq_guard_settings)
    strong_lowfreq_guard_settings.update(
        {
            "lr": 3.0e-7,
            "motion_loss_weight": 0.18,
            "motion_grad_weight": 0.10,
            "motion_input_lowfreq_weight": 5.0,
            "input_lowfreq_weight": 120.0,
            "region_kd_weight": 34.0,
            "identity_guard_kd_weight": 72.0,
            "identity_guard_position_weight": 0.032,
            "boundary_residual_adapter_max": 0.006,
            "external_selection_gate": "seeded_gmf_strong_lowfreq_guard",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V16] = strong_lowfreq_guard_settings
    native_raw_anchor_detail_settings = dict(strong_lowfreq_guard_settings)
    native_raw_anchor_detail_settings.update(
        {
            "lr": 3.0e-7,
            "motion_loss_weight": 0.16,
            "motion_grad_weight": 0.10,
            "motion_input_lowfreq_weight": 5.0,
            "input_lowfreq_weight": 24.0,
            "region_kd_weight": 28.0,
            "identity_guard_kd_weight": 64.0,
            "identity_guard_position_weight": 0.030,
            "boundary_residual_adapter_max": 0.006,
            "raw_anchor_output_mode": "detail",
            "raw_anchor_output_alpha": 0.10,
            "raw_anchor_output_sigma": 2.0,
            "raw_anchor_output_detail_gain": 0.35,
            "external_selection_gate": "native_raw_anchor_detail_guard",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V17] = native_raw_anchor_detail_settings
    native_raw_anchor_conservative_settings = dict(native_raw_anchor_detail_settings)
    native_raw_anchor_conservative_settings.update(
        {
            "lr": 2.0e-7,
            "motion_loss_weight": 0.14,
            "motion_grad_weight": 0.08,
            "motion_input_lowfreq_weight": 5.5,
            "input_lowfreq_weight": 18.0,
            "region_kd_weight": 32.0,
            "identity_guard_kd_weight": 70.0,
            "identity_guard_position_weight": 0.032,
            "boundary_residual_adapter_max": 0.005,
            "raw_anchor_output_detail_gain": 0.25,
            "external_selection_gate": "native_raw_anchor_conservative_detail_guard",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V18] = native_raw_anchor_conservative_settings
    v17_continue_open_gmf_guard_settings = dict(native_raw_anchor_detail_settings)
    v17_continue_open_gmf_guard_settings.update(
        {
            "base_checkpoint": V17_NATIVE_ANCHOR_E3_CHECKPOINT,
            "region_kd_teacher_checkpoint": V17_NATIVE_ANCHOR_E3_CHECKPOINT,
            "lr": 1.0e-7,
            "motion_loss_weight": 0.20,
            "motion_grad_weight": 0.12,
            "motion_input_lowfreq_weight": 5.5,
            "input_lowfreq_weight": 28.0,
            "region_kd_weight": 56.0,
            "identity_guard_kd_weight": 82.0,
            "identity_guard_position_weight": 0.034,
            "boundary_residual_adapter_max": 0.004,
            "raw_anchor_output_detail_gain": 0.35,
            "external_selection_gate": "open_gmf_like_primary_plus_guardrail_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V19] = v17_continue_open_gmf_guard_settings
    gmf_roi_guard_settings = dict(v17_continue_open_gmf_guard_settings)
    gmf_roi_guard_settings.update(
        {
            "profile": GMF_ROI_PROFILE,
            "train_include_subdirs": R62_GMF_ROI_INCLUDE_SUBDIRS,
            "required_roles": R62_GMF_ROI_REQUIRED_ROLES,
            "motion_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE),
            "seq_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE),
            "seq_val_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE),
            "motion_max_pairs": 2600,
            "seq_val_max_pairs": 420,
            "lr": 1.0e-7,
            "motion_loss_weight": 0.24,
            "motion_grad_weight": 0.14,
            "motion_input_lowfreq_weight": 6.5,
            "input_lowfreq_weight": 30.0,
            "region_kd_weight": 64.0,
            "identity_guard_kd_weight": 90.0,
            "identity_guard_position_weight": 0.038,
            "boundary_residual_adapter_max": 0.0035,
            "external_selection_gate": "gmf_roi_primary_plus_guardrail_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V20] = gmf_roi_guard_settings
    r61_lowmag_gmf_guard_settings = dict(strong_lowfreq_guard_settings)
    r61_lowmag_gmf_guard_settings.update(
        {
            "profile": GMF_ROI_PROFILE,
            "base_checkpoint": R61_V16_CHECKPOINT,
            "region_kd_teacher_checkpoint": R61_V16_CHECKPOINT,
            "train_include_subdirs": R62_GMF_ROI_INCLUDE_SUBDIRS,
            "required_roles": R62_GMF_ROI_REQUIRED_ROLES,
            "motion_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE),
            "seq_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE),
            "seq_val_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE),
            "motion_max_pairs": 3200,
            "seq_val_max_pairs": 520,
            "lr": 8.0e-8,
            "motion_loss_weight": 0.22,
            "motion_grad_weight": 0.16,
            "motion_input_lowfreq_weight": 8.0,
            "input_lowfreq_weight": 80.0,
            "region_kd_weight": 96.0,
            "identity_guard_kd_weight": 120.0,
            "identity_guard_position_weight": 0.050,
            "boundary_residual_adapter_max": 0.003,
            "external_selection_gate": "r61_lowmag_gmf_roi_preservation_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V21] = r61_lowmag_gmf_guard_settings
    dualroi_square_dot_settings = dict(v17_continue_open_gmf_guard_settings)
    dualroi_square_dot_settings.update(
        {
            "profile": LOWMAG_DUALROI_PROFILE,
            "train_include_subdirs": R62_LOWMAG_DUALROI_INCLUDE_SUBDIRS,
            "required_roles": R62_LOWMAG_DUALROI_REQUIRED_ROLES,
            "motion_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE),
            "seq_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE),
            "seq_val_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE),
            "motion_max_pairs": 3800,
            "seq_val_max_pairs": 680,
            "lr": 1.2e-7,
            "motion_loss_weight": 0.34,
            "motion_grad_weight": 0.22,
            "motion_input_lowfreq_weight": 5.2,
            "input_lowfreq_weight": 26.0,
            "region_kd_weight": 42.0,
            "identity_guard_kd_weight": 72.0,
            "identity_guard_position_weight": 0.036,
            "boundary_residual_adapter_max": 0.0035,
            "external_selection_gate": "dualroi_square_shape_plus_dot_gmf_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V22] = dualroi_square_dot_settings
    anchor_blend_teacher_settings = dict(dualroi_square_dot_settings)
    anchor_blend_teacher_settings.update(
        {
            "profile": ANCHOR_BLEND_TEACHER_PROFILE,
            "base_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "region_kd_teacher_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "train_include_subdirs": R62_ANCHOR_BLEND_TEACHER_INCLUDE_SUBDIRS,
            "required_roles": R62_ANCHOR_BLEND_TEACHER_REQUIRED_ROLES,
            "motion_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE, ANCHOR_BLEND_TEACHER_STAGE),
            "seq_include_subdirs": (SELF_SHIFT_STAGE, GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE, ANCHOR_BLEND_TEACHER_STAGE),
            "seq_val_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE, ANCHOR_BLEND_TEACHER_STAGE),
            "motion_max_pairs": 5200,
            "seq_val_max_pairs": 900,
            "lr": 8.0e-8,
            "motion_loss_weight": 0.36,
            "motion_grad_weight": 0.24,
            "motion_input_lowfreq_weight": 7.0,
            "input_lowfreq_weight": 34.0,
            "region_kd_weight": 0.0,
            "identity_guard_kd_weight": 0.0,
            "identity_guard_position_weight": 0.0,
            "boundary_residual_adapter_max": 0.0025,
            "raw_anchor_output_mode": "none",
            "external_selection_gate": "anchor_blend10_teacher_native_shape_motion_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V23] = anchor_blend_teacher_settings
    anchor_blend_safe_settings = dict(anchor_blend_teacher_settings)
    anchor_blend_safe_settings.update(
        {
            "base_checkpoint": V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT,
            "region_kd_teacher_checkpoint": V24_ANCHOR_BLEND_BUILTIN_CHECKPOINT,
            "lr": 5.0e-8,
            "motion_loss_weight": 0.30,
            "motion_grad_weight": 0.20,
            "motion_input_lowfreq_weight": 8.0,
            "input_lowfreq_weight": 42.0,
            "region_kd_weight": 24.0,
            "identity_guard_kd_weight": 32.0,
            "identity_guard_position_weight": 0.018,
            "boundary_residual_adapter_max": 0.002,
            "raw_anchor_output_mode": "blend",
            "raw_anchor_output_alpha": 0.10,
            "raw_anchor_output_sigma": 2.0,
            "raw_anchor_output_detail_gain": 0.35,
            "external_selection_gate": "anchor_blend10_safe_shape_motion_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V25] = anchor_blend_safe_settings
    primarysafe_raw_square_settings = dict(anchor_blend_safe_settings)
    primarysafe_raw_square_settings.update(
        {
            "lr": 2.0e-8,
            "motion_loss_weight": 0.20,
            "motion_grad_weight": 0.14,
            "motion_input_lowfreq_weight": 10.0,
            "input_lowfreq_weight": 64.0,
            "region_kd_weight": 64.0,
            "identity_guard_kd_weight": 96.0,
            "identity_guard_position_weight": 0.045,
            "boundary_residual_adapter_max": 0.0012,
            "motion_max_pairs": 3200,
            "seq_val_max_pairs": 900,
            "external_selection_gate": "primarysafe_raw_square_shape_motion_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V26] = primarysafe_raw_square_settings
    v20_lowmag_square_safety_settings = dict(gmf_roi_guard_settings)
    v20_lowmag_square_safety_settings.update(
        {
            "profile": LOWMAG_DUALROI_PROFILE,
            "base_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "region_kd_teacher_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "train_include_subdirs": R62_LOWMAG_DUALROI_INCLUDE_SUBDIRS,
            "required_roles": R62_LOWMAG_DUALROI_REQUIRED_ROLES,
            "motion_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE),
            "seq_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE),
            "seq_val_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE),
            "motion_max_pairs": 3000,
            "seq_val_max_pairs": 760,
            "lr": 2.0e-8,
            "motion_loss_weight": 0.16,
            "motion_grad_weight": 0.10,
            "motion_input_lowfreq_weight": 8.5,
            "input_lowfreq_weight": 72.0,
            "region_kd_weight": 104.0,
            "identity_guard_kd_weight": 132.0,
            "identity_guard_position_weight": 0.052,
            "boundary_residual_adapter_max": 0.0015,
            "external_selection_gate": "v20_lowmag_square_safety_gmf_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V27] = v20_lowmag_square_safety_settings
    v20_multimag_raw_guard_settings = dict(v20_lowmag_square_safety_settings)
    v20_multimag_raw_guard_settings.update(
        {
            "profile": MULTIMAG_RAW_GUARD_PROFILE,
            "train_include_subdirs": R62_MULTIMAG_RAW_GUARD_INCLUDE_SUBDIRS,
            "required_roles": R62_MULTIMAG_RAW_GUARD_REQUIRED_ROLES,
            "motion_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE, MULTIMAG_RAW_GUARD_STAGE),
            "seq_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE, MULTIMAG_RAW_GUARD_STAGE),
            "seq_val_include_subdirs": (GMF_ROI_STAGE, LOWMAG_DUALROI_STAGE, MULTIMAG_RAW_GUARD_STAGE),
            "motion_max_pairs": 4200,
            "seq_val_max_pairs": 920,
            "lr": 4.0e-8,
            "motion_loss_weight": 0.20,
            "motion_grad_weight": 0.12,
            "motion_input_lowfreq_weight": 9.5,
            "input_lowfreq_weight": 84.0,
            "region_kd_weight": 112.0,
            "identity_guard_kd_weight": 144.0,
            "identity_guard_position_weight": 0.056,
            "boundary_residual_adapter_max": 0.0018,
            "external_selection_gate": "v20_multimag_raw_motion_guard_gmf_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V28] = v20_multimag_raw_guard_settings
    hybrid_readout_teacher_settings = dict(v20_multimag_raw_guard_settings)
    hybrid_readout_teacher_settings.update(
        {
            "profile": HYBRID_READOUT_TEACHER_PROFILE,
            "base_checkpoint": V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT,
            "region_kd_teacher_checkpoint": V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT,
            "train_include_subdirs": R62_HYBRID_READOUT_TEACHER_INCLUDE_SUBDIRS,
            "required_roles": R62_HYBRID_READOUT_TEACHER_REQUIRED_ROLES,
            "motion_include_subdirs": (
                GMF_ROI_STAGE,
                LOWMAG_DUALROI_STAGE,
                MULTIMAG_RAW_GUARD_STAGE,
                HYBRID_READOUT_TEACHER_STAGE,
            ),
            "seq_include_subdirs": (
                GMF_ROI_STAGE,
                LOWMAG_DUALROI_STAGE,
                MULTIMAG_RAW_GUARD_STAGE,
                HYBRID_READOUT_TEACHER_STAGE,
            ),
            "seq_val_include_subdirs": (
                GMF_ROI_STAGE,
                LOWMAG_DUALROI_STAGE,
                MULTIMAG_RAW_GUARD_STAGE,
                HYBRID_READOUT_TEACHER_STAGE,
            ),
            "motion_max_pairs": 4800,
            "seq_val_max_pairs": 1000,
            "lr": 2.5e-8,
            "motion_loss_weight": 0.24,
            "motion_grad_weight": 0.13,
            "motion_input_lowfreq_weight": 10.0,
            "input_lowfreq_weight": 88.0,
            "region_kd_weight": 128.0,
            "identity_guard_kd_weight": 160.0,
            "identity_guard_position_weight": 0.060,
            "boundary_residual_adapter_max": 0.0016,
            "external_selection_gate": "hybrid_readout_teacher_shape_motion_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V32] = hybrid_readout_teacher_settings
    focused_hybrid_teacher_settings = dict(hybrid_readout_teacher_settings)
    focused_hybrid_teacher_settings.update(
        {
            "train_include_subdirs": R62_HYBRID_READOUT_TEACHER_FOCUSED_SUBDIRS,
            "required_roles": R62_HYBRID_READOUT_TEACHER_FOCUSED_REQUIRED_ROLES,
            "disable_external_fixed_split": True,
            "motion_include_subdirs": R62_HYBRID_READOUT_TEACHER_FOCUSED_SUBDIRS,
            "seq_include_subdirs": R62_HYBRID_READOUT_TEACHER_FOCUSED_SUBDIRS,
            "seq_val_include_subdirs": R62_HYBRID_READOUT_TEACHER_FOCUSED_SUBDIRS,
            "trainable_name_patterns": ("boundary_adapter",),
            "motion_max_pairs": 3600,
            "seq_val_max_pairs": 1000,
            "lr": 8.0e-9,
            "motion_loss_weight": 0.18,
            "motion_grad_weight": 0.09,
            "motion_input_lowfreq_weight": 11.0,
            "input_lowfreq_weight": 96.0,
            "region_kd_weight": 192.0,
            "identity_guard_kd_weight": 240.0,
            "identity_guard_position_weight": 0.080,
            "boundary_residual_adapter_max": 0.0008,
            "external_selection_gate": "focused_hybrid_teacher_shape_motion_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V33] = focused_hybrid_teacher_settings
    stability_shape_teacher_settings = dict(v20_multimag_raw_guard_settings)
    stability_shape_teacher_settings.update(
        {
            "profile": STABILITY_SHAPE_TEACHER_PROFILE,
            "base_checkpoint": V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT,
            "region_kd_teacher_checkpoint": V28_MULTIMAG_RAW_GUARD_LATEST_CHECKPOINT,
            "train_include_subdirs": R62_STABILITY_SHAPE_TEACHER_FOCUSED_SUBDIRS,
            "required_roles": R62_STABILITY_SHAPE_TEACHER_REQUIRED_ROLES,
            "disable_external_fixed_split": True,
            "motion_include_subdirs": R62_STABILITY_SHAPE_TEACHER_FOCUSED_SUBDIRS,
            "seq_include_subdirs": R62_STABILITY_SHAPE_TEACHER_FOCUSED_SUBDIRS,
            "seq_val_include_subdirs": R62_STABILITY_SHAPE_TEACHER_FOCUSED_SUBDIRS,
            "trainable_name_patterns": ("boundary_adapter", "out"),
            "motion_max_pairs": 4200,
            "seq_val_max_pairs": 1000,
            "lr": 1.2e-8,
            "motion_loss_weight": 0.22,
            "motion_grad_weight": 0.11,
            "motion_input_lowfreq_weight": 10.5,
            "input_lowfreq_weight": 104.0,
            "region_kd_weight": 180.0,
            "identity_guard_kd_weight": 232.0,
            "identity_guard_position_weight": 0.078,
            "boundary_residual_adapter_max": 0.0010,
            "external_selection_gate": "stability_shape_teacher_no_untrusted_5x1_gate",
            "external_selection_guardrail_cases": (
                "20260702_100MG/x_1um",
                "20260702_100MG/x_0p5um",
                "20260704_20x_5x/20x_1um",
                "20260704_20x_5x/20x_0p5um",
                "20260704_20x_5x/5x_0p5um",
            ),
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V34] = stability_shape_teacher_settings
    aggressive_stability_teacher_settings = dict(stability_shape_teacher_settings)
    aggressive_stability_teacher_settings.update(
        {
            "train_include_subdirs": R62_STABILITY_SHAPE_TEACHER_ONLY_SUBDIRS,
            "required_roles": R62_STABILITY_SHAPE_TEACHER_ONLY_REQUIRED_ROLES,
            "motion_include_subdirs": R62_STABILITY_SHAPE_TEACHER_ONLY_SUBDIRS,
            "seq_include_subdirs": R62_STABILITY_SHAPE_TEACHER_ONLY_SUBDIRS,
            "seq_val_include_subdirs": R62_STABILITY_SHAPE_TEACHER_ONLY_SUBDIRS,
            "trainable_name_patterns": ("boundary_adapter", "p1", "out"),
            "motion_max_pairs": 1200,
            "seq_val_max_pairs": 600,
            "lr": 8.0e-8,
            "motion_loss_weight": 0.32,
            "motion_grad_weight": 0.18,
            "motion_input_lowfreq_weight": 5.0,
            "input_lowfreq_weight": 28.0,
            "region_kd_weight": 24.0,
            "identity_guard_kd_weight": 32.0,
            "identity_guard_position_weight": 0.020,
            "boundary_residual_adapter_max": 0.0040,
            "external_selection_gate": "aggressive_stability_teacher_probe_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V35] = aggressive_stability_teacher_settings
    v20_stability_shape_teacher_settings = dict(aggressive_stability_teacher_settings)
    v20_stability_shape_teacher_settings.update(
        {
            "profile": V20_STABILITY_SHAPE_TEACHER_PROFILE,
            "base_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "region_kd_teacher_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "lr": 4.0e-8,
            "motion_loss_weight": 0.30,
            "motion_grad_weight": 0.16,
            "motion_input_lowfreq_weight": 6.0,
            "input_lowfreq_weight": 48.0,
            "region_kd_weight": 80.0,
            "identity_guard_kd_weight": 96.0,
            "identity_guard_position_weight": 0.035,
            "boundary_residual_adapter_max": 0.0025,
            "external_selection_gate": "v20_stability_shape_teacher_probe_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V36] = v20_stability_shape_teacher_settings
    measurement_view_teacher_settings = dict(aggressive_stability_teacher_settings)
    measurement_view_teacher_settings.update(
        {
            "profile": MEASUREMENT_VIEW_TEACHER_PROFILE,
            "base_checkpoint": V35_AGGRESSIVE_MTB500_CHECKPOINT,
            "region_kd_teacher_checkpoint": V35_AGGRESSIVE_MTB500_CHECKPOINT,
            "lr": 1.0e-7,
            "motion_loss_weight": 0.42,
            "motion_grad_weight": 0.24,
            "motion_input_lowfreq_weight": 3.0,
            "input_lowfreq_weight": 12.0,
            "region_kd_weight": 8.0,
            "identity_guard_kd_weight": 12.0,
            "identity_guard_position_weight": 0.010,
            "boundary_residual_adapter_max": 0.0060,
            "external_selection_gate": "measurement_view_teacher_probe_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V37] = measurement_view_teacher_settings
    wide_measurement_view_teacher_settings = dict(measurement_view_teacher_settings)
    wide_measurement_view_teacher_settings.update(
        {
            "trainable_name_patterns": ("boundary_adapter", "p1", "p2", "p3", "u1", "u2", "u3", "out"),
            "lr": 4.0e-7,
            "motion_loss_weight": 0.50,
            "motion_grad_weight": 0.32,
            "motion_input_lowfreq_weight": 1.5,
            "input_lowfreq_weight": 4.0,
            "region_kd_weight": 2.0,
            "identity_guard_kd_weight": 3.0,
            "identity_guard_position_weight": 0.003,
            "boundary_residual_adapter_max": 0.020,
            "external_selection_gate": "wide_measurement_view_teacher_probe_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V38] = wide_measurement_view_teacher_settings
    middle_measurement_view_guard_settings = dict(measurement_view_teacher_settings)
    middle_measurement_view_guard_settings.update(
        {
            "trainable_name_patterns": ("boundary_adapter", "p1", "p2", "out"),
            "lr": 2.0e-7,
            "motion_loss_weight": 0.46,
            "motion_grad_weight": 0.28,
            "motion_input_lowfreq_weight": 4.0,
            "input_lowfreq_weight": 16.0,
            "region_kd_weight": 12.0,
            "identity_guard_kd_weight": 18.0,
            "identity_guard_position_weight": 0.014,
            "boundary_residual_adapter_max": 0.010,
            "external_selection_gate": "middle_measurement_view_tail_guard_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V39] = middle_measurement_view_guard_settings
    safe_measurement_view_guard_settings = dict(middle_measurement_view_guard_settings)
    safe_measurement_view_guard_settings.update(
        {
            "profile": SAFE_MEASUREMENT_VIEW_TEACHER_PROFILE,
            "region_kd_weight": 16.0,
            "identity_guard_kd_weight": 22.0,
            "input_lowfreq_weight": 20.0,
            "external_selection_gate": "safe_measurement_view_tail_guard_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V40] = safe_measurement_view_guard_settings
    v20_safe_measurement_outer_guard_settings = dict(v20_stability_shape_teacher_settings)
    v20_safe_measurement_outer_guard_settings.update(
        {
            "profile": SAFE_MEASUREMENT_VIEW_TEACHER_PROFILE,
            "base_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "region_kd_teacher_checkpoint": V20_GMF_ROI_E1_CHECKPOINT,
            "trainable_name_patterns": ("boundary_adapter", "p1", "out"),
            "lr": 1.2e-7,
            "motion_loss_weight": 0.42,
            "motion_grad_weight": 0.24,
            "motion_input_lowfreq_weight": 4.0,
            "input_lowfreq_weight": 24.0,
            "region_kd_weight": 36.0,
            "identity_guard_kd_weight": 52.0,
            "identity_guard_position_weight": 0.018,
            "boundary_residual_adapter_max": 0.0060,
            "external_selection_gate": "v20_safe_measurement_outer_guard_gate",
        }
    )
    r61.CANDIDATE_SETTINGS[R62_CANDIDATE_V41] = v20_safe_measurement_outer_guard_settings
    r61.PROFILE_BY_CANDIDATE.clear()
    r61.PROFILE_BY_CANDIDATE.update({key: value["profile"] for key, value in r61.CANDIDATE_SETTINGS.items()})
    r61.REQUIRED_ROLES_BY_CANDIDATE.clear()
    r61.REQUIRED_ROLES_BY_CANDIDATE.update(
        {
            key: tuple(value.get("required_roles", tuple(sorted(r61.REQUIRED_R61_ROLES))))
            for key, value in r61.CANDIDATE_SETTINGS.items()
        }
    )


def build_arg_parser() -> argparse.ArgumentParser:
    patch_r61_registry()
    parser = r61.build_arg_parser()
    parser.set_defaults(
        candidate=R62_CANDIDATE,
        data_root=DEFAULT_DATA_ROOT,
        base_checkpoint=None,
        run_suffix="target_boost_20260705",
        num_epoch=4,
        batch_size=4,
        val_batch_size=2,
        num_workers=2,
        crop_size=256,
        seq_batch_size=2,
        val_ratio=0.12,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    patch_r61_registry()
    argv = list(argv) if argv is not None else sys.argv[1:]
    if "--candidate" not in argv:
        argv = ["--candidate", R62_CANDIDATE, *argv]
    if "--data-root" not in argv:
        argv = ["--data-root", str(DEFAULT_DATA_ROOT), *argv]
    selected_candidate = argv[argv.index("--candidate") + 1] if "--candidate" in argv else R62_CANDIDATE
    selected_settings = r61.CANDIDATE_SETTINGS.get(selected_candidate, {})
    selected_profile = selected_settings.get("profile", DEFAULT_PROFILE)
    selected_checkpoint = selected_settings.get("base_checkpoint", R61_V16_CHECKPOINT)
    if "--base-checkpoint" in argv:
        selected_checkpoint = argv[argv.index("--base-checkpoint") + 1]
    print(
        json.dumps(
            {
                "r62_launcher": True,
                "candidate": selected_candidate,
                "profile": selected_profile,
                "default_data_root": str(DEFAULT_DATA_ROOT),
                "base_checkpoint": str(selected_checkpoint),
                "target_stage": TARGET_STAGE,
                "real_motion_stage": REAL_MOTION_STAGE,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return r61.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
