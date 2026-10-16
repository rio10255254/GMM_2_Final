"""R54 masked small-overfit launcher for LabSystem_MOSR."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[5]
MODEL_DIR = PROJECT_ROOT / "Model"
SCRIPT_DIR = Path(__file__).resolve().parent
LAB_TRAINING_PROGRESS_ROOT = LAB_ROOT / "Traing_Progress"
LAB_CHECKPOINT_CACHE = LAB_TRAINING_PROGRESS_ROOT / "_checkpoint_cache"
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(MODEL_DIR))

from r54_masked_overfit_probe import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SELECTED_CSV,
    GEOMETRY_POLICY,
    LABEL_POLICY,
    PROFILE_NAME,
    materialize_overfit_package,
)


LAB_R40_TRADEOFF_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260609_185153"
    / "weights"
    / "best_tradeoff.pth.tar"
)

PROFILE_BY_CANDIDATE = {
    "r54_masked_overfit_from_r40": PROFILE_NAME,
}

BASE_CHECKPOINT_BY_CANDIDATE = {
    "r54_masked_overfit_from_r40": LAB_R40_TRADEOFF_CHECKPOINT,
}

CANDIDATE_NOTES = {
    "r54_masked_overfit_from_r40": (
        "Masked small-overfit probe from the Lab R40 best_tradeoff control. "
        "Uses real CAD GT only inside reliable masks."
    ),
}

BASE_OVERRIDES = {
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,
    "LOAD_RESET_EPOCH": True,
    "SEQ_ENABLE": False,
    "SEQ_SRC_DIR": "",
    "SEQ_LBL_DIR": "",
    "SEQ_INCLUDE_SUBDIRS": (),
    "SEQ_LOSS_WEIGHT": 0.0,
    "SEQ_GRAD_WEIGHT": 0.0,
    "SEQ_EVERY_N_BATCH": 999999,
    "SEQ_MIN_DELTA_THRESHOLD": 0.002,
    "SEQ_WARMUP_EPOCH": 0,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 0,
    "TRAIN_INCLUDE_SUBDIRS": (),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "PSF_FITTED_PATH": str(LAB_PSF_PATH),
    "PHYS_FORWARD_ENABLE": False,
    "W_PHYS_MAX": 0.0,
    "BATCH_SIZE": 8,
    "VAL_BATCH_SIZE": 4,
    "NUM_WORKERS": 0,
    "DATALOADER_PERSISTENT_WORKERS": False,
    "DATALOADER_PREFETCH_FACTOR": 2,
    "CROP_SIZE": 256,
    "SEQ_BATCH_SIZE": 2,
    "MOTION_BATCH_SIZE": 2,
    "W_REC": 1.0,
    "W_GRADMAG": 0.50,
    "W_EDGE_ORI_SIMPLE": 0.12,
    "W_HF_LAP": 0.04,
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
    "W_EDGELOCAL_LAP_START": 0.0,
    "W_EDGELOCAL_LAP_END": 0.010,
    "EDGELOCAL_LAP_RAMP_E1": 0,
    "EDGELOCAL_LAP_RAMP_E2": 3,
    "BOUNDARY_GEOM_ENABLE": True,
    "BOUNDARY_GEOM_DIR": "",
    "BOUNDARY_LOSS_WEIGHT": 0.020,
    "CENTERLINE_LOSS_WEIGHT": 0.010,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.005,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 0,
    "BOUNDARY_DISTANCE_SIGMA": 2.0,
    "BOUNDARY_DISTANCE_CLIP": 8.0,
    "MOTION_ENABLE": False,
    "KD_ENABLE": False,
    "REGION_KD_ENABLE": False,
    "VAL_RATIO": 0.0,
    "BEST_EPOCH_MIN": 1,
    "MAX_TRAIN_BATCHES_PER_EPOCH": 0,
}

PSF_BUFFER_KEYS = (
    "physics_layer.PSFs",
    "physics_layer.PSF_mean",
    "physics_layer.PSF_center",
    "weak_psf_block.PSFs",
)


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _require_lab_assets() -> None:
    if not MODEL_DIR.is_dir():
        raise FileNotFoundError(f"main model directory not found: {MODEL_DIR}")
    if not LAB_PSF_PATH.exists():
        raise FileNotFoundError(f"Lab PSF file not found: {LAB_PSF_PATH}")


def _cache_key_for_checkpoint(base_checkpoint: Path) -> str:
    base_stat = base_checkpoint.stat()
    psf_stat = LAB_PSF_PATH.stat()
    payload = "|".join(
        [
            str(base_checkpoint.resolve()),
            str(base_stat.st_size),
            str(base_stat.st_mtime_ns),
            str(LAB_PSF_PATH.resolve()),
            str(psf_stat.st_size),
            str(psf_stat.st_mtime_ns),
            ",".join(PSF_BUFFER_KEYS),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _shape_of(value) -> list[int] | str:
    shape = getattr(value, "shape", None)
    if shape is None:
        return type(value).__name__
    return [int(v) for v in shape]


def prepare_lab_checkpoint(base_checkpoint: Path) -> Path:
    _require_lab_assets()
    source = Path(base_checkpoint).resolve()
    if not source.exists():
        raise FileNotFoundError(f"checkpoint not found: {source}")

    cache_name = f"{source.stem}_labpsf_{_cache_key_for_checkpoint(source)}{source.suffix}"
    cache_path = LAB_CHECKPOINT_CACHE / cache_name
    if cache_path.exists():
        return cache_path

    import torch

    ckpt = torch.load(source, map_location="cpu")
    removed: dict[str, list[dict]] = {}
    for section in ("state_dict", "ema_state_dict"):
        state = ckpt.get(section)
        if not state:
            continue
        section_removed = []
        for key in PSF_BUFFER_KEYS:
            if key in state:
                section_removed.append({"key": key, "shape": _shape_of(state[key])})
                del state[key]
        if section_removed:
            removed[section] = section_removed

    ckpt["lab_psf_checkpoint_filter"] = {
        "source_checkpoint": str(source),
        "lab_psf": str(LAB_PSF_PATH),
        "removed": removed,
    }
    LAB_CHECKPOINT_CACHE.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    torch.save(ckpt, tmp_path)
    os.replace(tmp_path, cache_path)
    return cache_path


def ensure_data_package(
    profile_name: str,
    output_root: Path,
    *,
    build_data: bool,
    force_data: bool,
) -> tuple[Path, dict]:
    if profile_name != PROFILE_NAME:
        raise ValueError(f"unknown R54 data profile: {profile_name}")
    package_dir = Path(output_root) / profile_name
    if build_data:
        manifest = materialize_overfit_package(DEFAULT_SELECTED_CSV, package_dir, force=force_data)
    else:
        manifest = _load_manifest(package_dir / "manifest.json")
    if manifest.get("profile") != profile_name:
        raise RuntimeError(f"manifest profile mismatch in {package_dir}")
    if manifest.get("label_policy") != LABEL_POLICY:
        raise RuntimeError(f"unexpected R54 label policy in {package_dir}")
    if manifest.get("geometry_policy") not in {GEOMETRY_POLICY, None}:
        raise RuntimeError(f"unexpected R54 geometry policy in {package_dir}")
    if manifest.get("geometry_sidecars") is not True:
        raise RuntimeError(f"geometry sidecars are not ready in {package_dir}")
    if int(manifest.get("geometry_count", 0)) != int(manifest.get("total_pairs", -1)):
        raise RuntimeError(f"geometry count mismatch in {package_dir}")
    for leaf in ("src", "lbl", "geom"):
        if not (package_dir / leaf).is_dir():
            raise RuntimeError(f"missing {leaf} folder in {package_dir}")
    return package_dir, manifest


def _set_lab_progress_root(trainer) -> None:
    if hasattr(trainer, "_set_training_progress_root"):
        trainer._set_training_progress_root(str(LAB_TRAINING_PROGRESS_ROOT))
        return
    trainer.TRAINING_PROGRESS_ROOT = str(LAB_TRAINING_PROGRESS_ROOT)


def _sanitize_suffix(suffix: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in suffix.strip())
    return f"_{clean}" if clean else ""


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
    _require_lab_assets()
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)

    checkpoint = Path(args.base_checkpoint).resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")

    _set_lab_progress_root(trainer)
    lab_checkpoint = prepare_lab_checkpoint(checkpoint)
    CFG.RESUME_CHECKPOINT = str(lab_checkpoint)
    CFG.LAB_SOURCE_CHECKPOINT = str(checkpoint)
    CFG.MODEL_NAME = f"LAB_GESR_v1_v5_ST0p8_SWP_{args.candidate}{_sanitize_suffix(args.run_suffix)}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = int(args.num_epoch)
    CFG.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    CFG.DEVICE = str(args.device)

    if args.max_train_batches is not None:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
    if args.val_ratio is not None:
        CFG.VAL_RATIO = float(args.val_ratio)
    if args.batch_size is not None:
        CFG.BATCH_SIZE = int(args.batch_size)
    if args.val_batch_size is not None:
        CFG.VAL_BATCH_SIZE = int(args.val_batch_size)
    if args.num_workers is not None:
        CFG.NUM_WORKERS = int(args.num_workers)
    if args.crop_size is not None:
        CFG.CROP_SIZE = int(args.crop_size)

    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")
    trainer.TRAIN_GEOM_DIR = str(data_dir / "geom")
    CFG.BOUNDARY_GEOM_DIR = str(data_dir / "geom")


def _dry_run_data_missing_summary(
    *,
    args: argparse.Namespace,
    profile_name: str,
    error: Exception,
) -> dict:
    checkpoint = Path(args.base_checkpoint).resolve()
    return {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "training_ready": False,
        "reason": "data package is not ready",
        "data_error": str(error),
        "data_root": str(Path(args.data_root).resolve()),
        "base_checkpoint": str(checkpoint),
        "base_checkpoint_exists": checkpoint.exists(),
        "lab_psf": str(LAB_PSF_PATH),
        "lab_psf_exists": LAB_PSF_PATH.exists(),
        "label_policy": LABEL_POLICY,
        "geometry_policy": GEOMETRY_POLICY,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lab R54 masked small-overfit launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=20)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--val-batch-size", type=int, default=4)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

    if args.base_checkpoint is None:
        args.base_checkpoint = BASE_CHECKPOINT_BY_CANDIDATE[args.candidate]

    profile_name = PROFILE_BY_CANDIDATE[args.candidate]
    try:
        data_dir, manifest = ensure_data_package(
            profile_name,
            args.data_root,
            build_data=args.build_data,
            force_data=args.force_data,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        if args.dry_run:
            print(
                json.dumps(
                    _dry_run_data_missing_summary(args=args, profile_name=profile_name, error=exc),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            print("[R54][Lab] dry run complete; training cannot start until data is ready.")
            return 0
        raise

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    configure_trainer(trainer, args, data_dir)
    CFG = trainer.CFG
    summary = {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "count_by_role": manifest.get("count_by_role", {}),
        "base_checkpoint": str(Path(args.base_checkpoint).resolve()),
        "lab_compatible_checkpoint": CFG.RESUME_CHECKPOINT,
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "simpletest_max_epoch": CFG.SIMPLETEST_MAX_EPOCH,
        "device": CFG.DEVICE,
        "batch_size": CFG.BATCH_SIZE,
        "val_ratio": CFG.VAL_RATIO,
        "num_workers": CFG.NUM_WORKERS,
        "crop_size": CFG.CROP_SIZE,
        "lab_psf": CFG.PSF_FITTED_PATH,
        "training_progress_root": str(LAB_TRAINING_PROGRESS_ROOT),
        "seq_enable": bool(CFG.SEQ_ENABLE),
        "phys_forward_enable": bool(CFG.PHYS_FORWARD_ENABLE),
        "boundary_geom_enable": bool(CFG.BOUNDARY_GEOM_ENABLE),
        "boundary_geom_dir": CFG.BOUNDARY_GEOM_DIR,
        "label_policy": manifest.get("label_policy", ""),
        "geometry_policy": manifest.get("geometry_policy", ""),
        "max_train_batches": getattr(CFG, "MAX_TRAIN_BATCHES_PER_EPOCH", None),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R54][Lab] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
