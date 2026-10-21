"""R57 geometry-constrained MOSR fine-tune launcher for LabSystem_MOSR."""
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
LAB_TRAINING_PROGRESS_ROOT = LAB_ROOT / "Traing_Progress"
LAB_CHECKPOINT_CACHE = LAB_TRAINING_PROGRESS_ROOT / "_checkpoint_cache"
LAB_PSF_PATH = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_fit"
    / "PSF_fitted_2D_FOVstack.mat"
)
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r57_geometry_constrained" / "hs100mg_basler_anchor"
DEFAULT_R55_BEST_CHECKPOINT = (
    LAB_ROOT
    / "Traing_Progress"
    / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r55_source_style_r53_scratch_formal_source_style_e050_b016_w04_nophys_20260618_002532"
    / "weights"
    / "best_tradeoff.pth.tar"
)
DEFAULT_CD_SUMMARY = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "cd_measurement_20260620_basler_ace"
    / "cd_measurement_summary_basler_50x.csv"
)

sys.path.insert(0, str(MODEL_DIR))

SEQ_8PX_STAGES = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)

PROFILE_BY_CANDIDATE = {
    "r57_geom_cd_anchor_finetune": "r57_hs100mg_r55_finetune_train",
    "r57_1_asym_cd_anchor_finetune": "r57_hs100mg_r55_finetune_train",
}

CANDIDATE_NOTES = {
    "r57_geom_cd_anchor_finetune": (
        "R55 best-tradeoff fine-tune with HS-100MG Basler geometry anchors and a required 100MG CD gate."
    ),
    "r57_1_asym_cd_anchor_finetune": (
        "R57.1 asymmetric CD correction: train on HS-100MG anchors whose source radii encode raw via-shrink and pillar-expansion bias."
    ),
}

BASE_OVERRIDES = {
    "LR": 7.5e-6,
    "WEIGHT_DECAY": 0.0,
    "SEQ_ENABLE": True,
    "SEQ_SRC_DIR": str(LAB_ROOT / "Training_Data" / "generated_convolved"),
    "SEQ_LBL_DIR": str(LAB_ROOT / "Training_Data" / "generated"),
    "SEQ_INCLUDE_SUBDIRS": SEQ_8PX_STAGES,
    "SEQ_LOSS_WEIGHT": 0.25,
    "SEQ_GRAD_WEIGHT": 0.08,
    "SEQ_GEOM_ENABLE": True,
    "SEQ_GEOM_CENTER_WEIGHT": 0.025,
    "SEQ_GEOM_RADIUS_WEIGHT": 0.015,
    "SEQ_GEOM_THICK_WEIGHT": 0.010,
    "SEQ_STEP_MAG_WEIGHT": 0.020,
    "SEQ_EVERY_N_BATCH": 2,
    "SEQ_MIN_DELTA_THRESHOLD": 0.002,
    "SEQ_WARMUP_EPOCH": 5,
    "ROBUST_LOSS_PERCENTILE": 0.92,
    "ROBUST_LOSS_WARMUP": 5,
    "TRAIN_INCLUDE_SUBDIRS": (),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "PSF_FITTED_PATH": str(LAB_PSF_PATH),
    "PHYS_FORWARD_ENABLE": False,
    "W_PHYS_MAX": 0.0,
    "BATCH_SIZE": 8,
    "VAL_BATCH_SIZE": 2,
    "NUM_WORKERS": 2,
    "DATALOADER_PERSISTENT_WORKERS": False,
    "DATALOADER_PREFETCH_FACTOR": 2,
    "CROP_SIZE": 256,
    "SEQ_BATCH_SIZE": 2,
    "MOTION_BATCH_SIZE": 2,
    "W_REC": 1.0,
    "W_GRADMAG": 0.58,
    "W_EDGE_ORI_SIMPLE": 0.20,
    "W_HF_LAP": 0.035,
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
    "W_EDGELOCAL_LAP_START": 0.0,
    "W_EDGELOCAL_LAP_END": 0.018,
    "EDGELOCAL_LAP_RAMP_E1": 6,
    "EDGELOCAL_LAP_RAMP_E2": 25,
    "BOUNDARY_GEOM_ENABLE": True,
    "BOUNDARY_GEOM_DIR": "",
    "BOUNDARY_LOSS_WEIGHT": 0.045,
    "CENTERLINE_LOSS_WEIGHT": 0.025,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.025,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 3,
    "BOUNDARY_DISTANCE_SIGMA": 2.0,
    "BOUNDARY_DISTANCE_CLIP": 8.0,
    "MOTION_ENABLE": False,
    "KD_ENABLE": False,
    "REGION_KD_ENABLE": False,
    "BEST_EPOCH_MIN": 5,
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


def _count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file()) if root.exists() else 0


