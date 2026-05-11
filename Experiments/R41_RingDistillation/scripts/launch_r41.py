"""R41 ring-anchored distillation training launcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Model"))

from r41_data import DEFAULT_OUTPUT_ROOT, ensure_data_package  # noqa: E402


COMBO_CHECKPOINT = (
    REPO_ROOT
    / "Traing_Progress"
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
R40_ENDPOINT_CHECKPOINT = (
    REPO_ROOT
    / "Traing_Progress"
    / "training_progress_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260504_145920"
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

SEQ_8PX_STAGES = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)

PROFILE_BY_CANDIDATE = {
    "r41_kd_from_a045": "r41_ring_recover_train",
    "r41_kd_from_r40_endpoint": "r41_ring_recover_train",
}

BASE_CHECKPOINT_BY_CANDIDATE = {
    "r41_kd_from_a045": R40_A045_CHECKPOINT,
    "r41_kd_from_r40_endpoint": R40_ENDPOINT_CHECKPOINT,
}

CANDIDATE_NOTES = {
    "r41_kd_from_a045": "primary recovery from R40 a045 weight average",
    "r41_kd_from_r40_endpoint": "capacity endpoint recovery from R40 trained endpoint",
}

BASE_OVERRIDES = {
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,
    "LOAD_RESET_EPOCH": True,
    "LR": 8e-6,
    "SEQ_ENABLE": True,
    "SEQ_SRC_DIR": str(REPO_ROOT / "Training_Data" / "generated_convolved"),
    "SEQ_LBL_DIR": str(REPO_ROOT / "Training_Data" / "generated"),
    "SEQ_INCLUDE_SUBDIRS": SEQ_8PX_STAGES,
    "SEQ_LOSS_WEIGHT": 0.3,
    "SEQ_GRAD_WEIGHT": 0.1,
    "SEQ_EVERY_N_BATCH": 2,
    "SEQ_MIN_DELTA_THRESHOLD": 0.002,
    "SEQ_WARMUP_EPOCH": 15,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 10,
    "TRAIN_INCLUDE_SUBDIRS": (),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "KD_ENABLE": True,
    "KD_COMBO_PATH": str(COMBO_CHECKPOINT),
    "KD_R40_PATH": str(R40_ENDPOINT_CHECKPOINT),
    "KD_WEIGHT_COMBO": 0.10,
    "KD_WEIGHT_R40": 0.05,
    "KD_WARMUP_EPOCH": 0,
}


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)

    checkpoint = Path(args.base_checkpoint).resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")
    if not COMBO_CHECKPOINT.exists():
        raise FileNotFoundError(f"COMBO teacher not found: {COMBO_CHECKPOINT}")
    if not R40_ENDPOINT_CHECKPOINT.exists():
        raise FileNotFoundError(f"R40 teacher not found: {R40_ENDPOINT_CHECKPOINT}")

    CFG.RESUME_CHECKPOINT = str(checkpoint)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = int(args.num_epoch)
    CFG.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    if args.max_train_batches is not None:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
    CFG.DEVICE = str(args.device)

    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R41 ring-anchored distillation launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=30)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
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
    CFG = trainer.CFG
    summary = {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "count_by_role": manifest["count_by_role"],
        "base_checkpoint": str(Path(args.base_checkpoint).resolve()),
        "combo_teacher": CFG.KD_COMBO_PATH,
        "r40_teacher": CFG.KD_R40_PATH,
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "simpletest_max_epoch": CFG.SIMPLETEST_MAX_EPOCH,
        "max_train_batches": CFG.MAX_TRAIN_BATCHES_PER_EPOCH,
        "device": CFG.DEVICE,
        "lr": CFG.LR,
        "kd_weights": {"combo_ring": CFG.KD_WEIGHT_COMBO, "r40_micro": CFG.KD_WEIGHT_R40},
        "seq_stages": list(CFG.SEQ_INCLUDE_SUBDIRS),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R41] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
