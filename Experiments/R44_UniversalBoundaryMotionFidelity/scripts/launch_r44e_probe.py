"""R44E targeted probe launcher for large-region and mixed-scene repair."""
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


TARGET_STATIC_STAGES = (
    "stage_38_boundary_regions",
    "stage_40_boundary_mixed",
)
TARGET_MOTION_STAGES = (
    "stage_45_motion_regions",
    "stage_47_motion_mixed",
)

BASE_CHECKPOINTS = {
    "r44b_from_r42": (
        REPO_ROOT
        / "Experiments"
        / "R44_UniversalBoundaryMotionFidelity"
        / "results"
        / "archive_retained_20260824"
        / "training_checkpoints"
        / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r42_best_20260506_201801"
        / "best_tradeoff.pth.tar"
    ),
    "r41_direct": (
        REPO_ROOT
        / "Experiments"
        / "R41_RingDistillation"
        / "selected_checkpoint"
        / "best_tradeoff.pth.tar"
    ),
    "r44b_from_r40": (
        REPO_ROOT
        / "Experiments"
        / "R44_UniversalBoundaryMotionFidelity"
        / "results"
        / "archive_retained_20260824"
        / "training_checkpoints"
        / "training_progress_GESR_v1_v5_ST0p8_SWP_r44_motion_from_r40_a045_20260506_203143"
        / "best_tradeoff.pth.tar"
    ),
}

COMMON_TARGETED_OVERRIDES = {
    "TRAIN_INCLUDE_SUBDIRS": TARGET_STATIC_STAGES,
    "MOTION_INCLUDE_SUBDIRS": TARGET_MOTION_STAGES,
    "MOTION_EVERY_N_BATCH": 1,
    "MOTION_BATCH_SIZE": 2,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 0,
    "MOTION_WARMUP_EPOCH": 0,
}

PROBES = {
    "r44e_region_mix_repair_from_r44b_r42": {
        "base_id": "r44b_from_r42",
        "note": "repair large-region/mixed-scene boundaries from the best R44B motion candidate",
        "overrides": {
            **COMMON_TARGETED_OVERRIDES,
            "LR": 1.5e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.18,
            "CENTERLINE_LOSS_WEIGHT": 0.10,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.10,
            "MOTION_LOSS_WEIGHT": 0.08,
            "MOTION_BOUNDARY_WEIGHT": 1.70,
            "MOTION_RECON_WEIGHT": 0.35,
        },
    },
    "r44e_region_prior_from_r41": {
        "base_id": "r41_direct",
        "note": "start from the strongest large-region boundary source and test if targeted motion can keep it useful",
        "overrides": {
            **COMMON_TARGETED_OVERRIDES,
            "LR": 2.0e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.12,
            "CENTERLINE_LOSS_WEIGHT": 0.08,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.08,
            "MOTION_LOSS_WEIGHT": 0.12,
            "MOTION_BOUNDARY_WEIGHT": 1.40,
            "MOTION_RECON_WEIGHT": 0.30,
        },
    },
    "r44e_mixed_prior_from_r44b_r40": {
        "base_id": "r44b_from_r40",
        "note": "start from the strongest mixed-scene boundary source and protect it with targeted data",
        "overrides": {
            **COMMON_TARGETED_OVERRIDES,
            "LR": 1.5e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.14,
            "CENTERLINE_LOSS_WEIGHT": 0.09,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.09,
            "MOTION_LOSS_WEIGHT": 0.10,
            "MOTION_BOUNDARY_WEIGHT": 1.50,
            "MOTION_RECON_WEIGHT": 0.35,
        },
    },
}


def _probe_choices() -> list[str]:
    return sorted(PROBES)


def configure_probe(trainer, args: argparse.Namespace, static_dir: Path, motion_dir: Path) -> dict:
    probe = PROBES[args.probe]
    base_checkpoint = Path(args.base_checkpoint or BASE_CHECKPOINTS[probe["base_id"]]).resolve()
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
    cfg.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.probe}"
    trainer.MODEL_NAME_BASE = cfg.MODEL_NAME

    return {
        "probe": args.probe,
        "note": probe["note"],
        "base_id": probe["base_id"],
        "base_checkpoint": str(base_checkpoint),
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
    parser = argparse.ArgumentParser(description="Run R44E targeted large-region/mixed-scene probe training.")
    parser.add_argument("--probe", required=True, choices=_probe_choices())
    parser.add_argument("--num-epoch", type=int, default=14)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=60)
    parser.add_argument("--val-ratio", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--val-batch-size", type=int, default=4)
    parser.add_argument("--base-checkpoint", type=Path, default=None)
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

    summary = configure_probe(trainer, args, static_dir, motion_dir)
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
        print("[R44E] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
