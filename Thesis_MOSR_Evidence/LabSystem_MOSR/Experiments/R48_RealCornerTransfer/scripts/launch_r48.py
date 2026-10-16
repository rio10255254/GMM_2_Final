"""R48 real-corner transfer fine-tune launcher for LabSystem_MOSR."""
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

from r48_real_corner_data import DEFAULT_OUTPUT_ROOT, PROFILES, build_plan, materialize_plan


LAB_R39_LATEST_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r39_shape_mix_safe_20260609_173931"
    / "weights"
    / "latest.pth.tar"
)

LAB_R40_LATEST_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r40_micro_capacity_combo_20260609_185153"
    / "weights"
    / "latest.pth.tar"
)

SEQ_8PX_STAGES = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)

PROFILE_BY_CANDIDATE = {
    "r48_real_corner_r39_latest": "r48_real_corner_train_6000",
    "r48_real_corner_r40_latest": "r48_real_corner_train_6000",
}

BASE_CHECKPOINT_BY_CANDIDATE = {
    "r48_real_corner_r39_latest": LAB_R39_LATEST_CHECKPOINT,
    "r48_real_corner_r40_latest": LAB_R40_LATEST_CHECKPOINT,
}

CANDIDATE_NOTES = {
    "r48_real_corner_r39_latest": (
        "Real-corner Lab transfer fine-tune from the Lab R39 checkpoint."
    ),
    "r48_real_corner_r40_latest": (
        "Real-corner Lab transfer fine-tune from the Lab R40 checkpoint."
    ),
}

BASE_OVERRIDES = {
    "LOAD_MODEL": True,
    "LOAD_RESET_OPTIMIZER": True,
    "LOAD_RESET_EPOCH": True,
    "SEQ_ENABLE": True,
    "SEQ_SRC_DIR": str(LAB_ROOT / "Training_Data" / "generated_convolved"),
    "SEQ_LBL_DIR": str(LAB_ROOT / "Training_Data" / "generated"),
    "SEQ_INCLUDE_SUBDIRS": SEQ_8PX_STAGES,
    "SEQ_LOSS_WEIGHT": 0.3,
    "SEQ_GRAD_WEIGHT": 0.1,
    "SEQ_EVERY_N_BATCH": 2,
    "SEQ_MIN_DELTA_THRESHOLD": 0.002,
    "SEQ_WARMUP_EPOCH": 20,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 10,
    "TRAIN_INCLUDE_SUBDIRS": (),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "PSF_FITTED_PATH": str(LAB_PSF_PATH),
    # R48 keeps edge guidance active but moves the hard corner signal into
    # geometry sidecars so the model sees where the boundary must stay sharp.
    "W_REC": 1.0,
    "W_GRADMAG": 0.85,
    "W_EDGE_ORI_SIMPLE": 0.30,
    "W_HF_LAP": 0.10,
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
    "W_EDGELOCAL_LAP_START": 0.0,
    "W_EDGELOCAL_LAP_END": 0.04,
    "EDGELOCAL_LAP_RAMP_E1": 5,
    "EDGELOCAL_LAP_RAMP_E2": 20,
    "BOUNDARY_GEOM_ENABLE": True,
    "BOUNDARY_GEOM_DIR": "",
    "BOUNDARY_LOSS_WEIGHT": 0.08,
    "CENTERLINE_LOSS_WEIGHT": 0.04,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.03,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 3,
    "BOUNDARY_DISTANCE_SIGMA": 2.0,
    "BOUNDARY_DISTANCE_CLIP": 8.0,
    "MOTION_ENABLE": False,
    "KD_ENABLE": False,
    "REGION_KD_ENABLE": False,
    "BEST_EPOCH_MIN": 10,
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
    """Create a Lab-compatible checkpoint that reloads current Lab PSF buffers."""
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
    link_mode: str,
) -> tuple[Path, dict]:
    if profile_name not in PROFILES:
        raise ValueError(f"unknown R48 data profile: {profile_name}")
    package_dir = output_root / profile_name
    plan = build_plan(LAB_ROOT, PROFILES[profile_name])
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
    geom_dir = Path(str(manifest.get("geom_dir", "")))
    if manifest.get("geometry_sidecars") is not True or int(manifest.get("geometry_count", 0)) != len(plan.pairs):
        raise RuntimeError(f"geometry sidecars are not ready in {package_dir}")
    if not geom_dir.is_dir():
        raise RuntimeError(f"missing geometry folder in {package_dir}: {geom_dir}")
    return package_dir, manifest


