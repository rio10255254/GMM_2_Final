"""R63 — causal boundary/motion ablation launcher.

The PSF and optical settings are deliberately fixed in every condition.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = EXPERIMENT_ROOT.parents[1]
DEFAULT_PACKAGE_ROOT = (
    REPO_ROOT
    / "Thesis_MOSR_Evidence"
    / "LabSystem_MOSR"
    / "Model_Packages"
    / "V42_SoftLabelSNR_FullStandalone_20260709"
)
DEFAULT_OUTPUT_ROOT = EXPERIMENT_ROOT / "results" / "training_runs"
BASE_TRAINABLE = ("quality_gate", "boundary_adapter", "p1", "out")
ARCH_TRAINABLE = BASE_TRAINABLE + ("u1.conv", "u2.conv", "u3.conv")


SHAPE_GEOMETRY_OFF: dict[str, Any] = {
    "BOUNDARY_LOSS_WEIGHT": 0.0,
    "CENTERLINE_LOSS_WEIGHT": 0.0,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.0,
}

GLOBAL_POSITION_OFF: dict[str, Any] = {
    "BOUNDARY_POSITION_LOSS_WEIGHT": 0.0,
}

IDENTITY_GUARD_OFF: dict[str, Any] = {
    "IDENTITY_GUARD_ENABLE": False,
    "IDENTITY_GUARD_KD_WEIGHT": 0.0,
    "IDENTITY_GUARD_POSITION_WEIGHT": 0.0,
}

REGION_BOUNDARY_TEACHER_OFF: dict[str, Any] = {
    "REGION_KD_ENABLE": False,
    "REGION_KD_WEIGHT": 0.0,
}

GEOMETRY_OFF: dict[str, Any] = {
    "BOUNDARY_GEOM_ENABLE": False,
    **SHAPE_GEOMETRY_OFF,
    **GLOBAL_POSITION_OFF,
    **IDENTITY_GUARD_OFF,
    **REGION_BOUNDARY_TEACHER_OFF,
}

SEQUENCE_OFF: dict[str, Any] = {
    "SEQ_ENABLE": False,
    "SEQ_GEOM_ENABLE": False,
    "SEQ_LOSS_WEIGHT": 0.0,
    "SEQ_GRAD_WEIGHT": 0.0,
    "SEQ_GEOM_CENTER_WEIGHT": 0.0,
    "SEQ_GEOM_RADIUS_WEIGHT": 0.0,
    "SEQ_GEOM_THICK_WEIGHT": 0.0,
    "SEQ_GEOM_DRIFT_WEIGHT": 0.0,
    "SEQ_STEP_MAG_WEIGHT": 0.0,
    "SEQ_ABS_CENTER_WEIGHT": 0.0,
    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.0,
}

KNOWN_SHIFT_MOTION_OFF: dict[str, Any] = {
    "MOTION_ENABLE": False,
    "MOTION_LOSS_WEIGHT": 0.0,
    "MOTION_RECON_WEIGHT": 0.0,
    "MOTION_GRAD_WEIGHT": 0.0,
    "MOTION_BOUNDARY_WEIGHT": 0.0,
    "MOTION_CENTER_WEIGHT": 0.0,
    "MOTION_LOCAL_CENTER_WEIGHT": 0.0,
    "MOTION_INPUT_LOWFREQ_WEIGHT": 0.0,
}

SHIFT_EQUIVARIANCE_OFF: dict[str, Any] = {
    "ENABLE_SHIFT_EQ": False,
    "W_EQ_GEOM": 0.0,
}

MOTION_OFF: dict[str, Any] = {
    **SEQUENCE_OFF,
    **KNOWN_SHIFT_MOTION_OFF,
    **SHIFT_EQUIVARIANCE_OFF,
}

VARIANTS: dict[str, dict[str, Any]] = {
    "full_control": {},
    "no_geometry_anchor": dict(GEOMETRY_OFF),
    "no_motion_consistency": dict(MOTION_OFF),
    "no_geometry_no_motion": {**GEOMETRY_OFF, **MOTION_OFF},
    "no_shape_geometry": dict(SHAPE_GEOMETRY_OFF),
    "no_global_boundary_position": dict(GLOBAL_POSITION_OFF),
    "no_identity_boundary_guard": dict(IDENTITY_GUARD_OFF),
    "no_region_boundary_teacher": dict(REGION_BOUNDARY_TEACHER_OFF),
    "no_sequence_consistency": dict(SEQUENCE_OFF),
    "no_known_shift_motion": dict(KNOWN_SHIFT_MOTION_OFF),
    "no_shift_equivariance": dict(SHIFT_EQUIVARIANCE_OFF),
    "no_boundary_residual_adapter": {"BOUNDARY_RESIDUAL_ADAPTER_ENABLE": False},
    "no_raw_position_anchor": {"RAW_ANCHOR_OUTPUT_MODE": "none"},
    "no_quality_gate": {"QUALITY_GATE_ENABLE": False},
    "shift_safe_matched": {"TRAINABLE_NAME_PATTERNS": ARCH_TRAINABLE},
    "standard_upsample_matched": {
        "TRAINABLE_NAME_PATTERNS": ARCH_TRAINABLE,
        "R63_STANDARD_UPSAMPLE": True,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True, choices=tuple(VARIANTS))
    parser.add_argument("--seed", type=int, default=1261200)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--max-train-batches", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--val-batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--seq-batch-size", type=int, default=2)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--val-every", type=int, default=4)
    parser.add_argument("--seq-val-pairs", type=int, default=256)
    parser.add_argument("--checkpoint-every", type=int, default=4)
    parser.add_argument("--package-root", type=Path, default=DEFAULT_PACKAGE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--resume-checkpoint", type=Path, default=None)
    parser.add_argument(
        "--continue-training",
        action="store_true",
        help="Continue epoch and optimizer state from --resume-checkpoint.",
    )
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Optional forensic mode; the matched suite defaults to the original full-training CUDA settings.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _trainer_args(args: argparse.Namespace) -> argparse.Namespace:
    package_root = args.package_root.resolve()
    output_root = args.output_root.resolve()
    return argparse.Namespace(
        data_dir=str(package_root / "training_data"),
        output_dir=str(output_root),
        base_checkpoint=str(package_root / "weights" / "base_v41_standalone_best_tradeoff.pth.tar"),
        scratch=False,
        run_name=f"r63_{args.variant}_s{args.seed}",
        batch_size=int(args.batch_size),
        val_batch_size=int(args.val_batch_size),
        num_workers=int(args.num_workers),
        crop_size=256,
        seq_batch_size=int(args.seq_batch_size),
        max_train_batches=int(args.max_train_batches),
        dry_run=False,
        resume_checkpoint=str(args.resume_checkpoint.resolve()) if args.resume_checkpoint else None,
        reset_epoch=not bool(args.continue_training),
        reset_optimizer=not bool(args.continue_training),
        device=str(args.device),
        progress_root=str(output_root),
        simpletest_max_epoch=int(args.epochs),
        num_epoch=int(args.epochs),
        attrib_window=None,
        attrib_every=None,
        seed_deterministic=bool(args.deterministic),
        force_fast_eval=True,
    )


def _patch_standard_upsample(package_root: Path) -> None:
    import model_v42

    def forward_without_antialias(self, x):
        return self.conv(self.up(x))

    model_v42.ShiftSafeUpsample.forward = forward_without_antialias


def _json_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def configure(args: argparse.Namespace):
    package_root = args.package_root.resolve()
    if not package_root.is_dir():
        raise FileNotFoundError(f"Standalone package not found: {package_root}")
    sys.path.insert(0, str(package_root))
    import train_v42 as trainer

    trainer_args = _trainer_args(args)
    setup = trainer._apply_v42_standalone_package(trainer_args)
    cfg = trainer.CFG
    if args.continue_training:
        if args.resume_checkpoint is None or not args.resume_checkpoint.is_file():
            raise FileNotFoundError("--continue-training requires an existing --resume-checkpoint")
        cfg.RESUME_CHECKPOINT = str(args.resume_checkpoint.resolve())
        cfg.LOAD_RESET_EPOCH = False
        cfg.LOAD_RESET_OPTIMIZER = False
        setup["continued_from"] = str(args.resume_checkpoint.resolve())
        source_run = args.resume_checkpoint.resolve().parent
        monitor_reference_path = source_run / "monitor_ref.json"
        if not monitor_reference_path.is_file():
            raise FileNotFoundError(
                f"Continuation requires the source-run monitor reference: {monitor_reference_path}"
            )
        fixed_monitor_reference = json.loads(monitor_reference_path.read_text(encoding="utf-8"))
        required_reference_keys = {"edge_width_ref", "hf_proxy_ref", "cb_ref"}
        if not required_reference_keys.issubset(fixed_monitor_reference):
            raise RuntimeError(f"Incomplete monitor reference: {monitor_reference_path}")

        def reuse_source_monitor_reference(_model, _monitor_src):
            payload = dict(fixed_monitor_reference)
            payload["reused_from"] = str(monitor_reference_path)
            destination = Path(trainer.PROGRESS_DIR) / "monitor_ref.json"
            destination.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"[R63] Reusing source-run monitor reference: {monitor_reference_path}")
            return payload

        trainer.load_or_create_monitor_ref = reuse_source_monitor_reference
        setup["monitor_reference_reused_from"] = str(monitor_reference_path)
    else:
        cfg.LOAD_RESET_EPOCH = True
        cfg.LOAD_RESET_OPTIMIZER = True

    overrides = dict(VARIANTS[args.variant])
    standard_upsample = bool(overrides.pop("R63_STANDARD_UPSAMPLE", False))
    for key, value in overrides.items():
        setattr(cfg, key, value)
    if standard_upsample:
        _patch_standard_upsample(package_root)

    cfg.MODEL_NAME = f"R63_MOSR_{args.variant}_s{args.seed}"
    trainer.MODEL_NAME_BASE = cfg.MODEL_NAME
    trainer.RUN_TAG_BASE = cfg.MODEL_NAME
    trainer.RUN_TAG = cfg.MODEL_NAME
    cfg.NUM_EPOCH = int(args.epochs)
    cfg.SIMPLETEST_MAX_EPOCH = int(args.epochs)
    cfg.BEST_EPOCH_MAX = int(args.epochs)
    cfg.SEED_ACTIVE = int(args.seed)
    cfg.REPRO_SEED = int(args.seed)
    cfg.SEED_DETERMINISTIC = bool(args.deterministic)
    cfg.REPRO_MODE = bool(args.deterministic)
    cfg.REPRO_DETERMINISTIC = bool(args.deterministic)
    cfg.REPRO_FORCE_FIXED_SPLIT = True
    cfg.REPRO_DISABLE_TF32 = bool(args.deterministic)
    cfg.REPRO_NUM_WORKERS = int(args.num_workers)
    cfg.use_amp = False

    cadence = max(1, int(args.val_every))
    cfg.FAST_IO_MODE = True
    cfg.FAST_DISABLE_PLOTS = True
    cfg.TERMINAL_MINIMAL = True
    cfg.FAST_VAL_EVERY_EPOCH = cadence
    cfg.EARLY_FAST_VAL_EVERY_EPOCH = cadence
    cfg.GMF_VALIDATE_EVERY_N = cadence
    cfg.SEQ_VAL_MAX_PAIRS = max(1, int(args.seq_val_pairs))
    cfg.SAVE_CKPT_EVERY_EPOCH = True
    cfg.SAVE_CKPT_EVERY_N_EPOCH = max(1, int(args.checkpoint_every))

    # Explicit invariant: optics stay fixed in all R63 variants.
    cfg.PHYS_FORWARD_ENABLE = False
    cfg.W_PHYS_MAX = 0.0
    cfg.WEAK_PSF_BETA_INIT = 0.0
    cfg.WEAK_PSF_BETA_SCALE_MAX = 0.0
    cfg.WEAK_PSF_LR_MULT = 0.0

    snapshot_keys = (
        "MODEL_NAME",
        "NUM_EPOCH",
        "MAX_TRAIN_BATCHES_PER_EPOCH",
        "FIXED_SPLIT_DIR",
        "PSF_FITTED_PATH",
        "PHYS_FORWARD_ENABLE",
        "W_PHYS_MAX",
        "WEAK_PSF_BETA_SCALE_MAX",
        "TRAINABLE_NAME_PATTERNS",
        "BOUNDARY_GEOM_ENABLE",
        "BOUNDARY_LOSS_WEIGHT",
        "CENTERLINE_LOSS_WEIGHT",
        "DISTANCE_EDGE_LOSS_WEIGHT",
        "BOUNDARY_POSITION_LOSS_WEIGHT",
        "IDENTITY_GUARD_ENABLE",
        "IDENTITY_GUARD_KD_WEIGHT",
        "IDENTITY_GUARD_POSITION_WEIGHT",
        "REGION_KD_ENABLE",
        "REGION_KD_WEIGHT",
        "REGION_KD_BAND_PX",
        "SEQ_ENABLE",
        "SEQ_GEOM_ENABLE",
        "SEQ_LOSS_WEIGHT",
        "SEQ_GRAD_WEIGHT",
        "SEQ_GEOM_CENTER_WEIGHT",
        "SEQ_GEOM_RADIUS_WEIGHT",
        "SEQ_GEOM_THICK_WEIGHT",
        "SEQ_GEOM_DRIFT_WEIGHT",
        "SEQ_STEP_MAG_WEIGHT",
        "SEQ_ABS_CENTER_WEIGHT",
        "SEQ_SINGLE_ABS_CENTER_WEIGHT",
        "MOTION_ENABLE",
        "MOTION_LOSS_WEIGHT",
        "MOTION_RECON_WEIGHT",
        "MOTION_GRAD_WEIGHT",
        "MOTION_BOUNDARY_WEIGHT",
        "MOTION_CENTER_WEIGHT",
        "MOTION_LOCAL_CENTER_WEIGHT",
        "MOTION_INPUT_LOWFREQ_WEIGHT",
        "ENABLE_SHIFT_EQ",
        "W_EQ_GEOM",
        "RAW_ANCHOR_OUTPUT_MODE",
        "QUALITY_GATE_ENABLE",
        "BOUNDARY_RESIDUAL_ADAPTER_ENABLE",
    )
    snapshot = {
        "round": "R63",
        "variant": args.variant,
        "seed": int(args.seed),
        "standard_upsample": standard_upsample,
        "package_root": str(package_root),
        "output_root": str(args.output_root.resolve()),
        "continued_from": str(args.resume_checkpoint.resolve()) if args.resume_checkpoint else "",
        "setup": setup,
        "config": {key: _json_value(getattr(cfg, key)) for key in snapshot_keys},
        "environment": {
            "python": sys.version,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "deterministic": bool(args.deterministic),
        },
    }
    return trainer, trainer_args, snapshot


def main() -> None:
    args = parse_args()
    trainer, trainer_args, snapshot = configure(args)
    snapshot_dir = EXPERIMENT_ROOT / "results" / "config_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{args.variant}_seed{args.seed}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"[R63] config snapshot: {snapshot_path}")
    if args.dry_run:
        print("[R63] dry run complete")
        return
    trainer.run_one_seed(int(args.seed), args=trainer_args)


if __name__ == "__main__":
    main()