def ensure_data_package(profile_name: str, output_root: Path) -> tuple[Path, dict]:
    package_dir = Path(output_root) / profile_name
    manifest = _load_manifest(package_dir / "manifest.json")
    pairs = manifest.get("pairs", [])
    total_pairs = int(manifest.get("total_pairs", -1))
    if total_pairs <= 0 or total_pairs != len(pairs):
        raise RuntimeError(f"manifest pair count mismatch in {package_dir}")
    if manifest.get("r57_geometry_constrained") is not True:
        raise RuntimeError(f"not an R57 geometry-constrained package: {package_dir}")
    for leaf in ("src", "lbl"):
        if not (package_dir / leaf).is_dir():
            raise RuntimeError(f"missing {leaf} folder in {package_dir}")
    geom_dir = Path(str(manifest.get("geom_dir", package_dir / "geom")))
    if not geom_dir.is_absolute():
        geom_dir = package_dir / geom_dir
    if manifest.get("geometry_sidecars") is not True or int(manifest.get("geometry_count", 0)) != total_pairs:
        raise RuntimeError(f"geometry sidecars are not ready in {package_dir}")
    for leaf in ("boundary", "centerline", "distance"):
        if not (geom_dir / leaf).is_dir():
            raise RuntimeError(f"missing geometry {leaf} folder in {geom_dir}")
    if _count_files(geom_dir / "boundary") < total_pairs or _count_files(geom_dir / "centerline") < total_pairs:
        raise RuntimeError(f"geometry image sidecars are incomplete in {geom_dir}")
    if _count_files(geom_dir / "distance") < total_pairs:
        raise RuntimeError(f"geometry distance sidecars are incomplete in {geom_dir}")
    return package_dir, manifest


def _set_lab_progress_root(trainer) -> None:
    if hasattr(trainer, "_set_training_progress_root"):
        trainer._set_training_progress_root(str(LAB_TRAINING_PROGRESS_ROOT))
        return
    trainer.TRAINING_PROGRESS_ROOT = str(LAB_TRAINING_PROGRESS_ROOT)


