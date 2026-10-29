"""
Device configuration for R26 performance benchmark.
====================================================
This is the ONLY file you need to edit when running on a new device.
All paths must point to valid locations on the current machine.
"""
from __future__ import annotations

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[5]

# ---------------------------------------------------------------------------
# Device identity
# ---------------------------------------------------------------------------
# A short, unique name for this device. Used as the results subdirectory name.
# Examples: "RTX_3090_Main", "A100_Server", "CPU_Laptop", "RTX_4090_Lab_B"
DEVICE_NAME: str = "RTX_A6000_Main"

# ---------------------------------------------------------------------------
# Paths  (edit these to match the current machine)
# ---------------------------------------------------------------------------
# R26 model checkpoint (.pth.tar)
CHECKPOINT: Path = Path(
    str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/round26/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r26sm035_20260316_190408/weights/best_tradeoff.pth.tar')
)

# PSF fitted file (.mat)
PSF_PATH: Path = Path(
    str(PROJECT_ROOT / 'PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat')
)

# Directory containing test input images (BMP files) for inference benchmark
# Can be the single_image demo or a larger dataset directory.
TEST_INPUT_DIR: Path = Path(
    str(PROJECT_ROOT / 'Analyses/AnalysisLab/r26/single_image/inputs')
)

# Training data directories (src = input, lbl = ground truth label).
# Only needed for training benchmark; set both to None to skip or use synthetic data.
TRAINING_SRC_DIR: Path | None = Path(
    str(PROJECT_ROOT / 'Training_Data/tra_src_ring')
)
TRAINING_LBL_DIR: Path | None = Path(
    str(PROJECT_ROOT / 'Training_Data/tra_lbl_ring')
)

# ---------------------------------------------------------------------------
# Hardware selection
# ---------------------------------------------------------------------------
# GPU index to use. Set to None to run on CPU only.
CUDA_DEVICE: int | None = 0

# Whether to also run a CPU baseline in addition to GPU.
INCLUDE_CPU: bool = True

# ---------------------------------------------------------------------------
# Training benchmark settings
# ---------------------------------------------------------------------------
# "quick" = run a few epochs to measure per-epoch time (default)
# "full"  = run full training to convergence (hours)
TRAINING_MODE: str = "quick"

# Number of epochs for quick mode.
TRAINING_QUICK_EPOCHS: int = 3

# Number of epochs for full mode. None = use the training script's default.
TRAINING_FULL_EPOCHS: int | None = None

# ---------------------------------------------------------------------------
# Inference benchmark settings
# ---------------------------------------------------------------------------
# Number of warmup runs (not timed) to let JIT/CUDA warm up.
WARMUP_RUNS: int = 5

# Number of timed benchmark runs.
BENCHMARK_RUNS: int = 50

# Batch sizes to test. Current model is single-image, but kept as list for
# future expansion.
BATCH_SIZES: list[int] = [1]
