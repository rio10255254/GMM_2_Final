"""R39 shape-generalization training launcher."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_REPO_ROOT / "Model"))

from r39_shape_data import DEFAULT_OUTPUT_ROOT, PROFILES, build_plan, materialize_plan


COMBO_CHECKPOINT = (
    _REPO_ROOT
    / "Experiments"
    / "Training_Runs"
    / "training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525"
    / "weights"
    / "best_tradeoff.pth.tar"
)

SEQ_8PX_STAGES = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)

PROFILE_BY_CANDIDATE = {
    "r39_shape_mix_safe": "r39_shape_mix_safe",
    "r39_shape_mix_strong": "r39_shape_mix_strong",
}

BASE_OVERRIDES = {
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,
    "LOAD_RESET_EPOCH": True,
    "SEQ_ENABLE": True,
    "SEQ_SRC_DIR": str(_REPO_ROOT / "Training_Data" / "generated_convolved"),
    "SEQ_LBL_DIR": str(_REPO_ROOT / "Training_Data" / "generated"),
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
}

CANDIDATE_NOTES = {
    "r39_shape_mix_safe": "main candidate: ring data plus a conservative multi-shape mix",
    "r39_shape_mix_strong": "capacity probe: ring data plus a stronger multi-shape mix",
}


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_data_package(
    profile_name: str,
    output_root: Path,
    *,
    build_data: bool,
    force_data: bool,
    link_mode: str,
) -> tuple[Path, dict]:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown R39 data profile: {profile_name}")

    package_dir = output_root / profile_name
    plan = build_plan(_REPO_ROOT, PROFILES[profile_name])
    if build_data:
        manifest = materialize_plan(plan, package_dir, force=force_data, link_mode=link_mode)
    else:
        manifest = _load_manifest(package_dir / "manifest.json")

    if manifest.get("profile") != profile_name:
        raise RuntimeError(f"manifest profile mismatch in {package_dir}")
    if int(manifest.get("total_pairs", -1)) != len(plan.pairs):
        raise RuntimeError(f"manifest pair count mismatch in {package_dir}")
    for leaf in ("src", "lbl"):
        if not (package_dir / leaf).is_dir():
            raise RuntimeError(f"missing {leaf} folder in {package_dir}")
    return package_dir, manifest


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)

    checkpoint = Path(args.combo_checkpoint).resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(f"COMBO checkpoint not found: {checkpoint}")

    CFG.RESUME_CHECKPOINT = str(checkpoint)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = int(args.num_epoch)
    CFG.DEVICE = str(args.device)

    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R39 shape-generalization launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=100)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--combo-checkpoint", type=Path, default=COMBO_CHECKPOINT)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

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
        "combo_checkpoint": str(Path(args.combo_checkpoint).resolve()),
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "device": CFG.DEVICE,
        "seq_stages": list(CFG.SEQ_INCLUDE_SUBDIRS),
        "robust_loss_percentile": CFG.ROBUST_LOSS_PERCENTILE,
    }
    print(json.dumps(summary, indent=2))

    if args.dry_run:
        print("[R39] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