def _set_lab_progress_root(trainer) -> None:
    if hasattr(trainer, "_set_training_progress_root"):
        trainer._set_training_progress_root(str(LAB_TRAINING_PROGRESS_ROOT))
        return
    trainer.TRAINING_PROGRESS_ROOT = str(LAB_TRAINING_PROGRESS_ROOT)


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
    _require_lab_assets()
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)

    _set_lab_progress_root(trainer)
    resume_checkpoint = Path(args.resume_checkpoint).resolve() if args.resume_checkpoint is not None else None
    if resume_checkpoint is not None:
        if not resume_checkpoint.exists():
            raise FileNotFoundError(f"resume checkpoint not found: {resume_checkpoint}")
        checkpoint = resume_checkpoint
        lab_checkpoint = resume_checkpoint
        CFG.LOAD_RESET_OPTIMIZER = False
        CFG.LOAD_RESET_EPOCH = False
    else:
        checkpoint = Path(args.base_checkpoint).resolve()
        if not checkpoint.exists():
            raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")
        lab_checkpoint = prepare_lab_checkpoint(checkpoint)

    CFG.RESUME_CHECKPOINT = str(lab_checkpoint)
    CFG.LAB_SOURCE_CHECKPOINT = str(checkpoint)
    run_suffix = str(getattr(args, "run_suffix", "") or "").strip()
    if run_suffix:
        safe_suffix = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in run_suffix)
        run_suffix = f"_{safe_suffix}"
    CFG.MODEL_NAME = f"LAB_GESR_v1_v5_ST0p8_SWP_{args.candidate}{run_suffix}"
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
        "boundary_geom_enable": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lab R48 real-corner transfer fine-tune launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=200)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=None)
    parser.add_argument("--resume-checkpoint", type=Path, default=None)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--link-mode", choices=["auto", "hardlink", "copy"], default="auto")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--val-batch-size", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
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
            link_mode=args.link_mode,
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
            print("[R48][Lab] dry run complete; training cannot start until data is ready.")
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
        "count_by_role": manifest["count_by_role"],
        "base_checkpoint": str(Path(args.base_checkpoint).resolve()),
        "resume_checkpoint": str(Path(args.resume_checkpoint).resolve()) if args.resume_checkpoint is not None else None,
        "resume_mode": args.resume_checkpoint is not None,
        "lab_compatible_checkpoint": CFG.RESUME_CHECKPOINT,
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "simpletest_max_epoch": CFG.SIMPLETEST_MAX_EPOCH,
        "device": CFG.DEVICE,
        "lab_psf": CFG.PSF_FITTED_PATH,
        "training_progress_root": str(LAB_TRAINING_PROGRESS_ROOT),
        "seq_stages": list(CFG.SEQ_INCLUDE_SUBDIRS),
        "boundary_geom_enable": bool(CFG.BOUNDARY_GEOM_ENABLE),
        "boundary_geom_dir": CFG.BOUNDARY_GEOM_DIR,
        "boundary_weights": {
            "boundary": CFG.BOUNDARY_LOSS_WEIGHT,
            "centerline": CFG.CENTERLINE_LOSS_WEIGHT,
            "distance_edge": CFG.DISTANCE_EDGE_LOSS_WEIGHT,
            "warmup_epoch": CFG.BOUNDARY_LOSS_WARMUP_EPOCH,
        },
        "robust_loss_percentile": CFG.ROBUST_LOSS_PERCENTILE,
        "edge_weights": {
            "w_gradmag": CFG.W_GRADMAG,
            "w_edge_ori_simple": CFG.W_EDGE_ORI_SIMPLE,
            "w_hf_lap": CFG.W_HF_LAP,
            "w_edgelocal_lap_end": CFG.W_EDGELOCAL_LAP_END,
        },
        "max_train_batches": getattr(CFG, "MAX_TRAIN_BATCHES_PER_EPOCH", None),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R48][Lab] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
