# GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py
# Compatible inference script for:
# - GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py
# - GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py
#
# Notes:
# - Keeps folder-batch reconstruction style similar to existing infer script.
# - Auto-aligns model init with checkpoint structure.
# - Can build a temporary PSF .mat from checkpoint buffers to avoid PSF-shape mismatch.

import argparse
import json
import math
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
import scipy.io
import torch
import torch.nn.functional as F
_PROJECT_ROOT = Path(__file__).resolve().parents[5]


# -----------------------------------------------------------------------------
# Ensure local imports work
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(str(_PROJECT_ROOT / 'Model'))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

try:
    from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord
    from GeoEdgeAlignSR_v1_Utils import imread_unicode, imwrite_unicode
except ImportError:
    print("Error: required GeoEdgeAlignSR modules not found.")
    sys.exit(1)


# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------
PROJECT_ROOT = SCRIPT_DIR.parent
TRAINING_PROGRESS_ROOT = PROJECT_ROOT / "Experiments" / "Training_Runs"  # keep same folder name as training script
LEGACY_ROOT = PROJECT_ROOT / "Experiments" / "Legacy"  # early organized_* batches
CURRENT_SELECTED_SEED_MANIFEST = LEGACY_ROOT / "organized_20260307" / "selected" / "current_seed.json"
CURRENT_EXTERNAL_VALIDATION_ROOT = LEGACY_ROOT / "organized_20260309" / "external_validation" / "current_seed"
TRAIN_MODEL_NAME = "GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest"
TRAIN_PROGRESS_PREFIX = f"training_progress_{TRAIN_MODEL_NAME}"
TRAIN_WEIGHT_FILENAMES = [
    "best_tradeoff.pth.tar",
    "best_detail_guarded.pth.tar",
    f"{TRAIN_MODEL_NAME}_ema_best_tradeoff.pth.tar",
    f"{TRAIN_MODEL_NAME}.pth.tar",
    "latest.pth.tar",
]
LEGACY_WEIGHT_CANDIDATES: list[Path] = []
# DEFAULT_INPUT_DIR = PROJECT_ROOT / "Training_Data" / "tra_src_ring"
DEFAULT_INPUT_DIR = "C:\\Users\\Rio\\Downloads\\NTU_ImageDataset\\Pitch1um_Y_100\\Cropped_Output"
DEFAULT_RECON_PROGRESS_ROOT = CURRENT_EXTERNAL_VALIDATION_ROOT / "reconstructions"
DEFAULT_RUN_PREFIX = "reconstruct_progress"
TRAIN_PROGRESS_TS_PATTERN = re.compile(r"^training_progress_.+_(\d{8}(?:_\d{6})?)$")
FOLDER_TS_PATTERN = re.compile(r"(20\d{6}(?:_\d{6})?)")
DEFAULT_PSF_PATH = PROJECT_ROOT / "PSF_Fitting" / "Crop_circle_FreqFiltered" / "Fits" / "PSF_fitted_2D_FOVstack.mat"
DEFAULT_ALIGN_FACTOR = 64

# Set to "all"/"odd"/"even" for hard override; set None to use CLI arg.
MANUAL_SELECT_MODE = None
# Set to a path string or Path(...) for hard override; set None to use CLI/auto search.
# Example:
# MANUAL_WEIGHTS_PATH = Path(r"Experiments/Training_Runs/training_progress_xxx/weights/latest.pth.tar")
MANUAL_WEIGHTS_PATH = None

