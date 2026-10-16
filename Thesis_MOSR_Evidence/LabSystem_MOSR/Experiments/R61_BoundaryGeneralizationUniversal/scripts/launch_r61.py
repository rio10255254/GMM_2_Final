"""R61 universal boundary generalization launcher for LabSystem_MOSR."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[5]
MODEL_DIR = PROJECT_ROOT / "Model"
R60_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R60_SEMTruthBoundaryTraining" / "scripts"
R61_SCRIPT_DIR = EXPERIMENT_DIR / "scripts"
LAB_TRAINING_PROGRESS_ROOT = LAB_ROOT / "Traing_Progress"
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r61_universal_boundary_generalization" / "hs100mg_basler"
DEFAULT_R61_BASE_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r60_semtruth_boundary_focus_boundary_focus_e008_mtb064_20260622_20260622_020906"
    / "epoch_005.pth.tar"
)
R39_A970_BASE_CHECKPOINT = (
    EXPERIMENT_DIR
    / "reports"
    / "r39_best_latest_soup_20260623"
    / "r39_best_latest_a970.pth.tar"
)
V14_MOTION_TEXTURE_BASE_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_v11base_dualgate_boundary_focus_motiontexture_full_e8_20260623_150217"
    / "weights"
    / "best_tradeoff.pth.tar"
)
DEFAULT_VAL_RATIO = 0.1

R61_INCLUDE_SUBDIRS = (
    "stage_34_r61_legacy_shape",
    "stage_35_r61_sequence_guard",
    "stage_36_r61_sem_truth_anchor",
    "stage_37_r61_universal_synthetic",
)
R61_MOTION_INCLUDE_SUBDIRS = R61_INCLUDE_SUBDIRS + ("stage_38_r61_motion_synthetic",)
R61_MOTION_TEXTURE_INCLUDE_SUBDIRS = R61_MOTION_INCLUDE_SUBDIRS + (
    "stage_39_r61_motion_texture_synthetic",
)
R61_STEP_GUARD_MOTION_TEXTURE_INCLUDE_SUBDIRS = R61_MOTION_TEXTURE_INCLUDE_SUBDIRS + (
    "stage_40_r61_step_guard_motion_texture_synthetic",
)
REQUIRED_R61_ROLES = {
    "legacy_shape",
    "sequence_guard",
    "sem_truth_anchor",
    "universal_synthetic",
}

sys.path.insert(0, str(R61_SCRIPT_DIR))
sys.path.insert(0, str(R60_SCRIPT_DIR))
sys.path.insert(0, str(MODEL_DIR))

from prepare_r61_universal_dataset import prepare_grouped_fixed_split  # noqa: E402
from launch_r60 import BASE_OVERRIDES as R60_BASE_OVERRIDES  # noqa: E402
from launch_r60 import _count_files, prepare_lab_checkpoint  # noqa: E402


CANDIDATE_SETTINGS = {
    "r61_universal_balanced": {
        "profile": "r61_universal_boundary_train",
        "lr": 1.2e-6,
        "boundary": 0.110,
        "centerline": 0.062,
        "distance": 0.062,
        "seq_loss_weight": 0.14,
    },
    "r61_universal_boundary_focus": {
        "profile": "r61_universal_boundary_train",
        "lr": 1.0e-6,
        "boundary": 0.155,
        "centerline": 0.086,
        "distance": 0.086,
        "seq_loss_weight": 0.10,
    },
    "r61_polarity_truth_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_truth",
        "lr": 6.0e-7,
        "boundary": 0.170,
        "centerline": 0.092,
        "distance": 0.092,
        "seq_loss_weight": 0.08,
    },
    "r61_polarity_biasmix_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_biasmix",
        "lr": 6.0e-7,
        "boundary": 0.170,
        "centerline": 0.092,
        "distance": 0.092,
        "seq_loss_weight": 0.08,
    },
    "r61_polarity_subpixelmix_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_subpixelmix",
        "lr": 6.0e-7,
        "boundary": 0.170,
        "centerline": 0.092,
        "distance": 0.092,
        "seq_loss_weight": 0.08,
    },
    "r61_polarity_hybrid_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_hybrid",
        "lr": 6.0e-7,
        "boundary": 0.170,
        "centerline": 0.092,
        "distance": 0.092,
        "seq_loss_weight": 0.08,
    },
    "r61_polarity_hybrid_aligned_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_hybrid_aligned",
        "lr": 6.0e-7,
        "boundary": 0.170,
        "centerline": 0.092,
        "distance": 0.092,
        "seq_loss_weight": 0.08,
    },
    "r61_polarity_adaptive_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_adaptive",
        "lr": 6.0e-7,
        "boundary": 0.170,
        "centerline": 0.092,
        "distance": 0.092,
        "seq_loss_weight": 0.08,
    },
    "r61_polarity_identity_guard_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_identity_guard_v2",
        "lr": 5.0e-7,
        "boundary": 0.150,
        "centerline": 0.084,
        "distance": 0.084,
        "seq_loss_weight": 0.09,
    },
    "r61_polarity_small_bias_dark_thin_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_small_bias_dark_thin_v3",
        "lr": 2.0e-7,
        "boundary": 0.135,
        "centerline": 0.078,
        "distance": 0.078,
        "seq_loss_weight": 0.10,
    },
    "r61_polarity_small_bias_dark_thin_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_small_bias_dark_thin_v3",
        "lr": 5.0e-8,
        "boundary": 0.105,
        "centerline": 0.060,
        "distance": 0.060,
        "seq_loss_weight": 0.10,
        "region_kd_weight": 0.25,
        "region_kd_band_px": 8.0,
    },
    "r61_polarity_small_bias_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_small_bias_guard_v4",
        "lr": 2.0e-8,
        "boundary": 0.080,
        "centerline": 0.045,
        "distance": 0.045,
        "seq_loss_weight": 0.10,
        "region_kd_weight": 1.0,
        "region_kd_band_px": 8.0,
    },
    "r61_polarity_small_bias_replay_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_small_bias_replay_v5",
        "lr": 1.0e-8,
        "boundary": 0.060,
        "centerline": 0.035,
        "distance": 0.035,
        "seq_loss_weight": 0.10,
        "region_kd_weight": 2.0,
        "region_kd_band_px": 10.0,
    },
    "r61_polarity_small_bias_replay_head_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_small_bias_replay_v5",
        "lr": 2.0e-7,
        "boundary": 0.050,
        "centerline": 0.030,
        "distance": 0.030,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 3.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("p1", "out"),
    },
    "r61_polarity_small_bias_guard_head_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_small_bias_guard_v4",
        "lr": 5.0e-8,
        "boundary": 0.040,
        "centerline": 0.025,
        "distance": 0.025,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 4.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("p1", "out"),
    },
    "r61_polarity_failure_balanced_replay_head_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_failure_balanced_replay_v6",
        "lr": 1.5e-7,
        "boundary": 0.045,
        "centerline": 0.028,
        "distance": 0.028,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 4.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("p1", "out"),
    },
    "r61_polarity_failure_balanced_shape_neutral_head_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7",
        "lr": 1.0e-7,
        "boundary": 0.040,
        "centerline": 0.024,
        "distance": 0.024,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 4.5,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("p1", "out"),
    },
    "r61_polarity_bright_curve_replay_head_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_bright_curve_replay_v8",
        "lr": 4.0e-8,
        "boundary": 0.030,
        "centerline": 0.020,
        "distance": 0.020,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 5.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("p1", "out"),
    },
    "r61_polarity_boundary_adapter_shape_neutral_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7",
        "lr": 2.0e-4,
        "boundary": 0.040,
        "centerline": 0.024,
        "distance": 0.024,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 8.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
    },
    "r61_polarity_boundary_adapter_edgezero_shape_neutral_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7",
        "lr": 3.0e-4,
        "boundary": 0.040,
        "centerline": 0.024,
        "distance": 0.024,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 8.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.035,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_delta_bias": False,
        "boundary_residual_adapter_zero_mean": True,
        "boundary_residual_adapter_edge_gate": True,
    },
    "r61_polarity_boundary_adapter_failure_balanced_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_failure_balanced_replay_v6",
        "lr": 1.0e-4,
        "boundary": 0.045,
        "centerline": 0.028,
        "distance": 0.028,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 3.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
    },
    "r61_polarity_boundary_adapter_position_shape_neutral_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_failure_balanced_shape_neutral_v7",
        "lr": 5.0e-5,
        "boundary": 0.035,
        "centerline": 0.020,
        "distance": 0.020,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 3.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_position_loss_weight": 0.015,
        "boundary_position_coverage_weight": 0.20,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_position_bright_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_bright_curve_replay_v8",
        "lr": 1.5e-5,
        "boundary": 0.030,
        "centerline": 0.020,
        "distance": 0.020,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 5.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_position_loss_weight": 0.006,
        "boundary_position_coverage_weight": 0.15,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_position_bright_ellipse_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_bright_ellipse_guard_v9",
        "lr": 8.0e-6,
        "boundary": 0.028,
        "centerline": 0.018,
        "distance": 0.018,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 6.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_position_loss_weight": 0.004,
        "boundary_position_coverage_weight": 0.12,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_polarity_split_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_bright_curve_replay_v8",
        "lr": 6.0e-6,
        "boundary": 0.026,
        "centerline": 0.016,
        "distance": 0.016,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 6.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.020,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_polarity_split": True,
        "boundary_position_loss_weight": 0.003,
        "boundary_position_coverage_weight": 0.10,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_polarity_split_preserve_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_bright_curve_replay_v8",
        "lr": 4.0e-6,
        "boundary": 0.024,
        "centerline": 0.014,
        "distance": 0.014,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 8.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_polarity_split": True,
        "boundary_position_loss_weight": 0.002,
        "boundary_position_coverage_weight": 0.08,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_position_rotated_rect_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_rotated_rect_guard_v10",
        "lr": 3.0e-6,
        "boundary": 0.020,
        "centerline": 0.012,
        "distance": 0.012,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 10.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_position_loss_weight": 0.0015,
        "boundary_position_coverage_weight": 0.06,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_orientation_rotated_rect_guard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_rotated_rect_guard_v10",
        "lr": 2.0e-6,
        "boundary": 0.018,
        "centerline": 0.010,
        "distance": 0.010,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.001,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
    },
    "r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_rotated_rect_guard_v10",
        "lr": 1.5e-6,
        "boundary": 0.016,
        "centerline": 0.009,
        "distance": 0.009,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0008,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
    },
    "r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_identityguard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_rotated_rect_guard_v10",
        "lr": 1.2e-6,
        "boundary": 0.016,
        "centerline": 0.009,
        "distance": 0.009,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0008,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
    },
    "r61_polarity_boundary_adapter_orientation_rotrect_groupbalanced_identityposguard_region_kd_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_rotated_rect_guard_v10",
        "lr": 1.0e-6,
        "boundary": 0.016,
        "centerline": 0.009,
        "distance": 0.009,
        "seq_loss_weight": 0.08,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0008,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_position_weight": 0.012,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
    },
    "r61_motion_guard_dualgate_boundary_focus": {
        "profile": "r61_universal_boundary_train_polarity_rotated_rect_guard_v10",
        "base_checkpoint": R39_A970_BASE_CHECKPOINT,
        "lr": 8.0e-7,
        "boundary": 0.016,
        "centerline": 0.009,
        "distance": 0.009,
        "seq_loss_weight": 0.14,
        "region_kd_weight": 10.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.025,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0008,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_position_weight": 0.012,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard",),
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
    },
    "r61_motion_synthetic_dualgate_boundary_focus": {
        "profile": "r61_universal_boundary_train_motion_guard_v11",
        "base_checkpoint": R39_A970_BASE_CHECKPOINT,
        "lr": 5.0e-7,
        "boundary": 0.014,
        "centerline": 0.008,
        "distance": 0.008,
        "seq_loss_weight": 0.12,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.020,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0007,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_include_subdirs": R61_MOTION_INCLUDE_SUBDIRS,
        "required_roles": tuple(sorted(REQUIRED_R61_ROLES | {"motion_synthetic"})),
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_position_weight": 0.012,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "motion_enable": True,
        "motion_include_subdirs": ("stage_38_r61_motion_synthetic",),
        "motion_loss_weight": 0.08,
        "motion_recon_weight": 0.04,
        "motion_boundary_weight": 4.0,
        "motion_every_n_batch": 1,
        "motion_batch_size": 2,
        "motion_max_pairs": 640,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard",),
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
    },
    "r61_motion_gradient_dualgate_boundary_focus": {
        "profile": "r61_universal_boundary_train_motion_guard_v11",
        "base_checkpoint": R39_A970_BASE_CHECKPOINT,
        "lr": 3.0e-7,
        "boundary": 0.012,
        "centerline": 0.007,
        "distance": 0.007,
        "seq_loss_weight": 0.10,
        "region_kd_weight": 18.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.018,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0005,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_include_subdirs": R61_MOTION_INCLUDE_SUBDIRS,
        "required_roles": tuple(sorted(REQUIRED_R61_ROLES | {"motion_synthetic"})),
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 35.0,
        "identity_guard_position_weight": 0.014,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "motion_enable": True,
        "motion_include_subdirs": ("stage_38_r61_motion_synthetic",),
        "motion_loss_weight": 0.06,
        "motion_recon_weight": 0.025,
        "motion_grad_weight": 0.75,
        "motion_boundary_weight": 4.0,
        "motion_every_n_batch": 1,
        "motion_batch_size": 2,
        "motion_max_pairs": 640,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard",),
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
    },
    "r61_motion_gradient_v11base_dualgate_boundary_focus": {
        "profile": "r61_universal_boundary_train_motion_guard_v11",
        "base_checkpoint": R39_A970_BASE_CHECKPOINT,
        "lr": 5.0e-7,
        "boundary": 0.014,
        "centerline": 0.008,
        "distance": 0.008,
        "seq_loss_weight": 0.12,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.020,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0007,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_include_subdirs": R61_MOTION_INCLUDE_SUBDIRS,
        "required_roles": tuple(sorted(REQUIRED_R61_ROLES | {"motion_synthetic"})),
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_position_weight": 0.012,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "motion_enable": True,
        "motion_include_subdirs": ("stage_38_r61_motion_synthetic",),
        "motion_loss_weight": 0.08,
        "motion_recon_weight": 0.04,
        "motion_grad_weight": 0.25,
        "motion_boundary_weight": 4.0,
        "motion_every_n_batch": 1,
        "motion_batch_size": 2,
        "motion_max_pairs": 640,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard",),
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
    },
    "r61_motion_texture_v11base_dualgate_boundary_focus": {
        "profile": "r61_universal_boundary_train_motion_texture_guard_v14",
        "base_checkpoint": R39_A970_BASE_CHECKPOINT,
        "lr": 5.0e-7,
        "boundary": 0.014,
        "centerline": 0.008,
        "distance": 0.008,
        "seq_loss_weight": 0.12,
        "region_kd_weight": 12.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.020,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0007,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_include_subdirs": R61_MOTION_TEXTURE_INCLUDE_SUBDIRS,
        "required_roles": tuple(sorted(REQUIRED_R61_ROLES | {"motion_synthetic", "motion_texture_synthetic"})),
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_position_weight": 0.012,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "motion_enable": True,
        "motion_include_subdirs": (
            "stage_38_r61_motion_synthetic",
            "stage_39_r61_motion_texture_synthetic",
        ),
        "motion_loss_weight": 0.08,
        "motion_recon_weight": 0.04,
        "motion_grad_weight": 0.25,
        "motion_boundary_weight": 4.0,
        "motion_every_n_batch": 1,
        "motion_batch_size": 2,
        "motion_max_pairs": 1280,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard",),
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
    },
    "r61_motion_texture_stepguard_v16_dualgate_boundary_focus": {
        "profile": "r61_universal_boundary_train_motion_texture_step_guard_v16",
        "base_checkpoint": V14_MOTION_TEXTURE_BASE_CHECKPOINT,
        "region_kd_teacher_checkpoint": R39_A970_BASE_CHECKPOINT,
        "lr": 2.5e-7,
        "boundary": 0.014,
        "centerline": 0.008,
        "distance": 0.008,
        "seq_loss_weight": 0.12,
        "region_kd_weight": 10.0,
        "region_kd_band_px": 10.0,
        "trainable_name_patterns": ("boundary_adapter",),
        "boundary_residual_adapter_enable": True,
        "boundary_residual_adapter_hidden": 16,
        "boundary_residual_adapter_max": 0.018,
        "boundary_residual_adapter_gate_bias": -2.0,
        "boundary_residual_adapter_orientation_inputs": True,
        "boundary_position_loss_weight": 0.0006,
        "boundary_position_coverage_weight": 0.04,
        "boundary_position_distance_clip": 8.0,
        "train_include_subdirs": R61_STEP_GUARD_MOTION_TEXTURE_INCLUDE_SUBDIRS,
        "required_roles": tuple(
            sorted(
                REQUIRED_R61_ROLES
                | {
                    "motion_synthetic",
                    "motion_texture_synthetic",
                    "step_guard_motion_texture_synthetic",
                }
            )
        ),
        "train_group_balanced_sampler": True,
        "train_group_balance_keys": ("role", "polarity", "shape_family", "bias_px"),
        "train_group_balance_num_samples_mult": 1.0,
        "identity_guard_enable": True,
        "identity_guard_kd_weight": 30.0,
        "identity_guard_position_weight": 0.012,
        "identity_guard_bias_max": 0.5,
        "identity_guard_band_px": 10.0,
        "motion_enable": True,
        "motion_include_subdirs": (
            "stage_38_r61_motion_synthetic",
            "stage_39_r61_motion_texture_synthetic",
            "stage_40_r61_step_guard_motion_texture_synthetic",
        ),
        "motion_loss_weight": 0.08,
        "motion_recon_weight": 0.04,
        "motion_grad_weight": 0.25,
        "motion_boundary_weight": 4.0,
        "motion_every_n_batch": 1,
        "motion_batch_size": 2,
        "motion_max_pairs": 1920,
        "seq_val_enable": True,
        "seq_val_include_subdirs": ("stage_35_r61_sequence_guard",),
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
    },
}
PROFILE_BY_CANDIDATE = {key: value["profile"] for key, value in CANDIDATE_SETTINGS.items()}
REQUIRED_ROLES_BY_CANDIDATE = {
    key: tuple(value.get("required_roles", tuple(sorted(REQUIRED_R61_ROLES))))
    for key, value in CANDIDATE_SETTINGS.items()
}


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _require_assets() -> None:
    if not MODEL_DIR.is_dir():
        raise FileNotFoundError(f"main model directory not found: {MODEL_DIR}")
    if not LAB_PSF_PATH.exists():
        raise FileNotFoundError(f"Lab PSF file not found: {LAB_PSF_PATH}")


def ensure_data_package(
    profile_name: str,
    data_root: Path,
    required_roles: tuple[str, ...] | set[str] = tuple(sorted(REQUIRED_R61_ROLES)),
) -> tuple[Path, dict]:
    package_dir = Path(data_root) / str(profile_name)
    manifest = _load_manifest(package_dir / "manifest.json")
    if manifest.get("r61_universal_boundary_training") is not True:
        raise RuntimeError(f"not an R61 universal-boundary package: {package_dir}")
    if manifest.get("anti_answer_leakage_design") is not True:
        raise RuntimeError(f"R61 package is missing anti-answer-leakage design marker: {package_dir}")
    pairs = manifest.get("pairs", [])
    if int(manifest.get("total_pairs", -1)) != len(pairs) or not pairs:
        raise RuntimeError(f"R61 manifest pair count mismatch in {package_dir}")
    role_counts = dict(manifest.get("role_counts", {}))
    missing_roles = sorted(role for role in required_roles if int(role_counts.get(role, 0)) <= 0)
    if missing_roles:
        raise RuntimeError(f"missing required R61 roles: {missing_roles}")
    polarity_counts = dict(manifest.get("polarity_counts", {}))
    if int(polarity_counts.get("bright", 0)) <= 0 or int(polarity_counts.get("dark", 0)) <= 0:
        raise RuntimeError("R61 package must contain both bright and dark boundary examples")
    if manifest.get("geometry_sidecars") is not True or int(manifest.get("geometry_count", 0)) != len(pairs):
        raise RuntimeError(f"R61 geometry sidecars are not marked complete in {package_dir}")
    for leaf in ("src", "lbl", "geom"):
        if not (package_dir / leaf).is_dir():
            raise RuntimeError(f"missing {leaf} folder in {package_dir}")
    geom_dir = package_dir / "geom"
    for leaf in ("boundary", "centerline", "distance"):
        if _count_files(geom_dir / leaf) < len(pairs):
            raise RuntimeError(f"R61 geometry {leaf} sidecars are incomplete in {geom_dir}")
    return package_dir, manifest


def _set_lab_progress_root(trainer) -> None:
    if hasattr(trainer, "_set_training_progress_root"):
        trainer._set_training_progress_root(str(LAB_TRAINING_PROGRESS_ROOT))
    else:
        trainer.TRAINING_PROGRESS_ROOT = str(LAB_TRAINING_PROGRESS_ROOT)


def _resolve_base_checkpoint(args: argparse.Namespace) -> Path | None:
    if bool(getattr(args, "scratch", False)):
        return None
    checkpoint = getattr(args, "base_checkpoint", None)
    if checkpoint is not None:
        return Path(checkpoint)
    settings = CANDIDATE_SETTINGS.get(str(getattr(args, "candidate", "")), {})
    checkpoint = settings.get("base_checkpoint", DEFAULT_R61_BASE_CHECKPOINT)
    return Path(checkpoint)


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path, fixed_split_dir: Path | None = None) -> None:
    _require_assets()
    CFG = trainer.CFG
    for key, val in dict(R60_BASE_OVERRIDES).items():
        setattr(CFG, key, val)

    settings = CANDIDATE_SETTINGS[str(args.candidate)]
    CFG.LR = float(settings["lr"])
    CFG.BOUNDARY_LOSS_WEIGHT = float(settings["boundary"])
    CFG.CENTERLINE_LOSS_WEIGHT = float(settings["centerline"])
    CFG.DISTANCE_EDGE_LOSS_WEIGHT = float(settings["distance"])
    CFG.SEQ_LOSS_WEIGHT = float(settings["seq_loss_weight"])
    CFG.SEQ_ENABLE = True
    CFG.SEQ_GEOM_ENABLE = True
    if bool(settings.get("seq_use_train_dirs", False)):
        CFG.SEQ_SRC_DIR = str(Path(data_dir) / "src")
        CFG.SEQ_LBL_DIR = str(Path(data_dir) / "lbl")
    if "seq_src_dir" in settings:
        CFG.SEQ_SRC_DIR = str(Path(settings["seq_src_dir"]))
    if "seq_lbl_dir" in settings:
        CFG.SEQ_LBL_DIR = str(Path(settings["seq_lbl_dir"]))
    if "seq_include_subdirs" in settings:
        CFG.SEQ_INCLUDE_SUBDIRS = tuple(settings["seq_include_subdirs"])
    if "seq_grad_weight" in settings:
        CFG.SEQ_GRAD_WEIGHT = float(settings["seq_grad_weight"])
    if "seq_geom_enable" in settings:
        CFG.SEQ_GEOM_ENABLE = bool(settings["seq_geom_enable"])
    if "seq_geom_method" in settings:
        CFG.SEQ_GEOM_METHOD = str(settings["seq_geom_method"])
    if "seq_geom_center_weight" in settings:
        CFG.SEQ_GEOM_CENTER_WEIGHT = float(settings["seq_geom_center_weight"])
    if "seq_geom_radius_weight" in settings:
        CFG.SEQ_GEOM_RADIUS_WEIGHT = float(settings["seq_geom_radius_weight"])
    if "seq_geom_thick_weight" in settings:
        CFG.SEQ_GEOM_THICK_WEIGHT = float(settings["seq_geom_thick_weight"])
    if "seq_geom_drift_weight" in settings:
        CFG.SEQ_GEOM_DRIFT_WEIGHT = float(settings["seq_geom_drift_weight"])
    if "seq_step_mag_weight" in settings:
        CFG.SEQ_STEP_MAG_WEIGHT = float(settings["seq_step_mag_weight"])
    if "seq_abs_center_weight" in settings:
        CFG.SEQ_ABS_CENTER_WEIGHT = float(settings["seq_abs_center_weight"])
    if "seq_single_abs_center_weight" in settings:
        CFG.SEQ_SINGLE_ABS_CENTER_WEIGHT = float(settings["seq_single_abs_center_weight"])
    if "seq_mono_weight" in settings:
        CFG.SEQ_MONO_WEIGHT = float(settings["seq_mono_weight"])
    if "seq_every_n_batch" in settings:
        CFG.SEQ_EVERY_N_BATCH = int(settings["seq_every_n_batch"])
    if "seq_max_pairs" in settings:
        CFG.SEQ_MAX_PAIRS = int(settings["seq_max_pairs"])
    if "seq_min_delta_threshold" in settings:
        CFG.SEQ_MIN_DELTA_THRESHOLD = float(settings["seq_min_delta_threshold"])
    if "seq_warmup_epoch" in settings:
        CFG.SEQ_WARMUP_EPOCH = int(settings["seq_warmup_epoch"])
    if "use_amp" in settings:
        CFG.use_amp = bool(settings["use_amp"])
    CFG.TRAIN_INCLUDE_SUBDIRS = tuple(settings.get("train_include_subdirs", R61_INCLUDE_SUBDIRS))
    CFG.TRAIN_EXCLUDE_SUBDIRS = ()
    CFG.PSF_FITTED_PATH = str(LAB_PSF_PATH)
    CFG.PHYS_FORWARD_ENABLE = False
    CFG.W_PHYS_MAX = 0.0
    CFG.WEAK_PSF_BETA_INIT = 0.0
    CFG.WEAK_PSF_BETA_SCALE_MAX = 0.0
    CFG.WEAK_PSF_LR_MULT = 0.0
    CFG.BOUNDARY_GEOM_ENABLE = True
    CFG.R61_UNIVERSAL_BOUNDARY = True
    CFG.R61_ANTI_ANSWER_LEAKAGE_REQUIRED = True
    CFG.R61_VALIDATION_REQUIRED = True
    CFG.KD_ENABLE = False
    CFG.KD_WEIGHT_COMBO = 0.0
    CFG.KD_WEIGHT_R40 = 0.0
    CFG.KD_COMBO_PATH = ""
    CFG.KD_R40_PATH = ""
    CFG.REGION_KD_ENABLE = False
    CFG.REGION_KD_TEACHER_PATH = ""
    CFG.REGION_KD_WEIGHT = 0.0
    CFG.REGION_KD_WARMUP_EPOCH = 0
    CFG.REGION_KD_BAND_PX = 5.0
    CFG.TRAINABLE_NAME_PATTERNS = ()
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_HIDDEN = 16
    CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX = 0.025
    CFG.BOUNDARY_RESIDUAL_ADAPTER_GATE_BIAS = -2.0
    CFG.BOUNDARY_RESIDUAL_ADAPTER_DELTA_BIAS = True
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ZERO_MEAN = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_EDGE_GATE = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS = False
    CFG.BOUNDARY_POSITION_LOSS_WEIGHT = 0.0
    CFG.BOUNDARY_POSITION_COVERAGE_WEIGHT = 0.25
    CFG.BOUNDARY_POSITION_DISTANCE_CLIP = 8.0
    CFG.BOUNDARY_POSITION_WARMUP_EPOCH = 0
    CFG.TRAIN_GROUP_BALANCED_SAMPLER = False
    CFG.TRAIN_GROUP_BALANCE_MANIFEST = ""
    CFG.TRAIN_GROUP_BALANCE_KEYS = ("role", "polarity", "shape_family", "bias_px")
    CFG.TRAIN_GROUP_BALANCE_NUM_SAMPLES_MULT = 1.0
    CFG.IDENTITY_GUARD_ENABLE = False
    CFG.IDENTITY_GUARD_KD_WEIGHT = 0.0
    CFG.IDENTITY_GUARD_POSITION_WEIGHT = 0.0
    CFG.IDENTITY_GUARD_BIAS_MAX = 0.5
    CFG.IDENTITY_GUARD_BAND_PX = 10.0
    CFG.MOTION_ENABLE = False
    CFG.MOTION_SRC_DIR = ""
    CFG.MOTION_LBL_DIR = ""
    CFG.MOTION_GEOM_DIR = ""
    CFG.MOTION_META_DIR = ""
    CFG.MOTION_INCLUDE_SUBDIRS = ()
    CFG.MOTION_LOSS_WEIGHT = 0.0
    CFG.MOTION_BOUNDARY_WEIGHT = 1.0
    CFG.MOTION_RECON_WEIGHT = 0.0
    CFG.MOTION_GRAD_WEIGHT = 0.0
    CFG.MOTION_CENTER_WEIGHT = 0.0
    CFG.MOTION_CENTER_MASK_DILATE = 5
    CFG.MOTION_CENTER_INTENSITY_WEIGHT = 0.08
    CFG.MOTION_LOCAL_CENTER_WEIGHT = 0.0
    CFG.MOTION_LOCAL_CENTER_GRID = 4
    CFG.MOTION_INPUT_LOWFREQ_WEIGHT = 0.0
    CFG.MOTION_INPUT_LOWFREQ_SIGMA = 2.0
    CFG.INPUT_LOWFREQ_WEIGHT = 0.0
    CFG.INPUT_LOWFREQ_SIGMA = 2.0
    CFG.RAW_ANCHOR_OUTPUT_MODE = "none"
    CFG.RAW_ANCHOR_OUTPUT_ALPHA = 0.10
    CFG.RAW_ANCHOR_OUTPUT_SIGMA = 2.0
    CFG.RAW_ANCHOR_OUTPUT_DETAIL_GAIN = 0.35
    CFG.QUALITY_GATE_ENABLE = False
    CFG.QUALITY_GATE_HIDDEN = 8
    CFG.QUALITY_GATE_SCALE_MIN = 0.75
    CFG.QUALITY_GATE_SCALE_MAX = 1.08
    CFG.MOTION_WARMUP_EPOCH = 0
    CFG.MOTION_EVERY_N_BATCH = 2
    CFG.MOTION_BATCH_SIZE = 2
    CFG.MOTION_MAX_PAIRS = 0

    _set_lab_progress_root(trainer)
    checkpoint = _resolve_base_checkpoint(args)
    lab_checkpoint = None
    if checkpoint is not None:
        checkpoint = Path(checkpoint).resolve()
        if not checkpoint.exists():
            raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")
        lab_checkpoint = prepare_lab_checkpoint(checkpoint)
        CFG.LOAD_MODEL = True
        CFG.LOAD_RESET_OPTIMIZER = True
        CFG.LOAD_RESET_EPOCH = True
        CFG.RESUME_CHECKPOINT = str(lab_checkpoint)
        CFG.LAB_SOURCE_CHECKPOINT = str(checkpoint)
    else:
        CFG.LOAD_MODEL = False
        CFG.LOAD_RESET_OPTIMIZER = False
        CFG.LOAD_RESET_EPOCH = False
        CFG.RESUME_CHECKPOINT = ""
        CFG.LAB_SOURCE_CHECKPOINT = ""

    region_kd_weight = float(settings.get("region_kd_weight", 0.0))
    if region_kd_weight > 0.0:
        teacher_checkpoint = settings.get("region_kd_teacher_checkpoint", checkpoint)
        if teacher_checkpoint is None:
            raise RuntimeError("region-KD R61 candidates require a base checkpoint teacher")
        teacher_checkpoint = Path(teacher_checkpoint).resolve()
        if not teacher_checkpoint.exists():
            raise FileNotFoundError(f"region-KD teacher checkpoint not found: {teacher_checkpoint}")
        teacher_lab_checkpoint = (
            lab_checkpoint
            if checkpoint is not None and teacher_checkpoint == Path(checkpoint).resolve()
            else prepare_lab_checkpoint(teacher_checkpoint)
        )
        CFG.REGION_KD_ENABLE = True
        CFG.REGION_KD_TEACHER_PATH = str(teacher_lab_checkpoint)
        CFG.REGION_KD_WEIGHT = region_kd_weight
        CFG.REGION_KD_BAND_PX = float(settings.get("region_kd_band_px", 5.0))
    CFG.TRAINABLE_NAME_PATTERNS = tuple(settings.get("trainable_name_patterns", ()))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE = bool(settings.get("boundary_residual_adapter_enable", False))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_HIDDEN = int(settings.get("boundary_residual_adapter_hidden", 16))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX = float(settings.get("boundary_residual_adapter_max", 0.025))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_GATE_BIAS = float(settings.get("boundary_residual_adapter_gate_bias", -2.0))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_DELTA_BIAS = bool(settings.get("boundary_residual_adapter_delta_bias", True))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ZERO_MEAN = bool(settings.get("boundary_residual_adapter_zero_mean", False))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_EDGE_GATE = bool(settings.get("boundary_residual_adapter_edge_gate", False))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT = bool(settings.get("boundary_residual_adapter_polarity_split", False))
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS = bool(
        settings.get("boundary_residual_adapter_orientation_inputs", False)
    )
    CFG.BOUNDARY_POSITION_LOSS_WEIGHT = float(settings.get("boundary_position_loss_weight", 0.0))
    CFG.BOUNDARY_POSITION_COVERAGE_WEIGHT = float(settings.get("boundary_position_coverage_weight", 0.25))
    CFG.BOUNDARY_POSITION_DISTANCE_CLIP = float(settings.get("boundary_position_distance_clip", 8.0))
    CFG.BOUNDARY_POSITION_WARMUP_EPOCH = int(settings.get("boundary_position_warmup_epoch", 0))
    CFG.TRAIN_GROUP_BALANCED_SAMPLER = bool(settings.get("train_group_balanced_sampler", False))
    CFG.TRAIN_GROUP_BALANCE_MANIFEST = (
        str(Path(data_dir) / "manifest.json")
        if CFG.TRAIN_GROUP_BALANCED_SAMPLER
        else ""
    )
    CFG.TRAIN_GROUP_BALANCE_KEYS = tuple(
        settings.get("train_group_balance_keys", ("role", "polarity", "shape_family", "bias_px"))
    )
    CFG.TRAIN_GROUP_BALANCE_NUM_SAMPLES_MULT = float(settings.get("train_group_balance_num_samples_mult", 1.0))
    CFG.IDENTITY_GUARD_ENABLE = bool(settings.get("identity_guard_enable", False))
    CFG.IDENTITY_GUARD_KD_WEIGHT = float(settings.get("identity_guard_kd_weight", 0.0))
    CFG.IDENTITY_GUARD_POSITION_WEIGHT = float(settings.get("identity_guard_position_weight", 0.0))
    CFG.IDENTITY_GUARD_BIAS_MAX = float(settings.get("identity_guard_bias_max", 0.5))
    CFG.IDENTITY_GUARD_BAND_PX = float(settings.get("identity_guard_band_px", 10.0))
    CFG.MOTION_ENABLE = bool(settings.get("motion_enable", False))
    if CFG.MOTION_ENABLE:
        CFG.MOTION_SRC_DIR = str(Path(data_dir) / "src")
        CFG.MOTION_LBL_DIR = str(Path(data_dir) / "lbl")
        CFG.MOTION_GEOM_DIR = str(Path(data_dir) / "geom")
        CFG.MOTION_META_DIR = str(Path(data_dir) / "geom" / "meta")
    CFG.MOTION_INCLUDE_SUBDIRS = tuple(settings.get("motion_include_subdirs", ()))
    CFG.MOTION_LOSS_WEIGHT = float(settings.get("motion_loss_weight", 0.0))
    CFG.MOTION_BOUNDARY_WEIGHT = float(settings.get("motion_boundary_weight", 1.0))
    CFG.MOTION_RECON_WEIGHT = float(settings.get("motion_recon_weight", 0.0))
    CFG.MOTION_GRAD_WEIGHT = float(settings.get("motion_grad_weight", 0.0))
    CFG.MOTION_CENTER_WEIGHT = float(settings.get("motion_center_weight", 0.0))
    CFG.MOTION_CENTER_MASK_DILATE = int(settings.get("motion_center_mask_dilate", 5))
    CFG.MOTION_CENTER_INTENSITY_WEIGHT = float(settings.get("motion_center_intensity_weight", 0.08))
    CFG.MOTION_LOCAL_CENTER_WEIGHT = float(settings.get("motion_local_center_weight", 0.0))
    CFG.MOTION_LOCAL_CENTER_GRID = int(settings.get("motion_local_center_grid", 4))
    CFG.MOTION_INPUT_LOWFREQ_WEIGHT = float(settings.get("motion_input_lowfreq_weight", 0.0))
    CFG.MOTION_INPUT_LOWFREQ_SIGMA = float(settings.get("motion_input_lowfreq_sigma", 2.0))
    CFG.INPUT_LOWFREQ_WEIGHT = float(settings.get("input_lowfreq_weight", 0.0))
    CFG.INPUT_LOWFREQ_SIGMA = float(settings.get("input_lowfreq_sigma", 2.0))
    CFG.RAW_ANCHOR_OUTPUT_MODE = str(settings.get("raw_anchor_output_mode", "none"))
    CFG.RAW_ANCHOR_OUTPUT_ALPHA = float(settings.get("raw_anchor_output_alpha", 0.10))
    CFG.RAW_ANCHOR_OUTPUT_SIGMA = float(settings.get("raw_anchor_output_sigma", 2.0))
    CFG.RAW_ANCHOR_OUTPUT_DETAIL_GAIN = float(settings.get("raw_anchor_output_detail_gain", 0.35))
    CFG.QUALITY_GATE_ENABLE = bool(settings.get("quality_gate_enable", False))
    CFG.QUALITY_GATE_HIDDEN = int(settings.get("quality_gate_hidden", 8))
    CFG.QUALITY_GATE_SCALE_MIN = float(settings.get("quality_gate_scale_min", 0.75))
    CFG.QUALITY_GATE_SCALE_MAX = float(settings.get("quality_gate_scale_max", 1.08))
    CFG.MOTION_WARMUP_EPOCH = int(settings.get("motion_warmup_epoch", 0))
    CFG.MOTION_EVERY_N_BATCH = int(settings.get("motion_every_n_batch", 2))
    CFG.MOTION_BATCH_SIZE = int(settings.get("motion_batch_size", 2))
    CFG.MOTION_MAX_PAIRS = int(settings.get("motion_max_pairs", 0))
    CFG.SEQ_VAL_ENABLE = bool(settings.get("seq_val_enable", False))
    CFG.SEQ_VAL_INCLUDE_SUBDIRS = tuple(settings.get("seq_val_include_subdirs", ()))
    CFG.SEQ_VAL_MAX_PAIRS = int(settings.get("seq_val_max_pairs", getattr(CFG, "SEQ_VAL_MAX_PAIRS", 120)))
    CFG.SEQ_VAL_BATCH_SIZE = int(settings.get("seq_val_batch_size", getattr(CFG, "SEQ_VAL_BATCH_SIZE", 2)))
    CFG.GMF_VALIDATE_SOURCE = str(settings.get("gmf_validate_source", getattr(CFG, "GMF_VALIDATE_SOURCE", "val_batch")))
    CFG.GMF_VALIDATE_EVERY_N = int(settings.get("gmf_validate_every_n", getattr(CFG, "GMF_VALIDATE_EVERY_N", 2)))
    CFG.BEST_EPOCH_MIN = int(settings.get("best_epoch_min", getattr(CFG, "BEST_EPOCH_MIN", 1)))
    for obj_suffix in "JKLMNOPQRSTUV":
        setattr(CFG, f"GMF_OBJ_{obj_suffix}", float(settings.get(f"gmf_obj_{obj_suffix.lower()}", 0.0)))

    run_suffix = str(getattr(args, "run_suffix", "") or "").strip()
    if run_suffix:
        safe_suffix = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in run_suffix)
        run_suffix = f"_{safe_suffix}"
    CFG.MODEL_NAME = f"LAB_GESR_v1_v5_ST0p8_SWP_{args.candidate}{run_suffix}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = int(args.num_epoch)
    CFG.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    CFG.BEST_EPOCH_MAX = int(args.num_epoch)
    CFG.DEVICE = str(args.device)
    CFG.BATCH_SIZE = int(args.batch_size)
    CFG.VAL_BATCH_SIZE = int(args.val_batch_size)
    CFG.NUM_WORKERS = int(args.num_workers)
    CFG.CROP_SIZE = int(args.crop_size)
    CFG.SEQ_BATCH_SIZE = int(args.seq_batch_size)
    if args.max_train_batches is not None:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH = int(args.num_epoch)
    if args.lr is not None:
        CFG.LR = float(args.lr)

    if fixed_split_dir is not None:
        CFG.REPRO_MODE = True
        CFG.REPRO_FORCE_FIXED_SPLIT = False
        CFG.FIXED_SPLIT_DIR = str(Path(fixed_split_dir).resolve())
    else:
        CFG.FIXED_SPLIT_DIR = ""
    trainer.TRAIN_SRC_DIR = str(Path(data_dir) / "src")
    trainer.TRAIN_LBL_DIR = str(Path(data_dir) / "lbl")
    trainer.TRAIN_GEOM_DIR = str(Path(data_dir) / "geom")
    CFG.BOUNDARY_GEOM_DIR = str(Path(data_dir) / "geom")


def _dry_run_data_missing_summary(*, args: argparse.Namespace, profile_name: str, error: Exception) -> dict:
    checkpoint = _resolve_base_checkpoint(args)
    checkpoint = checkpoint.resolve() if checkpoint is not None else None
    return {
        "candidate": args.candidate,
        "profile": profile_name,
        "training_ready": False,
        "reason": "data package is not ready",
        "data_error": str(error),
        "data_root": str(Path(args.data_root).resolve()),
        "base_checkpoint": str(checkpoint) if checkpoint is not None else "",
        "base_checkpoint_exists": checkpoint.exists() if checkpoint is not None else False,
        "scratch_training": checkpoint is None,
        "r61_universal_boundary_training": True,
        "anti_answer_leakage_required": True,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lab R61 universal boundary generalization training launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=8)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=DEFAULT_VAL_RATIO)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--val-batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--seq-batch-size", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining
    profile_name = PROFILE_BY_CANDIDATE[str(args.candidate)]
    settings = CANDIDATE_SETTINGS[str(args.candidate)]
    try:
        data_dir, manifest = ensure_data_package(
            profile_name,
            args.data_root,
            required_roles=tuple(settings.get("required_roles", tuple(sorted(REQUIRED_R61_ROLES)))),
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        if args.dry_run:
            print(json.dumps(_dry_run_data_missing_summary(args=args, profile_name=profile_name, error=exc), indent=2, ensure_ascii=False))
            print("[R61][Lab] dry run complete; training cannot start until data is ready.")
            return 0
        raise

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    split_info = {
        "split_dir": "",
        "group_overlap_count": 0,
        "train_count": 0,
        "val_count": 0,
    }
    fixed_split_dir = None
    if not bool(settings.get("disable_external_fixed_split", False)):
        split_info = prepare_grouped_fixed_split(
            package_dir=data_dir,
            manifest=manifest,
            val_ratio=float(args.val_ratio),
            seed=1337,
        )
        fixed_split_dir = Path(split_info["split_dir"])
    configure_trainer(trainer, args, data_dir, fixed_split_dir=fixed_split_dir)
    CFG = trainer.CFG
    checkpoint = _resolve_base_checkpoint(args)
    summary = {
        "candidate": args.candidate,
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "role_counts": manifest.get("role_counts", {}),
        "polarity_counts": manifest.get("polarity_counts", {}),
        "base_checkpoint": str(Path(checkpoint).resolve()) if checkpoint is not None else "",
        "scratch_training": checkpoint is None,
        "lab_compatible_checkpoint": CFG.RESUME_CHECKPOINT,
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "device": CFG.DEVICE,
        "lr": CFG.LR,
        "use_amp": bool(getattr(CFG, "use_amp", True)),
        "train_include_subdirs": list(CFG.TRAIN_INCLUDE_SUBDIRS),
        "motion_enable": bool(getattr(CFG, "MOTION_ENABLE", False)),
        "motion_include_subdirs": list(getattr(CFG, "MOTION_INCLUDE_SUBDIRS", ())),
        "motion_grad_weight": float(getattr(CFG, "MOTION_GRAD_WEIGHT", 0.0)),
        "motion_input_lowfreq_weight": float(getattr(CFG, "MOTION_INPUT_LOWFREQ_WEIGHT", 0.0)),
        "motion_input_lowfreq_sigma": float(getattr(CFG, "MOTION_INPUT_LOWFREQ_SIGMA", 2.0)),
        "input_lowfreq_weight": float(getattr(CFG, "INPUT_LOWFREQ_WEIGHT", 0.0)),
        "input_lowfreq_sigma": float(getattr(CFG, "INPUT_LOWFREQ_SIGMA", 2.0)),
        "quality_gate_enable": bool(getattr(CFG, "QUALITY_GATE_ENABLE", False)),
        "quality_gate_scale_min": float(getattr(CFG, "QUALITY_GATE_SCALE_MIN", 0.75)),
        "quality_gate_scale_max": float(getattr(CFG, "QUALITY_GATE_SCALE_MAX", 1.08)),
        "seq_src_dir": str(getattr(CFG, "SEQ_SRC_DIR", "")),
        "seq_lbl_dir": str(getattr(CFG, "SEQ_LBL_DIR", "")),
        "seq_include_subdirs": list(getattr(CFG, "SEQ_INCLUDE_SUBDIRS", ())),
        "seq_loss_weight": float(getattr(CFG, "SEQ_LOSS_WEIGHT", 0.0)),
        "seq_grad_weight": float(getattr(CFG, "SEQ_GRAD_WEIGHT", 0.0)),
        "seq_geom_weights": {
            "center": float(getattr(CFG, "SEQ_GEOM_CENTER_WEIGHT", 0.0)),
            "radius": float(getattr(CFG, "SEQ_GEOM_RADIUS_WEIGHT", 0.0)),
            "thick": float(getattr(CFG, "SEQ_GEOM_THICK_WEIGHT", 0.0)),
            "drift": float(getattr(CFG, "SEQ_GEOM_DRIFT_WEIGHT", 0.0)),
            "step_mag": float(getattr(CFG, "SEQ_STEP_MAG_WEIGHT", 0.0)),
            "abs_center": float(getattr(CFG, "SEQ_ABS_CENTER_WEIGHT", 0.0)),
            "single_abs_center": float(getattr(CFG, "SEQ_SINGLE_ABS_CENTER_WEIGHT", 0.0)),
        },
        "fixed_split_dir": CFG.FIXED_SPLIT_DIR,
        "fixed_split_group_overlap_count": split_info["group_overlap_count"],
        "fixed_split_train_count": split_info["train_count"],
        "fixed_split_val_count": split_info["val_count"],
        "boundary_geom_enable": bool(CFG.BOUNDARY_GEOM_ENABLE),
        "r61_universal_boundary_training": True,
        "anti_answer_leakage_required": True,
        "selection_gate": "synthetic_generalization_plus_cd_plus_sequence_guard",
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("[R61][Lab] dry run complete; training was not started.")
        return 0
    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
