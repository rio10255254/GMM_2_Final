"""Launch R75-v2 as a hard-locked random-initialization training run."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = EXPERIMENT_DIR / "model"
TRAINER_RUNTIME_DIR = EXPERIMENT_DIR / "training" / "runtime"
SCRIPT_DIR = Path(__file__).resolve().parent
PROGRESS_ROOT = EXPERIMENT_DIR / "runs"
WEIGHTS_ROOT = EXPERIMENT_DIR / "weights"
CONFIG = json.loads((EXPERIMENT_DIR / "config" / "experiment.json").read_text(encoding="utf-8"))
ARCHITECTURE_CONTRACT = json.loads(
    (EXPERIMENT_DIR / "config" / "architecture_contract.json").read_text(encoding="utf-8")
)
DATA_ROOT = EXPERIMENT_DIR / "data"
LIVE_VALIDATION_CONFIG = CONFIG.get("live_validation", {})

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(TRAINER_RUNTIME_DIR))
sys.path.insert(0, str(MODEL_DIR))

from r75v2_dataset import audit_package, build_package  # noqa: E402


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _experiment_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (EXPERIMENT_DIR / path).resolve()


def ensure_package(profile: str, *, build_data: bool, force_data: bool) -> tuple[Path, dict, dict]:
    package_dir = DATA_ROOT / f"r75v2_{profile}_diverse_primitives"
    if build_data:
        return build_package(profile, DATA_ROOT, force=force_data)
    manifest = _read_json(package_dir / "manifest.json")
    audit = audit_package(package_dir, manifest)
    return package_dir, manifest, audit


def _prepare_synthetic_monitor(package_dir: Path, manifest: dict) -> Path:
    train_row = next((row for row in manifest["pairs"] if row["split"] == "train"), None)
    if train_row is None:
        raise RuntimeError("R75-v2 package has no training record for its monitor")
    source = package_dir / train_row["package_src"]
    monitor = package_dir / "runtime" / "Test_Image" / "r75v2_synthetic_monitor.bmp"
    monitor.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, monitor)
    return monitor


def _set_progress_root(trainer) -> None:
    PROGRESS_ROOT.mkdir(parents=True, exist_ok=True)
    if hasattr(trainer, "_set_training_progress_root"):
        trainer._set_training_progress_root(str(PROGRESS_ROOT))
    else:
        trainer.TRAINING_PROGRESS_ROOT = str(PROGRESS_ROOT)


def export_run_weights(run_dir: Path, args: argparse.Namespace, manifest: dict) -> dict:
    source_weights = run_dir / "weights"
    best = source_weights / "best_tradeoff.pth.tar"
    if not best.is_file():
        raise RuntimeError(f"Training finished without best_tradeoff.pth.tar: {source_weights}")
    destination = WEIGHTS_ROOT / str(args.profile) / f"seed_{int(args.seed)}" / run_dir.name
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sorted(source_weights.glob("*.pth.tar")):
        target = destination / source.name
        shutil.copy2(source, target)
        copied.append(
            {
                "filename": target.name,
                "size_bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )
    run_meta = run_dir / "run_meta.json"
    if run_meta.is_file():
        shutil.copy2(run_meta, destination / "run_meta.json")
    export_manifest = {
        "experiment_id": CONFIG["experiment_id"],
        "profile": str(args.profile),
        "seed": int(args.seed),
        "source_run": str(run_dir),
        "checkpoint_loaded": False,
        "teacher_loaded": False,
        "dataset_content_sha256": manifest["content_sha256"],
        "dataset_generator": manifest["generator_version"],
        "label_supersample_factor": manifest["label_supersample_factor"],
        "live_validation_role": "observation_only_no_loss_no_selection_no_training_control",
        "live_validation_image": str(Path(args.live_validation_image).resolve()) if not args.disable_live_validation else None,
        "live_validation_every_n_epochs": int(args.live_validation_every),
        "architecture_source_sha256": ARCHITECTURE_CONTRACT["architecture_source_sha256"],
        "utility_source_sha256": ARCHITECTURE_CONTRACT["utility_source_sha256"],
        "analytic_psf_source_sha256": ARCHITECTURE_CONTRACT["analytic_psf_source_sha256"],
        "trainer_source_sha256": ARCHITECTURE_CONTRACT["trainer_source_sha256"],
        "files": copied,
    }
    (destination / "export_manifest.json").write_text(
        json.dumps(export_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"weights_dir": str(destination), **export_manifest}


def assert_runtime_contract(trainer) -> dict:
    architecture_path = _experiment_path(ARCHITECTURE_CONTRACT["architecture_source"])
    utility_path = _experiment_path(ARCHITECTURE_CONTRACT["utility_source"])
    analytic_psf_path = _experiment_path(ARCHITECTURE_CONTRACT["analytic_psf_source"])
    trainer_path = Path(trainer.__file__).resolve()
    architecture_hash = _sha256(architecture_path)
    utility_hash = _sha256(utility_path)
    analytic_psf_hash = _sha256(analytic_psf_path)
    trainer_hash = _sha256(trainer_path)
    violations = []
    if architecture_hash != ARCHITECTURE_CONTRACT["architecture_source_sha256"]:
        violations.append("the pinned model architecture file changed")
    if utility_hash != ARCHITECTURE_CONTRACT["utility_source_sha256"]:
        violations.append("the pinned model utility file changed")
    if analytic_psf_hash != ARCHITECTURE_CONTRACT["analytic_psf_source_sha256"]:
        violations.append("the pinned analytic PSF file changed")
    if trainer_hash != ARCHITECTURE_CONTRACT["trainer_source_sha256"]:
        violations.append("the pinned trainer file changed")
    if trainer_path != _experiment_path(ARCHITECTURE_CONTRACT["trainer_source"]):
        violations.append("a different trainer file was imported")
    if violations:
        raise RuntimeError("R75-v2 runtime contract failed: " + "; ".join(violations))
    return {
        "passed": True,
        "architecture_source_sha256": architecture_hash,
        "utility_source_sha256": utility_hash,
        "analytic_psf_source_sha256": analytic_psf_hash,
        "trainer_source_sha256": trainer_hash,
    }


def configure_trainer(trainer, args: argparse.Namespace, package_dir: Path, manifest: dict) -> None:
    CFG = trainer.CFG
    audit = audit_package(package_dir, manifest)
    if not audit["passed"]:
        raise RuntimeError("R75-v2 source audit did not pass")

    monitor = _prepare_synthetic_monitor(package_dir, manifest)
    trainer.SCRIPT_DIR = str(monitor.parents[1])
    _set_progress_root(trainer)

    # Hard scratch lock.  There is intentionally no command-line checkpoint option.
    CFG.LOAD_MODEL = False
    CFG.LOAD_RESET_OPTIMIZER = False
    CFG.LOAD_RESET_EPOCH = False
    CFG.RESUME_CHECKPOINT = ""
    CFG.PRETRAINED_PATH = ""
    CFG.PRETRAINED_FALLBACK_PATH = ""
    CFG.LAB_SOURCE_CHECKPOINT = ""
    CFG.TRAINABLE_NAME_PATTERNS = ()

    # No teacher, replay, sequence, motion, or external-data side channel.
    CFG.KD_ENABLE = False
    CFG.KD_COMBO_PATH = ""
    CFG.KD_R40_PATH = ""
    CFG.KD_WEIGHT_COMBO = 0.0
    CFG.KD_WEIGHT_R40 = 0.0
    CFG.REGION_KD_ENABLE = False
    CFG.REGION_KD_TEACHER_PATH = ""
    CFG.REGION_KD_WEIGHT = 0.0
    CFG.SEQ_ENABLE = False
    CFG.SEQ_SRC_DIR = ""
    CFG.SEQ_LBL_DIR = ""
    CFG.SEQ_INCLUDE_SUBDIRS = ()
    CFG.SEQ_LOSS_WEIGHT = 0.0
    CFG.SEQ_GEOM_ENABLE = False
    CFG.SEQ_VAL_ENABLE = False
    CFG.MOTION_ENABLE = False
    CFG.MOTION_SRC_DIR = ""
    CFG.MOTION_LBL_DIR = ""
    CFG.MOTION_GEOM_DIR = ""
    CFG.MOTION_META_DIR = ""
    CFG.MOTION_INCLUDE_SUBDIRS = ()
    CFG.MOTION_LOSS_WEIGHT = 0.0

    # R61v16 architectural form, initialized directly with the intended 0.018 cap.
    CFG.USE_UPSAMPLE_CONV = True
    CFG.USE_BAND_LIMIT = False
    CFG.LEARNABLE_BLUR = False
    CFG.USE_BOTTLENECK_SE = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ENABLE = True
    CFG.BOUNDARY_RESIDUAL_ADAPTER_HIDDEN = 16
    CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX = 0.018
    CFG.BOUNDARY_RESIDUAL_ADAPTER_GATE_BIAS = -2.0
    CFG.BOUNDARY_RESIDUAL_ADAPTER_DELTA_BIAS = True
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ZERO_MEAN = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_EDGE_GATE = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_POLARITY_SPLIT = False
    CFG.BOUNDARY_RESIDUAL_ADAPTER_ORIENTATION_INPUTS = True
    CFG.RAW_ANCHOR_OUTPUT_MODE = "none"
    CFG.QUALITY_GATE_ENABLE = False

    # Keep the same optional optical blocks, but feed them only an analytic bank.
    psf_path = package_dir / manifest["analytic_psf"]["relative_path"]
    CFG.PSF_FITTED_PATH = str(psf_path)
    CFG.PSF_GRID_ROWS = 3
    CFG.PSF_GRID_COLS = 3
    CFG.PSF_USE_STACK_MEAN = True
    CFG.PSF_DECONV_REG = 30.0
    CFG.PSF_PHYS_ALPHA_INIT = 0.05
    CFG.PSF_PHYS_ALPHA_MIN = 0.0
    CFG.PSF_PHYS_ALPHA_MAX = 0.20
    CFG.PSF_PHYS_TRAINABLE_REG = False
    CFG.PHYSICS_LR_MULT = 0.10
    CFG.PHYS_FORWARD_ENABLE = False
    CFG.W_PHYS_MAX = 0.0
    CFG.WEAK_PSF_ENABLE = True
    CFG.WEAK_PSF_K = 4
    CFG.WEAK_PSF_BETA_INIT = 0.0
    CFG.WEAK_PSF_BETA_SCALE_MAX = 0.0
    CFG.WEAK_PSF_BETA_SCALE_STAGE1 = 0.0
    CFG.WEAK_PSF_BETA_SCALE_STAGE2 = 0.0
    CFG.WEAK_PSF_BETA_SCALE_STAGE3 = 0.0
    CFG.WEAK_PSF_LR_MULT = 0.0
    CFG.WEAK_PSF_LR_MULT_STAGE1 = 0.0
    CFG.WEAK_PSF_LR_MULT_STAGE2 = 0.0
    CFG.WEAK_PSF_LR_MULT_STAGE3 = 0.0
    CFG.WEAK_PSF_GUARD_ENABLE = False
    CFG.ENABLE_PSF_GUARD_ONLY = False

    # Diverse pure-procedural package and geometry-grouped split.
    CFG.TRAIN_INCLUDE_SUBDIRS = (str(CONFIG["dataset"]["stage_name"]),)
    CFG.TRAIN_EXCLUDE_SUBDIRS = ()
    CFG.TRAIN_GROUP_BALANCED_SAMPLER = True
    CFG.TRAIN_GROUP_BALANCE_MANIFEST = str(package_dir / "manifest.json")
    CFG.TRAIN_GROUP_BALANCE_KEYS = tuple(CONFIG["training"]["group_balancing_keys"])
    CFG.TRAIN_GROUP_BALANCE_NUM_SAMPLES_MULT = 1.0
    CFG.BOUNDARY_GEOM_ENABLE = True
    CFG.BOUNDARY_GEOM_DIR = str(package_dir / "geom")
    CFG.FIXED_SPLIT_DIR = str(package_dir / manifest["fixed_split_dir"])
    CFG.VAL_RATIO = 0.1

    # Conservative full-network scratch objective.
    CFG.W_REC = 1.0
    CFG.W_GRADMAG = 0.60
    CFG.W_EDGE_ORI_SIMPLE = 0.18
    CFG.W_HF_LAP = 0.04
    CFG.W_EDGELOCAL_LAP_START = 0.0
    CFG.W_EDGELOCAL_LAP_END = 0.015
    CFG.EDGELOCAL_LAP_RAMP_E1 = 8
    CFG.EDGELOCAL_LAP_RAMP_E2 = 40
    CFG.BOUNDARY_LOSS_WEIGHT = 0.050
    CFG.CENTERLINE_LOSS_WEIGHT = 0.025
    CFG.DISTANCE_EDGE_LOSS_WEIGHT = 0.025
    CFG.BOUNDARY_LOSS_WARMUP_EPOCH = 5
    CFG.BOUNDARY_POSITION_LOSS_WEIGHT = 0.0004
    CFG.BOUNDARY_POSITION_COVERAGE_WEIGHT = 0.02
    CFG.BOUNDARY_POSITION_DISTANCE_CLIP = 8.0
    CFG.BOUNDARY_POSITION_WARMUP_EPOCH = 5
    CFG.IDENTITY_GUARD_ENABLE = False
    CFG.GMF_VALIDATE_ENABLE = False
    CFG.GMF_VALIDATE_SOURCE = "val_batch"

    # Reproducible run settings.
    seed = int(args.seed)
    CFG.SPLIT_SEED = seed
    CFG.REPRO_SEED = seed
    CFG.SEED_ACTIVE = seed
    CFG.SEED_DETERMINISTIC = True
    CFG.REPRO_MODE = True
    CFG.REPRO_FORCE_FIXED_SPLIT = False
    CFG.REPRO_NUM_WORKERS = int(args.num_workers)
    configured_amp = bool(CONFIG["training"].get("amp_enabled", False))
    requested_amp = configured_amp if args.amp is None else bool(args.amp)
    CFG.REPRO_DISABLE_AMP = bool((not requested_amp) or not str(args.device).lower().startswith("cuda"))
    CFG.REPRO_DISABLE_TF32 = True
    CFG.REPRO_DETERMINISTIC = True
    CFG.REPRO_STRICT_DETERMINISTIC = False
    CFG.SEED_SWEEP_ENABLE = False
    CFG.use_amp = not CFG.REPRO_DISABLE_AMP

    run_suffix = str(args.run_suffix or "").strip()
    if run_suffix:
        safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in run_suffix)
        run_suffix = f"_{safe}"
    CFG.MODEL_NAME = f"LAB_GESR_v1_v5_R75v2_scratch_{args.profile}_seed{seed}{run_suffix}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME
    CFG.NUM_EPOCH = int(args.num_epoch)
    CFG.SIMPLETEST_MAX_EPOCH = int(args.num_epoch)
    CFG.BEST_EPOCH_MIN = min(20, max(1, int(args.num_epoch) // 5))
    CFG.BEST_EPOCH_MAX = int(args.num_epoch)
    CFG.DEVICE = str(args.device)
    CFG.LR = float(args.lr)
    CFG.WEIGHT_DECAY = 0.0
    CFG.BATCH_SIZE = int(args.batch_size)
    CFG.VAL_BATCH_SIZE = int(args.val_batch_size)
    CFG.NUM_WORKERS = int(args.num_workers)
    CFG.CROP_SIZE = int(CONFIG["training"]["crop_size"])
    CFG.DATALOADER_PERSISTENT_WORKERS = False
    CFG.FAST_IO_MODE = True
    CFG.FAST_DISABLE_PLOTS = True
    CFG.FAST_VAL_EVERY_EPOCH = 1 if int(args.num_epoch) <= 3 else 2
    CFG.FAST_MONITOR_EVERY_EPOCH = 5
    CFG.EXTERNAL_VISUAL_MONITOR_ENABLE = not bool(args.disable_live_validation)
    CFG.EXTERNAL_VISUAL_MONITOR_PATH = (
        str(Path(args.live_validation_image).resolve())
        if CFG.EXTERNAL_VISUAL_MONITOR_ENABLE
        else ""
    )
    CFG.EXTERNAL_VISUAL_MONITOR_EVERY_N_EPOCHS = int(args.live_validation_every)
    CFG.EXTERNAL_VISUAL_MONITOR_OUTPUT_DIR = "live_validation_pillar_center9"
    CFG.SAVE_MONITOR_EVERY_EPOCH = True
    CFG.RUN_PREFLIGHT_SANITY = False
    if args.max_train_batches is not None:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH = int(args.max_train_batches)
        CFG.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH = int(args.num_epoch)
    else:
        CFG.MAX_TRAIN_BATCHES_PER_EPOCH = 0
        CFG.EARLY_MAX_TRAIN_BATCHES_PER_EPOCH = 0
        CFG.EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH = 0

    trainer.TRAIN_SRC_DIR = str(package_dir / "src")
    trainer.TRAIN_LBL_DIR = str(package_dir / "lbl")
    trainer.TRAIN_GEOM_DIR = str(package_dir / "geom")


def assert_scratch_lock(trainer, package_dir: Path, manifest: dict) -> dict:
    CFG = trainer.CFG
    violations: list[str] = []
    if bool(CFG.LOAD_MODEL) or str(CFG.RESUME_CHECKPOINT or "").strip():
        violations.append("checkpoint loading is enabled")
    if str(getattr(CFG, "PRETRAINED_PATH", "")).strip() or str(getattr(CFG, "PRETRAINED_FALLBACK_PATH", "")).strip():
        violations.append("pretrained fallback path is populated")
    if bool(CFG.KD_ENABLE) or bool(CFG.REGION_KD_ENABLE):
        violations.append("a teacher-model path is enabled")
    if tuple(CFG.TRAINABLE_NAME_PATTERNS):
        violations.append("the full network is not trainable")
    if bool(CFG.SEQ_ENABLE) or bool(CFG.MOTION_ENABLE):
        violations.append("an auxiliary sequence or motion source is enabled")
    live_validation_path = None
    if bool(getattr(CFG, "EXTERNAL_VISUAL_MONITOR_ENABLE", False)):
        live_validation_path = Path(str(CFG.EXTERNAL_VISUAL_MONITOR_PATH)).resolve()
        live_validation_root = (EXPERIMENT_DIR / "data" / "live_validation").resolve()
        if not live_validation_path.is_file():
            violations.append("the observation-only live-validation image is missing")
        if not live_validation_path.is_relative_to(live_validation_root):
            violations.append("the live-validation image escapes data/live_validation")
        if live_validation_path.is_relative_to(package_dir.resolve()):
            violations.append("the live-validation image is inside the training package")
        if str(LIVE_VALIDATION_CONFIG.get("role", "")) != "observation_only_no_loss_no_selection_no_training_control":
            violations.append("the live-validation role is not observation-only")
    approved_root = package_dir.resolve()
    for label, path_text in {
        "training source": trainer.TRAIN_SRC_DIR,
        "training label": trainer.TRAIN_LBL_DIR,
        "training geometry": trainer.TRAIN_GEOM_DIR,
        "analytic PSF": CFG.PSF_FITTED_PATH,
        "fixed split": CFG.FIXED_SPLIT_DIR,
    }.items():
        path = Path(path_text).resolve()
        try:
            inside = path.is_relative_to(approved_root)
        except AttributeError:
            inside = str(path).lower().startswith(str(approved_root).lower() + "\\")
        if not inside:
            violations.append(f"{label} escapes the approved package")
    audit = audit_package(package_dir, manifest)
    if not audit["passed"]:
        violations.append("source audit failed")
    if violations:
        raise RuntimeError("R75-v2 scratch lock failed: " + "; ".join(violations))
    return {
        "passed": True,
        "checkpoint_loading": False,
        "teacher_models": False,
        "legacy_or_real_training_sources": False,
        "full_network_trainable": True,
        "live_validation_observation_only": bool(live_validation_path is not None),
        "live_validation_path": str(live_validation_path) if live_validation_path else None,
        "live_validation_affects_training": False,
        "approved_package_root": str(approved_root),
        "source_audit": audit,
    }


def verify_architecture(trainer, package_dir: Path, profile: str, seed: int) -> dict:
    import torch

    CFG = trainer.CFG
    requested_device = str(CFG.DEVICE)
    requested_amp = bool(CFG.use_amp)
    CFG.DEVICE = "cpu"
    CFG.use_amp = False
    torch.manual_seed(int(seed))
    model = trainer._build_model_from_cfg()
    model.eval()
    parameter_count = sum(int(parameter.numel()) for parameter in model.parameters())
    trainable_count = sum(int(parameter.numel()) for parameter in model.parameters() if parameter.requires_grad)
    fixed_parameters = {
        name: int(parameter.numel())
        for name, parameter in model.named_parameters()
        if not parameter.requires_grad
    }
    expected_fixed = {"u3.blur.weight", "u2.blur.weight", "u1.blur.weight"}
    digest = hashlib.sha256()
    for name, parameter in model.named_parameters():
        digest.update(name.encode("utf-8"))
        digest.update(str(tuple(parameter.shape)).encode("ascii"))
        digest.update(parameter.detach().cpu().contiguous().numpy().tobytes())

    monitor_path = package_dir / "runtime" / "Test_Image" / "r75v2_synthetic_monitor.bmp"
    image_data = np.fromfile(monitor_path, dtype=np.uint8)
    monitor = cv2.imdecode(image_data, cv2.IMREAD_GRAYSCALE)
    if monitor is None:
        raise RuntimeError(f"Could not read synthetic monitor: {monitor_path}")
    monitor = cv2.resize(monitor, (64, 64), interpolation=cv2.INTER_AREA)
    tensor = torch.from_numpy(monitor.astype(np.float32) / 255.0)[None, None]
    with torch.no_grad():
        output = model(tensor)
    if tuple(output.shape) != (1, 1, 64, 64) or not bool(torch.isfinite(output).all()):
        raise RuntimeError(f"R75-v2 architecture forward check failed: shape={tuple(output.shape)}")
    adapter_cap = float(model.boundary_adapter.max_residual.detach().cpu().item())
    if abs(adapter_cap - 0.018) > 1e-8:
        raise RuntimeError(f"Boundary adapter cap mismatch: {adapter_cap}")
    unexpected_fixed = sorted(set(fixed_parameters) - expected_fixed)
    missing_fixed = sorted(expected_fixed - set(fixed_parameters))
    if unexpected_fixed or missing_fixed:
        raise RuntimeError(
            "Unexpected frozen parameter set: "
            f"unexpected={unexpected_fixed}, missing_expected={missing_fixed}"
        )
    if parameter_count != int(ARCHITECTURE_CONTRACT["expected_parameter_count"]):
        raise RuntimeError(f"Architecture parameter count changed: {parameter_count}")
    if trainable_count != int(ARCHITECTURE_CONTRACT["expected_trainable_parameter_count"]):
        raise RuntimeError(f"Trainable parameter count changed: {trainable_count}")
    if fixed_parameters != ARCHITECTURE_CONTRACT["expected_fixed_architecture_kernels"]:
        raise RuntimeError(f"Fixed kernel contract changed: {fixed_parameters}")

    architecture_file = _experiment_path(CONFIG["architecture"]["source_file"])
    result = {
        "passed": True,
        "profile": profile,
        "class_name": type(model).__name__,
        "architecture_source": str(architecture_file),
        "architecture_source_sha256": _sha256(architecture_file),
        "parameter_count": parameter_count,
        "trainable_parameter_count": trainable_count,
        "all_learnable_layers_trainable": True,
        "fixed_architecture_kernels": fixed_parameters,
        "fixed_architecture_kernel_count": sum(fixed_parameters.values()),
        "random_initialization_seed": int(seed),
        "initial_parameter_sha256": digest.hexdigest(),
        "checkpoint_loaded": False,
        "teacher_loaded": False,
        "boundary_adapter_enabled": model.boundary_adapter is not None,
        "boundary_adapter_max_residual": adapter_cap,
        "boundary_adapter_orientation_inputs": bool(model.boundary_adapter.orientation_inputs),
        "analytic_psf_path": str(Path(CFG.PSF_FITTED_PATH).resolve()),
        "analytic_psf_sha256": _sha256(Path(CFG.PSF_FITTED_PATH)),
        "forward_input_shape": [1, 1, 64, 64],
        "forward_output_shape": list(output.shape),
        "forward_output_range": [float(output.min()), float(output.max())],
        "forward_finite": True,
    }
    default_seed = int(CONFIG["training"]["seed"])
    report_name = f"architecture_audit_{profile}.json" if int(seed) == default_seed else f"architecture_audit_{profile}_seed{int(seed)}.json"
    report_path = EXPERIMENT_DIR / "reports" / report_name
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    del model, output, tensor
    CFG.DEVICE = requested_device
    CFG.use_amp = requested_amp
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="R75-v2 diverse pure-procedural scratch-training launcher")
    parser.add_argument("--profile", choices=sorted(CONFIG["dataset"]["profiles"]), default="pilot")
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--force-data", action="store_true")
    parser.add_argument("--num-epoch", type=int, default=int(CONFIG["training"]["formal_epochs"]))
    parser.add_argument("--seed", type=int, choices=CONFIG["training"]["stability_seeds"], default=int(CONFIG["training"]["seed"]))
    parser.add_argument("--lr", type=float, default=float(CONFIG["training"]["learning_rate"]))
    parser.add_argument("--batch-size", type=int, default=int(CONFIG["training"]["batch_size"]))
    parser.add_argument("--val-batch-size", type=int, default=int(CONFIG["training"]["validation_batch_size"]))
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--device", default="cuda:0")
    amp_group = parser.add_mutually_exclusive_group()
    amp_group.add_argument("--amp", dest="amp", action="store_true", help="明確啟用半精度；R75-v2 正式設定不建議使用")
    amp_group.add_argument("--no-amp", dest="amp", action="store_false", help="關閉半精度，避免邊界損失溢位")
    parser.set_defaults(amp=None)
    parser.add_argument("--max-train-batches", type=int, default=None)
    parser.add_argument("--run-suffix", default="")
    parser.add_argument(
        "--live-validation-image",
        type=Path,
        default=_experiment_path(LIVE_VALIDATION_CONFIG["relative_image_path"]),
    )
    parser.add_argument(
        "--live-validation-every",
        type=int,
        default=int(LIVE_VALIDATION_CONFIG.get("every_n_epochs", 5)),
    )
    parser.add_argument("--disable-live-validation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-model-check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    package_dir, manifest, source_audit = ensure_package(
        args.profile,
        build_data=args.build_data,
        force_data=args.force_data,
    )
    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer

    runtime_contract = assert_runtime_contract(trainer)
    configure_trainer(trainer, args, package_dir, manifest)
    scratch_audit = assert_scratch_lock(trainer, package_dir, manifest)
    architecture_audit = None if args.skip_model_check else verify_architecture(trainer, package_dir, args.profile, args.seed)
    CFG = trainer.CFG
    summary = {
        "experiment_id": CONFIG["experiment_id"],
        "status": "ready_to_train" if not args.dry_run else "dry_run_verified",
        "profile": args.profile,
        "package_dir": str(package_dir),
        "total_pairs": manifest["total_pairs"],
        "split_counts": source_audit["split_counts"],
        "source_audit_passed": source_audit["passed"],
        "scratch_lock_passed": scratch_audit["passed"],
        "runtime_contract_passed": runtime_contract["passed"],
        "checkpoint_loading": False,
        "teacher_models": False,
        "real_or_measured_training_shapes": False,
        "live_validation_image": str(Path(args.live_validation_image).resolve()) if not args.disable_live_validation else None,
        "live_validation_every_n_epochs": int(args.live_validation_every),
        "live_validation_role": "observation_only_no_loss_no_selection_no_training_control",
        "live_validation_affects_training": False,
        "model_name": CFG.MODEL_NAME,
        "num_epoch": CFG.NUM_EPOCH,
        "seed": int(args.seed),
        "learning_rate": CFG.LR,
        "device": CFG.DEVICE,
        "amp_enabled": bool(CFG.use_amp),
        "batch_size": CFG.BATCH_SIZE,
        "fixed_split_dir": CFG.FIXED_SPLIT_DIR,
        "training_source_dir": trainer.TRAIN_SRC_DIR,
        "training_label_dir": trainer.TRAIN_LBL_DIR,
        "training_geometry_dir": trainer.TRAIN_GEOM_DIR,
        "analytic_psf": CFG.PSF_FITTED_PATH,
        "architecture_audit_passed": bool(architecture_audit and architecture_audit["passed"]),
        "parameter_count": architecture_audit["parameter_count"] if architecture_audit else None,
        "all_learnable_layers_trainable": architecture_audit["all_learnable_layers_trainable"] if architecture_audit else None,
        "boundary_adapter_max_residual": CFG.BOUNDARY_RESIDUAL_ADAPTER_MAX,
        "max_train_batches": args.max_train_batches,
        "progress_root": str(PROGRESS_ROOT),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.dry_run:
        print("[R75-v2] Dry run complete; no training was started.")
        return 0

    # Clear launcher arguments so the legacy trainer cannot re-enable a resume path.
    before_runs = {path.resolve() for path in PROGRESS_ROOT.glob("training_progress_*") if path.is_dir()}
    sys.argv = [sys.argv[0]]
    trainer.main()
    candidates = [
        path
        for path in PROGRESS_ROOT.glob(f"training_progress_{CFG.MODEL_NAME}_*")
        if path.is_dir() and path.resolve() not in before_runs
    ]
    if not candidates:
        raise RuntimeError("Training returned without creating a new R75-v2 run folder")
    run_dir = max(candidates, key=lambda path: path.stat().st_mtime_ns)
    export_summary = export_run_weights(run_dir, args, manifest)
    print(json.dumps({"training_complete": True, **export_summary}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