VALID_EXTS = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}
ALLOWED_MISMATCH = {"band_limit.filter_mask"}


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", type=Path, default=None, help="Checkpoint path (.pth / .pth.tar)")
    p.add_argument("--input-dir", type=Path, default=None, help="Input image folder")
    p.add_argument("--recon-root", type=Path, default=None, help="Optional base folder for reconstruction runs")
    p.add_argument("--output-name", default=None, help="Optional leaf folder name under this run folder")
    p.add_argument("--gt-dir", type=Path, default=None, help="Optional GT folder with same filenames")
    p.add_argument("--device", default="auto", help="auto / cuda / cuda:0 / cpu")
    p.add_argument("--align-factor", type=int, default=DEFAULT_ALIGN_FACTOR, help="Pad H/W to multiple of this value")
    p.add_argument("--exts", default=None, help="Comma-separated suffix list, e.g. .bmp,.png")
    p.add_argument("--select-mode", default="all", choices=["all", "odd", "even"], help="all/odd/even image selection")

    # PSF source
    p.add_argument("--psf-fitted-path", type=Path, default=None, help="Optional explicit PSF .mat path")
    p.add_argument("--psf-from-ckpt", dest="psf_from_ckpt", action="store_true", help="Build PSF .mat from checkpoint buffers")
    p.add_argument("--no-psf-from-ckpt", dest="psf_from_ckpt", action="store_false", help="Do not build PSF .mat from checkpoint buffers")
    p.set_defaults(psf_from_ckpt=True)
    p.add_argument("--psf-grid-rows", type=int, default=None, help="Optional PSF grid rows")
    p.add_argument("--psf-grid-cols", type=int, default=None, help="Optional PSF grid cols")
    p.add_argument("--psf-use-stack-mean", dest="psf_use_stack_mean", action="store_true")
    p.add_argument("--psf-use-stack-center", dest="psf_use_stack_mean", action="store_false")
    p.set_defaults(psf_use_stack_mean=True)
    p.add_argument("--psf-deconv-reg", type=float, default=None, help="Override physics reg")
    p.add_argument("--psf-phys-alpha", type=float, default=None, help="Override physics alpha init")
    p.add_argument("--psf-phys-trainable-reg", action="store_true", help="Create physics reg as trainable parameter")

    # Optical band-limit
    p.add_argument("--use-band-limit", dest="use_band_limit", action="store_true")
    p.add_argument("--no-band-limit", dest="use_band_limit", action="store_false")
    p.set_defaults(use_band_limit=None)
    p.add_argument("--band-limit-cutoff", type=float, default=0.95)
    p.add_argument("--band-limit-order", type=float, default=8.0)

    # Weak PSF block
    p.add_argument("--weak-psf-enable", dest="weak_psf_enable", action="store_true")
    p.add_argument("--weak-psf-disable", dest="weak_psf_enable", action="store_false")
    p.set_defaults(weak_psf_enable=None)
    p.add_argument("--weak-psf-k", type=int, default=None, help="Override weak-PSF K")
    p.add_argument("--weak-psf-indices", default=None, help="Comma-separated PSF indices (length must equal K)")
    p.add_argument("--weak-psf-reg", type=float, default=None, help="Override weak-PSF reg")
    p.add_argument("--weak-psf-beta-init", type=float, default=None, help="Override weak-PSF beta init")
    p.add_argument("--weak-psf-beta-min", type=float, default=0.0)
    p.add_argument("--weak-psf-beta-max", type=float, default=0.10)
    p.add_argument("--weak-psf-beta-scale-max", type=float, default=None)
    p.add_argument("--weak-psf-beta-scale", type=float, default=None, help="Override beta_scale; default keeps checkpoint value")
    p.add_argument("--weak-psf-gating-temp", type=float, default=None, help="Override gating temperature")
    p.add_argument("--weak-psf-psf-temp", type=float, default=None, help="Override PSF softmax temperature")
    p.add_argument("--weak-psf-entropy-mix", type=float, default=None, help="Override entropy_mix; default keeps checkpoint value")
    p.add_argument("--weak-psf-trainable-reg", action="store_true")
    p.add_argument("--weak-psf-lowfreq-ratio", type=float, default=None, help="Override low-frequency ratio")
    p.add_argument("--weak-psf-inject", default="y2", choices=["y1", "y2"])
    p.add_argument("--weak-psf-deconv-mode", default="clamp", choices=["clamp", "abs"])

    p.add_argument("--strict-load", action="store_true", help="Use strict=True when loading checkpoint")
    p.add_argument("--print-model-config", action="store_true", help="Print inferred model config before init")
    return p.parse_args()


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    out = []
    seen = set()
    for p in paths:
        s = str(p)
        if s in seen:
            continue
        seen.add(s)
        out.append(p)
    return out


def resolve_current_seed_weights(manifest_path: Path) -> Path | None:
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    weights_path = data.get("weights_path")
    if not weights_path:
        return None
    return Path(str(weights_path))


def build_default_weight_candidates() -> list[Path]:
    candidates: list[Path] = []

    run_dirs: list[Path] = []
    if TRAINING_PROGRESS_ROOT.exists():
        all_runs = [p for p in TRAINING_PROGRESS_ROOT.glob("training_progress_*") if p.is_dir()]
        preferred = [p for p in all_runs if p.name.startswith(TRAIN_PROGRESS_PREFIX)]
        others = [p for p in all_runs if p not in preferred]
        preferred.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        others.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        run_dirs = preferred + others

    for run_dir in run_dirs:
        wdir = run_dir / "weights"
        for name in TRAIN_WEIGHT_FILENAMES:
            candidates.append(wdir / name)
        candidates.append(run_dir / f"{TRAIN_MODEL_NAME}_last_good.pth.tar")
        candidates.append(run_dir / f"{TRAIN_MODEL_NAME}_last_good_ema.pth.tar")

    candidates.extend(LEGACY_WEIGHT_CANDIDATES)
    return _dedupe_paths(candidates)


