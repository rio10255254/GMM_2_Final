"""R60 SEM-truth boundary training launcher for LabSystem_MOSR."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
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
DEFAULT_DATA_ROOT = LAB_ROOT / "Training_Data" / "r60_sem_truth_boundary" / "hs100mg_basler"
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
DEFAULT_VAL_RATIO = 0.1

sys.path.insert(0, str(MODEL_DIR))

REAL_CROP_ROLE_DIR = "stage_60_hs100mg_real_crop"
ANCHOR_ROLE_DIR = "stage_60_hs100mg_sem_anchor"
SEQ_8PX_STAGES = (
    "stage_25_annulus_gmf_sequence_macro_clean",
    "stage_26_annulus_gmf_sequence_macro_defect",
)

CANDIDATE_SETTINGS = {
    "r60_semtruth_realcrop_anchor": {
        "profile": "r60_sem_truth_realcrop_anchor_train",
        "lr": 2.0e-6,
        "boundary": 0.065,
        "centerline": 0.038,
        "distance": 0.038,
    },
    "r60_semtruth_boundary_focus": {
        "profile": "r60_sem_truth_realcrop_anchor_train",
        "lr": 1.5e-6,
        "boundary": 0.140,
        "centerline": 0.080,
        "distance": 0.080,
        "overrides": {
            "SEQ_ENABLE": False,
            "SEQ_LOSS_WEIGHT": 0.0,
            "SEQ_GRAD_WEIGHT": 0.0,
            "SEQ_GEOM_ENABLE": False,
            "ENABLE_EDGELOCAL_LAPLACIAN": True,
            "W_EDGELOCAL_LAP_END": 0.024,
        },
    },
}
PROFILE_BY_CANDIDATE = {key: value["profile"] for key, value in CANDIDATE_SETTINGS.items()}

BASE_OVERRIDES = {
    "LR": 2.0e-6,
    "WEIGHT_DECAY": 0.0,
    "SEQ_ENABLE": True,
    "SEQ_SRC_DIR": str(LAB_ROOT / "Training_Data" / "generated_convolved"),
    "SEQ_LBL_DIR": str(LAB_ROOT / "Training_Data" / "generated"),
    "SEQ_INCLUDE_SUBDIRS": SEQ_8PX_STAGES,
    "SEQ_LOSS_WEIGHT": 0.16,
    "SEQ_GRAD_WEIGHT": 0.05,
    "SEQ_GEOM_ENABLE": True,
    "SEQ_GEOM_CENTER_WEIGHT": 0.016,
    "SEQ_GEOM_RADIUS_WEIGHT": 0.014,
    "SEQ_GEOM_THICK_WEIGHT": 0.006,
    "SEQ_STEP_MAG_WEIGHT": 0.010,
    "SEQ_EVERY_N_BATCH": 2,
    "SEQ_MIN_DELTA_THRESHOLD": 0.002,
    "SEQ_WARMUP_EPOCH": 2,
    "ROBUST_LOSS_PERCENTILE": 0.95,
    "ROBUST_LOSS_WARMUP": 1,
    "TRAIN_INCLUDE_SUBDIRS": (REAL_CROP_ROLE_DIR, ANCHOR_ROLE_DIR),
    "TRAIN_EXCLUDE_SUBDIRS": (),
    "PSF_FITTED_PATH": str(LAB_PSF_PATH),
    "PHYS_FORWARD_ENABLE": False,
    "W_PHYS_MAX": 0.0,
    "BATCH_SIZE": 4,
    "VAL_BATCH_SIZE": 2,
    "NUM_WORKERS": 2,
    "DATALOADER_PERSISTENT_WORKERS": False,
    "DATALOADER_PREFETCH_FACTOR": 2,
    "CROP_SIZE": 256,
    "SEQ_BATCH_SIZE": 2,
    "MOTION_BATCH_SIZE": 2,
    "W_REC": 1.0,
    "W_GRADMAG": 0.52,
    "W_EDGE_ORI_SIMPLE": 0.15,
    "W_HF_LAP": 0.030,
    "ENABLE_EDGELOCAL_LAPLACIAN": True,
    "W_EDGELOCAL_LAP_START": 0.0,
    "W_EDGELOCAL_LAP_END": 0.016,
    "EDGELOCAL_LAP_RAMP_E1": 1,
    "EDGELOCAL_LAP_RAMP_E2": 5,
    "BOUNDARY_GEOM_ENABLE": True,
    "BOUNDARY_GEOM_DIR": "",
    "BOUNDARY_LOSS_WEIGHT": 0.065,
    "CENTERLINE_LOSS_WEIGHT": 0.038,
    "DISTANCE_EDGE_LOSS_WEIGHT": 0.038,
    "BOUNDARY_LOSS_WARMUP_EPOCH": 0,
    "BOUNDARY_DISTANCE_SIGMA": 2.0,
    "BOUNDARY_DISTANCE_CLIP": 8.0,
    "MOTION_ENABLE": False,
    "KD_ENABLE": False,
    "REGION_KD_ENABLE": False,
    "BEST_EPOCH_MIN": 1,
    "BEST_EPOCH_MAX": 999,
    "WEAK_PSF_BETA_INIT": 0.0,
    "WEAK_PSF_BETA_SCALE_MAX": 0.0,
    "WEAK_PSF_LR_MULT": 0.0,
}

PSF_BUFFER_KEYS = (
    "physics_layer.PSFs",
    "physics_layer.PSF_mean",
    "physics_layer.PSF_center",
    "weak_psf_block.PSFs",
)
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


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


def _rel_norm(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _path_matches_include(path: Path, include_subdirs: tuple[str, ...]) -> bool:
    if not include_subdirs:
        return True
    parts = {part.lower() for part in path.parts}
    return any(tag.lower() in parts for tag in include_subdirs)


def _collect_package_src_rels(package_dir: Path, include_subdirs: tuple[str, ...]) -> list[str]:
    package_dir = Path(package_dir)
    src_root = package_dir / "src"
    paths = []
    for path in src_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if not _path_matches_include(path, include_subdirs):
            continue
        paths.append(str(path.resolve()))
    paths = sorted(paths)
    return [_rel_norm(Path(path).relative_to(package_dir.resolve())) for path in paths]


def _fallback_repeatless_stem(package_src: str) -> str:
    stem = Path(package_src).stem
    return re.sub(r"_r\d+_\d+$", "", stem, flags=re.IGNORECASE)


def group_key_for_manifest_pair(pair: dict) -> str:
    source_group = str(pair.get("source_group", "")).strip().lower()
    domain = str(pair.get("domain", "")).strip().lower()
    feature = str(pair.get("feature", pair.get("feature_display", "unknown"))).strip().lower() or "unknown"
    if source_group == "hs100mg_real_crop" or domain == "real_microscope_crop":
        template_id = pair.get("template_id", pair.get("sem_reference_id", None))
        if template_id is None:
            template_id = _fallback_repeatless_stem(str(pair.get("package_src", "")))
        return f"real:{feature}:template:{template_id}"
    if source_group == "hs100mg_sem_anchor" or domain == "synthetic_sem_anchor":
        sem_reference_id = pair.get("sem_reference_id", None)
        if sem_reference_id is None:
            sem_reference_id = _fallback_repeatless_stem(str(pair.get("package_src", "")))
        return f"anchor:{feature}:sem:{sem_reference_id}"
    return f"single:{feature}:{_rel_norm(str(pair.get('package_src', 'unknown')))}"


def _split_groups(
    group_to_indices: dict[str, list[int]],
    *,
    group_to_stratum: dict[str, str],
    total_count: int,
    val_ratio: float,
    seed: int,
) -> tuple[list[int], list[int]]:
    val_ratio = max(0.0, min(0.95, float(val_ratio)))
    group_keys = sorted(group_to_indices)
    rng = random.Random(int(seed))
    rng.shuffle(group_keys)
    if val_ratio <= 0.0 or len(group_keys) <= 1:
        return list(range(total_count)), []

    target_val = max(1, int(round(total_count * val_ratio)))
    val_groups: list[str] = []
    groups_by_stratum: dict[str, list[str]] = {}
    for key in group_keys:
        groups_by_stratum.setdefault(group_to_stratum.get(key, "unknown:unknown"), []).append(key)

    for stratum in sorted(groups_by_stratum):
        candidates = groups_by_stratum[stratum][:]
        rng.shuffle(candidates)
        for key in candidates:
            if key not in val_groups:
                val_groups.append(key)
                break

    val_count = 0
    for key in val_groups:
        val_count += len(group_to_indices[key])
    for key in group_keys:
        if len(val_groups) >= len(group_keys) - 1:
            break
        if val_count >= target_val:
            break
        if key in val_groups:
            continue
        val_groups.append(key)
        val_count += len(group_to_indices[key])

    val_group_set = set(val_groups)
    train_idx: list[int] = []
    val_idx: list[int] = []
    for key in sorted(group_to_indices):
        target = val_idx if key in val_group_set else train_idx
        target.extend(group_to_indices[key])
    return sorted(train_idx), sorted(val_idx)


def prepare_grouped_fixed_split(
    *,
    package_dir: Path,
    manifest: dict,
    include_subdirs: tuple[str, ...],
    val_ratio: float,
    seed: int,
) -> dict:
    package_dir = Path(package_dir).resolve()
    src_rels = _collect_package_src_rels(package_dir, include_subdirs)
    if not src_rels:
        raise RuntimeError(f"No source images available for grouped split in {package_dir}")

    pair_by_src = {
        _rel_norm(pair.get("package_src", "")): pair
        for pair in manifest.get("pairs", [])
        if pair.get("package_src")
    }
    missing = [rel for rel in src_rels if rel not in pair_by_src]
    if missing:
        raise RuntimeError(f"manifest is missing {len(missing)} source paths required for grouped split; first={missing[0]}")

    group_to_indices: dict[str, list[int]] = {}
    source_groups: dict[str, str] = {}
    group_to_stratum: dict[str, str] = {}
    for idx, rel in enumerate(src_rels):
        pair = pair_by_src[rel]
        key = group_key_for_manifest_pair(pair)
        source_group = str(pair.get("source_group", pair.get("domain", "unknown"))).strip() or "unknown"
        feature = str(pair.get("feature", pair.get("feature_display", "unknown"))).strip().lower() or "unknown"
        stratum = f"{source_group}:{feature}"
        group_to_indices.setdefault(key, []).append(idx)
        source_groups[key] = source_group
        group_to_stratum[key] = stratum

    train_idx, val_idx = _split_groups(
        group_to_indices,
        group_to_stratum=group_to_stratum,
        total_count=len(src_rels),
        val_ratio=val_ratio,
        seed=seed,
    )

    index_to_group = {}
    for key, indices in group_to_indices.items():
        for idx in indices:
            index_to_group[int(idx)] = key
    train_groups = {index_to_group[int(i)] for i in train_idx}
    val_groups = {index_to_group[int(i)] for i in val_idx}
    overlap = sorted(train_groups & val_groups)
    train_strata = sorted({group_to_stratum[group] for group in train_groups})
    val_strata = sorted({group_to_stratum[group] for group in val_groups})

    import numpy as np

    val_tag = int(round(max(0.0, min(0.95, float(val_ratio))) * 1000.0))
    split_dir = package_dir / "splits" / f"grouped_seed{int(seed):04d}_val{val_tag:03d}"
    split_dir.mkdir(parents=True, exist_ok=True)
    np.save(split_dir / "train_idx.npy", np.asarray(train_idx, dtype=np.int64))
    np.save(split_dir / "val_idx.npy", np.asarray(val_idx, dtype=np.int64))

    meta = {
        "split_type": "manifest_grouped_fixed_split",
        "seed": int(seed),
        "val_ratio": float(max(0.0, min(0.95, float(val_ratio)))),
        "source_path_count": int(len(src_rels)),
        "train_count": int(len(train_idx)),
        "val_count": int(len(val_idx)),
        "group_count": int(len(group_to_indices)),
        "train_group_count": int(len(train_groups)),
        "val_group_count": int(len(val_groups)),
        "stratified_by": "source_group:feature",
        "train_strata": train_strata,
        "val_strata": val_strata,
        "group_overlap_count": int(len(overlap)),
        "group_overlap_examples": overlap[:10],
        "include_subdirs": list(include_subdirs),
        "source_groups": {
            key: source_groups[key]
            for key in sorted(source_groups)
        },
        "source_paths_sorted": src_rels,
    }
    (split_dir / "split_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    if overlap:
        raise RuntimeError(f"grouped split leaked {len(overlap)} groups across train/val")
    return {"split_dir": str(split_dir), **meta}


def ensure_data_package(profile_name: str, data_root: Path) -> tuple[Path, dict]:
    package_dir = Path(data_root) / profile_name
    manifest = _load_manifest(package_dir / "manifest.json")
    pairs = manifest.get("pairs", [])
    total_pairs = int(manifest.get("total_pairs", -1))
    if total_pairs <= 0 or total_pairs != len(pairs):
        raise RuntimeError(f"manifest pair count mismatch in {package_dir}")
    if manifest.get("r60_sem_truth_boundary_training") is not True:
        raise RuntimeError(f"not an R60 SEM-truth package: {package_dir}")
    if manifest.get("target_is_sem_truth") is not True:
        raise RuntimeError(f"R60 package target is not marked SEM truth: {package_dir}")
    if int(manifest.get("real_crop_pairs", 0)) <= 0:
        raise RuntimeError(f"R60 package has no real microscope crops: {package_dir}")
    if int(manifest.get("anchor_pairs", 0)) <= 0:
        raise RuntimeError(f"R60 package has no SEM anchor pairs: {package_dir}")
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


def configure_trainer(trainer, args: argparse.Namespace, data_dir: Path, fixed_split_dir: Path | None = None) -> None:
    _require_lab_assets()
    CFG = trainer.CFG
    for key, val in BASE_OVERRIDES.items():
        setattr(CFG, key, val)

    settings = CANDIDATE_SETTINGS[str(args.candidate)]
    CFG.LR = float(settings["lr"])
    CFG.BOUNDARY_LOSS_WEIGHT = float(settings["boundary"])
    CFG.CENTERLINE_LOSS_WEIGHT = float(settings["centerline"])
    CFG.DISTANCE_EDGE_LOSS_WEIGHT = float(settings["distance"])
    for key, val in dict(settings.get("overrides", {})).items():
        setattr(CFG, key, val)

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
    CFG.BEST_EPOCH_MAX = int(args.num_epoch)
    CFG.DEVICE = str(args.device)

    if args.max_train_batches is not None:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH = int(args.num_epoch)
    if args.val_ratio is not None:
        CFG.VAL_RATIO = float(args.val_ratio)
    if args.lr is not None:
        CFG.LR = float(args.lr)
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

    CFG.TRAIN_INCLUDE_SUBDIRS = (str(args.real_crop_role_dir), str(args.anchor_role_dir))
    CFG.R60_SEM_TRUTH_BOUNDARY = True
    CFG.R60_TARGET_IS_SEM_TRUTH = True
    CFG.R60_CD_SELECTION_REQUIRED = True
    CFG.R60_CD_SUMMARY = str(Path(args.cd_summary).resolve())
    if fixed_split_dir is not None:
        CFG.REPRO_MODE = True
        CFG.REPRO_FORCE_FIXED_SPLIT = False
        CFG.FIXED_SPLIT_DIR = str(Path(fixed_split_dir).resolve())
    else:
        CFG.FIXED_SPLIT_DIR = ""
    trainer.TRAIN_SRC_DIR = str(data_dir / "src")
    trainer.TRAIN_LBL_DIR = str(data_dir / "lbl")
    trainer.TRAIN_GEOM_DIR = str(data_dir / "geom")
    CFG.BOUNDARY_GEOM_DIR = str(data_dir / "geom")


def _dry_run_data_missing_summary(*, args: argparse.Namespace, profile_name: str, error: Exception) -> dict:
    checkpoint = _resolve_base_checkpoint(args)
    checkpoint = checkpoint.resolve() if checkpoint is not None else None
    return {
        "candidate": args.candidate,
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
        "sem_truth_boundary_training": True,
        "target_is_sem_truth": True,
        "cd_selection_required": True,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lab R60 SEM-truth boundary training launcher")
    parser.add_argument("--candidate", required=True, choices=sorted(PROFILE_BY_CANDIDATE))
    parser.add_argument("--num-epoch", type=int, default=12)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--base-checkpoint", type=Path, default=DEFAULT_R55_BEST_CHECKPOINT)
    parser.add_argument("--scratch", action="store_true")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--cd-summary", type=Path, default=DEFAULT_CD_SUMMARY)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--val-ratio", type=float, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--val-batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--crop-size", type=int, default=256)
    parser.add_argument("--seq-batch-size", type=int, default=2)
    parser.add_argument("--real-crop-role-dir", default=REAL_CROP_ROLE_DIR)
    parser.add_argument("--anchor-role-dir", default=ANCHOR_ROLE_DIR)
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
            print(json.dumps(_dry_run_data_missing_summary(args=args, profile_name=profile_name, error=exc), indent=2, ensure_ascii=False))
            print("[R60][Lab] dry run complete; training cannot start until data is ready.")
            return 0
        raise

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    split_val_ratio = float(args.val_ratio) if args.val_ratio is not None else DEFAULT_VAL_RATIO
    split_info = prepare_grouped_fixed_split(
        package_dir=data_dir,
        manifest=manifest,
        include_subdirs=(str(args.real_crop_role_dir), str(args.anchor_role_dir)),
        val_ratio=split_val_ratio,
        seed=1337,
    )

    configure_trainer(trainer, args, data_dir, fixed_split_dir=Path(split_info["split_dir"]))
    CFG = trainer.CFG
    checkpoint = _resolve_base_checkpoint(args)
    summary = {
        "candidate": args.candidate,
        "profile": profile_name,
        "data_dir": str(data_dir),
        "total_pairs": manifest["total_pairs"],
        "real_crop_pairs": manifest.get("real_crop_pairs", 0),
        "anchor_pairs": manifest.get("anchor_pairs", 0),
        "geometry_count": manifest.get("geometry_count", 0),
        "target_is_sem_truth": bool(manifest.get("target_is_sem_truth", False)),
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
        "training_progress_root": str(LAB_TRAINING_PROGRESS_ROOT),
        "train_include_subdirs": list(CFG.TRAIN_INCLUDE_SUBDIRS),
        "fixed_split_dir": CFG.FIXED_SPLIT_DIR,
        "fixed_split_type": split_info["split_type"],
        "fixed_split_group_overlap_count": split_info["group_overlap_count"],
        "fixed_split_train_count": split_info["train_count"],
        "fixed_split_val_count": split_info["val_count"],
        "fixed_split_group_count": split_info["group_count"],
        "boundary_geom_enable": bool(CFG.BOUNDARY_GEOM_ENABLE),
        "boundary_geom_dir": CFG.BOUNDARY_GEOM_DIR,
        "phys_forward_enable": bool(CFG.PHYS_FORWARD_ENABLE),
        "w_phys_max": float(CFG.W_PHYS_MAX),
        "weak_psf_beta_scale_max": float(CFG.WEAK_PSF_BETA_SCALE_MAX),
        "boundary_weights": {
            "boundary": CFG.BOUNDARY_LOSS_WEIGHT,
            "centerline": CFG.CENTERLINE_LOSS_WEIGHT,
            "distance_edge": CFG.DISTANCE_EDGE_LOSS_WEIGHT,
            "warmup_epoch": CFG.BOUNDARY_LOSS_WARMUP_EPOCH,
        },
        "sem_truth_boundary_training": True,
        "cd_selection_required": True,
        "selection_metric": "post_reconstruction_cd_error_vs_sem",
        "internal_best_tradeoff_is_not_adoption_gate": True,
        "cd_summary": CFG.R60_CD_SUMMARY,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("[R60][Lab] dry run complete; training was not started.")
        return 0

    trainer.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
