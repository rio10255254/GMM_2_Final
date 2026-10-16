"""R86 phase-locked block-normalized inference with shared optical input."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "model"
DEFAULT_CHECKPOINT = ROOT / "weights" / "seed" / "r79e23_parent.pth.tar"
DEFAULT_INPUT = ROOT / "data" / "inference_input"
DEFAULT_OUTPUT = ROOT / "results" / "inference_output"
PSF = MODEL_DIR / "analytic_psf_bank.mat"
CORE_SIZE = 512
HALO = 192
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}

sys.path.insert(0, str(MODEL_DIR))
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import (  # noqa: E402
    GeoEdgeAlignSR_v1_v5_NoCoord,
    BlockGroupNorm,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", np.asarray(image, dtype=np.uint8))
    if not ok:
        raise OSError(path)
    encoded.tofile(path.with_suffix(".bmp"))


def collect_images(path: Path) -> tuple[Path, list[Path]]:
    path = path.resolve()
    if path.is_file():
        return path.parent, [path]
    path.mkdir(parents=True, exist_ok=True)
    images = sorted(item for item in path.rglob("*") if item.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        raise FileNotFoundError(path)
    return path, images


def build_model(
    checkpoint_path: Path,
    device: str,
    *,
    tile_stable: bool = True,
    use_ema: bool = True,
) -> tuple[torch.nn.Module, str]:
    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        psf_fitted_path=str(PSF),
        psf_grid_rows=3,
        psf_grid_cols=3,
        psf_use_stack_mean=True,
        psf_deconv_reg=30.0,
        psf_phys_alpha_init=0.05,
        psf_phys_alpha_min=0.0,
        psf_phys_alpha_max=0.20,
        use_upsample_conv=True,
        use_band_limit=False,
        weak_psf_enable=True,
        weak_psf_k=4,
        weak_psf_beta_init=0.0,
        weak_psf_beta_scale_max=0.0,
        learnable_blur=False,
        use_bottleneck_se=False,
        boundary_residual_adapter_enable=True,
        boundary_residual_adapter_hidden=16,
        boundary_residual_adapter_max=0.018,
        boundary_residual_adapter_gate_bias=-2.0,
        boundary_residual_adapter_delta_bias=True,
        boundary_residual_adapter_zero_mean=False,
        boundary_residual_adapter_edge_gate=False,
        boundary_residual_adapter_polarity_split=False,
        boundary_residual_adapter_orientation_inputs=True,
        raw_anchor_output_mode="none",
        quality_gate_enable=False,
        tile_stable_local_norm=tile_stable,
        tile_stable_bypass_global=tile_stable,
    )
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state_key = "ema_state_dict" if use_ema and checkpoint.get("ema_state_dict") else "state_dict"
    state = checkpoint.get(state_key, checkpoint)
    cleaned = {(name[7:] if name.startswith("module.") else name): value for name, value in state.items()}
    model.load_state_dict(cleaned, strict=True)
    model.to(device).eval()
    if tile_stable:
        local_count = sum(isinstance(item, BlockGroupNorm) for item in model.modules())
        if local_count != 23 or model.tile_stable_norm_count != 23:
            raise RuntimeError(f"Expected 23 local normalization layers, found {local_count}.")
    return model, state_key


def _run(model: torch.nn.Module, image: np.ndarray, device: str) -> np.ndarray:
    if image.shape[0] % 8 or image.shape[1] % 8:
        raise ValueError(f"Model input must be divisible by 8, found {image.shape}.")
    tensor = torch.from_numpy(image.astype(np.float32) / 255.0)[None, None].to(device)
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        output = model(tensor).float().clamp(0.0, 1.0)
    return output[0, 0].cpu().numpy()


def _run_tensor(model: torch.nn.Module, tensor: torch.Tensor) -> torch.Tensor:
    if tensor.shape[-2] % 8 or tensor.shape[-1] % 8:
        raise ValueError(f"Model tensor must be divisible by 8, found {tuple(tensor.shape)}.")
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        return model(tensor).float().clamp(0.0, 1.0)


def canonical_canvas(image: np.ndarray, core_size: int = CORE_SIZE) -> tuple[np.ndarray, tuple[int, int]]:
    height, width = image.shape
    pad_bottom = (-height) % core_size
    pad_right = (-width) % core_size
    canvas = cv2.copyMakeBorder(image, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT_101)
    return canvas, (height, width)


def shared_preconditioned_canvas(
    model: torch.nn.Module,
    image: np.ndarray,
    device: str,
    core_size: int = CORE_SIZE,
    strength: float = 1.0,
) -> tuple[torch.Tensor, tuple[int, int]]:
    """Compute the optical input exactly once so full and tiled paths share it."""
    canvas, original_shape = canonical_canvas(image, core_size)
    tensor = torch.from_numpy(canvas.astype(np.float32) / 255.0)[None, None].to(device)
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=False):
        physics = model.physics_layer(tensor).float()
        conditioned = tensor + float(strength) * (physics - tensor)
    return conditioned, original_shape


def infer_canonical_full(
    model: torch.nn.Module,
    image: np.ndarray,
    device: str,
    core_size: int = CORE_SIZE,
) -> np.ndarray:
    conditioned, original_shape = shared_preconditioned_canvas(model, image, device, core_size)
    prediction = _run_tensor(model, conditioned)[0, 0].cpu().numpy()
    height, width = original_shape
    return np.clip(np.rint(prediction[:height, :width] * 255.0), 0, 255).astype(np.uint8)


def infer_phase_locked_tiled(
    model: torch.nn.Module,
    image: np.ndarray,
    device: str,
    core_size: int = CORE_SIZE,
    halo: int = HALO,
) -> np.ndarray:
    if core_size % 8 or halo % 8:
        raise ValueError("core_size and halo must both be divisible by 8")
    conditioned, original_shape = shared_preconditioned_canvas(model, image, device, core_size)
    _, _, height, width = conditioned.shape
    output = np.empty((height, width), dtype=np.float32)
    for core_y in range(0, height, core_size):
        for core_x in range(0, width, core_size):
            patch_y0 = max(0, core_y - halo)
            patch_x0 = max(0, core_x - halo)
            patch_y1 = min(height, core_y + core_size + halo)
            patch_x1 = min(width, core_x + core_size + halo)
            patch = conditioned[:, :, patch_y0:patch_y1, patch_x0:patch_x1]
            prediction = _run_tensor(model, patch)[0, 0].cpu().numpy()
            crop_y0 = core_y - patch_y0
            crop_x0 = core_x - patch_x0
            output[core_y:core_y + core_size, core_x:core_x + core_size] = prediction[
                crop_y0:crop_y0 + core_size,
                crop_x0:crop_x0 + core_size,
            ]
    original_height, original_width = original_shape
    return np.clip(np.rint(output[:original_height, :original_width] * 255.0), 0, 255).astype(np.uint8)


def difference_metrics(full: np.ndarray, tiled: np.ndarray) -> dict[str, float]:
    difference = np.abs(full.astype(np.float32) - tiled.astype(np.float32))
    return {
        "mean_abs_gray": float(difference.mean()),
        "p99_abs_gray": float(np.quantile(difference, 0.99)),
        "max_abs_gray": float(difference.max()),
        "changed_fraction": float(np.mean(difference > 0)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R84 tile-stable inference")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--mode", choices=("full", "tiled"), default="tiled")
    parser.add_argument("--core-size", type=int, default=CORE_SIZE)
    parser.add_argument("--halo", type=int, default=HALO)
    args = parser.parse_args(argv)

    checkpoint = args.checkpoint.resolve()
    model, state_key = build_model(checkpoint, args.device, tile_stable=True, use_ema=True)
    input_root, images = collect_images(args.input)
    records = []
    for source in images:
        raw = read_gray(source)
        if args.mode == "full":
            reconstructed = infer_canonical_full(model, raw, args.device, args.core_size)
        else:
            reconstructed = infer_phase_locked_tiled(model, raw, args.device, args.core_size, args.halo)
        target = args.output.resolve() / source.relative_to(input_root)
        write_bmp(target, reconstructed)
        records.append({"input": str(source), "output": str(target.with_suffix('.bmp')), "shape": list(raw.shape)})
        print(f"complete {source.name}", flush=True)
    manifest = {
        "experiment_id": "R86_R79BlockGroupNormRepair",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "state_key": state_key,
        "mode": args.mode,
        "core_size": args.core_size,
        "halo": args.halo,
        "shared_canvas_optical_preconditioner": True,
        "records": records,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "inference_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