def resolve_weights_path(user_path: Path | None) -> Path:
    if user_path is not None:
        return user_path

    if MANUAL_WEIGHTS_PATH is not None:
        manual_text = str(MANUAL_WEIGHTS_PATH).strip()
        if manual_text == "__CURRENT_SELECTED_SEED__":
            current_seed_weights = resolve_current_seed_weights(CURRENT_SELECTED_SEED_MANIFEST)
            if current_seed_weights is not None:
                return current_seed_weights
        return Path(MANUAL_WEIGHTS_PATH)

    candidates = build_default_weight_candidates()
    for p in candidates:
        if p.exists():
            return p

    # If none exists, return the most likely training output target path.
    if candidates:
        return candidates[0]
    return TRAINING_PROGRESS_ROOT / f"training_progress_{TRAIN_MODEL_NAME}" / "weights" / "latest.pth.tar"


def resolve_device(device_str: str) -> torch.device:
    if device_str == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_str)


def _sanitize_tag(text: str) -> str:
    keep = []
    for ch in str(text):
        if ch.isalnum() or ch in ("_", "-", "."):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "model"


def infer_model_name_for_output(ckpt_obj, weights_path: Path) -> str:
    if isinstance(ckpt_obj, dict):
        for k in ("model_name", "MODEL_NAME", "name"):
            v = ckpt_obj.get(k)
            if isinstance(v, str) and v.strip():
                return _sanitize_tag(v.strip())
    stem = weights_path.stem
    if stem.endswith(".pth"):
        stem = Path(stem).stem
    return _sanitize_tag(stem or TRAIN_MODEL_NAME)


def infer_train_timestamp_from_weights_path(weights_path: Path) -> str | None:
    for parent in weights_path.parents:
        m = TRAIN_PROGRESS_TS_PATTERN.match(parent.name)
        if m:
            return m.group(1)
        m2 = FOLDER_TS_PATTERN.search(parent.name)
        if m2:
            return m2.group(1)
    if weights_path.parent.exists():
        return time.strftime("%Y%m%d_%H%M%S", time.localtime(weights_path.parent.stat().st_mtime))
    return None


def build_output_dir(
    project_root: Path,
    model_name: str,
    output_name: str | None,
    train_ts: str | None,
    input_dir: Path | None = None,
) -> Path:
    ts = train_ts or time.strftime("%Y%m%d_%H%M%S", time.localtime())
    input_tag = _sanitize_tag(input_dir.name) if input_dir is not None else None
    if input_tag:
        run_dir = project_root / f"{DEFAULT_RUN_PREFIX}_{_sanitize_tag(model_name)}_in_{input_tag}_{ts}"
    else:
        run_dir = project_root / f"{DEFAULT_RUN_PREFIX}_{_sanitize_tag(model_name)}_{ts}"
    if output_name:
        return run_dir / _sanitize_tag(output_name)
    return run_dir


def parse_indices(indices_str: str | None, k: int | None):
    if indices_str is None:
        return None
    if k is None:
        raise ValueError("weak-psf-indices requires weak-psf-k.")
    parts = [p.strip() for p in indices_str.split(",") if p.strip()]
    if not parts:
        return None
    indices = tuple(int(p) for p in parts)
    if len(indices) != int(k):
        raise ValueError(f"weak-psf-indices length {len(indices)} != k ({k})")
    return indices


def extract_state_dict(ckpt_obj):
    if isinstance(ckpt_obj, dict):
        state_dict = ckpt_obj.get("state_dict", ckpt_obj)
    else:
        state_dict = ckpt_obj
    if not isinstance(state_dict, dict):
        raise TypeError(f"Unsupported state_dict type: {type(state_dict)}")
    clean = {}
    for k, v in state_dict.items():
        nk = k.replace("module.", "", 1) if isinstance(k, str) and k.startswith("module.") else k
        clean[nk] = v
    return clean


def tensor_scalar(state_dict: dict, key: str, default: float | None = None) -> float | None:
    v = state_dict.get(key, None)
    if isinstance(v, torch.Tensor) and v.numel() == 1:
        return float(v.detach().cpu().item())
    return default


