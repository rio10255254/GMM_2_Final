# -*- coding: utf-8 -*-
"""
GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py

[Problem Statement - keep at top]
1) Outputs show checkerboard/whiskers (non-natural periodic high frequency) that break MATLAB dftregistration.
2) Phase/PSR/mining can incentivize artificial HF peaks, inflating internal tiny metrics.
3) Final evaluation uses MATLAB removeMean=1, hann=1, gradient=0; validation/best must align.

[FIX] Strict Zeros Padding + Mask Erosion (r=4px) to eliminate border artifacts:
1) All shift/warp operations use zeros padding.
2) Valid mask is eroded by r=4px before any masked loss/phase calculations.
3) FFT/phase weights softened to reduce ringing.

Logging includes GMF metrics curves; pair-wise shift metrics removed.

[PATCH]
- Fix to 50-epoch rhythm (E1-10 / E11-35 / E36-50) for ramps/guards.
- Add edge-local Laplacian detail rescue with tiny weight and guard-aware modulation.
- Tighten thickening/self-band guards to brake smoothing-side terms earlier.
- Keep PSF as guard-only short burst (early tiny train + artifact-spike rescue), not long-term smoother.
"""

# [NEW SWITCHES & DEFAULTS - v5 stable-basin]
# EQ_PROB=0.45
# EQ schedule (SIMPLETEST): E1-5 off, E6-20 ramp->1.0, E21-40=1.0, E41-100 fade->0.4
# ENABLE_THICKEN_GUARD=True; reference anchors: edge_width_ref/hf_proxy_ref/cb_ref from monitor_ref.json
# DETAIL_START_EPOCH=10; W_DETAIL_BASE=0.02 (DoG edge-band detail recovery)
# EMA_ENABLE=True; EMA_DECAY=0.997
# Weak-PSF stages: freeze E1-10; beta_scale~0.12 (E11-30, LR_MULT=0.05);
#                 ramp to 0.28 by E80; hold E81-100

import os
import argparse
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import glob
import csv
import json
import time
import math
import random
import copy
import functools
from collections import OrderedDict, deque
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchmetrics.image import StructuralSimilarityIndexMeasure
from GeoEdgeAlignSR_v1_ModelA_v5_NoCoord import GeoEdgeAlignSR_v1_v5_NoCoord
# NOTE: shift_tensor_subpixel MUST support: padding_mode="zeros" and return_mask=True
from GeoEdgeAlignSR_v1_Utils import shift_tensor_subpixel, sobel_magnitude, apply_hann_and_mask


# ============================================================
# Config
# ============================================================
DEFAULT_PSF_PATH = str(Path(__file__).resolve().parents[1] / "PSF_Fitting" / "Crop_circle_FreqFiltered" / "Fits" / "PSF_fitted_2D_FOVstack.mat")
DEFAULT_PRETRAINED_PATH = os.path.join("pretrained_geoedgealign_v5", "GeoEdgeAlignSR_v1_v5.pth.tar")
FALLBACK_PRETRAINED_PATH = os.path.join("pretrained_geoedgealign_v4", "GeoEdgeAlignSR_v1_v4.pth.tar")

@dataclass
class TrainConfig:
    MODEL_NAME: str = "GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest"
    SIMPLETEST_MODE: bool = True
    SIMPLETEST_MAX_EPOCH: int = 100
    # GMF proxy expected step (optional; only used for step_err ranking if set)
    GMF_EXPECT_DX_PX: Optional[float] = None
    GMF_EXPECT_DY_PX: Optional[float] = None

    LR: float = 2e-5
    WEIGHT_DECAY: float = 0.0
    DEVICE: str = "cuda:0" if torch.cuda.is_available() else "cpu"
    LR_MIN: float = 1e-6
    LR_DECAY_ON_BAD: float = 0.5
    GEOM_MULT_DECAY: float = 0.8
    GEOM_READY_REC_DELTA: float = 0.02
    GEOM_MULT_MIN: float = 0.5
    COLLAPSE_SAT_THRESH: float = 0.60
    COLLAPSE_STD_MIN: float = 0.02
    COLLAPSE_HF_RATIO_MAX: float = 0.60

    BATCH_SIZE: int = 4  # [Revert] Fixed-size patch training.
    acc_steps: int = 1
    NUM_EPOCH: int = 100
    NUM_WORKERS: int = 4
    PIN_MEMORY: bool = True
    DATALOADER_PERSISTENT_WORKERS: bool = True
    DATALOADER_PREFETCH_FACTOR: int = 4
    CROP_SIZE: int = 256

    VAL_RATIO: float = 0.1
    VAL_BATCH_SIZE: int = 1
    SPLIT_SEED: int = 1337
    REPRO_MODE: bool = False
    REPRO_SEED: int = 1261200
    REPRO_FORCE_FIXED_SPLIT: bool = True
    REPRO_SPLIT_DIRNAME: str = "_repro"
    REPRO_NUM_WORKERS: int = 0
    REPRO_DISABLE_AMP: bool = True
    REPRO_DISABLE_TF32: bool = True
    REPRO_DETERMINISTIC: bool = True
    REPRO_STRICT_DETERMINISTIC: bool = False

    # ---- Seed sweep (disabled; single-run only) ----
    SEED_SWEEP_ENABLE: bool = False
    SEED_LIST: list = field(default_factory=lambda: [1261200])
    SEED_DETERMINISTIC: bool = False
    SEED_BASE_TAG: str = "seed"
    SEED_PER_RUN_EPOCHS: int = 50
    SEED_SWEEP_STOP_ON_GOOD: bool = False
    SEED_GOOD_THRESHOLD_STD: float = 0.16
    SEED_GOOD_THRESHOLD_PASS02: float = 0.80
    SEED_ACTIVE: int = 0

    LOAD_MODEL: bool = False
    PRETRAINED_PATH: str = DEFAULT_PRETRAINED_PATH
    PRETRAINED_FALLBACK_PATH: str = FALLBACK_PRETRAINED_PATH
    FREEZE_PHYSICS_EPOCH: int = 0
    STAGE0_EPOCHS: int = 0

    # ---- PSF-guided physics layer ----
    PSF_FITTED_PATH: str = DEFAULT_PSF_PATH
    PSF_GRID_ROWS: Optional[int] = None
    PSF_GRID_COLS: Optional[int] = None
    PSF_USE_STACK_MEAN: bool = True
    PSF_DECONV_REG: float = 10.0
    PSF_PHYS_ALPHA_INIT: float = 0.10
    PSF_PHYS_TRAINABLE_REG: bool = False
    PSF_PHYS_ALPHA_MIN: float = 0.05
    PSF_PHYS_ALPHA_MAX: float = 0.35
    PHYSICS_LR_MULT: float = 0.10

    # ---- Architectural change ----
    USE_UPSAMPLE_CONV: bool = True

    # ---- Optical band-limit ----
    USE_BAND_LIMIT: bool = False
    OPTICAL_CUTOFF: float = 0.95

    # ---- Weak PSF mixing block ----
    WEAK_PSF_ENABLE: bool = True
    WEAK_PSF_K: int = 4
    WEAK_PSF_INDICES: Optional[Tuple[int, ...]] = None
    WEAK_PSF_REG: float = 30.0
    WEAK_PSF_BETA_INIT: float = 0.02
    WEAK_PSF_TRAINABLE_REG: bool = False
    WEAK_PSF_GATING_TEMP: float = 2.5
    WEAK_PSF_PSF_TEMP: float = 2.5
    WEAK_PSF_LOWFREQ_RATIO: float = 0.25
    WEAK_PSF_BETA_MIN: float = 0.0
    WEAK_PSF_BETA_MAX: float = 0.10
    WEAK_PSF_BETA_SCALE_MAX: float = 0.35
    WEAK_PSF_ENTROPY_MIX_STAGE2: float = 0.0
    WEAK_PSF_ENTROPY_MIX_STAGE3: float = 0.05
    WEAK_PSF_LR_MULT: float = 0.05
    WEAK_PSF_STAGE0_EPOCHS: int = 10
    WEAK_PSF_STAGE1_EPOCHS: int = 30
    WEAK_PSF_STAGE2_EPOCHS: int = 80
    WEAK_PSF_STAGE3_EPOCHS: int = 100
    WEAK_PSF_BETA_SCALE_STAGE1: float = 0.12
    WEAK_PSF_BETA_SCALE_STAGE2: float = 0.28
    WEAK_PSF_BETA_SCALE_STAGE3: float = 0.28
    WEAK_PSF_LR_MULT_STAGE1: float = 0.05
    WEAK_PSF_LR_MULT_STAGE2: float = 0.05
    WEAK_PSF_LR_MULT_STAGE3: float = 0.05
    WEAK_PSF_BETA_RAMP_START_E: int = 31
    WEAK_PSF_BETA_RAMP_END_E: int = 80
    WEAK_PSF_BETA_EMA: float = 0.90
    WEAK_PSF_TOP1_MAX: float = 0.70
    WEAK_PSF_ENTROPY_MIN: float = 0.80
    WEAK_PSF_COLLAPSE_W: float = 0.005
    WEAK_PSF_COLLAPSE_START_E: int = 60
    WEAK_PSF_GATE_DECAY: float = 0.80
    WEAK_PSF_GATE_RECOVER: float = 0.05
    WEAK_PSF_GATE_FREEZE_AFTER: int = 0
    WEAK_PSF_FREEZE_ON_BAD: bool = False
    WEAK_PSF_GATE_EMA: float = 0.90
    WEAK_PSF_GUARD_GATE_MULT: float = 0.70
    WEAK_PSF_RESCUE_GATE_MULT: float = 0.50
    WEAK_PSF_EXTREME_FREEZE_EPOCHS: int = 5
    WEAK_PSF_ENTROPY_COLLAPSE_THR: float = 0.20
    WEAK_PSF_INJECT: str = "y2"
    WEAK_PSF_DECONV_MODE: str = "clamp"
    WEAK_PSF_ENTROPY_LOSS_W: float = 0.02
    WEAK_PSF_ENTROPY_LOSS_START_E: int = 60
    WEAK_PSF_ACTIVE_START_E: int = 1
    WEAK_PSF_ACTIVE_END_E: int = 100
    WEAK_PSF_GUARD_ENABLE: bool = True
    WEAK_PSF_GUARD_EDGE_UP_REL: float = 0.08
    WEAK_PSF_GUARD_HF_DROP_REL: float = 0.10
    WEAK_PSF_GUARD_HOLD_EPOCHS: int = 3

    # ---- GMF fitness weights (normalized) ----
    GMF_W_STEP_STD: float = 1.5
    GMF_W_OUTLIER: float = 2.0
    GMF_W_STEP_ERR: float = 1.0
    GMF_W_GAIN_P10: float = 0.6
    GMF_W_PROXY_MEAN: float = 0.2
    GMF_Z_BAD: float = 1.0
    GMF_FITNESS_LAST: float = 0.0
    GMF_OBJ_A: float = 1.0
    GMF_OBJ_B: float = 0.5
    GMF_OBJ_C: float = 0.02
    GMF_OBJ_D: float = 0.01
    GMF_OBJ_E: float = 10.0
    GMF_OBJ_F: float = 10.0
    GMF_OBJ_BAD_DELTA: float = 1e-4
    GMF_REC_BAD_DELTA: float = 0.15
    BEST_EPOCH_MIN: int = 20
    BEST_EPOCH_MAX: int = 60
    BEST_EDGEW_TOL: float = 0.10
    BEST_HF_TOL: float = 0.08
    BEST_EDGEW_PENALTY: float = 5.0
    BEST_HF_PENALTY: float = 5.0

    # ---- Attribution ----
    ATTRIB_WINDOW: int = 10
    ATTRIB_EVERY: int = 1

    # ---- Shift sampling (mixture biased to tiny shifts) ----
    SHIFT_MIX_TINY_P: float = 0.80
    SHIFT_MIX_MID_P: float = 0.18
    SHIFT_MIX_INT_P: float = 0.02
    SHIFT_TINY_RANGE: Tuple[float, float] = (0.01, 0.30)
    SHIFT_MID_RANGE: Tuple[float, float] = (0.30, 1.00)
    SHIFT_INT_RANGE: Tuple[float, float] = (1.0, 2.0)
    TINY_SIGMA: float = 0.02
    TINY_CLIP: float = 0.05
    MID_MAX: float = 1.00
    MAX_INT_SHIFT: int = 2
    INT_SHIFT_EXCLUDE_ZERO: bool = True
    ENABLE_SHIFT_EQ: bool = True
    EQ_PROB: float = 0.45
    EQ_WARMUP_OFF_E: int = 5
    EQ_RAMP_START_E: int = 6
    EQ_RAMP_END_E: int = 20
    EQ_FULL_END_E: int = 40
    EQ_TAIL_END_E: int = 100
    EQ_TAIL_FACTOR: float = 0.4
    EQ_SHIFT_MIX_TINY_P: float = 0.80
    EQ_SHIFT_MIX_MID_P: float = 0.20
    EQ_SHIFT_MIX_INT_P: float = 0.00
    EQ_SHIFT_TINY_RANGE: Tuple[float, float] = (0.01, 0.20)
    EQ_SHIFT_MID_RANGE: Tuple[float, float] = (0.20, 0.50)
    EQ_MAX_INT_SHIFT: int = 0
    EQ_SHIFT_INT_EXCLUDE_ZERO: bool = True
    EQ_INTERIOR_MARGIN_PAD: int = 6
    EQ_SHIFT_TINY_ONLY_ON_THICKEN: bool = True

    # ---- SimpleTest core weights ----
    W_REC: float = 1.0
    W_GRADMAG: float = 0.8
    W_EDGE_ORI_SIMPLE: float = 0.3
    W_EQ_GEOM: float = 0.5
    W_STAT: float = 0.10
    W_BAND: float = 0.10
    W_HF_LAP: float = 0.15
    ENABLE_EDGELOCAL_LAPLACIAN: bool = True
    EDGELOCAL_LAP_THR: float = 0.06
    EDGELOCAL_LAP_DILATE: int = 3
    W_EDGELOCAL_LAP_START: float = 0.00
    W_EDGELOCAL_LAP_END: float = 0.06
    EDGELOCAL_LAP_RAMP_E1: int = 6
    EDGELOCAL_LAP_RAMP_E2: int = 20
    EDGELOCAL_LAP_HF_GUARD_MULT: float = 0.50
    EDGELOCAL_LAP_GUARD_EPOCHS: int = 4
    BAND_LOSS_EVERY_N_BATCH: int = 2
    BAND_R_LOW: float = 0.15
    BAND_R_HIGH: float = 0.45
    BAND_ENERGY_EPS: float = 1e-8
    PHYS_FORWARD_ENABLE: bool = True
    W_PHYS_MAX: float = 0.05
    PHYS_WARMUP_END: int = 10
    PHYS_RAMP_END: int = 30
    W_MEAN: float = 0.0
    W_SSIM: float = 0.0
    W_EDGE: float = 0.0
    W_EQ: float = 0.0
    W_PHASE: float = 0.0
    W_SMOOTH: float = 0.0
    W_CONSISTENCY: float = 0.0
    CONSIST_MICRO_PROB: float = 1.0
    CONSIST_MICRO_MIN_PX: float = 0.1
    CONSIST_MICRO_MAX_PX: float = 0.9
    CONSIST_MACRO_MIN_PX: float = 0.0
    CONSIST_MACRO_MAX_PX: float = 0.0
    CONSIST_ON_GRAD_ONLY: bool = True
    W_GRAD_PROFILE: float = 0.0
    W_FFL: float = 0.0
    W_PERCEPTUAL: float = 0.0

    # edge-weighted Eq and grad Eq
    W_EQ_EDGE: float = 0.0
    W_EQ_GRAD: float = 0.0
    EQ_EDGE_BETA: float = 8.0
    EQ_EDGE_THR_MODE: str = "quantile"
    EQ_EDGE_THR_Q: float = 0.75
    EQ_EDGE_REF: str = "pred01"  # "pred01" or "pred_warp"
    EQ_GRAD_MODE: str = "sobel_mag"
    ENABLE_EQ_COUPLE_SMOOTH: bool = True
    ENABLE_EQ_GRAD_DIR: bool = False
    ENABLE_EQ_EDGE_WEIGHT: bool = True
    EQ_EPOCH_START: int = 1
    EQ_EPOCH_FULL: int = 5
    EQ_EPOCH_END: int = 35
    EQ_EPOCH_FADE: int = 50
    EQ_MIN_FACTOR: float = 0.3
    EQ_MAX_FACTOR: float = 1.0
    EQ_INTENSITY_MODE: str = "off"  # "off" / "warmup_only" / "on"
    EQ_INTENSITY_EARLY_END: int = 5
    EQ_INTENSITY_EARLY_SCALE: float = 0.20
    EQ_INTENSITY_WARMUP_END: int = 20
    EQ_INTENSITY_REL_WEIGHT: float = 0.10
    EQ_INTENSITY_EXTRA_SCALE: float = 0.10
    EQ_DISABLE_INTENSITY_ON_THICKEN_GUARD: bool = True

    # SSIM in Rec
    W_SSIM_START: float = 0.05
    W_SSIM_END: float = 0.05
    SSIM_ANNEAL_START_E: int = 1
    SSIM_ANNEAL_END_E: int = 1

    # Eq ramp (front-high then lower)
    W_EQ_START: float = 1.0
    W_EQ_END: float = 1.0
    EQ_RAMP_START_E: int = 1
    EQ_RAMP_END_E: int = 35

    # Edge anneal (low weight for geometry stability)
    W_EDGE_START: float = 0.0
    W_EDGE_END: float = 0.0
    EDGE_ANNEAL_START_E: int = 1
    EDGE_ANNEAL_END_E: int = 40

    # Edge alignment loss (direction + magnitude)
    EDGE_USE_SCHARR: bool = False
    EDGE_DIR_WEIGHT: float = 1.0
    EDGE_MAG_WEIGHT: float = 1.0
    EDGE_MAG_BETA: float = 0.02
    EDGE_DIR_EPS: float = 1e-6
    EDGE_SOFT_THR: float = 0.02
    EDGE_SOFT_BETA: float = 0.01
    EDGE_GATE_MAG_THRESH: float = 0.02
    EDGE_GATE_MODE: str = "abs"  # "abs" or "quantile"
    EDGE_GATE_Q: float = 0.90
    EDGE_GATE_MIN_FRAC: float = 0.005
    EDGE_LOSS_CAP: float = 0.20
    EDGE_EXTRACT_Q_INIT: float = 0.88
    EDGE_EXTRACT_Q_STEP: float = 0.03
    EDGE_EXTRACT_Q_MIN: float = 0.75
    EDGE_EXTRACT_Q_MAX: float = 0.98
    EDGE_EXTRACT_MAX_STEPS: int = 4
    EDGE_EXTRACT_USE_TOPK: bool = True
    EDGE_TOPK_TARGET_DENSITY: float = 0.18
    EDGE_DENSITY_MIN: float = 0.02
    EDGE_DENSITY_MAX: float = 0.35
    EDGE_MAG_NORM_Q: float = 0.95
    EDGE_MAG_NORM_MIN: float = 1e-3
    EDGE_N_MIN_PIX: int = 256
    EDGE_N_MIN_FRAC: float = 0.002

    # Edge profile width regularizer (scale-translation stabilizer)
    W_EDGE_PROFILE_START: float = 0.0
    W_EDGE_PROFILE_END: float = 0.0
    EDGE_PROFILE_RAMP_START_E: int = 1
    EDGE_PROFILE_RAMP_END_E: int = 30
    EDGE_PROFILE_STEP: float = 1.0
    EDGE_PROFILE_MAG_THRESH: float = 0.02
    EDGE_PROFILE_CAP: float = 0.20
    EDGE_PROFILE_PRED_GATE_RATIO: float = 0.5
    EDGE_PROFILE_DENOM_MIN: float = 0.02
    EDGE_PROFILE_DENOM_Q: float = 0.10
    EDGE_PROFILE_WIDTH_CAP: float = 3.0
    EDGE_PROFILE_MIN_PIX: int = 64
    EDGE_PROFILE_MIN_FRAC: float = 0.002
    EDGE_PROFILE_GATE_TAU_FRAC: float = 0.001
    EDGE_PROFILE_GATE_TAU_PIX: float = 32.0
    EDGE_PROFILE_GMF_BAD_K: int = 2
    EDGE_PROFILE_GMF_DECAY: float = 0.5
    EDGE_PROFILE_GMF_RECOVER: float = 0.10
    EDGE_PROFILE_GMF_MIN: float = 0.10

    # Edge orientation consistency loss
    W_EDGE_ORI_START: float = 0.0
    W_EDGE_ORI_END: float = 0.0
    EDGE_ORI_RAMP_START_E: int = 1
    EDGE_ORI_RAMP_END_E: int = 1
    EDGE_ORI_CAP: float = 0.20

    # Soft chamfer edge distance (approx)
    W_EDGE_CHAMFER_START: float = 0.0
    W_EDGE_CHAMFER_END: float = 0.0
    EDGE_CHAMFER_RAMP_START_E: int = 70
    EDGE_CHAMFER_RAMP_END_E: int = 90
    EDGE_CHAMFER_SIGMA: float = 2.0
    EDGE_CHAMFER_TAU: float = 1.0
    EDGE_CHAMFER_CAP: float = 0.30
    EDGE_CHAMFER_HUBER_BETA: float = 0.05

    # Spectral loss
    W_FFT_START: float = 0.0
    W_FFT_END: float = 0.0
    FFT_RAMP_START_E: int = 10
    FFT_RAMP_END_E: int = 28
    FFT_EPS: float = 1e-6
    FFT_LOGMAG: bool = True
    FFT_PHASE_COS: bool = True
    FFT_W_LOGMAG: float = 1.0
    FFT_W_PHASE: float = 1.0
    FFT_R_LOW: float = 0.05
    FFT_R_HIGH: float = 0.65
    FFT_BAND_SOFT: float = 0.10
    FFT_BAND_GAMMA: float = 1.0

    # Phase losses
    W_PHASE_CE_START: float = 0.0
    W_PHASE_CE_END: float = 0.0
    PHASE_CE_RAMP_START_E: int = 5
    PHASE_CE_RAMP_END_E: int = 20

    W_PHASE_PSR_START: float = 0.0
    W_PHASE_PSR_END: float = 0.0
    PHASE_PSR_RAMP_START_E: int = 5
    PHASE_PSR_RAMP_END_E: int = 20

    PHASE_TEMP: float = 0.10
    PHASE_USE_MASK_HANN: bool = True
    PHASE_REMOVE_MEAN: bool = True
    PHASE_USE_EDGE: bool = False
    PHASE_EDGE_MIX: float = 0.0
    SUBPIXEL_WIN: int = 5
    SUBPIXEL_USE_QUAD_FIT: bool = True
    SUBPIXEL_FIT_COND_MAX: float = 1e5
    SUBPIXEL_FIT_DET_EPS: float = 1e-6

    PHASE_BP_ENABLE: bool = False
    PHASE_BP_R_LOW: float = 0.10
    PHASE_BP_R_HIGH: float = 0.60
    PHASE_BP_SOFT: float = 0.02

    PSR_PEAK_RADIUS: int = 2
    PSR_OUTER_RADIUS: int = 10
    PSR_USE_LOG_RATIO: bool = True
    PSR_LAMBDA_OUTMEAN: float = 1.0
    PSR_LAMBDA_OUTMAX: float = 1.0

    # Mining (tighten threshold for tiny shifts)
    MINING_ENABLE: bool = False
    MINING_ALPHA: float = 1.1
    MINING_THRESH_PX: float = 0.02
    MINING_USE_PROPORTIONAL: bool = True
    TINY_THR: float = 0.03
    TINY_HIT_EPS: float = 0.01
    REL_ERR_EPS: float = 1e-6
    MINING_ENABLE_EPOCH: int = 40

    # ---- Contrast calibration (START EARLY, small) ----
    W_CONTRAST_START: float = 0.0
    W_CONTRAST_END: float = 0.0
    CONTRAST_RAMP_START_E: int = 1
    CONTRAST_RAMP_END_E: int = 12
    CONTRAST_USE_MEANSTD: bool = True
    CONTRAST_USE_PCTL: bool = True
    CONTRAST_P_LOW: float = 0.05
    CONTRAST_P_HIGH: float = 0.95
    CONTRAST_STD_EPS: float = 1e-6
    CONTRAST_CLIP_GRAD: float = 1.0

    # Laplacian (2nd-order) loss
    LAP_ENABLE: bool = False
    W_LAP_START: float = 0.0
    W_LAP_END: float = 0.0
    LAP_RAMP_START_E: int = 5
    LAP_RAMP_END_E: int = 25

    # Saturation penalty (anti-exposure)
    W_SAT_START: float = 0.0
    W_SAT_END: float = 0.0
    SAT_RAMP_START_E: int = 1
    SAT_RAMP_END_E: int = 10
    SAT_LOW: float = 0.02
    SAT_HIGH: float = 0.98

    PRINT_EVERY: int = 50
    SAVE_MONITOR_EVERY_EPOCH: bool = True
    SAVE_CKPT_EVERY_EPOCH: bool = True
    SAVE_CKPT_EVERY_N_EPOCH: int = 5
    SAVE_LAST_GOOD_TO_DISK: bool = False
    GRAD_CLIP_NORM: float = 1.0

    # Logging figs
    SAVE_LOSS_CURVE_EVERY_EPOCH: bool = True
    SAVE_LOSS_CURVE_EVERY_N: int = 1
    SAVE_GMF_CURVE_EVERY_EPOCH: bool = True
    SAVE_GMF_CURVE_EVERY_N: int = 1

    # Fast I/O mode (must not change training numeric path)
    FAST_IO_MODE: bool = True
    FAST_DISABLE_PLOTS: bool = True
    FAST_PLOT_EVERY_EPOCH: int = 20
    FAST_MONITOR_EVERY_EPOCH: int = 5
    FAST_VAL_EVERY_EPOCH: int = 2
    BATCH_LOG_EVERY_N: int = 5
    FAST_CSV_FLUSH_EVERY_N: int = 50
    FAST_TQDM_MININTERVAL: float = 1.0
    FAST_SAVE_PROXY_SANITY: bool = False
    FAST_IMAGE_CACHE_ENABLE: bool = True
    FAST_IMAGE_CACHE_SIZE: int = 64

    # NaN guard
    SKIP_ON_NAN: bool = True

    # EMA stabilizer
    EMA_ENABLE: bool = True
    EMA_DECAY: float = 0.997
    EMA_UPDATE_EVERY: int = 1
    EMA_START_EPOCH: int = 1

    # Acceleration toggles
    use_amp: bool = True
    use_compile: bool = False  # [CRITICAL] Disable for dynamic shapes.
    RUN_PREFLIGHT_SANITY: bool = False  # [PERF] Skip preflight checks to start faster.

    # Mask erosion (r=4px)
    MASK_ERODE_RADIUS: int = 4

    # Optional ROI mask (x, y, w, h) in pixel coords
    ROI_ENABLE: bool = False
    ROI_XYWH: tuple = (0, 0, 0, 0)

    # Anti-checkerboard penalty
    W_CB_START: float = 0.0
    W_CB_END: float = 0.0
    CB_RAMP_START_E: int = 1
    CB_RAMP_END_E: int = 30
    CB_CAP_DELTA: float = 0.10
    CB_REF_EMA: float = 0.95

    # FFT shape matching (soft, mid-band emphasis)
    W_FFT_SHAPE_START: float = 0.0
    W_FFT_SHAPE_END: float = 0.0
    FFT_SHAPE_RAMP_START_E: int = 3
    FFT_SHAPE_RAMP_END_E: int = 18
    FFT_SHAPE_R_CENTER: float = 0.35
    FFT_SHAPE_R_SIGMA: float = 0.25
    FFT_SHAPE_CAP: float = 0.02

    # Monitor thresholds
    HF_RATIO_WARN: float = 1.2

    # Anti-HF loss
    W_HF_START: float = 0.0
    W_HF_END: float = 0.0
    HF_RAMP_START_E: int = 1
    HF_RAMP_END_E: int = 30
    HF_SIGMA: float = 0.8
    HF_SMOOTH_BETA: float = 0.02
    HF_CAP_DELTA: float = 0.10
    HF_CAP_MIN: float = 0.0

    # HF ratio definition (FFT band)
    HF_RATIO_R_LOW: float = 0.55
    HF_RATIO_R_HIGH: float = 0.95

    # Dynamic gating
    HF_RATIO_DELTA: float = 0.10
    CB_SCORE_DELTA: float = 0.10
    WEIGHT_MULT_UP: float = 1.5
    WEIGHT_MULT_DOWN: float = 0.9
    WEIGHT_MULT_MAX: float = 5.0
    GMF_ARTIFACT_MULT_UP: float = 1.5
    GMF_ARTIFACT_MULT_DOWN: float = 0.95
    GMF_ARTIFACT_MULT_MAX: float = 2.0

    # Consistency schedule (avoid late-stage thickening drift)
    ENABLE_CONSIST_SCHEDULE: bool = False
    CONSIST_FACTOR_E1_E10: float = 0.40
    CONSIST_FACTOR_E1_E20: float = 0.50
    CONSIST_FACTOR_E21_E80_TARGET: float = 1.00
    CONSIST_FACTOR_E81_PLUS: float = 0.55

    # AntiHF / Checkerboard cap fuse (weak by default, short boost on spikes)
    ENABLE_CAP_FUSE: bool = False
    CAP_FACTOR_BASE: float = 0.35
    CAP_GUARD_MIN_MULT: float = 0.25
    CAP_SPIKE_BOOST: float = 0.80
    CAP_SPIKE_EPOCHS: int = 3
    CAP_SPIKE_WINDOW: int = 7
    CAP_SPIKE_THRESH_REL: float = 0.15
    CAP_SPIKE_COOLDOWN: int = 5

    # Oversmooth / thickening guard
    ENABLE_THICKEN_GUARD: bool = True
    THICKEN_GUARD_MULT: float = 0.70
    THICKEN_GUARD_MIN_MULT: float = 0.40
    THICKEN_GUARD_HOLD_EPOCHS: int = 5
    THICKEN_GUARD_PATIENCE: int = 2
    THICKEN_GUARD_RELEASE_STEP: float = 0.05
    THICKEN_EDGEWIDTH_UP_REL: float = 0.10
    THICKEN_HF_DROP_REL: float = 0.08
    THICKEN_REQUIRE_REC_IMPROVE: bool = False
    THICKEN_REC_KEY: str = "val_rec"
    THICKEN_METRIC_SOURCE: str = "monitor"
    MONITOR_REF_FILENAME: str = "monitor_ref.json"
    SELF_WARMUP_EPOCHS: int = 5
    SELF_BAND_READY_EPOCH: int = 6
    SELF_BAND_EDGE_SCORE_MIN_RATIO: float = 0.92
    SELF_BAND_EDGE_WIDTH_MAX_RATIO: float = 1.10
    SELF_BAND_HF_PROXY_MIN_RATIO: float = 0.90
    SELF_BAND_GUARD_HOLD_EPOCHS: int = 3
    SELF_BAND_DETAIL_RESCUE_EPOCHS: int = 3
    SELF_BAND_DETAIL_RESCUE_MULT: float = 1.25

    # Detail rescue (anti-thickening)
    DETAIL_RESCUE_ENABLE: bool = True
    DETAIL_RESCUE_MULT: float = 2.50
    DETAIL_RESCUE_HOLD_EPOCHS: int = 4
    DETAIL_RESCUE_RELEASE_STEP: float = 0.05
    DETAIL_RESCUE_RELEASE_EDGE_REL: float = 0.02
    DETAIL_RESCUE_RELEASE_HF_REL: float = 0.02
    DETAIL_RESCUE_START_E: int = 10
    DETAIL_RESCUE_END_E: int = 100
    DETAIL_RESCUE_FFT_SHAPE_MULT: float = 1.10
    DETAIL_RESCUE_FFT_SHAPE_END_E: int = 40
    DETAIL_RESCUE_EDGE_PROFILE_MULT: float = 1.10
    DETAIL_START_EPOCH: int = 10
    W_DETAIL_BASE: float = 0.02
    DETAIL_DOG_SIGMA1: float = 0.8
    DETAIL_DOG_SIGMA2: float = 1.6
    DETAIL_EDGE_MASK_MODE: str = "quantile"  # "quantile" or "thr"
    DETAIL_EDGE_Q: float = 0.80
    DETAIL_EDGE_THR: float = 0.04
    DETAIL_EDGE_MIN_FRAC: float = 0.02
    DETAIL_EDGE_MAX_FRAC: float = 0.35
    DETAIL_EDGE_DILATE: int = 1
    DETAIL_CHARB_EPS: float = 1e-3
    DETAIL_CB_UP_REL: float = 0.12
    DETAIL_CB_REDUCE_STEP: float = 0.25
    DETAIL_CB_MIN_MULT: float = 0.50

    ENABLE_PSF_GUARD_ONLY: bool = False
    PSF_GUARD_MAX_EPOCHS: int = 10
    PSF_GUARD_ON_ARTIFACT_SPIKE: bool = True
    PSF_GUARD_HOLD_EPOCHS: int = 3
    PSF_LR_MULT_GUARD: float = 0.25

    # Monitor edge-width metric sampling (fixed strategy)
    EDGE_WIDTH_TOPK: int = 2000
    EDGE_WIDTH_PROFILE_LEN: int = 41

    # 100-epoch high-success control (rescue only; no early abort by default)
    TRAIN_MODE_100E: bool = False
    ENABLE_EARLY_RESCUE: bool = False
    ENABLE_RESCUE: bool = True
    ENABLE_EARLY_ABORT: bool = False
    EARLY_ABORT_DEBUG_BREAK: bool = False
    EARLY_BASELINE_EPOCHS: Tuple[int, int] = (2, 3)
    EARLY_RESCUE_EPOCH_START: int = 8
    EARLY_RESCUE_EPOCH_END: int = 12
    EARLY_RESCUE_EDGEWIDTH_UP_REL: float = 0.08
    EARLY_RESCUE_HF_DROP_REL: float = 0.12
    EARLY_RESCUE_THICKEN_TRIGGER_K: int = 2
    RESCUE_HOLD_EPOCHS: int = 4
    RESCUE_START_EPOCH: int = 6
    RESCUE_EDGEW_UP_REL: float = 0.10
    RESCUE_HF_DROP_REL: float = 0.08
    RESCUE_GMF_DROP_REL: float = 0.05
    RESCUE_GMF_DROP_ABS: float = 1e-4
    RESCUE_LR_MULT: float = 0.50
    RESCUE_LR_RELEASE_STEP: float = 0.05
    RESCUE_EQ_MULT: float = 0.50
    RESCUE_EQ_RELEASE_STEP: float = 0.05
    RESCUE_DETAIL_MULT: float = 2.50
    RESCUE_COOLDOWN_EPOCHS: int = 3
    RESCUE_CONSIST_MULT: float = 0.60
    RESCUE_EDGE_PROFILE_MULT: float = 1.15
    RESCUE_EDGE_PROFILE_MULT_MAX: float = 1.5
    EARLY_ABORT_EPOCHS: Tuple[int, int] = (20, 25)
    EARLY_ABORT_EDGEWIDTH_BAND_REL: float = 0.06
    EARLY_ABORT_HF_BAND_REL: float = 0.08

    # Sequence proxy metrics
    SEQ_METRIC_SAMPLES: int = 8
    E_SEQ_ENABLE: int = 15
    SEQ_TIE_EPS: float = 1e-4

    # Edge loss robustness
    EDGE_CLIP_MAX: float = 2.0
    EDGE_CHARB_EPS: float = 1e-3

    # GMF proxy validation (internal; no external tool)
    GMF_VALIDATE_ENABLE: bool = True
    GMF_VALIDATE_EVERY_N: int = 2
    GMF_VAL_NUM_FRAMES: int = 20
    GMF_SCORE_PASS_THRESH: float = 90.0
    GMF_PASS_DELTA: float = 0.2
    GMF_OUTLIER_T: float = 0.5
    GMF_OUTLIER_T_REL: float = 0.10
    GMF_PASS_TIE_EPS: float = 1.0
    GMF_P10_TIE_EPS: float = 0.1
    GMF_STEPERR_TIE_EPS: float = 1e-6
    GMF_SCALE_DEV_TIE_EPS: float = 1e-6
    GMF_STD_TIE_EPS: float = 1e-6
    GMF_REC_TIE_EPS: float = 1e-6
    GMF_SSIM_TIE_EPS: float = 1e-6
    GMF_STEP_ERR_CAP: float = 0.10
    GMF_POS_STD_CAP: float = 0.20
    GMF_BAD_STREAK: int = 2

    PROXY_SEARCH_RADIUS: int = 12
    PROXY_COARSE_STRIDE: int = 4
    PROXY_FINE_STRIDE: int = 1
    PROXY_ORI_WEIGHT: float = 0.5
    PROXY_CHAMFER_NORM: float = 3.0
    PROXY_SCORE_NORM: float = 1.0
    PROXY_EDGE_Q: float = 0.90
    PROXY_EDGE_DENSITY_MIN: float = 0.02
    PROXY_EDGE_DENSITY_MAX: float = 0.35
    PROXY_MATCH_DIST: float = 2.0
    PROXY_MATCH_ANG_DEG: float = 20.0
    PROXY_MATCH_SIGMA_D: float = 1.0
    PROXY_MATCH_SIGMA_ANG_DEG: float = 15.0
    PROXY_INVALID_SCORE: float = 0.0
    PROXY_INVALID_PENALTY: float = 999.0
    PROXY_INVALID_RATE_MAX: float = 0.20
    PROXY_SCORE_GATE: float = 20.0
    PROXY_PASS_GATE: float = 50.0
    PROXY_SCALE_ENABLE: bool = False
    PROXY_SCALE_MIN: float = 0.98
    PROXY_SCALE_MAX: float = 1.02
    PROXY_SCALE_STEP: float = 0.01


CFG = TrainConfig()


# ============================================================
# Checkpoint helpers
# ============================================================
def save_ckpt(state: dict, path: str):
    tmp = path + ".tmp"
    torch.save(state, tmp)
    os.replace(tmp, path)

def load_ckpt(path: str, model: nn.Module, optimizer=None, ema_model: Optional[nn.Module] = None) -> Tuple[int, bool]:
    ckpt = torch.load(path, map_location=CFG.DEVICE)
    state_dict = ckpt["state_dict"]
    # Remove runtime buffer that causes strict loading mismatch (initialized as None)
    if "band_limit.filter_mask" in state_dict:
        del state_dict["band_limit.filter_mask"]
    model.load_state_dict(state_dict, strict=True)
    if (optimizer is not None) and ("optimizer" in ckpt):
        optimizer.load_state_dict(ckpt["optimizer"])
    ema_loaded = False
    if (ema_model is not None) and ("ema_state_dict" in ckpt) and (ckpt["ema_state_dict"] is not None):
        ema_model.load_state_dict(ckpt["ema_state_dict"], strict=True)
        ema_loaded = True
    epoch = int(ckpt.get("epoch", 0))
    return epoch, ema_loaded


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
TRAINING_PROGRESS_ROOT = os.path.join(PROJECT_ROOT, "Traing_Progress")
MODEL_NAME_BASE = CFG.MODEL_NAME
RUN_TAG_BASE = MODEL_NAME_BASE
RUN_TAG = RUN_TAG_BASE
RUN_TS = None

TRAIN_SRC_DIR = os.path.join(SCRIPT_DIR, "..", "Training_Data", "generated_convolved")
TRAIN_LBL_DIR = os.path.join(SCRIPT_DIR, "..", "Training_Data", "generated")

PROGRESS_DIR = os.path.join(TRAINING_PROGRESS_ROOT, f"training_progress_{RUN_TAG_BASE}")
PRETRAINED_DIR = os.path.join(PROGRESS_DIR, "weights")


def _configure_run_paths():
    global RUN_TAG, PRETRAINED_DIR, PROGRESS_DIR, RUN_TS
    RUN_TS = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    RUN_TAG = f"{MODEL_NAME_BASE}_{RUN_TS}"
    CFG.MODEL_NAME = MODEL_NAME_BASE
    PROGRESS_DIR = os.path.join(TRAINING_PROGRESS_ROOT, f"training_progress_{RUN_TAG}")
    PRETRAINED_DIR = os.path.join(PROGRESS_DIR, "weights")
    os.makedirs(PRETRAINED_DIR, exist_ok=True)
    os.makedirs(PROGRESS_DIR, exist_ok=True)


def _write_run_meta(seed: int, deterministic: bool, use_amp: bool):
    meta = {
        "seed": int(seed),
        "seed_deterministic": bool(deterministic),
        "run_tag": RUN_TAG,
        "model_name": CFG.MODEL_NAME,
        "progress_dir": PROGRESS_DIR,
        "pretrained_dir": PRETRAINED_DIR,
        "device": str(CFG.DEVICE),
        "amp": bool(use_amp),
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "tf32_matmul": bool(getattr(torch.backends.cuda.matmul, "allow_tf32", False)) if hasattr(torch.backends, "cuda") else False,
        "tf32_cudnn": bool(getattr(torch.backends.cudnn, "allow_tf32", False)),
        "torch_version": torch.__version__,
        "cuda_version": torch.version.cuda if hasattr(torch, "version") else None,
        "cudnn_version": torch.backends.cudnn.version(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_local": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    meta_path = os.path.join(PROGRESS_DIR, "run_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _append_seed_sweep_summary(path: str, summary: dict):
    header = [
        "seed",
        "best_epoch",
        "best_proxy_score",
        "best_step_err",
        "best_pos_std_sum",
        "best_edge_width",
        "best_hf_proxy",
        "best_pass02_estimate",
    ]
    exists = os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        row = [
            summary.get("seed", 0),
            summary.get("best_epoch", np.nan),
            summary.get("best_proxy_score", np.nan),
            summary.get("best_step_err", np.nan),
            summary.get("best_pos_std_sum", np.nan),
            summary.get("best_edge_width", np.nan),
            summary.get("best_hf_proxy", np.nan),
            summary.get("best_pass02_estimate", np.nan),
        ]
        w.writerow([_safe_csv_value(v) for v in row])


def set_global_seed(seed: int, deterministic: bool):
    seed = int(seed)
    deterministic = bool(deterministic)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = deterministic
    torch.backends.cudnn.benchmark = not deterministic

    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        torch.backends.cuda.matmul.allow_tf32 = not deterministic
    if hasattr(torch.backends, "cudnn") and hasattr(torch.backends.cudnn, "allow_tf32"):
        torch.backends.cudnn.allow_tf32 = not deterministic

    if hasattr(torch, "use_deterministic_algorithms"):
        strict = bool(getattr(CFG, "REPRO_STRICT_DETERMINISTIC", False)) and deterministic
        torch.use_deterministic_algorithms(strict)


def _apply_repro_runtime_flags():
    repro_mode = bool(CFG.REPRO_MODE)
    deterministic = repro_mode and bool(CFG.REPRO_DETERMINISTIC)
    seed = int(CFG.REPRO_SEED if repro_mode else CFG.SPLIT_SEED)
    set_global_seed(seed, deterministic)


def _worker_init_fn_seed(worker_id: int, base_seed: int):
    worker_seed = int(base_seed) + int(worker_id)
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    torch.manual_seed(worker_seed)


def _make_worker_init_fn(base_seed: int):
    return functools.partial(_worker_init_fn_seed, base_seed=int(base_seed))


# ============================================================
# Dataset
# ============================================================
IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def collect_image_paths(root_dir: str, recursive: bool = True):
    root_abs = os.path.abspath(root_dir)
    if not os.path.isdir(root_abs):
        return []

    paths = []
    if recursive:
        for cur_root, _, files in os.walk(root_abs):
            for fname in files:
                if os.path.splitext(fname)[1].lower() in IMAGE_EXTENSIONS:
                    paths.append(os.path.join(cur_root, fname))
    else:
        for fname in os.listdir(root_abs):
            full = os.path.join(root_abs, fname)
            if os.path.isfile(full) and os.path.splitext(fname)[1].lower() in IMAGE_EXTENSIONS:
                paths.append(full)
    return sorted(paths)


class PairedGrayFolder(Dataset):
    def __init__(self, src_dir: str, lbl_dir: str, crop_size: int = 256,
                 src_paths=None, random_crop: bool = True):
        self.src_dir = os.path.abspath(src_dir)
        self.lbl_dir = os.path.abspath(lbl_dir)
        if src_paths is None:
            self.src_paths = collect_image_paths(self.src_dir, recursive=True)
        else:
            self.src_paths = list(src_paths)

        self.crop_size = int(crop_size)
        self.random_crop = bool(random_crop)
        self._cache_enabled = bool(CFG.FAST_IO_MODE and CFG.FAST_IMAGE_CACHE_ENABLE)
        self._cache_max = max(0, int(CFG.FAST_IMAGE_CACHE_SIZE)) if self._cache_enabled else 0
        self._pair_cache = OrderedDict()
        if len(self.src_paths) == 0:
            raise RuntimeError(f"No training images found in {self.src_dir}")

    def __len__(self):
        return len(self.src_paths)

    @staticmethod
    def _imread_gray(path: str) -> np.ndarray:
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise RuntimeError(f"Failed to read image: {path}")
        if img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if img.dtype == np.uint16:
            img = img.astype(np.float32) / 65535.0
        else:
            img = img.astype(np.float32) / 255.0
        return img

    def _load_pair(self, src_path: str):
        if self._cache_max > 0 and src_path in self._pair_cache:
            src_c, lbl_c = self._pair_cache[src_path]
            self._pair_cache.move_to_end(src_path, last=True)
            return src_c, lbl_c

        name = os.path.basename(src_path)
        rel_path = os.path.relpath(src_path, self.src_dir)
        lbl_candidates = [os.path.join(self.lbl_dir, rel_path), os.path.join(self.lbl_dir, name)]
        lbl_path = None
        for cand in lbl_candidates:
            if os.path.exists(cand):
                lbl_path = cand
                break
        if lbl_path is None:
            raise RuntimeError(
                f"Label not found for {name}: expected one of {lbl_candidates[0]} or {lbl_candidates[1]}"
            )
        src = self._imread_gray(src_path)
        lbl = self._imread_gray(lbl_path)

        if self._cache_max > 0:
            self._pair_cache[src_path] = (src, lbl)
            self._pair_cache.move_to_end(src_path, last=True)
            if len(self._pair_cache) > self._cache_max:
                self._pair_cache.popitem(last=False)
        return src, lbl

    def _pad_if_needed(self, src: np.ndarray, lbl: np.ndarray):
        h, w = src.shape
        cs = self.crop_size
        if (h < cs) or (w < cs):
            pad_h = max(0, cs - h)
            pad_w = max(0, cs - w)
            src = np.pad(src, ((0, pad_h), (0, pad_w)), mode="reflect")
            lbl = np.pad(lbl, ((0, pad_h), (0, pad_w)), mode="reflect")
        return src, lbl

    def __getitem__(self, idx: int):
        src, lbl = self._load_pair(self.src_paths[idx])
        src, lbl = self._pad_if_needed(src, lbl)
        h, w = src.shape
        cs = self.crop_size
        if self.random_crop:
            y0 = np.random.randint(0, h - cs + 1)
            x0 = np.random.randint(0, w - cs + 1)
        else:
            y0 = (h - cs) // 2
            x0 = (w - cs) // 2

        src = src[y0:y0 + cs, x0:x0 + cs]
        lbl = lbl[y0:y0 + cs, x0:x0 + cs]

        src_t = torch.from_numpy(src).unsqueeze(0)
        lbl_t = torch.from_numpy(lbl).unsqueeze(0)

        return src_t, lbl_t


def make_train_val_loaders():
    all_src_paths = collect_image_paths(TRAIN_SRC_DIR, recursive=True)
    if len(all_src_paths) == 0:
        raise RuntimeError(f"No training images found in {TRAIN_SRC_DIR}")

    val_ratio = float(CFG.VAL_RATIO)
    val_ratio = max(0.0, min(0.95, val_ratio))
    use_repro = bool(CFG.REPRO_MODE) or bool(getattr(CFG, "SEED_DETERMINISTIC", False))
    seed = int(getattr(CFG, "SEED_ACTIVE", 0))
    if seed <= 0:
        seed = int(CFG.REPRO_SEED if CFG.REPRO_MODE else CFG.SPLIT_SEED)
    num_workers = int(CFG.REPRO_NUM_WORKERS if use_repro else CFG.NUM_WORKERS)
    val_workers = 0 if use_repro else max(0, int(CFG.NUM_WORKERS) // 2)

    g = None
    worker_init_fn = None
    if use_repro:
        g = torch.Generator()
        g.manual_seed(seed)
        worker_init_fn = _make_worker_init_fn(seed)

    def _build_split_indices():
        rng = np.random.RandomState(seed)
        idx = np.arange(len(all_src_paths), dtype=np.int64)
        rng.shuffle(idx)
        if val_ratio <= 0.0:
            return idx, np.empty(0, dtype=np.int64)
        n_val = max(1, int(round(len(all_src_paths) * val_ratio)))
        val_idx_local = idx[:n_val]
        train_idx_local = idx[n_val:]
        return train_idx_local, val_idx_local

    if use_repro and CFG.REPRO_FORCE_FIXED_SPLIT:
        split_dir = os.path.join(PROGRESS_DIR, CFG.REPRO_SPLIT_DIRNAME, CFG.MODEL_NAME)
        os.makedirs(split_dir, exist_ok=True)
        train_idx_path = os.path.join(split_dir, "train_idx.npy")
        val_idx_path = os.path.join(split_dir, "val_idx.npy")
        split_meta_path = os.path.join(split_dir, "split_meta.json")
        if os.path.exists(train_idx_path) and os.path.exists(val_idx_path):
            train_idx = np.load(train_idx_path).astype(np.int64, copy=False)
            val_idx = np.load(val_idx_path).astype(np.int64, copy=False)
            print(f"[REPRO][SPLIT] load fixed split: {split_dir}")
        else:
            train_idx, val_idx = _build_split_indices()
            np.save(train_idx_path, train_idx.astype(np.int64))
            np.save(val_idx_path, val_idx.astype(np.int64))
            split_meta = {
                "seed": int(seed),
                "val_ratio": float(val_ratio),
                "N_total": int(len(all_src_paths)),
                "created_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with open(split_meta_path, "w", encoding="utf-8") as f:
                json.dump(split_meta, f, indent=2)
            print(f"[REPRO][SPLIT] save fixed split: {split_dir}")
    else:
        train_idx, val_idx = _build_split_indices()

    train_paths = [all_src_paths[int(i)] for i in train_idx.tolist()]
    val_paths = [all_src_paths[int(i)] for i in val_idx.tolist()]
    if len(train_paths) == 0:
        raise RuntimeError("[FATAL] Empty training split; adjust VAL_RATIO or dataset size.")

    train_ds = PairedGrayFolder(
        TRAIN_SRC_DIR, TRAIN_LBL_DIR,
        crop_size=CFG.CROP_SIZE,
        src_paths=train_paths,
        random_crop=True,
    )

    train_loader_kwargs = dict(
        dataset=train_ds,
        batch_size=CFG.BATCH_SIZE,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=CFG.PIN_MEMORY,
        drop_last=True,
    )
    if g is not None:
        train_loader_kwargs["generator"] = g
    if worker_init_fn is not None:
        train_loader_kwargs["worker_init_fn"] = worker_init_fn
    if num_workers > 0:
        train_loader_kwargs["persistent_workers"] = bool(getattr(CFG, "DATALOADER_PERSISTENT_WORKERS", True))
        train_loader_kwargs["prefetch_factor"] = max(2, int(getattr(CFG, "DATALOADER_PREFETCH_FACTOR", 2)))
    train_loader = DataLoader(**train_loader_kwargs)
    if len(val_paths) == 0:
        return train_loader, None

    val_ds = PairedGrayFolder(
        TRAIN_SRC_DIR, TRAIN_LBL_DIR,
        crop_size=CFG.CROP_SIZE,
        src_paths=val_paths,
        random_crop=False,
    )
    val_loader_kwargs = dict(
        dataset=val_ds,
        batch_size=CFG.VAL_BATCH_SIZE,
        shuffle=False,
        num_workers=val_workers,
        pin_memory=CFG.PIN_MEMORY,
        drop_last=False,
    )
    if g is not None:
        val_loader_kwargs["generator"] = g
    if worker_init_fn is not None:
        val_loader_kwargs["worker_init_fn"] = worker_init_fn
    if val_workers > 0:
        val_loader_kwargs["persistent_workers"] = bool(getattr(CFG, "DATALOADER_PERSISTENT_WORKERS", True))
        val_loader_kwargs["prefetch_factor"] = max(2, int(getattr(CFG, "DATALOADER_PREFETCH_FACTOR", 2)))
    val_loader = DataLoader(**val_loader_kwargs)
    return train_loader, val_loader


def _unpack_batch(batch):
    if isinstance(batch, dict):
        src = batch.get("src")
        lbl = batch.get("lbl")
        return src, lbl
    if isinstance(batch, (list, tuple)):
        if len(batch) == 2:
            return batch[0], batch[1]
        if len(batch) >= 3:
            return batch[0], batch[1]
    raise ValueError(f"Unsupported batch format: {type(batch)}")


# ============================================================
# Losses & helpers
# ============================================================
def _linear_schedule(epoch1: int, start_e: int, end_e: int, v0: float, v1: float) -> float:
    if end_e <= start_e:
        return float(v1)
    if epoch1 <= start_e:
        return float(v0)
    if epoch1 >= end_e:
        return float(v1)
    t = (epoch1 - start_e) / float(end_e - start_e)
    return float(v0 + (v1 - v0) * t)


def get_eq_factor(epoch1: int) -> float:
    if not CFG.ENABLE_SHIFT_EQ:
        return 0.0
    if bool(getattr(CFG, "SIMPLETEST_MODE", False)):
        if epoch1 <= 0:
            return 0.0
        warmup_off = int(getattr(CFG, "EQ_WARMUP_OFF_E", 5))
        ramp_start = int(getattr(CFG, "EQ_RAMP_START_E", 6))
        ramp_end = int(getattr(CFG, "EQ_RAMP_END_E", 20))
        full_end = int(getattr(CFG, "EQ_FULL_END_E", 40))
        tail_end = int(getattr(CFG, "EQ_TAIL_END_E", 100))
        tail_factor = float(getattr(CFG, "EQ_TAIL_FACTOR", 0.4))
        if epoch1 <= warmup_off:
            return 0.0
        if epoch1 <= ramp_end:
            ramp_start = max(1, ramp_start)
            denom = max(1, ramp_end - ramp_start)
            t = max(0.0, min(1.0, (epoch1 - ramp_start) / float(denom)))
            return float(max(0.0, min(1.0, t)))
        if epoch1 <= full_end:
            return 1.0
        if epoch1 <= tail_end:
            denom = max(1, tail_end - full_end)
            t = max(0.0, min(1.0, (epoch1 - full_end) / float(denom)))
            return float(1.0 + (tail_factor - 1.0) * t)
        return float(tail_factor)

    start_e = int(CFG.EQ_EPOCH_START)
    full_e = int(CFG.EQ_EPOCH_FULL)
    end_e = int(CFG.EQ_EPOCH_END)
    fade_e = int(CFG.EQ_EPOCH_FADE)

    if epoch1 < start_e:
        raw = 0.0
    elif epoch1 <= full_e:
        denom = max(1, full_e - start_e)
        raw = (epoch1 - start_e) / float(denom)
    elif epoch1 <= end_e:
        raw = 1.0
    elif epoch1 <= fade_e:
        denom = max(1, fade_e - end_e)
        raw = 1.0 - (epoch1 - end_e) / float(denom)
    else:
        raw = 0.0

    raw = max(0.0, min(1.0, raw))
    fmin = float(CFG.EQ_MIN_FACTOR)
    fmax = float(CFG.EQ_MAX_FACTOR)
    if fmax < fmin:
        fmin, fmax = fmax, fmin
    return float(fmin + (fmax - fmin) * raw)


def get_consistency_factor(epoch1: int) -> float:
    if bool(getattr(CFG, "SIMPLETEST_MODE", False)):
        if epoch1 <= 10:
            return float(getattr(CFG, "CONSIST_FACTOR_E1_E10", CFG.CONSIST_FACTOR_E1_E20))
        if epoch1 <= 20:
            return float(CFG.CONSIST_FACTOR_E1_E20)
        return 1.0
    if not bool(CFG.ENABLE_CONSIST_SCHEDULE):
        return 1.0
    if epoch1 <= 20:
        return float(CFG.CONSIST_FACTOR_E1_E20)
    if epoch1 <= 80:
        return _linear_schedule(
            epoch1,
            start_e=21,
            end_e=80,
            v0=float(CFG.CONSIST_FACTOR_E1_E20),
            v1=float(CFG.CONSIST_FACTOR_E21_E80_TARGET),
        )
    return float(CFG.CONSIST_FACTOR_E81_PLUS)


def get_edgelocal_lap_weight(epoch1: int) -> float:
    if not bool(getattr(CFG, "ENABLE_EDGELOCAL_LAPLACIAN", False)):
        return 0.0
    if epoch1 <= 5:
        return 0.0
    e1 = max(6, int(getattr(CFG, "EDGELOCAL_LAP_RAMP_E1", 6)))
    e2 = max(e1 + 1, int(getattr(CFG, "EDGELOCAL_LAP_RAMP_E2", 20)))
    w0 = float(getattr(CFG, "W_EDGELOCAL_LAP_START", 0.0))
    w1 = float(getattr(CFG, "W_EDGELOCAL_LAP_END", 0.06))
    if epoch1 < e1:
        return 0.0
    if epoch1 <= e2:
        return _linear_schedule(epoch1, e1, e2, w0, w1)
    return w1


def get_epoch_weights(epoch1: int):
    if bool(getattr(CFG, "SIMPLETEST_MODE", False)):
        w_ssim = _linear_schedule(
            epoch1,
            CFG.SSIM_ANNEAL_START_E,
            CFG.SSIM_ANNEAL_END_E,
            CFG.W_SSIM_START,
            CFG.W_SSIM_END,
        )
        return (
            float(CFG.W_REC), 0.0, 0.0, 0.0, 0.0, 0.0,
            w_ssim, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        )

    w_eq = float(CFG.W_EQ)
    w_edge = float(CFG.W_EDGE) * _linear_schedule(
        epoch1, CFG.EDGE_ANNEAL_START_E, CFG.EDGE_ANNEAL_END_E, CFG.W_EDGE_START, CFG.W_EDGE_END
    )
    w_edge_profile = _linear_schedule(
        epoch1, CFG.EDGE_PROFILE_RAMP_START_E, CFG.EDGE_PROFILE_RAMP_END_E,
        CFG.W_EDGE_PROFILE_START, CFG.W_EDGE_PROFILE_END
    )
    w_edge_ori = _linear_schedule(
        epoch1, CFG.EDGE_ORI_RAMP_START_E, CFG.EDGE_ORI_RAMP_END_E,
        CFG.W_EDGE_ORI_START, CFG.W_EDGE_ORI_END
    )
    w_edge_chamfer = _linear_schedule(
        epoch1, CFG.EDGE_CHAMFER_RAMP_START_E, CFG.EDGE_CHAMFER_RAMP_END_E,
        CFG.W_EDGE_CHAMFER_START, CFG.W_EDGE_CHAMFER_END
    )
    w_ssim = _linear_schedule(epoch1, CFG.SSIM_ANNEAL_START_E, CFG.SSIM_ANNEAL_END_E, CFG.W_SSIM_START, CFG.W_SSIM_END)
    w_fft = _linear_schedule(epoch1, CFG.FFT_RAMP_START_E, CFG.FFT_RAMP_END_E, CFG.W_FFT_START, CFG.W_FFT_END)
    w_fft_shape = _linear_schedule(
        epoch1, CFG.FFT_SHAPE_RAMP_START_E, CFG.FFT_SHAPE_RAMP_END_E,
        CFG.W_FFT_SHAPE_START, CFG.W_FFT_SHAPE_END
    )
    w_phase_ce = _linear_schedule(
        epoch1, CFG.PHASE_CE_RAMP_START_E, CFG.PHASE_CE_RAMP_END_E,
        CFG.W_PHASE_CE_START, CFG.W_PHASE_CE_END
    )
    w_phase_psr = _linear_schedule(
        epoch1, CFG.PHASE_PSR_RAMP_START_E, CFG.PHASE_PSR_RAMP_END_E,
        CFG.W_PHASE_PSR_START, CFG.W_PHASE_PSR_END
    )
    w_contrast = _linear_schedule(
        epoch1, CFG.CONTRAST_RAMP_START_E, CFG.CONTRAST_RAMP_END_E,
        CFG.W_CONTRAST_START, CFG.W_CONTRAST_END
    )
    w_lap = _linear_schedule(epoch1, CFG.LAP_RAMP_START_E, CFG.LAP_RAMP_END_E, CFG.W_LAP_START, CFG.W_LAP_END) if CFG.LAP_ENABLE else 0.0
    w_sat = _linear_schedule(epoch1, CFG.SAT_RAMP_START_E, CFG.SAT_RAMP_END_E, CFG.W_SAT_START, CFG.W_SAT_END)
    w_cb = _linear_schedule(epoch1, CFG.CB_RAMP_START_E, CFG.CB_RAMP_END_E, CFG.W_CB_START, CFG.W_CB_END)
    w_rec = float(CFG.W_REC)
    if not CFG.ENABLE_SHIFT_EQ:
        w_eq = 0.0
        w_phase_ce = 0.0
        w_phase_psr = 0.0
    if epoch1 <= int(CFG.STAGE0_EPOCHS):
        w_edge = 0.0
        w_edge_ori = 0.0
        w_edge_chamfer = 0.0
    return (
        w_rec, w_eq, w_edge, w_edge_profile, w_edge_ori, w_edge_chamfer,
        w_ssim, w_fft, w_fft_shape, w_phase_ce, w_phase_psr, w_contrast, w_lap, w_sat, w_cb
    )


def reconstruction_terms(pred01: torch.Tensor, lbl01: torch.Tensor,
                         huber: nn.Module,
                         ssim: StructuralSimilarityIndexMeasure):
    l_pix = huber(pred01, lbl01)
    ssim_v = ssim(pred01, lbl01)
    l_ssim = 1.0 - ssim_v
    return l_pix, ssim_v, l_ssim


def reconstruction_loss(pred01: torch.Tensor, lbl01: torch.Tensor,
                        huber: nn.Module,
                        ssim: StructuralSimilarityIndexMeasure,
                        w_ssim: float) -> torch.Tensor:
    l_pix = huber(pred01, lbl01)
    l_ssim = 1.0 - ssim(pred01, lbl01)
    return l_pix + float(w_ssim) * l_ssim


def freeze_physics_layer(model: nn.Module, freeze: bool):
    for n, p in model.named_parameters():
        if "physics_layer" in n:
            p.requires_grad = not freeze


def freeze_weak_psf_block(model: nn.Module, freeze: bool):
    for n, p in model.named_parameters():
        if "weak_psf" in n:
            p.requires_grad = not freeze


def freeze_weak_psf_beta(model: nn.Module, freeze: bool):
    for n, p in model.named_parameters():
        if "weak_psf_block.beta" in n:
            p.requires_grad = not freeze


def get_weak_psf_block(model: nn.Module):
    return getattr(model, "weak_psf_block", None)


def get_weak_psf_stats(model: nn.Module):
    block = get_weak_psf_block(model)
    if block is None:
        return {
            "enabled": False,
            "beta": float("nan"),
            "beta_scale": 0.0,
            "beta_eff": 0.0,
            "entropy": float("nan"),
            "top1_ratio": float("nan"),
            "logits_mean": float("nan"),
            "weights_mean": float("nan"),
            "bypass": True,
        }
    beta_scale = float(getattr(block, "beta_scale", torch.tensor(0.0)).detach().item())
    beta_param = float(getattr(block, "beta", torch.tensor(0.0)).detach().item())
    beta_min = float(getattr(block, "beta_min", 0.0))
    beta_max = float(getattr(block, "beta_max", beta_param))
    beta_scale_max = float(getattr(block, "beta_scale_max", torch.tensor(beta_scale)).detach().item())
    beta_scale = max(0.0, min(beta_scale, beta_scale_max))
    beta_param = max(beta_min, min(beta_param, beta_max))
    beta_eff = beta_param * beta_scale
    beta_val = float(getattr(block, "last_beta", beta_eff))
    if not np.isfinite(beta_val):
        beta_val = beta_eff
    entropy = float(getattr(block, "last_entropy", 0.0))
    if not np.isfinite(entropy):
        entropy = 0.0
    top1 = float(getattr(block, "last_top1_ratio", 0.0))
    if not np.isfinite(top1):
        top1 = 0.0
    logits_mean = float(getattr(block, "last_logits_mean", 0.0))
    if not np.isfinite(logits_mean):
        logits_mean = 0.0
    weights_mean = float(getattr(block, "last_weight_mean", 0.0))
    if not np.isfinite(weights_mean):
        weights_mean = 0.0
    bypass = bool(getattr(block, "last_bypass", beta_scale == 0.0))
    return {
        "enabled": True,
        "beta": beta_val,
        "beta_scale": beta_scale,
        "beta_eff": beta_eff,
        "entropy": entropy,
        "top1_ratio": top1,
        "logits_mean": logits_mean,
        "weights_mean": weights_mean,
        "bypass": bypass,
    }


def get_physics_stats(model: nn.Module):
    layer = getattr(model, "physics_layer", None)
    if layer is None:
        return {"enabled": False, "alpha": 0.0, "reg": 0.0}
    alpha = float(getattr(layer, "alpha", torch.tensor(0.0)).detach().item())
    reg = float(getattr(layer, "reg", torch.tensor(0.0)).detach().item())
    if not np.isfinite(alpha):
        alpha = 0.0
    if not np.isfinite(reg):
        reg = 0.0
    return {"enabled": True, "alpha": alpha, "reg": reg}


def _ema_update(curr: float, target: float, ema: float) -> float:
    ema = float(ema)
    if ema <= 0.0:
        return float(target)
    if ema >= 1.0:
        return float(curr)
    return ema * float(curr) + (1.0 - ema) * float(target)


def init_ema_model(model: nn.Module) -> nn.Module:
    ema = copy.deepcopy(model).eval()
    for p in ema.parameters():
        p.requires_grad_(False)
    return ema


@torch.no_grad()
def update_ema_model(ema_model: Optional[nn.Module], model: nn.Module, decay: float):
    if ema_model is None:
        return
    d = float(decay)
    if d <= 0.0:
        for ema_p, p in zip(ema_model.parameters(), model.parameters()):
            ema_p.data.copy_(p.data)
    else:
        for ema_p, p in zip(ema_model.parameters(), model.parameters()):
            ema_p.data.mul_(d).add_(p.data, alpha=1.0 - d)
    for ema_b, b in zip(ema_model.buffers(), model.buffers()):
        ema_b.data.copy_(b.data)


def apply_weak_psf_schedule(
    model: nn.Module,
    epoch1: int,
    gate_scale: float = 1.0,
    gate_freeze: bool = False,
    guard_active: bool = False,
    guard_lr_mult: float = 0.0,
    force_freeze: bool = False,
):
    block = get_weak_psf_block(model)
    if (block is None) or (not CFG.WEAK_PSF_ENABLE):
        if epoch1 <= CFG.FREEZE_PHYSICS_EPOCH:
            freeze_physics_layer(model, freeze=True)
        else:
            freeze_physics_layer(model, freeze=False)
        return {
            "stage": "none",
            "beta_scale": 0.0,
            "entropy_mix": 0.0,
            "physics_frozen": (epoch1 <= CFG.FREEZE_PHYSICS_EPOCH),
            "weak_frozen": True,
            "gate_scale": float(gate_scale),
            "gate_freeze": bool(gate_freeze),
            "psf_guard_active": False,
            "lr_mult": 0.0,
        }

    active_start = int(getattr(CFG, "WEAK_PSF_ACTIVE_START_E", 10))
    active_end = int(getattr(CFG, "WEAK_PSF_ACTIVE_END_E", 40))
    in_active_window = (epoch1 >= active_start) and (epoch1 <= active_end)

    if force_freeze:
        freeze_physics_layer(model, freeze=True)
        freeze_weak_psf_block(model, freeze=True)
        freeze_weak_psf_beta(model, freeze=True)
        block.set_beta_scale(0.0)
        block.set_entropy_mix(0.0)
        stage = "force_freeze"
        return {
            "stage": stage,
            "beta_scale": 0.0,
            "entropy_mix": 0.0,
            "physics_frozen": True,
            "weak_frozen": True,
            "gate_scale": float(gate_scale),
            "gate_freeze": True,
            "psf_guard_active": False,
            "lr_mult": 0.0,
        }

    if bool(getattr(CFG, "ENABLE_PSF_GUARD_ONLY", False)):
        active = bool(in_active_window)
        if active:
            freeze_physics_layer(model, freeze=False)
            freeze_weak_psf_block(model, freeze=False)
            freeze_weak_psf_beta(model, freeze=False)
            beta_scale = _linear_schedule(
                epoch1, active_start, active_end,
                0.0, float(getattr(CFG, "WEAK_PSF_BETA_SCALE_MAX", 0.35))
            )
            beta_scale = min(beta_scale, float(CFG.WEAK_PSF_BETA_SCALE_MAX))
            if gate_freeze:
                beta_scale = 0.0
            else:
                beta_scale *= float(gate_scale)
            curr_scale = float(getattr(block, "beta_scale", torch.tensor(0.0)).detach().item())
            beta_scale = _ema_update(curr_scale, beta_scale, CFG.WEAK_PSF_BETA_EMA)
            block.set_beta_scale(beta_scale)
            block.set_entropy_mix(0.0)
            block.set_gating_temp(CFG.WEAK_PSF_PSF_TEMP)
            block.set_lowfreq_ratio(CFG.WEAK_PSF_LOWFREQ_RATIO)
            stage = "guard_on"
            weak_frozen = False
            physics_frozen = False
            lr_mult = float(guard_lr_mult) if guard_lr_mult > 0.0 else float(getattr(CFG, "WEAK_PSF_LR_MULT", 0.0))
        else:
            freeze_physics_layer(model, freeze=True)
            freeze_weak_psf_block(model, freeze=True)
            freeze_weak_psf_beta(model, freeze=True)
            block.set_beta_scale(0.0)
            block.set_entropy_mix(0.0)
            stage = "guard_off"
            weak_frozen = True
            physics_frozen = True
            lr_mult = 0.0
        return {
            "stage": stage,
            "beta_scale": float(getattr(block, "beta_scale", torch.tensor(0.0)).detach().item()),
            "entropy_mix": 0.0,
            "physics_frozen": physics_frozen,
            "weak_frozen": weak_frozen,
            "gate_scale": float(gate_scale),
            "gate_freeze": bool(gate_freeze),
            "psf_guard_active": active,
            "lr_mult": lr_mult,
        }

    if not in_active_window:
        freeze_physics_layer(model, freeze=True)
        freeze_weak_psf_block(model, freeze=True)
        freeze_weak_psf_beta(model, freeze=True)
        block.set_beta_scale(0.0)
        block.set_entropy_mix(0.0)
        stage = "window_off"
        return {
            "stage": stage,
            "beta_scale": 0.0,
            "entropy_mix": 0.0,
            "physics_frozen": True,
            "weak_frozen": True,
            "gate_scale": float(gate_scale),
            "gate_freeze": bool(gate_freeze),
            "psf_guard_active": False,
            "lr_mult": 0.0,
        }

    stage0 = max(int(CFG.FREEZE_PHYSICS_EPOCH), int(CFG.WEAK_PSF_STAGE0_EPOCHS))
    stage1 = max(stage0 + 1, int(CFG.WEAK_PSF_STAGE1_EPOCHS))
    stage2 = max(stage1 + 1, int(CFG.WEAK_PSF_STAGE2_EPOCHS))
    stage3 = max(stage2 + 1, int(getattr(CFG, "WEAK_PSF_STAGE3_EPOCHS", stage2 + 1)))

    if epoch1 <= stage0:
        freeze_physics_layer(model, freeze=True)
        freeze_weak_psf_block(model, freeze=True)
        freeze_weak_psf_beta(model, freeze=True)
        beta_scale = 0.0
        entropy_mix = 0.0
        stage = "stage0_freeze"
        weak_frozen = True
        lr_mult = 0.0
    elif epoch1 <= stage1:
        freeze_physics_layer(model, freeze=False)
        freeze_weak_psf_block(model, freeze=False)
        freeze_weak_psf_beta(model, freeze=False)
        beta_scale = float(getattr(CFG, "WEAK_PSF_BETA_SCALE_STAGE1", 0.12))
        entropy_mix = float(getattr(CFG, "WEAK_PSF_ENTROPY_MIX_STAGE2", 0.0))
        stage = "stage1_low"
        weak_frozen = False
        lr_mult = float(getattr(CFG, "WEAK_PSF_LR_MULT_STAGE1", CFG.WEAK_PSF_LR_MULT))
    elif epoch1 <= stage2:
        freeze_physics_layer(model, freeze=False)
        freeze_weak_psf_block(model, freeze=False)
        freeze_weak_psf_beta(model, freeze=False)
        beta_scale = _linear_schedule(
            epoch1,
            int(getattr(CFG, "WEAK_PSF_BETA_RAMP_START_E", stage1 + 1)),
            int(getattr(CFG, "WEAK_PSF_BETA_RAMP_END_E", stage2)),
            float(getattr(CFG, "WEAK_PSF_BETA_SCALE_STAGE1", 0.12)),
            float(getattr(CFG, "WEAK_PSF_BETA_SCALE_STAGE2", 0.28)),
        )
        entropy_mix = float(getattr(CFG, "WEAK_PSF_ENTROPY_MIX_STAGE2", 0.0))
        stage = "stage2_ramp"
        weak_frozen = False
        lr_mult = float(getattr(CFG, "WEAK_PSF_LR_MULT_STAGE2", CFG.WEAK_PSF_LR_MULT))
    else:
        freeze_physics_layer(model, freeze=False)
        freeze_weak_psf_block(model, freeze=False)
        freeze_weak_psf_beta(model, freeze=False)
        beta_scale = float(getattr(CFG, "WEAK_PSF_BETA_SCALE_STAGE3", getattr(CFG, "WEAK_PSF_BETA_SCALE_STAGE2", 0.28)))
        entropy_mix = float(getattr(CFG, "WEAK_PSF_ENTROPY_MIX_STAGE3", 0.0))
        stage = "stage3_hold"
        weak_frozen = False
        lr_mult = float(getattr(CFG, "WEAK_PSF_LR_MULT_STAGE3", CFG.WEAK_PSF_LR_MULT))

    beta_scale = min(beta_scale, float(CFG.WEAK_PSF_BETA_SCALE_MAX))
    if gate_freeze:
        beta_scale = 0.0
    else:
        beta_scale *= float(gate_scale)
    curr_scale = float(getattr(block, "beta_scale", torch.tensor(0.0)).detach().item())
    beta_scale = _ema_update(curr_scale, beta_scale, CFG.WEAK_PSF_BETA_EMA)
    block.set_beta_scale(beta_scale)
    block.set_entropy_mix(entropy_mix)
    block.set_gating_temp(CFG.WEAK_PSF_PSF_TEMP)
    block.set_lowfreq_ratio(CFG.WEAK_PSF_LOWFREQ_RATIO)

    if guard_active and (guard_lr_mult > 0.0):
        lr_mult = min(float(lr_mult), float(guard_lr_mult))

    return {
        "stage": stage,
        "beta_scale": beta_scale,
        "entropy_mix": entropy_mix,
        "physics_frozen": bool(epoch1 <= stage0),
        "weak_frozen": weak_frozen,
        "gate_scale": float(gate_scale),
        "gate_freeze": bool(gate_freeze),
        "psf_guard_active": bool(guard_active),
        "lr_mult": float(lr_mult),
    }

def _sample_shift_vec(n: int, rng: Tuple[float, float], device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
    if n <= 0:
        z = torch.empty(0, device=device, dtype=torch.float32)
        return z, z
    lo = float(min(rng))
    hi = float(max(rng))
    lo = max(0.0, lo)
    hi = max(lo, hi)
    mag = lo + (hi - lo) * torch.rand(n, device=device, dtype=torch.float32)
    ang = 2.0 * math.pi * torch.rand(n, device=device, dtype=torch.float32)
    return mag * torch.cos(ang), mag * torch.sin(ang)


def _sample_int_shift_vec(
    n: int,
    rng: Tuple[float, float],
    device: torch.device,
    exclude_zero: bool = True,
) -> Tuple[torch.Tensor, torch.Tensor]:
    if n <= 0:
        z = torch.empty(0, device=device, dtype=torch.float32)
        return z, z

    lo_f = float(min(rng))
    hi_f = float(max(rng))
    lo_i = int(math.ceil(lo_f))
    hi_i = int(math.floor(hi_f))
    if hi_i < lo_i:
        v = int(round((lo_f + hi_f) * 0.5))
        lo_i = v
        hi_i = v

    mag = torch.randint(low=lo_i, high=hi_i + 1, size=(n,), device=device).float()
    if exclude_zero:
        mag = torch.where(mag == 0.0, mag.new_tensor(1.0), mag)

    sx = torch.where(
        torch.rand(n, device=device) < 0.5,
        mag.new_full((n,), -1.0),
        mag.new_full((n,), 1.0),
    )
    sy = torch.where(
        torch.rand(n, device=device) < 0.5,
        mag.new_full((n,), -1.0),
        mag.new_full((n,), 1.0),
    )
    return mag * sx, mag * sy


def sample_shifts(bs: int, device: str, mode: str = "train", override: Optional[dict] = None):
    dev = torch.device(device)
    u = torch.rand(bs, device=dev)

    dx = torch.empty(bs, device=dev, dtype=torch.float32)
    dy = torch.empty(bs, device=dev, dtype=torch.float32)

    mode = str(mode).lower()
    if mode == "eq":
        if isinstance(override, dict):
            p_tiny = float(override.get("p_tiny", CFG.EQ_SHIFT_MIX_TINY_P))
            p_mid = float(override.get("p_mid", CFG.EQ_SHIFT_MIX_MID_P))
            p_int = float(override.get("p_int", CFG.EQ_SHIFT_MIX_INT_P))
            tiny_rng = override.get("tiny_rng", CFG.EQ_SHIFT_TINY_RANGE)
            mid_rng = override.get("mid_rng", CFG.EQ_SHIFT_MID_RANGE)
            max_int = max(0, int(override.get("max_int", CFG.EQ_MAX_INT_SHIFT)))
            int_rng = (1.0, float(max_int)) if max_int > 0 else (0.0, 0.0)
            int_exclude_zero = bool(override.get("int_exclude_zero", CFG.EQ_SHIFT_INT_EXCLUDE_ZERO))
        else:
            p_tiny = float(CFG.EQ_SHIFT_MIX_TINY_P)
            p_mid = float(CFG.EQ_SHIFT_MIX_MID_P)
            p_int = float(CFG.EQ_SHIFT_MIX_INT_P)
            tiny_rng = CFG.EQ_SHIFT_TINY_RANGE
            mid_rng = CFG.EQ_SHIFT_MID_RANGE
            max_int = max(0, int(CFG.EQ_MAX_INT_SHIFT))
            int_rng = (1.0, float(max_int)) if max_int > 0 else (0.0, 0.0)
            int_exclude_zero = bool(CFG.EQ_SHIFT_INT_EXCLUDE_ZERO)
    else:
        p_tiny = float(CFG.SHIFT_MIX_TINY_P)
        p_mid = float(CFG.SHIFT_MIX_MID_P)
        p_int = float(CFG.SHIFT_MIX_INT_P)
        tiny_rng = CFG.SHIFT_TINY_RANGE
        mid_rng = CFG.SHIFT_MID_RANGE
        int_rng = CFG.SHIFT_INT_RANGE
        int_exclude_zero = bool(CFG.INT_SHIFT_EXCLUDE_ZERO)
    p_sum = max(p_tiny + p_mid + p_int, 1e-6)
    t1 = p_tiny / p_sum
    t2 = (p_tiny + p_mid) / p_sum

    tiny_mask = (u < t1)
    mid_mask = (u >= t1) & (u < t2)
    int_mask = (u >= t2)

    if tiny_mask.any():
        tx, ty = _sample_shift_vec(int(tiny_mask.sum().item()), tiny_rng, dev)
        dx[tiny_mask] = tx
        dy[tiny_mask] = ty

    if mid_mask.any():
        mx, my = _sample_shift_vec(int(mid_mask.sum().item()), mid_rng, dev)
        dx[mid_mask] = mx
        dy[mid_mask] = my

    if int_mask.any():
        if float(max(int_rng)) > 0.0:
            ix, iy = _sample_int_shift_vec(
                int(int_mask.sum().item()),
                int_rng,
                dev,
                exclude_zero=bool(int_exclude_zero),
            )
        else:
            ix = torch.zeros(int(int_mask.sum().item()), device=dev, dtype=torch.float32)
            iy = torch.zeros(int(int_mask.sum().item()), device=dev, dtype=torch.float32)
        dx[int_mask] = ix
        dy[int_mask] = iy

    return dx, dy


def set_psf_group_lr(optimizer: optim.Optimizer, lr_mult: float):
    if optimizer is None:
        return
    mult = max(0.0, float(lr_mult))
    target_lr = float(CFG.LR) * mult
    if len(optimizer.param_groups) >= 3:
        optimizer.param_groups[1]["lr"] = target_lr
        optimizer.param_groups[2]["lr"] = target_lr


def apply_lr_multipliers(optimizer: optim.Optimizer, global_mult: float, psf_mult: Optional[float] = None):
    if optimizer is None:
        return
    gmult = max(0.0, float(global_mult))
    for g in optimizer.param_groups:
        base = g.get("initial_lr", g["lr"])
        g["lr"] = float(base) * gmult
    if (psf_mult is not None) and len(optimizer.param_groups) >= 3:
        pmult = max(0.0, float(psf_mult))
        target_lr = float(CFG.LR) * gmult * pmult
        for idx in (1, 2):
            optimizer.param_groups[idx]["lr"] = target_lr


# ============================================================
# Phase correlation + losses
# ============================================================
def prepare_phase_input(x01: torch.Tensor, mask: torch.Tensor):
    x = x01
    if CFG.PHASE_USE_EDGE:
        x = sobel_magnitude(x01)
    if CFG.PHASE_USE_MASK_HANN:
        x = apply_hann_and_mask(x, mask, remove_mean=CFG.PHASE_REMOVE_MEAN, normalize_std=False)
    else:
        if mask is not None:
            if mask.ndim == 3:
                mask = mask.unsqueeze(1)
            x = x * mask
    return x


def prepare_phase_input_matlab(x01: torch.Tensor, mask: torch.Tensor):
    if mask is not None and mask.ndim == 3:
        mask = mask.unsqueeze(1)
    return apply_hann_and_mask(x01, mask, remove_mean=True, normalize_std=False)


def erode_mask(mask: torch.Tensor, radius: int) -> torch.Tensor:
    if mask is None:
        return None
    if mask.ndim == 3:
        mask = mask.unsqueeze(1)
    if radius <= 0:
        return mask
    k = int(radius) * 2 + 1
    return -F.max_pool2d(-mask, kernel_size=k, stride=1, padding=radius)


def _sobel_xy(x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    kx = x.new_tensor([[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]]).view(1, 1, 3, 3)
    ky = x.new_tensor([[-1.0, -2.0, -1.0], [0.0, 0.0, 0.0], [1.0, 2.0, 1.0]]).view(1, 1, 3, 3)
    gx = F.conv2d(x, kx, padding=1)
    gy = F.conv2d(x, ky, padding=1)
    return gx, gy


def _masked_mean(x: torch.Tensor, mask: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    if mask is None:
        return x.mean()
    m = mask
    if m.ndim == 3:
        m = m.unsqueeze(1)
    if m.shape[1] == 1 and x.shape[1] != 1:
        m = m.expand(-1, x.shape[1], -1, -1)
    denom = m.sum().clamp_min(float(eps))
    return (x * m).sum() / denom


def _masked_l1(a: torch.Tensor, b: torch.Tensor, mask: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    return _masked_mean(torch.abs(a - b), mask, eps=eps)


def _laplacian(x: torch.Tensor) -> torch.Tensor:
    k = x.new_tensor([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]]).view(1, 1, 3, 3)
    return F.conv2d(x, k, padding=1)


def _edge_mask_from_gt(gt01: torch.Tensor, thr: float, dilate: int) -> torch.Tensor:
    gx, gy = _sobel_xy(gt01)
    mag = torch.sqrt(gx * gx + gy * gy + 1e-12)
    edge = (mag >= float(thr)).to(dtype=gt01.dtype)
    d = max(0, int(dilate))
    if d > 0:
        k = 2 * d + 1
        edge = F.max_pool2d(edge, kernel_size=k, stride=1, padding=d)
    return (edge > 0.5).to(dtype=gt01.dtype)


def masked_mean_std(x: torch.Tensor, mask: torch.Tensor, eps: float = 1e-6) -> Tuple[torch.Tensor, torch.Tensor]:
    if mask is None:
        mu = x.mean()
        std = x.std(unbiased=False)
        return mu, std
    m = mask
    if m.ndim == 3:
        m = m.unsqueeze(1)
    if m.shape[1] == 1 and x.shape[1] != 1:
        m = m.expand(-1, x.shape[1], -1, -1)
    den = m.sum().clamp_min(float(eps))
    mu = (x * m).sum() / den
    var = ((x - mu) ** 2 * m).sum() / den
    std = torch.sqrt(var + float(eps))
    return mu, std


_BAND_MASK_CACHE = {}


def _band_mask(H: int, W: int, device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    key = (H, W, device, dtype, float(CFG.BAND_R_LOW), float(CFG.BAND_R_HIGH))
    if key in _BAND_MASK_CACHE:
        return _BAND_MASK_CACHE[key]
    fy = torch.fft.fftfreq(H, device=device, dtype=dtype)
    fx = torch.fft.fftfreq(W, device=device, dtype=dtype)
    Y, X = torch.meshgrid(fy, fx, indexing="ij")
    r = torch.sqrt(X * X + Y * Y)
    r_max = torch.sqrt((fx.abs().max() ** 2) + (fy.abs().max() ** 2)) + 1e-12
    rn = r / r_max
    m = ((rn >= float(CFG.BAND_R_LOW)) & (rn <= float(CFG.BAND_R_HIGH))).to(dtype)
    _BAND_MASK_CACHE[key] = m
    return m


def band_energy_proxy(x01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    x = apply_hann_and_mask(x01, mask, remove_mean=True, normalize_std=False)
    Fx = torch.fft.fft2(x.squeeze(1), dim=(-2, -1))
    power = Fx.real * Fx.real + Fx.imag * Fx.imag
    H, W = power.shape[-2], power.shape[-1]
    bm = _band_mask(H, W, power.device, power.dtype)[None, ...]
    num = torch.sum(power * bm, dim=(-2, -1))
    den = bm.sum().clamp_min(1.0)
    return torch.mean(num / den)


def laplacian_hf_loss(pred01: torch.Tensor, tgt01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    hp_pred = _laplacian(pred01)
    hp_tgt = _laplacian(tgt01)
    return _masked_mean(torch.abs(hp_pred - hp_tgt), mask)


def _psf_forward_available(model: nn.Module) -> Tuple[bool, str]:
    layer = getattr(model, "physics_layer", None)
    if layer is None:
        return False, "physics_layer missing"
    psf = getattr(layer, "PSF_center", None)
    if psf is None:
        return False, "PSF_center missing"
    if not torch.is_tensor(psf):
        return False, "PSF_center invalid"
    if psf.ndim != 4:
        return False, f"PSF_center shape invalid: {tuple(psf.shape)}"
    if int(psf.shape[2]) < 1 or int(psf.shape[3]) < 1:
        return False, "PSF kernel empty"
    return True, "ok"


def _apply_psf_forward_blur(model: nn.Module, x01: torch.Tensor) -> Optional[torch.Tensor]:
    ok, _ = _psf_forward_available(model)
    if not ok:
        return None
    layer = getattr(model, "physics_layer")
    k = layer.PSF_center.to(device=x01.device, dtype=x01.dtype)
    ksum = k.sum(dim=(2, 3), keepdim=True).clamp_min(1e-12)
    k = k / ksum
    c = x01.shape[1]
    if k.shape[1] != c:
        k = k.repeat(1, c, 1, 1)
        k = k.view(c, 1, k.shape[2], k.shape[3])
    else:
        k = k.view(c, 1, k.shape[2], k.shape[3])
    kh, kw = int(k.shape[-2]), int(k.shape[-1])
    pad_l = kw // 2
    pad_r = kw - 1 - pad_l
    pad_t = kh // 2
    pad_b = kh - 1 - pad_t
    x_pad = F.pad(x01, (pad_l, pad_r, pad_t, pad_b), mode="reflect")
    return F.conv2d(x_pad, k, stride=1, padding=0, groups=c)


def get_phys_weight(epoch1: int) -> float:
    if not bool(CFG.PHYS_FORWARD_ENABLE):
        return 0.0
    warmup_end = int(CFG.PHYS_WARMUP_END)
    ramp_end = max(warmup_end + 1, int(CFG.PHYS_RAMP_END))
    if epoch1 <= warmup_end:
        return 0.0
    if epoch1 >= ramp_end:
        return float(CFG.W_PHYS_MAX)
    t = (epoch1 - warmup_end) / float(ramp_end - warmup_end)
    return float(CFG.W_PHYS_MAX) * max(0.0, min(1.0, t))


def gradient_magnitude_loss(pred01: torch.Tensor, tgt01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    eps = float(max(1e-6, CFG.EDGE_CHARB_EPS))
    g_pred = sobel_magnitude(pred01)
    g_tgt = sobel_magnitude(tgt01)
    diff = torch.sqrt((g_pred - g_tgt) ** 2 + eps * eps)
    return _masked_mean(diff, mask)


def compute_shift_eq_losses(
    model: nn.Module,
    src: torch.Tensor,
    pred01: torch.Tensor,
    eq_factor: float,
    epoch1: int,
    use_amp: bool,
    disable_intensity: bool = False,
    eq_intensity_weight_effective: float = 0.0,
    eq_shift_override: Optional[dict] = None,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, str, float, float, float, float]:
    z = pred01.new_tensor(0.0)
    if (not CFG.ENABLE_SHIFT_EQ) or (eq_factor <= 0.0):
        return z, z, z, z, "na", float("nan"), float("nan"), float("nan"), float("nan")

    bs = src.size(0)
    dx, dy = sample_shifts(bs, str(pred01.device), mode="eq", override=eq_shift_override)
    shift_r = torch.sqrt(dx * dx + dy * dy + 1e-12)
    shift_r_min = float(shift_r.min().item())
    shift_r_max = float(shift_r.max().item())
    shift_range_used = f"{shift_r_min:.3f}-{shift_r_max:.3f}px"
    src_shift = shift_tensor_subpixel(src.float(), dx, dy, padding_mode="zeros")

    with torch.cuda.amp.autocast(enabled=use_amp):
        pred_shift = model(src_shift)
    pred_shift01 = pred_shift.float().clamp(0.0, 1.0)

    pred01_det = pred01.detach()
    try:
        pred_warp, mask_raw = shift_tensor_subpixel(pred01_det, dx, dy, padding_mode="zeros", return_mask=True)
    except TypeError:
        pred_warp = shift_tensor_subpixel(pred01_det, dx, dy, padding_mode="zeros")
        mask_raw = torch.ones_like(pred_warp[:, :1, ...])

    interior_margin = max(
        int(CFG.MASK_ERODE_RADIUS),
        int(max(0, int(CFG.EQ_MAX_INT_SHIFT)) + max(0, int(CFG.EQ_INTERIOR_MARGIN_PAD))),
    )
    mask_valid = erode_mask(mask_raw, radius=interior_margin)
    if mask_valid is None:
        mask_valid = torch.ones_like(pred_warp[:, :1, ...])

    if interior_margin > 0:
        _, _, h, w = mask_valid.shape
        crop_mask = torch.zeros_like(mask_valid)
        if (h > 2 * interior_margin) and (w > 2 * interior_margin):
            crop_mask[..., interior_margin:h - interior_margin, interior_margin:w - interior_margin] = 1.0
        mask_valid = mask_valid * crop_mask

    eps = 1e-6
    gx_s, gy_s = _sobel_xy(pred_shift01)
    gx_b, gy_b = _sobel_xy(pred01_det)
    mag_s = torch.sqrt(gx_s * gx_s + gy_s * gy_s + eps)
    mag_b = torch.sqrt(gx_b * gx_b + gy_b * gy_b + eps)
    mag_b_warp = shift_tensor_subpixel(mag_b, dx, dy, padding_mode="zeros")

    if bool(getattr(CFG, "SIMPLETEST_MODE", False)):
        diff_geom = torch.sqrt((mag_s - mag_b_warp) ** 2 + float(CFG.EDGE_CHARB_EPS) ** 2)
        l_eq_geom_raw = _masked_mean(diff_geom, mask_valid)
        l_eq_geom = pred01.new_tensor(float(eq_factor * CFG.W_EQ_GEOM)) * l_eq_geom_raw
        edge_w_mean = float("nan")
        edge_w_p95 = float("nan")
        return l_eq_geom, z, z, l_eq_geom, shift_range_used, edge_w_mean, edge_w_p95, shift_r_min, shift_r_max

    diff_int = torch.abs(pred_shift01 - pred_warp)
    l_eq_int_raw = _masked_mean(diff_int, mask_valid)
    diff_mag = torch.abs(mag_s - mag_b_warp)
    if bool(CFG.ENABLE_EQ_EDGE_WEIGHT):
        edge_ref_mode = str(getattr(CFG, "EQ_EDGE_REF", "pred01")).lower()
        if edge_ref_mode == "pred_warp":
            mag_ref = sobel_magnitude(pred_warp).detach()
        else:
            mag_ref = sobel_magnitude(pred01_det)
        thr_mode = str(getattr(CFG, "EQ_EDGE_THR_MODE", "mean")).lower()
        if thr_mode == "quantile":
            thr_q = float(getattr(CFG, "EQ_EDGE_THR_Q", 0.75))
            thr_q = max(0.0, min(1.0, thr_q))
            thr_l = []
            for i in range(mag_ref.shape[0]):
                m = (mask_valid[i, 0] > 0.5)
                vals = mag_ref[i, 0][m]
                if vals.numel() < 8:
                    vals = mag_ref[i, 0].reshape(-1)
                thr_l.append(float(torch.quantile(vals, thr_q).item()) if vals.numel() > 0 else 0.0)
            thr = torch.tensor(thr_l, device=mag_ref.device, dtype=mag_ref.dtype).view(-1, 1, 1, 1)
        else:
            thr = (mag_ref * mask_valid).sum(dim=(2, 3), keepdim=True) / (mask_valid.sum(dim=(2, 3), keepdim=True) + eps)
        w_edge = torch.sigmoid(float(CFG.EQ_EDGE_BETA) * (mag_ref - thr)).detach()
    else:
        w_edge = torch.ones_like(mask_valid)
    edge_w_mean = float(w_edge.mean().item())
    edge_w_p95 = float(torch.quantile(w_edge.reshape(-1), 0.95).item())
    num_edge = (w_edge * diff_mag * mask_valid).sum()
    den_edge = (w_edge * mask_valid).sum().clamp_min(eps)
    l_eq_edge_raw = num_edge / den_edge
    l_eq_grad_mag = _masked_mean(diff_mag, mask_valid)

    l_eq_grad_dir = z
    mode = str(getattr(CFG, "EQ_GRAD_MODE", "sobel_mag")).lower()
    use_dir = ("dir" in mode) and bool(CFG.ENABLE_EQ_GRAD_DIR)
    if use_dir:
        dir_s = torch.atan2(gy_s, gx_s)
        dir_b = torch.atan2(gy_b, gx_b)
        dir_b_warp = shift_tensor_subpixel(dir_b, dx, dy, padding_mode="zeros")
        l_eq_grad_dir = _masked_mean(1.0 - torch.cos(dir_s - dir_b_warp), mask_valid)

    l_eq_grad_raw = l_eq_grad_mag + 0.25 * l_eq_grad_dir
    w_eq_int = float(CFG.W_EQ) * _linear_schedule(
        epoch1,
        int(CFG.EQ_RAMP_START_E),
        int(CFG.EQ_RAMP_END_E),
        float(CFG.W_EQ_START),
        float(CFG.W_EQ_END),
    ) * float(eq_intensity_weight_effective)
    if disable_intensity:
        w_eq_int = 0.0
    else:
        w_eq_int *= float(getattr(CFG, "EQ_INTENSITY_EXTRA_SCALE", 0.10))
    l_eq_int = pred01.new_tensor(float(eq_factor * w_eq_int)) * l_eq_int_raw
    l_eq_edge = pred01.new_tensor(float(eq_factor * CFG.W_EQ_EDGE)) * l_eq_edge_raw
    l_eq_grad = pred01.new_tensor(float(eq_factor * CFG.W_EQ_GRAD)) * l_eq_grad_raw
    l_eq_total = l_eq_int + l_eq_edge + l_eq_grad
    return l_eq_total, l_eq_int, l_eq_edge, l_eq_grad, shift_range_used, edge_w_mean, edge_w_p95, shift_r_min, shift_r_max


@torch.no_grad()
def run_preflight_sanity_check(device):
    print("[INFO] Running Pre-flight Sanity Check for v5 Geometry...")
    if CFG.PHASE_USE_EDGE or CFG.PHASE_BP_ENABLE:
        raise RuntimeError("[FATAL] Phase config must be raw-only: PHASE_USE_EDGE=False, PHASE_BP_ENABLE=False.")
    dev = torch.device(device)
    src = torch.ones((1, 1, 32, 32), device=dev)
    dx = torch.tensor([4.0], device=dev)
    dy = torch.tensor([4.0], device=dev)

    out_shift = shift_tensor_subpixel(src, dx, dy, padding_mode="zeros")
    top_left_sum = out_shift[..., :4, :4].sum().item()
    if top_left_sum > 1e-4:
        raise RuntimeError(
            f"[FATAL] Zero padding check failed! Top-left sum={top_left_sum:.6f} (expected 0)."
        )

    _, mask_raw = shift_tensor_subpixel(src, dx, dy, padding_mode="zeros", return_mask=True)
    mask_eroded = erode_mask(mask_raw, radius=CFG.MASK_ERODE_RADIUS)

    invalid_max = mask_raw[..., :4, :4].max().item()
    if invalid_max > 1e-4:
        raise RuntimeError(
            f"[FATAL] Mask invalid-region check failed! Max={invalid_max:.6f} (expected 0)."
        )

    raw_area = mask_raw.sum().item()
    expected_area = float((32 - int(abs(float(dx.item())))) * (32 - int(abs(float(dy.item())))))
    if abs(raw_area - expected_area) > 1e-3:
        raise RuntimeError(
            f"[FATAL] Mask area check failed! raw_area={raw_area:.3f}, expected={expected_area:.1f}."
        )

    eroded_area = mask_eroded.sum().item()
    print(f"[CHECK] Mask Raw Area: {raw_area:.1f}, Eroded Area: {eroded_area:.1f}")
    if eroded_area >= raw_area:
        raise RuntimeError("[FATAL] Mask erosion check failed! Eroded area not smaller than raw mask.")

    bin_res = (mask_raw * (1.0 - mask_raw)).max().item()
    if bin_res > 1e-4:
        raise RuntimeError(
            f"[FATAL] Mask binarization check failed! max(m*(1-m))={bin_res:.6f} (expected 0)."
        )

    valid_mean = float((out_shift * mask_raw).sum().item() / (raw_area + 1e-6))
    if abs(valid_mean - 1.0) > 1e-4:
        raise RuntimeError(
            f"[FATAL] Shift/mask alignment check failed! valid_mean={valid_mean:.6f} (expected 1)."
        )

    matlab_ref = apply_hann_and_mask(src, mask_raw, remove_mean=True, normalize_std=False)
    matlab_chk = prepare_phase_input_matlab(src, mask_raw)
    max_diff = (matlab_ref - matlab_chk).abs().max().item()
    if max_diff > 1e-6:
        raise RuntimeError(
            f"[FATAL] MATLAB phase input check failed! max_diff={max_diff:.6e} (expected 0)."
        )

    debug_vis = torch.cat([src, out_shift, mask_raw, mask_eroded], dim=3).clamp(0.0, 1.0)
    debug_np = (debug_vis[0, 0].cpu().numpy() * 255.0).astype(np.uint8)
    debug_bgr = cv2.cvtColor(debug_np, cv2.COLOR_GRAY2BGR)

    b = 4
    border = torch.cat([
        out_shift[..., :b, :].reshape(-1),
        out_shift[..., -b:, :].reshape(-1),
        out_shift[..., :, :b].reshape(-1),
        out_shift[..., :, -b:].reshape(-1),
    ], dim=0)
    border_min = float(border.min().item())
    border_max = float(border.max().item())
    mask_ratio = float(mask_eroded.mean().item())
    raw_ratio = float(raw_area / (32 * 32))
    cb_score = float(checkerboard_energy(out_shift, mask_eroded).item())
    hf_score = float(hf_ratio(out_shift, mask_eroded).item())

    texts = [
        f"border min/max: {border_min:.4f}/{border_max:.4f}",
        f"mask_ratio: {mask_ratio:.4f} raw_ratio: {raw_ratio:.4f}",
        f"cb_score: {cb_score:.6f}",
        f"hf_ratio: {hf_score:.6f}",
    ]
    y0 = 15
    for t in texts:
        cv2.putText(debug_bgr, t, (5, y0), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        y0 += 14

    cv2.imwrite(os.path.join(PROGRESS_DIR, "debug_sanity_check_v5.png"), debug_bgr)
    print("[PASS] Pre-flight sanity check passed. Debug image saved.")


def _phase_bandpass_mask(H: int, W: int, device: torch.device, dtype: torch.dtype):
    fy = torch.fft.fftfreq(H, device=device)
    fx = torch.fft.fftfreq(W, device=device)
    Y, X = torch.meshgrid(fy, fx, indexing="ij")
    r = torch.sqrt(Y ** 2 + X ** 2)
    r_max = torch.sqrt((fy.abs().max() ** 2 + fx.abs().max() ** 2)) + 1e-12
    rn = r / r_max

    r_low = float(CFG.PHASE_BP_R_LOW)
    r_high = float(CFG.PHASE_BP_R_HIGH)
    soft = max(float(CFG.PHASE_BP_SOFT), 1e-6)

    low_gate = torch.sigmoid((rn - r_low) / soft)
    high_gate = 1.0 - torch.sigmoid((rn - r_high) / soft)
    return (low_gate * high_gate).to(dtype)


def phase_corr_map(a01: torch.Tensor, b01: torch.Tensor, eps: float = 1e-8):
    A = torch.fft.fft2(a01.squeeze(1), dim=(-2, -1))
    B = torch.fft.fft2(b01.squeeze(1), dim=(-2, -1))
    if CFG.PHASE_BP_ENABLE:
        raise RuntimeError("[FATAL] PHASE_BP_ENABLE must remain False for compute-aligned phase.")
    R = A * torch.conj(B)
    R = R / (torch.abs(R) + eps)
    r = torch.fft.ifft2(R, dim=(-2, -1))
    r_abs = torch.abs(r)
    r_abs = torch.fft.fftshift(r_abs, dim=(-2, -1))
    return r_abs


def _shift_corr_to_center(r_abs: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor):
    if r_abs.ndim == 3:
        r_abs = r_abs.unsqueeze(1)
    dx = dx.detach()
    dy = dy.detach()
    r_shift = shift_tensor_subpixel(r_abs, -dx, -dy, padding_mode="zeros")
    return r_shift.squeeze(1)


def phase_peak_loss_ce(a01: torch.Tensor, b01: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor, temp: float):
    r_abs = phase_corr_map(a01, b01)
    r_abs = _shift_corr_to_center(r_abs, dx, dy)
    N, H, W = r_abs.shape
    ty = H // 2
    tx = W // 2
    target = (ty * W + tx)
    logits = (r_abs / max(float(temp), 1e-6)).reshape(N, -1)
    logp = F.log_softmax(logits, dim=1)
    return (-logp[:, target]).mean()


def _psr_masks(H: int, W: int, peak_radius: int, outer_radius: int, device: torch.device):
    yy = torch.arange(H, device=device).float()
    xx = torch.arange(W, device=device).float()
    Y, X = torch.meshgrid(yy, xx, indexing="ij")
    cy = H // 2
    cx = W // 2
    r = torch.sqrt((Y - cy)**2 + (X - cx)**2)
    peak_mask = (r <= float(peak_radius)).float()
    outer_mask = (r <= float(outer_radius)).float()
    return peak_mask, outer_mask


def phase_psr_loss(a01: torch.Tensor, b01: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor):
    r_abs = phase_corr_map(a01, b01)
    r_abs = _shift_corr_to_center(r_abs, dx, dy)
    N, H, W = r_abs.shape
    device = r_abs.device

    peak_mask, outer_mask = _psr_masks(H, W, CFG.PSR_PEAK_RADIUS, CFG.PSR_OUTER_RADIUS, device=device)
    peak_sum = torch.sum(r_abs * peak_mask[None, ...], dim=(-2, -1))

    outside = r_abs * (outer_mask[None, ...] - peak_mask[None, ...]).clamp_min(0.0)
    side_mean = torch.mean(outside, dim=(-2, -1))
    side_max = torch.amax(outside, dim=(-2, -1))

    eps = 1e-8
    if CFG.PSR_USE_LOG_RATIO:
        l_mean = torch.log1p(side_mean / (peak_sum + eps))
        l_max  = torch.log1p(side_max  / (peak_sum + eps))
    else:
        l_mean = side_mean / (peak_sum + eps)
        l_max  = side_max  / (peak_sum + eps)

    return float(CFG.PSR_LAMBDA_OUTMEAN) * l_mean.mean() + float(CFG.PSR_LAMBDA_OUTMAX) * l_max.mean()


@torch.no_grad()
def phase_psr_raw_mean(a01: torch.Tensor, b01: torch.Tensor, dx: torch.Tensor, dy: torch.Tensor):
    r_abs = phase_corr_map(a01, b01)
    r_abs = _shift_corr_to_center(r_abs, dx, dy)
    N, H, W = r_abs.shape
    device = r_abs.device

    peak_mask, outer_mask = _psr_masks(H, W, CFG.PSR_PEAK_RADIUS, CFG.PSR_OUTER_RADIUS, device=device)
    peak_sum = torch.sum(r_abs * peak_mask[None, ...], dim=(-2, -1))

    outside = r_abs * (outer_mask[None, ...] - peak_mask[None, ...]).clamp_min(0.0)
    side_mean = torch.mean(outside, dim=(-2, -1))

    eps = 1e-8
    psr = peak_sum / (side_mean + eps)
    return psr.mean()

@torch.no_grad()
def estimate_shift_argmax(a01: torch.Tensor, b01: torch.Tensor):
    # Deprecated: integer argmax estimator (kept for reference only).
    r_abs = phase_corr_map(a01, b01)
    N, H, W = r_abs.shape
    flat = r_abs.reshape(N, -1)
    idx = torch.argmax(flat, dim=1)
    y = (idx // W).to(torch.int64)
    x = (idx % W).to(torch.int64)
    dy = (y - (H // 2)).float()
    dx = (x - (W // 2)).float()
    return dx, dy


@torch.no_grad()
def estimate_shift_subpixel(a01: torch.Tensor, b01: torch.Tensor, win: int = 3):
    r_abs = phase_corr_map(a01, b01)
    return estimate_shift_subpixel_from_map(r_abs, win=win)


@torch.no_grad()
def estimate_shift_subpixel_from_map(r_abs: torch.Tensor, win: int = 3):
    N, H, W = r_abs.shape
    win = int(win)
    if win < 3:
        win = 3
    if (win % 2) == 0:
        win += 1
    rad = win // 2

    device = r_abs.device
    pad = rad
    r_pad = F.pad(r_abs.unsqueeze(1), (pad, pad, pad, pad), mode="replicate").squeeze(1)

    flat = r_abs.reshape(N, -1)
    idx = torch.argmax(flat, dim=1)
    y0 = (idx // W).to(torch.int64)
    x0 = (idx % W).to(torch.int64)

    coords = torch.arange(-rad, rad + 1, device=device, dtype=r_abs.dtype)
    grid_y, grid_x = torch.meshgrid(coords, coords, indexing="ij")

    dx_out = torch.zeros((N,), device=device, dtype=r_abs.dtype)
    dy_out = torch.zeros((N,), device=device, dtype=r_abs.dtype)

    use_quad = bool(CFG.SUBPIXEL_USE_QUAD_FIT)
    A_pinv = None
    if use_quad:
        gx = grid_x.reshape(-1)
        gy = grid_y.reshape(-1)
        ones = torch.ones_like(gx)
        A = torch.stack([gx * gx, gy * gy, gx * gy, gx, gy, ones], dim=1)
        A_pinv = torch.linalg.pinv(A)

    det_eps = float(CFG.SUBPIXEL_FIT_DET_EPS)
    cond_max = float(CFG.SUBPIXEL_FIT_COND_MAX)
    max_off = float(rad) + 0.5
    eps = 1e-8

    for n in range(N):
        yy = int(y0[n].item()) + pad
        xx = int(x0[n].item()) + pad
        patch = r_pad[n, yy - rad:yy + rad + 1, xx - rad:xx + rad + 1]
        z = patch - patch.min()
        z_sum = float(z.sum().item())
        off_x = 0.0
        off_y = 0.0

        use_centroid = True
        if use_quad and (z_sum > eps):
            coeff = A_pinv @ z.reshape(-1)
            a, b, c, d, e, _ = [float(v.item()) for v in coeff]
            det = (2.0 * a) * (2.0 * b) - (c * c)
            if abs(det) > det_eps:
                tr = 2.0 * a + 2.0 * b
                disc = tr * tr - 4.0 * det
                if disc < 0.0:
                    disc = 0.0
                lam1 = 0.5 * (tr + math.sqrt(disc))
                lam2 = 0.5 * (tr - math.sqrt(disc))
                if cond_max > 0.0:
                    cond = abs(lam1) / (abs(lam2) + eps)
                    cond_ok = (cond <= cond_max)
                else:
                    cond_ok = True
                x_star = (-2.0 * b * d + c * e) / det
                y_star = (c * d - 2.0 * a * e) / det
                if cond_ok and math.isfinite(x_star) and math.isfinite(y_star):
                    if (abs(x_star) <= max_off) and (abs(y_star) <= max_off):
                        off_x = x_star
                        off_y = y_star
                        use_centroid = False

        if use_centroid:
            if z_sum > eps:
                w = z / z_sum
                off_y = float((w * grid_y).sum().item())
                off_x = float((w * grid_x).sum().item())
            else:
                off_y = 0.0
                off_x = 0.0

        y_peak = float(y0[n].item()) + off_y
        x_peak = float(x0[n].item()) + off_x
        dy_out[n] = y_peak - float(H // 2)
        dx_out[n] = x_peak - float(W // 2)

    return dx_out, dy_out


def mining_weights_from_error(err: torch.Tensor):
    if not CFG.MINING_ENABLE:
        return torch.ones_like(err)
    th = float(CFG.MINING_THRESH_PX)
    alpha = float(CFG.MINING_ALPHA)
    if CFG.MINING_USE_PROPORTIONAL:
        return 1.0 + alpha * F.relu(err - th) / (th + 1e-6)
    return 1.0 + alpha * (err > th).float()


# ============================================================
# Anti-checkerboard loss
# ============================================================
def _box_blur(x: torch.Tensor, k: int = 3) -> torch.Tensor:
    k = int(k)
    if k < 3:
        k = 3
    if (k % 2) == 0:
        k += 1
    return F.avg_pool2d(x, kernel_size=k, stride=1, padding=k // 2)


def _crop_pair(a: torch.Tensor, b: torch.Tensor):
    h = min(a.shape[-2], b.shape[-2])
    w = min(a.shape[-1], b.shape[-1])
    return a[..., :h, :w], b[..., :h, :w]


def checkerboard_energy(x01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    hp = x01 - _box_blur(x01, k=3)
    if mask is not None:
        if mask.ndim == 3:
            mask = mask.unsqueeze(1)
        hp = hp * mask

    hp00 = hp[..., 0::2, 0::2]
    hp11 = hp[..., 1::2, 1::2]
    hp01 = hp[..., 0::2, 1::2]
    hp10 = hp[..., 1::2, 0::2]

    hp00, hp11 = _crop_pair(hp00, hp11)
    hp01, hp10 = _crop_pair(hp01, hp10)

    e1 = torch.abs(hp00 - hp11)
    e2 = torch.abs(hp01 - hp10)

    if mask is None:
        return e1.mean() + e2.mean()

    m00 = mask[..., 0::2, 0::2]
    m11 = mask[..., 1::2, 1::2]
    m01 = mask[..., 0::2, 1::2]
    m10 = mask[..., 1::2, 0::2]

    m00, m11 = _crop_pair(m00, m11)
    m01, m10 = _crop_pair(m01, m10)

    m1 = m00 * m11
    m2 = m01 * m10
    e1_sum = (e1 * m1).sum(dim=(1, 2, 3)) / (m1.sum(dim=(1, 2, 3)) + 1e-6)
    e2_sum = (e2 * m2).sum(dim=(1, 2, 3)) / (m2.sum(dim=(1, 2, 3)) + 1e-6)
    return (e1_sum + e2_sum).mean()


_HF_MASK_CACHE = {}


def _hf_ratio_mask(H: int, W: int, device: torch.device, dtype: torch.dtype):
    key = (H, W, device, dtype)
    if key in _HF_MASK_CACHE:
        return _HF_MASK_CACHE[key]
    yy = torch.arange(H, device=device, dtype=dtype)
    xx = torch.arange(W, device=device, dtype=dtype)
    Y, X = torch.meshgrid(yy, xx, indexing="ij")
    cy = (H - 1) * 0.5
    cx = (W - 1) * 0.5
    r = torch.sqrt((Y - cy) ** 2 + (X - cx) ** 2)
    r_max = math.sqrt(float(cy * cy + cx * cx)) + 1e-12
    rn = r / r_max
    r_low = float(CFG.HF_RATIO_R_LOW)
    r_high = float(CFG.HF_RATIO_R_HIGH)
    m = ((rn >= r_low) & (rn <= r_high)).to(dtype)
    _HF_MASK_CACHE[key] = m
    return m


def hf_ratio(pred01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    if mask is not None and mask.ndim == 3:
        mask = mask.unsqueeze(1)
    x = apply_hann_and_mask(pred01, mask, remove_mean=True, normalize_std=False)
    Fp = torch.fft.fft2(x.squeeze(1), dim=(-2, -1))
    Fp = torch.fft.fftshift(Fp, dim=(-2, -1))
    power = (Fp.real ** 2 + Fp.imag ** 2)
    H, W = power.shape[-2], power.shape[-1]
    m = _hf_ratio_mask(H, W, device=power.device, dtype=power.dtype)[None, ...]
    hf = torch.sum(power * m, dim=(-2, -1))
    tot = torch.sum(power, dim=(-2, -1)) + 1e-12
    return torch.mean(hf / tot)


_GAUSS_CACHE = {}


def _gauss_kernel1d(sigma: float, device: torch.device, dtype: torch.dtype):
    key = (sigma, device, dtype)
    if key in _GAUSS_CACHE:
        return _GAUSS_CACHE[key]
    radius = max(1, int(round(3.0 * float(sigma))))
    xs = torch.arange(-radius, radius + 1, device=device, dtype=dtype)
    k = torch.exp(-(xs ** 2) / (2.0 * sigma * sigma))
    k = k / (k.sum() + 1e-12)
    _GAUSS_CACHE[key] = (k, radius)
    return _GAUSS_CACHE[key]


def gaussian_blur(x: torch.Tensor, sigma: float) -> torch.Tensor:
    if sigma <= 0.0:
        return x
    k1, radius = _gauss_kernel1d(float(sigma), device=x.device, dtype=x.dtype)
    kx = k1.view(1, 1, 1, -1)
    ky = k1.view(1, 1, -1, 1)
    c = x.shape[1]
    x = F.conv2d(x, kx.repeat(c, 1, 1, 1), padding=(0, radius), groups=c)
    x = F.conv2d(x, ky.repeat(c, 1, 1, 1), padding=(radius, 0), groups=c)
    return x


def _detail_edge_mask(ref01: torch.Tensor, mask_valid: torch.Tensor = None) -> Optional[torch.Tensor]:
    mag = sobel_magnitude(ref01).detach()
    if mask_valid is not None:
        if mask_valid.ndim == 3:
            mask_valid = mask_valid.unsqueeze(1)
        mag = mag * mask_valid
    mode = str(getattr(CFG, "DETAIL_EDGE_MASK_MODE", "quantile")).lower()
    thr = float(getattr(CFG, "DETAIL_EDGE_THR", 0.04))
    q = float(getattr(CFG, "DETAIL_EDGE_Q", 0.80))
    if mask_valid is not None:
        vals = mag[mask_valid > 0.5]
    else:
        vals = mag.reshape(-1)
    if vals.numel() == 0:
        return None
    if mode == "quantile":
        q = max(0.0, min(1.0, q))
        thr = float(torch.quantile(vals, q).item())
    mask = (mag >= thr).float()
    if mask_valid is not None:
        mask = mask * mask_valid
    min_frac = float(getattr(CFG, "DETAIL_EDGE_MIN_FRAC", 0.02))
    max_frac = float(getattr(CFG, "DETAIL_EDGE_MAX_FRAC", 0.35))
    frac = float(mask.mean().item())
    if (frac < min_frac) and (vals.numel() > 0):
        k = max(1, int(min_frac * vals.numel()))
        thr = float(torch.topk(vals, k=k, largest=True).values.min().item())
        mask = (mag >= thr).float()
        if mask_valid is not None:
            mask = mask * mask_valid
    elif (frac > max_frac) and (vals.numel() > 0):
        k = max(1, int(max_frac * vals.numel()))
        thr = float(torch.topk(vals, k=k, largest=True).values.min().item())
        mask = (mag >= thr).float()
        if mask_valid is not None:
            mask = mask * mask_valid
    dilate = max(0, int(getattr(CFG, "DETAIL_EDGE_DILATE", 1)))
    if dilate > 0:
        mask = F.max_pool2d(mask, kernel_size=2 * dilate + 1, stride=1, padding=dilate)
    return mask


def detail_recovery_loss(pred01: torch.Tensor, ref01: torch.Tensor, mask_valid: torch.Tensor = None) -> torch.Tensor:
    sigma1 = float(getattr(CFG, "DETAIL_DOG_SIGMA1", 0.8))
    sigma2 = float(getattr(CFG, "DETAIL_DOG_SIGMA2", 1.6))
    bp_pred = gaussian_blur(pred01, sigma=sigma1) - gaussian_blur(pred01, sigma=sigma2)
    bp_ref = (gaussian_blur(ref01, sigma=sigma1) - gaussian_blur(ref01, sigma=sigma2)).detach()
    diff = bp_pred - bp_ref
    eps = float(getattr(CFG, "DETAIL_CHARB_EPS", 1e-3))
    loss_map = torch.sqrt(diff * diff + eps * eps)
    edge_mask = _detail_edge_mask(ref01, mask_valid=mask_valid)
    if edge_mask is not None:
        return _masked_mean(loss_map, edge_mask)
    return _masked_mean(loss_map, mask_valid)


def anti_hf_loss(pred01: torch.Tensor, ref01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    lp_pred = gaussian_blur(pred01, sigma=float(CFG.HF_SIGMA))
    lp_ref = gaussian_blur(ref01, sigma=float(CFG.HF_SIGMA))
    pred_hf = torch.abs(pred01 - lp_pred)
    ref_hf = torch.abs(ref01 - lp_ref).detach()

    bound = ref_hf * (1.0 + float(CFG.HF_CAP_DELTA))
    if float(CFG.HF_CAP_MIN) > 0.0:
        bound = torch.maximum(bound, pred_hf.new_tensor(float(CFG.HF_CAP_MIN)))
    excess = F.relu(pred_hf - bound)

    beta = float(CFG.HF_SMOOTH_BETA)
    if mask is not None:
        if mask.ndim == 3:
            mask = mask.unsqueeze(1)
        loss_map = F.smooth_l1_loss(excess, torch.zeros_like(excess), beta=beta, reduction="none")
        num = torch.sum(loss_map * mask, dim=(1, 2, 3))
        den = torch.sum(mask, dim=(1, 2, 3)) + 1e-6
        return torch.mean(num / den)
    return F.smooth_l1_loss(excess, torch.zeros_like(excess), beta=beta, reduction="mean")


# ============================================================
# Spectral reconstruction loss
# ============================================================
def fft_bandpass_mask(H: int, W: int, device: torch.device):
    yy = torch.arange(H, device=device).float()
    xx = torch.arange(W, device=device).float()
    Y, X = torch.meshgrid(yy, xx, indexing="ij")
    cy = (H // 2)
    cx = (W // 2)
    r = torch.sqrt((Y - cy)**2 + (X - cx)**2)
    r_max = torch.sqrt(torch.tensor((cy**2 + cx**2), device=device).float()) + 1e-6
    rn = r / r_max

    r_low = float(CFG.FFT_R_LOW)
    r_high = float(CFG.FFT_R_HIGH)
    soft = max(float(CFG.FFT_BAND_SOFT), 1e-6)

    low_gate = torch.sigmoid((rn - r_low) / soft)
    high_gate = 1.0 - torch.sigmoid((rn - r_high) / soft)
    m = low_gate * high_gate

    gamma = float(CFG.FFT_BAND_GAMMA)
    if gamma != 1.0:
        m = m.pow(gamma)
    return m


def spectral_recon_loss(pred01: torch.Tensor, lbl01: torch.Tensor):
    eps = float(CFG.FFT_EPS)
    N, _, H, W = pred01.shape
    device = pred01.device

    Fp = torch.fft.fft2(pred01.squeeze(1), dim=(-2, -1))
    Fl = torch.fft.fft2(lbl01.squeeze(1), dim=(-2, -1))

    Fp = torch.fft.fftshift(Fp, dim=(-2, -1))
    Fl = torch.fft.fftshift(Fl, dim=(-2, -1))

    mask = fft_bandpass_mask(H, W, device=device)[None, ...]

    loss = 0.0
    if CFG.FFT_LOGMAG:
        mp = torch.log(torch.abs(Fp) + eps)
        ml = torch.log(torch.abs(Fl) + eps)
        loss = loss + float(CFG.FFT_W_LOGMAG) * torch.mean(torch.abs(mp - ml) * mask)
    else:
        mp = torch.abs(Fp)
        ml = torch.abs(Fl)
        loss = loss + float(CFG.FFT_W_LOGMAG) * torch.mean(torch.abs(mp - ml) * mask)

    if CFG.FFT_PHASE_COS:
        ph_p = torch.angle(Fp)
        ph_l = torch.angle(Fl)
        loss = loss + float(CFG.FFT_W_PHASE) * torch.mean((1.0 - torch.cos(ph_p - ph_l)) * mask)

    return loss


def fft_midband_weight(H: int, W: int, device: torch.device, dtype: torch.dtype):
    yy = torch.linspace(-1.0, 1.0, H, device=device, dtype=dtype)
    xx = torch.linspace(-1.0, 1.0, W, device=device, dtype=dtype)
    Y, X = torch.meshgrid(yy, xx, indexing="ij")
    r = torch.sqrt(X ** 2 + Y ** 2) / math.sqrt(2.0)
    c = float(CFG.FFT_SHAPE_R_CENTER)
    s = max(float(CFG.FFT_SHAPE_R_SIGMA), 1e-6)
    return torch.exp(-((r - c) / s) ** 2)


def spectral_shape_loss(pred01: torch.Tensor, lbl01: torch.Tensor):
    N, _, H, W = pred01.shape
    device = pred01.device
    dtype = pred01.dtype

    Fp = torch.fft.fft2(pred01.squeeze(1), dim=(-2, -1))
    Fl = torch.fft.fft2(lbl01.squeeze(1), dim=(-2, -1))

    Fp = torch.fft.fftshift(Fp, dim=(-2, -1))
    Fl = torch.fft.fftshift(Fl, dim=(-2, -1))

    mp = torch.log1p(torch.abs(Fp))
    ml = torch.log1p(torch.abs(Fl))

    w = fft_midband_weight(H, W, device=device, dtype=dtype)[None, ...]
    raw = torch.mean(torch.abs(mp - ml) * w)
    cap = float(CFG.FFT_SHAPE_CAP)
    if cap > 0.0:
        return F.relu(raw - cap)
    return raw


# ============================================================
# Contrast calibration loss
# ============================================================
def contrast_calibration_loss(pred01: torch.Tensor, lbl01: torch.Tensor):
    B = pred01.shape[0]
    eps = float(CFG.CONTRAST_STD_EPS)
    loss = 0.0

    p = pred01.view(B, -1)
    t = lbl01.view(B, -1)

    if CFG.CONTRAST_USE_MEANSTD:
        pm = p.mean(dim=1)
        tm = t.mean(dim=1)
        ps = p.std(dim=1, unbiased=False)
        ts = t.std(dim=1, unbiased=False)
        loss = loss + (torch.mean(torch.abs(pm - tm)) + torch.mean(torch.abs(ps - ts)))

    if CFG.CONTRAST_USE_PCTL:
        ql = float(CFG.CONTRAST_P_LOW)
        qh = float(CFG.CONTRAST_P_HIGH)
        p_lo = torch.quantile(p, ql, dim=1)
        p_hi = torch.quantile(p, qh, dim=1)
        t_lo = torch.quantile(t, ql, dim=1)
        t_hi = torch.quantile(t, qh, dim=1)
        p_rng = (p_hi - p_lo).clamp_min(eps)
        t_rng = (t_hi - t_lo).clamp_min(eps)
        loss = loss + (torch.mean(torch.abs(p_rng - t_rng)) +
                       torch.mean(torch.abs(p_lo - t_lo)) +
                       torch.mean(torch.abs(p_hi - t_hi)))

    return torch.clamp(loss, 0.0, float(CFG.CONTRAST_CLIP_GRAD))


def saturation_penalty(pred01: torch.Tensor):
    hi = F.relu(pred01 - float(CFG.SAT_HIGH))
    lo = F.relu(float(CFG.SAT_LOW) - pred01)
    return torch.mean(hi) + torch.mean(lo)


# ============================================================
# Masks + edge profile stabilizer
# ============================================================
_EDGE_KERNEL_CACHE = {}
_GRID_CACHE = {}


def _get_edge_kernels(device: torch.device, dtype: torch.dtype):
    key = (bool(CFG.EDGE_USE_SCHARR), device, dtype)
    if key in _EDGE_KERNEL_CACHE:
        return _EDGE_KERNEL_CACHE[key]
    if CFG.EDGE_USE_SCHARR:
        kx = torch.tensor([[-3, 0, 3],
                           [-10, 0, 10],
                           [-3, 0, 3]], device=device, dtype=dtype).view(1, 1, 3, 3)
        ky = torch.tensor([[-3, -10, -3],
                           [ 0,   0,  0],
                           [ 3,  10,  3]], device=device, dtype=dtype).view(1, 1, 3, 3)
    else:
        kx = torch.tensor([[-1, 0, 1],
                           [-2, 0, 2],
                           [-1, 0, 1]], device=device, dtype=dtype).view(1, 1, 3, 3)
        ky = torch.tensor([[-1, -2, -1],
                           [ 0,  0,  0],
                           [ 1,  2,  1]], device=device, dtype=dtype).view(1, 1, 3, 3)
    _EDGE_KERNEL_CACHE[key] = (kx, ky)
    return kx, ky


def _prepare_mask(mask: torch.Tensor, like: torch.Tensor) -> torch.Tensor:
    if mask is None:
        return torch.ones_like(like)
    if mask.ndim == 3:
        return mask.unsqueeze(1)
    return mask


def _edge_mag_norm_torch(mag: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    B, _, H, W = mag.shape
    q = float(CFG.EDGE_MAG_NORM_Q)
    floor = float(CFG.EDGE_MAG_NORM_MIN)
    mag_n = torch.empty_like(mag)
    for i in range(B):
        sel = mag[i, 0][mask[i, 0] > 0.5]
        if sel.numel() < 8:
            scale = max(float(sel.max().item()) if sel.numel() > 0 else 1.0, floor)
        else:
            scale = max(float(torch.quantile(sel, q).item()), floor)
        mag_n[i, 0] = mag[i, 0] / scale
    return mag_n


def _edge_mask_from_mag_torch(mag: torch.Tensor, mask: torch.Tensor, q_init: float = None):
    mask = _prepare_mask(mask, mag)
    B, _, H, W = mag.shape
    mag_n = _edge_mag_norm_torch(mag, mask)
    edge = torch.zeros_like(mag, dtype=torch.float32)
    q_used = []
    k_used = []
    density = []
    thr_used = []
    n_eff = []
    n_min = max(int(CFG.EDGE_N_MIN_FRAC * H * W), int(CFG.EDGE_N_MIN_PIX))
    q0 = float(CFG.EDGE_EXTRACT_Q_INIT) if q_init is None else float(q_init)
    q_step = float(CFG.EDGE_EXTRACT_Q_STEP)
    q_min = float(CFG.EDGE_EXTRACT_Q_MIN)
    q_max = float(CFG.EDGE_EXTRACT_Q_MAX)
    min_d = float(CFG.EDGE_DENSITY_MIN)
    max_d = float(CFG.EDGE_DENSITY_MAX)
    max_steps = max(1, int(CFG.EDGE_EXTRACT_MAX_STEPS))
    target_d = float(CFG.EDGE_TOPK_TARGET_DENSITY)
    if target_d <= 0.0:
        target_d = 0.5 * (min_d + max_d)

    for i in range(B):
        m = mask[i, 0] > 0.5
        n_mask = int(m.sum().item())
        if n_mask <= 0:
            edge[i, 0] = 0.0
            q_used.append(float("nan"))
            k_used.append(0)
            density.append(0.0)
            thr_used.append(float("nan"))
            n_eff.append(0)
            continue
        vals = mag_n[i, 0][m]
        q = q0
        if vals.numel() < 8:
            thr = float(vals.max().item()) if vals.numel() > 0 else float("inf")
        else:
            thr = float(torch.quantile(vals, q).item())
        edge_i = (mag_n[i, 0] > thr) & m
        dens = float(edge_i.sum().item() / max(n_mask, 1))
        for _ in range(max_steps):
            if dens > max_d and q < q_max - 1e-6:
                q = min(q + q_step, q_max)
            elif dens < min_d and q > q_min + 1e-6:
                q = max(q - q_step, q_min)
            else:
                break
            if vals.numel() < 8:
                thr = float(vals.max().item()) if vals.numel() > 0 else float("inf")
            else:
                thr = float(torch.quantile(vals, q).item())
            edge_i = (mag_n[i, 0] > thr) & m
            dens = float(edge_i.sum().item() / max(n_mask, 1))

        k = 0
        if (dens > max_d or dens < min_d) and bool(CFG.EDGE_EXTRACT_USE_TOPK):
            k = int(round(target_d * n_mask))
            k = max(k, n_min)
            k = min(k, n_mask)
            if vals.numel() >= k:
                kth = torch.topk(vals, k, largest=True).values.min().item()
                edge_i = (mag_n[i, 0] >= kth) & m
                dens = float(edge_i.sum().item() / max(n_mask, 1))

        edge[i, 0] = edge_i.float()
        q_used.append(float(q))
        k_used.append(int(k))
        density.append(float(dens))
        thr_used.append(float(thr))
        n_eff.append(int(edge_i.sum().item()))

    info = {
        "q_used": q_used,
        "k_used": k_used,
        "density": density,
        "thr": thr_used,
        "n_eff": n_eff,
        "n_min": n_min,
    }
    return edge, mag_n, info


def _edge_gate_from_target(mag_t: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    edge, _, _ = _edge_mask_from_mag_torch(mag_t, mask)
    return edge


def _base_grid(H: int, W: int, device: torch.device, dtype: torch.dtype):
    key = (H, W, device, dtype)
    if key in _GRID_CACHE:
        return _GRID_CACHE[key]
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, H, device=device, dtype=dtype),
        torch.linspace(-1.0, 1.0, W, device=device, dtype=dtype),
        indexing="ij",
    )
    grid = torch.stack([xx, yy], dim=-1).unsqueeze(0)
    _GRID_CACHE[key] = grid
    return grid


def _sample_along_normal(mag: torch.Tensor, nx: torch.Tensor, ny: torch.Tensor, step: float):
    B, _, H, W = mag.shape
    base = _base_grid(H, W, device=mag.device, dtype=mag.dtype).repeat(B, 1, 1, 1)
    dx = (nx.squeeze(1) * step) * (2.0 / max(1.0, float(W - 1)))
    dy = (ny.squeeze(1) * step) * (2.0 / max(1.0, float(H - 1)))
    grid = base.clone()
    grid[..., 0] = grid[..., 0] + dx
    grid[..., 1] = grid[..., 1] + dy
    return F.grid_sample(mag, grid, mode="bilinear", padding_mode="border", align_corners=True)


def make_valid_mask(x01: torch.Tensor) -> torch.Tensor:
    mask = torch.ones_like(x01)
    mask = erode_mask(mask, radius=CFG.MASK_ERODE_RADIUS)
    if not CFG.ROI_ENABLE:
        return mask
    _, _, H, W = mask.shape
    x0, y0, w, h = [int(v) for v in CFG.ROI_XYWH]
    x1 = min(W, x0 + max(0, w))
    y1 = min(H, y0 + max(0, h))
    roi = torch.zeros_like(mask)
    if (x1 > x0) and (y1 > y0):
        roi[..., y0:y1, x0:x1] = 1.0
    return mask * roi


def edge_profile_width_loss(pred01: torch.Tensor, src01: torch.Tensor, mask: torch.Tensor = None,
                            return_stats: bool = False):
    kx, ky = _get_edge_kernels(device=pred01.device, dtype=pred01.dtype)
    gx_s = F.conv2d(src01, kx, padding=1)
    gy_s = F.conv2d(src01, ky, padding=1)
    gx_p = F.conv2d(pred01, kx, padding=1)
    gy_p = F.conv2d(pred01, ky, padding=1)

    eps = float(CFG.EDGE_DIR_EPS)
    mag_s = torch.sqrt(gx_s * gx_s + gy_s * gy_s + eps * eps)
    mag_p = torch.sqrt(gx_p * gx_p + gy_p * gy_p + eps * eps)

    nx = (gx_s / (mag_s + eps)).detach()
    ny = (gy_s / (mag_s + eps)).detach()

    step = float(CFG.EDGE_PROFILE_STEP)
    mag_p_plus = _sample_along_normal(mag_p, nx, ny, step)
    mag_p_minus = _sample_along_normal(mag_p, nx, ny, -step)
    mag_s_plus = _sample_along_normal(mag_s, nx, ny, step)
    mag_s_minus = _sample_along_normal(mag_s, nx, ny, -step)

    mask_m = _prepare_mask(mask, mag_s)
    edge_s, mag_s_n, info_s = _edge_mask_from_mag_torch(mag_s, mask_m)
    mag_p_n = _edge_mag_norm_torch(mag_p, mask_m)

    B, _, H, W = mag_s.shape
    edge_p = torch.zeros_like(edge_s)
    thr_s = info_s["thr"]
    pred_ratio = float(CFG.EDGE_PROFILE_PRED_GATE_RATIO)
    for i in range(B):
        thr_p = float(thr_s[i]) * pred_ratio
        m = mask_m[i, 0] > 0.5
        edge_p[i, 0] = ((mag_p_n[i, 0] > thr_p) & m).float()

    edge_mask = edge_s * edge_p
    n_min = max(int(CFG.EDGE_PROFILE_MIN_FRAC * H * W), int(CFG.EDGE_PROFILE_MIN_PIX))
    n_eff = edge_mask.sum(dim=(1, 2, 3))

    denom_floor_s = []
    denom_floor_p = []
    denom_q = float(CFG.EDGE_PROFILE_DENOM_Q)
    denom_min = float(CFG.EDGE_PROFILE_DENOM_MIN)
    for i in range(B):
        sel_s = mag_s[i, 0][mask_m[i, 0] > 0.5]
        sel_p = mag_p[i, 0][mask_m[i, 0] > 0.5]
        if sel_s.numel() >= 8:
            denom_floor_s.append(max(float(torch.quantile(sel_s, denom_q).item()), denom_min))
        else:
            denom_floor_s.append(denom_min)
        if sel_p.numel() >= 8:
            denom_floor_p.append(max(float(torch.quantile(sel_p, denom_q).item()), denom_min))
        else:
            denom_floor_p.append(denom_min)
    denom_floor_s_t = torch.tensor(denom_floor_s, device=mag_s.device, dtype=mag_s.dtype).view(B, 1, 1, 1)
    denom_floor_p_t = torch.tensor(denom_floor_p, device=mag_p.device, dtype=mag_p.dtype).view(B, 1, 1, 1)
    denom_s = torch.maximum(mag_s, denom_floor_s_t)
    denom_p = torch.maximum(mag_p, denom_floor_p_t)
    width_p = (mag_p_plus + mag_p_minus) / denom_p
    width_s = (mag_s_plus + mag_s_minus) / denom_s

    width_cap = float(CFG.EDGE_PROFILE_WIDTH_CAP)
    width_p = width_p.clamp(0.0, width_cap)
    width_s = width_s.clamp(0.0, width_cap)

    loss_map = F.smooth_l1_loss(width_p, width_s, beta=float(CFG.EDGE_MAG_BETA), reduction="none")
    stats = None
    if return_stats:
        vals = loss_map[edge_mask > 0.5]
        if vals.numel() > 0:
            stats = {
                "n": int(vals.numel()),
                "p50": float(torch.quantile(vals, 0.50).item()),
                "p90": float(torch.quantile(vals, 0.90).item()),
                "p99": float(torch.quantile(vals, 0.99).item()),
                "max": float(vals.max().item()),
                "skip": False,
                "cap_hit": 0,
            }
        else:
            stats = {"n": 0, "p50": np.nan, "p90": np.nan, "p99": np.nan, "max": np.nan, "skip": True, "cap_hit": 0}
    num = torch.sum(loss_map * edge_mask, dim=(1, 2, 3))
    den = torch.sum(edge_mask, dim=(1, 2, 3)).clamp_min(1.0)
    loss = (num / den)

    mask_sum = mask_m.sum(dim=(1, 2, 3)).clamp_min(1.0)
    edge_ratio = n_eff / mask_sum
    tau_frac = max(float(CFG.EDGE_PROFILE_GATE_TAU_FRAC), 1e-6)
    tau_pix = max(float(CFG.EDGE_PROFILE_GATE_TAU_PIX), 1.0)
    gate_frac = torch.sigmoid((edge_ratio - float(CFG.EDGE_PROFILE_MIN_FRAC)) / tau_frac)
    gate_pix = torch.sigmoid((n_eff - float(CFG.EDGE_PROFILE_MIN_PIX)) / tau_pix)
    gate = gate_frac * gate_pix
    loss = (loss * gate).mean()

    cap = float(CFG.EDGE_PROFILE_CAP)
    if cap > 0.0:
        capped = (loss > cap)
        loss = F.relu(loss - cap)
        if return_stats and stats is not None:
            stats["cap_hit"] = int(capped.item())
    if return_stats and stats is not None:
        stats["edge_ratio"] = float(edge_ratio.mean().item())
        stats["gate_mean"] = float(gate.mean().item())
    return (loss, stats) if return_stats else loss


def edge_orientation_loss(pred01: torch.Tensor, tgt01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    kx, ky = _get_edge_kernels(device=pred01.device, dtype=pred01.dtype)
    gx_p = F.conv2d(pred01, kx, padding=1)
    gy_p = F.conv2d(pred01, ky, padding=1)
    gx_t = F.conv2d(tgt01, kx, padding=1)
    gy_t = F.conv2d(tgt01, ky, padding=1)
    eps = float(CFG.EDGE_DIR_EPS)
    mag_p = torch.sqrt(gx_p * gx_p + gy_p * gy_p + eps * eps)
    mag_t = torch.sqrt(gx_t * gx_t + gy_t * gy_t + eps * eps)
    cos = (gx_p * gx_t + gy_p * gy_t) / (mag_p * mag_t + eps)
    loss_map = 1.0 - cos
    # edge-orientation loss is edge-gated by target mag threshold
    edge_gate, _, info = _edge_mask_from_mag_torch(mag_t, mask)

    if mask is not None:
        if mask.ndim == 3:
            mask = mask.unsqueeze(1)
        mask = mask * edge_gate
    else:
        mask = edge_gate
    den = torch.sum(mask, dim=(1, 2, 3))
    n_eff = torch.tensor(info["n_eff"], device=mask.device, dtype=den.dtype)
    valid = n_eff >= float(info["n_min"])
    if not torch.any(valid):
        return pred01.new_tensor(0.0)
    den = den.clamp_min(1.0)
    num = torch.sum(loss_map * mask, dim=(1, 2, 3))
    loss = (num / den) * valid.float()
    loss = loss.sum() / valid.float().sum().clamp_min(1.0)
    cap = float(CFG.EDGE_ORI_CAP)
    if cap > 0.0:
        loss = F.relu(loss - cap)
    return loss


def _edge_soft_map(x01: torch.Tensor) -> torch.Tensor:
    kx, ky = _get_edge_kernels(device=x01.device, dtype=x01.dtype)
    gx = F.conv2d(x01, kx, padding=1)
    gy = F.conv2d(x01, ky, padding=1)
    mag = torch.sqrt(gx * gx + gy * gy + float(CFG.EDGE_DIR_EPS) ** 2)
    thr = float(CFG.EDGE_SOFT_THR)
    beta = max(float(CFG.EDGE_SOFT_BETA), 1e-6)
    return torch.sigmoid((mag - thr) / beta)


def _soft_distance_transform(edge_map: torch.Tensor) -> torch.Tensor:
    blur = gaussian_blur(edge_map, sigma=float(CFG.EDGE_CHAMFER_SIGMA))
    eps = 1e-6
    return -float(CFG.EDGE_CHAMFER_TAU) * torch.log(blur + eps)


def edge_chamfer_loss(pred01: torch.Tensor, tgt01: torch.Tensor, mask: torch.Tensor = None) -> torch.Tensor:
    kx, ky = _get_edge_kernels(device=pred01.device, dtype=pred01.dtype)
    gx_t = F.conv2d(tgt01, kx, padding=1)
    gy_t = F.conv2d(tgt01, ky, padding=1)
    mag_t = torch.sqrt(gx_t * gx_t + gy_t * gy_t + float(CFG.EDGE_DIR_EPS) ** 2)
    edge_gate, _, info_t = _edge_mask_from_mag_torch(mag_t, mask)

    gx_p = F.conv2d(pred01, kx, padding=1)
    gy_p = F.conv2d(pred01, ky, padding=1)
    mag_p = torch.sqrt(gx_p * gx_p + gy_p * gy_p + float(CFG.EDGE_DIR_EPS) ** 2)
    pred_edge, _, info_p = _edge_mask_from_mag_torch(mag_p, mask)
    tgt_edge = edge_gate
    dt_t = _soft_distance_transform(tgt_edge)
    dt_p = _soft_distance_transform(pred_edge)

    if mask is not None:
        if mask.ndim == 3:
            mask = mask.unsqueeze(1)
        mask = mask * edge_gate
    else:
        mask = edge_gate
    den = torch.sum(mask, dim=(1, 2, 3))
    n_eff_t = torch.tensor(info_t["n_eff"], device=mask.device, dtype=den.dtype)
    n_eff_p = torch.tensor(info_p["n_eff"], device=mask.device, dtype=den.dtype)
    valid = (n_eff_t >= float(info_t["n_min"])) & (n_eff_p >= float(info_p["n_min"]))
    if not torch.any(valid):
        return pred01.new_tensor(0.0)
    den = den.clamp_min(1.0)
    num1 = torch.sum(pred_edge * dt_t * mask, dim=(1, 2, 3))
    num2 = torch.sum(tgt_edge * dt_p * mask, dim=(1, 2, 3))
    loss = (num1 / den + num2 / den) * valid.float()
    loss = loss.sum() / valid.float().sum().clamp_min(1.0)
    cap = float(CFG.EDGE_CHAMFER_CAP)
    if cap > 0.0:
        loss = F.smooth_l1_loss(loss, loss.new_tensor(cap), beta=float(CFG.EDGE_CHAMFER_HUBER_BETA))
    return loss


# ============================================================
# GMF proxy validation helpers
# ============================================================
def _sobel_np(x01: np.ndarray):
    gx = cv2.Sobel(x01, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(x01, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy)
    ang = np.arctan2(gy, gx)
    return mag, ang


def _edge_mag_norm_np(mag: np.ndarray, mask: np.ndarray) -> np.ndarray:
    q = float(CFG.EDGE_MAG_NORM_Q)
    floor = float(CFG.EDGE_MAG_NORM_MIN)
    if mask is not None:
        sel = mag[mask > 0.5]
    else:
        sel = mag.reshape(-1)
    if sel.size < 8:
        scale = max(float(sel.max()) if sel.size else 1.0, floor)
    else:
        scale = max(float(np.quantile(sel, q)), floor)
    return mag / scale


def extract_edgels_np(x01: np.ndarray, mask: np.ndarray, q_init: float = None):
    mag, ang = _sobel_np(x01)
    if mask is None:
        mask = np.ones_like(mag, dtype=bool)
    else:
        mask = mask > 0.5
    mag_n = _edge_mag_norm_np(mag, mask)
    q0 = float(CFG.EDGE_EXTRACT_Q_INIT) if q_init is None else float(q_init)
    q_step = float(CFG.EDGE_EXTRACT_Q_STEP)
    q_min = float(CFG.EDGE_EXTRACT_Q_MIN)
    q_max = float(CFG.EDGE_EXTRACT_Q_MAX)
    min_d = float(CFG.EDGE_DENSITY_MIN)
    max_d = float(CFG.EDGE_DENSITY_MAX)
    max_steps = max(1, int(CFG.EDGE_EXTRACT_MAX_STEPS))
    target_d = float(CFG.EDGE_TOPK_TARGET_DENSITY)
    if target_d <= 0.0:
        target_d = 0.5 * (min_d + max_d)

    sel = mag_n[mask]
    if sel.size < 8:
        thr = float(sel.max()) if sel.size else float("inf")
    else:
        thr = float(np.quantile(sel, q0))
    edge = (mag_n > thr) & mask
    n_mask = int(mask.sum())
    dens = float(edge.sum() / max(n_mask, 1))
    q_used = q0
    for _ in range(max_steps):
        if dens > max_d and q_used < q_max - 1e-6:
            q_used = min(q_used + q_step, q_max)
        elif dens < min_d and q_used > q_min + 1e-6:
            q_used = max(q_used - q_step, q_min)
        else:
            break
        thr = float(np.quantile(sel, q_used)) if sel.size >= 8 else float(sel.max()) if sel.size else float("inf")
        edge = (mag_n > thr) & mask
        dens = float(edge.sum() / max(n_mask, 1))

    k_used = 0
    if (dens > max_d or dens < min_d) and bool(CFG.EDGE_EXTRACT_USE_TOPK) and n_mask > 0:
        n_min = max(int(CFG.EDGE_N_MIN_FRAC * mag.shape[0] * mag.shape[1]), int(CFG.EDGE_N_MIN_PIX))
        k = int(round(target_d * n_mask))
        k = max(k, n_min)
        k = min(k, n_mask)
        if sel.size >= k:
            kth = float(np.partition(sel, -k)[-k])
            edge = (mag_n >= kth) & mask
            dens = float(edge.sum() / max(n_mask, 1))
            k_used = k

    info = {
        "q_used": float(q_used),
        "k_used": int(k_used),
        "density": float(dens),
        "thr": float(thr),
        "n_eff": int(edge.sum()),
        "n_mask": n_mask,
    }
    return edge.astype(np.uint8), ang.astype(np.float32), mag_n.astype(np.float32), info


def save_proxy_edge_sanity(raw01: np.ndarray, sr01: np.ndarray, mask: np.ndarray,
                           out_dir: Path, epoch1: int):
    h = min(raw01.shape[0], sr01.shape[0])
    w = min(raw01.shape[1], sr01.shape[1])
    raw01 = raw01[:h, :w]
    sr01 = sr01[:h, :w]
    mask = mask[:h, :w]

    edge_raw, ang_raw, mag_raw_n, info_raw = extract_edgels_np(raw01, mask)
    edge_sr, ang_sr, mag_sr_n, info_sr = extract_edgels_np(sr01, mask)
    density_raw = float(info_raw["density"])
    density_sr = float(info_sr["density"])
    base = (raw01 * 0.35).astype(np.float32)
    overlay = np.zeros((h, w, 3), dtype=np.float32)
    overlay[..., 0] = np.clip(base + mag_raw_n, 0.0, 1.0)
    overlay[..., 1] = np.clip(base + mag_sr_n, 0.0, 1.0)
    overlay[..., 2] = base
    overlay_u8 = (overlay * 255.0).round().clip(0, 255).astype(np.uint8)
    out_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_dir / "gmf_edge_overlay.png"), cv2.cvtColor(overlay_u8, cv2.COLOR_RGB2BGR))

    bins = np.linspace(0.0, np.pi, 37)
    if edge_raw.any():
        ang_raw_m = np.mod(ang_raw[edge_raw > 0], np.pi)
        hist_raw, _ = np.histogram(ang_raw_m, bins=bins, density=True)
    else:
        hist_raw = np.zeros(len(bins) - 1, dtype=np.float32)
    if edge_sr.any():
        ang_sr_m = np.mod(ang_sr[edge_sr > 0], np.pi)
        hist_sr, _ = np.histogram(ang_sr_m, bins=bins, density=True)
    else:
        hist_sr = np.zeros(len(bins) - 1, dtype=np.float32)
    centers = (bins[:-1] + bins[1:]) * 0.5
    hist_sim = float(np.dot(hist_raw, hist_sr) / (np.linalg.norm(hist_raw) * np.linalg.norm(hist_sr) + 1e-9))
    if edge_raw.any():
        a = ang_raw_m
        c = np.cos(2.0 * a).mean()
        s = np.sin(2.0 * a).mean()
        mean_raw = 0.5 * math.atan2(s, c)
        if mean_raw < 0:
            mean_raw += np.pi
        R_raw = math.sqrt(c * c + s * s)
    else:
        mean_raw = float("nan")
        R_raw = float("nan")
    if edge_sr.any():
        a = ang_sr_m
        c = np.cos(2.0 * a).mean()
        s = np.sin(2.0 * a).mean()
        mean_sr = 0.5 * math.atan2(s, c)
        if mean_sr < 0:
            mean_sr += np.pi
        R_sr = math.sqrt(c * c + s * s)
    else:
        mean_sr = float("nan")
        R_sr = float("nan")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.5))
    ax1.bar([0, 1], [density_raw, density_sr], color=["#d95f02", "#1b9e77"])
    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(["Raw", "SR"])
    ax1.set_ylabel("Edge Density")
    ax1.set_ylim(0.0, max(density_raw, density_sr) * 1.2 + 1e-6)
    ax1.grid(True, axis="y")
    ax1.text(
        0.02, 0.98,
        f"q_raw={info_raw['q_used']:.2f} k_raw={info_raw['k_used']}\n"
        f"q_sr={info_sr['q_used']:.2f} k_sr={info_sr['k_used']}\n"
        f"raw_dens={density_raw:.4f} sr_dens={density_sr:.4f}",
        transform=ax1.transAxes, va="top", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.6", alpha=0.85),
    )
    ax2.plot(centers, hist_raw, label="Raw")
    ax2.plot(centers, hist_sr, label="SR")
    ax2.set_xlim(0.0, np.pi)
    ax2.set_xlabel("Orientation (rad)")
    ax2.set_ylabel("Density")
    ax2.grid(True)
    ax2.legend(loc="best")
    ax2.text(
        0.02, 0.98,
        f"raw_mean={mean_raw:.2f}, R={R_raw:.2f}\n"
        f"sr_mean={mean_sr:.2f}, R={R_sr:.2f}\n"
        f"hist_sim={hist_sim:.3f}",
        transform=ax2.transAxes, va="top", fontsize=8,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.6", alpha=0.85),
    )
    fig.suptitle(f"GMF Proxy Edge Sanity (E{int(epoch1):03d})")
    fig.savefig(out_dir / "gmf_edge_hist.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return {
        "density_raw": float(density_raw),
        "density_sr": float(density_sr),
        "hist_sim": float(hist_sim),
        "q_raw": float(info_raw["q_used"]),
        "q_sr": float(info_sr["q_used"]),
        "k_raw": float(info_raw["k_used"]),
        "k_sr": float(info_sr["k_used"]),
    }


def _shift_map(arr: np.ndarray, tx: int, ty: int) -> np.ndarray:
    h, w = arr.shape
    out = np.zeros_like(arr)
    width = w - abs(int(tx))
    height = h - abs(int(ty))
    if width <= 0 or height <= 0:
        return out
    x0_src = max(0, -int(tx))
    y0_src = max(0, -int(ty))
    x0_dst = max(0, int(tx))
    y0_dst = max(0, int(ty))
    out[y0_dst:y0_dst + height, x0_dst:x0_dst + width] = arr[y0_src:y0_src + height, x0_src:x0_src + width]
    return out


def _center_pad_or_crop(arr: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    h, w = arr.shape
    out = np.zeros((target_h, target_w), dtype=arr.dtype)
    y0_src = max(0, (h - target_h) // 2)
    x0_src = max(0, (w - target_w) // 2)
    y1_src = y0_src + min(h, target_h)
    x1_src = x0_src + min(w, target_w)
    y0_dst = max(0, (target_h - h) // 2)
    x0_dst = max(0, (target_w - w) // 2)
    out[y0_dst:y0_dst + (y1_src - y0_src), x0_dst:x0_dst + (x1_src - x0_src)] = arr[y0_src:y1_src, x0_src:x1_src]
    return out


def _scale_edge_maps(edge: np.ndarray, ang: np.ndarray, scale: float, target_h: int, target_w: int):
    if abs(scale - 1.0) < 1e-6:
        return edge, ang
    new_h = max(1, int(round(edge.shape[0] * float(scale))))
    new_w = max(1, int(round(edge.shape[1] * float(scale))))
    edge_r = cv2.resize(edge.astype(np.uint8), (new_w, new_h), interpolation=cv2.INTER_NEAREST).astype(edge.dtype)
    ang_r = cv2.resize(ang.astype(np.float32), (new_w, new_h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    return _center_pad_or_crop(edge_r, target_h, target_w), _center_pad_or_crop(ang_r, target_h, target_w)


def _proxy_match_cost(model_edge: np.ndarray, model_ang: np.ndarray, frame_edge: np.ndarray, frame_ang: np.ndarray,
                      dt_frame: np.ndarray, mask: np.ndarray, tx: int, ty: int) -> float:
    me = _shift_map(model_edge, tx, ty)
    ma = _shift_map(model_ang, tx, ty)
    edge_mask = (me > 0) & mask
    edge_count = float(edge_mask.sum())
    if edge_count <= 0:
        return 1e6
    chamfer = float(dt_frame[edge_mask].mean())
    overlap = edge_mask & (frame_edge > 0)
    if overlap.any():
        diff = ma[overlap] - frame_ang[overlap]
        ori_cost = float(np.mean(1.0 - np.cos(diff)))
    else:
        ori_cost = 1.0
    chamfer = chamfer / max(float(CFG.PROXY_CHAMFER_NORM), 1e-6)
    return chamfer + float(CFG.PROXY_ORI_WEIGHT) * ori_cost


def _proxy_match_score(model_edge: np.ndarray, model_ang: np.ndarray, frame_edge: np.ndarray, frame_ang: np.ndarray,
                       dt_frame: np.ndarray, mask: np.ndarray, tx: int, ty: int):
    me = _shift_map(model_edge, tx, ty)
    ma = _shift_map(model_ang, tx, ty)
    edge_mask = (me > 0) & mask
    n = int(edge_mask.sum())
    if n <= 0:
        return 0.0, 0.0, 0.0
    dist = dt_frame[edge_mask]
    match_dist = float(CFG.PROXY_MATCH_DIST)
    matched = dist <= match_dist
    matched_ratio = float(np.mean(matched)) if matched.size else 0.0

    overlap = edge_mask & (frame_edge > 0)
    if overlap.any():
        diff = ma[overlap] - frame_ang[overlap]
        ang_diff = np.abs(np.arctan2(np.sin(diff), np.cos(diff)))
        ang_thresh = math.radians(float(CFG.PROXY_MATCH_ANG_DEG))
        ang_match = ang_diff <= ang_thresh
        ori_ratio = float(np.mean(ang_match)) if ang_match.size else 0.0
    else:
        ori_ratio = 0.0

    score = matched_ratio * (0.5 + 0.5 * ori_ratio) * 100.0
    return score, matched_ratio, ori_ratio


def _proxy_search_translation(model_edge: np.ndarray, model_ang: np.ndarray, frame_edge: np.ndarray,
                              frame_ang: np.ndarray, dt_frame: np.ndarray, mask: np.ndarray):
    r = int(CFG.PROXY_SEARCH_RADIUS)
    coarse = max(1, int(CFG.PROXY_COARSE_STRIDE))
    fine = max(1, int(CFG.PROXY_FINE_STRIDE))
    best = (1e12, 0, 0)
    for ty in range(-r, r + 1, coarse):
        for tx in range(-r, r + 1, coarse):
            cost = _proxy_match_cost(model_edge, model_ang, frame_edge, frame_ang, dt_frame, mask, tx, ty)
            if cost < best[0]:
                best = (cost, tx, ty)
    fine_r = max(coarse, fine)
    bt, bx, by = best[0], best[1], best[2]
    for ty in range(by - fine_r, by + fine_r + 1, fine):
        for tx in range(bx - fine_r, bx + fine_r + 1, fine):
            if abs(tx) > r or abs(ty) > r:
                continue
            cost = _proxy_match_cost(model_edge, model_ang, frame_edge, frame_ang, dt_frame, mask, tx, ty)
            if cost < bt:
                bt, bx, by = cost, tx, ty
    return bt, bx, by


def _proxy_search_pose(model_edge: np.ndarray, model_ang: np.ndarray, frame_edge: np.ndarray,
                       frame_ang: np.ndarray, dt_frame: np.ndarray, mask: np.ndarray):
    h, w = mask.shape
    if not CFG.PROXY_SCALE_ENABLE:
        cost, tx, ty = _proxy_search_translation(model_edge, model_ang, frame_edge, frame_ang, dt_frame, mask)
        return cost, tx, ty, 1.0
    scales = []
    s = float(CFG.PROXY_SCALE_MIN)
    s_max = float(CFG.PROXY_SCALE_MAX)
    step = max(float(CFG.PROXY_SCALE_STEP), 1e-6)
    while s <= s_max + 1e-9:
        scales.append(s)
        s += step
    best = (1e12, 0, 0, 1.0)
    for sc in scales:
        me, ma = _scale_edge_maps(model_edge, model_ang, sc, h, w)
        cost, tx, ty = _proxy_search_translation(me, ma, frame_edge, frame_ang, dt_frame, mask)
        if cost < best[0]:
            best = (cost, tx, ty, sc)
    return best


def _edge_density(edge: np.ndarray, mask: np.ndarray) -> float:
    denom = float(mask.sum())
    if denom <= 0:
        return 0.0
    return float(edge.sum() / denom)


def _density_penalty(density: float) -> float:
    min_d = float(CFG.PROXY_EDGE_DENSITY_MIN)
    max_d = float(CFG.PROXY_EDGE_DENSITY_MAX)
    if density <= 0.0:
        return 0.0
    if density < min_d:
        return max(0.0, density / max(min_d, 1e-6))
    if density > max_d:
        return max(0.0, max_d / max(density, 1e-6))
    return 1.0


def _robust_std(arr: np.ndarray) -> float:
    if arr.size <= 0:
        return 0.0
    med = float(np.median(arr))
    mad = float(np.median(np.abs(arr - med)))
    return 1.4826 * mad


def compute_proxy_metrics(scores: np.ndarray, posx: np.ndarray, posy: np.ndarray, scales: np.ndarray,
                          lr_scores: Optional[np.ndarray] = None,
                          invalid_count: int = 0, total_frames: int = 0):
    metrics = {}
    metrics["proxy_score_mean"] = float(np.mean(scores)) if scores.size else 0.0
    metrics["proxy_score_p10"] = float(np.percentile(scores, 10)) if scores.size else 0.0
    if lr_scores is not None:
        lr_scores = np.asarray(lr_scores, dtype=np.float64)
    if lr_scores is not None and lr_scores.size:
        lr_scores = np.asarray(lr_scores, dtype=np.float64)
        n = min(scores.size, lr_scores.size)
        delta = scores[:n] - lr_scores[:n]
        metrics["proxy_score_lr_mean"] = float(np.mean(lr_scores)) if lr_scores.size else 0.0
        metrics["proxy_score_lr_p10"] = float(np.percentile(lr_scores, 10)) if lr_scores.size else 0.0
        metrics["proxy_score_pass_rate"] = float(np.mean(delta > float(CFG.GMF_PASS_DELTA)) * 100.0) if n > 0 else 0.0
        metrics["proxy_gain_mean"] = float(np.mean(delta)) if n > 0 else 0.0
        metrics["proxy_gain_p10"] = float(np.percentile(delta, 10)) if n > 0 else 0.0
        metrics["proxy_lr_enable"] = 1
    else:
        metrics["proxy_score_lr_mean"] = 0.0
        metrics["proxy_score_lr_p10"] = 0.0
        metrics["proxy_score_pass_rate"] = 0.0
        metrics["proxy_gain_mean"] = 0.0
        metrics["proxy_gain_p10"] = 0.0
        metrics["proxy_lr_enable"] = 0
    if posx.size >= 2:
        dx = np.diff(posx)
        metrics["proxy_posx_step_mean"] = float(np.mean(dx))
        metrics["proxy_posx_adj_std"] = float(_robust_std(dx))
    else:
        metrics["proxy_posx_step_mean"] = 0.0
        metrics["proxy_posx_adj_std"] = 0.0
    if posy.size >= 2:
        dy = np.diff(posy)
        metrics["proxy_posy_step_mean"] = float(np.mean(dy))
        metrics["proxy_posy_adj_std"] = float(_robust_std(dy))
    else:
        metrics["proxy_posy_step_mean"] = 0.0
        metrics["proxy_posy_adj_std"] = 0.0

    expect_dx = CFG.GMF_EXPECT_DX_PX
    expect_dy = CFG.GMF_EXPECT_DY_PX
    if (expect_dx is not None) and (expect_dy is not None) and np.isfinite(expect_dx) and np.isfinite(expect_dy):
        if np.isfinite(metrics["proxy_posx_step_mean"]) and np.isfinite(metrics["proxy_posy_step_mean"]):
            metrics["proxy_step_err"] = abs(metrics["proxy_posx_step_mean"] - float(expect_dx)) + abs(metrics["proxy_posy_step_mean"] - float(expect_dy))
        else:
            metrics["proxy_step_err"] = 0.0
    else:
        mad_dx = _robust_std(np.diff(posx)) if posx.size >= 2 else 0.0
        mad_dy = _robust_std(np.diff(posy)) if posy.size >= 2 else 0.0
        metrics["proxy_step_err"] = mad_dx + mad_dy
    if not np.isfinite(metrics["proxy_step_err"]):
        metrics["proxy_step_err"] = 0.0

    steps = np.sqrt((np.diff(posx) ** 2) + (np.diff(posy) ** 2)) if posx.size >= 2 else np.zeros(0, dtype=np.float64)
    expected_step_px = 0.0
    expected_enable = 0
    if (expect_dx is not None) and (expect_dy is not None) and np.isfinite(expect_dx) and np.isfinite(expect_dy):
        expected_step_px = float(np.sqrt(float(expect_dx) ** 2 + float(expect_dy) ** 2))
        expected_enable = 1
    step_mean = float(np.mean(steps)) if steps.size else 0.0
    step_std = float(np.std(steps)) if steps.size else 0.0
    step_mean_err = abs(step_mean - expected_step_px) if expected_enable else 0.0
    outlier_t = float(CFG.GMF_OUTLIER_T)
    if expected_enable and float(CFG.GMF_OUTLIER_T_REL) > 0.0:
        outlier_t = max(outlier_t, expected_step_px * float(CFG.GMF_OUTLIER_T_REL))
    if expected_enable and steps.size:
        outlier_rate = float(np.mean(np.abs(steps - expected_step_px) > outlier_t))
    else:
        outlier_rate = 0.0
    metrics["kpi_step_mean_err"] = float(step_mean_err)
    metrics["kpi_step_std"] = float(step_std)
    metrics["kpi_outlier_rate"] = float(outlier_rate)
    metrics["kpi_outlier_t"] = float(outlier_t)
    metrics["kpi_expected_step_px"] = float(expected_step_px)
    metrics["kpi_expected_step_enable"] = int(expected_enable)

    metrics["proxy_pos_step_std_sum"] = (
        float(metrics["proxy_posx_adj_std"] + metrics["proxy_posy_adj_std"])
        if np.isfinite(metrics["proxy_posx_adj_std"]) and np.isfinite(metrics["proxy_posy_adj_std"])
        else np.nan
    )
    if CFG.PROXY_SCALE_ENABLE:
        metrics["proxy_scale_mean"] = float(np.mean(scales)) if scales.size else np.nan
        metrics["proxy_scale_dev"] = float(np.mean(np.abs(scales - 1.0))) if scales.size else np.nan
        metrics["proxy_scale_std"] = float(np.std(scales)) if scales.size else np.nan
    else:
        metrics["proxy_scale_mean"] = np.nan
        metrics["proxy_scale_dev"] = np.nan
        metrics["proxy_scale_std"] = np.nan

    invalid_count = int(invalid_count)
    total_frames = int(total_frames)
    metrics["proxy_invalid_count"] = invalid_count
    metrics["proxy_invalid_rate"] = float(invalid_count / max(total_frames, 1))
    if invalid_count > 0:
        penalty = float(CFG.PROXY_INVALID_PENALTY)
        metrics["proxy_score_mean"] = min(metrics["proxy_score_mean"], float(CFG.PROXY_INVALID_SCORE))
        metrics["proxy_score_p10"] = min(metrics["proxy_score_p10"], float(CFG.PROXY_INVALID_SCORE))
        metrics["proxy_score_pass_rate"] = min(metrics["proxy_score_pass_rate"], 0.0)
        metrics["proxy_posx_adj_std"] = max(metrics["proxy_posx_adj_std"], penalty)
        metrics["proxy_posy_adj_std"] = max(metrics["proxy_posy_adj_std"], penalty)
        metrics["proxy_pos_step_std_sum"] = max(metrics["proxy_pos_step_std_sum"], penalty)
        metrics["proxy_scale_std"] = max(metrics["proxy_scale_std"], penalty)
        metrics["proxy_scale_dev"] = max(metrics["proxy_scale_dev"], penalty)
        metrics["proxy_step_err"] = max(metrics["proxy_step_err"], penalty)
    return metrics


def _gmf_proxy_from_frames(frames: list, raws: list, epoch1: int, save_sanity: bool = True, verbose: bool = True):
    if len(frames) < 2:
        scores = np.array([0.0], dtype=np.float64)
        posx = np.array([0.0], dtype=np.float64)
        posy = np.array([0.0], dtype=np.float64)
        scales = np.array([1.0], dtype=np.float64)
        metrics = compute_proxy_metrics(scores, posx, posy, scales, lr_scores=scores, invalid_count=1, total_frames=1)
        metrics["proxy_epoch"] = int(epoch1)
        metrics["proxy_invalid_density"] = 1.0
        return metrics

    device = torch.device(CFG.DEVICE)
    h_min = min(f.shape[0] for f in frames)
    w_min = min(f.shape[1] for f in frames)
    if raws:
        h_min = min(h_min, min(r.shape[0] for r in raws))
        w_min = min(w_min, min(r.shape[1] for r in raws))
    if any(f.shape[0] != h_min or f.shape[1] != w_min for f in frames):
        frames = [f[:h_min, :w_min] for f in frames]
    if raws:
        if any(r.shape[0] != h_min or r.shape[1] != w_min for r in raws):
            raws = [r[:h_min, :w_min] for r in raws]

    h, w = frames[0].shape
    mask_t = make_valid_mask(torch.zeros((1, 1, h, w), device=device)).squeeze(0).squeeze(0).cpu().numpy()
    mask = (mask_t > 0.5)

    n_min = max(int(CFG.EDGE_N_MIN_FRAC * h * w), int(CFG.EDGE_N_MIN_PIX))
    model_ref = raws[0] if len(raws) > 0 else frames[0]
    model_edge, model_ang, _, info_m = extract_edgels_np(model_ref, mask)
    density_m = float(info_m["density"])
    penalty_m = _density_penalty(density_m)
    invalid_density = int(penalty_m < 1.0)
    invalid_model = int(info_m["n_eff"] < n_min)
    if verbose:
        if invalid_model:
            print(f"[PROXY] Model edge count too low: n_eff={info_m['n_eff']} (<{n_min}).")
        if penalty_m < 1.0:
            print(f"[PROXY] Model edge density out of range: {density_m:.4f} (penalty={penalty_m:.2f})")

    scores = []
    lr_scores = []
    posx = []
    posy = []
    scales = []
    match_ratios = []
    ori_ratios = []
    dens_sr = []
    q_sr = []
    k_sr = []
    invalid_count = 0
    invalid_frame = 0
    sanity_stats = None
    if save_sanity and len(raws) > 0:
        sanity_dir = Path(PROGRESS_DIR) / "gmf_val_sr__sanity"
        sanity_stats = save_proxy_edge_sanity(raws[0], frames[0], mask, sanity_dir, epoch1)

    if invalid_model:
        scores = np.zeros(len(frames), dtype=np.float64)
        lr_scores = np.zeros(len(frames), dtype=np.float64)
        posx = np.zeros(len(frames), dtype=np.float64)
        posy = np.zeros(len(frames), dtype=np.float64)
        scales = np.ones(len(frames), dtype=np.float64)
        metrics = compute_proxy_metrics(scores, posx, posy, scales, lr_scores=lr_scores,
                                        invalid_count=len(frames), total_frames=len(frames))
        metrics["proxy_epoch"] = int(epoch1)
        metrics["proxy_edge_density_model"] = density_m
        metrics["proxy_edge_density_sr_mean"] = 0.0
        metrics["proxy_edge_q_model"] = float(info_m["q_used"])
        metrics["proxy_edge_q_sr_mean"] = float("nan")
        metrics["proxy_edge_k_model"] = float(info_m["k_used"])
        metrics["proxy_edge_k_sr_mean"] = float("nan")
        metrics["proxy_match_ratio_mean"] = 0.0
        metrics["proxy_ori_ratio_mean"] = 0.0
        metrics["proxy_hist_sim"] = float(sanity_stats["hist_sim"]) if sanity_stats else float("nan")
        metrics["proxy_invalid_model"] = float(invalid_model)
        metrics["proxy_invalid_frame"] = float(len(frames))
        metrics["proxy_invalid_density"] = float(invalid_density)
        return metrics

    for idx, frame in enumerate(frames):
        frame_edge, frame_ang, _, info_f = extract_edgels_np(frame, mask)
        density_f = float(info_f["density"])
        penalty_f = _density_penalty(density_f)
        dens_sr.append(density_f)
        q_sr.append(float(info_f["q_used"]))
        k_sr.append(int(info_f["k_used"]))
        if verbose and penalty_f < 1.0:
            print(f"[PROXY] Frame edge density out of range: {density_f:.4f} (penalty={penalty_f:.2f})")
            invalid_density += 1
        dt = cv2.distanceTransform((1 - frame_edge).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)

        raw_frame = raws[idx] if idx < len(raws) else frame
        raw_edge, raw_ang, _, info_r = extract_edgels_np(raw_frame, mask)
        density_r = float(info_r["density"])
        penalty_r = _density_penalty(density_r)
        dt_raw = cv2.distanceTransform((1 - raw_edge).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)

        if idx == 0:
            score0, mratio0, oratio0 = _proxy_match_score(model_edge, model_ang, frame_edge, frame_ang, dt, mask, 0, 0)
            score0_lr, _, _ = _proxy_match_score(model_edge, model_ang, raw_edge, raw_ang, dt_raw, mask, 0, 0)
            scores.append(score0)
            lr_scores.append(score0_lr * penalty_m * penalty_r)
            posx.append(0.0)
            posy.append(0.0)
            scales.append(1.0)
            match_ratios.append(mratio0)
            ori_ratios.append(oratio0)
            continue

        if invalid_model or (info_f["n_eff"] < n_min):
            invalid_count += 1
            invalid_frame += int(info_f["n_eff"] < n_min)
            scores.append(float(CFG.PROXY_INVALID_SCORE))
            lr_scores.append(float(CFG.PROXY_INVALID_SCORE))
            posx.append(0.0)
            posy.append(0.0)
            scales.append(1.0)
            match_ratios.append(0.0)
            ori_ratios.append(0.0)
            continue

        cost, tx, ty, sc = _proxy_search_pose(model_edge, model_ang, frame_edge, frame_ang, dt, mask)
        score, mratio, oratio = _proxy_match_score(model_edge, model_ang, frame_edge, frame_ang, dt, mask, tx, ty)
        score *= penalty_m * penalty_f
        scores.append(score)

        if info_r["n_eff"] < n_min:
            lr_scores.append(float(CFG.PROXY_INVALID_SCORE))
        else:
            cost_lr, tx_lr, ty_lr, sc_lr = _proxy_search_pose(model_edge, model_ang, raw_edge, raw_ang, dt_raw, mask)
            score_lr, _, _ = _proxy_match_score(model_edge, model_ang, raw_edge, raw_ang, dt_raw, mask, tx_lr, ty_lr)
            lr_scores.append(score_lr * penalty_m * penalty_r)

        posx.append(float(tx))
        posy.append(float(ty))
        scales.append(float(sc))
        match_ratios.append(mratio)
        ori_ratios.append(oratio)

    scores = np.array(scores, dtype=np.float64)
    posx = np.array(posx, dtype=np.float64)
    posy = np.array(posy, dtype=np.float64)
    scales = np.array(scales, dtype=np.float64)
    metrics = compute_proxy_metrics(scores, posx, posy, scales, lr_scores=lr_scores,
                                    invalid_count=invalid_count, total_frames=len(frames))
    metrics["proxy_epoch"] = int(epoch1)
    metrics["proxy_edge_density_model"] = density_m
    metrics["proxy_edge_density_sr_mean"] = float(np.mean(dens_sr)) if len(dens_sr) else 0.0
    metrics["proxy_edge_q_model"] = float(info_m["q_used"])
    metrics["proxy_edge_q_sr_mean"] = float(np.mean(q_sr)) if len(q_sr) else float("nan")
    metrics["proxy_edge_k_model"] = float(info_m["k_used"])
    metrics["proxy_edge_k_sr_mean"] = float(np.mean(k_sr)) if len(k_sr) else float("nan")
    metrics["proxy_match_ratio_mean"] = float(np.mean(match_ratios)) if len(match_ratios) else 0.0
    metrics["proxy_ori_ratio_mean"] = float(np.mean(ori_ratios)) if len(ori_ratios) else 0.0
    metrics["proxy_hist_sim"] = float(sanity_stats["hist_sim"]) if sanity_stats else float("nan")
    metrics["proxy_invalid_model"] = float(invalid_model)
    metrics["proxy_invalid_frame"] = float(invalid_frame)
    metrics["proxy_invalid_density"] = float(invalid_density)
    return metrics


@torch.no_grad()
def run_gmf_proxy_validation(model: nn.Module, val_loader, epoch1: int):
    if val_loader is None:
        print("[PROXY] Validation loader is None; proxy metrics will be NaN.")
        return {
            "proxy_score_mean": np.nan,
            "proxy_score_p10": np.nan,
            "proxy_score_lr_mean": 0.0,
            "proxy_score_lr_p10": 0.0,
            "proxy_score_pass_rate": np.nan,
            "proxy_gain_mean": 0.0,
            "proxy_gain_p10": 0.0,
            "proxy_lr_enable": 0,
            "kpi_step_mean_err": 0.0,
            "kpi_step_std": 0.0,
            "kpi_outlier_rate": 0.0,
            "kpi_outlier_t": float(CFG.GMF_OUTLIER_T),
            "kpi_expected_step_px": 0.0,
            "kpi_expected_step_enable": 0,
            "proxy_posx_step_mean": np.nan,
            "proxy_posy_step_mean": np.nan,
            "proxy_step_err": np.nan,
            "proxy_pos_step_std_sum": np.nan,
            "proxy_scale_mean": np.nan,
            "proxy_scale_dev": np.nan,
            "proxy_posx_adj_std": np.nan,
            "proxy_posy_adj_std": np.nan,
            "proxy_scale_std": np.nan,
            "proxy_invalid_count": np.nan,
            "proxy_invalid_rate": np.nan,
            "proxy_edge_density_model": np.nan,
            "proxy_edge_density_sr_mean": np.nan,
            "proxy_edge_q_model": np.nan,
            "proxy_edge_q_sr_mean": np.nan,
            "proxy_edge_k_model": np.nan,
            "proxy_edge_k_sr_mean": np.nan,
            "proxy_match_ratio_mean": np.nan,
            "proxy_ori_ratio_mean": np.nan,
            "proxy_hist_sim": np.nan,
            "proxy_invalid_model": np.nan,
            "proxy_invalid_frame": np.nan,
            "proxy_invalid_density": np.nan,
            "kpi_step_mean_err_off": 0.0,
            "kpi_step_std_off": 0.0,
            "kpi_outlier_rate_off": 0.0,
            "kpi_step_mean_err_delta": 0.0,
            "kpi_step_std_delta": 0.0,
            "kpi_outlier_rate_delta": 0.0,
        }

    device = torch.device(CFG.DEVICE)
    model.eval()
    frames = []
    raws = []
    max_frames = int(CFG.GMF_VAL_NUM_FRAMES)

    for batch in val_loader:
        src, _ = _unpack_batch(batch)
        src = src.to(device, non_blocking=True)
        with torch.cuda.amp.autocast(enabled=CFG.use_amp):
            pred = model(src)
        pred01 = pred.float().clamp(0.0, 1.0).cpu().numpy()
        src01 = src.float().clamp(0.0, 1.0).cpu().numpy()
        for i in range(pred01.shape[0]):
            frames.append(pred01[i, 0])
            raws.append(src01[i, 0])
            if len(frames) >= max_frames:
                break
        if len(frames) >= max_frames:
            break

    if len(frames) < 2:
        print(f"[PROXY] Need >= 2 frames for proxy validation, found {len(frames)}. Returning low scores.")

    save_proxy_sanity = True
    proxy_verbose = True
    if CFG.FAST_IO_MODE:
        save_proxy_sanity = bool(CFG.FAST_SAVE_PROXY_SANITY)
        proxy_verbose = False
    metrics = _gmf_proxy_from_frames(
        frames,
        raws,
        epoch1,
        save_sanity=save_proxy_sanity,
        verbose=proxy_verbose,
    )
    metrics["kpi_step_mean_err_off"] = 0.0
    metrics["kpi_step_std_off"] = 0.0
    metrics["kpi_outlier_rate_off"] = 0.0
    metrics["kpi_step_mean_err_delta"] = 0.0
    metrics["kpi_step_std_delta"] = 0.0
    metrics["kpi_outlier_rate_delta"] = 0.0

    block = get_weak_psf_block(model)
    if (block is not None) and CFG.WEAK_PSF_ENABLE and len(raws) >= 2:
        beta_scale = float(getattr(block, "beta_scale", torch.tensor(0.0)).detach().item())
        entropy_mix = float(getattr(block, "entropy_mix", torch.tensor(0.0)).detach().item())
        try:
            block.set_beta_scale(0.0)
            block.set_entropy_mix(0.0)
            raw_np = np.stack(raws, axis=0)
            raw_t = torch.from_numpy(raw_np).unsqueeze(1).to(device=device, dtype=torch.float32)
            with torch.cuda.amp.autocast(enabled=CFG.use_amp):
                pred_off = model(raw_t)
            pred01_off = pred_off.float().clamp(0.0, 1.0).cpu().numpy()
            frames_off = [pred01_off[i, 0] for i in range(pred01_off.shape[0])]
            off_metrics = _gmf_proxy_from_frames(frames_off, raws, epoch1, save_sanity=False, verbose=False)
            metrics["kpi_step_mean_err_off"] = float(off_metrics.get("kpi_step_mean_err", 0.0))
            metrics["kpi_step_std_off"] = float(off_metrics.get("kpi_step_std", 0.0))
            metrics["kpi_outlier_rate_off"] = float(off_metrics.get("kpi_outlier_rate", 0.0))
            metrics["kpi_step_mean_err_delta"] = float(metrics.get("kpi_step_mean_err", 0.0)) - metrics["kpi_step_mean_err_off"]
            metrics["kpi_step_std_delta"] = float(metrics.get("kpi_step_std", 0.0)) - metrics["kpi_step_std_off"]
            metrics["kpi_outlier_rate_delta"] = float(metrics.get("kpi_outlier_rate", 0.0)) - metrics["kpi_outlier_rate_off"]
        except Exception as exc:
            print(f"[PROXY][AB] weak-psf bypass eval failed: {exc}")
        finally:
            block.set_beta_scale(beta_scale)
            block.set_entropy_mix(entropy_mix)

    return metrics


def _zscore(curr: float, history: list, key: str) -> float:
    vals = [d.get(key, np.nan) for d in history if isinstance(d, dict)]
    vals = [v for v in vals if np.isfinite(v)]
    if len(vals) < 2 or (not np.isfinite(curr)):
        return 0.0
    mu = float(np.mean(vals))
    sigma = float(np.std(vals))
    if sigma < 1e-6:
        return 0.0
    return (float(curr) - mu) / sigma


def compute_gmf_obj(curr: dict):
    if curr is None:
        return None

    def _finite(v):
        return (v is not None) and np.isfinite(v)

    def _val(key: str, default: float = 0.0) -> float:
        v = curr.get(key, default)
        return float(v) if _finite(v) else float(default)

    score_p10 = _val("proxy_score_p10", 0.0)
    score_mean = _val("proxy_score_mean", 0.0)
    step_err = _val("proxy_step_err", 0.0)
    pos_std_sum = _val("proxy_pos_step_std_sum", 0.0)
    val_hf = curr.get("val_hf_ratio", np.nan)
    if not _finite(val_hf):
        val_hf = _val("train_hf_ratio", 0.0)
    val_cb = curr.get("val_cb", np.nan)
    if not _finite(val_cb):
        val_cb = _val("train_cb", 0.0)

    obj = (
        float(CFG.GMF_OBJ_A) * score_p10
        + float(CFG.GMF_OBJ_B) * score_mean
        - float(CFG.GMF_OBJ_C) * step_err
        - float(CFG.GMF_OBJ_D) * pos_std_sum
        - float(CFG.GMF_OBJ_E) * float(val_hf)
        - float(CFG.GMF_OBJ_F) * float(val_cb)
    )
    return float(obj)


def compute_tradeoff_score(curr: dict) -> Tuple[float, float, float]:
    if curr is None:
        return float("nan"), 0.0, 0.0
    gmf_obj = curr.get("gmf_obj", np.nan)
    if not np.isfinite(gmf_obj):
        gmf_obj = compute_gmf_obj(curr)
    score = float(gmf_obj) if (gmf_obj is not None and np.isfinite(gmf_obj)) else float("nan")
    edge = curr.get("metric_edge_width", curr.get("edge_width", np.nan))
    hf = curr.get("metric_hf_proxy", curr.get("hf_proxy", np.nan))
    edge_ref = curr.get("edge_width_ref", np.nan)
    hf_ref = curr.get("hf_proxy_ref", np.nan)
    edge_pen = 0.0
    hf_pen = 0.0
    edge_tol = float(getattr(CFG, "BEST_EDGEW_TOL", 0.10))
    hf_tol = float(getattr(CFG, "BEST_HF_TOL", 0.08))
    edge_w = float(getattr(CFG, "BEST_EDGEW_PENALTY", 5.0))
    hf_w = float(getattr(CFG, "BEST_HF_PENALTY", 5.0))
    if np.isfinite(edge) and np.isfinite(edge_ref) and (edge_ref > 1e-8):
        edge_lim = edge_ref * (1.0 + edge_tol)
        if edge > edge_lim:
            edge_pen = edge_w * float((edge - edge_lim) / max(edge_ref, 1e-6))
    if np.isfinite(hf) and np.isfinite(hf_ref) and (hf_ref > 1e-8):
        hf_lim = hf_ref * (1.0 - hf_tol)
        if hf < hf_lim:
            hf_pen = hf_w * float((hf_lim - hf) / max(hf_ref, 1e-6))
    if np.isfinite(score):
        score = score - edge_pen - hf_pen
    return float(score), float(edge_pen), float(hf_pen)


def compute_gmf_fitness(curr: dict, history: list):
    if curr is None:
        return None, {}

    def _finite(v):
        return (v is not None) and np.isfinite(v)

    step_std = curr.get("kpi_step_std")
    outlier = curr.get("kpi_outlier_rate")
    step_err = curr.get("kpi_step_mean_err")
    gain_p10 = curr.get("proxy_gain_p10")
    proxy_mean = curr.get("proxy_score_mean")
    if not all(_finite(v) for v in [step_std, outlier, step_err, gain_p10, proxy_mean]):
        return None, {}

    hist = list(history) + [curr]
    z_std = _zscore(step_std, hist, "kpi_step_std")
    z_out = _zscore(outlier, hist, "kpi_outlier_rate")
    z_err = _zscore(step_err, hist, "kpi_step_mean_err")
    z_gain = _zscore(gain_p10, hist, "proxy_gain_p10")
    z_proxy = _zscore(proxy_mean, hist, "proxy_score_mean")

    score = (
        -float(CFG.GMF_W_STEP_STD) * z_std
        -float(CFG.GMF_W_OUTLIER) * z_out
        -float(CFG.GMF_W_STEP_ERR) * z_err
        +float(CFG.GMF_W_GAIN_P10) * z_gain
        +float(CFG.GMF_W_PROXY_MEAN) * z_proxy
    )
    components = {
        "gmf_fitness": float(score),
        "gmf_z_step_std": float(z_std),
        "gmf_z_outlier": float(z_out),
        "gmf_z_step_mean_err": float(z_err),
        "gmf_z_gain_p10": float(z_gain),
        "gmf_z_proxy_mean": float(z_proxy),
    }
    return float(score), components


def is_better_gmf(curr: dict, best: dict, history: list) -> bool:
    if curr is None:
        return False
    curr_obj = curr.get("gmf_obj", np.nan)
    if not np.isfinite(curr_obj):
        curr_obj = compute_gmf_obj(curr)
    if curr_obj is not None and np.isfinite(curr_obj):
        if best is None:
            return True
        best_obj = best.get("gmf_obj", np.nan) if isinstance(best, dict) else np.nan
        if not np.isfinite(best_obj):
            best_obj = compute_gmf_obj(best)
        if best_obj is None or (not np.isfinite(best_obj)):
            return True
        return curr_obj > best_obj + 1e-6

    score_curr, _ = compute_gmf_fitness(curr, history)
    if score_curr is None:
        return False
    if best is None:
        return True
    score_best, _ = compute_gmf_fitness(best, history)
    if score_best is None:
        return True
    return score_curr > score_best + 1e-6


def is_better_tradeoff(curr: dict, best: Optional[dict]) -> bool:
    if curr is None:
        return False
    score_curr, _, _ = compute_tradeoff_score(curr)
    if not np.isfinite(score_curr):
        return False
    if best is None:
        return True
    score_best, _, _ = compute_tradeoff_score(best)
    if not np.isfinite(score_best):
        return True
    return score_curr > score_best + 1e-6


def _safe_csv_value(v, default: float = 0.0):
    if isinstance(v, str):
        return v
    if isinstance(v, (bool, np.bool_)):
        return int(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    try:
        val = float(v)
    except Exception:
        return default
    if not np.isfinite(val):
        return default
    return val


def _rankdata(arr: np.ndarray) -> np.ndarray:
    order = np.argsort(arr)
    ranks = np.empty_like(order, dtype=np.float64)
    n = len(arr)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        rank = 0.5 * (i + j)
        ranks[order[i:j + 1]] = rank
        i = j + 1
    return ranks


def _corr_pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2:
        return 0.0
    vx = x - np.mean(x)
    vy = y - np.mean(y)
    denom = float(np.sqrt(np.sum(vx * vx) * np.sum(vy * vy)))
    if denom < 1e-12:
        return 0.0
    return float(np.sum(vx * vy) / denom)


def _corr_spearman(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2:
        return 0.0
    rx = _rankdata(x)
    ry = _rankdata(y)
    return _corr_pearson(rx, ry)


def _series(history: list, key: str) -> np.ndarray:
    vals = [_safe_csv_value(d.get(key, 0.0)) for d in history if isinstance(d, dict)]
    return np.array(vals, dtype=np.float64)


def _attrib_top(history: list, factors: list, kpis: list):
    results = []
    for f_name, f_key in factors:
        x = _series(history, f_key)
        for k_name, k_key in kpis:
            y = _series(history, k_key)
            corr = _corr_spearman(x, y)
            results.append((corr, f_name, k_name))
    results.sort(key=lambda v: v[0], reverse=True)
    pos = results[:5]
    neg = sorted(results, key=lambda v: v[0])[:5]
    return pos, neg


def _format_corr_list(items: list) -> str:
    return ", ".join([f"{n}->{k}:{c:+.3f}" for (c, n, k) in items])


def log_attribution(epoch1: int, history: list, attrib_path: str):
    window = min(int(CFG.ATTRIB_WINDOW), len(history))
    if window < 2:
        return
    hist = history[-window:]
    kpis = [
        ("kpi_step_mean_err", "kpi_step_mean_err"),
        ("kpi_step_std", "kpi_step_std"),
        ("kpi_outlier_rate", "kpi_outlier_rate"),
    ]
    prefixed_factors = [
        ("edge", "edge"),
        ("edge_profile", "edge_profile"),
        ("edge_ori", "edge_ori"),
        ("edge_chamfer_raw", "edge_chamfer_raw"),
        ("edge_chamfer_w", "edge_chamfer_w"),
        ("hf_ratio", "hf_ratio"),
        ("checkerboard", "cb"),
        ("fft", "fft"),
    ]
    shared_factors = [
        ("phys_alpha", "physics_alpha"),
        ("phys_reg", "physics_reg"),
        ("weak_beta", "weak_psf_beta"),
        ("weak_beta_scale", "weak_psf_beta_scale"),
        ("weak_entropy", "weak_psf_entropy"),
        ("weak_top1", "weak_psf_top1_ratio"),
        ("weak_bypass", "weak_psf_bypass"),
    ]
    val_factors = [(name, f"val_{key}") for name, key in prefixed_factors] + shared_factors
    train_factors = [(name, f"train_{key}") for name, key in prefixed_factors] + shared_factors

    pos_val, neg_val = _attrib_top(hist, val_factors, kpis)
    pos_tr, neg_tr = _attrib_top(hist, train_factors, kpis)
    line_val = f"[ATTRIB][E{epoch1:03d}] win={window} VAL +: {_format_corr_list(pos_val)} | -: {_format_corr_list(neg_val)}"
    line_tr = f"[ATTRIB][E{epoch1:03d}] win={window} TRN->VAL +: {_format_corr_list(pos_tr)} | -: {_format_corr_list(neg_tr)}"
    print(line_val)
    print(line_tr)

    with open(attrib_path, "a", encoding="utf-8") as f:
        f.write(line_val + "\n")
        f.write(line_tr + "\n")


def init_attrib_log(attrib_path: str):
    if os.path.exists(attrib_path):
        return
    expect_dx = CFG.GMF_EXPECT_DX_PX
    expect_dy = CFG.GMF_EXPECT_DY_PX
    expected_step_px = 0.0
    expected_enable = 0
    if (expect_dx is not None) and (expect_dy is not None) and np.isfinite(expect_dx) and np.isfinite(expect_dy):
        expected_step_px = float(np.sqrt(float(expect_dx) ** 2 + float(expect_dy) ** 2))
        expected_enable = 1
    outlier_t = float(CFG.GMF_OUTLIER_T)
    if expected_enable and float(CFG.GMF_OUTLIER_T_REL) > 0.0:
        outlier_t = max(outlier_t, expected_step_px * float(CFG.GMF_OUTLIER_T_REL))
    with open(attrib_path, "w", encoding="utf-8") as f:
        f.write("# Attribution correlation log\n")
        f.write(f"# expect_dx_px={expect_dx} expect_dy_px={expect_dy} expected_step_px={expected_step_px:.6f} "
                f"expected_enable={expected_enable}\n")
        f.write(f"# outlier_t={outlier_t:.6f} outlier_t_rel={float(CFG.GMF_OUTLIER_T_REL):.6f}\n")
# ============================================================
# Plotting / debug figures
# ============================================================
def plot_loss_curves(epoch_summaries: list, out_main_path: str, out_phase_path: str, title: str = "Loss Curves"):
    if len(epoch_summaries) == 0:
        return

    xs = np.arange(1, len(epoch_summaries) + 1)

    def arr(key):
        return np.array([d.get(key, np.nan) for d in epoch_summaries], dtype=np.float64)

    tr_total = arr("total")
    tr_rec   = arr("rec")
    tr_fft   = arr("fft")
    tr_fft_shape = arr("fft_shape")
    tr_edge  = arr("edge")
    tr_edge_profile = arr("edge_profile")
    tr_edge_ori = arr("edge_ori")
    tr_edge_chamfer = arr("edge_chamfer")
    tr_ctr   = arr("contrast")
    tr_cb    = arr("cb")
    tr_hf    = arr("hf_ratio")
    tr_ssim  = arr("ssim")

    v_total = arr("val_total")
    v_rec   = arr("val_rec")
    v_edge  = arr("val_edge")
    v_edge_profile = arr("val_edge_profile")
    v_ssim = arr("val_ssim")
    v_hf = arr("val_hf_ratio")
    v_cb = arr("val_cb")

    fig, ax1 = plt.subplots()
    ax1.plot(xs, tr_total, linestyle="-", label="Train Total")
    ax1.plot(xs, tr_rec,   linestyle="-", label="Train Rec")
    ax1.plot(xs, tr_fft,   linestyle="-", label="Train FFT")
    ax1.plot(xs, tr_fft_shape, linestyle="-", label="Train FFTShape")
    ax1.plot(xs, tr_edge,  linestyle="-", label="Train Edge")
    if np.isfinite(tr_edge_profile).any():
        ax1.plot(xs, tr_edge_profile, linestyle="-", label="Train EdgeProfile")
    if np.isfinite(tr_edge_ori).any():
        ax1.plot(xs, tr_edge_ori, linestyle="-", label="Train EdgeOri")
    if np.isfinite(tr_edge_chamfer).any():
        ax1.plot(xs, tr_edge_chamfer, linestyle="-", label="Train EdgeChamfer")
    ax1.plot(xs, tr_ctr,   linestyle="-", label="Train Contrast")
    ax1.plot(xs, tr_cb,    linestyle="-", label="Train Checkerboard")
    if np.isfinite(tr_ssim).any():
        ax1.plot(xs, tr_ssim, linestyle="-", label="Train SSIM")

    if np.isfinite(v_total).any():
        ax1.plot(xs, v_total, linestyle="--", label="Val Total")
    if np.isfinite(v_rec).any():
        ax1.plot(xs, v_rec,   linestyle="--", label="Val Rec")
    if np.isfinite(v_edge).any():
        ax1.plot(xs, v_edge,  linestyle="--", label="Val Edge")
    if np.isfinite(v_edge_profile).any():
        ax1.plot(xs, v_edge_profile, linestyle="--", label="Val EdgeProfile")
    if np.isfinite(v_ssim).any():
        ax1.plot(xs, v_ssim,  linestyle="--", label="Val SSIM")

    ax1.grid(True)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title(title)

    ax1.legend(loc="best")

    fig.savefig(out_main_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    fig_p = plt.figure()
    if np.isfinite(tr_edge).any():
        plt.plot(xs, tr_edge, linestyle="-", label="Train Edge")
    if np.isfinite(tr_edge_profile).any():
        plt.plot(xs, tr_edge_profile, linestyle="-", label="Train EdgeProfile")
    if np.isfinite(tr_edge_ori).any():
        plt.plot(xs, tr_edge_ori, linestyle="-", label="Train EdgeOri")
    if np.isfinite(tr_edge_chamfer).any():
        plt.plot(xs, tr_edge_chamfer, linestyle="-", label="Train EdgeChamfer")
    if np.isfinite(v_edge).any():
        plt.plot(xs, v_edge, linestyle="--", label="Val Edge")
    if np.isfinite(v_edge_profile).any():
        plt.plot(xs, v_edge_profile, linestyle="--", label="Val EdgeProfile")
    plt.grid(True)
    plt.xlabel("Epoch")
    plt.ylabel("Edge Loss")
    plt.title(f"{title} (Edge Alignment)")
    plt.legend()
    fig_p.savefig(out_phase_path, dpi=150, bbox_inches="tight")
    plt.close(fig_p)

    out_artifact = out_main_path.replace("_loss_curve_main_", "_loss_curve_artifact_")
    fig_a = plt.figure()
    if np.isfinite(tr_cb).any():
        plt.plot(xs, tr_cb, linestyle="-", label="Train CB")
    if np.isfinite(tr_hf).any():
        plt.plot(xs, tr_hf, linestyle="-", label="Train HF Ratio")
    if np.isfinite(v_cb).any():
        plt.plot(xs, v_cb, linestyle="--", label="Val CB")
    if np.isfinite(v_hf).any():
        plt.plot(xs, v_hf, linestyle="--", label="Val HF Ratio")
    plt.grid(True)
    plt.xlabel("Epoch")
    plt.ylabel("Score")
    plt.title(f"{title} (Artifacts)")
    plt.legend()
    fig_a.savefig(out_artifact, dpi=150, bbox_inches="tight")
    plt.close(fig_a)


def plot_gmf_curves(epoch_summaries: list, out_path: str, title: str = "GMF Proxy Metrics"):
    if len(epoch_summaries) == 0:
        return

    xs = np.arange(1, len(epoch_summaries) + 1)

    def arr(key):
        return np.array([d.get(key, np.nan) for d in epoch_summaries], dtype=np.float64)

    score_mean = arr("proxy_score_mean")
    score_p10 = arr("proxy_score_p10")
    pass_rate = arr("proxy_score_pass_rate")
    pos_std_sum = arr("proxy_pos_step_std_sum")
    step_err = arr("proxy_step_err")
    scale_dev = arr("proxy_scale_dev") if CFG.PROXY_SCALE_ENABLE else None
    posx_std = arr("proxy_posx_adj_std")
    posy_std = arr("proxy_posy_adj_std")
    scale_std = arr("proxy_scale_std") if CFG.PROXY_SCALE_ENABLE else None

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True)
    ax1.plot(xs, pass_rate, linestyle="-", label="Proxy Pass Rate (%)")
    ax1.plot(xs, score_p10, linestyle="-", label="Proxy Score P10")
    ax1.plot(xs, score_mean, linestyle="-", label="Proxy Score Mean")
    ax1.set_ylabel("Score")
    ax1.grid(True)
    ax1.legend(loc="best")

    ax2.plot(xs, pos_std_sum, linestyle="-", label="Pos Std Sum")
    ax2.plot(xs, step_err, linestyle="-", label="Step Err")
    if CFG.PROXY_SCALE_ENABLE and scale_dev is not None:
        ax2.plot(xs, scale_dev, linestyle="-", label="Scale Dev")
    ax2.plot(xs, posx_std, linestyle="-", label="PosX Adj Std")
    ax2.plot(xs, posy_std, linestyle="-", label="PosY Adj Std")
    if CFG.PROXY_SCALE_ENABLE and scale_std is not None:
        ax2.plot(xs, scale_std, linestyle="-", label="Scale Std")
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Std")
    ax2.grid(True)
    ax2.legend(loc="best")

    fig.suptitle(title)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


@torch.no_grad()
# ============================================================
# Training
# ============================================================
def train_one_epoch(model, loader, optimizer, scaler, huber, ssim,
                    epoch_idx: int, csv_writer, csv_file, w_cb_mult: float, w_hf_mult: float,
                    geom_mult: float, edge_ori_mult: float, edge_chamfer_mult: float,
                    edge_profile_mult: float, edge_profile_gmf_mult: float,
                    consist_factor: float, cap_base_factor: float, cap_spike_factor: float,
                    thicken_guard_mult: float, eq_disable_intensity: bool,
                    eq_intensity_weight_effective: float, eq_factor_epoch: float,
                    detail_rescue_mult: float = 1.0,
                    eq_shift_override: Optional[dict] = None,
                    phys_forward_runtime: bool = False,
                    w_edge_local_lap_epoch: float = 0.0,
                    enable_edge_local_lap: bool = False,
                    ema_model: Optional[nn.Module] = None,
                    ema_decay: float = 0.0):
    model.train()
    if not torch.is_grad_enabled():
        torch.set_grad_enabled(True)
    use_amp = bool(CFG.use_amp)
    acc_steps = max(1, int(CFG.acc_steps))
    if scaler is None:
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp and torch.cuda.is_available())
    optimizer.zero_grad(set_to_none=True)

    running = {
        "total": 0.0, "rec": 0.0, "gradmag": 0.0, "edge_ori": 0.0, "eq_total": 0.0,
        "loss_stat": 0.0, "loss_band": 0.0, "loss_hf_lap": 0.0, "loss_phys": 0.0,
        "loss_edgeLocalLap": 0.0, "loss_detail": 0.0,
        "pred_mean_mask": 0.0, "pred_std_mask": 0.0,
        "eq_pix": 0.0, "eq_edge": 0.0, "eq_grad": 0.0,
        "eq_edgew_mean": 0.0, "eq_edgew_p95": 0.0,
        "fft": 0.0, "fft_shape": 0.0, "ffl": 0.0, "percep": 0.0, "grad_profile": 0.0,
        "mean": 0.0, "ssim_struct": 0.0, "edge": 0.0, "edge_profile": 0.0,
        "edge_profile_p99": 0.0, "edge_profile_n": 0.0,
        "edge_chamfer": 0.0, "edge_chamfer_w": 0.0,
        "contrast": 0.0, "cb": 0.0, "phase": 0.0, "smooth": 0.0, "consistency": 0.0,
        "hf_ratio": 0.0, "hf_loss": 0.0, "ssim": 0.0,
        "sr_mean": 0.0, "sr_std": 0.0, "sr_min": 0.0, "sr_max": 0.0, "sr_sat": 0.0,
    }
    band_e_pred_sum = 0.0
    band_e_gt_sum = 0.0
    band_updates = 0
    n_samples = 0
    last_weak = {"beta": np.nan, "entropy": np.nan, "top1_ratio": np.nan, "bypass": True}

    epoch1 = epoch_idx + 1
    (
        w_rec, _w_eq, _w_edge, w_edge_profile, _w_edge_ori_sched, w_edge_chamfer,
        w_ssim, w_fft, w_fft_shape, w_phase_ce, w_phase_psr, w_contrast, w_lap, w_sat, w_cb
    ) = get_epoch_weights(epoch1)
    w_gradmag = float(CFG.W_GRADMAG)
    w_edge_ori = float(CFG.W_EDGE_ORI_SIMPLE)
    w_stat = float(CFG.W_STAT)
    w_band = float(CFG.W_BAND)
    w_hf_lap = float(CFG.W_HF_LAP)
    w_phys_epoch = get_phys_weight(epoch1) if bool(phys_forward_runtime) else 0.0
    eq_factor = float(eq_factor_epoch)
    eq_prob = float(getattr(CFG, "EQ_PROB", 1.0))
    w_detail_base = float(getattr(CFG, "W_DETAIL_BASE", 0.0))

    guard_mult = float(thicken_guard_mult)

    tqdm_mininterval = float(CFG.FAST_TQDM_MININTERVAL) if CFG.FAST_IO_MODE else 0.1
    pbar = tqdm(enumerate(loader), total=len(loader), ncols=110, leave=False, mininterval=tqdm_mininterval)
    t0 = time.time()
    flush_every_n = max(1, int(CFG.FAST_CSV_FLUSH_EVERY_N)) if CFG.FAST_IO_MODE else 0
    batch_log_every = max(1, int(getattr(CFG, "BATCH_LOG_EVERY_N", 1)))
    batch_log_count = 0
    eq_shift_range_last = "na"
    eq_shift_r_min_last = float("nan")
    eq_shift_r_max_last = float("nan")

    for b, batch in pbar:
        src, lbl = _unpack_batch(batch)
        src = src.to(CFG.DEVICE, non_blocking=True)
        lbl = lbl.to(CFG.DEVICE, non_blocking=True)
        bs = src.size(0)

        with torch.enable_grad():
            with torch.cuda.amp.autocast(enabled=use_amp):
                pred = model(src)
            if not pred.requires_grad:
                raise RuntimeError("[FATAL] pred.requires_grad=False; training is running under no-grad context.")

            with torch.cuda.amp.autocast(enabled=False):
                pred01 = pred.float().clamp(0.0, 1.0)
                lbl01 = lbl.float().clamp(0.0, 1.0)

                with torch.no_grad():
                    sr_mean = pred01.mean()
                    sr_std = pred01.std(unbiased=False)
                    sr_min = pred01.min()
                    sr_max = pred01.max()
                    sr_sat = (pred01 < 0.01).float().mean() + (pred01 > 0.99).float().mean()

                mask_valid = make_valid_mask(pred01)
                src01 = src.float().clamp(0.0, 1.0)
                l_pix, ssim_v, l_ssim_raw = reconstruction_terms(pred01, lbl01, huber, ssim)
                l_rec = l_pix + float(w_ssim) * l_ssim_raw
                l_gradmag = gradient_magnitude_loss(pred01, lbl01, mask_valid)
                l_edge_ori = edge_orientation_loss(pred01, lbl01, mask_valid) if w_edge_ori > 0.0 else pred01.new_tensor(0.0)
                pred_mean_mask, pred_std_mask = masked_mean_std(pred01, mask_valid)
                gt_mean_mask, gt_std_mask = masked_mean_std(lbl01, mask_valid)
                l_stat = torch.abs(pred_mean_mask - gt_mean_mask) + torch.abs(pred_std_mask - gt_std_mask)
                l_ssim = ssim_v
                hf = hf_ratio(pred01, mask_valid)
                l_hf_lap = laplacian_hf_loss(pred01, lbl01, mask_valid)
                l_edge_local_lap = pred01.new_tensor(0.0)
                if bool(enable_edge_local_lap) and (float(w_edge_local_lap_epoch) > 0.0):
                    edge_mask = _edge_mask_from_gt(
                        lbl01,
                        thr=float(getattr(CFG, "EDGELOCAL_LAP_THR", 0.06)),
                        dilate=int(getattr(CFG, "EDGELOCAL_LAP_DILATE", 3)),
                    )
                    if mask_valid is not None:
                        edge_mask = edge_mask * mask_valid
                    lap_pred = _laplacian(pred01)
                    lap_gt = _laplacian(lbl01)
                    l_edge_local_lap = _masked_l1(lap_pred, lap_gt, edge_mask)

                l_detail = pred01.new_tensor(0.0)
                if (w_detail_base > 0.0) and (epoch1 >= int(getattr(CFG, "DETAIL_START_EPOCH", 0))):
                    l_detail = detail_recovery_loss(pred01, lbl01, mask_valid=mask_valid)

                band_n = max(1, int(getattr(CFG, "BAND_LOSS_EVERY_N_BATCH", 2)))
                do_band = ((b % band_n) == 0)
                if do_band:
                    band_e_pred = band_energy_proxy(pred01, mask_valid)
                    band_e_gt = band_energy_proxy(lbl01, mask_valid).detach()
                    l_band = torch.abs(
                        torch.log(band_e_pred + float(CFG.BAND_ENERGY_EPS))
                        - torch.log(band_e_gt + float(CFG.BAND_ENERGY_EPS))
                    )
                else:
                    band_e_pred = pred01.new_tensor(float("nan"))
                    band_e_gt = pred01.new_tensor(float("nan"))
                    l_band = pred01.new_tensor(0.0)

                l_phys = pred01.new_tensor(0.0)
                if w_phys_epoch > 0.0:
                    phys_blur = _apply_psf_forward_blur(model, pred01)
                    if phys_blur is not None:
                        l_phys_map = F.smooth_l1_loss(phys_blur, src01, reduction="none")
                        l_phys = _masked_mean(l_phys_map, mask_valid)

                do_eq = (float(eq_factor) > 0.0) and (float(eq_prob) > 0.0) and (random.random() < float(eq_prob))
                if do_eq:
                    l_eq_total, l_eq_pix, l_eq_edge, l_eq_grad, eq_shift_range_last, eq_w_mean, eq_w_p95, eq_shift_r_min_last, eq_shift_r_max_last = compute_shift_eq_losses(
                        model=model,
                        src=src,
                        pred01=pred01,
                        eq_factor=float(eq_factor),
                        epoch1=epoch1,
                        use_amp=use_amp,
                        disable_intensity=bool(eq_disable_intensity),
                        eq_intensity_weight_effective=float(eq_intensity_weight_effective),
                        eq_shift_override=eq_shift_override,
                    )
                else:
                    z = pred01.new_tensor(0.0)
                    l_eq_total = z
                    l_eq_pix = z
                    l_eq_edge = z
                    l_eq_grad = z
                    eq_shift_range_last = "skip"
                    eq_w_mean = float("nan")
                    eq_w_p95 = float("nan")
                    eq_shift_r_min_last = float("nan")
                    eq_shift_r_max_last = float("nan")

                loss_raw = (
                    float(w_rec) * l_rec
                    + float(w_gradmag) * l_gradmag
                    + float(w_edge_ori) * l_edge_ori
                    + l_eq_total
                    + float(w_stat) * l_stat
                    + float(w_band) * l_band
                    + float(w_hf_lap) * l_hf_lap
                    + float(w_phys_epoch) * l_phys
                    + float(w_edge_local_lap_epoch) * l_edge_local_lap
                    + float(w_detail_base) * float(detail_rescue_mult) * l_detail
                )

                last_weak = get_weak_psf_stats(model)

        if CFG.SKIP_ON_NAN and (not torch.isfinite(loss_raw)):
            pbar.set_postfix_str("loss=NaN (skip)")
            optimizer.zero_grad(set_to_none=True)
            continue

        loss = loss_raw / float(acc_steps)
        scaler.scale(loss).backward()
        if ((b + 1) % acc_steps == 0) or ((b + 1) == len(loader)):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), CFG.GRAD_CLIP_NORM)
            scaler.step(optimizer)
            scaler.update()
            if (ema_model is not None) and (epoch1 >= int(getattr(CFG, "EMA_START_EPOCH", 1))):
                if ((b + 1) % max(1, int(getattr(CFG, "EMA_UPDATE_EVERY", 1)))) == 0:
                    update_ema_model(ema_model, model, float(ema_decay))
            optimizer.zero_grad(set_to_none=True)

        log_this_batch = (((b + 1) % batch_log_every) == 0) or ((b + 1) == len(loader))
        if (csv_writer is not None) and log_this_batch:
            row = [
                epoch1, b,
                float(loss_raw.item()),
                float(l_rec.item()),
                float(l_gradmag.item()),
                float(l_edge_ori.item()),
                float(l_eq_total.item()),
                float(l_eq_grad.item()),
                float(l_stat.item()),
                float(l_band.item()),
                float(l_hf_lap.item()),
                float(l_phys.item()),
                float(l_edge_local_lap.item()),
                float(l_detail.item()),
                float(w_edge_local_lap_epoch),
                float(pred_mean_mask.item()),
                float(pred_std_mask.item()),
                float(band_e_pred.item()) if torch.isfinite(band_e_pred) else np.nan,
                float(band_e_gt.item()) if torch.isfinite(band_e_gt) else np.nan,
                float(w_phys_epoch),
                float(eq_shift_r_min_last),
                float(eq_shift_r_max_last),
                float(eq_factor),
                float(last_weak.get("beta", 0.0)),
                float(last_weak.get("beta_scale", 0.0)),
                float(last_weak.get("entropy", 0.0)),
                float(last_weak.get("top1_ratio", 0.0)),
                int(bool(last_weak.get("bypass", True))),
                optimizer.param_groups[0]["lr"],
            ]
            csv_writer.writerow([_safe_csv_value(v) for v in row])
            batch_log_count += 1
            if (csv_file is not None) and (flush_every_n > 0) and (batch_log_count % flush_every_n == 0):
                csv_file.flush()

        with torch.no_grad():
            running["total"] += float(loss_raw.item()) * bs
            running["rec"] += float(l_rec.item()) * bs
            running["gradmag"] += float(l_gradmag.item()) * bs
            running["edge_ori"] += float(l_edge_ori.item()) * bs
            running["loss_stat"] += float(l_stat.item()) * bs
            running["loss_band"] += float(l_band.item()) * bs
            running["loss_hf_lap"] += float(l_hf_lap.item()) * bs
            running["loss_phys"] += float(l_phys.item()) * bs
            running["loss_edgeLocalLap"] += float(l_edge_local_lap.item()) * bs
            running["loss_detail"] += float(l_detail.item()) * bs
            running["pred_mean_mask"] += float(pred_mean_mask.item()) * bs
            running["pred_std_mask"] += float(pred_std_mask.item()) * bs
            running["eq_total"] += float(l_eq_total.item()) * bs
            running["eq_pix"] += float(l_eq_pix.item()) * bs
            running["eq_edge"] += float(l_eq_edge.item()) * bs
            running["eq_grad"] += float(l_eq_grad.item()) * bs
            if np.isfinite(eq_w_mean):
                running["eq_edgew_mean"] += float(eq_w_mean) * bs
            if np.isfinite(eq_w_p95):
                running["eq_edgew_p95"] += float(eq_w_p95) * bs
            running["hf_ratio"] += float(hf.item()) * bs
            running["ssim"] += float(l_ssim.item()) * bs
            running["sr_mean"] += float(sr_mean.item()) * bs
            running["sr_std"] += float(sr_std.item()) * bs
            running["sr_min"] += float(sr_min.item()) * bs
            running["sr_max"] += float(sr_max.item()) * bs
            running["sr_sat"] += float(sr_sat.item()) * bs
            if do_band and torch.isfinite(band_e_pred) and torch.isfinite(band_e_gt):
                band_e_pred_sum += float(band_e_pred.item())
                band_e_gt_sum += float(band_e_gt.item())
                band_updates += 1
        n_samples += bs

        if (b % CFG.PRINT_EVERY) == 0:
            pbar.set_postfix({
                "L": f"{float(loss_raw.item()):.4f}",
                "Rec": f"{float(l_rec.item()):.4f}",
                "Grad": f"{float(l_gradmag.item()):.4f}",
                "Ori": f"{float(l_edge_ori.item()):.4f}",
                "Eq": f"{float(l_eq_total.item()):.4f}",
                "Stat": f"{float(l_stat.item()):.4f}",
            })

    dt = time.time() - t0
    if n_samples == 0:
        out_nan = {k: np.nan for k in running}
        out_nan["sec"] = dt
        out_nan["eq_factor"] = float(eq_factor)
        out_nan["eq_couple"] = 1.0
        out_nan["sched_consist_factor"] = 1.0
        out_nan["sched_cap_factor"] = 1.0
        out_nan["guard_thicken_mult"] = 1.0
        out_nan["consistency_factor"] = 1.0
        out_nan["eq_shift_mode"] = "eq"
        out_nan["eq_shift_range"] = str(eq_shift_range_last)
        out_nan["eq_shift_r_min"] = float(eq_shift_r_min_last)
        out_nan["eq_shift_r_max"] = float(eq_shift_r_max_last)
        out_nan["eq_int"] = np.nan
        out_nan["eq_disable_intensity"] = 1
        out_nan["eq_intensity_mode"] = "off"
        out_nan["eq_intensity_weight_effective"] = 0.0
        out_nan["edge_profile_p99"] = np.nan
        out_nan["edge_profile_n"] = 0
        out_nan["bandE_pred"] = np.nan
        out_nan["bandE_gt"] = np.nan
        out_nan["phys_weight"] = float(w_phys_epoch)
        out_nan["w_edgeLocalLap"] = float(w_edge_local_lap_epoch)
        out_nan["w_detail_base"] = float(w_detail_base)
        out_nan["detail_rescue_mult"] = float(detail_rescue_mult)
        return out_nan

    out = {k: running[k] / max(1, n_samples) for k in running}
    out["sec"] = dt
    out["eq_factor"] = float(eq_factor)
    out["eq_couple"] = 1.0
    out["sched_consist_factor"] = 1.0
    out["sched_cap_factor"] = 1.0
    out["guard_thicken_mult"] = 1.0
    out["consistency_factor"] = 1.0
    out["eq_shift_mode"] = "eq"
    out["eq_shift_range"] = str(eq_shift_range_last)
    out["eq_shift_r_min"] = float(eq_shift_r_min_last)
    out["eq_shift_r_max"] = float(eq_shift_r_max_last)
    out["eq_int"] = out["eq_pix"]
    out["eqgeom"] = out["eq_total"]
    out["eq_disable_intensity"] = 1
    out["eq_intensity_mode"] = "off"
    out["eq_intensity_weight_effective"] = 0.0
    out["edge_profile_n"] = float(running.get("edge_profile_n", 0.0))
    out["bandE_pred"] = float(band_e_pred_sum / max(1, band_updates)) if band_updates > 0 else np.nan
    out["bandE_gt"] = float(band_e_gt_sum / max(1, band_updates)) if band_updates > 0 else np.nan
    out["phys_weight"] = float(w_phys_epoch)
    out["w_edgeLocalLap"] = float(w_edge_local_lap_epoch)
    out["w_detail_base"] = float(w_detail_base)
    out["detail_rescue_mult"] = float(detail_rescue_mult)
    out["weak_psf_beta"] = float(last_weak.get("beta", 0.0))
    out["weak_psf_beta_scale"] = float(last_weak.get("beta_scale", 0.0))
    out["weak_psf_beta_eff"] = float(last_weak.get("beta_eff", 0.0))
    out["weak_psf_entropy"] = float(last_weak.get("entropy", 0.0))
    out["weak_psf_top1_ratio"] = float(last_weak.get("top1_ratio", 0.0))
    out["weak_psf_bypass"] = bool(last_weak.get("bypass", True))
    return out


# ============================================================
# Validation + monitor
# ============================================================
@torch.no_grad()
def validate_one_epoch(model, loader, huber, ssim, epoch_idx: int):
    model.eval()
    epoch1 = epoch_idx + 1
    w_rec, _, _, _, _, _, w_ssim, *_rest = get_epoch_weights(epoch1)
    w_gradmag = float(CFG.W_GRADMAG)
    w_edge_ori = float(CFG.W_EDGE_ORI_SIMPLE)

    running = {
        "total": 0.0, "rec": 0.0, "gradmag": 0.0, "edge_ori": 0.0,
        "edge": 0.0, "edge_profile": 0.0,
        "edge_chamfer_raw": 0.0, "edge_chamfer_w": 0.0,
        "mse": 0.0, "ssim": 0.0, "fft": 0.0, "fft_shape": 0.0,
        "cb": 0.0, "hf_ratio": 0.0,
    }
    n_samples = 0

    for batch in loader:
        src, lbl = _unpack_batch(batch)
        src = src.to(CFG.DEVICE, non_blocking=True)
        lbl = lbl.to(CFG.DEVICE, non_blocking=True)
        bs = src.size(0)

        with torch.cuda.amp.autocast(enabled=CFG.use_amp):
            pred = model(src)

        pred01 = pred.float().clamp(0.0, 1.0)
        lbl01 = lbl.float().clamp(0.0, 1.0)
        mask_valid = make_valid_mask(pred01)

        l_pix, ssim_v, l_ssim_raw = reconstruction_terms(pred01, lbl01, huber, ssim)
        l_rec = l_pix + float(w_ssim) * l_ssim_raw
        l_gradmag = gradient_magnitude_loss(pred01, lbl01, mask_valid)
        l_edge_ori = edge_orientation_loss(pred01, lbl01, mask_valid) if w_edge_ori > 0.0 else pred01.new_tensor(0.0)
        l_total = float(w_rec) * l_rec + float(w_gradmag) * l_gradmag + float(w_edge_ori) * l_edge_ori

        mse = torch.mean((pred01 - lbl01) ** 2)
        hf = hf_ratio(pred01, mask_valid)

        if not torch.isfinite(l_total):
            continue

        running["total"] += float(l_total.item()) * bs
        running["rec"] += float(l_rec.item()) * bs
        running["gradmag"] += float(l_gradmag.item()) * bs
        running["edge_ori"] += float(l_edge_ori.item()) * bs
        running["edge"] += float(l_gradmag.item()) * bs
        running["edge_profile"] += 0.0
        running["mse"] += float(mse.item()) * bs
        running["ssim"] += float(ssim_v.item()) * bs
        running["hf_ratio"] += float(hf.item()) * bs
        n_samples += bs

    if n_samples == 0:
        return {
            "total": np.nan, "rec": np.nan, "gradmag": np.nan, "edge": np.nan, "edge_profile": np.nan,
            "edge_ori": np.nan, "edge_chamfer_raw": 0.0, "edge_chamfer_w": 0.0,
            "psnr": np.nan, "ssim": np.nan, "fft": 0.0, "fft_shape": np.nan,
            "cb": np.nan, "hf_ratio": np.nan,
        }

    out = {k: running[k] / n_samples for k in running}
    psnr = 10.0 * np.log10(1.0 / (out["mse"] + 1e-12))
    return {
        "total": out["total"], "rec": out["rec"], "gradmag": out["gradmag"],
        "edge": out["edge"], "edge_profile": out["edge_profile"],
        "edge_ori": out["edge_ori"], "edge_chamfer_raw": out["edge_chamfer_raw"], "edge_chamfer_w": out["edge_chamfer_w"],
        "psnr": psnr, "ssim": out["ssim"], "fft": out["fft"], "fft_shape": out["fft_shape"],
        "cb": out["cb"], "hf_ratio": out["hf_ratio"],
    }


def _find_crossing_left(profile_1d: torch.Tensor, peak_idx: int, thr: float) -> Optional[float]:
    for i in range(int(peak_idx), 0, -1):
        v0 = float(profile_1d[i - 1].item())
        v1 = float(profile_1d[i].item())
        if (v0 - thr) * (v1 - thr) > 0.0:
            continue
        if abs(v1 - v0) < 1e-8:
            return float(i - 1)
        t = (thr - v0) / (v1 - v0)
        t = max(0.0, min(1.0, float(t)))
        return float(i - 1) + t
    return None


def _find_crossing_right(profile_1d: torch.Tensor, peak_idx: int, thr: float) -> Optional[float]:
    n = int(profile_1d.numel())
    for i in range(int(peak_idx), n - 1):
        v0 = float(profile_1d[i].item())
        v1 = float(profile_1d[i + 1].item())
        if (v0 - thr) * (v1 - thr) > 0.0:
            continue
        if abs(v1 - v0) < 1e-8:
            return float(i)
        t = (thr - v0) / (v1 - v0)
        t = max(0.0, min(1.0, float(t)))
        return float(i) + t
    return None


def _profile_w20_80(profile_1d: torch.Tensor) -> Optional[float]:
    if profile_1d.numel() < 5:
        return None
    peak_v, peak_i_t = torch.max(profile_1d, dim=0)
    peak = float(peak_v.item())
    if peak <= 1e-8:
        return None
    peak_i = int(peak_i_t.item())
    thr20 = peak * 0.20
    thr80 = peak * 0.80
    l20 = _find_crossing_left(profile_1d, peak_i, thr20)
    r20 = _find_crossing_right(profile_1d, peak_i, thr20)
    l80 = _find_crossing_left(profile_1d, peak_i, thr80)
    r80 = _find_crossing_right(profile_1d, peak_i, thr80)
    if (l20 is None) or (r20 is None) or (l80 is None) or (r80 is None):
        return None
    w20 = max(0.0, float(r20 - l20))
    w80 = max(0.0, float(r80 - l80))
    return max(0.0, w20 - w80)


@torch.no_grad()
def compute_edge_width_metric(pred01_t: torch.Tensor, mask_valid: torch.Tensor = None) -> float:
    if pred01_t.ndim != 4 or pred01_t.size(0) <= 0:
        return float("nan")
    if mask_valid is None:
        mask_valid = make_valid_mask(pred01_t)
    mag = sobel_magnitude(pred01_t).detach()
    m = mag[0, 0]
    mask = (mask_valid[0, 0] > 0.5).clone()
    h, w = int(m.shape[0]), int(m.shape[1])

    profile_len = max(5, int(CFG.EDGE_WIDTH_PROFILE_LEN))
    if profile_len % 2 == 0:
        profile_len += 1
    r = profile_len // 2
    if (h <= 2 * r) or (w <= 2 * r):
        return float("nan")

    mask[:r, :] = False
    mask[-r:, :] = False
    mask[:, :r] = False
    mask[:, -r:] = False

    vals = m[mask]
    if vals.numel() <= 0:
        return float("nan")
    coords = torch.nonzero(mask, as_tuple=False)
    k = min(int(CFG.EDGE_WIDTH_TOPK), int(vals.numel()))
    if k <= 0:
        return float("nan")
    _, top_idx = torch.topk(vals, k=k, largest=True, sorted=False)
    pts = coords[top_idx]

    widths = []
    for p in pts:
        y = int(p[0].item())
        x = int(p[1].item())
        prof = m[y, x - r:x + r + 1]
        w20_80 = _profile_w20_80(prof)
        if w20_80 is not None and np.isfinite(w20_80):
            widths.append(float(w20_80))
    if len(widths) == 0:
        return float("nan")
    return float(np.median(np.asarray(widths, dtype=np.float64)))


def _read_monitor_meta_hw(meta_path: str) -> Tuple[Optional[int], Optional[int]]:
    if not os.path.exists(meta_path):
        return None, None
    h = w = None
    with open(meta_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("orig_hw="):
                hw = line.strip().split("=", 1)[1]
                h, w = [int(x) for x in hw.split(",")]
                break
    return h, w


@torch.no_grad()
def compute_monitor_reference(model: Optional[nn.Module], monitor_src: Optional[torch.Tensor]) -> dict:
    if monitor_src is None:
        return {
            "edge_width_ref": float("nan"),
            "hf_proxy_ref": float("nan"),
            "cb_ref": float("nan"),
        }
    if model is None:
        pred01_t = monitor_src.float().clamp(0.0, 1.0)
    else:
        model.eval()
        pred = model(monitor_src)
        pred01_t = pred.float().clamp(0.0, 1.0)
    meta_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_monitor_meta.txt")
    h, w = _read_monitor_meta_hw(meta_path)
    if (h is not None) and (w is not None):
        pred01_t = pred01_t[..., :h, :w]
    mask_valid = make_valid_mask(pred01_t)
    edge_width_val = float(compute_edge_width_metric(pred01_t, mask_valid))
    hf_proxy_val = float(hf_ratio(pred01_t, mask_valid).item())
    cb_energy = float(checkerboard_energy(pred01_t).item())
    return {
        "edge_width_ref": edge_width_val,
        "hf_proxy_ref": hf_proxy_val,
        "cb_ref": cb_energy,
    }


def load_or_create_monitor_ref(model: Optional[nn.Module], monitor_src: Optional[torch.Tensor]) -> dict:
    ref_name = str(getattr(CFG, "MONITOR_REF_FILENAME", "monitor_ref.json"))
    ref_path = os.path.join(PROGRESS_DIR, ref_name)
    if os.path.exists(ref_path):
        try:
            with open(ref_path, "r", encoding="utf-8") as f:
                ref = json.load(f)
            return ref
        except Exception:
            pass
    ref = compute_monitor_reference(model, monitor_src)
    ref["timestamp_local"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    ref["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(ref_path, "w", encoding="utf-8") as f:
        json.dump(ref, f, indent=2)
    return ref


@torch.no_grad()
def load_monitor_image():
    monitor_dir = os.path.join(SCRIPT_DIR, "Test_Image")
    monitor_candidates = []
    for pattern in ("*.bmp", "*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"):
        monitor_candidates.extend(glob.glob(os.path.join(monitor_dir, pattern)))
    monitor_candidates = sorted(monitor_candidates)

    candidates = monitor_candidates + [
        os.path.join(SCRIPT_DIR, "test", "W", "VisionTop_20251029182653732.bmp"),
        os.path.join(SCRIPT_DIR, "test", "W", "monitor.bmp"),
    ]
    for c in candidates:
        if os.path.exists(c):
            path = c
            break
    else:
        src_list = collect_image_paths(TRAIN_SRC_DIR, recursive=True)
        if len(src_list) == 0:
            print("[WARN] No monitor image found and training folder empty. Monitor disabled.")
            return None
        path = src_list[0]
        print(f"[WARN] monitor image not found. Using first train src: {path}")

    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"[WARN] Failed to read monitor image: {path}")
        return None
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if img.dtype == np.uint16:
        img01 = img.astype(np.float32) / 65535.0
    else:
        img01 = img.astype(np.float32) / 255.0

    h, w = img01.shape
    pad_h = (8 - (h % 8)) % 8
    pad_w = (8 - (w % 8)) % 8
    img_pad = np.pad(img01, ((0, pad_h), (0, pad_w)), mode="reflect")
    ten = torch.from_numpy(img_pad).float()[None, None, ...]
    cv2.imwrite(os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_monitor_input.bmp"), img)

    meta_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_monitor_meta.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"path={path}\n")
        f.write(f"orig_hw={h},{w}\n")
        f.write(f"pad_hw={img_pad.shape[0]},{img_pad.shape[1]}\n")
    return ten.to(CFG.DEVICE)


@torch.no_grad()
def save_monitor(model, monitor_src: torch.Tensor, epoch_idx: int, save_outputs: bool = True, verbose: bool = True):
    model.eval()
    pred = model(monitor_src)
    pred01_t = pred.float().clamp(0.0, 1.0)

    meta_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_monitor_meta.txt")
    h = w = None
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("orig_hw="):
                    hw = line.strip().split("=", 1)[1]
                    h, w = [int(x) for x in hw.split(",")]

    if (h is not None) and (w is not None):
        pred01_t = pred01_t[..., :h, :w]

    cb_energy = float(checkerboard_energy(pred01_t).item())
    hf_ratio_val = float(hf_ratio(pred01_t).item())
    sr_mean = float(pred01_t.mean().item())
    sr_std = float(pred01_t.std(unbiased=False).item())
    sr_min = float(pred01_t.min().item())
    sr_max = float(pred01_t.max().item())
    sr_sat = float((pred01_t < 0.01).float().mean().item() + (pred01_t > 0.99).float().mean().item())

    mask_valid = make_valid_mask(pred01_t)
    mag = sobel_magnitude(pred01_t)
    edge_mask, _, info = _edge_mask_from_mag_torch(mag, mask_valid)
    edge_density = float(np.mean(info["density"])) if info["density"] else 0.0
    edge_width_val = float(compute_edge_width_metric(pred01_t, mask_valid=mask_valid))

    pred01 = pred01_t[0, 0].cpu().numpy()

    if save_outputs:
        pred_u8 = (pred01 * 255.0).clip(0, 255).astype(np.uint8)
        out1 = os.path.join(PROGRESS_DIR, f"monitor_epoch_{epoch_idx+1:03d}_v5.bmp")
        out2 = os.path.join(PRETRAINED_DIR, "latest_v5.bmp")
        cv2.imwrite(out1, pred_u8)
        cv2.imwrite(out2, pred_u8)

    epoch1 = epoch_idx + 1
    if verbose:
        if epoch1 <= 10:
            flat = pred01_t.detach().reshape(-1).cpu()
            p95 = torch.quantile(flat, 0.95).item()
            p99 = torch.quantile(flat, 0.99).item()
            print(f"[MONITOR][E{epoch1:03d}] range[{pred01.min():.4f},{pred01.max():.4f}] "
                  f"mean={pred01.mean():.4f} std={pred01.std():.4f} p95={p95:.4f} p99={p99:.4f} "
                  f"cb={cb_energy:.5f} hf_ratio={hf_ratio_val:.3f} edgeW={edge_width_val:.4f}")
        else:
            print(f"[MONITOR][E{epoch1:03d}] range[{pred01.min():.4f},{pred01.max():.4f}] "
                  f"mean={pred01.mean():.4f} std={pred01.std():.4f} "
                  f"cb={cb_energy:.5f} hf_ratio={hf_ratio_val:.3f} edgeW={edge_width_val:.4f}")

    if hf_ratio_val > float(CFG.HF_RATIO_WARN):
        print(f"[WARN][MONITOR] HF ratio high: {hf_ratio_val:.3f} (> {float(CFG.HF_RATIO_WARN):.2f})")

    return {
        "mean": sr_mean,
        "std": sr_std,
        "min": sr_min,
        "max": sr_max,
        "sat": sr_sat,
        "cb": cb_energy,
        "hf_ratio": hf_ratio_val,
        "hf_proxy": hf_ratio_val,
        "edge_width": edge_width_val,
        "edge_density": edge_density,
    }


# ============================================================
# Main
# ============================================================
_PROXY_BASE_KEYS = (
    "proxy_score_mean", "proxy_score_p10", "proxy_score_pass_rate", "proxy_score_lr_mean", "proxy_score_lr_p10",
    "proxy_posx_step_mean", "proxy_posy_step_mean", "proxy_step_err", "proxy_pos_step_std_sum",
    "proxy_scale_mean", "proxy_scale_dev", "proxy_posx_adj_std", "proxy_posy_adj_std", "proxy_scale_std",
    "proxy_invalid_count", "proxy_invalid_rate", "proxy_edge_density_model", "proxy_edge_density_sr_mean",
    "proxy_edge_q_model", "proxy_edge_q_sr_mean", "proxy_edge_k_model", "proxy_edge_k_sr_mean",
    "proxy_match_ratio_mean", "proxy_ori_ratio_mean", "proxy_hist_sim",
    "proxy_invalid_model", "proxy_invalid_frame", "proxy_invalid_density",
)

_BATCH_LOG_HEADER_V5 = [
    "epoch", "batch",
    "loss_total", "loss_rec", "loss_gradmag", "loss_edgeori", "loss_eqgeom", "loss_eqgrad",
    "loss_stat", "loss_band", "loss_hf_lap", "loss_phys", "loss_edgeLocalLap", "loss_detail", "w_edgeLocalLap",
    "pred_mean_mask", "pred_std_mask", "bandE_pred", "bandE_gt", "phys_weight",
    "eq_shift_r_min", "eq_shift_r_max", "eq_factor",
    "weak_psf_beta", "weak_psf_beta_scale", "weak_psf_entropy", "weak_psf_top1", "weak_psf_bypass",
    "lr",
]

_VAL_MONITOR_KEYS = ("edge_width", "hf_proxy", "metric_edge_width", "metric_hf_proxy", "metric_cb_proxy")
_VAL_SCHED_KEYS = ("sched_consist_factor", "sched_cap_factor", "guard_thicken_mult", "guard_thicken_hold")
_VAL_WEIGHT_KEYS = ("w_rec", "w_consistency_eff", "w_smooth_eff", "w_cap_eff", "w_edgeLocalLap")
_VAL_FLAG_KEYS = ("flag_thicken_guard", "flag_oversmooth_guard", "flag_lap_guard", "flag_psf_guard")
_VAL_LOSS_SUMMARY_KEYS = (
    "rec", "gradmag", "edge_ori", "eq_total", "loss_stat", "loss_band", "loss_hf_lap", "loss_phys",
    "loss_edgeLocalLap", "loss_detail", "pred_mean_mask", "pred_std_mask", "bandE_pred", "bandE_gt",
)
_VAL_LOSS_HEADER_KEYS = (
    "loss_rec", "loss_gradmag", "loss_edgeori", "loss_eqgeom", "loss_stat", "loss_band", "loss_hf_lap", "loss_phys",
    "loss_edgeLocalLap", "loss_detail", "pred_mean_mask", "pred_std_mask", "bandE_pred", "bandE_gt",
)
_VAL_RAW_METRIC_KEYS = ("total", "rec", "edge", "edge_profile", "psnr", "ssim", "fft_shape", "cb", "hf_ratio")
_VAL_SR_KEYS = ("sr_mean", "sr_std", "sr_min", "sr_max", "sr_sat")
_VAL_PROXY_SCORE_KEYS = _PROXY_BASE_KEYS[:3]
_VAL_PROXY_LR_KEYS = _PROXY_BASE_KEYS[3:5]
_VAL_PROXY_DETAIL_KEYS = _PROXY_BASE_KEYS[5:]
_VAL_GMF_KEYS = (
    "gmf_obj", "tradeoff_score", "tradeoff_edge_pen", "tradeoff_hf_pen", "gmf_fitness",
    "gmf_z_step_std", "gmf_z_outlier", "gmf_z_step_mean_err", "gmf_z_gain_p10", "gmf_z_proxy_mean",
    "best_score", "best_z_score_mean", "best_z_score_p10", "best_z_pos_std", "best_z_step_err",
)
_VAL_TRAIN_DIAG_KEYS = (
    "train_edge", "train_edge_profile", "train_edge_profile_w", "train_edge_ori", "train_edge_ori_w",
    "train_edge_chamfer_raw", "train_edge_chamfer_w", "train_fft", "train_cb", "train_hf_ratio",
    "val_edge_profile_w", "val_edge_ori", "val_edge_ori_w", "val_edge_chamfer_raw", "val_edge_chamfer_w", "val_fft",
    "physics_alpha", "physics_reg",
)
_VAL_ENABLE_KEYS = ("physics_enable", "weak_psf_enable", "chamfer_enable")
_VAL_KPI_KEYS = ("kpi_step_mean_err", "kpi_step_std", "kpi_outlier_rate", "kpi_outlier_t", "kpi_expected_step_px", "kpi_expected_step_enable")
_VAL_KPI_OFF_KEYS = ("kpi_step_mean_err_off", "kpi_step_std_off", "kpi_outlier_rate_off", "kpi_step_mean_err_delta", "kpi_step_std_delta", "kpi_outlier_rate_delta")

_VAL_LOG_HEADER_V5 = [
    "epoch", "seed", "detail_rescue_mult", "psf_forced_freeze",
    *_VAL_LOSS_HEADER_KEYS,
    *[f"val_{k}" for k in _VAL_RAW_METRIC_KEYS],
    *_VAL_MONITOR_KEYS, *_VAL_SCHED_KEYS, *_VAL_WEIGHT_KEYS, *_VAL_FLAG_KEYS,
    *[f"train_{k}" for k in _VAL_SR_KEYS],
    "eq_factor", "eq_shift_range", "loss_eq_total", "loss_eq_grad", "loss_eq_edge", "loss_eq_int",
    "eq_disable_intensity", "eq_intensity_mode", "eq_intensity_weight_effective",
    "eq_edge_w_mean", "eq_edge_w_p95",
    "consistency_factor", "rescue_flag", "fail_flag",
    *_VAL_PROXY_SCORE_KEYS, *_VAL_PROXY_LR_KEYS,
    "proxy_expect_dx_px", "proxy_expect_dy_px",
    *_VAL_PROXY_DETAIL_KEYS, *_VAL_GMF_KEYS,
    "weak_psf_beta", "weak_psf_beta_eff", "weak_psf_beta_scale", "weak_psf_entropy", "weak_psf_top1", "weak_psf_bypass",
    *_VAL_KPI_KEYS,
    "proxy_gain_mean", "proxy_gain_p10", "proxy_lr_enable",
    *_VAL_KPI_OFF_KEYS,
    *_VAL_TRAIN_DIAG_KEYS, *_VAL_ENABLE_KEYS,
]

_VAL_METRICS_DEFAULT = {k: np.nan for k in ("total", "rec", "edge", "edge_profile", "psnr", "ssim", "fft_shape", "cb", "hf_ratio")}
_VAL_METRICS_DEFAULT.update({"edge_ori": 0.0, "edge_chamfer_raw": 0.0, "edge_chamfer_w": 0.0, "fft": 0.0})

_PROXY_METRICS_DEFAULT = {k: np.nan for k in _PROXY_BASE_KEYS}

_PROXY_SUMMARY_FIELDS = tuple((k, np.nan) for k in _PROXY_BASE_KEYS) + (
    ("proxy_gain_mean", 0.0), ("proxy_gain_p10", 0.0), ("proxy_lr_enable", 0),
    ("kpi_step_mean_err", 0.0), ("kpi_step_std", 0.0), ("kpi_outlier_rate", 0.0), ("kpi_outlier_t", None),
    ("kpi_expected_step_px", 0.0), ("kpi_expected_step_enable", 0),
    ("kpi_step_mean_err_off", 0.0), ("kpi_step_std_off", 0.0), ("kpi_outlier_rate_off", 0.0),
    ("kpi_step_mean_err_delta", 0.0), ("kpi_step_std_delta", 0.0), ("kpi_outlier_rate_delta", 0.0),
)


def _apply_cli_overrides(args: argparse.Namespace):
    if args.attrib_window is not None:
        CFG.ATTRIB_WINDOW = int(args.attrib_window)
    if args.attrib_every is not None:
        CFG.ATTRIB_EVERY = int(args.attrib_every)
    if getattr(args, "seed_deterministic", False):
        CFG.SEED_DETERMINISTIC = True
    if getattr(args, "force_fast_eval", False):
        CFG.FAST_VAL_EVERY_EPOCH = max(2, int(CFG.FAST_VAL_EVERY_EPOCH))
        CFG.GMF_VALIDATE_EVERY_N = max(2, int(CFG.GMF_VALIDATE_EVERY_N))


def _prepare_seed_run(seed: int) -> Tuple[int, bool]:
    seed = int(seed)
    seed_deterministic = bool(getattr(CFG, "SEED_DETERMINISTIC", False))
    CFG.SEED_ACTIVE = seed
    CFG.REPRO_SEED = seed
    CFG.REPRO_MODE = seed_deterministic
    CFG.REPRO_DETERMINISTIC = seed_deterministic
    CFG.REPRO_DISABLE_TF32 = seed_deterministic

    _configure_run_paths()
    print(f"[RUN] tag={RUN_TAG} model={CFG.MODEL_NAME}")
    print(f"[RUN] progress_dir={PROGRESS_DIR}")
    print(f"[RUN] weights_dir={PRETRAINED_DIR}")

    set_global_seed(seed, seed_deterministic)
    use_amp = bool(CFG.use_amp)
    if CFG.REPRO_MODE and CFG.REPRO_DISABLE_AMP:
        use_amp = False
    CFG.use_amp = use_amp

    if bool(getattr(CFG, "SEED_SWEEP_ENABLE", False)):
        if bool(getattr(CFG, "SIMPLETEST_MODE", False)):
            CFG.SIMPLETEST_MAX_EPOCH = int(getattr(CFG, "SEED_PER_RUN_EPOCHS", CFG.SIMPLETEST_MAX_EPOCH))
        else:
            CFG.NUM_EPOCH = int(getattr(CFG, "SEED_PER_RUN_EPOCHS", CFG.NUM_EPOCH))

    repro_seed = int(CFG.REPRO_SEED if CFG.REPRO_MODE else CFG.SPLIT_SEED)
    repro_num_workers = int(CFG.REPRO_NUM_WORKERS if CFG.REPRO_MODE else CFG.NUM_WORKERS)
    print(
        f"[REPRO] mode={'ON' if CFG.REPRO_MODE else 'OFF'} "
        f"seed={repro_seed} "
        f"deterministic={'ON' if (CFG.REPRO_MODE and CFG.REPRO_DETERMINISTIC) else 'OFF'} "
        f"tf32={'OFF' if (CFG.REPRO_MODE and CFG.REPRO_DISABLE_TF32) else 'ON'} "
        f"amp={'ON' if use_amp else 'OFF'} "
        f"fixed_split={'ON' if (CFG.REPRO_MODE and CFG.REPRO_FORCE_FIXED_SPLIT) else 'OFF'} "
        f"num_workers={repro_num_workers}"
    )
    print(
        f"[SEED] active={seed} "
        f"cudnn_deterministic={int(torch.backends.cudnn.deterministic)} "
        f"cudnn_benchmark={int(torch.backends.cudnn.benchmark)} "
        f"tf32_matmul={int(getattr(torch.backends.cuda.matmul, 'allow_tf32', False)) if hasattr(torch.backends, 'cuda') else 0} "
        f"tf32_cudnn={int(getattr(torch.backends.cudnn, 'allow_tf32', False))}"
    )
    _write_run_meta(seed, seed_deterministic, use_amp)
    print(
        f"[FAST_IO] mode={'ON' if CFG.FAST_IO_MODE else 'OFF'} "
        f"disable_plots={'ON' if CFG.FAST_DISABLE_PLOTS else 'OFF'} "
        f"plot_every={int(CFG.FAST_PLOT_EVERY_EPOCH)} "
        f"monitor_every={int(CFG.FAST_MONITOR_EVERY_EPOCH)} "
        f"val_every={int(CFG.FAST_VAL_EVERY_EPOCH)} "
        f"batch_log_every={int(getattr(CFG, 'BATCH_LOG_EVERY_N', 1))} "
        f"csv_flush_n={int(CFG.FAST_CSV_FLUSH_EVERY_N)}"
    )
    return seed, use_amp


def _build_model_from_cfg() -> nn.Module:
    model = GeoEdgeAlignSR_v1_v5_NoCoord(
        psf_fitted_path=CFG.PSF_FITTED_PATH,
        psf_grid_rows=CFG.PSF_GRID_ROWS,
        psf_grid_cols=CFG.PSF_GRID_COLS,
        psf_use_stack_mean=CFG.PSF_USE_STACK_MEAN,
        psf_deconv_reg=CFG.PSF_DECONV_REG,
        psf_phys_alpha_init=CFG.PSF_PHYS_ALPHA_INIT,
        psf_phys_trainable_reg=CFG.PSF_PHYS_TRAINABLE_REG,
        psf_phys_alpha_min=CFG.PSF_PHYS_ALPHA_MIN,
        psf_phys_alpha_max=CFG.PSF_PHYS_ALPHA_MAX,
        use_upsample_conv=CFG.USE_UPSAMPLE_CONV,
        use_band_limit=CFG.USE_BAND_LIMIT,
        band_limit_cutoff=CFG.OPTICAL_CUTOFF,
        weak_psf_enable=CFG.WEAK_PSF_ENABLE,
        weak_psf_k=CFG.WEAK_PSF_K,
        weak_psf_indices=CFG.WEAK_PSF_INDICES,
        weak_psf_reg=CFG.WEAK_PSF_REG,
        weak_psf_beta_init=CFG.WEAK_PSF_BETA_INIT,
        weak_psf_gating_temp=CFG.WEAK_PSF_GATING_TEMP,
        weak_psf_psf_temp=CFG.WEAK_PSF_PSF_TEMP,
        weak_psf_entropy_mix=CFG.WEAK_PSF_ENTROPY_MIX_STAGE2,
        weak_psf_deconv_mode=CFG.WEAK_PSF_DECONV_MODE,
        weak_psf_inject=CFG.WEAK_PSF_INJECT,
        weak_psf_trainable_reg=CFG.WEAK_PSF_TRAINABLE_REG,
        weak_psf_lowfreq_ratio=CFG.WEAK_PSF_LOWFREQ_RATIO,
        weak_psf_beta_min=CFG.WEAK_PSF_BETA_MIN,
        weak_psf_beta_max=CFG.WEAK_PSF_BETA_MAX,
        weak_psf_beta_scale_max=CFG.WEAK_PSF_BETA_SCALE_MAX,
    ).to(CFG.DEVICE)
    if not any(p.requires_grad for p in model.parameters()):
        raise RuntimeError("[FATAL] No trainable parameters found; check freeze settings.")
    return model


def _build_optimizer(model: nn.Module) -> optim.Optimizer:
    physics_params = []
    weak_psf_params = []
    other_params = []
    for name, param in model.named_parameters():
        if "physics_layer" in name:
            physics_params.append(param)
        elif "weak_psf" in name:
            weak_psf_params.append(param)
        else:
            other_params.append(param)

    optimizer = optim.Adam(
        [
            {"params": other_params, "lr": CFG.LR, "weight_decay": CFG.WEIGHT_DECAY},
            {"params": physics_params, "lr": CFG.LR * float(CFG.PHYSICS_LR_MULT), "weight_decay": CFG.WEIGHT_DECAY},
            {"params": weak_psf_params, "lr": CFG.LR * float(CFG.WEAK_PSF_LR_MULT), "weight_decay": CFG.WEIGHT_DECAY},
        ]
    )
    for group in optimizer.param_groups:
        group.setdefault("initial_lr", group.get("lr", CFG.LR))
    return optimizer


def _resolve_script_relative(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(SCRIPT_DIR, path)


def _open_csv_logger(path: str, header: list):
    exists = os.path.exists(path)
    csv_f = open(path, "a", newline="", encoding="utf-8", buffering=(1 << 20))
    csv_w = csv.writer(csv_f)
    if not exists:
        csv_w.writerow(header)
    return csv_f, csv_w


def _default_val_metrics() -> dict:
    return dict(_VAL_METRICS_DEFAULT)


def _default_proxy_metrics() -> dict:
    return dict(_PROXY_METRICS_DEFAULT)


def _copy_proxy_metrics(summary: dict, proxy_m: dict):
    for key, default in _PROXY_SUMMARY_FIELDS:
        if key == "kpi_outlier_t":
            summary[key] = proxy_m.get(key, float(CFG.GMF_OUTLIER_T))
        else:
            summary[key] = proxy_m.get(key, default)


def _log_data_and_loss_setup(train_loader, val_loader, phys_forward_runtime: bool):
    print(f"[INFO] Train batches/epoch: {len(train_loader)}")
    if val_loader is None:
        print("[INFO] Validation: DISABLED (VAL_RATIO <= 0)")
    else:
        print(f"[INFO] Validation: ENABLED (VAL_RATIO={CFG.VAL_RATIO}, val batches={len(val_loader)})")
    if CFG.GMF_VALIDATE_ENABLE and val_loader is None:
        print("[WARN][PROXY] GMF proxy validation requires val_loader; proxy metrics will be low/unstable.")

    if CFG.GMF_VALIDATE_ENABLE:
        if int(CFG.GMF_VAL_NUM_FRAMES) < 2:
            print("[WARN][PROXY] GMF_VAL_NUM_FRAMES < 2; proxy metrics may be unstable.")
        if (CFG.GMF_EXPECT_DX_PX is not None) and (CFG.GMF_EXPECT_DY_PX is not None):
            print(
                f"[INFO] GMF_EXPECT_DX_PX/DY_PX (px/step) = "
                f"({float(CFG.GMF_EXPECT_DX_PX):.6f}, {float(CFG.GMF_EXPECT_DY_PX):.6f})"
            )

    print("[INFO] Loss = Rec(Huber+SSIM small) + GradMag + EdgeOri + EqGeom(grad-only)")
    print("[INFO] [FIX] Strict Zeros Padding + Mask Erosion (r=4px) enabled")
    print(
        "[PATCH] 50-epoch rhythm; add edge-local Lap rescue; tighten thicken/self-band guards; "
        "PSF only guard-burst (no long-term smoothing)."
    )
    print(
        f"[SIMPLETEST_V2] w_rec={float(CFG.W_REC):.3f} w_ssim={float(CFG.W_SSIM_START):.3f} "
        f"w_gradmag={float(CFG.W_GRADMAG):.3f} w_edgeori={float(CFG.W_EDGE_ORI_SIMPLE):.3f} "
        f"w_eqgeom={float(CFG.W_EQ_GEOM):.3f}"
    )
    print(
        f"[SIMPLETEST_V2] w_stat={float(CFG.W_STAT):.3f} w_band={float(CFG.W_BAND):.3f} "
        f"w_hf_lap={float(CFG.W_HF_LAP):.3f} w_phys_max={float(CFG.W_PHYS_MAX):.3f} "
        f"w_edgeLocalLap_end={float(CFG.W_EDGELOCAL_LAP_END):.3f} "
        f"phys_warmup_end={int(CFG.PHYS_WARMUP_END)} phys_ramp_end={int(CFG.PHYS_RAMP_END)} "
        f"phys_runtime={int(phys_forward_runtime)}"
    )
    print(
        f"[SIMPLETEST_V2] eq_shift_range<=0.5px tiny={CFG.EQ_SHIFT_TINY_RANGE} mid={CFG.EQ_SHIFT_MID_RANGE} "
        f"band_r=[{float(CFG.BAND_R_LOW):.2f},{float(CFG.BAND_R_HIGH):.2f}] "
        f"band_every_n_batch={max(1, int(CFG.BAND_LOSS_EVERY_N_BATCH))} "
        f"edgeLap_thr={float(CFG.EDGELOCAL_LAP_THR):.3f} dilate={int(CFG.EDGELOCAL_LAP_DILATE)}"
    )
    print(
        f"[SIMPLETEST_V2] intensity-eq=DISABLED thicken_guard={int(CFG.ENABLE_THICKEN_GUARD)} "
        f"self_band_ready_e={int(CFG.SELF_BAND_READY_EPOCH)} psf_guard_only={int(CFG.ENABLE_PSF_GUARD_ONLY)}"
    )


def _init_monitor_reference(model: nn.Module, ema_model: Optional[nn.Module]):
    monitor_src = load_monitor_image()
    ref_model = ema_model if ema_model is not None else model
    monitor_ref = load_or_create_monitor_ref(ref_model, monitor_src)
    edge_width_ref = float(monitor_ref.get("edge_width_ref", np.nan))
    hf_proxy_ref = float(monitor_ref.get("hf_proxy_ref", np.nan))
    cb_ref = float(monitor_ref.get("cb_ref", np.nan))
    print(f"[MONITOR_REF] edgeW_ref={edge_width_ref:.4f} hf_ref={hf_proxy_ref:.4f} cb_ref={cb_ref:.6f}")
    return monitor_src, edge_width_ref, hf_proxy_ref, cb_ref


def _resume_training_state(model: nn.Module, optimizer: optim.Optimizer, ema_model: Optional[nn.Module]) -> int:
    start_epoch = 0
    ema_loaded = False

    if CFG.LOAD_MODEL:
        ckpt_path_v5 = _resolve_script_relative(CFG.PRETRAINED_PATH)
        ckpt_path_v4 = _resolve_script_relative(CFG.PRETRAINED_FALLBACK_PATH)

        if os.path.exists(ckpt_path_v5):
            print(f"[INFO] Resuming v5 training from: {ckpt_path_v5}")
            start_epoch, ema_loaded = load_ckpt(ckpt_path_v5, model, optimizer, ema_model=ema_model)
            print(f"[INFO] Resumed from epoch {start_epoch}")
        elif os.path.exists(ckpt_path_v4):
            print(f"[INFO] v5 checkpoint not found. Inheriting weights from v4: {ckpt_path_v4}")
            _, ema_loaded = load_ckpt(ckpt_path_v4, model, None, ema_model=None)
            start_epoch = 0
        else:
            print("[WARN] No checkpoint found (v5 or v4). Starting from scratch.")

    if (ema_model is not None) and (not ema_loaded):
        update_ema_model(ema_model, model, 0.0)
    return start_epoch


def _build_val_log_row(epoch1: int, summary: dict, val_m: dict) -> list:
    sg = summary.get
    row = [
        epoch1,
        int(sg("seed", getattr(CFG, "SEED_ACTIVE", 0))),
        sg("detail_rescue_mult", 1.0),
        int(sg("psf_forced_freeze", 0)),
    ]
    row += [sg(k, np.nan) for k in _VAL_LOSS_SUMMARY_KEYS]
    row += [val_m[k] for k in _VAL_RAW_METRIC_KEYS]
    row += [sg(k, np.nan) for k in _VAL_MONITOR_KEYS]
    row += [sg("sched_consist_factor", 1.0), sg("sched_cap_factor", 1.0), sg("guard_thicken_mult", 1.0), sg("guard_thicken_hold", 0)]
    row += [sg("w_rec", float(CFG.W_REC)), sg("w_consistency_eff", 0.0), sg("w_smooth_eff", 0.0), sg("w_cap_eff", 0.0), sg("w_edgeLocalLap", 0.0)]
    row += [int(sg(k, 0)) for k in _VAL_FLAG_KEYS]
    row += [summary[k] for k in _VAL_SR_KEYS]
    row += [sg("eq_factor", 0.0), sg("eq_shift_range", "na"), sg("eq_total", 0.0), sg("eq_grad", 0.0), sg("eq_edge", 0.0), sg("eq_int", sg("eq_pix", 0.0))]
    row += [
        int(sg("eq_disable_intensity", 0)),
        {"off": 0, "warmup_only": 1, "on": 2}.get(str(sg("eq_intensity_mode", "warmup_only")).lower(), -1),
        sg("eq_intensity_weight_effective", 0.0),
        sg("eq_edgew_mean", np.nan),
        sg("eq_edgew_p95", np.nan),
        sg("consistency_factor", sg("sched_consist_factor", 1.0)),
        int(sg("rescue_flag", 0)),
        int(sg("fail_flag", 0)),
    ]
    row += [summary[k] for k in _VAL_PROXY_SCORE_KEYS]
    row += [sg(k, np.nan) for k in _VAL_PROXY_LR_KEYS]
    row += [float(CFG.GMF_EXPECT_DX_PX) if CFG.GMF_EXPECT_DX_PX is not None else 0.0, float(CFG.GMF_EXPECT_DY_PX) if CFG.GMF_EXPECT_DY_PX is not None else 0.0]
    row += [summary[k] for k in _VAL_PROXY_DETAIL_KEYS]
    row += [sg(k, np.nan) for k in _VAL_GMF_KEYS]
    row += [sg("weak_psf_beta", np.nan), sg("weak_psf_beta_eff", 0.0), sg("weak_psf_beta_scale", 0.0), sg("weak_psf_entropy", np.nan), sg("weak_psf_top1_ratio", np.nan), int(bool(sg("weak_psf_bypass", False)))]
    row += [int(sg(k, 0)) if k == "kpi_expected_step_enable" else sg(k, 0.0) for k in _VAL_KPI_KEYS]
    row += [sg("proxy_gain_mean", 0.0), sg("proxy_gain_p10", 0.0), int(sg("proxy_lr_enable", 0))]
    row += [sg(k, 0.0) for k in _VAL_KPI_OFF_KEYS]
    row += [sg(k, 0.0) for k in _VAL_TRAIN_DIAG_KEYS]
    row += [int(sg(k, 0)) for k in _VAL_ENABLE_KEYS]
    return row


def _compute_epoch_runtime_controls(
    epoch1: int,
    rescue_remaining: int,
    band_guard_hold: int,
    thicken_guard_mult: float,
    detail_rescue_mult: float,
    rescue_eq_mult: float,
    cap_spike_left: int,
    thicken_guard_hold: int,
    last_thicken_trigger: bool,
    lap_guard_hold: int,
    lap_boost_hold: int,
    psf_force_hold: int,
    psf_guard_hold: int,
) -> dict:
    rescue_active_epoch = bool(rescue_remaining > 0)
    rescue_flag_epoch = int(rescue_active_epoch)
    band_guard_mult_epoch = float(CFG.THICKEN_GUARD_MULT) if band_guard_hold > 0 else 1.0
    guard_mult_epoch = min(float(thicken_guard_mult), float(band_guard_mult_epoch))

    consist_factor_eff = float(get_consistency_factor(epoch1)) * float(guard_mult_epoch)
    if rescue_active_epoch:
        consist_factor_eff *= float(getattr(CFG, "RESCUE_CONSIST_MULT", 0.60))

    detail_rescue_mult_epoch = float(detail_rescue_mult)
    detail_rescue_active_epoch = bool(detail_rescue_mult_epoch > 1.0)
    edge_profile_mult_epoch = 1.0
    if detail_rescue_active_epoch and (int(getattr(CFG, "DETAIL_RESCUE_START_E", 0)) <= epoch1 <= int(getattr(CFG, "DETAIL_RESCUE_END_E", 0))):
        edge_profile_mult_epoch *= float(getattr(CFG, "DETAIL_RESCUE_EDGE_PROFILE_MULT", 1.0))
    if rescue_active_epoch:
        edge_profile_mult_epoch = min(
            edge_profile_mult_epoch * float(getattr(CFG, "RESCUE_EDGE_PROFILE_MULT", 1.15)),
            float(getattr(CFG, "RESCUE_EDGE_PROFILE_MULT_MAX", 1.5)),
        )

    eq_factor_epoch = float(get_eq_factor(epoch1)) * float(thicken_guard_mult) * float(rescue_eq_mult)
    eq_intensity_mode = str(getattr(CFG, "EQ_INTENSITY_MODE", "off")).lower()
    eq_intensity_weight_effective = 0.0
    if (not bool(getattr(CFG, "SIMPLETEST_MODE", False))) and (eq_intensity_mode != "off"):
        if eq_intensity_mode == "on":
            eq_intensity_weight_effective = float(getattr(CFG, "EQ_INTENSITY_REL_WEIGHT", 0.10))
        elif eq_intensity_mode == "warmup_only":
            early_end = int(getattr(CFG, "EQ_INTENSITY_EARLY_END", 5))
            if epoch1 <= max(1, early_end):
                eq_intensity_weight_effective = float(getattr(CFG, "EQ_INTENSITY_EARLY_SCALE", 0.20))
    eq_disable_intensity = bool(eq_intensity_weight_effective <= 0.0)
    if eq_disable_intensity and eq_intensity_mode == "off":
        eq_intensity_mode = "off"
    if bool(getattr(CFG, "EQ_DISABLE_INTENSITY_ON_THICKEN_GUARD", True)) and (thicken_guard_hold > 0):
        eq_intensity_weight_effective = 0.0
        eq_disable_intensity = True
    if rescue_remaining > 0:
        eq_intensity_weight_effective = 0.0
        eq_disable_intensity = True

    cap_base_factor = float(getattr(CFG, "CAP_FACTOR_BASE", 0.0))
    cap_spike_factor = float(getattr(CFG, "CAP_SPIKE_BOOST", 0.0)) if cap_spike_left > 0 else 0.0
    cap_factor_epoch = max(cap_base_factor, cap_base_factor + cap_spike_factor)
    cap_guarded_factor = max(float(getattr(CFG, "CAP_GUARD_MIN_MULT", 0.25)), cap_factor_epoch * float(guard_mult_epoch))
    w_smooth = float(CFG.W_SMOOTH) * float(guard_mult_epoch)
    w_consistency = float(CFG.W_CONSISTENCY) * float(consist_factor_eff)
    w_cap_eff = float(cap_guarded_factor)

    eq_shift_override = None
    if bool(getattr(CFG, "EQ_SHIFT_TINY_ONLY_ON_THICKEN", True)) and (thicken_guard_hold > 0 or last_thicken_trigger):
        eq_shift_override = {
            "p_tiny": 1.0,
            "p_mid": 0.0,
            "p_int": 0.0,
            "tiny_rng": CFG.EQ_SHIFT_TINY_RANGE,
            "mid_rng": CFG.EQ_SHIFT_TINY_RANGE,
            "max_int": 0,
            "int_exclude_zero": True,
        }

    w_edge_local_lap_epoch = get_edgelocal_lap_weight(epoch1)
    if lap_guard_hold > 0:
        w_edge_local_lap_epoch *= float(CFG.EDGELOCAL_LAP_HF_GUARD_MULT)
    if lap_boost_hold > 0:
        w_edge_local_lap_epoch = min(
            w_edge_local_lap_epoch * float(CFG.SELF_BAND_DETAIL_RESCUE_MULT),
            float(CFG.W_EDGELOCAL_LAP_END),
        )
    if detail_rescue_active_epoch and (int(getattr(CFG, "DETAIL_RESCUE_START_E", 0)) <= epoch1 <= int(getattr(CFG, "DETAIL_RESCUE_END_E", 0))):
        w_edge_local_lap_epoch = w_edge_local_lap_epoch * float(detail_rescue_mult_epoch)

    psf_force_freeze_epoch = bool(psf_force_hold > 0)
    psf_guard_active_epoch = bool(psf_guard_hold > 0)
    psf_guard_lr = float(CFG.PSF_LR_MULT_GUARD) if psf_guard_active_epoch else 0.0

    return {
        "rescue_active_epoch": rescue_active_epoch,
        "rescue_flag_epoch": rescue_flag_epoch,
        "guard_mult_epoch": guard_mult_epoch,
        "consist_factor_eff": consist_factor_eff,
        "detail_rescue_mult_epoch": detail_rescue_mult_epoch,
        "detail_rescue_active_epoch": detail_rescue_active_epoch,
        "edge_profile_mult_epoch": edge_profile_mult_epoch,
        "eq_factor_epoch": eq_factor_epoch,
        "eq_intensity_mode": eq_intensity_mode,
        "eq_intensity_weight_effective": eq_intensity_weight_effective,
        "eq_disable_intensity": eq_disable_intensity,
        "cap_base_factor": cap_base_factor,
        "cap_spike_factor": cap_spike_factor,
        "cap_factor_epoch": cap_factor_epoch,
        "w_smooth": w_smooth,
        "w_consistency": w_consistency,
        "w_cap_eff": w_cap_eff,
        "eq_shift_override": eq_shift_override,
        "w_edge_local_lap_epoch": w_edge_local_lap_epoch,
        "psf_force_freeze_epoch": psf_force_freeze_epoch,
        "psf_guard_active_epoch": psf_guard_active_epoch,
        "psf_guard_lr": psf_guard_lr,
    }


def _log_epoch_start(
    epoch1: int,
    total_epochs: int,
    w_rec: float,
    w_ssim: float,
    w_edge_local_lap_epoch: float,
    eq_factor_epoch: float,
    eq_disable_intensity: bool,
    consist_factor_eff: float,
    rescue_flag_epoch: int,
    rescue_remaining: int,
    thicken_guard_hold: int,
    guard_mult_epoch: float,
    rescue_lr_mult: float,
    rescue_eq_mult: float,
    phys_forward_runtime: bool,
):
    print(f"\nStarting Epoch {epoch1}/{total_epochs}")
    print(
        f"[EPOCH_CTRL][START] epoch={epoch1} eq_factor={eq_factor_epoch:.3f} "
        f"eq_prob={float(getattr(CFG, 'EQ_PROB', 1.0)):.2f} "
        f"eq_disable_intensity={int(eq_disable_intensity)} "
        f"consistency_factor={consist_factor_eff:.3f} "
        f"thicken_guard_hold={thicken_guard_hold} guard_mult={guard_mult_epoch:.3f} "
        f"rescue_lr_mult={rescue_lr_mult:.2f} rescue_eq_mult={rescue_eq_mult:.2f}"
    )
    print(
        f"[WEIGHT][E{epoch1:03d}] w_rec={w_rec:.3f} w_ssim={w_ssim:.3f} "
        f"w_gradmag={float(CFG.W_GRADMAG):.3f} w_edgeori={float(CFG.W_EDGE_ORI_SIMPLE):.3f} "
        f"w_eqgeom={float(CFG.W_EQ_GEOM):.3f} w_stat={float(CFG.W_STAT):.3f} "
        f"w_band={float(CFG.W_BAND):.3f} w_hf_lap={float(CFG.W_HF_LAP):.3f} "
        f"w_edgeLocalLap={w_edge_local_lap_epoch:.3f} "
        f"w_phys={get_phys_weight(epoch1) if phys_forward_runtime else 0.0:.3f} "
        f"eq_factor={eq_factor_epoch:.3f}"
    )
    print(f"[CONSIST] factor={consist_factor_eff:.3f} grad_only={int(bool(CFG.CONSIST_ON_GRAD_ONLY))}")
    print(f"[RESCUE] active={rescue_flag_epoch} remaining_epochs={int(rescue_remaining)}")


def _run_validation_epoch(
    eval_model: nn.Module,
    val_loader,
    huber,
    ssim,
    epoch: int,
    epoch1: int,
    fast_val_every: int,
    collapse: bool,
    prev_val_rec: Optional[float],
) -> Tuple[dict, Optional[float]]:
    val_m = _default_val_metrics()
    run_val_now = (epoch1 % fast_val_every) == 0
    if val_loader is not None and (not collapse) and run_val_now:
        val_m = validate_one_epoch(eval_model, val_loader, huber, ssim, epoch)
        print(
            f"-> Epoch {epoch1} Val Done. "
            f"Total={val_m['total']:.6f} | Rec={val_m['rec']:.6f} | Edge={val_m['edge']:.6f} "
            f"| EdgeProf={val_m['edge_profile']:.6f} | PSNR={val_m['psnr']:.2f} | SSIM={val_m['ssim']:.4f} "
            f"| FFTShape={val_m['fft_shape']:.6f} | CB={val_m['cb']:.6f} | HF={val_m['hf_ratio']:.3f}"
        )
        if np.isfinite(val_m["rec"]) and (prev_val_rec is not None) and np.isfinite(prev_val_rec):
            rec_delta = abs(float(val_m["rec"]) - float(prev_val_rec))
            if rec_delta > float(CFG.GEOM_READY_REC_DELTA):
                print(f"[SIMPLETEST][CTRL_OFF] rec_delta={rec_delta:.6f}; geom softening control disabled.")
        prev_val_rec = float(val_m["rec"]) if np.isfinite(val_m["rec"]) else prev_val_rec
    elif val_loader is not None and (not collapse) and (not run_val_now):
        print(f"[VAL][E{epoch1:03d}] skipped by FAST_VAL_EVERY_EPOCH={fast_val_every}")
    return val_m, prev_val_rec


def _update_val_summary_and_monitor_metrics(
    summary: dict,
    val_m: dict,
    monitor_stats: Optional[dict],
    edge_width_ref: float,
    hf_proxy_ref: float,
    cb_ref: float,
):
    summary["val_total"] = val_m["total"]
    summary["val_rec"] = val_m["rec"]
    summary["val_edge"] = val_m["edge"]
    summary["val_edge_profile"] = val_m["edge_profile"]
    summary["val_ssim"] = val_m["ssim"]
    summary["val_fft_shape"] = val_m["fft_shape"]
    summary["val_cb"] = val_m["cb"]
    summary["val_hf_ratio"] = val_m["hf_ratio"]

    metric_edge_width = float("nan")
    metric_hf_proxy = float("nan")
    metric_cb_proxy = float("nan")
    if monitor_stats is not None:
        metric_edge_width = float(monitor_stats.get("edge_width", np.nan))
        metric_hf_proxy = float(monitor_stats.get("hf_proxy", monitor_stats.get("hf_ratio", np.nan)))
        metric_cb_proxy = float(monitor_stats.get("cb", np.nan))
    if not np.isfinite(metric_hf_proxy):
        metric_hf_proxy = float(val_m.get("hf_ratio", np.nan))
    if not np.isfinite(metric_cb_proxy):
        metric_cb_proxy = float(val_m.get("cb", np.nan))

    summary["metric_edge_width"] = metric_edge_width
    summary["metric_hf_proxy"] = metric_hf_proxy
    summary["metric_cb_proxy"] = metric_cb_proxy
    summary["edge_width_ref"] = edge_width_ref
    summary["hf_proxy_ref"] = hf_proxy_ref
    summary["cb_ref"] = cb_ref


def _run_proxy_validation_epoch(eval_model: nn.Module, val_loader, epoch1: int, collapse: bool) -> dict:
    proxy_m = _default_proxy_metrics()
    if CFG.GMF_VALIDATE_ENABLE and (epoch1 % max(1, int(CFG.GMF_VALIDATE_EVERY_N)) == 0) and (not collapse):
        proxy_m = run_gmf_proxy_validation(eval_model, val_loader, epoch1)
        scale_dev_s = "disabled" if not CFG.PROXY_SCALE_ENABLE else f"{proxy_m['proxy_scale_dev']:.6f}"
        scale_std_s = "disabled" if not CFG.PROXY_SCALE_ENABLE else f"{proxy_m['proxy_scale_std']:.6f}"
        print(
            f"[PROXY][E{epoch1:03d}] mean={proxy_m['proxy_score_mean']:.2f} "
            f"p10={proxy_m['proxy_score_p10']:.2f} "
            f"lr_mean={proxy_m.get('proxy_score_lr_mean', np.nan):.2f} "
            f"pass={proxy_m['proxy_score_pass_rate']:.1f}% "
            f"step_err={proxy_m['proxy_step_err']:.4f} "
            f"scale_dev={scale_dev_s} "
            f"adj_std=({proxy_m['proxy_posx_adj_std']:.4f},{proxy_m['proxy_posy_adj_std']:.4f}) "
            f"scale_std={scale_std_s}"
        )
    return proxy_m


def _hist_mean(hist) -> float:
    return float(np.mean(hist)) if len(hist) > 0 else np.nan


def _is_relative_spike(curr: float, hist, rel: float, min_hist: int = 2) -> bool:
    if (not np.isfinite(curr)) or (len(hist) < int(min_hist)):
        return False
    base = float(np.median(np.asarray(hist, dtype=np.float64)))
    return bool(np.isfinite(base) and (base > 1e-8) and (curr > base * (1.0 + float(rel))))


def _tick_cap_spike_counters(cap_spike_left: int, cap_spike_cooldown: int) -> Tuple[int, int]:
    if cap_spike_left > 0:
        cap_spike_left -= 1
    if cap_spike_cooldown > 0:
        cap_spike_cooldown -= 1
    return cap_spike_left, cap_spike_cooldown


def _update_cap_fuse_state(
    summary: dict,
    cap_spike_left: int,
    cap_spike_cooldown: int,
    cap_hf_hist: deque,
    cap_cb_hist: deque,
) -> Tuple[int, int]:
    if bool(CFG.ENABLE_CAP_FUSE):
        curr_hf = float(summary.get("metric_hf_proxy", np.nan))
        curr_cb = float(summary.get("metric_cb_proxy", np.nan))
        spike_rel = float(CFG.CAP_SPIKE_THRESH_REL)
        spike_now = _is_relative_spike(curr_hf, cap_hf_hist, spike_rel, min_hist=2) or _is_relative_spike(curr_cb, cap_cb_hist, spike_rel, min_hist=2)
        if spike_now and (cap_spike_cooldown <= 0):
            cap_spike_left = max(cap_spike_left, int(CFG.CAP_SPIKE_EPOCHS))
            cap_spike_cooldown = max(cap_spike_cooldown, int(CFG.CAP_SPIKE_COOLDOWN))
            print(
                f"[SCHED][CAP_FUSE] spike boost={float(CFG.CAP_SPIKE_BOOST):.2f} "
                f"epochs={cap_spike_left} cooldown={cap_spike_cooldown} "
                f"hf={curr_hf:.4f} cb={curr_cb:.4f}"
            )
        if np.isfinite(curr_hf):
            cap_hf_hist.append(curr_hf)
        if np.isfinite(curr_cb):
            cap_cb_hist.append(curr_cb)
    return cap_spike_left, cap_spike_cooldown


def _update_thicken_guard(
    summary: dict,
    edge_width_ref: float,
    hf_proxy_ref: float,
    thicken_guard_mult: float,
    thicken_guard_hold: int,
    thicken_guard_hits: int,
) -> Tuple[bool, bool, float, int, int]:
    thicken_triggered_epoch = False
    oversmooth_triggered_epoch = False

    if bool(CFG.ENABLE_THICKEN_GUARD):
        rec_key = str(getattr(CFG, "THICKEN_REC_KEY", "val_rec"))
        rec_curr = float(summary.get(rec_key, summary.get("val_rec", np.nan)))
        edge_curr = float(summary.get("metric_edge_width", np.nan))
        hf_curr = float(summary.get("metric_hf_proxy", np.nan))
        edge_ref = float(edge_width_ref) if np.isfinite(edge_width_ref) else float("nan")
        hf_ref = float(hf_proxy_ref) if np.isfinite(hf_proxy_ref) else float("nan")
        patience = max(1, int(CFG.THICKEN_GUARD_PATIENCE))
        cond_edge = np.isfinite(edge_curr) and np.isfinite(edge_ref) and (edge_curr > edge_ref * (1.0 + float(CFG.THICKEN_EDGEWIDTH_UP_REL)))
        cond_hf = np.isfinite(hf_curr) and np.isfinite(hf_ref) and (hf_curr < hf_ref * (1.0 - float(CFG.THICKEN_HF_DROP_REL)))
        oversmooth_triggered_epoch = bool(cond_hf and (not cond_edge))
        if cond_edge:
            thicken_guard_hits += 1
        else:
            thicken_guard_hits = 0
        trigger = bool((thicken_guard_hold <= 0) and (thicken_guard_hits >= patience))
        if trigger:
            thicken_triggered_epoch = True
            thicken_guard_mult = max(
                float(CFG.THICKEN_GUARD_MIN_MULT),
                float(thicken_guard_mult) * float(CFG.THICKEN_GUARD_MULT),
            )
            thicken_guard_hold = max(0, int(CFG.THICKEN_GUARD_HOLD_EPOCHS))
            thicken_guard_hits = 0
            print(
                f"[GUARD][THICKEN] trigger mult={thicken_guard_mult:.3f} hold={thicken_guard_hold} "
                f"edgeW={edge_curr:.4f}/{edge_ref:.4f} hf={hf_curr:.4f}/{hf_ref:.4f} rec={rec_curr:.6f}"
            )
        else:
            if thicken_guard_hold > 0:
                thicken_guard_hold -= 1
            elif thicken_guard_mult < 1.0:
                thicken_guard_mult = min(1.0, thicken_guard_mult + float(getattr(CFG, "THICKEN_GUARD_RELEASE_STEP", 0.05)))
                print(f"[GUARD][THICKEN] release mult={thicken_guard_mult:.3f} hold={thicken_guard_hold}")
    else:
        thicken_guard_mult = 1.0
        thicken_guard_hold = 0
        thicken_guard_hits = 0

    return (
        thicken_triggered_epoch,
        oversmooth_triggered_epoch,
        float(thicken_guard_mult),
        int(thicken_guard_hold),
        int(thicken_guard_hits),
    )


def _update_epoch_summary_and_gmf_state(
    epoch1: int,
    summary: dict,
    val_m: dict,
    model: nn.Module,
    psf_sched: dict,
    w_edge_profile: float,
    w_edge_ori: float,
    w_edge_chamfer: float,
    epoch_summaries: list,
    collapse: bool,
    prev_val_rec: Optional[float],
    best_gmf_obj: Optional[float],
    gmf_bad_streak: int,
    prev_proxy_step_err: Optional[float],
    prev_proxy_pos_std_sum: Optional[float],
    prev_gmf_obj: Optional[float],
    gmf_gate_bad_count: int,
    gmf_gate_scale: float,
) -> Tuple[dict, Optional[float], int, Optional[float], Optional[float], Optional[float], int]:
    weak_stats = get_weak_psf_stats(model)
    summary.update({
        "weak_psf_beta": weak_stats["beta"],
        "weak_psf_beta_scale": weak_stats.get("beta_scale", 0.0),
        "weak_psf_beta_eff": weak_stats.get("beta_eff", 0.0),
        "weak_psf_entropy": weak_stats["entropy"],
        "weak_psf_top1_ratio": weak_stats["top1_ratio"],
        "weak_psf_bypass": weak_stats["bypass"],
        "weak_psf_gate_scale": float(psf_sched.get("gate_scale", 1.0)),
        "weak_psf_frozen": int(psf_sched.get("weak_frozen", False)),
    })

    phys_stats = get_physics_stats(model)
    summary.update({
        "physics_alpha": phys_stats["alpha"],
        "physics_reg": phys_stats["reg"],
        "physics_enable": int(phys_stats["enabled"]),
        "train_edge": summary.get("edge", 0.0),
        "train_edge_profile": summary.get("edge_profile", 0.0),
        "train_edge_profile_w": summary.get("edge_profile", 0.0) * float(w_edge_profile),
        "train_edge_ori": summary.get("edge_ori", 0.0),
        "train_edge_ori_w": summary.get("edge_ori", 0.0) * float(w_edge_ori),
        "train_edge_chamfer_raw": summary.get("edge_chamfer", 0.0),
        "train_edge_chamfer_w": summary.get("edge_chamfer", 0.0) * float(w_edge_chamfer),
        "train_fft": summary.get("fft", 0.0),
        "train_cb": summary.get("cb", 0.0),
        "train_hf_ratio": summary.get("hf_ratio", 0.0),
        "val_edge_profile_w": val_m.get("edge_profile", 0.0) * float(w_edge_profile),
        "val_edge_ori": val_m.get("edge_ori", 0.0),
        "val_edge_ori_w": val_m.get("edge_ori", 0.0) * float(w_edge_ori),
        "val_edge_chamfer_raw": val_m.get("edge_chamfer_raw", 0.0),
        "val_edge_chamfer_w": val_m.get("edge_chamfer_w", 0.0),
        "val_fft": val_m.get("fft", 0.0),
        "weak_psf_enable": int(CFG.WEAK_PSF_ENABLE),
        "chamfer_enable": int(float(w_edge_chamfer) > 0.0),
    })

    gmf_obj = compute_gmf_obj(summary)
    summary["gmf_obj"] = gmf_obj if gmf_obj is not None else np.nan
    if gmf_obj is not None and np.isfinite(gmf_obj):
        print(f"[GMF_OBJ][E{epoch1:03d}] gmf_obj={gmf_obj:.4f}")
        if (best_gmf_obj is None) or (gmf_obj > best_gmf_obj):
            best_gmf_obj = float(gmf_obj)

    _, gmf_components = compute_gmf_fitness(summary, epoch_summaries)
    if gmf_components:
        summary.update(gmf_components)
        summary["best_score"] = summary.get("gmf_obj", summary["gmf_fitness"])
        summary["best_z_score_mean"] = summary["gmf_z_proxy_mean"]
        summary["best_z_score_p10"] = summary["gmf_z_gain_p10"]
        summary["best_z_pos_std"] = summary["gmf_z_step_std"]
        summary["best_z_step_err"] = summary["gmf_z_step_mean_err"]
        print(
            f"[GMF_FIT][E{epoch1:03d}] fitness={summary['gmf_fitness']:.4f} "
            f"z_std={summary['gmf_z_step_std']:.3f} z_out={summary['gmf_z_outlier']:.3f} "
            f"z_err={summary['gmf_z_step_mean_err']:.3f} z_gain={summary['gmf_z_gain_p10']:.3f} "
            f"z_proxy={summary['gmf_z_proxy_mean']:.3f}"
        )
        CFG.GMF_FITNESS_LAST = float(summary["gmf_fitness"])

    if CFG.GMF_VALIDATE_ENABLE and (not collapse):
        invalid_rate = summary.get("proxy_invalid_rate", 0.0)
        if (np.isfinite(invalid_rate) and invalid_rate > float(CFG.PROXY_INVALID_RATE_MAX)) or \
           (np.isfinite(summary.get("gmf_z_step_std", np.nan)) and summary["gmf_z_step_std"] > float(CFG.GMF_Z_BAD)) or \
           (np.isfinite(summary.get("gmf_z_outlier", np.nan)) and summary["gmf_z_outlier"] > float(CFG.GMF_Z_BAD)):
            print("[SIMPLETEST][CTRL_OFF] Proxy quality low/invalid detected; geom/LR controls disabled.")

    step_err = summary.get("proxy_step_err", np.nan)
    pos_std_sum = summary.get("proxy_pos_step_std_sum", np.nan)
    gmf_kpi_worse = False
    if prev_proxy_step_err is not None and np.isfinite(prev_proxy_step_err) and np.isfinite(step_err):
        if step_err > prev_proxy_step_err + float(CFG.GMF_STEPERR_TIE_EPS):
            gmf_kpi_worse = True
    if prev_proxy_pos_std_sum is not None and np.isfinite(prev_proxy_pos_std_sum) and np.isfinite(pos_std_sum):
        if pos_std_sum > prev_proxy_pos_std_sum + float(CFG.GMF_STD_TIE_EPS):
            gmf_kpi_worse = True
    if gmf_kpi_worse:
        print("[SIMPLETEST][CTRL_OFF] GMF KPI worsened; artifact multiplier control disabled.")

    gmf_bad = False
    if np.isfinite(step_err) and step_err > float(CFG.GMF_STEP_ERR_CAP):
        gmf_bad = True
    if np.isfinite(pos_std_sum) and pos_std_sum > float(CFG.GMF_POS_STD_CAP):
        gmf_bad = True
    gmf_obj_curr = summary.get("gmf_obj", np.nan)
    if (prev_gmf_obj is not None) and np.isfinite(prev_gmf_obj) and np.isfinite(gmf_obj_curr):
        if gmf_obj_curr < prev_gmf_obj - float(CFG.GMF_OBJ_BAD_DELTA):
            gmf_bad = True
    if np.isfinite(val_m["rec"]) and (prev_val_rec is not None) and np.isfinite(prev_val_rec):
        if val_m["rec"] > prev_val_rec * (1.0 + float(CFG.GMF_REC_BAD_DELTA)):
            gmf_bad = True

    if gmf_bad:
        gmf_bad_streak += 1
    else:
        gmf_bad_streak = 0
    if gmf_bad_streak >= int(CFG.GMF_BAD_STREAK):
        print("[SIMPLETEST][CTRL_OFF] GMF_BAD triggered; LR/geom decay disabled.")
        gmf_bad_streak = 0

    if np.isfinite(step_err):
        prev_proxy_step_err = float(step_err)
    if np.isfinite(pos_std_sum):
        prev_proxy_pos_std_sum = float(pos_std_sum)
    if np.isfinite(gmf_obj_curr):
        prev_gmf_obj = float(gmf_obj_curr)

    scale_std_s = "disabled"
    scale_dev_s = "disabled"
    if CFG.PROXY_SCALE_ENABLE:
        scale_std_s = f"{summary['proxy_scale_std']:.6f}"
        scale_dev_s = f"{summary['proxy_scale_dev']:.6f}"
    print(
        f"[RANK][E{epoch1:03d}] tuple=("
        f"pass={summary['proxy_score_pass_rate']:.1f}%, "
        f"p10={summary['proxy_score_p10']:.2f}, "
        f"pos_std_sum={pos_std_sum:.4f}, "
        f"scale_std={scale_std_s}, "
        f"scale_dev={scale_dev_s}, "
        f"step_err={summary['proxy_step_err']:.4f}, "
        f"rec={val_m['rec']:.6f}, "
        f"ssim={val_m['ssim']:.4f})"
    )
    print(
        f"[RANK_EXTRA][E{epoch1:03d}] "
        f"edge_dens_sr/raw={summary['proxy_edge_density_sr_mean']:.3f}/"
        f"{summary['proxy_edge_density_model']:.3f} "
        f"match={summary['proxy_match_ratio_mean']:.3f} "
        f"ori={summary['proxy_ori_ratio_mean']:.3f} "
        f"hist_sim={summary['proxy_hist_sim']:.3f} "
        f"invalid={summary['proxy_invalid_count']} ({summary['proxy_invalid_rate']:.2f}) "
        f"dens_bad={summary['proxy_invalid_density']}"
    )
    print(
        f"[GMF_SUMMARY][E{epoch1:03d}] stage={psf_sched.get('stage', 'na')} "
        f"gmf_obj={summary.get('gmf_obj', 0.0):.4f} "
        f"gmf={summary.get('gmf_fitness', 0.0):.4f} "
        f"step_std={summary.get('kpi_step_std', 0.0):.4f} "
        f"outlier={summary.get('kpi_outlier_rate', 0.0):.4f} "
        f"step_err={summary.get('kpi_step_mean_err', 0.0):.4f} "
        f"gain_p10={summary.get('proxy_gain_p10', 0.0):.4f} "
        f"top1={summary.get('weak_psf_top1_ratio', 0.0):.3f} "
        f"entropy={summary.get('weak_psf_entropy', 0.0):.3f} "
        f"beta_scale={summary.get('weak_psf_beta_scale', 0.0):.3f} "
        f"beta_eff={summary.get('weak_psf_beta_eff', 0.0):.4f} "
        f"gate={psf_sched.get('gate_scale', 1.0):.2f} "
        f"freeze={psf_sched.get('gate_freeze', False)}"
    )

    if CFG.WEAK_PSF_ENABLE:
        delta_std = summary.get("kpi_step_std_delta", 0.0)
        delta_out = summary.get("kpi_outlier_rate_delta", 0.0)
        bad = np.isfinite(delta_std) and np.isfinite(delta_out) and (delta_std > 0.0) and (delta_out > 0.0)
        if bad:
            gmf_gate_bad_count += 1
            print(
                f"[GMF_GATE][E{epoch1:03d}] bad_ab=True count={gmf_gate_bad_count} "
                f"gate_scale={gmf_gate_scale:.3f} freeze=False (log-only)"
            )
        else:
            gmf_gate_bad_count = 0

    return (
        weak_stats,
        best_gmf_obj,
        gmf_bad_streak,
        prev_proxy_step_err,
        prev_proxy_pos_std_sum,
        prev_gmf_obj,
        gmf_gate_bad_count,
    )


def _evaluate_self_band_guard(epoch1: int, self_band_ready: bool, self_band_edge_score_hist, self_band_edge_width_hist, self_band_hf_proxy_hist,
                              edge_score_curr: float, metric_edge: float, metric_hf: float, artifact_spike: bool,
                              band_guard_hold: int, lap_boost_hold: int) -> Tuple[bool, int, int]:
    band_guard_triggered_epoch = False
    if self_band_ready:
        base_score = _hist_mean(self_band_edge_score_hist)
        base_edge_w = _hist_mean(self_band_edge_width_hist)
        base_hf = _hist_mean(self_band_hf_proxy_hist)
        cond_score = np.isfinite(edge_score_curr) and np.isfinite(base_score) and (edge_score_curr < base_score * float(CFG.SELF_BAND_EDGE_SCORE_MIN_RATIO))
        cond_edge_w = np.isfinite(metric_edge) and np.isfinite(base_edge_w) and (metric_edge > base_edge_w * float(CFG.SELF_BAND_EDGE_WIDTH_MAX_RATIO))
        cond_hf_low = np.isfinite(metric_hf) and np.isfinite(base_hf) and (metric_hf < base_hf * float(CFG.SELF_BAND_HF_PROXY_MIN_RATIO))
        band_guard_triggered_epoch = bool(cond_score or cond_edge_w or cond_hf_low)
        if band_guard_triggered_epoch:
            band_guard_hold = max(band_guard_hold, int(CFG.SELF_BAND_GUARD_HOLD_EPOCHS))
            if not artifact_spike:
                lap_boost_hold = max(lap_boost_hold, int(CFG.SELF_BAND_DETAIL_RESCUE_EPOCHS))
            print(
                f"[GUARD][BAND][E{epoch1:03d}] trigger hold={band_guard_hold} "
                f"score={edge_score_curr:.4f}/{base_score:.4f} "
                f"edgeW={metric_edge:.4f}/{base_edge_w:.4f} "
                f"hf={metric_hf:.4f}/{base_hf:.4f} "
                f"lap_boost={'off' if artifact_spike else f'on({lap_boost_hold})'}"
            )
    return band_guard_triggered_epoch, band_guard_hold, lap_boost_hold


def _update_detail_rescue_state(epoch1: int, metric_edge: float, edge_width_ref: float, metric_hf: float, hf_proxy_ref: float, metric_cb: float, cb_ref: float,
                                thicken_triggered_epoch: bool, rescue_triggered_epoch: bool, rescue_active_epoch: bool,
                                detail_rescue_mult: float, detail_rescue_hold: int) -> Tuple[float, int]:
    if not bool(getattr(CFG, "DETAIL_RESCUE_ENABLE", True)):
        return detail_rescue_mult, detail_rescue_hold
    rescue_start = int(getattr(CFG, "DETAIL_RESCUE_START_E", 0))
    rescue_end = int(getattr(CFG, "DETAIL_RESCUE_END_E", 0))
    in_rescue_window = (epoch1 >= rescue_start) and (epoch1 <= rescue_end)
    detail_trigger = bool((thicken_triggered_epoch or rescue_triggered_epoch or rescue_active_epoch) and in_rescue_window)
    if detail_trigger:
        target_mult = float(getattr(CFG, "DETAIL_RESCUE_MULT", 1.25))
        target_mult = max(target_mult, float(getattr(CFG, "RESCUE_DETAIL_MULT", target_mult)))
        detail_rescue_mult = max(detail_rescue_mult, target_mult)
        detail_rescue_hold = max(detail_rescue_hold, int(getattr(CFG, "DETAIL_RESCUE_HOLD_EPOCHS", 4)))
        print(f"[RESCUE_DETAIL][E{epoch1:03d}] mult={detail_rescue_mult:.3f} hold={detail_rescue_hold}")
    else:
        if detail_rescue_hold > 0:
            detail_rescue_hold -= 1
        else:
            edge_ok = True
            hf_ok = True
            edge_rel = float(getattr(CFG, "DETAIL_RESCUE_RELEASE_EDGE_REL", 0.02))
            hf_rel = float(getattr(CFG, "DETAIL_RESCUE_RELEASE_HF_REL", 0.02))
            if np.isfinite(metric_edge) and np.isfinite(edge_width_ref) and edge_width_ref > 1e-8:
                edge_ok = metric_edge <= edge_width_ref * (1.0 + edge_rel)
            if np.isfinite(metric_hf) and np.isfinite(hf_proxy_ref) and hf_proxy_ref > 1e-8:
                hf_ok = metric_hf >= hf_proxy_ref * (1.0 - hf_rel)
            if not in_rescue_window:
                edge_ok = True
                hf_ok = True
            if (detail_rescue_mult > 1.0) and edge_ok and hf_ok:
                detail_rescue_mult = max(
                    1.0,
                    detail_rescue_mult - float(getattr(CFG, "DETAIL_RESCUE_RELEASE_STEP", 0.05)),
                )
    if np.isfinite(metric_cb) and np.isfinite(cb_ref):
        cb_rel = float(getattr(CFG, "DETAIL_CB_UP_REL", 0.12))
        if (detail_rescue_mult > 1.0) and (metric_cb > cb_ref * (1.0 + cb_rel)):
            detail_rescue_mult = max(
                float(getattr(CFG, "DETAIL_CB_MIN_MULT", 0.5)),
                detail_rescue_mult - float(getattr(CFG, "DETAIL_CB_REDUCE_STEP", 0.25)),
            )
    return detail_rescue_mult, detail_rescue_hold


def _apply_guard_trigger_holds(epoch1: int, artifact_spike: bool, band_guard_triggered_epoch: bool, thicken_triggered_epoch: bool, oversmooth_triggered_epoch: bool,
                               band_guard_hold: int, lap_guard_hold: int, psf_guard_hold: int) -> Tuple[int, int, int]:
    if band_guard_triggered_epoch and band_guard_hold <= 0:
        band_guard_hold = int(CFG.SELF_BAND_GUARD_HOLD_EPOCHS)
    if thicken_triggered_epoch or oversmooth_triggered_epoch or band_guard_triggered_epoch:
        lap_guard_hold = max(lap_guard_hold, int(CFG.EDGELOCAL_LAP_GUARD_EPOCHS))
        print(
            f"[GUARD][LAP][E{epoch1:03d}] hold={lap_guard_hold} "
            f"reason={'thicken' if thicken_triggered_epoch else ('oversmooth' if oversmooth_triggered_epoch else 'band_guard')}"
        )
    psf_spike_gate = (epoch1 > int(getattr(CFG, "PSF_GUARD_MAX_EPOCHS", 10))) and artifact_spike
    if bool(getattr(CFG, "ENABLE_PSF_GUARD_ONLY", False)) and bool(getattr(CFG, "PSF_GUARD_ON_ARTIFACT_SPIKE", True)):
        if psf_spike_gate:
            psf_guard_hold = max(psf_guard_hold, int(getattr(CFG, "PSF_GUARD_HOLD_EPOCHS", 3)))
            print(f"[GUARD][PSF][E{epoch1:03d}] artifact spike -> hold={psf_guard_hold}")
    return band_guard_hold, lap_guard_hold, psf_guard_hold


def _decay_guard_and_rescue_counters(epoch1: int, artifact_spike: bool, band_guard_triggered_epoch: bool, thicken_triggered_epoch: bool, oversmooth_triggered_epoch: bool,
                                     psf_force_triggered_epoch: bool, rescue_remaining: int, rescue_lr_mult: float, rescue_eq_mult: float, rescue_cooldown: int,
                                     band_guard_hold: int, lap_guard_hold: int, lap_boost_hold: int, psf_guard_hold: int,
                                     psf_force_hold: int) -> Tuple[int, float, float, int, int, int, int, int, int]:
    if rescue_remaining > 0:
        rescue_remaining -= 1
    if rescue_remaining <= 0:
        if rescue_lr_mult < 1.0:
            rescue_lr_mult = min(1.0, rescue_lr_mult + float(getattr(CFG, "RESCUE_LR_RELEASE_STEP", 0.05)))
        if rescue_eq_mult < 1.0:
            rescue_eq_mult = min(1.0, rescue_eq_mult + float(getattr(CFG, "RESCUE_EQ_RELEASE_STEP", 0.05)))
    if rescue_cooldown > 0:
        rescue_cooldown -= 1
    if (band_guard_hold > 0) and (not band_guard_triggered_epoch):
        band_guard_hold -= 1
    if (lap_guard_hold > 0) and (not (thicken_triggered_epoch or oversmooth_triggered_epoch or band_guard_triggered_epoch)):
        lap_guard_hold -= 1
    if (lap_boost_hold > 0) and (not band_guard_triggered_epoch):
        lap_boost_hold -= 1
    psf_spike_gate = (epoch1 > int(getattr(CFG, "PSF_GUARD_MAX_EPOCHS", 10))) and artifact_spike
    if (psf_guard_hold > 0) and (not psf_spike_gate):
        psf_guard_hold -= 1
    if (psf_force_hold > 0) and (not psf_force_triggered_epoch):
        psf_force_hold -= 1
    return rescue_remaining, rescue_lr_mult, rescue_eq_mult, rescue_cooldown, band_guard_hold, lap_guard_hold, lap_boost_hold, psf_guard_hold, psf_force_hold


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--attrib_window", type=int, default=None, help="Attribution rolling window")
    p.add_argument("--attrib_every", type=int, default=None, help="Attribution logging interval")
    p.add_argument("--seed_deterministic", action="store_true", help="Enable deterministic/repro mode (slower).")
    p.add_argument("--force_fast_eval", action="store_true", help="Force slower validations to run less often.")
    return p.parse_args()

def run_one_seed(seed: int, args: Optional[argparse.Namespace] = None):
    if args is None:
        args = parse_args()
    _apply_cli_overrides(args)
    seed, use_amp = _prepare_seed_run(seed)
    attrib_path = os.path.join(PROGRESS_DIR, "attribution_log.txt")
    init_attrib_log(attrib_path)
    expect_dx = CFG.GMF_EXPECT_DX_PX
    expect_dy = CFG.GMF_EXPECT_DY_PX
    expected_step_px = 0.0
    expected_enable = 0
    if (expect_dx is not None) and (expect_dy is not None) and np.isfinite(expect_dx) and np.isfinite(expect_dy):
        expected_step_px = float(np.sqrt(float(expect_dx) ** 2 + float(expect_dy) ** 2))
        expected_enable = 1
    outlier_t = float(CFG.GMF_OUTLIER_T)
    if expected_enable and float(CFG.GMF_OUTLIER_T_REL) > 0.0:
        outlier_t = max(outlier_t, expected_step_px * float(CFG.GMF_OUTLIER_T_REL))
    print(f"[GMF_KPI] expect_dx_px={expect_dx} expect_dy_px={expect_dy} "
          f"expected_step_px={expected_step_px:.6f} outlier_t={outlier_t:.6f} "
          f"outlier_t_rel={float(CFG.GMF_OUTLIER_T_REL):.6f}")

    # Model
    model = _build_model_from_cfg()
    ema_model = init_ema_model(model) if bool(getattr(CFG, "EMA_ENABLE", False)) else None

    # Pre-flight integrity validation (Hard Check 1)
    if CFG.RUN_PREFLIGHT_SANITY:
        run_preflight_sanity_check(CFG.DEVICE)
    else:
        print("[INFO] Pre-flight sanity check disabled.")

    if CFG.use_compile:
        print("[INFO] torch.compile disabled for dynamic shapes; running in eager mode.")

    phys_ok, phys_reason = _psf_forward_available(model)
    phys_forward_runtime = bool(CFG.PHYS_FORWARD_ENABLE) and bool(phys_ok)
    if not phys_forward_runtime:
        if bool(CFG.PHYS_FORWARD_ENABLE):
            print(f"[PHYS] disabled: psf forward op not found ({phys_reason})")
        else:
            print("[PHYS] disabled: PHYS_FORWARD_ENABLE=False")

    # Loss fns
    huber = nn.HuberLoss()
    ssim = StructuralSimilarityIndexMeasure(data_range=1.0).to(CFG.DEVICE)
    optimizer = _build_optimizer(model)

    scaler = torch.cuda.amp.GradScaler(enabled=use_amp and torch.cuda.is_available())

    # Data
    train_loader, val_loader = make_train_val_loaders()
    _log_data_and_loss_setup(train_loader, val_loader, phys_forward_runtime)

    # Monitor
    monitor_src, edge_width_ref, hf_proxy_ref, cb_ref = _init_monitor_reference(model, ema_model)

    # Resume
    best_proxy = None
    best_val_rec = None
    best_val_ssim = None
    best_epoch = None
    best_detail = None
    prev_proxy_step_err = None
    prev_proxy_pos_std_sum = None
    gmf_bad_streak = 0
    prev_gmf_obj = None
    prev_total = None
    prev_edge_profile = None
    prev_edge_chamfer = None
    prev_val_rec = None
    last_good_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_last_good.pth.tar")
    last_good_ema_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_last_good_ema.pth.tar")
    last_good_ckpt = None
    last_good_ema_ckpt = None
    cap_spike_left = 0
    cap_spike_cooldown = 0
    cap_hf_hist = deque(maxlen=max(2, int(CFG.CAP_SPIKE_WINDOW)))
    cap_cb_hist = deque(maxlen=max(2, int(CFG.CAP_SPIKE_WINDOW)))
    thicken_guard_mult = 1.0
    thicken_guard_hold = 0
    thicken_guard_hits = 0
    band_guard_hold = 0
    lap_guard_hold = 0
    lap_boost_hold = 0
    psf_guard_hold = 0
    psf_force_hold = 0
    last_thicken_trigger = False
    last_oversmooth_trigger = False
    last_lap_guard_flag = False
    last_psf_guard_flag = False
    last_psf_force_freeze = False
    self_band_edge_score_hist = []
    self_band_edge_width_hist = []
    self_band_hf_proxy_hist = []
    self_band_ready = False
    recent_hf_hist = deque(maxlen=max(3, int(CFG.CAP_SPIKE_WINDOW)))
    recent_cb_hist = deque(maxlen=max(3, int(CFG.CAP_SPIKE_WINDOW)))
    rescue_remaining = 0
    rescue_lr_mult = 1.0
    rescue_eq_mult = 1.0
    rescue_cooldown = 0
    detail_rescue_mult = 1.0
    detail_rescue_hold = 0
    fail_flag_global = 0
    stop_after_epoch = False
    thicken_triggered_epoch = False
    best_gmf_obj = None

    start_epoch = _resume_training_state(model, optimizer, ema_model)

    # CSV logger (train batch log)
    csv_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_batch_log_v5.csv")
    csv_f, csv_w = _open_csv_logger(csv_path, _BATCH_LOG_HEADER_V5)

    # Val epoch log
    val_csv_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_val_log_v5.csv")
    val_csv_f, val_csv_w = _open_csv_logger(val_csv_path, _VAL_LOG_HEADER_V5)

    epoch_summaries = []
    gmf_gate_scale = 1.0
    gmf_gate_bad_count = 0
    fast_io_mode = bool(CFG.FAST_IO_MODE)
    fast_monitor_every = max(1, int(CFG.FAST_MONITOR_EVERY_EPOCH)) if fast_io_mode else 1
    fast_val_every = max(1, int(CFG.FAST_VAL_EVERY_EPOCH)) if fast_io_mode else 1
    fast_plot_every = max(1, int(CFG.FAST_PLOT_EVERY_EPOCH))
    total_epochs = int(CFG.SIMPLETEST_MAX_EPOCH if CFG.SIMPLETEST_MODE else CFG.NUM_EPOCH)
    print("[SCHED_SUMMARY][SIMPLETEST] rec/grad/ori fixed; eq uses geometry-only ramp")
    print("[SCHED_SUMMARY][SIMPLETEST] eq: E1-5 off, E6-20 ramp->1, E21-40=1, E41-100 fade->0.4")
    print("[SCHED_SUMMARY][SIMPLETEST] intensity-eq off; thicken/self-band/lap/psf guards active")
    chk_epochs = [1, 5, 6, 20, 21, 40, 41, 100]
    for e_chk in chk_epochs:
        print(
            f"[SELF_CHECK][E{e_chk:03d}] "
            f"consistency_factor={get_consistency_factor(e_chk):.4f} "
            f"eq_factor={get_eq_factor(e_chk):.4f}"
        )

    try:
        for epoch in range(start_epoch, total_epochs):
            epoch1 = epoch + 1
            w_rec, _w_eq, _w_edge, w_edge_profile, w_edge_ori, w_edge_chamfer, w_ssim, *_ = get_epoch_weights(epoch1)
            ctrl = _compute_epoch_runtime_controls(
                epoch1=epoch1,
                rescue_remaining=rescue_remaining,
                band_guard_hold=band_guard_hold,
                thicken_guard_mult=thicken_guard_mult,
                detail_rescue_mult=detail_rescue_mult,
                rescue_eq_mult=rescue_eq_mult,
                cap_spike_left=cap_spike_left,
                thicken_guard_hold=thicken_guard_hold,
                last_thicken_trigger=last_thicken_trigger,
                lap_guard_hold=lap_guard_hold,
                lap_boost_hold=lap_boost_hold,
                psf_force_hold=psf_force_hold,
                psf_guard_hold=psf_guard_hold,
            )
            rescue_active_epoch = bool(ctrl["rescue_active_epoch"])
            rescue_flag_epoch = int(ctrl["rescue_flag_epoch"])
            guard_mult_epoch = float(ctrl["guard_mult_epoch"])
            consist_factor_eff = float(ctrl["consist_factor_eff"])
            detail_rescue_mult_epoch = float(ctrl["detail_rescue_mult_epoch"])
            detail_rescue_active_epoch = bool(ctrl["detail_rescue_active_epoch"])
            edge_profile_mult_epoch = float(ctrl["edge_profile_mult_epoch"])
            eq_factor_epoch = float(ctrl["eq_factor_epoch"])
            eq_intensity_mode = str(ctrl["eq_intensity_mode"])
            eq_intensity_weight_effective = float(ctrl["eq_intensity_weight_effective"])
            eq_disable_intensity = bool(ctrl["eq_disable_intensity"])
            cap_base_factor = float(ctrl["cap_base_factor"])
            cap_spike_factor = float(ctrl["cap_spike_factor"])
            cap_factor_epoch = float(ctrl["cap_factor_epoch"])
            w_smooth = float(ctrl["w_smooth"])
            w_consistency = float(ctrl["w_consistency"])
            w_cap_eff = float(ctrl["w_cap_eff"])
            eq_shift_override = ctrl["eq_shift_override"]
            w_edge_local_lap_epoch = float(ctrl["w_edge_local_lap_epoch"])
            psf_force_freeze_epoch = bool(ctrl["psf_force_freeze_epoch"])
            psf_guard_active_epoch = bool(ctrl["psf_guard_active_epoch"])
            psf_guard_lr = float(ctrl["psf_guard_lr"])

            _log_epoch_start(
                epoch1=epoch1,
                total_epochs=total_epochs,
                w_rec=w_rec,
                w_ssim=w_ssim,
                w_edge_local_lap_epoch=w_edge_local_lap_epoch,
                eq_factor_epoch=eq_factor_epoch,
                eq_disable_intensity=eq_disable_intensity,
                consist_factor_eff=consist_factor_eff,
                rescue_flag_epoch=rescue_flag_epoch,
                rescue_remaining=rescue_remaining,
                thicken_guard_hold=thicken_guard_hold,
                guard_mult_epoch=guard_mult_epoch,
                rescue_lr_mult=rescue_lr_mult,
                rescue_eq_mult=rescue_eq_mult,
                phys_forward_runtime=bool(phys_forward_runtime),
            )
    
            psf_sched = apply_weak_psf_schedule(
                model,
                epoch1,
                gate_scale=gmf_gate_scale,
                gate_freeze=False,
                guard_active=psf_guard_active_epoch,
                guard_lr_mult=psf_guard_lr,
                force_freeze=psf_force_freeze_epoch,
            )
            apply_lr_multipliers(optimizer, rescue_lr_mult, psf_mult=psf_sched.get("lr_mult", 0.0))
            eval_model = ema_model if ema_model is not None else model
            if psf_sched["stage"] == "none":
                if epoch1 <= CFG.FREEZE_PHYSICS_EPOCH:
                    print(f"[INFO] physics_layer frozen (epoch {epoch1}/{CFG.FREEZE_PHYSICS_EPOCH})")
                elif epoch1 == (CFG.FREEZE_PHYSICS_EPOCH + 1):
                    print("[INFO] physics_layer unfrozen. Train full model.")
            else:
                print(
                    f"[WEAK_PSF][E{epoch1:03d}] stage={psf_sched['stage']} "
                    f"beta_scale={psf_sched['beta_scale']:.4f} entropy_mix={psf_sched['entropy_mix']:.4f} "
                    f"physics_frozen={psf_sched['physics_frozen']} weak_frozen={psf_sched['weak_frozen']} "
                    f"gate_scale={psf_sched.get('gate_scale', 1.0):.2f} gate_freeze={psf_sched.get('gate_freeze', False)} "
                    f"psf_guard={int(psf_sched.get('psf_guard_active', False))} lr_mult={psf_sched.get('lr_mult', 0.0):.2f}"
                )
    
            summary = train_one_epoch(
                model, train_loader, optimizer, scaler, huber, ssim,
                epoch, csv_w, csv_f, 1.0, 1.0,
                1.0, 1.0, 1.0, edge_profile_mult_epoch, 1.0,
                consist_factor_eff, cap_base_factor, cap_spike_factor, guard_mult_epoch,
                eq_disable_intensity, eq_intensity_weight_effective, eq_factor_epoch,
                detail_rescue_mult=detail_rescue_mult_epoch,
                eq_shift_override=eq_shift_override,
                phys_forward_runtime=bool(phys_forward_runtime),
                w_edge_local_lap_epoch=float(w_edge_local_lap_epoch),
                enable_edge_local_lap=bool(CFG.ENABLE_EDGELOCAL_LAPLACIAN),
                ema_model=ema_model,
                ema_decay=float(getattr(CFG, "EMA_DECAY", 0.0)) if ema_model is not None else 0.0,
            )
            summary["sched_consist_factor"] = float(consist_factor_eff)
            summary["sched_cap_factor"] = float(cap_factor_epoch)
            summary["guard_thicken_mult"] = float(guard_mult_epoch)
            summary["guard_thicken_hold"] = int(thicken_guard_hold)
            summary["consistency_factor"] = float(consist_factor_eff)
            summary["w_rec"] = float(CFG.W_REC)
            summary["w_consistency_eff"] = float(w_consistency)
            summary["w_smooth_eff"] = float(w_smooth)
            summary["w_cap_eff"] = float(w_cap_eff)
            summary["w_edgeLocalLap"] = float(w_edge_local_lap_epoch)
            summary["detail_rescue_mult"] = float(detail_rescue_mult_epoch)
            summary["eq_disable_intensity"] = int(eq_disable_intensity)
            summary["eq_intensity_mode"] = str(eq_intensity_mode)
            summary["eq_intensity_weight_effective"] = float(eq_intensity_weight_effective)
            summary["eq_prob"] = float(getattr(CFG, "EQ_PROB", 1.0))
            summary["seed"] = int(getattr(CFG, "SEED_ACTIVE", 0))
            summary["flag_thicken_guard"] = int(last_thicken_trigger)
            summary["flag_oversmooth_guard"] = int(last_oversmooth_trigger)
            summary["flag_lap_guard"] = int(last_lap_guard_flag)
            summary["flag_psf_guard"] = int(psf_sched.get("psf_guard_active", False))
            summary["rescue_flag"] = int(rescue_flag_epoch)
            summary["fail_flag"] = int(fail_flag_global)
    
            rec_w = float(CFG.W_REC) * float(summary.get("rec", 0.0))
            grad_w = float(CFG.W_GRADMAG) * float(summary.get("gradmag", 0.0))
            ori_w = float(CFG.W_EDGE_ORI_SIMPLE) * float(summary.get("edge_ori", 0.0))
            eq_w = float(summary.get("eq_total", 0.0))
            loss_core = max(1e-12, rec_w + grad_w + ori_w + eq_w)
            print(
                f"[SIMPLETEST][E{epoch1:03d}] "
                f"Rec={summary.get('rec', 0.0):.6f} ({100.0 * rec_w / loss_core:.1f}%) "
                f"GradMag={summary.get('gradmag', 0.0):.6f} ({100.0 * grad_w / loss_core:.1f}%) "
                f"EdgeOri={summary.get('edge_ori', 0.0):.6f} ({100.0 * ori_w / loss_core:.1f}%) "
                f"EqGeom={summary.get('eq_total', 0.0):.6f} ({100.0 * eq_w / loss_core:.1f}%) "
                f"Total={summary.get('total', 0.0):.6f} time={summary.get('sec', 0.0):.1f}s"
            )
            print(
                f"[EQ][SIMPLETEST] factor={summary.get('eq_factor', 0.0):.3f} "
                f"shift_range={summary.get('eq_shift_range', 'na')} "
                f"intensity_eq_disabled=1"
            )
    
            weak_stats = get_weak_psf_stats(model)
            if weak_stats["enabled"]:
                print(
                    f"[WEAK_PSF][E{epoch1:03d}] beta={weak_stats['beta']:.5f} "
                    f"entropy={weak_stats['entropy']:.4f} top1={weak_stats['top1_ratio']:.4f} "
                    f"gate_scale={psf_sched.get('gate_scale', 1.0):.2f} "
                    f"freeze={int(psf_sched.get('weak_frozen', False))} "
                    f"bypass={weak_stats['bypass']}"
                )
    
            monitor_stats = None
            collapse = False
            spike = False
            if (monitor_src is not None) and CFG.SAVE_MONITOR_EVERY_EPOCH:
                save_monitor_outputs = True
                if fast_io_mode:
                    save_monitor_outputs = (epoch1 == 1) or ((epoch1 % fast_monitor_every) == 0)
                monitor_stats = save_monitor(
                    eval_model,
                    monitor_src,
                    epoch,
                    save_outputs=save_monitor_outputs,
                    verbose=(not fast_io_mode) or save_monitor_outputs,
                )
                if monitor_stats["sat"] > float(CFG.COLLAPSE_SAT_THRESH):
                    collapse = True
                if monitor_stats["std"] < float(CFG.COLLAPSE_STD_MIN):
                    collapse = True
                if monitor_stats["hf_ratio"] > float(CFG.COLLAPSE_HF_RATIO_MAX):
                    collapse = True
            else:
                if summary["sr_sat"] > float(CFG.COLLAPSE_SAT_THRESH):
                    collapse = True
                if summary["sr_std"] < float(CFG.COLLAPSE_STD_MIN):
                    collapse = True
                if summary["hf_ratio"] > float(CFG.COLLAPSE_HF_RATIO_MAX):
                    collapse = True
            print(
                f"[SIMPLETEST_V2][MON] pred_mean={summary.get('pred_mean_mask', np.nan):.6f} "
                f"pred_std={summary.get('pred_std_mask', np.nan):.6f} "
                f"bandE_pred={summary.get('bandE_pred', np.nan):.6e} "
                f"bandE_gt={summary.get('bandE_gt', np.nan):.6e} "
                f"loss_stat={summary.get('loss_stat', np.nan):.6f} "
                f"loss_band={summary.get('loss_band', np.nan):.6f} "
                f"loss_hf_lap={summary.get('loss_hf_lap', np.nan):.6f} "
                f"loss_phys={summary.get('loss_phys', np.nan):.6f} "
                f"loss_edgeLocalLap={summary.get('loss_edgeLocalLap', np.nan):.6f} "
                f"loss_detail={summary.get('loss_detail', np.nan):.6f} "
                f"w_edgeLocalLap={summary.get('w_edgeLocalLap', np.nan):.3f}"
            )
    
            if prev_total is not None and np.isfinite(summary["total"]):
                if summary["total"] > prev_total * 2.0:
                    spike = True
            if prev_edge_profile is not None and np.isfinite(summary["edge_profile"]):
                if summary["edge_profile"] > prev_edge_profile * 2.0:
                    spike = True
            if np.isfinite(summary.get("edge_profile_p99", np.nan)):
                if summary["edge_profile_p99"] > float(CFG.EDGE_PROFILE_CAP) * 2.0:
                    spike = True
            if prev_edge_chamfer is not None and np.isfinite(summary["edge_chamfer"]):
                if summary["edge_chamfer"] > prev_edge_chamfer * 2.0:
                    spike = True
            if np.isfinite(summary.get("edge_chamfer", np.nan)):
                if summary["edge_chamfer"] > float(CFG.EDGE_CHAMFER_CAP) * 2.0:
                    spike = True
    
            if collapse or spike:
                print("[SIMPLETEST][CTRL_OFF] collapse/spike detected; LR/geom/weak_psf controls are disabled.")
            else:
                last_good_ckpt = {"state_dict": model.state_dict(), "optimizer": optimizer.state_dict(), "epoch": epoch1}
                if bool(getattr(CFG, "SAVE_LAST_GOOD_TO_DISK", False)):
                    save_ckpt(last_good_ckpt, last_good_path)
                if ema_model is not None:
                    last_good_ema_ckpt = {"state_dict": ema_model.state_dict(), "epoch": epoch1}
                    if bool(getattr(CFG, "SAVE_LAST_GOOD_TO_DISK", False)):
                        save_ckpt(last_good_ema_ckpt, last_good_ema_path)
    
            if np.isfinite(summary["total"]):
                prev_total = float(summary["total"])
            if np.isfinite(summary["edge_profile"]):
                prev_edge_profile = float(summary["edge_profile"])
            if np.isfinite(summary["edge_chamfer"]):
                prev_edge_chamfer = float(summary["edge_chamfer"])
    
            # Validation
            val_m, prev_val_rec = _run_validation_epoch(
                eval_model=eval_model,
                val_loader=val_loader,
                huber=huber,
                ssim=ssim,
                epoch=epoch,
                epoch1=epoch1,
                fast_val_every=fast_val_every,
                collapse=collapse,
                prev_val_rec=prev_val_rec,
            )
            _update_val_summary_and_monitor_metrics(
                summary=summary,
                val_m=val_m,
                monitor_stats=monitor_stats,
                edge_width_ref=edge_width_ref,
                hf_proxy_ref=hf_proxy_ref,
                cb_ref=cb_ref,
            )

            proxy_m = _run_proxy_validation_epoch(
                eval_model=eval_model,
                val_loader=val_loader,
                epoch1=epoch1,
                collapse=collapse,
            )
    
            _copy_proxy_metrics(summary, proxy_m)
    
            (
                weak_stats,
                best_gmf_obj,
                gmf_bad_streak,
                prev_proxy_step_err,
                prev_proxy_pos_std_sum,
                prev_gmf_obj,
                gmf_gate_bad_count,
            ) = _update_epoch_summary_and_gmf_state(
                epoch1=epoch1,
                summary=summary,
                val_m=val_m,
                model=model,
                psf_sched=psf_sched,
                w_edge_profile=w_edge_profile,
                w_edge_ori=w_edge_ori,
                w_edge_chamfer=w_edge_chamfer,
                epoch_summaries=epoch_summaries,
                collapse=collapse,
                prev_val_rec=prev_val_rec,
                best_gmf_obj=best_gmf_obj,
                gmf_bad_streak=gmf_bad_streak,
                prev_proxy_step_err=prev_proxy_step_err,
                prev_proxy_pos_std_sum=prev_proxy_pos_std_sum,
                prev_gmf_obj=prev_gmf_obj,
                gmf_gate_bad_count=gmf_gate_bad_count,
                gmf_gate_scale=gmf_gate_scale,
            )

            metric_edge = float(summary.get("metric_edge_width", np.nan))
            metric_hf = float(summary.get("metric_hf_proxy", np.nan))
            metric_cb = float(summary.get("metric_cb_proxy", np.nan))
            edge_score_curr = float(summary.get("proxy_score_mean", np.nan))
            summary["edge_width"] = metric_edge
            summary["hf_proxy"] = metric_hf
            print(
                f"[MON_METRIC][E{epoch1:03d}] "
                f"edgeW={metric_edge:.4f} hf_proxy={metric_hf:.4f} cb={metric_cb:.6f} "
                f"pred_mean={summary.get('pred_mean_mask', np.nan):.6f} pred_std={summary.get('pred_std_mask', np.nan):.6f}"
            )
            warmup_epochs = max(1, int(getattr(CFG, "SELF_WARMUP_EPOCHS", 5)))
            if epoch1 <= warmup_epochs:
                if np.isfinite(metric_edge):
                    self_band_edge_width_hist.append(metric_edge)
                if np.isfinite(metric_hf):
                    self_band_hf_proxy_hist.append(metric_hf)
                if np.isfinite(edge_score_curr):
                    self_band_edge_score_hist.append(edge_score_curr)

            artifact_spike = _is_relative_spike(metric_hf, recent_hf_hist, 0.15, min_hist=3) or _is_relative_spike(metric_cb, recent_cb_hist, 0.15, min_hist=3)
            if np.isfinite(metric_hf):
                recent_hf_hist.append(metric_hf)
            if np.isfinite(metric_cb):
                recent_cb_hist.append(metric_cb)

            ready_epoch = max(warmup_epochs + 1, int(getattr(CFG, "SELF_BAND_READY_EPOCH", 6)))
            if (epoch1 >= ready_epoch) and (not self_band_ready):
                self_band_ready = True
                print(
                    f"[SELF_BAND] ready at E{epoch1:03d} "
                    f"base_score={_hist_mean(self_band_edge_score_hist):.4f} "
                    f"base_edgeW={_hist_mean(self_band_edge_width_hist):.4f} "
                    f"base_hf={_hist_mean(self_band_hf_proxy_hist):.4f}"
                )

            band_guard_triggered_epoch, band_guard_hold, lap_boost_hold = _evaluate_self_band_guard(
                epoch1, self_band_ready, self_band_edge_score_hist, self_band_edge_width_hist, self_band_hf_proxy_hist,
                edge_score_curr, metric_edge, metric_hf, artifact_spike, band_guard_hold, lap_boost_hold,
            )

            baseline_edge = float(edge_width_ref)
            baseline_hf = float(hf_proxy_ref)

            rescue_triggered_epoch = False
            psf_force_triggered_epoch = False
            if bool(getattr(CFG, "WEAK_PSF_GUARD_ENABLE", True)):
                cond_edge = np.isfinite(metric_edge) and np.isfinite(baseline_edge) and baseline_edge > 1e-8 and (
                    metric_edge > baseline_edge * (1.0 + float(getattr(CFG, "WEAK_PSF_GUARD_EDGE_UP_REL", 0.08)))
                )
                cond_hf = np.isfinite(metric_hf) and np.isfinite(baseline_hf) and baseline_hf > 1e-8 and (
                    metric_hf < baseline_hf * (1.0 - float(getattr(CFG, "WEAK_PSF_GUARD_HF_DROP_REL", 0.10)))
                )
                gate_target = 1.0
                if thicken_triggered_epoch or (thicken_guard_hold > 0):
                    gate_target = min(gate_target, float(getattr(CFG, "WEAK_PSF_GUARD_GATE_MULT", 0.70)))
                if rescue_active_epoch or rescue_triggered_epoch:
                    gate_target = min(gate_target, float(getattr(CFG, "WEAK_PSF_RESCUE_GATE_MULT", 0.50)))
                if cond_edge or cond_hf:
                    gate_target = min(gate_target, float(getattr(CFG, "WEAK_PSF_GUARD_GATE_MULT", 0.70)))
                gmf_gate_scale = _ema_update(gmf_gate_scale, gate_target, float(getattr(CFG, "WEAK_PSF_GATE_EMA", 0.90)))

            if weak_stats.get("enabled", False):
                entropy = float(weak_stats.get("entropy", 0.0))
                if (not np.isfinite(entropy)) or (entropy < float(getattr(CFG, "WEAK_PSF_ENTROPY_COLLAPSE_THR", 0.20))):
                    psf_force_hold = max(psf_force_hold, int(getattr(CFG, "WEAK_PSF_EXTREME_FREEZE_EPOCHS", 5)))
                    psf_force_triggered_epoch = True
                    print(f"[GUARD][WEAK_PSF][E{epoch1:03d}] extreme_freeze hold={psf_force_hold} entropy={entropy:.4f}")

            fail_flag_epoch = 0
            if bool(getattr(CFG, "ENABLE_RESCUE", True)) and (epoch1 >= int(getattr(CFG, "RESCUE_START_EPOCH", 6))):
                if (rescue_remaining <= 0) and (rescue_cooldown <= 0):
                    edge_bad = np.isfinite(metric_edge) and np.isfinite(edge_width_ref) and (metric_edge > edge_width_ref * (1.0 + float(getattr(CFG, "RESCUE_EDGEW_UP_REL", 0.10))))
                    hf_bad = np.isfinite(metric_hf) and np.isfinite(hf_proxy_ref) and (metric_hf < hf_proxy_ref * (1.0 - float(getattr(CFG, "RESCUE_HF_DROP_REL", 0.08))))
                    gmf_curr = summary.get("gmf_obj", np.nan)
                    gmf_ref = best_gmf_obj if (best_gmf_obj is not None and np.isfinite(best_gmf_obj)) else prev_gmf_obj
                    gmf_bad = False
                    if np.isfinite(gmf_curr) and np.isfinite(gmf_ref):
                        gmf_bad = (gmf_curr < (gmf_ref - float(getattr(CFG, "RESCUE_GMF_DROP_ABS", 1e-4)))) or (
                            gmf_curr < gmf_ref * (1.0 - float(getattr(CFG, "RESCUE_GMF_DROP_REL", 0.05)))
                        )
                    rescue_triggered_epoch = bool(edge_bad and hf_bad and gmf_bad)
                if rescue_triggered_epoch:
                    rescue_remaining = max(rescue_remaining, int(getattr(CFG, "RESCUE_HOLD_EPOCHS", 4)))
                    rescue_lr_mult = min(rescue_lr_mult, float(getattr(CFG, "RESCUE_LR_MULT", 0.50)))
                    rescue_eq_mult = min(rescue_eq_mult, float(getattr(CFG, "RESCUE_EQ_MULT", 0.50)))
                    rescue_cooldown = max(rescue_cooldown, int(getattr(CFG, "RESCUE_COOLDOWN_EPOCHS", 3)))
                    fail_flag_epoch = 1
                    fail_flag_global = 1
                    if last_good_ckpt is not None:
                        model.load_state_dict(last_good_ckpt["state_dict"], strict=True)
                        if "optimizer" in last_good_ckpt:
                            optimizer.load_state_dict(last_good_ckpt["optimizer"])
                    if (ema_model is not None) and (last_good_ema_ckpt is not None):
                        ema_model.load_state_dict(last_good_ema_ckpt["state_dict"], strict=True)
                    print(
                        f"[RESCUE][E{epoch1:03d}] bad_basin -> rollback + lr_mult={rescue_lr_mult:.2f} "
                        f"eq_mult={rescue_eq_mult:.2f} hold={rescue_remaining} "
                        f"edgeW={metric_edge:.4f}/{edge_width_ref:.4f} hf={metric_hf:.4f}/{hf_proxy_ref:.4f} "
                        f"gmf={gmf_curr:.4f}/{gmf_ref if np.isfinite(gmf_ref) else np.nan:.4f}"
                    )

            if rescue_triggered_epoch:
                gmf_gate_scale = _ema_update(
                    gmf_gate_scale,
                    float(getattr(CFG, "WEAK_PSF_RESCUE_GATE_MULT", 0.50)),
                    float(getattr(CFG, "WEAK_PSF_GATE_EMA", 0.90)),
                )

            summary["rescue_flag"] = int(rescue_active_epoch or rescue_triggered_epoch)
            summary["fail_flag"] = int(fail_flag_epoch)
            summary["consistency_factor"] = float(consist_factor_eff)
            if fail_flag_epoch:
                print(f"[RESCUE_FLAG] fail_flag={int(fail_flag_epoch)} (no abort)")
                if bool(getattr(CFG, "EARLY_ABORT_DEBUG_BREAK", False)):
                    stop_after_epoch = True
    
            row = _build_val_log_row(epoch1, summary, val_m)
            val_csv_w.writerow([_safe_csv_value(v) for v in row])
            val_csv_f.flush()

            cap_spike_left, cap_spike_cooldown = _tick_cap_spike_counters(cap_spike_left, cap_spike_cooldown)
            cap_spike_left, cap_spike_cooldown = _update_cap_fuse_state(
                summary=summary,
                cap_spike_left=cap_spike_left,
                cap_spike_cooldown=cap_spike_cooldown,
                cap_hf_hist=cap_hf_hist,
                cap_cb_hist=cap_cb_hist,
            )

            (
                thicken_triggered_epoch,
                oversmooth_triggered_epoch,
                thicken_guard_mult,
                thicken_guard_hold,
                thicken_guard_hits,
            ) = _update_thicken_guard(
                summary=summary,
                edge_width_ref=edge_width_ref,
                hf_proxy_ref=hf_proxy_ref,
                thicken_guard_mult=thicken_guard_mult,
                thicken_guard_hold=thicken_guard_hold,
                thicken_guard_hits=thicken_guard_hits,
            )

            detail_rescue_mult, detail_rescue_hold = _update_detail_rescue_state(
                epoch1, metric_edge, edge_width_ref, metric_hf, hf_proxy_ref, metric_cb, cb_ref,
                thicken_triggered_epoch, rescue_triggered_epoch, rescue_active_epoch, detail_rescue_mult, detail_rescue_hold,
            )

            band_guard_hold, lap_guard_hold, psf_guard_hold = _apply_guard_trigger_holds(
                epoch1, artifact_spike, band_guard_triggered_epoch, thicken_triggered_epoch, oversmooth_triggered_epoch,
                band_guard_hold, lap_guard_hold, psf_guard_hold,
            )

            last_thicken_trigger = bool(thicken_triggered_epoch)
            last_oversmooth_trigger = bool(oversmooth_triggered_epoch or band_guard_triggered_epoch)
            last_lap_guard_flag = bool(lap_guard_hold > 0)
            last_psf_guard_flag = bool(psf_guard_active_epoch)
            last_psf_force_freeze = bool(psf_force_hold > 0 or psf_force_triggered_epoch)
            summary["flag_thicken_guard"] = int(last_thicken_trigger)
            summary["flag_oversmooth_guard"] = int(last_oversmooth_trigger)
            summary["flag_lap_guard"] = int(last_lap_guard_flag)
            summary["flag_psf_guard"] = int(last_psf_guard_flag)
            summary["psf_forced_freeze"] = int(last_psf_force_freeze)
            summary["w_consistency_eff"] = float(w_consistency)
            summary["w_smooth_eff"] = float(w_smooth)
            summary["w_cap_eff"] = float(w_cap_eff)
            summary["w_edgeLocalLap"] = float(w_edge_local_lap_epoch)

            rescue_remaining, rescue_lr_mult, rescue_eq_mult, rescue_cooldown, band_guard_hold, lap_guard_hold, lap_boost_hold, psf_guard_hold, psf_force_hold = (
                _decay_guard_and_rescue_counters(
                    epoch1, artifact_spike, band_guard_triggered_epoch, thicken_triggered_epoch, oversmooth_triggered_epoch,
                    psf_force_triggered_epoch, rescue_remaining, rescue_lr_mult, rescue_eq_mult, rescue_cooldown,
                    band_guard_hold, lap_guard_hold, lap_boost_hold, psf_guard_hold, psf_force_hold,
                )
            )

            print(
                f"[SCHED] w_rec={summary.get('w_rec', float(CFG.W_REC)):.3f} "
                f"w_consist={summary.get('w_consistency_eff', 0.0):.3f} "
                f"w_smooth={summary.get('w_smooth_eff', 0.0):.3f} "
                f"w_cap={summary.get('w_cap_eff', 0.0):.3f} "
                f"w_edgeLocalLap={summary.get('w_edgeLocalLap', 0.0):.3f} "
                f"consist_mult={guard_mult_epoch:.3f} smooth_mult={guard_mult_epoch:.3f} cap_mult={guard_mult_epoch:.3f} "
                f"eq_factor={summary.get('eq_factor', 0.0):.3f} "
                f"thick_guard_mult={thicken_guard_mult:.3f} hold={thicken_guard_hold} "
                f"band_hold={band_guard_hold} lap_guard_hold={lap_guard_hold} lap_boost_hold={lap_boost_hold} "
                f"psf_guard_hold={psf_guard_hold} "
                f"edgeW={summary.get('metric_edge_width', np.nan):.4f} "
                f"hf={summary.get('metric_hf_proxy', np.nan):.4f} "
                f"cb={summary.get('metric_cb_proxy', np.nan):.6f}"
            )
            print(
                f"[GUARD_FLAG][E{epoch1:03d}] THICKEN={int(last_thicken_trigger)} "
                f"OVERSMOOTH={int(last_oversmooth_trigger)} LAP={int(last_lap_guard_flag)} "
                f"PSF={int(last_psf_guard_flag)}"
            )
            print(
                f"[EPOCH_CTRL][END] epoch={epoch1} eq_factor={summary.get('eq_factor', 0.0):.3f} "
                f"eq_disable_intensity={int(summary.get('eq_disable_intensity', 0))} "
                f"consistency_factor={summary.get('consistency_factor', summary.get('sched_consist_factor', 1.0)):.3f} "
                f"thicken_guard_hold={thicken_guard_hold} guard_mult={thicken_guard_mult:.3f}"
            )
    
            update = False
            best_min_epoch = int(getattr(CFG, "BEST_EPOCH_MIN", 20))
            best_max_epoch = min(int(getattr(CFG, "BEST_EPOCH_MAX", 60)), total_epochs)
            if not collapse and not spike and (best_min_epoch <= epoch1 <= best_max_epoch):
                update = is_better_tradeoff(summary, best_proxy)
                if update and np.isfinite(val_m["rec"]) and (prev_val_rec is not None) and np.isfinite(prev_val_rec):
                    if val_m["rec"] > prev_val_rec * (1.0 + float(CFG.GMF_REC_BAD_DELTA)):
                        update = False
                        print("[BEST] GMF improved but val_rec diverged; skip best update.")
            elif not collapse and not spike and (epoch1 < 5):
                print(f"[BEST] skip update at E{epoch1:03d} (<E005 warmup)")
            elif not collapse and not spike:
                print(f"[BEST] skip update at E{epoch1:03d} (best window E{best_min_epoch:03d}-E{best_max_epoch:03d})")
            if update:
                best_proxy = dict(summary)
                if np.isfinite(val_m["rec"]):
                    best_val_rec = float(val_m["rec"])
                if np.isfinite(val_m["ssim"]):
                    best_val_ssim = float(val_m["ssim"])
                best_epoch = epoch1
                best_state = (ema_model.state_dict() if ema_model is not None else model.state_dict())
                best_ckpt = {
                    "state_dict": best_state,
                    "ema_state_dict": (ema_model.state_dict() if ema_model is not None else None),
                    "optimizer": optimizer.state_dict(),
                    "epoch": epoch1,
                    "best_proxy_score_mean": best_proxy.get("proxy_score_mean"),
                    "best_proxy_score_p10": best_proxy.get("proxy_score_p10"),
                    "best_proxy_score_pass_rate": best_proxy.get("proxy_score_pass_rate"),
                    "best_proxy_score_lr_mean": best_proxy.get("proxy_score_lr_mean"),
                    "best_proxy_score_lr_p10": best_proxy.get("proxy_score_lr_p10"),
                    "best_proxy_posx_step_mean": best_proxy.get("proxy_posx_step_mean"),
                    "best_proxy_posy_step_mean": best_proxy.get("proxy_posy_step_mean"),
                    "best_proxy_step_err": best_proxy.get("proxy_step_err"),
                    "best_proxy_scale_mean": best_proxy.get("proxy_scale_mean"),
                    "best_proxy_scale_dev": best_proxy.get("proxy_scale_dev"),
                    "best_proxy_posx_adj_std": best_proxy.get("proxy_posx_adj_std"),
                    "best_proxy_posy_adj_std": best_proxy.get("proxy_posy_adj_std"),
                    "best_proxy_scale_std": best_proxy.get("proxy_scale_std"),
                    "gmf_obj": best_proxy.get("gmf_obj"),
                    "gmf_fitness": best_proxy.get("gmf_fitness"),
                    "gmf_z_step_std": best_proxy.get("gmf_z_step_std"),
                    "gmf_z_outlier": best_proxy.get("gmf_z_outlier"),
                    "gmf_z_step_mean_err": best_proxy.get("gmf_z_step_mean_err"),
                    "gmf_z_gain_p10": best_proxy.get("gmf_z_gain_p10"),
                    "gmf_z_proxy_mean": best_proxy.get("gmf_z_proxy_mean"),
                    "best_score": best_proxy.get("best_score"),
                    "best_z_score_mean": best_proxy.get("best_z_score_mean"),
                    "best_z_score_p10": best_proxy.get("best_z_score_p10"),
                    "best_z_pos_std": best_proxy.get("best_z_pos_std"),
                    "best_z_step_err": best_proxy.get("best_z_step_err"),
                    "best_val_rec": best_val_rec,
                    "best_val_ssim": best_val_ssim,
                    "tradeoff_score": best_proxy.get("tradeoff_score"),
                    "tradeoff_edge_pen": best_proxy.get("tradeoff_edge_pen"),
                    "tradeoff_hf_pen": best_proxy.get("tradeoff_hf_pen"),
                }
                save_ckpt(best_ckpt, os.path.join(PRETRAINED_DIR, f"{CFG.MODEL_NAME}_ema_best_tradeoff.pth.tar"))
                save_ckpt(best_ckpt, os.path.join(PRETRAINED_DIR, "best_tradeoff.pth.tar"))
                print(
                    f"[BEST] Updated best: tradeoff={best_proxy.get('tradeoff_score', np.nan):.4f} "
                    f"(edge_pen={best_proxy.get('tradeoff_edge_pen', np.nan):.3f} "
                    f"hf_pen={best_proxy.get('tradeoff_hf_pen', np.nan):.3f}) "
                    f"gmf_obj={best_proxy.get('gmf_obj', np.nan):.4f} "
                    f"gmf_fitness={best_proxy.get('gmf_fitness', np.nan):.4f} "
                    f"step_std={best_proxy.get('kpi_step_std', np.nan):.4f} "
                    f"outlier={best_proxy.get('kpi_outlier_rate', np.nan):.4f} "
                    f"step_err={best_proxy.get('kpi_step_mean_err', np.nan):.4f} "
                    f"gain_p10={best_proxy.get('proxy_gain_p10', np.nan):.4f} "
                    f"at epoch {epoch1}"
                )

            trade_score, trade_edge_pen, trade_hf_pen = compute_tradeoff_score(summary)
            summary["tradeoff_score"] = trade_score
            summary["tradeoff_edge_pen"] = trade_edge_pen
            summary["tradeoff_hf_pen"] = trade_hf_pen

            if detail_rescue_active_epoch and (not collapse) and (not spike) and is_better_gmf(summary, best_detail, epoch_summaries):
                best_detail = dict(summary)
                detail_state = (ema_model.state_dict() if ema_model is not None else model.state_dict())
                best_detail_ckpt = {
                    "state_dict": detail_state,
                    "ema_state_dict": (ema_model.state_dict() if ema_model is not None else None),
                    "optimizer": optimizer.state_dict(),
                    "epoch": epoch1,
                    "detail_rescue_mult": summary.get("detail_rescue_mult", 1.0),
                    "detail_edge_width": summary.get("metric_edge_width", np.nan),
                    "detail_hf_proxy": summary.get("metric_hf_proxy", np.nan),
                    "detail_proxy_step_err": summary.get("proxy_step_err", np.nan),
                    "detail_proxy_pass_rate": summary.get("proxy_score_pass_rate", np.nan),
                }
                save_ckpt(best_detail_ckpt, os.path.join(PRETRAINED_DIR, "best_detail_guarded.pth.tar"))
    
            # Save checkpoints
            if CFG.SAVE_CKPT_EVERY_EPOCH:
                ckpt_every_n = max(1, int(getattr(CFG, "SAVE_CKPT_EVERY_N_EPOCH", 1)))
                should_save_ckpt = ((epoch1 % ckpt_every_n) == 0) or (epoch1 == total_epochs)
                if should_save_ckpt:
                    ckpt = {
                        "state_dict": model.state_dict(),
                        "ema_state_dict": (ema_model.state_dict() if ema_model is not None else None),
                        "optimizer": optimizer.state_dict(),
                        "epoch": epoch1,
                    }
                    epoch_ckpt_name = f"epoch_{epoch1:03d}.pth.tar"
                    save_ckpt(ckpt, os.path.join(PROGRESS_DIR, epoch_ckpt_name))
                    save_ckpt(ckpt, os.path.join(PRETRAINED_DIR, f"{CFG.MODEL_NAME}.pth.tar"))
                    save_ckpt(ckpt, os.path.join(PRETRAINED_DIR, "latest.pth.tar"))
    
            # Store summary and plot curves
            epoch_summaries.append(summary)
            if epoch1 % max(1, int(CFG.ATTRIB_EVERY)) == 0:
                log_attribution(epoch1, epoch_summaries, attrib_path)
            if stop_after_epoch:
                fail_path = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_EARLY_ABORT_FAIL.txt")
                with open(fail_path, "w", encoding="utf-8") as f:
                    f.write(f"epoch={epoch1}\n")
                    f.write(f"edge_width={summary.get('edge_width', np.nan)}\n")
                    f.write(f"hf_proxy={summary.get('hf_proxy', np.nan)}\n")
                    f.write(f"fail_flag={summary.get('fail_flag', 1)}\n")
                print(f"[DEBUG_STOP] early-stop at epoch {epoch1}; fail marker: {fail_path}")
                break
            if fast_io_mode:
                if CFG.FAST_DISABLE_PLOTS:
                    plot_loss_now = False
                    plot_gmf_now = False
                else:
                    plot_loss_now = CFG.SAVE_LOSS_CURVE_EVERY_EPOCH and ((epoch1 % fast_plot_every) == 0)
                    plot_gmf_now = CFG.SAVE_GMF_CURVE_EVERY_EPOCH and ((epoch1 % fast_plot_every) == 0)
            else:
                plot_loss_now = CFG.SAVE_LOSS_CURVE_EVERY_EPOCH and (epoch1 % max(1, CFG.SAVE_LOSS_CURVE_EVERY_N) == 0)
                plot_gmf_now = CFG.SAVE_GMF_CURVE_EVERY_EPOCH and (epoch1 % max(1, CFG.SAVE_GMF_CURVE_EVERY_N) == 0)
    
            if plot_loss_now:
                out_main = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_loss_curve_main_v5.png")
                out_phase = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_loss_curve_phase_v5.png")
                plot_loss_curves(epoch_summaries, out_main, out_phase, title=f"Loss Curves ({CFG.MODEL_NAME} v5)")
            if plot_gmf_now:
                out_gmf = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_gmf_proxy_metrics_v5.png")
                plot_gmf_curves(epoch_summaries, out_gmf, title=f"GMF Proxy Metrics ({CFG.MODEL_NAME} v5)")
                
            best_score_s = "nan"
            best_trade_s = "nan"
            best_std_s = "nan"
            best_out_s = "nan"
            best_err_s = "nan"
            best_gain_s = "nan"
            if best_proxy is not None:
                if np.isfinite(best_proxy.get("tradeoff_score", np.nan)):
                    best_trade_s = f"{best_proxy.get('tradeoff_score', np.nan):.4f}"
                if np.isfinite(best_proxy.get("gmf_obj", np.nan)):
                    best_score_s = f"{best_proxy.get('gmf_obj', np.nan):.4f}"
                elif np.isfinite(best_proxy.get("gmf_fitness", np.nan)):
                    best_score_s = f"{best_proxy.get('gmf_fitness', np.nan):.4f}"
                if np.isfinite(best_proxy.get("kpi_step_std", np.nan)):
                    best_std_s = f"{best_proxy.get('kpi_step_std', np.nan):.4f}"
                if np.isfinite(best_proxy.get("kpi_outlier_rate", np.nan)):
                    best_out_s = f"{best_proxy.get('kpi_outlier_rate', np.nan):.4f}"
                if np.isfinite(best_proxy.get("kpi_step_mean_err", np.nan)):
                    best_err_s = f"{best_proxy.get('kpi_step_mean_err', np.nan):.4f}"
                if np.isfinite(best_proxy.get("proxy_gain_p10", np.nan)):
                    best_gain_s = f"{best_proxy.get('proxy_gain_p10', np.nan):.4f}"
            best_rec_s = f"{best_val_rec:.6f}" if (best_val_rec is not None and np.isfinite(best_val_rec)) else "nan"
            best_ssim_s = f"{best_val_ssim:.4f}" if (best_val_ssim is not None and np.isfinite(best_val_ssim)) else "nan"
            print(f"[SUMMARY] Best epoch = {best_epoch}, "
                  f"tradeoff = {best_trade_s}, "
                  f"gmf_obj = {best_score_s}, "
                  f"step_std = {best_std_s}, "
                  f"outlier = {best_out_s}, "
                  f"step_err = {best_err_s}, "
                  f"gain_p10 = {best_gain_s}, "
                  f"best_val_rec = {best_rec_s}, "
                  f"best_val_ssim = {best_ssim_s}")
    
    finally:
        if fast_io_mode and CFG.FAST_DISABLE_PLOTS and len(epoch_summaries) > 0:
            if CFG.SAVE_LOSS_CURVE_EVERY_EPOCH:
                out_main = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_loss_curve_main_v5.png")
                out_phase = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_loss_curve_phase_v5.png")
                plot_loss_curves(epoch_summaries, out_main, out_phase, title=f"Loss Curves ({CFG.MODEL_NAME} v5)")
            if CFG.SAVE_GMF_CURVE_EVERY_EPOCH:
                out_gmf = os.path.join(PROGRESS_DIR, f"{CFG.MODEL_NAME}_gmf_proxy_metrics_v5.png")
                plot_gmf_curves(epoch_summaries, out_gmf, title=f"GMF Proxy Metrics ({CFG.MODEL_NAME} v5)")
    
        csv_f.flush()
        val_csv_f.flush()
        csv_f.close()
        val_csv_f.close()

    best_proxy_score = np.nan
    best_step_err = np.nan
    best_pos_std_sum = np.nan
    best_edge_width = np.nan
    best_hf_proxy = np.nan
    best_pass02 = np.nan
    if best_proxy is not None:
        if np.isfinite(best_proxy.get("tradeoff_score", np.nan)):
            best_proxy_score = float(best_proxy.get("tradeoff_score", np.nan))
        elif np.isfinite(best_proxy.get("gmf_obj", np.nan)):
            best_proxy_score = float(best_proxy.get("gmf_obj", np.nan))
        elif np.isfinite(best_proxy.get("gmf_fitness", np.nan)):
            best_proxy_score = float(best_proxy.get("gmf_fitness", np.nan))
        elif np.isfinite(best_proxy.get("proxy_score_p10", np.nan)):
            best_proxy_score = float(best_proxy.get("proxy_score_p10", np.nan))
        best_step_err = float(best_proxy.get("proxy_step_err", np.nan))
        best_pos_std_sum = float(best_proxy.get("proxy_pos_step_std_sum", np.nan))
        best_edge_width = float(best_proxy.get("metric_edge_width", best_proxy.get("edge_width", np.nan)))
        best_hf_proxy = float(best_proxy.get("metric_hf_proxy", best_proxy.get("hf_proxy", np.nan)))
        pass_rate = float(best_proxy.get("proxy_score_pass_rate", np.nan))
        if np.isfinite(pass_rate):
            best_pass02 = pass_rate / 100.0 if pass_rate > 1.5 else pass_rate

    seed_good = False
    if bool(getattr(CFG, "SEED_SWEEP_STOP_ON_GOOD", False)):
        thr_std = float(getattr(CFG, "SEED_GOOD_THRESHOLD_STD", 0.16))
        thr_pass = float(getattr(CFG, "SEED_GOOD_THRESHOLD_PASS02", 0.80))
        if np.isfinite(best_pos_std_sum) and np.isfinite(best_pass02):
            seed_good = (best_pos_std_sum <= thr_std) and (best_pass02 >= thr_pass)

    return {
        "seed": int(seed),
        "best_epoch": int(best_epoch) if best_epoch is not None else np.nan,
        "best_proxy_score": best_proxy_score,
        "best_step_err": best_step_err,
        "best_pos_std_sum": best_pos_std_sum,
        "best_edge_width": best_edge_width,
        "best_hf_proxy": best_hf_proxy,
        "best_pass02_estimate": best_pass02,
        "seed_good": seed_good,
    }


def main():
    args = parse_args()
    seed = int(getattr(CFG, "REPRO_SEED", CFG.SPLIT_SEED))
    run_one_seed(seed, args=args)


if __name__ == "__main__":
    torch.cuda.empty_cache()
    main()