def _resolve_base_checkpoint(args: argparse.Namespace) -> Path | None:
    if bool(getattr(args, "scratch", False)):
        return None
    checkpoint = getattr(args, "base_checkpoint", None)
    if checkpoint is None:
        return DEFAULT_R55_BEST_CHECKPOINT
    return Path(checkpoint)


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path) -> None:
    _require_lab_assets()
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)
    is_r57_1 = str(args.candidate) == "r57_1_asym_cd_anchor_finetune"
    if is_r57_1:
        CFG.LR = 3e-6

    _set_lab_progress_root(trainer)
    checkpoint = _resolve_base_checkpoint(args)
    if checkpoint is not None:
        checkpoint = Path(checkpoint).resolve()
        if not checkpoint.exists():
            raise FileNotFoundError(f"base checkpoint not found: {checkpoint}")
        lab_checkpoint = prepare_lab_checkpoint(checkpoint)
        CFG.LOAD_MODEL = True
        CFG.LOAD_RESET_OPTIMIZER = True
        CFG.LOAD_RESET_EPOCH = True
        CFG.RESUME_CHECKPOINT = str(lab_checkpoint)
        CFG.LAB_SOURCE_CHECKPOINT = str(checkpoint)
    else:
        CFG.LOAD_MODEL = False
        CFG.LOAD_RESET_OPTIMIZER = False
        CFG.LOAD_RESET_EPOCH = False
        CFG.RESUME_CHECKPOINT = ""
        CFG.LAB_SOURCE_CHECKPOINT = ""

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
    if args.early_max_train_batches is not None:
        CFG.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH = int(args.early_max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH = int(args.num_epoch)
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
    if args.seq_batch_size is not None:
        CFG.SEQ_BATCH_SIZE = int(args.seq_batch_size)
    if args.lr is not None:
        CFG.LR = float(args.lr)
    if bool(getattr(args, "anchor_focus", False)) or is_r57_1:
        CFG.TRAIN_INCLUDE_SUBDIRS = (str(args.anchor_role_dir),)
        CFG.R57_ANCHOR_FOCUS = True
    else:
        CFG.R57_ANCHOR_FOCUS = False
    CFG.R57_ASYMMETRIC_CD_CORRECTION = bool(is_r57_1)

    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")
    trainer.TRAIN_GEOM_DIR = str(data_dir / "geom")
    CFG.BOUNDARY_GEOM_DIR = str(data_dir / "geom")
    CFG.R57_CD_SUMMARY = str(Path(args.cd_summary).resolve())
    CFG.R57_CD_GATE_REQUIRED = True


def _dry_run_data_missing_summary(*, args: argparse.Namespace, profile_name: str, error: Exception) -> dict:
    checkpoint = _resolve_base_checkpoint(args)
    checkpoint = checkpoint.resolve() if checkpoint is not None else None
    return {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "training_ready": False,
        "reason": "data package is not ready",
        "data_error": str(error),
        "data_root": str(Path(args.data_root).resolve()),
        "base_checkpoint": str(checkpoint) if checkpoint is not None else "",
        "base_checkpoint_exists": checkpoint.exists() if checkpoint is not None else False,
        "scratch_training": checkpoint is None,
        "num_epoch": int(args.num_epoch),
        "batch_size": int(args.batch_size),
        "val_batch_size": int(args.val_batch_size),
        "num_workers": int(args.num_workers),
        "crop_size": int(args.crop_size),
        "lab_psf": str(LAB_PSF_PATH),
        "lab_psf_exists": LAB_PSF_PATH.exists(),
        "geometry_constrained": True,
        "asymmetric_cd_correction": str(args.candidate) == "r57_1_asym_cd_anchor_finetune",
        "cd_gate_required": True,
        "cd_summary": str(Path(args.cd_summary).resolve()),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lab R57 geometry-constrained MOSR training launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=20)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=DEFAULT_R55_BEST_CHECKPOINT)
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--cd-summary", type=Path, default=DEFAULT_CD_SUMMARY)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--early-max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--val-batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--seq-batch-size", type=int, default=2)
    parser.add_argument("--anchor-focus", action="store_true")
    parser.add_argument("--anchor-role-dir", default="stage_34_hs100mg_anchor")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args, remaining = parser.parse_known_args(argv)
    sys.argv = [sys.argv[0]] + remaining

    profile_name = PROFILE_BY_CANDIDATE[args.candidate]
    try:
        data_dir, manifest = ensure_data_package(profile_name, args.data_root)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        if args.dry_run:
            print(
                json.dumps(
                    _dry_run_data_missing_summary(args=args, profile_name=profile_name, error=exc),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            print("[R57][Lab] dry run complete; training cannot start until data is ready.")
            return 0
        raise

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    configure_trainer(trainer, args, data_dir)
    CFG = trainer.CFG
    checkpoint = _resolve_base_checkpoint(args)
    summary = {
        "candidate": args.candidate,
        "note": CANDIDATE_NOTES[args.candidate],
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "base_pairs": manifest.get("base_pairs", 0),
        "anchor_pairs": manifest.get("anchor_pairs", 0),
        "geometry_count": manifest.get("geometry_count", 0),
        "base_checkpoint": str(Path(checkpoint).resolve()) if checkpoint is not None else "",
        "scratch_training": checkpoint is None,
        "lab_compatible_checkpoint": CFG.RESUME_CHECKPOINT,
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "simpletest_max_epoch": CFG.SIMPLETEST_MAX_EPOCH,
        "device": CFG.DEVICE,
        "lr": CFG.LR,
        "batch_size": CFG.BATCH_SIZE,
        "val_batch_size": CFG.VAL_BATCH_SIZE,
        "num_workers": CFG.NUM_WORKERS,
        "crop_size": CFG.CROP_SIZE,
        "lab_psf": CFG.PSF_FITTED_PATH,
        "training_progress_root": str(LAB_TRAINING_PROGRESS_ROOT),
        "seq_stages": list(CFG.SEQ_INCLUDE_SUBDIRS),
        "seq_geom_enable": bool(CFG.SEQ_GEOM_ENABLE),
        "boundary_geom_enable": bool(CFG.BOUNDARY_GEOM_ENABLE),
        "boundary_geom_dir": CFG.BOUNDARY_GEOM_DIR,
        "anchor_focus": bool(getattr(CFG, "R57_ANCHOR_FOCUS", False)),
        "asymmetric_cd_correction": bool(getattr(CFG, "R57_ASYMMETRIC_CD_CORRECTION", False)),
        "train_include_subdirs": list(getattr(CFG, "TRAIN_INCLUDE_SUBDIRS", ())),
        "phys_forward_enable": bool(CFG.PHYS_FORWARD_ENABLE),
        "w_phys_max": float(CFG.W_PHYS_MAX),
        "boundary_weights": {
            "boundary": CFG.BOUNDARY_LOSS_WEIGHT,
            "centerline": CFG.CENTERLINE_LOSS_WEIGHT,
            "distance_edge": CFG.DISTANCE_EDGE_LOSS_WEIGHT,
            "warmup_epoch": CFG.BOUNDARY_LOSS_WARMUP_EPOCH,
        },
        "seq_geom_weights": {
            "center": CFG.SEQ_GEOM_CENTER_WEIGHT,
            "radius": CFG.SEQ_GEOM_RADIUS_WEIGHT,
            "thickness": CFG.SEQ_GEOM_THICK_WEIGHT,
            "step_mag": CFG.SEQ_STEP_MAG_WEIGHT,
        },
        "edge_weights": {
            "w_gradmag": CFG.W_GRADMAG,
            "w_edge_ori_simple": CFG.W_EDGE_ORI_SIMPLE,
            "w_hf_lap": CFG.W_HF_LAP,
            "w_edgelocal_lap_end": CFG.W_EDGELOCAL_LAP_END,
        },
        "max_train_batches": getattr(CFG, "MAX_TRAIN_BATCHES_PER_EPOCH", None),
        "geometry_constrained": True,
        "cd_gate_required": True,
        "cd_summary": CFG.R57_CD_SUMMARY,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R57][Lab] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