def infer_arch_from_state(state_dict: dict, ckpt_obj=None):
    conv = state_dict.get("e1.0.conv.weight")
    in_ch = 1
    base = 48
    if isinstance(conv, torch.Tensor) and conv.ndim == 4:
        base = int(conv.shape[0])
        in_ch = int(conv.shape[1])

    use_physics_layer = any(k.startswith("physics_layer.") for k in state_dict.keys())
    weak_psf_enable = any(k.startswith("weak_psf_block.") for k in state_dict.keys())
    use_band_limit = any(k.startswith("band_limit.") for k in state_dict.keys())
    boundary_adapter_enable = any(k.startswith("boundary_adapter.") for k in state_dict.keys())

    weak_psf_k = 4
    weak_psf_psfs = state_dict.get("weak_psf_block.PSFs")
    if isinstance(weak_psf_psfs, torch.Tensor) and weak_psf_psfs.ndim == 4:
        weak_psf_k = int(weak_psf_psfs.shape[1])

    boundary_adapter_hidden = 16
    boundary_adapter_w = state_dict.get("boundary_adapter.body.0.weight")
    if isinstance(boundary_adapter_w, torch.Tensor) and boundary_adapter_w.ndim == 4:
        boundary_adapter_hidden = int(boundary_adapter_w.shape[0])
    boundary_adapter_meta = {}
    if isinstance(ckpt_obj, dict):
        model_config = ckpt_obj.get("model_config", {})
        if isinstance(model_config, dict):
            value = model_config.get("boundary_residual_adapter", {})
            if isinstance(value, dict):
                boundary_adapter_meta = value
    boundary_adapter_delta_bias = "boundary_adapter.delta.bias" in state_dict
    if "delta_bias" in boundary_adapter_meta:
        boundary_adapter_delta_bias = bool(boundary_adapter_meta["delta_bias"])
    boundary_adapter_zero_mean = bool(boundary_adapter_meta.get("zero_mean", False))
    boundary_adapter_edge_gate = bool(boundary_adapter_meta.get("edge_gate", False))
    boundary_adapter_polarity_split = bool(boundary_adapter_meta.get("polarity_split", False))
    boundary_adapter_orientation_inputs = bool(boundary_adapter_meta.get("orientation_inputs", False))
    if isinstance(boundary_adapter_w, torch.Tensor) and boundary_adapter_w.ndim == 4:
        expected_old_inputs = int(base) + 1
        boundary_adapter_orientation_inputs = (
            boundary_adapter_orientation_inputs
            or int(boundary_adapter_w.shape[1]) >= expected_old_inputs + 3
        )
    boundary_adapter_delta_w = state_dict.get("boundary_adapter.delta.weight")
    if isinstance(boundary_adapter_delta_w, torch.Tensor) and boundary_adapter_delta_w.ndim == 4:
        boundary_adapter_polarity_split = boundary_adapter_polarity_split or int(boundary_adapter_delta_w.shape[0]) == 2

    return {
        "in_ch": in_ch,
        "base": base,
        "use_physics_layer": use_physics_layer,
        "weak_psf_enable": weak_psf_enable,
        "use_band_limit": use_band_limit,
        "boundary_residual_adapter_enable": boundary_adapter_enable,
        "boundary_residual_adapter_hidden": boundary_adapter_hidden,
        "boundary_residual_adapter_max": tensor_scalar(state_dict, "boundary_adapter.max_residual", 0.025),
        "boundary_residual_adapter_gate_bias": tensor_scalar(state_dict, "boundary_adapter.gate.bias", -2.0),
        "boundary_residual_adapter_delta_bias": boundary_adapter_delta_bias,
        "boundary_residual_adapter_zero_mean": boundary_adapter_zero_mean,
        "boundary_residual_adapter_edge_gate": boundary_adapter_edge_gate,
        "boundary_residual_adapter_polarity_split": boundary_adapter_polarity_split,
        "boundary_residual_adapter_orientation_inputs": boundary_adapter_orientation_inputs,
        "weak_psf_k": weak_psf_k,
        "psf_deconv_reg": tensor_scalar(state_dict, "physics_layer.reg", 10.0),
        "psf_phys_alpha_init": tensor_scalar(state_dict, "physics_layer.alpha", 0.10),
        "weak_psf_reg": tensor_scalar(state_dict, "weak_psf_block.reg", 30.0),
        "weak_psf_beta_init": tensor_scalar(state_dict, "weak_psf_block.beta", 0.02),
        "weak_psf_gating_temp": tensor_scalar(state_dict, "weak_psf_block.gating_temp", None),
        "weak_psf_psf_temp": tensor_scalar(state_dict, "weak_psf_block.psf_temp", 2.5),
        "weak_psf_entropy_mix": tensor_scalar(state_dict, "weak_psf_block.entropy_mix", 0.0),
        "weak_psf_lowfreq_ratio": tensor_scalar(state_dict, "weak_psf_block.lowfreq_ratio", 0.25),
        "weak_psf_beta_scale_max": tensor_scalar(state_dict, "weak_psf_block.beta_scale_max", 0.35),
    }


def extract_psf_path_from_ckpt(ckpt_obj) -> Path | None:
    if not isinstance(ckpt_obj, dict):
        return None
    for key in ("psf_fitted_path", "PSF_FITTED_PATH"):
        if key in ckpt_obj:
            return Path(ckpt_obj[key])
    cfg = ckpt_obj.get("cfg") or ckpt_obj.get("config") or ckpt_obj.get("train_config")
    if isinstance(cfg, dict):
        val = cfg.get("PSF_FITTED_PATH") or cfg.get("psf_fitted_path")
        if val:
            return Path(val)
    return None


def build_temp_psf_mat_from_state(state_dict: dict):
    psfs = state_dict.get("physics_layer.PSFs", None)
    if not isinstance(psfs, torch.Tensor):
        return None, None
    if psfs.ndim != 4 or int(psfs.shape[0]) < 1:
        return None, None

    psfs_np = psfs.detach().cpu().float().numpy()[0]  # [N, H, W]
    n = int(psfs_np.shape[0])
    if n == 1:
        fitted = psfs_np[0]
    else:
        fitted = np.transpose(psfs_np, (1, 2, 0))  # [H, W, N]

    temp_dir = Path(tempfile.mkdtemp(prefix="geoedge_psf_"))
    temp_mat = temp_dir / "psf_from_ckpt.mat"
    scipy.io.savemat(str(temp_mat), {"fitted_psf": fitted})
    return temp_mat, temp_dir


