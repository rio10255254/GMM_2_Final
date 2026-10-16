"""Standalone V41 long-training launcher for thesis use.

This launcher keeps the final V41 training story clean:
- one named candidate,
- one final training package,
- one universal pretrained starting point,
- one explicit long-training configuration.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[5]
R61_SCRIPT_DIR = LAB_ROOT / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts"

sys.path.insert(0, str(R61_SCRIPT_DIR))

import launch_r61 as r61  # noqa: E402


STANDALONE_CANDIDATE = "v41_standalone_long"
STANDALONE_PROFILE = "r62_target_sample_boost_v13_measurement_view_safe_teacher"
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r62_target_sample_boost" / "hs100mg_basler"
DEFAULT_BASE_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r61_motion_texture_stepguard_v16_dualgate_boundary_focus_full_e8_20260623_20260623_200020"
    / "weights"
    / "best_tradeoff.pth.tar"
)

STANDALONE_INCLUDE_SUBDIRS = (
    "stage_34_r61_legacy_shape",
    "stage_35_r61_sequence_guard",
    "stage_36_r61_sem_truth_anchor",
    "stage_37_r61_universal_synthetic",
    "stage_38_r61_motion_synthetic",
    "stage_39_r61_motion_texture_synthetic",
    "stage_40_r61_step_guard_motion_texture_synthetic",
    "stage_40_r62_target_real_pseudo",
    "stage_40_r62_real_motion_pair",
    "stage_40_r62_target_selfshift_motion_pair",
    "stage_40_r62_gmf_roi_selfshift_motion_pair",
    "stage_40_r62_lowmag_dualroi_selfshift_pair",
    "stage_40_r62_multimag_raw_motion_guard_pair",
    "stage_40_r62_stability_shape_teacher_pair",
)

STANDALONE_MOTION_SUBDIRS = (
    "stage_38_r61_motion_synthetic",
    "stage_39_r61_motion_texture_synthetic",
    "stage_40_r61_step_guard_motion_texture_synthetic",
    "stage_40_r62_real_motion_pair",
    "stage_40_r62_target_selfshift_motion_pair",
    "stage_40_r62_gmf_roi_selfshift_motion_pair",
    "stage_40_r62_lowmag_dualroi_selfshift_pair",
    "stage_40_r62_multimag_raw_motion_guard_pair",
    "stage_40_r62_stability_shape_teacher_pair",
)

STANDALONE_SEQ_VAL_SUBDIRS = (
    "stage_40_r62_real_motion_pair",
    "stage_40_r62_target_selfshift_motion_pair",
    "stage_40_r62_gmf_roi_selfshift_motion_pair",
    "stage_40_r62_lowmag_dualroi_selfshift_pair",
    "stage_40_r62_multimag_raw_motion_guard_pair",
    "stage_40_r62_stability_shape_teacher_pair",
)

STANDALONE_REQUIRED_ROLES = (
    "legacy_shape",
    "sequence_guard",
    "sem_truth_anchor",
    "universal_synthetic",
    "motion_synthetic",
    "motion_texture_synthetic",
    "step_guard_motion_texture_synthetic",
    "target_real_pseudo_boundary",
    "target_real_motion_pair",
    "target_real_selfshift_motion_pair",
    "target_real_gmf_roi_selfshift_motion_pair",
    "target_real_lowmag_gmf_dot_r61_motion_pair",
    "target_real_lowmag_square_raw_shape_pair",
    "target_real_multimag_raw_motion_guard_pair",
    "target_real_stability_shape_teacher_pair",
)

STANDALONE_SETTINGS: dict[str, Any] = {
    "profile": STANDALONE_PROFILE,
    "base_checkpoint": DEFAULT_BASE_CHECKPOINT,
    "region_kd_teacher_checkpoint": DEFAULT_BASE_CHECKPOINT,
    "lr": 1.2e-7,
    "boundary": 0.004,
    "centerline": 0.002,
    "distance": 0.002,
    "seq_loss_weight": 0.24,
    "seq_grad_weight": 0.06,
    "seq_use_train_dirs": True,
    "seq_include_subdirs": STANDALONE_MOTION_SUBDIRS,
    "seq_geom_method": "soft_band_stepmix_sharp",
    "seq_geom_center_weight": 0.034,
    "seq_geom_radius_weight": 0.012,
    "seq_geom_thick_weight": 0.004,
    "seq_geom_drift_weight": 0.006,
    "seq_step_mag_weight": 0.04,
    "seq_abs_center_weight": 0.024,
    "seq_single_abs_center_weight": 0.018,
    "seq_every_n_batch": 1,
    "seq_max_pairs": 2400,
    "seq_min_delta_threshold": 0.0,
    "seq_warmup_epoch": 0,
    "region_kd_weight": 36.0,
    "region_kd_band_px": 12.0,
    "trainable_name_patterns": ("boundary_adapter", "p1", "out"),
    "boundary_residual_adapter_enable": True,
    "boundary_residual_adapter_hidden": 16,
    "boundary_residual_adapter_max": 0.006,
    "boundary_residual_adapter_gate_bias": -2.0,
    "boundary_residual_adapter_orientation_inputs": True,
    "boundary_position_loss_weight": 0.0008,
    "boundary_position_coverage_weight": 0.04,
    "boundary_position_distance_clip": 8.0,
    "train_include_subdirs": STANDALONE_INCLUDE_SUBDIRS,
    "required_roles": STANDALONE_REQUIRED_ROLES,
    "train_group_balanced_sampler": True,
    "train_group_balance_keys": ("role", "target_dataset", "magnification_hint", "shape_family"),
    "train_group_balance_num_samples_mult": 1.25,
    "identity_guard_enable": True,
    "identity_guard_kd_weight": 52.0,
    "identity_guard_position_weight": 0.018,
    "identity_guard_bias_max": 0.5,
    "identity_guard_band_px": 10.0,
    "motion_enable": True,
    "motion_include_subdirs": STANDALONE_MOTION_SUBDIRS,
    "motion_loss_weight": 0.42,
    "motion_recon_weight": 0.0,
    "motion_grad_weight": 0.24,
    "motion_boundary_weight": 7.0,
    "motion_every_n_batch": 1,
    "motion_batch_size": 2,
    "motion_max_pairs": 3600,
    "seq_val_enable": True,
    "seq_val_include_subdirs": STANDALONE_SEQ_VAL_SUBDIRS,
    "seq_val_max_pairs": 1000,
    "seq_val_batch_size": 2,
    "gmf_validate_source": "seq_val",
    "gmf_validate_every_n": 1,
    "best_epoch_min": 2,
    "gmf_obj_j": 18.0,
    "gmf_obj_k": 5.0,
    "gmf_obj_l": 14.0,
    "gmf_obj_m": 7.0,
    "gmf_obj_n": 2.0,
    "gmf_obj_o": 8.0,
    "gmf_obj_p": 3.0,
    "gmf_obj_q": 10.0,
    "gmf_obj_r": 4.0,
    "gmf_obj_u": 3.0,
    "gmf_obj_v": 3.0,
    "use_amp": False,
    "input_lowfreq_weight": 24.0,
    "input_lowfreq_sigma": 2.0,
    "motion_input_lowfreq_weight": 4.0,
    "motion_input_lowfreq_sigma": 2.0,
    "raw_anchor_output_mode": "detail",
    "raw_anchor_output_alpha": 0.1,
    "raw_anchor_output_sigma": 2.0,
    "raw_anchor_output_detail_gain": 0.35,
    "disable_external_fixed_split": False,
    "external_selection_gate": "v41_standalone_full_final_gate",
}

PROFILE_BY_CANDIDATE = {STANDALONE_CANDIDATE: STANDALONE_PROFILE}
REQUIRED_ROLES_BY_CANDIDATE = {STANDALONE_CANDIDATE: STANDALONE_REQUIRED_ROLES}


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value).__name__)


def patch_r61_registry() -> None:
    """Expose only the standalone candidate to the shared R61 launcher."""
    r61.DEFAULT_DATA_ROOT = DEFAULT_DATA_ROOT
    r61.CANDIDATE_SETTINGS.clear()
    r61.CANDIDATE_SETTINGS[STANDALONE_CANDIDATE] = dict(STANDALONE_SETTINGS)
    r61.PROFILE_BY_CANDIDATE.clear()
    r61.PROFILE_BY_CANDIDATE.update(PROFILE_BY_CANDIDATE)
    r61.REQUIRED_ROLES_BY_CANDIDATE.clear()
    r61.REQUIRED_ROLES_BY_CANDIDATE.update(REQUIRED_ROLES_BY_CANDIDATE)


def profile_dir(data_root: Path = DEFAULT_DATA_ROOT) -> Path:
    return Path(data_root) / STANDALONE_PROFILE


def load_manifest(data_root: Path = DEFAULT_DATA_ROOT) -> dict[str, Any]:
    manifest_path = profile_dir(data_root) / "manifest.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_standalone_summary(data_root: Path = DEFAULT_DATA_ROOT) -> dict[str, Any]:
    manifest = load_manifest(data_root)
    role_counts = manifest.get("role_counts", {})
    missing_roles = sorted(set(STANDALONE_REQUIRED_ROLES) - set(role_counts))
    return {
        "training_story": "standalone_full_final_training",
        "candidate": STANDALONE_CANDIDATE,
        "profile": STANDALONE_PROFILE,
        "data_root": str(Path(data_root)),
        "profile_dir": str(profile_dir(data_root)),
        "base_checkpoint": str(DEFAULT_BASE_CHECKPOINT),
        "uses_version_chain_checkpoint": False,
        "total_pairs": int(manifest.get("total_pairs", 0)),
        "required_role_count": len(STANDALONE_REQUIRED_ROLES),
        "missing_required_roles": missing_roles,
        "train_include_subdirs": list(STANDALONE_INCLUDE_SUBDIRS),
        "motion_include_subdirs": list(STANDALONE_MOTION_SUBDIRS),
        "default_num_epoch": 16,
        "default_batch_size": 4,
        "default_num_workers": 2,
        "default_lr": STANDALONE_SETTINGS["lr"],
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V41 standalone long-training launcher")
    parser.add_argument("--candidate", default=STANDALONE_CANDIDATE, choices=[STANDALONE_CANDIDATE])
    parser.add_argument("--num-epoch", type=int, default=16)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--run-suffix", default="standalone_full_e16_20260708")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=0.12)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--val-batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--seq-batch-size", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--print-standalone-summary",
        action="store_true",
        help="Print the thesis-facing standalone configuration summary and exit.",
    )
    return parser


def _forward_arg(argv: list[str], flag: str, value: Any) -> None:
    argv.extend([flag, str(value)])


def build_forward_argv(args: argparse.Namespace, remaining: list[str]) -> list[str]:
    forwarded: list[str] = []
    _forward_arg(forwarded, "--candidate", STANDALONE_CANDIDATE)
    _forward_arg(forwarded, "--data-root", Path(args.data_root))
    _forward_arg(forwarded, "--num-epoch", int(args.num_epoch))
    _forward_arg(forwarded, "--device", args.device)
    _forward_arg(forwarded, "--run-suffix", args.run_suffix)
    _forward_arg(forwarded, "--val-ratio", float(args.val_ratio))
    _forward_arg(forwarded, "--batch-size", int(args.batch_size))
    _forward_arg(forwarded, "--val-batch-size", int(args.val_batch_size))
    _forward_arg(forwarded, "--num-workers", int(args.num_workers))
    _forward_arg(forwarded, "--crop-size", int(args.crop_size))
    _forward_arg(forwarded, "--seq-batch-size", int(args.seq_batch_size))
    if args.base_checkpoint is not None:
        _forward_arg(forwarded, "--base-checkpoint", Path(args.base_checkpoint))
    if args.max_train_batches is not None:
        _forward_arg(forwarded, "--max-train-batches", int(args.max_train_batches))
    if args.lr is not None:
        _forward_arg(forwarded, "--lr", float(args.lr))
    if args.scratch:
        forwarded.append("--scratch")
    if args.dry_run:
        forwarded.append("--dry-run")
    forwarded.extend(remaining)
    return forwarded


def main(argv: list[str] | None = None) -> int:
    patch_r61_registry()
    parser = build_arg_parser()
    args, remaining = parser.parse_known_args(argv)
    if args.print_standalone_summary:
        print(json.dumps(build_standalone_summary(args.data_root), indent=2, ensure_ascii=False, default=_json_default))
        return 0
    summary = build_standalone_summary(args.data_root)
    if summary["missing_required_roles"]:
        raise RuntimeError(f"standalone package missing roles: {summary['missing_required_roles']}")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=_json_default))
    return r61.main(build_forward_argv(args, remaining))


if __name__ == "__main__":
    raise SystemExit(main())
