"""
GeoEdge R26 Inference Performance Benchmark
============================================
Measures model loading time, per-image inference latency, throughput,
GPU/CPU memory usage, and output numerical consistency (hash).

Usage:
    python AnalysisLab/r26/performance/scripts/run_inference_benchmark.py
    python AnalysisLab/r26/performance/scripts/run_inference_benchmark.py --device cpu
    python AnalysisLab/r26/performance/scripts/run_inference_benchmark.py --device cuda:1
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Resolve project paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PERF_ROOT = SCRIPT_DIR.parent
CONFIGS_DIR = PERF_ROOT / "configs"
RESULTS_ROOT = PERF_ROOT / "results"

# Add configs to sys.path for import
sys.path.insert(0, str(CONFIGS_DIR))

# Add Model/ to sys.path so inference helpers can be imported
MODEL_DIR = PERF_ROOT.parents[2] / "Model"
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

import torch

from device_config import (
    BENCHMARK_RUNS,
    CHECKPOINT,
    CUDA_DEVICE,
    DEVICE_NAME,
    INCLUDE_CPU,
    PSF_PATH,
    TEST_INPUT_DIR,
    WARMUP_RUNS,
)

# Import inference helpers from the main inference script
from GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest import (
    extract_state_dict,
    infer_arch_from_state,
    load_weights,
    normalize_to_01,
    pad_to_multiple_np,
    read_image_keep_dtype,
)
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_device_info(device: torch.device) -> dict:
    """Collect hardware and software environment info."""
    info = {
        "device_name_config": DEVICE_NAME,
        "torch_device": str(device),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }
    if device.type == "cuda" and torch.cuda.is_available():
        info["gpu_name"] = torch.cuda.get_device_name(device)
        info["gpu_memory_total_mb"] = round(
            torch.cuda.get_device_properties(device).total_memory / 1024**2, 1
        )
        info["cuda_version"] = torch.version.cuda or "N/A"
        info["cudnn_version"] = str(torch.backends.cudnn.version()) if torch.backends.cudnn.is_available() else "N/A"
    return info


def collect_input_images(input_dir: Path, max_images: int = 50) -> list[Path]:
    """Collect BMP images from the input directory."""
    patterns = ["*.bmp", "*.BMP", "*.png", "*.PNG", "*.tif", "*.TIF"]
    images: list[Path] = []
    for pat in patterns:
        images.extend(sorted(input_dir.glob(pat)))
    if not images:
        raise FileNotFoundError(f"No images found in {input_dir}")
    return images[:max_images]


def build_model(ckpt_obj: dict, state_dict: dict, arch: dict, device: torch.device) -> torch.nn.Module:
    """Build and load the R26 model for benchmarking."""
    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=arch.get("use_band_limit", False),
        psf_fitted_path=str(PSF_PATH),
        psf_grid_rows=None,
        psf_grid_cols=None,
        psf_use_stack_mean=True,
        psf_deconv_reg=float(arch.get("psf_deconv_reg") or 10.0),
        psf_phys_alpha_init=float(arch.get("psf_phys_alpha_init") or 0.10),
        weak_psf_enable=arch.get("weak_psf_enable", True),
        weak_psf_k=arch.get("weak_psf_k", 4),
        weak_psf_reg=float(arch.get("weak_psf_reg") or 30.0),
        weak_psf_beta_init=float(arch.get("weak_psf_beta_init") or 0.02),
        weak_psf_beta_scale_max=float(arch.get("weak_psf_beta_scale_max") or 0.35),
        weak_psf_gating_temp=float(arch.get("weak_psf_gating_temp") or 2.5),
        weak_psf_psf_temp=float(arch.get("weak_psf_psf_temp") or 2.5),
        weak_psf_entropy_mix=float(arch.get("weak_psf_entropy_mix") or 0.0),
        weak_psf_lowfreq_ratio=float(arch.get("weak_psf_lowfreq_ratio") or 0.25),
    ).to(device)
    model.eval()
    load_weights(model, state_dict, strict=False)
    return model


@torch.inference_mode()
def run_single_inference(model: torch.nn.Module, device: torch.device,
                         img_np: np.ndarray, align_factor: int = 64) -> np.ndarray:
    """Run a single inference pass and return the output numpy array."""
    x_pad, h0, w0 = pad_to_multiple_np(img_np, align_factor)
    x_t = torch.from_numpy(x_pad).unsqueeze(0).unsqueeze(0).to(device)
    pred = model(x_t).clamp(0.0, 1.0)
    pred_np = pred[0, 0].detach().cpu().numpy().astype(np.float32)
    return pred_np[:h0, :w0]


def compute_output_hash(output: np.ndarray) -> str:
    """SHA256 hash of quantized output for cross-device consistency check."""
    quantized = (output * 255.0).round().clip(0, 255).astype(np.uint8)
    return hashlib.sha256(quantized.tobytes()).hexdigest()


def benchmark_on_device(device: torch.device, images: list[Path],
                        warmup: int, runs: int) -> dict:
    """Run the full inference benchmark on one device."""
    is_cuda = device.type == "cuda"
    print(f"\n{'='*60}")
    print(f"  Inference Benchmark: {device}")
    print(f"{'='*60}")

    # --- Model loading ---
    print("  Loading checkpoint...")
    if is_cuda:
        # Ensure CUDA context is initialized before memory tracking
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats(device)

    t0 = time.perf_counter()
    ckpt_obj = torch.load(str(CHECKPOINT), map_location="cpu")
    state_dict = extract_state_dict(ckpt_obj)
    arch = infer_arch_from_state(state_dict)
    model = build_model(ckpt_obj, state_dict, arch, device)
    model_load_time_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  Model loaded in {model_load_time_ms:.1f} ms")

    # --- Prepare first image ---
    first_img_path = images[0]
    raw, dtype = read_image_keep_dtype(first_img_path)
    img01 = normalize_to_01(raw, dtype)

    # --- First inference (includes JIT warmup) ---
    if is_cuda:
        torch.cuda.synchronize(device)
    t0 = time.perf_counter()
    first_output = run_single_inference(model, device, img01)
    if is_cuda:
        torch.cuda.synchronize(device)
    first_inference_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  First inference: {first_inference_ms:.1f} ms")

    # --- Warmup ---
    print(f"  Warming up ({warmup} runs)...")
    for _ in range(warmup):
        run_single_inference(model, device, img01)
    if is_cuda:
        torch.cuda.synchronize(device)

    # --- Timed benchmark ---
    print(f"  Benchmarking ({runs} runs)...")
    # Cycle through all available images
    latencies: list[float] = []
    output_hashes: list[str] = []
    for i in range(runs):
        img_path = images[i % len(images)]
        raw_i, dtype_i = read_image_keep_dtype(img_path)
        img01_i = normalize_to_01(raw_i, dtype_i)

        if is_cuda:
            torch.cuda.synchronize(device)
        t0 = time.perf_counter()
        out = run_single_inference(model, device, img01_i)
        if is_cuda:
            torch.cuda.synchronize(device)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)

        if i == 0:
            output_hashes.append(compute_output_hash(out))

    latencies_arr = np.array(latencies)

    # --- Memory ---
    gpu_memory_peak_mb = None
    if is_cuda:
        gpu_memory_peak_mb = round(
            torch.cuda.max_memory_allocated(device) / 1024**2, 1
        )

    result = {
        "device": str(device),
        "device_info": collect_device_info(device),
        "checkpoint": str(CHECKPOINT),
        "test_input_dir": str(TEST_INPUT_DIR),
        "num_test_images": len(images),
        "warmup_runs": warmup,
        "benchmark_runs": runs,
        "model_load_time_ms": round(model_load_time_ms, 2),
        "first_inference_ms": round(first_inference_ms, 2),
        "mean_inference_ms": round(float(latencies_arr.mean()), 2),
        "std_inference_ms": round(float(latencies_arr.std()), 2),
        "min_inference_ms": round(float(latencies_arr.min()), 2),
        "max_inference_ms": round(float(latencies_arr.max()), 2),
        "p95_inference_ms": round(float(np.percentile(latencies_arr, 95)), 2),
        "throughput_fps": round(1000.0 / float(latencies_arr.mean()), 2),
        "gpu_memory_peak_mb": gpu_memory_peak_mb,
        "output_hash": output_hashes[0] if output_hashes else None,
        "all_latencies_ms": [round(x, 2) for x in latencies],
    }

    # --- Print summary ---
    print(f"\n  Results:")
    print(f"    Model load:      {result['model_load_time_ms']:>10.1f} ms")
    print(f"    First inference: {result['first_inference_ms']:>10.1f} ms")
    print(f"    Mean latency:    {result['mean_inference_ms']:>10.1f} ms")
    print(f"    Std latency:     {result['std_inference_ms']:>10.1f} ms")
    print(f"    P95 latency:     {result['p95_inference_ms']:>10.1f} ms")
    print(f"    Throughput:      {result['throughput_fps']:>10.1f} FPS")
    if gpu_memory_peak_mb is not None:
        print(f"    GPU peak mem:    {gpu_memory_peak_mb:>10.1f} MB")
    print(f"    Output hash:     {result['output_hash']}")

    # Cleanup
    del model
    gc.collect()
    if is_cuda:
        torch.cuda.empty_cache()

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="R26 Inference Benchmark")
    parser.add_argument("--device", type=str, default=None,
                        help="Override device (e.g., 'cuda:0', 'cpu'). "
                             "Default: use CUDA_DEVICE from config.")
    parser.add_argument("--warmup", type=int, default=None,
                        help="Override warmup runs.")
    parser.add_argument("--runs", type=int, default=None,
                        help="Override benchmark runs.")
    parser.add_argument("--no-cpu", action="store_true",
                        help="Skip CPU baseline even if INCLUDE_CPU is True.")
    return parser.parse_args()


def main():
    args = parse_args()

    # Validate paths
    if not CHECKPOINT.exists():
        print(f"Error: Checkpoint not found: {CHECKPOINT}")
        print("Please edit configs/device_config.py to set the correct CHECKPOINT path.")
        sys.exit(1)
    if not PSF_PATH.exists():
        print(f"Error: PSF file not found: {PSF_PATH}")
        print("Please edit configs/device_config.py to set the correct PSF_PATH.")
        sys.exit(1)
    if not TEST_INPUT_DIR.exists():
        print(f"Error: Test input directory not found: {TEST_INPUT_DIR}")
        print("Please edit configs/device_config.py to set the correct TEST_INPUT_DIR.")
        sys.exit(1)

    images = collect_input_images(TEST_INPUT_DIR)
    print(f"Found {len(images)} test images in {TEST_INPUT_DIR}")

    warmup = args.warmup if args.warmup is not None else WARMUP_RUNS
    runs = args.runs if args.runs is not None else BENCHMARK_RUNS
    include_cpu = INCLUDE_CPU and not args.no_cpu

    # Determine devices to benchmark
    devices: list[torch.device] = []
    if args.device is not None:
        devices.append(torch.device(args.device))
    else:
        if CUDA_DEVICE is not None and torch.cuda.is_available():
            devices.append(torch.device(f"cuda:{CUDA_DEVICE}"))
        elif CUDA_DEVICE is not None:
            print(f"Warning: CUDA_DEVICE={CUDA_DEVICE} but CUDA not available. Using CPU.")
        if include_cpu:
            devices.append(torch.device("cpu"))
        if not devices:
            devices.append(torch.device("cpu"))

    # Run benchmarks
    all_results: dict[str, dict] = {}
    for device in devices:
        result = benchmark_on_device(device, images, warmup, runs)
        all_results[str(device)] = result

    # Save results
    out_dir = RESULTS_ROOT / DEVICE_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "inference_benchmark.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
