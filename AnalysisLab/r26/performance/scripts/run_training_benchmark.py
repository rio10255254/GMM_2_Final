"""
GeoEdge R26 Training Performance Benchmark
===========================================
Measures per-epoch training time, throughput (samples/sec), and GPU memory
usage using a minimal training loop with the same model architecture and
real training data.

Supports two modes:
  - quick (default): 3 epochs, enough to get reliable per-epoch timing
  - full: run for the full number of epochs (hours)

Usage:
    python AnalysisLab/r26/performance/scripts/run_training_benchmark.py
    python AnalysisLab/r26/performance/scripts/run_training_benchmark.py --mode full
    python AnalysisLab/r26/performance/scripts/run_training_benchmark.py --device cpu --epochs 2
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import sys
import time
from pathlib import Path

import numpy as np

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# ---------------------------------------------------------------------------
# Resolve project paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PERF_ROOT = SCRIPT_DIR.parent
CONFIGS_DIR = PERF_ROOT / "configs"
RESULTS_ROOT = PERF_ROOT / "results"

sys.path.insert(0, str(CONFIGS_DIR))

# Search upward from script dir to support both repo layout and standalone package.
def _find_model_dir() -> Path:
    for ancestor in [PERF_ROOT] + list(PERF_ROOT.parents):
        candidate = ancestor / "Model"
        if candidate.is_dir() and (candidate / "GeoEdgeAlignSR_v1_Utils.py").exists():
            return candidate
    raise FileNotFoundError("Cannot find Model/ directory. Make sure it exists.")

MODEL_DIR = _find_model_dir()
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

from device_config import (
    CHECKPOINT,
    CUDA_DEVICE,
    DEVICE_NAME,
    INCLUDE_CPU,
    PSF_PATH,
    TRAINING_SRC_DIR,
    TRAINING_LBL_DIR,
    TRAINING_FULL_EPOCHS,
    TRAINING_MODE,
    TRAINING_QUICK_EPOCHS,
)

from GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest import (
    extract_state_dict,
    infer_arch_from_state,
)
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord
from GeoEdgeAlignSR_v1_Utils import imread_unicode


# ---------------------------------------------------------------------------
# Simple paired dataset (mirrors training script's PairedGrayFolder logic)
# ---------------------------------------------------------------------------

def _collect_image_paths(root: Path) -> list[Path]:
    """Recursively collect image paths under root."""
    exts = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}
    paths = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in exts and p.is_file():
            paths.append(p)
    return paths


class PairedGrayBenchmarkDataset(Dataset):
    """Minimal paired dataset for benchmark: loads (src, label) grayscale pairs.

    Expects src_dir and lbl_dir to have matching filenames (e.g. both contain
    0001.bmp, 0002.bmp, ...).  Subdirectories are searched recursively; the
    label is looked up by the same *relative* path under lbl_dir.
    """

    def __init__(self, src_dir: Path, lbl_dir: Path, crop_size: int = 256,
                 max_samples: int | None = None):
        self.src_paths = _collect_image_paths(src_dir)
        self.src_dir = Path(src_dir)
        self.lbl_dir = Path(lbl_dir)
        self.crop_size = crop_size
        if max_samples is not None:
            self.src_paths = self.src_paths[:max_samples]
        if not self.src_paths:
            raise FileNotFoundError(f"No images found under {src_dir}")

    def __len__(self) -> int:
        return len(self.src_paths)

    def __getitem__(self, idx: int):
        src_path = self.src_paths[idx]
        # Resolve label by same relative path under lbl_dir
        rel = src_path.relative_to(self.src_dir)
        lbl_path = self.lbl_dir / rel
        if not lbl_path.exists():
            lbl_path = src_path  # fallback: use src as label

        src = imread_unicode(str(src_path)).astype(np.float32)
        lbl = imread_unicode(str(lbl_path)).astype(np.float32)

        # Normalize to [0, 1]
        if src.max() > 1.0:
            src = src / 255.0
        if lbl.max() > 1.0:
            lbl = lbl / 255.0

        # Random crop
        h, w = src.shape[:2]
        cs = self.crop_size
        if h >= cs and w >= cs:
            y = np.random.randint(0, h - cs + 1)
            x = np.random.randint(0, w - cs + 1)
            src = src[y:y+cs, x:x+cs]
            lbl = lbl[y:y+cs, x:x+cs]
        elif h < cs or w < cs:
            src = np.pad(src, ((0, max(0, cs-h)), (0, max(0, cs-w))), mode="reflect")[:cs, :cs]
            lbl = np.pad(lbl, ((0, max(0, cs-h)), (0, max(0, cs-w))), mode="reflect")[:cs, :cs]

        # Ensure 2D
        if src.ndim == 3:
            src = src[:, :, 0]
        if lbl.ndim == 3:
            lbl = lbl[:, :, 0]

        return (
            torch.from_numpy(src).unsqueeze(0).float(),
            torch.from_numpy(lbl).unsqueeze(0).float(),
        )


class SyntheticBenchmarkDataset(Dataset):
    """Fallback: synthetic random patches when no real data is available."""

    def __init__(self, num_samples: int = 200, crop_size: int = 256):
        self.num_samples = num_samples
        self.crop_size = crop_size

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int):
        src = torch.randn(1, self.crop_size, self.crop_size)
        lbl = torch.randn(1, self.crop_size, self.crop_size)
        return src, lbl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_device_info(device: torch.device) -> dict:
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


def build_model_for_training(arch: dict, device: torch.device) -> nn.Module:
    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        in_ch=arch["in_ch"],
        base=arch["base"],
        use_physics_layer=arch["use_physics_layer"],
        use_sigmoid_output=True,
        use_upsample_conv=True,
        use_band_limit=arch.get("use_band_limit", False),
        psf_fitted_path=str(PSF_PATH),
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
    return model


def make_dataloader(batch_size: int = 4, crop_size: int = 256,
                    num_workers: int = 4) -> DataLoader:
    """Create a training-like dataloader from real or synthetic data."""
    src_ok = TRAINING_SRC_DIR is not None and Path(TRAINING_SRC_DIR).exists()
    lbl_ok = TRAINING_LBL_DIR is not None and Path(TRAINING_LBL_DIR).exists()

    if src_ok and lbl_ok:
        ds = PairedGrayBenchmarkDataset(
            src_dir=Path(TRAINING_SRC_DIR),
            lbl_dir=Path(TRAINING_LBL_DIR),
            crop_size=crop_size,
        )
        print(f"  Using real training data: {TRAINING_SRC_DIR} ({len(ds)} samples)")
    else:
        ds = SyntheticBenchmarkDataset(num_samples=200, crop_size=crop_size)
        reason = "paths not set" if not src_ok else f"lbl dir missing: {TRAINING_LBL_DIR}"
        print(f"  Using synthetic data ({len(ds)} samples) [{reason}]")

    return DataLoader(
        ds,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
    )


def benchmark_training_on_device(device: torch.device, num_epochs: int,
                                 mode: str) -> dict:
    """Run training benchmark on one device."""
    is_cuda = device.type == "cuda"
    print(f"\n{'='*60}")
    print(f"  Training Benchmark: {device}  (mode={mode}, epochs={num_epochs})")
    print(f"{'='*60}")

    # Load architecture from checkpoint
    print("  Loading checkpoint for architecture info...")
    ckpt_obj = torch.load(str(CHECKPOINT), map_location="cpu")
    state_dict = extract_state_dict(ckpt_obj)
    arch = infer_arch_from_state(state_dict)

    # Build model
    model = build_model_for_training(arch, device)
    num_params = sum(p.numel() for p in model.parameters())
    num_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Model params: {num_params:,} total, {num_trainable:,} trainable")

    # Optimizer and loss
    optimizer = optim.Adam(model.parameters(), lr=2e-5)
    criterion = nn.HuberLoss(delta=0.02)
    use_amp = is_cuda and hasattr(torch.cuda.amp, "GradScaler")
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp) if use_amp else None

    # Data loader
    nw = 4 if is_cuda else 0
    loader = make_dataloader(batch_size=4, crop_size=256, num_workers=nw)

    if is_cuda:
        torch.cuda.reset_peak_memory_stats(device)

    # --- Training loop ---
    epoch_times: list[float] = []
    epoch_samples: list[int] = []
    total_start = time.perf_counter()

    for epoch in range(num_epochs):
        model.train()
        epoch_start = time.perf_counter()
        samples_this_epoch = 0

        for batch_idx, (src, lbl) in enumerate(loader):
            src = src.to(device, non_blocking=True)
            lbl = lbl.to(device, non_blocking=True)

            if use_amp and scaler is not None:
                with torch.cuda.amp.autocast():
                    pred = model(src)
                    loss = criterion(pred, lbl)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                pred = model(src)
                loss = criterion(pred, lbl)
                loss.backward()
                optimizer.step()

            optimizer.zero_grad(set_to_none=True)
            samples_this_epoch += src.shape[0]

        if is_cuda:
            torch.cuda.synchronize(device)

        epoch_time = time.perf_counter() - epoch_start
        epoch_times.append(epoch_time)
        epoch_samples.append(samples_this_epoch)
        throughput = samples_this_epoch / epoch_time if epoch_time > 0 else 0
        print(f"  Epoch {epoch+1}/{num_epochs}: {epoch_time:.1f}s "
              f"({samples_this_epoch} samples, {throughput:.1f} samples/sec)")

    total_time = time.perf_counter() - total_start

    # Memory stats
    gpu_memory_peak_mb = None
    if is_cuda:
        gpu_memory_peak_mb = round(
            torch.cuda.max_memory_allocated(device) / 1024**2, 1
        )

    epoch_times_arr = np.array(epoch_times)
    total_samples = sum(epoch_samples)
    result = {
        "device": str(device),
        "device_info": collect_device_info(device),
        "mode": mode,
        "epochs_run": num_epochs,
        "batch_size": 4,
        "crop_size": 256,
        "use_amp": use_amp,
        "num_params": num_params,
        "num_trainable_params": num_trainable,
        "total_samples_processed": total_samples,
        "epoch_times_sec": [round(t, 3) for t in epoch_times],
        "mean_epoch_time_sec": round(float(epoch_times_arr.mean()), 3),
        "std_epoch_time_sec": round(float(epoch_times_arr.std()), 3),
        "throughput_samples_per_sec": round(total_samples / total_time, 2) if total_time > 0 else 0,
        "total_time_sec": round(total_time, 3),
        "gpu_memory_peak_mb": gpu_memory_peak_mb,
    }

    print(f"\n  Results:")
    print(f"    Total time:      {result['total_time_sec']:>10.1f} s")
    print(f"    Mean epoch:      {result['mean_epoch_time_sec']:>10.1f} s")
    print(f"    Throughput:      {result['throughput_samples_per_sec']:>10.1f} samples/sec")
    if gpu_memory_peak_mb is not None:
        print(f"    GPU peak mem:    {gpu_memory_peak_mb:>10.1f} MB")

    # Cleanup
    del model, optimizer, loader
    gc.collect()
    if is_cuda:
        torch.cuda.empty_cache()

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="R26 Training Benchmark")
    parser.add_argument("--mode", type=str, default=None,
                        choices=["quick", "full"],
                        help="Override training mode.")
    parser.add_argument("--epochs", type=int, default=None,
                        help="Override number of epochs.")
    parser.add_argument("--device", type=str, default=None,
                        help="Override device (e.g., 'cuda:0', 'cpu').")
    parser.add_argument("--no-cpu", action="store_true",
                        help="Skip CPU baseline even if INCLUDE_CPU is True.")
    return parser.parse_args()


def main():
    args = parse_args()

    if not CHECKPOINT.exists():
        print(f"Error: Checkpoint not found: {CHECKPOINT}")
        print("Please edit configs/device_config.py to set the correct CHECKPOINT path.")
        sys.exit(1)
    if not PSF_PATH.exists():
        print(f"Error: PSF file not found: {PSF_PATH}")
        print("Please edit configs/device_config.py to set the correct PSF_PATH.")
        sys.exit(1)

    # Determine mode and epochs
    mode = args.mode or TRAINING_MODE
    if args.epochs is not None:
        num_epochs = args.epochs
    elif mode == "quick":
        num_epochs = TRAINING_QUICK_EPOCHS
    elif TRAINING_FULL_EPOCHS is not None:
        num_epochs = TRAINING_FULL_EPOCHS
    else:
        num_epochs = 100  # training script default

    include_cpu = INCLUDE_CPU and not args.no_cpu

    # Determine devices
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
        result = benchmark_training_on_device(device, num_epochs, mode)
        all_results[str(device)] = result

    # Save results
    out_dir = RESULTS_ROOT / DEVICE_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "training_benchmark.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # Human-readable summary (Markdown, Chinese)
    summary_path = out_dir / "training_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# GeoEdge R26 訓練效能報告\n\n")
        f.write(f"- **設備名稱：** {DEVICE_NAME}\n")
        f.write(f"- **測試日期：** {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        for dev_key, r in all_results.items():
            info = r.get("device_info", {})
            gpu = info.get("gpu_name", "CPU")
            f.write(f"## {gpu} (`{dev_key}`)\n\n")
            f.write(f"### 效能指標\n\n")
            f.write(f"| 指標 | 數值 | 說明 |\n")
            f.write(f"|------|------|------|\n")
            mode_zh = "快速模式（少量 epoch 估算）" if r['mode'] == "quick" else "完整訓練"
            f.write(f"| 測試模式 | {r['mode']} | {mode_zh} |\n")
            f.write(f"| 訓練輪數 | {r['epochs_run']} | 本次實際執行的 epoch 數 |\n")
            f.write(f"| 批次大小 | {r['batch_size']} | 每次送入 GPU 的影像數量 |\n")
            amp_zh = "開啟（FP16 加速）" if r['use_amp'] else "關閉（純 FP32）"
            f.write(f"| 混合精度（AMP） | {r['use_amp']} | {amp_zh} |\n")
            f.write(f"| 模型參數量 | {r['num_params']:,} | 模型的總可學習參數數量 |\n")
            f.write(f"| **平均每輪時間** | **{r['mean_epoch_time_sec']:.1f} s** | **跑完一個 epoch 的平均秒數** |\n")
            f.write(f"| 每輪時間標準差 | {r['std_epoch_time_sec']:.3f} s | epoch 間的時間波動，越小越穩定 |\n")
            f.write(f"| **訓練吞吐量** | **{r['throughput_samples_per_sec']:.1f} samples/sec** | **每秒處理的訓練樣本數** |\n")
            f.write(f"| 總測試時間 | {r['total_time_sec']:.1f} s | 所有 epoch 的總執行時間 |\n")
            if r.get("gpu_memory_peak_mb"):
                f.write(f"| GPU 記憶體峰值 | {r['gpu_memory_peak_mb']:.1f} MB | 訓練過程中 GPU 顯存的最大佔用量 |\n")
            f.write(f"\n### 逐輪明細\n\n")
            f.write(f"| Epoch | 時間 (秒) |\n")
            f.write(f"|-------|----------|\n")
            for i, t in enumerate(r["epoch_times_sec"], 1):
                f.write(f"| {i} | {t:.3f} |\n")
            f.write(f"\n### 測試環境\n\n")
            f.write(f"| 項目 | 數值 |\n")
            f.write(f"|------|------|\n")
            f.write(f"| PyTorch 版本 | {info.get('torch_version', '?')} |\n")
            f.write(f"| CUDA 版本 | {info.get('cuda_version', 'N/A')} |\n")
            f.write(f"| cuDNN 版本 | {info.get('cudnn_version', 'N/A')} |\n")
            f.write(f"| Python 版本 | {info.get('python_version', '?')} |\n")
            f.write(f"| 作業系統 | {info.get('platform', '?')} |\n")
            f.write(f"| 處理器 | {info.get('processor', '?')} |\n")
            if info.get("gpu_memory_total_mb"):
                f.write(f"| GPU 總顯存 | {info['gpu_memory_total_mb']:.0f} MB |\n")
            f.write(f"\n")

    print(f"\nResults saved to:")
    print(f"  {out_path}")
    print(f"  {summary_path}")


if __name__ == "__main__":
    main()
