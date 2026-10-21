"""R44C probe launcher for family-balanced boundary-motion tests."""
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
    BASE_CHECKPOINT_BY_CANDIDATE,
    DEFAULT_DATA_ROOT,
    R42_DATA_ROOT,
    configure_trainer,
    ensure_data_package,
    ensure_motion_package,
)
from r44_motion_data import MOTION_STAGES  # noqa: E402


R42_BASE_CANDIDATE = "r44_motion_from_r42_best"
MOTION_NO_REGION_MIXED = tuple(
    stage
    for stage in MOTION_STAGES
    if stage not in {"stage_45_motion_regions", "stage_47_motion_mixed"}
)

PROBES = {
    "r44c_low_motion_static_guard": {
        "note": "lower motion pressure and stronger static boundary guard",
        "overrides": {
            "LR": 3.0e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.10,
            "CENTERLINE_LOSS_WEIGHT": 0.07,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.07,
            "MOTION_LOSS_WEIGHT": 0.10,
            "MOTION_BOUNDARY_WEIGHT": 1.20,
            "MOTION_RECON_WEIGHT": 0.25,
            "MOTION_EVERY_N_BATCH": 3,
            "MOTION_INCLUDE_SUBDIRS": MOTION_STAGES,
        },
    },
    "r44c_family_holdout_motion": {
        "note": "exclude large regions and mixed scenes from motion loss, keep them as static boundary anchors",
        "overrides": {
            "LR": 3.0e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.10,
            "CENTERLINE_LOSS_WEIGHT": 0.08,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.08,
            "MOTION_LOSS_WEIGHT": 0.16,
            "MOTION_BOUNDARY_WEIGHT": 1.30,
            "MOTION_RECON_WEIGHT": 0.25,
            "MOTION_EVERY_N_BATCH": 2,
            "MOTION_INCLUDE_SUBDIRS": MOTION_NO_REGION_MIXED,
        },
    },
    "r44c_static_heavy_all_motion": {
        "note": "keep all motion families but heavily protect static boundary fidelity",
        "overrides": {
            "LR": 2.5e-6,
            "BOUNDARY_LOSS_WEIGHT": 0.14,
            "CENTERLINE_LOSS_WEIGHT": 0.09,
            "DISTANCE_EDGE_LOSS_WEIGHT": 0.09,
            "MOTION_LOSS_WEIGHT": 0.14,
            "MOTION_BOUNDARY_WEIGHT": 1.10,
            "MOTION_RECON_WEIGHT": 0.30,
            "MOTION_EVERY_N_BATCH": 2,
            "MOTION_INCLUDE_SUBDIRS": MOTION_STAGES,
        },
    },
}


def _probe_choices() -> list[str]:
    return sorted(PROBES)


def configure_probe(trainer, args: argparse.Namespace, static_dir: Path, motion_dir: Path) -> dict:
    base_args = SimpleNamespace(
        candidate=R42_BASE_CANDIDATE,
        base_checkpoint=args.base_checkpoint,
        num_epoch=args.num_epoch,
        max_train_batches=args.max_train_batches,
        val_ratio=args.val_ratio,
        batch_size=args.batch_size,
        val_batch_size=args.val_batch_size,
        device=args.device,
    )
    configure_trainer(trainer, base_args, static_dir, motion_dir)

    cfg = trainer.CFG
    probe = PROBES[args.probe]
    for key, value in probe["overrides"].items():
        setattr(cfg, key, value)
    cfg.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.probe}"
    trainer.MODEL_NAME_BASE = cfg.MODEL_NAME

    return {
        "probe": args.probe,
        "note": probe["note"],
        "base_candidate": R42_BASE_CANDIDATE,
        "base_checkpoint": str(Path(args.base_checkpoint).resolve()),
        "model_name": cfg.MODEL_NAME,
        "num_epoch": cfg.NUM_EPOCH,
        "max_train_batches": cfg.MAX_TRAIN_BATCHES_PER_EPOCH,
        "device": cfg.DEVICE,
        "lr": cfg.LR,
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
    parser = argparse.ArgumentParser(description="Run R44C short probe training.")
    parser.add_argument("--probe", required=True, choices=_probe_choices())
    parser.add_argument("--num-epoch", type=int, default=21)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=80)
    parser.add_argument("--val-ratio", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--val-batch-size", type=int, default=4)
    parser.add_argument("--base-checkpoint", type=Path, default=BASE_CHECKPOINT_BY_CANDIDATE[R42_BASE_CANDIDATE])
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
        print("[R44C] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
