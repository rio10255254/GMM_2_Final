"""R42 microscopy-boundary fidelity training launcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Model"))

from r42_boundary_data import DEFAULT_DATA_ROOT, ensure_data_package  # noqa: E402


COMBO_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "Training_Runs"
    / "training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525"
    / "weights"
    / "best_tradeoff.pth.tar"
)
R39_A030_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R39_ShapeGeneralization"
    / "results"
    / "weight_sweep"
    / "checkpoints"
    / "a030"
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
R41_DIRECT_CHECKPOINT = (
    REPO_ROOT
    / "Experiments"
    / "R41_RingDistillation"
    / "selected_checkpoint"
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
    "r42_boundary_from_combo": "r42_boundary_research_train",
    "r42_boundary_from_r41": "r42_boundary_research_train",
    "r42_boundary_guarded_kd_probe": "r42_guarded_kd_probe_train",
}

BASE_CHECKPOINT_BY_CANDIDATE = {
    "r42_boundary_from_combo": COMBO_CHECKPOINT,
    "r42_boundary_from_r41": R41_DIRECT_CHECKPOINT,
    "r42_boundary_guarded_kd_probe": R42_R41_BEST_CHECKPOINT,
}

CANDIDATE_NOTES = {
    "r42_boundary_from_combo": "conservative start from COMBO to test boundary learning without capacity-rich start",
    "r42_boundary_from_r41": "capacity-rich start from R41 endpoint to test boundary precision on top of micro clarity",
    "r42_boundary_guarded_kd_probe": "short diagnostic from R42/R41 best with COMBO legacy teacher and R42 boundary teacher",
}

BASE_OVERRIDES = {
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,
    "LOAD_RESET_EPOCH": True,
    "LR": 1.0e-5,
    "SEQ_ENABLE": False,
    "KD_ENABLE": False,
    "TRAIN_INCLUDE_SUBDIRS": (),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "BOUNDARY_GEOM_ENABLE": True,
    "BOUNDARY_LOSS_WEIGHT": 0.10,
    "CENTERLINE_LOSS_WEIGHT": 0.05,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.05,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 0,
    "BOUNDARY_DISTANCE_SIGMA": 2.0,
    "BOUNDARY_DISTANCE_CLIP": 8.0,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 10,
    "W_GRADMAG": 0.8,
    "W_EDGE_ORI_SIMPLE": 0.3,
    "W_HF_LAP": 0.15,
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
}

CANDIDATE_OVERRIDES = {
    "r42_boundary_guarded_kd_probe": {
        "LR": 3.0e-6,
        "KD_ENABLE": True,
        "KD_COMBO_PATH": str(COMBO_CHECKPOINT),
        "KD_R40_PATH": str(R42_R41_BEST_CHECKPOINT),
        "KD_WEIGHT_COMBO": 0.20,
        "KD_WEIGHT_R40": 0.05,
        "KD_WARMUP_EPOCH": 0,
        "BOUNDARY_LOSS_WEIGHT": 0.06,
        "CENTERLINE_LOSS_WEIGHT": 0.03,
        "DISTANCE_EDGE_LOSS_WEIGHT": 0.03,
    },
}


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
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
    cfg.BOUNDARY_GEOM_DIR = str(data_dir / "geom")

    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")
    trainer.TRAIN_GEOM_DIR = str(data_dir / "geom")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R42 microscopy-boundary fidelity launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=50)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--val-batch-size", type=int, default=None)
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

    if args.base_checkpoint is None:
        args.base_checkpoint = BASE_CHECKPOINT_BY_CANDIDATE[args.candidate]

    profile_name = PROFILE_BY_CANDIDATE[args.candidate]
    data_dir, manifest = ensure_data_package(
        profile_name,
        args.data_root,
        build_data=args.build_data,
        force_data=args.force_data,
        link_mode=args.link_mode,
    )

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    configure_trainer(trainer, args, data_dir)
    cfg = trainer.CFG
    summary = {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "count_by_role": manifest["count_by_role"],
        "base_checkpoint": str(Path(args.base_checkpoint).resolve()),
        "model_name": cfg.MODEL_NAME,
        "num_epoch": cfg.NUM_EPOCH,
        "simpletest_max_epoch": cfg.SIMPLETEST_MAX_EPOCH,
        "max_train_batches": cfg.MAX_TRAIN_BATCHES_PER_EPOCH,
        "val_ratio": cfg.VAL_RATIO,
        "batch_size": cfg.BATCH_SIZE,
        "val_batch_size": cfg.VAL_BATCH_SIZE,
        "device": cfg.DEVICE,
        "lr": cfg.LR,
        "boundary_weights": {
            "boundary": cfg.BOUNDARY_LOSS_WEIGHT,
            "centerline": cfg.CENTERLINE_LOSS_WEIGHT,
            "distance_edge": cfg.DISTANCE_EDGE_LOSS_WEIGHT,
        },
        "kd": {
            "enabled": cfg.KD_ENABLE,
            "combo_weight": cfg.KD_WEIGHT_COMBO,
            "capacity_weight": cfg.KD_WEIGHT_R40,
            "combo_path": cfg.KD_COMBO_PATH,
            "capacity_path": cfg.KD_R40_PATH,
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R42] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
