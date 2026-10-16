"""R44 universal boundary-motion fidelity training launcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "Model"))

from r42_boundary_data import DEFAULT_DATA_ROOT as R42_DATA_ROOT  # noqa: E402
from r42_boundary_data import ensure_data_package  # noqa: E402
from r44_motion_data import (  # noqa: E402
    DEFAULT_CLEAN_ROOT,
    DEFAULT_DATA_ROOT,
    DEFAULT_GEOM_ROOT,
    DEFAULT_SOURCE_ROOT,
    MOTION_STAGES,
    ensure_motion_package,
    generate_motion_dataset,
)


COMBO_CHECKPOINT = (
    REPO_ROOT
    / "Traing_Progress"
    / "training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525"
    / "weights"
    / "best_tradeoff.pth.tar"
)
R40_A045_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R40_MicroscopyFeatureCoverage"
    / "results"
    / "weight_sweep"
    / "combo_best_low_alpha"
    / "checkpoints"
    / "a045"
    / "best_tradeoff.pth.tar"
)
R42_R41_BEST_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R42_MicroscopyBoundaryFidelity"
    / "results"
    / "archive_retained_20260824"
    / "training_checkpoints"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r42_boundary_from_r41_20260505_145229"
    / "best_tradeoff.pth.tar"
)


PROFILE_BY_CANDIDATE = {
    "r44_motion_from_r42_best": "r44_motion_research_train",
    "r44_motion_from_r40_a045": "r44_motion_research_train",
    "r44_motion_from_combo": "r44_motion_research_train",
}

BASE_CHECKPOINT_BY_CANDIDATE = {
    "r44_motion_from_r42_best": R42_R41_BEST_CHECKPOINT,
    "r44_motion_from_r40_a045": R40_A045_CHECKPOINT,
    "r44_motion_from_combo": COMBO_CHECKPOINT,
}

STATIC_PROFILE_BY_CANDIDATE = {
    "r44_motion_from_r42_best": "r42_boundary_research_train",
    "r44_motion_from_r40_a045": "r42_boundary_research_train",
    "r44_motion_from_combo": "r42_boundary_research_train",
}

CANDIDATE_NOTES = {
    "r44_motion_from_r42_best": "start from R42 boundary-specialist endpoint and repair generic motion fidelity",
    "r44_motion_from_r40_a045": "start from R40 microscopy-feature compromise and test steadier motion behavior",
    "r44_motion_from_combo": "start from COMBO as conservative boundary-motion learning reference",
}

BASE_OVERRIDES = {
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,
    "LOAD_RESET_EPOCH": True,
    "LR": 6.0e-6,
    "SEQ_ENABLE": False,
    "SEQ_GEOM_ENABLE": False,
    "KD_ENABLE": False,
    "TRAIN_INCLUDE_SUBDIRS": (),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "BOUNDARY_GEOM_ENABLE": True,
    "BOUNDARY_LOSS_WEIGHT": 0.08,
    "CENTERLINE_LOSS_WEIGHT": 0.05,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.05,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 0,
    "MOTION_ENABLE": True,
    "MOTION_LOSS_WEIGHT": 0.20,
    "MOTION_BOUNDARY_WEIGHT": 1.50,
    "MOTION_RECON_WEIGHT": 0.20,
    "MOTION_WARMUP_EPOCH": 0,
    "MOTION_EVERY_N_BATCH": 2,
    "MOTION_BATCH_SIZE": 2,
    "MOTION_INCLUDE_SUBDIRS": MOTION_STAGES,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 10,
    "W_GRADMAG": 0.8,
    "W_EDGE_ORI_SIMPLE": 0.3,
    "W_HF_LAP": 0.15,
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
}

CANDIDATE_OVERRIDES = {
    "r44_motion_from_combo": {
        "LR": 8.0e-6,
        "MOTION_LOSS_WEIGHT": 0.25,
    },
    "r44_motion_from_r42_best": {
        "LR": 4.0e-6,
        "BOUNDARY_LOSS_WEIGHT": 0.06,
    },
}


def configure_trainer(trainer, args: argparse.Namespace, static_dir: Path, motion_dir: Path) -> None:
    cfg = trainer.CFG
    for key, value in BASE_OVERRIDES.items():
        setattr(cfg, key, value)
    for key, value in CANDIDATE_OVERRIDES.get(args.candidate, {}).items():
        setattr(cfg, key, value)

    checkpoint = Path(args.base_checkpoint).resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")

    cfg.RESUME_CHECKPOINT = str(checkpoint)
    cfg.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = cfg.MODEL_NAME
    cfg.NUM_EPOCH = int(args.num_epoch)
    cfg.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    if args.max_train_batches is not None:
        cfg.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
    if args.val_ratio is not None:
        cfg.VAL_RATIO = float(args.val_ratio)
    if args.batch_size is not None:
        cfg.BATCH_SIZE = int(args.batch_size)
    if args.val_batch_size is not None:
        cfg.VAL_BATCH_SIZE = int(args.val_batch_size)
    cfg.DEVICE = str(args.device)
    cfg.BOUNDARY_GEOM_DIR = str(static_dir / "geom")
    cfg.MOTION_SRC_DIR = str(motion_dir / "src")
    cfg.MOTION_LBL_DIR = str(motion_dir / "lbl")
    cfg.MOTION_GEOM_DIR = str(motion_dir / "geom")
    cfg.MOTION_META_DIR = str(motion_dir / "geom" / "meta")

    trainer.TRAIN_SRC_DIR = str(static_dir / "src")
    trainer.TRAIN_LBL_DIR = str(static_dir / "lbl")
    trainer.TRAIN_GEOM_DIR = str(static_dir / "geom")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R44 universal boundary-motion fidelity launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=40)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--val-batch-size", type=int, default=None)
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--static-data-root", type=Path, default=R42_DATA_ROOT)
    parser.add_argument("--motion-data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--generate-motion-pool", action="store_true")
    parser.add_argument("--motion-pool-count", type=int, default=100)
    parser.add_argument("--motion-size", type=int, default=512)
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

    if args.base_checkpoint is None:
        args.base_checkpoint = BASE_CHECKPOINT_BY_CANDIDATE[args.candidate]

    if args.generate_motion_pool:
        generate_motion_dataset(
            clean_root=DEFAULT_CLEAN_ROOT,
            source_root=DEFAULT_SOURCE_ROOT,
            geom_root=DEFAULT_GEOM_ROOT,
            count_per_stage=args.motion_pool_count,
            size=args.motion_size,
            force=args.force_data,
        )

    static_profile = STATIC_PROFILE_BY_CANDIDATE[args.candidate]
    motion_profile = PROFILE_BY_CANDIDATE[args.candidate]
    static_dir, static_manifest = ensure_data_package(
        static_profile,
        args.static_data_root,
        build_data=args.build_data,
        force_data=args.force_data,
        link_mode=args.link_mode,
    )
    motion_dir, motion_manifest = ensure_motion_package(
        motion_profile,
        args.motion_data_root,
        build_data=args.build_data,
        force_data=args.force_data,
        link_mode=args.link_mode,
    )

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    configure_trainer(trainer, args, static_dir, motion_dir)
    cfg = trainer.CFG
    summary = {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "static_profile": static_profile,
        "static_dir": str(static_dir),
        "static_total_pairs": static_manifest["total_pairs"],
        "motion_profile": motion_profile,
        "motion_dir": str(motion_dir),
        "motion_total_frames": motion_manifest["total_frames"],
        "motion_count_by_family": motion_manifest["count_by_family"],
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
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R44] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
