"""R83 launcher: conservative fine-tuning from an exact R79 epoch-23 EMA seed."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = EXPERIMENT_DIR / "model"
TRAINER_RUNTIME_DIR = EXPERIMENT_DIR / "training" / "runtime"
SCRIPT_DIR = Path(__file__).resolve().parent
PROGRESS_ROOT = EXPERIMENT_DIR / "runs"
WEIGHTS_ROOT = EXPERIMENT_DIR / "weights"
CONFIG = json.loads((EXPERIMENT_DIR / "config" / "experiment.json").read_text(encoding="utf-8"))
CONTRACT = json.loads((EXPERIMENT_DIR / "config" / "architecture_contract.json").read_text(encoding="utf-8"))
DATA_ROOT = EXPERIMENT_DIR / "data"
LIVE_CONFIG = CONFIG["live_validation"]
CANDIDATES = CONFIG["training"]["candidates"]

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(TRAINER_RUNTIME_DIR))
sys.path.insert(0, str(MODEL_DIR))

from r83_dataset import audit_package, build_package  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def experiment_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (EXPERIMENT_DIR / path).resolve()


def configured_live_paths() -> list[Path]:
    return [experiment_path(row["relative_image_path"]) for row in LIVE_CONFIG["images"]]


def ensure_package(profile: str, build_data: bool, force_data: bool) -> tuple[Path, dict, dict]:
    package = DATA_ROOT / f"r83_{profile}_severe_microscopy"
    if build_data:
        return build_package(profile, DATA_ROOT, force=force_data)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    return package, manifest, audit_package(package, manifest)


def prepare_monitor(package: Path, manifest: dict) -> Path:
    row = next((item for item in manifest["pairs"] if item["split"] == "train"), None)
    if row is None:
        raise RuntimeError("R83 training package has no training record")
    target = package / "runtime" / "Test_Image" / "r83_synthetic_monitor.bmp"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(package / row["package_src"], target)
    return target


def set_progress_root(trainer) -> None:
    PROGRESS_ROOT.mkdir(parents=True, exist_ok=True)
    if hasattr(trainer, "_set_training_progress_root"):
        trainer._set_training_progress_root(str(PROGRESS_ROOT))
    else:
        trainer.TRAINING_PROGRESS_ROOT = str(PROGRESS_ROOT)


def assert_runtime_contract(trainer) -> dict:
    files = {
        "architecture_source": experiment_path(CONTRACT["architecture_source"]),
        "utility_source": experiment_path(CONTRACT["utility_source"]),
        "analytic_psf_source": experiment_path(CONTRACT["analytic_psf_source"]),
        "trainer_source": Path(trainer.__file__).resolve(),
    }
    violations = []
    hashes = {}
    for key, path in files.items():
        hashes[key] = sha256(path)
        expected = CONTRACT[f"{key}_sha256"]
        if hashes[key] != expected:
            violations.append(f"{key} changed")
    if files["trainer_source"] != experiment_path(CONTRACT["trainer_source"]):
        violations.append("a non-local trainer was imported")
    if violations:
        raise RuntimeError("R83 runtime contract failed: " + "; ".join(violations))
    return {"passed": True, "hashes": hashes}


def assert_seed_checkpoint() -> dict:
    parent = CONFIG["parent_model"]
    source = experiment_path(parent["checkpoint"])
    seed = experiment_path(parent["seed_checkpoint"])
    if not source.is_file():
        raise FileNotFoundError(f"R79 source checkpoint is missing: {source}")
    if sha256(source) != parent["checkpoint_sha256"]:
        raise RuntimeError("R79 source checkpoint hash changed")
    if not seed.is_file():
        raise FileNotFoundError(
            f"R83 reset seed is missing: {seed}. Run scripts/prepare_r83_seed.py first."
        )
    checkpoint = torch.load(seed, map_location="cpu")
    if int(checkpoint.get("epoch", -1)) != 0:
        raise RuntimeError("R83 reset seed epoch is not zero")
    state = checkpoint.get("state_dict")
    ema = checkpoint.get("ema_state_dict")
    if not isinstance(state, dict) or not isinstance(ema, dict):
        raise RuntimeError("R83 reset seed does not contain both train and EMA states")
    if set(state) != set(ema):
        raise RuntimeError("R83 reset seed state keys differ")
    max_difference = max(float(torch.max(torch.abs(state[key].float() - ema[key].float())).item()) for key in state)
    if max_difference != 0.0:
        raise RuntimeError(f"R83 reset train/EMA states differ by {max_difference}")
    return {
        "passed": True,
        "source_checkpoint": str(source),
        "source_sha256": parent["checkpoint_sha256"],
        "seed_checkpoint": str(seed),
        "seed_sha256": sha256(seed),
        "state_key_count": len(state),
        "train_ema_max_abs_difference": max_difference,
    }


def configure_trainer(trainer, args: argparse.Namespace, package: Path, manifest: dict) -> None:
    cfg = trainer.CFG
    candidate = CANDIDATES[args.candidate]
    monitor = prepare_monitor(package, manifest)
    trainer.SCRIPT_DIR = str(monitor.parents[1])
    set_progress_root(trainer)

    cfg.LOAD_MODEL = False
    cfg.RESUME_CHECKPOINT = str(experiment_path(CONFIG["parent_model"]["seed_checkpoint"]))
    cfg.LOAD_RESET_OPTIMIZER = True
    cfg.LOAD_RESET_EPOCH = True
    cfg.PRETRAINED_PATH = ""
    cfg.PRETRAINED_FALLBACK_PATH = ""
    cfg.LAB_SOURCE_CHECKPOINT = ""
    cfg.TRAINABLE_NAME_PATTERNS = tuple(candidate["trainable_name_patterns"])

    cfg.KD_ENABLE = False
    cfg.KD_COMBO_PATH = ""
    cfg.KD_R40_PATH = ""
    cfg.KD_WEIGHT_COMBO = 0.0
    cfg.KD_WEIGHT_R40 = 0.0
    cfg.REGION_KD_ENABLE = False
    cfg.REGION_KD_TEACHER_PATH = ""
    cfg.REGION_KD_WEIGHT = 0.0
    cfg.SEQ_ENABLE = False
    cfg.SEQ_SRC_DIR = ""
    cfg.SEQ_LBL_DIR = ""
    cfg.SEQ_INCLUDE_SUBDIRS = ()
    cfg.SEQ_LOSS_WEIGHT = 0.0
    cfg.SEQ_GEOM_ENABLE = False
    cfg.SEQ_VAL_ENABLE = False
    cfg.MOTION_ENABLE = False
    cfg.MOTION_SRC_DIR = ""
    cfg.MOTION_LBL_DIR = ""
    cfg.MOTION_GEOM_DIR = ""
    cfg.MOTION_META_DIR = ""
    cfg.MOTION_INCLUDE_SUBDIRS = ()
    cfg.MOTION_LOSS_WEIGHT = 0.0

    cfg.USE_UPSAMPLE_CONV = True
    cfg.USE_BAND_LIMIT = False
    cfg.LEARNABLE_BLUR = False
    cfg.USE_BOTTLENECK_SE = False
    cfg.BOUNDARY_RESIDUAL_ADAPTER_ENABLE = True
    cfg.BOUNDARY_RESIDUAL_ADAPTER_HIDDEN = 16
    cfg.BOUNDARY_RESIDUAL_ADAPTER_MAX = 0.018
    cfg.BOUNDARY_RESIDUAL_ADAPTER_GATE_BIAS = -2.0
    cfg.BOUNDARY_RESIDUAL_ADAPTER_DELTA_BIAS = True
    cfg.BOUNDARY_RESIDUAL_ADAPTER_ZERO_MEAN = False
    cfg.BOUNDARY_RESIDUAL_ADAPTER_EDGE_GATE = False
    cfg.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT = False
    cfg.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS = True
    cfg.RAW_ANCHOR_OUTPUT_MODE = "none"
    cfg.QUALITY_GATE_ENABLE = False

    psf_path = package / manifest["analytic_psf"]["relative_path"]
    cfg.PSF_FITTED_PATH = str(psf_path)
    cfg.PSF_GRID_ROWS = 3
    cfg.PSF_GRID_COLS = 3
    cfg.PSF_USE_STACK_MEAN = True
    cfg.PSF_DECONV_REG = 30.0
    cfg.PSF_PHYS_ALPHA_INIT = 0.05
    cfg.PSF_PHYS_ALPHA_MIN = 0.0
    cfg.PSF_PHYS_ALPHA_MAX = 0.20
    cfg.PSF_PHYS_TRAINABLE_REG = False
    cfg.PHYSICS_LR_MULT = 0.10
    cfg.PHYS_FORWARD_ENABLE = False
    cfg.W_PHYS_MAX = 0.0
    cfg.WEAK_PSF_ENABLE = True
    cfg.WEAK_PSF_K = 4
    cfg.WEAK_PSF_BETA_INIT = 0.0
    cfg.WEAK_PSF_BETA_SCALE_MAX = 0.0
    cfg.WEAK_PSF_BETA_SCALE_STAGE1 = 0.0
    cfg.WEAK_PSF_BETA_SCALE_STAGE2 = 0.0
    cfg.WEAK_PSF_BETA_SCALE_STAGE3 = 0.0
    cfg.WEAK_PSF_LR_MULT = 0.0
    cfg.WEAK_PSF_LR_MULT_STAGE1 = 0.0
    cfg.WEAK_PSF_LR_MULT_STAGE2 = 0.0
    cfg.WEAK_PSF_LR_MULT_STAGE3 = 0.0
    cfg.WEAK_PSF_GUARD_ENABLE = False
    cfg.ENABLE_PSF_GUARD_ONLY = False
    cfg.WEAK_PSF_PRESERVE_LOADED_STATE = True

    cfg.TRAIN_INCLUDE_SUBDIRS = (str(CONFIG["dataset"]["stage_name"]),)
    cfg.TRAIN_EXCLUDE_SUBDIRS = ()
    cfg.TRAIN_GROUP_BALANCED_SAMPLER = True
    cfg.TRAIN_GROUP_BALANCE_MANIFEST = str(package / "manifest.json")
    cfg.TRAIN_GROUP_BALANCE_KEYS = tuple(CONFIG["training"]["group_balancing_keys"])
    cfg.TRAIN_GROUP_BALANCE_NUM_SAMPLES_MULT = 1.0
    cfg.BOUNDARY_GEOM_ENABLE = False
    cfg.BOUNDARY_GEOM_DIR = ""
    cfg.FIXED_SPLIT_DIR = str(package / manifest["fixed_split_dir"])
    cfg.VAL_RATIO = 0.1

    cfg.W_REC = 1.0
    cfg.W_GRADMAG = 0.45
    cfg.W_EDGE_ORI_SIMPLE = 0.10
    cfg.W_HF_LAP = 0.02
    cfg.W_EDGELOCAL_LAP_START = 0.0
    cfg.W_EDGELOCAL_LAP_END = 0.0
    cfg.BOUNDARY_LOSS_WEIGHT = 0.0
    cfg.CENTERLINE_LOSS_WEIGHT = 0.0
    cfg.DISTANCE_EDGE_LOSS_WEIGHT = 0.0
    cfg.BOUNDARY_POSITION_LOSS_WEIGHT = 0.0
    cfg.IDENTITY_GUARD_ENABLE = False
    cfg.INPUT_LOWFREQ_WEIGHT = 0.05
    cfg.INPUT_LOWFREQ_SIGMA = 2.0
    cfg.GMF_VALIDATE_ENABLE = False
    # Very-low-contrast procedural monitors are valid R83 inputs.  The legacy
    # 0.02 standard-deviation threshold incorrectly marks them as collapsed.
    cfg.COLLAPSE_STD_MIN = 0.005
    cfg.COLLAPSE_SAT_THRESH = 0.95
    cfg.COLLAPSE_HF_RATIO_MAX = 0.90

    seed = int(args.seed)
    cfg.SPLIT_SEED = seed
    cfg.REPRO_SEED = seed
    cfg.SEED_ACTIVE = seed
    cfg.SEED_DETERMINISTIC = True
    cfg.REPRO_MODE = True
    cfg.REPRO_FORCE_FIXED_SPLIT = False
    cfg.REPRO_NUM_WORKERS = int(args.num_workers)
    cfg.REPRO_DISABLE_AMP = True
    cfg.REPRO_DISABLE_TF32 = True
    cfg.REPRO_DETERMINISTIC = True
    cfg.REPRO_STRICT_DETERMINISTIC = False
    cfg.SEED_SWEEP_ENABLE = False
    cfg.use_amp = False
    cfg.EMA_ENABLE = True
    cfg.EMA_DECAY = 0.997
    cfg.EMA_START_EPOCH = 1

    suffix = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(args.run_suffix))
    suffix = f"_{suffix}" if suffix else ""
    cfg.MODEL_NAME = f"LAB_GESR_v1_v5_R83_r79e23_{args.candidate}_{args.profile}_seed{seed}{suffix}"
    trainer.MODEL_NAME_BASE = cfg.MODEL_NAME
    cfg.NUM_EPOCH = int(args.num_epoch)
    cfg.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    cfg.BEST_EPOCH_MIN = 1
    cfg.BEST_EPOCH_MAX = int(args.num_epoch)
    cfg.DEVICE = str(args.device)
    cfg.LR = float(args.lr)
    cfg.WEIGHT_DECAY = 0.0
    cfg.BATCH_SIZE = int(args.batch_size)
    cfg.VAL_BATCH_SIZE = int(args.val_batch_size)
    cfg.NUM_WORKERS = int(args.num_workers)
    cfg.CROP_SIZE = int(CONFIG["training"]["crop_size"])
    cfg.DATALOADER_PERSISTENT_WORKERS = False
    cfg.FAST_IO_MODE = True
    cfg.FAST_DISABLE_PLOTS = True
    cfg.FAST_VAL_EVERY_EPOCH = 1 if args.profile != "formal" else 2
    cfg.FAST_MONITOR_EVERY_EPOCH = 2
    cfg.EXTERNAL_VISUAL_MONITOR_ENABLE = not args.disable_live_validation
    cfg.EXTERNAL_VISUAL_MONITOR_PATH = str(Path(args.live_validation_dir).resolve()) if not args.disable_live_validation else ""
    cfg.EXTERNAL_VISUAL_MONITOR_EVERY_N_EPOCHS = int(args.live_validation_every)
    cfg.EXTERNAL_VISUAL_MONITOR_OUTPUT_DIR = "live_validation"
    cfg.SAVE_MONITOR_EVERY_EPOCH = True
    cfg.RUN_PREFLIGHT_SANITY = False
    cfg.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches or 0)
    cfg.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches or 0)
    cfg.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH = int(args.num_epoch) if args.max_train_batches else 0

    trainer.TRAIN_SRC_DIR = str(package / "src")
    trainer.TRAIN_LBL_DIR = str(package / "lbl")
    trainer.TRAIN_GEOM_DIR = ""


def assert_finetune_lock(trainer, package: Path, manifest: dict, args: argparse.Namespace) -> dict:
    cfg = trainer.CFG
    violations = []
    expected_seed = experiment_path(CONFIG["parent_model"]["seed_checkpoint"])
    if Path(str(cfg.RESUME_CHECKPOINT)).resolve() != expected_seed:
        violations.append("resume checkpoint is not the locked R79 EMA reset seed")
    if not cfg.LOAD_RESET_EPOCH or not cfg.LOAD_RESET_OPTIMIZER:
        violations.append("epoch or optimizer reset is disabled")
    if cfg.KD_ENABLE or cfg.REGION_KD_ENABLE or cfg.SEQ_ENABLE or cfg.MOTION_ENABLE:
        violations.append("an unapproved teacher, sequence, or motion path is enabled")
    expected_patterns = tuple(CANDIDATES[args.candidate]["trainable_name_patterns"])
    if tuple(cfg.TRAINABLE_NAME_PATTERNS) != expected_patterns:
        violations.append("trainable layer lock changed")
    if cfg.BOUNDARY_GEOM_ENABLE:
        violations.append("clean geometry loss conflicts with ambiguity-aware targets")
    if cfg.QUALITY_GATE_ENABLE:
        violations.append("unapproved image-quality gate is enabled")
    if not bool(getattr(cfg, "WEAK_PSF_PRESERVE_LOADED_STATE", False)):
        violations.append("loaded R79 weak-PSF state is not protected")
    audit = audit_package(package, manifest)
    if not audit["passed"]:
        violations.append("procedural source audit failed")
    live_root = (EXPERIMENT_DIR / "data" / "live_validation").resolve()
    for path in configured_live_paths():
        if not path.is_file() or not path.is_relative_to(live_root):
            violations.append(f"invalid live observation image: {path.name}")
    if Path(trainer.TRAIN_SRC_DIR).resolve().is_relative_to(live_root):
        violations.append("live observation pixels entered training")
    if violations:
        raise RuntimeError("R83 fine-tune lock failed: " + "; ".join(violations))
    return {
        "passed": True,
        "candidate": args.candidate,
        "trainable_name_patterns": list(expected_patterns),
        "checkpoint_loading": "locked_r79e23_ema_reset_seed",
        "teacher_models": False,
        "real_training_pixels": False,
        "quality_gate": False,
        "weak_psf_loaded_state_preserved": True,
        "geometry_loss": False,
        "source_audit": audit,
    }


def verify_model_seed(trainer, package: Path, args: argparse.Namespace) -> dict:
    requested_device, requested_amp = trainer.CFG.DEVICE, trainer.CFG.use_amp
    trainer.CFG.DEVICE, trainer.CFG.use_amp = "cpu", False
    model = trainer._build_model_from_cfg()
    checkpoint = torch.load(experiment_path(CONFIG["parent_model"]["seed_checkpoint"]), map_location="cpu")
    state = checkpoint["state_dict"]
    model.load_state_dict(state, strict=True)
    parameter_count = sum(int(p.numel()) for p in model.parameters())
    trainable = {name: int(p.numel()) for name, p in model.named_parameters() if p.requires_grad}
    patterns = tuple(CANDIDATES[args.candidate]["trainable_name_patterns"])
    if not trainable or any(not any(pattern in name for pattern in patterns) for name in trainable):
        raise RuntimeError(f"R83 trainable-layer audit failed: {sorted(trainable)[:10]}")
    if parameter_count != int(CONTRACT["expected_parameter_count"]):
        raise RuntimeError(f"R83 architecture parameter count changed: {parameter_count}")
    for name, count in CONTRACT["expected_fixed_architecture_kernels"].items():
        parameter = dict(model.named_parameters()).get(name)
        if parameter is None or int(parameter.numel()) != int(count) or parameter.requires_grad:
            raise RuntimeError(f"Fixed shift-safe kernel changed: {name}")
    monitor_path = package / "runtime" / "Test_Image" / "r83_synthetic_monitor.bmp"
    monitor = cv2.imdecode(np.fromfile(monitor_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    tensor = torch.from_numpy(cv2.resize(monitor, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0)[None, None]
    model.eval()
    with torch.no_grad():
        output = model(tensor)
    if tuple(output.shape) != (1, 1, 64, 64) or not bool(torch.isfinite(output).all()):
        raise RuntimeError("R83 seed forward check failed")
    report = {
        "passed": True,
        "candidate": args.candidate,
        "parameter_count": parameter_count,
        "trainable_parameter_count": sum(trainable.values()),
        "trainable_parameter_names": sorted(trainable),
        "seed_checkpoint_sha256": sha256(experiment_path(CONFIG["parent_model"]["seed_checkpoint"])),
        "forward_output_range": [float(output.min()), float(output.max())],
    }
    report_path = EXPERIMENT_DIR / "reports" / f"model_seed_audit_{args.candidate}_{args.profile}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    trainer.CFG.DEVICE, trainer.CFG.use_amp = requested_device, requested_amp
    return report


def export_run(run_dir: Path, args: argparse.Namespace, manifest: dict) -> dict:
    source_dir = run_dir / "weights"
    if not (source_dir / "best_tradeoff.pth.tar").is_file():
        raise RuntimeError("Training finished without best_tradeoff.pth.tar")
    destination = WEIGHTS_ROOT / args.profile / args.candidate / f"seed_{args.seed}" / run_dir.name
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for source in sorted(source_dir.glob("*.pth.tar")):
        target = destination / source.name
        shutil.copy2(source, target)
        files.append({"filename": target.name, "size_bytes": target.stat().st_size, "sha256": sha256(target)})
    for name in ("run_meta.json", "run_summary.json"):
        source = run_dir / name
        if source.is_file():
            shutil.copy2(source, destination / name)
    export = {
        "experiment_id": CONFIG["experiment_id"],
        "profile": args.profile,
        "candidate": args.candidate,
        "seed": args.seed,
        "source_run": str(run_dir),
        "parent_checkpoint_sha256": CONFIG["parent_model"]["checkpoint_sha256"],
        "reset_seed_sha256": sha256(experiment_path(CONFIG["parent_model"]["seed_checkpoint"])),
        "dataset_content_sha256": manifest["content_sha256"],
        "files": files,
    }
    (destination / "export_manifest.json").write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"weights_dir": str(destination), **export}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R83 conservative R79 strengthening launcher")
    parser.add_argument("--candidate", choices=sorted(CANDIDATES), default="adapter_tail")
    parser.add_argument("--profile", choices=("smoke", "pilot", "formal"), default="pilot")
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--num-epoch", type=int, default=int(CONFIG["training"]["formal_epochs"]))
    parser.add_argument("--seed", type=int, choices=CONFIG["training"]["stability_seeds"], default=int(CONFIG["training"]["seed"]))
    parser.add_argument("--lr", type=float, default=float(CONFIG["training"]["learning_rate"]))
    parser.add_argument("--batch-size", type=int, default=int(CONFIG["training"]["batch_size"]))
    parser.add_argument("--val-batch-size", type=int, default=int(CONFIG["training"]["validation_batch_size"]))
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument("--live-validation-dir", type=Path, default=experiment_path(LIVE_CONFIG["image_dir"]))
    parser.add_argument("--live-validation-every", type=int, default=int(LIVE_CONFIG["every_n_epochs"]))
    parser.add_argument("--disable-live-validation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    package, manifest, source_audit = ensure_package(args.profile, args.build_data, args.force_data)
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    runtime_audit = assert_runtime_contract(trainer)
    seed_audit = assert_seed_checkpoint()
    configure_trainer(trainer, args, package, manifest)
    lock_audit = assert_finetune_lock(trainer, package, manifest, args)
    model_audit = verify_model_seed(trainer, package, args)
    cfg = trainer.CFG
    summary = {
        "experiment_id": CONFIG["experiment_id"],
        "status": "dry_run_verified" if args.dry_run else "ready_to_train",
        "profile": args.profile,
        "candidate": args.candidate,
        "total_pairs": manifest["total_pairs"],
        "split_counts": source_audit["split_counts"],
        "runtime_contract_passed": runtime_audit["passed"],
        "seed_parity_passed": seed_audit["passed"],
        "fine_tune_lock_passed": lock_audit["passed"],
        "model_seed_audit_passed": model_audit["passed"],
        "model_name": cfg.MODEL_NAME,
        "num_epoch": cfg.NUM_EPOCH,
        "learning_rate": cfg.LR,
        "device": cfg.DEVICE,
        "batch_size": cfg.BATCH_SIZE,
        "trainable_parameter_count": model_audit["trainable_parameter_count"],
        "progress_root": str(PROGRESS_ROOT),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("[R83] Dry run complete; no training was started.")
        return 0

    before = {path.resolve() for path in PROGRESS_ROOT.glob("training_progress_*") if path.is_dir()}
    sys.argv = [sys.argv[0]]
    trainer.main()
    candidates = [
        path for path in PROGRESS_ROOT.glob(f"training_progress_{cfg.MODEL_NAME}_*")
        if path.is_dir() and path.resolve() not in before
    ]
    if not candidates:
        raise RuntimeError("Training returned without creating an R83 run folder")
    run_dir = max(candidates, key=lambda path: path.stat().st_mtime_ns)
    print(json.dumps({"training_complete": True, **export_run(run_dir, args, manifest)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