def resolve_psf_path(args: argparse.Namespace, ckpt_obj, state_dict: dict):
    if args.psf_fitted_path is not None:
        p = args.psf_fitted_path.expanduser().resolve()
        return p, None, "arg"

    if bool(args.psf_from_ckpt):
        p, temp_dir = build_temp_psf_mat_from_state(state_dict)
        if p is not None:
            return p, temp_dir, "ckpt-buffer"

    psf_ckpt = extract_psf_path_from_ckpt(ckpt_obj)
    if psf_ckpt is not None:
        p = psf_ckpt.expanduser().resolve()
        if p.exists():
            return p, None, "ckpt-meta"

    p = DEFAULT_PSF_PATH.resolve()
    return p, None, "default"


def read_image_keep_dtype(path: Path):
    img = imread_unicode(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to read image: {path}")
    original_dtype = img.dtype
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img, original_dtype


def pad_to_multiple_np(img_2d: np.ndarray, factor: int):
    h, w = img_2d.shape
    new_h = math.ceil(h / factor) * factor
    new_w = math.ceil(w / factor) * factor
    if new_h == h and new_w == w:
        return img_2d, h, w
    pad_h = new_h - h
    pad_w = new_w - w
    padded = np.pad(img_2d, ((0, pad_h), (0, pad_w)), mode="reflect")
    return padded, h, w


def normalize_to_01(raw: np.ndarray, dtype: np.dtype) -> np.ndarray:
    raw_f = raw.astype(np.float32)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        denom = float(info.max - info.min) if info.max != info.min else 255.0
        x = (raw_f - float(info.min)) / denom
        return np.clip(x, 0.0, 1.0)
    mx = float(np.max(raw_f)) if raw_f.size else 1.0
    x = raw_f / 255.0 if mx > 1.5 else raw_f
    return np.clip(x, 0.0, 1.0)


def denormalize_to_dtype(pred01: np.ndarray, dtype: np.dtype) -> np.ndarray:
    pred01 = np.clip(pred01, 0.0, 1.0)
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        out = pred01 * float(info.max - info.min) + float(info.min)
        return np.clip(np.rint(out), info.min, info.max).astype(dtype)
    return pred01.astype(np.float32)


_SSIM_WINDOW_CACHE = {}


def compute_psnr(pred01: np.ndarray, gt01: np.ndarray) -> float:
    mse = float(np.mean((pred01 - gt01) ** 2))
    if mse <= 1e-12:
        return float("inf")
    return 10.0 * math.log10(1.0 / mse)


def _get_ssim_window(window_size: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    key = (window_size, device.type, device.index, dtype)
    window = _SSIM_WINDOW_CACHE.get(key)
    if window is not None:
        return window
    vals = [math.exp(-(x - window_size // 2) ** 2 / float(2 * 1.5 ** 2)) for x in range(window_size)]
    gauss = torch.tensor(vals, device=device, dtype=dtype)
    gauss = gauss / gauss.sum()
    w1 = gauss.unsqueeze(1)
    w2 = w1.mm(w1.t()).float().unsqueeze(0).unsqueeze(0)
    _SSIM_WINDOW_CACHE[key] = w2
    return w2


def compute_ssim(pred01: np.ndarray, gt01: np.ndarray, window_size: int = 11) -> float:
    pred_t = torch.from_numpy(pred01).unsqueeze(0).unsqueeze(0).float()
    gt_t = torch.from_numpy(gt01).unsqueeze(0).unsqueeze(0).float()
    device = pred_t.device
    window = _get_ssim_window(window_size, device, pred_t.dtype)

    mu1 = F.conv2d(pred_t, window, padding=window_size // 2)
    mu2 = F.conv2d(gt_t, window, padding=window_size // 2)
    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)
    mu1_mu2 = mu1 * mu2

    sigma1_sq = F.conv2d(pred_t * pred_t, window, padding=window_size // 2) - mu1_sq
    sigma2_sq = F.conv2d(gt_t * gt_t, window, padding=window_size // 2) - mu2_sq
    sigma12 = F.conv2d(pred_t * gt_t, window, padding=window_size // 2) - mu1_mu2

    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    ssim_map = ((2 * mu1_mu2 + c1) * (2 * sigma12 + c2)) / (
        (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    )
    return float(ssim_map.mean().item())


def load_weights(model: torch.nn.Module, state_dict: dict, strict: bool = False):
    if strict:
        model.load_state_dict(state_dict, strict=True)
        return

    load_res = model.load_state_dict(state_dict, strict=False)
    missing = [k for k in load_res.missing_keys if k not in ALLOWED_MISMATCH]
    unexpected = [k for k in load_res.unexpected_keys if k not in ALLOWED_MISMATCH]
    if missing:
        raise RuntimeError(
            "Error(s) in loading state_dict for GeoEdgeAlignSR_v1_v5_NoCoord:\n"
            f"\tMissing keys: {missing}\n"
            f"\tUnexpected keys: {unexpected}"
        )
    ignored = sorted(set(load_res.missing_keys + load_res.unexpected_keys))
    if ignored:
        print(f"-> Ignored non-critical keys: {ignored}")


@torch.inference_mode()
def run_one(model: torch.nn.Module, device: torch.device, in_path: Path, out_path: Path, align_factor: int, gt_path: Path | None = None):
    raw, dtype = read_image_keep_dtype(in_path)
    x01 = normalize_to_01(raw, dtype)
    x_pad, h0, w0 = pad_to_multiple_np(x01, align_factor)
    x_t = torch.from_numpy(x_pad).unsqueeze(0).unsqueeze(0).to(device)

    pred = model(x_t).clamp(0.0, 1.0)
    pred_np = pred[0, 0].detach().cpu().numpy().astype(np.float32)
    pred_np = pred_np[:h0, :w0]
    out = denormalize_to_dtype(pred_np, dtype)

    if np.issubdtype(dtype, np.floating):
        out_u8 = (pred_np * 255.0).round().clip(0, 255).astype(np.uint8)
        if not imwrite_unicode(str(out_path), out_u8):
            raise OSError(f"Failed to write image: {out_path}")
    else:
        if not imwrite_unicode(str(out_path), out):
            raise OSError(f"Failed to write image: {out_path}")

    if gt_path is None or (not gt_path.exists()):
        return None

    gt_raw, gt_dtype = read_image_keep_dtype(gt_path)
    gt01 = normalize_to_01(gt_raw, gt_dtype)
    if gt01.shape != pred_np.shape:
        print(f"[WARN] GT shape mismatch: {gt_path.name} gt={gt01.shape} pred={pred_np.shape} (skip metrics)")
        return None
    psnr = compute_psnr(pred_np, gt01)
    ssim = compute_ssim(pred_np, gt01)
    return {"psnr": psnr, "ssim": ssim}


def main():
    args = parse_args()
    if MANUAL_SELECT_MODE is not None:
        args.select_mode = MANUAL_SELECT_MODE
        print(f"-> [DEBUG] Manual override active: select_mode='{args.select_mode}'")

    weights_path = resolve_weights_path(args.weights).resolve()
    input_dir = Path(args.input_dir or DEFAULT_INPUT_DIR).expanduser().resolve()
    recon_root = Path(args.recon_root or DEFAULT_RECON_PROGRESS_ROOT).expanduser().resolve()
    output_dir = None
    gt_dir = args.gt_dir.resolve() if args.gt_dir is not None else None

    device = resolve_device(args.device)
    print(f"-> Using device: {device}")
    print(f"-> Weights: {weights_path}")

    if not weights_path.exists():
        print(f"Error: Weights file not found at {weights_path}")
        sys.exit(1)
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input dir not found: {input_dir}")
        sys.exit(1)
    if gt_dir is not None and (not gt_dir.exists() or not gt_dir.is_dir()):
        print(f"Error: GT dir not found: {gt_dir}")
        sys.exit(1)

    ckpt_obj = torch.load(weights_path, map_location="cpu")
    state_dict = extract_state_dict(ckpt_obj)
    arch = infer_arch_from_state(state_dict, ckpt_obj=ckpt_obj)
    model_name_for_output = infer_model_name_for_output(ckpt_obj, weights_path)
    source_train_ts = infer_train_timestamp_from_weights_path(weights_path)
    output_dir = build_output_dir(
        recon_root,
        model_name_for_output,
        args.output_name,
        source_train_ts,
        input_dir=input_dir,
    )
    psf_path = None
    temp_psf_dir = None
    try:
        psf_path, temp_psf_dir, psf_src = resolve_psf_path(args, ckpt_obj, state_dict)
        if psf_path is None or (not psf_path.exists()):
            print(f"Error: PSF fitted path invalid or missing: {psf_path}")
            sys.exit(1)
        print(f"-> PSF source: {psf_src} ({psf_path})")

        use_band_limit = arch["use_band_limit"] if args.use_band_limit is None else bool(args.use_band_limit)
        weak_psf_enable = arch["weak_psf_enable"] if args.weak_psf_enable is None else bool(args.weak_psf_enable)
        weak_psf_k = arch["weak_psf_k"] if args.weak_psf_k is None else int(args.weak_psf_k)
        weak_psf_indices = parse_indices(args.weak_psf_indices, weak_psf_k)

        psf_deconv_reg = arch["psf_deconv_reg"] if args.psf_deconv_reg is None else float(args.psf_deconv_reg)
        psf_phys_alpha = arch["psf_phys_alpha_init"] if args.psf_phys_alpha is None else float(args.psf_phys_alpha)
        weak_psf_reg = arch["weak_psf_reg"] if args.weak_psf_reg is None else float(args.weak_psf_reg)
        weak_psf_beta_init = arch["weak_psf_beta_init"] if args.weak_psf_beta_init is None else float(args.weak_psf_beta_init)
        weak_psf_beta_scale_max = arch["weak_psf_beta_scale_max"] if args.weak_psf_beta_scale_max is None else float(args.weak_psf_beta_scale_max)
        weak_psf_gating_temp = arch["weak_psf_gating_temp"] if args.weak_psf_gating_temp is None else float(args.weak_psf_gating_temp)
        weak_psf_psf_temp = arch["weak_psf_psf_temp"] if args.weak_psf_psf_temp is None else float(args.weak_psf_psf_temp)
        weak_psf_entropy_mix = arch["weak_psf_entropy_mix"] if args.weak_psf_entropy_mix is None else float(args.weak_psf_entropy_mix)
        weak_psf_lowfreq_ratio = arch["weak_psf_lowfreq_ratio"] if args.weak_psf_lowfreq_ratio is None else float(args.weak_psf_lowfreq_ratio)

        if args.print_model_config:
            print("-> Inferred model config from checkpoint:")
            print(f"   in_ch={arch['in_ch']} base={arch['base']}")
            print(f"   use_physics_layer={arch['use_physics_layer']} use_band_limit={use_band_limit} weak_psf_enable={weak_psf_enable}")
            print(
                f"   boundary_residual_adapter_enable={arch['boundary_residual_adapter_enable']} "
                f"hidden={arch['boundary_residual_adapter_hidden']} "
                f"delta_bias={arch['boundary_residual_adapter_delta_bias']} "
                f"zero_mean={arch['boundary_residual_adapter_zero_mean']} "
                f"edge_gate={arch['boundary_residual_adapter_edge_gate']} "
                f"polarity_split={arch['boundary_residual_adapter_polarity_split']} "
                f"orientation_inputs={arch['boundary_residual_adapter_orientation_inputs']}"
            )
            print(f"   weak_psf_k={weak_psf_k} weak_psf_beta_scale_max={weak_psf_beta_scale_max}")

        model = GeoEdgeAlignSR_v1_v5_NoCoord(
            in_ch=arch["in_ch"],
            base=arch["base"],
            use_physics_layer=arch["use_physics_layer"],
            use_sigmoid_output=True,
            use_upsample_conv=True,
            use_band_limit=use_band_limit,
            band_limit_cutoff=float(args.band_limit_cutoff),
            band_limit_order=float(args.band_limit_order),
            psf_fitted_path=str(psf_path),
            psf_grid_rows=args.psf_grid_rows,
            psf_grid_cols=args.psf_grid_cols,
            psf_use_stack_mean=args.psf_use_stack_mean,
            psf_deconv_reg=float(psf_deconv_reg if psf_deconv_reg is not None else 10.0),
            psf_phys_alpha_init=float(psf_phys_alpha if psf_phys_alpha is not None else 0.10),
            psf_phys_trainable_reg=bool(args.psf_phys_trainable_reg),
            weak_psf_enable=weak_psf_enable,
            weak_psf_k=weak_psf_k,
            weak_psf_indices=weak_psf_indices,
            weak_psf_reg=float(weak_psf_reg if weak_psf_reg is not None else 30.0),
            weak_psf_beta_init=float(weak_psf_beta_init if weak_psf_beta_init is not None else 0.02),
            weak_psf_gating_temp=float(weak_psf_gating_temp if weak_psf_gating_temp is not None else 2.5),
            weak_psf_psf_temp=float(weak_psf_psf_temp if weak_psf_psf_temp is not None else 2.5),
            weak_psf_entropy_mix=float(weak_psf_entropy_mix if weak_psf_entropy_mix is not None else 0.0),
            weak_psf_trainable_reg=bool(args.weak_psf_trainable_reg),
            weak_psf_lowfreq_ratio=float(weak_psf_lowfreq_ratio if weak_psf_lowfreq_ratio is not None else 0.25),
            weak_psf_beta_min=float(args.weak_psf_beta_min),
            weak_psf_beta_max=float(args.weak_psf_beta_max),
            weak_psf_beta_scale_max=float(weak_psf_beta_scale_max if weak_psf_beta_scale_max is not None else 0.35),
            weak_psf_deconv_mode=args.weak_psf_deconv_mode,
            weak_psf_inject=args.weak_psf_inject,
            boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
            boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
            boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
            boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
            boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
            boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
            boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
            boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
            boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
        ).to(device)
        model.eval()

        load_weights(model, state_dict, strict=bool(args.strict_load))
        print("-> Weights loaded successfully.")

        # Apply physics overrides after loading checkpoint weights.
        physics_layer = getattr(model, "physics_layer", None)
        if physics_layer is not None:
            if args.psf_deconv_reg is not None and hasattr(physics_layer, "reg"):
                reg_t = getattr(physics_layer, "reg")
                if isinstance(reg_t, torch.Tensor):
                    reg_t.data.fill_(float(args.psf_deconv_reg))
            if args.psf_phys_alpha is not None and hasattr(physics_layer, "alpha"):
                alpha_t = getattr(physics_layer, "alpha")
                if isinstance(alpha_t, torch.Tensor):
                    alpha_t.data.fill_(float(args.psf_phys_alpha))
            if hasattr(physics_layer, "reg") and hasattr(physics_layer, "alpha"):
                reg_now = float(getattr(physics_layer, "reg").detach().cpu().item())
                alpha_now = float(getattr(physics_layer, "alpha").detach().cpu().item())
                print(f"-> Physics active. reg={reg_now:.6f}, alpha={alpha_now:.6f}")

        weak_block = getattr(model, "weak_psf_block", None)
        if weak_block is not None:
            if args.weak_psf_gating_temp is not None:
                weak_block.set_gating_temp(float(args.weak_psf_gating_temp))
            if args.weak_psf_psf_temp is not None:
                weak_block.set_psf_temp(float(args.weak_psf_psf_temp))
            if args.weak_psf_lowfreq_ratio is not None:
                weak_block.set_lowfreq_ratio(float(args.weak_psf_lowfreq_ratio))
            if args.weak_psf_beta_scale is not None:
                weak_block.set_beta_scale(float(args.weak_psf_beta_scale))
            if args.weak_psf_entropy_mix is not None:
                weak_block.set_entropy_mix(float(args.weak_psf_entropy_mix))

            beta_now = float(getattr(weak_block, "beta_scale", torch.tensor(float("nan"))).detach().cpu().item())
            emix_now = float(getattr(weak_block, "entropy_mix", torch.tensor(float("nan"))).detach().cpu().item())
            print(f"-> Weak PSF active. beta_scale={beta_now:.6f}, entropy_mix={emix_now:.6f}")

        if args.exts is None:
            valid_exts = set(VALID_EXTS)
        else:
            valid_exts = {e.strip().lower() for e in args.exts.split(",") if e.strip()}
            if not valid_exts:
                valid_exts = set(VALID_EXTS)

        all_image_paths = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_exts])

        if args.select_mode == "odd":
            image_paths = all_image_paths[0::2]
            print(f"-> Mode 'odd': selected {len(image_paths)}/{len(all_image_paths)}")
        elif args.select_mode == "even":
            image_paths = all_image_paths[1::2]
            print(f"-> Mode 'even': selected {len(image_paths)}/{len(all_image_paths)}")
        else:
            image_paths = all_image_paths

        if not image_paths:
            print(f"No images found in {input_dir} with exts: {sorted(valid_exts)}")
            sys.exit(0)

        recon_root.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        if source_train_ts is not None:
            print(f"-> Output tag timestamp from weight source: {source_train_ts}")
        else:
            print("-> Output tag timestamp fallback: current time (source training timestamp not found)")
        print(f"-> Found {len(image_paths)} images. Starting reconstruction...")
        print(f"-> Output dir: {output_dir}")
        print(f"-> Recon root: {recon_root}")
        print(f"-> Align factor: {args.align_factor}")
        if gt_dir is not None:
            print(f"-> GT dir: {gt_dir}")

        metric_sum = {"psnr": 0.0, "ssim": 0.0}
        metric_count = 0
        for i, p in enumerate(image_paths):
            print(f"[{i + 1}/{len(image_paths)}] Processing {p.name}...", end=" ", flush=True)
            try:
                out_path = output_dir / p.name
                gt_path = (gt_dir / p.name) if gt_dir is not None else None
                metrics = run_one(model, device, p, out_path, align_factor=args.align_factor, gt_path=gt_path)
                if metrics:
                    metric_sum["psnr"] += metrics["psnr"]
                    metric_sum["ssim"] += metrics["ssim"]
                    metric_count += 1
                    print(f"Done. PSNR={metrics['psnr']:.2f} SSIM={metrics['ssim']:.4f}")
                else:
                    print("Done.")
            except Exception as e:
                print(f"Failed! Error: {e}")

        if metric_count > 0:
            avg_psnr = metric_sum["psnr"] / metric_count
            avg_ssim = metric_sum["ssim"] / metric_count
            print(f"-> Avg PSNR/SSIM over {metric_count} pairs: PSNR={avg_psnr:.2f} SSIM={avg_ssim:.4f}")
        print(f"-> All done. Results saved to: {output_dir}")

    finally:
        if temp_psf_dir is not None:
            shutil.rmtree(temp_psf_dir, ignore_errors=True)


if __name__ == "__main__":
    torch.cuda.empty_cache()
    main()
