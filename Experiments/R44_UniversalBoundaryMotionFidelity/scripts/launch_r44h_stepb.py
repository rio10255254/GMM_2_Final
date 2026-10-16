"""R44H Step B single-teacher region-masked KD launcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Model"))

from launch_r44 import (  # noqa: E402
    DEFAULT_DATA_ROOT,
    R42_DATA_ROOT,
    configure_trainer,
    ensure_data_package,
    ensure_motion_package,
)


STUDENT_START_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R44_UniversalBoundaryMotionFidelity"
    / "results"
    / "archive_retained_20260824"
    / "training_checkpoints"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r42_best_20260506_201801"
    / "best_tradeoff.pth.tar"
)
LARGE_REGION_TEACHER_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R44_UniversalBoundaryMotionFidelity"
    / "results"
    / "archive_retained_20260824"
    / "training_checkpoints"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_combo_20260506_204231"
    / "best_tradeoff.pth.tar"
)

TARGET_STATIC_STAGES = ("stage_38_boundary_regions",)
TARGET_MOTION_STAGES = ("stage_45_motion_regions",)

PROBES = {
    "r44h_stepb_region_kd_main": {
        "teacher_id": "r44b_from_combo",
        "note": "single-teacher region-masked KD on large-region boundary bands, starting from R44B from R42",
        "overrides": {
            "KD_ENABLE": False,
            "REGION_KD_ENABLE": True,
            "REGION_KD_WEIGHT": 0.05,
            "REGION_KD_WARMUP_EPOCH": 0,
            "REGION_KD_BAND_PX": 5.0,
            "TRAIN_INCLUDE_SUBDIRS": TARGET_STATIC_STAGES,
            "MOTION_INCLUDE_SUBDIRS": TARGET_MOTION_STAGES,
            "LR": 1.2e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.10,
            "CENTERLINE_LOSS_WEIGHT": 0.06,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.06,
            "BOUNDARY_LOSS_WARMUP_EPOCH": 0,
            "MOTION_LOSS_WEIGHT": 0.10,
            "MOTION_BOUNDARY_WEIGHT": 1.60,
            "MOTION_RECON_WEIGHT": 0.25,
            "MOTION_WARMUP_EPOCH": 0,
            "MOTION_EVERY_N_BATCH": 1,
            "MOTION_BATCH_SIZE": 2,
        },
    },
}


def _probe_choices() -> list[str]:
    return sorted(PROBES)


def configure_stepb(trainer, args: argparse.Namespace, static_dir: Path, motion_dir: Path) -> dict:
    probe = PROBES[args.candidate]
    base_checkpoint = Path(args.base_checkpoint or STUDENT_START_CHECKPOINT).resolve()
    teacher_checkpoint = Path(args.teacher_checkpoint or LARGE_REGION_TEACHER_CHECKPOINT).resolve()
    if not base_checkpoint.exists():
        raise FileNotFoundError(f"student checkpoint not found: {base_checkpoint}")
    if not teacher_checkpoint.exists():
        raise FileNotFoundError(f"teacher checkpoint not found: {teacher_checkpoint}")

    base_args = SimpleNamespace(
        candidate="r44_motion_from_r42_best",
        base_checkpoint=base_checkpoint,
        num_epoch=args.num_epoch,
        max_train_batches=args.max_train_batches,
        val_ratio=args.val_ratio,
        batch_size=args.batch_size,
        val_batch_size=args.val_batch_size,
        device=args.device,
    )
    configure_trainer(trainer, base_args, static_dir, motion_dir)

    cfg = trainer.CFG
    for key, value in probe["overrides"].items():
        setattr(cfg, key, value)
    cfg.REGION_KD_TEACHER_PATH = str(teacher_checkpoint)
    cfg.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = cfg.MODEL_NAME

    return {
        "candidate": args.candidate,
        "note": probe["note"],
        "student_id": "r44b_from_r42",
        "teacher_id": probe["teacher_id"],
        "base_checkpoint": str(base_checkpoint),
        "teacher_checkpoint": str(teacher_checkpoint),
        "model_name": cfg.MODEL_NAME,
        "num_epoch": cfg.NUM_EPOCH,
        "max_train_batches": cfg.MAX_TRAIN_BATCHES_PER_EPOCH,
        "device": cfg.DEVICE,
        "lr": cfg.LR,
        "train_include_subdirs": list(cfg.TRAIN_INCLUDE_SUBDIRS),
        "boundary_weights": {
            "boundary": cfg.BOUNDARY_LOSS_WEIGHT,
            "centerline": cfg.CENTERLINE_LOSS_WEIGHT,
            "distance_edge": cfg.DISTANCE_EDGE_LOSS_WEIGHT,
        },
        "region_kd": {
            "enabled": cfg.REGION_KD_ENABLE,
            "teacher_path": cfg.REGION_KD_TEACHER_PATH,
            "weight": cfg.REGION_KD_WEIGHT,
            "band_px": cfg.REGION_KD_BAND_PX,
            "warmup_epoch": cfg.REGION_KD_WARMUP_EPOCH,
        },
        "motion": {
            "enabled": cfg.MOTION_ENABLE,
            "loss_weight": cfg.MOTION_LOSS_WEIGHT,
            "boundary_weight": cfg.MOTION_BOUNDARY_WEIGHT,
            "recon_weight": cfg.MOTION_RECON_WEIGHT,
            "every_n_batch": cfg.MOTION_EVERY_N_BATCH,
            "batch_size": cfg.MOTION_BATCH_SIZE,
            "include_subdirs": list(cfg.MOTION_INCLUDE_SUBDIRS),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run R44H Step B single-teacher region-masked KD.")
    parser.add_argument("--candidate", default="r44h_stepb_region_kd_main", choices=_probe_choices())
    parser.add_argument("--num-epoch", type=int, default=12)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=50)
    parser.add_argument("--val-ratio", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--val-batch-size", type=int, default=4)
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--teacher-checkpoint", type=Path, default=None)
    parser.add_argument("--static-data-root", type=Path, default=R42_DATA_ROOT)
    parser.add_argument("--motion-data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

    static_dir, static_manifest = ensure_data_package(
        "r42_boundary_research_train",
        args.static_data_root,
        build_data=args.build_data,
        force_data=args.force_data,
        link_mode=args.link_mode,
    )
    motion_dir, motion_manifest = ensure_motion_package(
        "r44_motion_research_train",
        args.motion_data_root,
        build_data=args.build_data,
        force_data=args.force_data,
        link_mode=args.link_mode,
    )

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    summary = configure_stepb(trainer, args, static_dir, motion_dir)
    summary.update(
        {
            "static_dir": str(static_dir),
            "static_total_pairs": static_manifest["total_pairs"],
            "motion_dir": str(motion_dir),
            "motion_total_frames": motion_manifest["total_frames"],
        }
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R44H] Step B dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
