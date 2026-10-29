from __future__ import annotations

import argparse
import csv
import gc
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.cuda.amp import autocast


EXPERIMENT = Path(__file__).resolve().parent
BASE_EXPERIMENT = EXPERIMENT.parent / "BaseUNet_Baseline_20260718"
PACKAGE = EXPERIMENT.parents[1] / ".." / ".." / "Deliverables" / "Standalone_Models" / "V42_SoftLabelSNR_FullStandalone_20260709"
for path in (EXPERIMENT, BASE_EXPERIMENT, PACKAGE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from infer_base_unet import load_model as load_base_model  # noqa: E402
from infer_modern_baseline import (  # noqa: E402
    load_model as load_modern_model,
    reconstruct_tiled,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


BASE_CHECKPOINT = (
    BASE_EXPERIMENT
    / "results_full_data_fixed_psf_tiled_e30"
    / "best_base_unet.pth.tar"
)
MOSR_CHECKPOINT = (
    PACKAGE
    / "results"
    / "training_results"
    / "training_progress_V42_SoftLabelSNR_full_training_20260709_202710_20260709_202713"
    / "epoch_120.pth.tar"
)
FULL_FRAME = Path(
    str(PROJECT_ROOT / 'Analyses/20260702_100MG_displacement_analysis/raw_inputs/x_0p5um/bmp/frame_0000.bmp')
)


def import_mosr_inference():
    path = PACKAGE / "infer_v42.py"
    spec = importlib.util.spec_from_file_location("formal_mosr_inference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_mosr_model(device: torch.device) -> tuple[torch.nn.Module, dict]:
    inference = import_mosr_inference()
    checkpoint = torch.load(MOSR_CHECKPOINT, map_location="cpu")
    state = inference.extract_state_dict(checkpoint)
    arch = inference.infer_arch_from_state(state, ckpt_obj=checkpoint)
    psf_path, temp_dir = inference.build_temp_psf_mat_from_state(state)
    if psf_path is None:
        psf_path = PACKAGE / "psf" / "PSF_fitted_2D_FOVstack.mat"
    weak_k = int(arch["weak_psf_k"])
    model = inference.GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=int(arch["in_ch"]),
        base=int(arch["base"]),
        use_physics_layer=bool(arch["use_physics_layer"]),
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=bool(arch["use_band_limit"]),
        band_limit_cutoff=0.95,
        band_limit_order=8.0,
        psf_fitted_path=str(psf_path),
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=float(arch["psf_deconv_reg"] or 10.0),
        psf_phys_alpha_init=float(arch["psf_phys_alpha_init"] or 0.10),
        psf_phys_trainable_reg=False,
        weak_psf_enable=bool(arch["weak_psf_enable"]),
        weak_psf_k=weak_k,
        weak_psf_indices=None,
        weak_psf_reg=float(arch["weak_psf_reg"] or 30.0),
        weak_psf_beta_init=float(arch["weak_psf_beta_init"] or 0.02),
        weak_psf_gating_temp=float(arch["weak_psf_gating_temp"] or 2.5),
        weak_psf_psf_temp=float(arch["weak_psf_psf_temp"] or 2.5),
        weak_psf_entropy_mix=float(arch["weak_psf_entropy_mix"] or 0.0),
        weak_psf_trainable_reg=False,
        weak_psf_lowfreq_ratio=float(arch["weak_psf_lowfreq_ratio"] or 0.25),
        weak_psf_beta_min=0.0,
        weak_psf_beta_max=0.10,
        weak_psf_beta_scale_max=float(arch["weak_psf_beta_scale_max"] or 0.35),
        weak_psf_deconv_mode="clamp",
        weak_psf_inject="y2",
        boundary_residual_adapter_enable=bool(arch["boundary_residual_adapter_enable"]),
        boundary_residual_adapter_hidden=int(arch["boundary_residual_adapter_hidden"]),
        boundary_residual_adapter_max=float(arch["boundary_residual_adapter_max"]),
        boundary_residual_adapter_gate_bias=float(arch["boundary_residual_adapter_gate_bias"]),
        boundary_residual_adapter_delta_bias=bool(arch["boundary_residual_adapter_delta_bias"]),
        boundary_residual_adapter_zero_mean=bool(arch["boundary_residual_adapter_zero_mean"]),
        boundary_residual_adapter_edge_gate=bool(arch["boundary_residual_adapter_edge_gate"]),
        boundary_residual_adapter_polarity_split=bool(arch["boundary_residual_adapter_polarity_split"]),
        boundary_residual_adapter_orientation_inputs=bool(arch["boundary_residual_adapter_orientation_inputs"]),
        raw_anchor_output_mode=str(arch["raw_anchor_output_mode"]),
        raw_anchor_output_alpha=float(arch["raw_anchor_output_alpha"]),
        raw_anchor_output_sigma=float(arch["raw_anchor_output_sigma"]),
        raw_anchor_output_detail_gain=float(arch["raw_anchor_output_detail_gain"]),
        quality_gate_enable=bool(arch["quality_gate_enable"]),
        quality_gate_hidden=int(arch["quality_gate_hidden"]),
        quality_gate_scale_min=float(arch["quality_gate_scale_min"]),
        quality_gate_scale_max=float(arch["quality_gate_scale_max"]),
    ).to(device)
    model.eval()
    inference.load_weights(model, state, strict=False)
    model._benchmark_temp_psf_dir = temp_dir  # type: ignore[attr-defined]
    return model, checkpoint


def read_gray_u8(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


@torch.inference_mode()
def patch_benchmark(
    model: torch.nn.Module,
    patch: torch.Tensor,
    device: torch.device,
    iterations: int,
) -> tuple[list[float], float]:
    model.eval()
    for _ in range(5):
        with autocast(enabled=device.type == "cuda"):
            _ = model(patch)
    synchronize(device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    times: list[float] = []
    for _ in range(iterations):
        synchronize(device)
        tick = time.perf_counter()
        with autocast(enabled=device.type == "cuda"):
            output = model(patch)
        synchronize(device)
        times.append(time.perf_counter() - tick)
    if output.shape != patch.shape:
        raise RuntimeError(f"Patch output shape mismatch: {output.shape} != {patch.shape}")
    peak_mb = (
        float(torch.cuda.max_memory_allocated(device) / 2**20)
        if device.type == "cuda"
        else np.nan
    )
    return times, peak_mb


@torch.inference_mode()
def direct_full_frame(
    model: torch.nn.Module,
    image_u8: np.ndarray,
    device: torch.device,
) -> tuple[np.ndarray, float]:
    tensor = torch.from_numpy(image_u8.astype(np.float32) / 255.0)[None, None].to(device)
    pad_h = (-tensor.shape[-2]) % 64
    pad_w = (-tensor.shape[-1]) % 64
    if pad_h or pad_w:
        tensor = F.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")
    synchronize(device)
    tick = time.perf_counter()
    with autocast(enabled=device.type == "cuda"):
        output = model(tensor).clamp(0.0, 1.0)
    result = output[0, 0, : image_u8.shape[0], : image_u8.shape[1]].float().cpu().numpy()
    synchronize(device)
    return result, time.perf_counter() - tick


def summarize_times(times: list[float]) -> dict[str, float]:
    values = np.asarray(times, dtype=float)
    return {
        "mean_ms": float(np.mean(values) * 1000.0),
        "median_ms": float(np.median(values) * 1000.0),
        "p95_ms": float(np.percentile(values, 95.0) * 1000.0),
    }


def checkpoint_path(model_name: str) -> Path:
    mapping = {
        "Base U-Net": BASE_CHECKPOINT,
        "NAFNet": EXPERIMENT / "results" / "nafnet" / "best_nafnet.pth.tar",
        "EDSR": EXPERIMENT / "results" / "edsr" / "best_edsr.pth.tar",
        "MOSR": MOSR_CHECKPOINT,
    }
    return mapping[model_name]


def load_named_model(
    model_name: str,
    device: torch.device,
) -> tuple[torch.nn.Module, dict]:
    path = checkpoint_path(model_name)
    if model_name == "Base U-Net":
        return load_base_model(path, device)
    if model_name in {"NAFNet", "EDSR"}:
        return load_modern_model(path, PACKAGE, device)
    if model_name == "MOSR":
        return load_mosr_model(device)
    raise KeyError(model_name)


def main(output_root: Path, patch_iterations: int, full_iterations: int) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("The formal benchmark requires the experiment GPU")
    image = read_gray_u8(FULL_FRAME)
    crop = image[640:896, 896:1152]
    patch = torch.from_numpy(crop.astype(np.float32) / 255.0)[None, None].to(device)
    rows: list[dict[str, object]] = []
    for model_name in ("Base U-Net", "NAFNet", "EDSR", "MOSR"):
        path = checkpoint_path(model_name)
        if not path.is_file():
            raise FileNotFoundError(path)
        model, checkpoint = load_named_model(model_name, device)
        total_params = sum(parameter.numel() for parameter in model.parameters())
        trainable_params = sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        )
        patch_times, patch_peak_mb = patch_benchmark(
            model,
            patch,
            device,
            patch_iterations,
        )
        patch_stats = summarize_times(patch_times)

        for _ in range(2):
            if model_name == "MOSR":
                direct_full_frame(model, image, device)
            else:
                reconstruct_tiled(model, image, device, 256, 128, 32)
        synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
        full_times: list[float] = []
        for _ in range(full_iterations):
            if model_name == "MOSR":
                result, seconds = direct_full_frame(model, image, device)
                if result.shape != image.shape:
                    raise RuntimeError("MOSR full-frame output shape mismatch")
            else:
                result_u8, seconds = reconstruct_tiled(
                    model,
                    image,
                    device,
                    tile_size=256,
                    overlap=128,
                    tile_batch=32,
                )
                if result_u8.shape != image.shape:
                    raise RuntimeError(f"{model_name} full-frame output shape mismatch")
            full_times.append(seconds)
        full_peak_mb = float(torch.cuda.max_memory_allocated(device) / 2**20)
        full_stats = summarize_times(full_times)
        rows.append(
            {
                "method": model_name,
                "checkpoint": str(path),
                "checkpoint_epoch": int(checkpoint.get("epoch", 0)),
                "checkpoint_size_mb": path.stat().st_size / 2**20,
                "parameter_count": total_params,
                "trainable_parameter_count": trainable_params,
                "patch_height": 256,
                "patch_width": 256,
                "patch_iterations": patch_iterations,
                "patch_mean_ms": patch_stats["mean_ms"],
                "patch_median_ms": patch_stats["median_ms"],
                "patch_p95_ms": patch_stats["p95_ms"],
                "patch_peak_gpu_memory_mb": patch_peak_mb,
                "full_height": int(image.shape[0]),
                "full_width": int(image.shape[1]),
                "full_inference_mode": "direct full frame" if model_name == "MOSR" else "256/128 overlap tiled",
                "full_iterations": full_iterations,
                "full_mean_ms": full_stats["mean_ms"],
                "full_median_ms": full_stats["median_ms"],
                "full_p95_ms": full_stats["p95_ms"],
                "full_peak_gpu_memory_mb": full_peak_mb,
                "full_median_megapixels_per_second": (
                    image.size / 1.0e6 / (full_stats["median_ms"] / 1000.0)
                ),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=False, indent=2), flush=True)
        del model
        gc.collect()
        torch.cuda.empty_cache()

    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "computational_performance.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "purpose": "Computational performance benchmark on the formal experiment workstation",
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0),
        "torch_version": torch.__version__,
        "precision": "CUDA automatic mixed precision for all measured forwards",
        "synchronization": "CUDA synchronized before and after every timed forward",
        "patch_rule": "256x256 real image crop, batch size 1, five warmups",
        "full_frame_rule": (
            "Base U-Net, NAFNet, and EDSR use the deployed 256-pixel overlap-tiled path; "
            "MOSR uses its deployed direct full-frame path"
        ),
        "input_frame": str(FULL_FRAME),
    }
    (output_root / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=EXPERIMENT / "evaluation" / "runtime",
    )
    parser.add_argument("--patch-iterations", type=int, default=50)
    parser.add_argument("--full-iterations", type=int, default=8)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(
        arguments.output_root.resolve(),
        arguments.patch_iterations,
        arguments.full_iterations,
    )
