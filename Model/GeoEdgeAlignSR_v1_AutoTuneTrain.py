#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GeoEdgeAlignSR_v1_AutoTuneTrain.py

Automated training + tuning focused on:
1) displacement precision
2) boundary position reconstruction correctness
3) keeping visually natural boundary/texture

Workflow:
- Run short sweep candidates
- Rank with shift-first objective
- Auto-run final training using best candidate
- Save full report JSON
"""

import argparse
import copy
import json
import math
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as train_mod

PROJECT_ROOT = Path(__file__).resolve().parents[1]

r26_r25_seed_ckpt = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/round25/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r25sw010_20260316_173027/weights/best_tradeoff.pth.tar')
r27_r26_seed_ckpt = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/round26/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r26sm035_20260316_190408/weights/best_tradeoff.pth.tar')
r28_r27_seed_ckpt = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/round27/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r27sm028_20260316_202936/weights/best_tradeoff.pth.tar')
# Round28 seeds from R26 (not R27): searching 0.8px/0.08px balance sweet spot
r28_r26_seed_ckpt = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/round26/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r26sm035_20260316_190408/weights/best_tradeoff.pth.tar')
r31_r30_b1_seed_ckpt = str(PROJECT_ROOT / 'Traing_Progress/organized_20260316/round30/archive/runs/training_progress_GESR_v1_v5_ST0p8_SWP_r30b1dir_20260317_152913/weights/best_tradeoff.pth.tar')


def _jsonable(v: Any):
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (np.floating,)):
        v = float(v)
    if isinstance(v, (np.integer,)):
        v = int(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            return None
        return float(v)
    if isinstance(v, (str, int, bool)) or v is None:
        return v
    return str(v)


def _safe_float(v: Any, default: float) -> float:
    try:
        x = float(v)
    except Exception:
        return float(default)
    if not math.isfinite(x):
        return float(default)
    return x


def _resolve_run_best_checkpoint(progress_dir: str) -> str:
    if not progress_dir:
        return ""
    root = Path(str(progress_dir))
    candidates = [
        root / "weights" / "best_tradeoff.pth.tar",
        root / "weights" / "best_detail.pth.tar",
        root / "weights" / "best.pth.tar",
    ]
    for ckpt in candidates:
        if ckpt.exists():
            return str(ckpt)
    return ""


def _build_short_final_cfg_overrides(final_epochs: int, init_checkpoint_path: str) -> Dict[str, Any]:
    total = max(2, int(final_epochs))
    eq_ramp_end = min(total, max(4, min(6, total)))
    return {
        "LOAD_MODEL": True,
        "PRETRAINED_PATH": str(init_checkpoint_path),
        "LOAD_RESET_OPTIMIZER": True,
        "LOAD_RESET_EPOCH": True,
        "EQ_WARMUP_OFF_E": 0,
        "EQ_RAMP_START_E": 1,
        "EQ_RAMP_END_E": int(eq_ramp_end),
        "EQ_FULL_END_E": int(total),
        "EQ_TAIL_END_E": int(total),
        "EQ_TAIL_FACTOR": 1.0,
        "FREEZE_PHYSICS_EPOCH": 0,
        "W_PHYS_MAX": 0.0,
        "PHYS_WARMUP_END": 0,
        "PHYS_RAMP_END": 1,
        "WEAK_PSF_STAGE0_EPOCHS": 0,
        "WEAK_PSF_ACTIVE_START_E": int(total + 1),
        "WEAK_PSF_ACTIVE_END_E": int(total + 1),
        "ENABLE_PSF_GUARD_ONLY": False,
        "SELF_BAND_READY_EPOCH": int(total + 1),
        "SELF_BAND_HF_PROXY_MIN_RATIO": 0.70,
        "RESCUE_START_EPOCH": int(total + 1),
        "RESCUE_GMF_DROP_REL": 0.12,
        "RESCUE_GMF_DROP_ABS": 1.0,
        "WEAK_PSF_GUARD_HF_DROP_REL": 0.25,
    }


def _build_short_final_refine_overrides() -> Dict[str, Any]:
    lr = max(1.0e-6, float(getattr(train_mod.CFG, "LR", 1.0e-6)) * 0.35)
    w_eq = min(0.60, float(getattr(train_mod.CFG, "W_EQ_GEOM", 0.0)) * 1.15)
    return {
        "LR": float(lr),
        "EQ_PROB": min(0.35, max(0.18, float(getattr(train_mod.CFG, "EQ_PROB", 0.18)))),
        "W_EQ_GEOM": float(w_eq),
        "W_GRADMAG": float(getattr(train_mod.CFG, "W_GRADMAG", 0.0)) * 0.88,
        "W_EDGE_ORI_SIMPLE": float(getattr(train_mod.CFG, "W_EDGE_ORI_SIMPLE", 0.0)) * 0.90,
        "W_HF_LAP": float(getattr(train_mod.CFG, "W_HF_LAP", 0.0)) * 0.55,
        "W_EDGELOCAL_LAP_END": float(getattr(train_mod.CFG, "W_EDGELOCAL_LAP_END", 0.0)) * 0.50,
        "W_DETAIL_BASE": float(getattr(train_mod.CFG, "W_DETAIL_BASE", 0.0)) * 0.50,
        "W_STAT": float(getattr(train_mod.CFG, "W_STAT", 0.0)) * 0.70,
        "W_BAND": float(getattr(train_mod.CFG, "W_BAND", 0.0)) * 0.70,
    }


def _choose_recommended_candidate(best: Dict[str, Any], final_run: Dict[str, Any] | None) -> Dict[str, Any]:
    sweep_score = _safe_float(best.get("score_shift_first"), float("-inf"))
    final_score = _safe_float((final_run or {}).get("score_shift_first"), float("-inf"))
    sweep_ckpt = str(best.get("best_checkpoint_path") or "")
    final_ckpt = _resolve_run_best_checkpoint(str((final_run or {}).get("progress_dir", "")))
    use_final = bool(final_run) and math.isfinite(final_score) and (final_score > sweep_score) and bool(final_ckpt)
    if use_final:
        return {
            "kind": "final",
            "candidate": str((final_run or {}).get("candidate", "")),
            "score_shift_first": float(final_score),
            "progress_dir": str((final_run or {}).get("progress_dir", "")),
            "checkpoint_path": str(final_ckpt),
        }
    return {
        "kind": "sweep",
        "candidate": str(best.get("name", best.get("candidate", ""))),
        "score_shift_first": float(sweep_score),
        "progress_dir": str(best.get("progress_dir", "")),
        "checkpoint_path": str(sweep_ckpt),
    }


def _resolve_seed_checkpoint() -> str:
    progress_root = Path(train_mod.PROJECT_ROOT) / "Traing_Progress"
    selected_roots = [
        progress_root / "organized_20260309" / "selected",
        progress_root / "organized_20260307" / "selected",
    ]
    for selected_root in selected_roots:
        manifest_path = selected_root / "current_seed.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                ckpt_path = manifest.get("weights_path") or manifest.get("checkpoint_path")
                if ckpt_path:
                    ckpt = Path(str(ckpt_path))
                    if ckpt.exists():
                        return str(ckpt)
            except Exception:
                pass

    fallback = (
        progress_root
        / "organized_20260307"
        / "selected"
        / "runs"
        / "training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625"
        / "weights"
        / "best_tradeoff.pth.tar"
    )
    return str(fallback)


def _resolve_manifest_checkpoint(manifest_path: Path, fallback: str = "") -> str:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}

    for key in ("weights_path", "checkpoint_path"):
        ckpt = Path(str(payload.get(key) or ""))
        if ckpt and ckpt.exists():
            return str(ckpt)

    fallback_path = Path(str(fallback)) if fallback else Path()
    if fallback_path and fallback_path.exists():
        return str(fallback_path)
    return ""


def _set_model_name_base(name: str):
    train_mod.MODEL_NAME_BASE = str(name)
    train_mod.RUN_TAG_BASE = str(name)
    train_mod.RUN_TAG = str(name)
    train_mod.CFG.MODEL_NAME = str(name)


def _restore_cfg_from_snapshot(snapshot: Dict[str, Any]):
    for k, v in snapshot.items():
        setattr(train_mod.CFG, k, copy.deepcopy(v))


def _apply_overrides(overrides: Dict[str, Any]):
    for k, v in overrides.items():
        if not hasattr(train_mod.CFG, k):
            raise AttributeError(f"Unknown CFG key: {k}")
        setattr(train_mod.CFG, k, copy.deepcopy(v))


def _split_cfg_and_auto_overrides(overrides: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    cfg_overrides: Dict[str, Any] = {}
    auto_overrides: Dict[str, Any] = {}
    for k, v in overrides.items():
        if str(k).startswith("AUTO_"):
            auto_overrides[str(k)] = copy.deepcopy(v)
        else:
            cfg_overrides[str(k)] = copy.deepcopy(v)
    return cfg_overrides, auto_overrides


def _apply_runtime_override_map(runtime_overrides: Dict[str, Any], auto_overrides: Dict[str, Any], prefix: str) -> None:
    key_map = {
        f"{prefix}_BEST_EPOCH_MIN": "BEST_EPOCH_MIN",
        f"{prefix}_BEST_EPOCH_MAX": "BEST_EPOCH_MAX",
        f"{prefix}_FAST_VAL_EVERY_EPOCH": "FAST_VAL_EVERY_EPOCH",
        f"{prefix}_EARLY_FAST_VAL_EVERY_EPOCH": "EARLY_FAST_VAL_EVERY_EPOCH",
        f"{prefix}_EARLY_FAST_VAL_UNTIL_EPOCH": "EARLY_FAST_VAL_UNTIL_EPOCH",
        f"{prefix}_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": "EARLY_MAX_TRAIN_BATCHES_PER_EPOCH",
        f"{prefix}_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": "EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH",
        f"{prefix}_SAVE_CKPT_EVERY_EPOCH": "SAVE_CKPT_EVERY_EPOCH",
        f"{prefix}_SAVE_CKPT_EVERY_N_EPOCH": "SAVE_CKPT_EVERY_N_EPOCH",
        f"{prefix}_FAST_MONITOR_EVERY_EPOCH": "FAST_MONITOR_EVERY_EPOCH",
    }
    for src_key, dst_key in key_map.items():
        if src_key in auto_overrides:
            runtime_overrides[dst_key] = copy.deepcopy(auto_overrides[src_key])


def _score_shift_first(
    summary: Dict[str, Any],
    edge_target: float = 10.5,
    hf_floor: float = 1.0e-3,
) -> float:
    pass02_raw = _safe_float(summary.get("best_pass02_estimate", np.nan), np.nan)
    pos_std_raw = _safe_float(summary.get("best_pos_std_sum", np.nan), np.nan)
    step_err_raw = _safe_float(summary.get("best_step_err", np.nan), np.nan)
    kpi_step_std_raw = _safe_float(summary.get("best_kpi_step_std", np.nan), np.nan)
    kpi_outlier_raw = _safe_float(summary.get("best_kpi_outlier_rate", np.nan), np.nan)
    kpi_step_mean_err_raw = _safe_float(summary.get("best_kpi_step_mean_err", np.nan), np.nan)
    gmf_obj_raw = _safe_float(summary.get("best_gmf_obj", np.nan), np.nan)
    has_step_proxy = math.isfinite(step_err_raw) and math.isfinite(pos_std_raw)
    has_kpi_proxy = all(
        math.isfinite(v)
        for v in (
            kpi_step_std_raw,
            kpi_outlier_raw,
            kpi_step_mean_err_raw,
        )
    )
    pass02 = pass02_raw if math.isfinite(pass02_raw) else None
    pos_std = pos_std_raw if math.isfinite(pos_std_raw) else None
    step_err = step_err_raw if math.isfinite(step_err_raw) else None
    kpi_step_std = kpi_step_std_raw if has_kpi_proxy else None
    kpi_outlier = kpi_outlier_raw if has_kpi_proxy else None
    kpi_step_mean_err = kpi_step_mean_err_raw if has_kpi_proxy else None
    gmf_obj = gmf_obj_raw if math.isfinite(gmf_obj_raw) else 0.0
    edge_w_raw = _safe_float(summary.get("best_edge_width", np.nan), np.nan)
    hf_raw = _safe_float(summary.get("best_hf_proxy", np.nan), np.nan)
    edge_w = edge_w_raw if math.isfinite(edge_w_raw) else None
    hf = hf_raw if math.isfinite(hf_raw) else None
    seq_score_raw = _safe_float(summary.get("best_seq_val_score", np.nan), np.nan)
    seq_sign_raw = _safe_float(summary.get("best_seq_val_sign_acc", np.nan), np.nan)
    seq_d1_raw = _safe_float(summary.get("best_seq_val_delta_l1_rel", np.nan), np.nan)
    seq_grad_raw = _safe_float(summary.get("best_seq_val_delta_grad_rel", np.nan), np.nan)
    seq_ratio_raw = _safe_float(summary.get("best_seq_val_mag_ratio_err", np.nan), np.nan)
    ann_score_raw = _safe_float(summary.get("best_ann_seq_score", np.nan), np.nan)
    ann_sign_raw = _safe_float(summary.get("best_ann_seq_sign_acc", np.nan), np.nan)
    ann_step_raw = _safe_float(summary.get("best_ann_seq_step_err_rel", np.nan), np.nan)
    ann_center_raw = _safe_float(summary.get("best_ann_seq_center_err_px", np.nan), np.nan)
    ann_radius_raw = _safe_float(summary.get("best_ann_seq_radius_err_rel", np.nan), np.nan)
    ann_thick_raw = _safe_float(summary.get("best_ann_seq_thickness_err_rel", np.nan), np.nan)
    ann_r_drift_raw = _safe_float(summary.get("best_ann_seq_radius_drift_rel", np.nan), np.nan)
    ann_t_drift_raw = _safe_float(summary.get("best_ann_seq_thickness_drift_rel", np.nan), np.nan)
    seq_score = seq_score_raw if math.isfinite(seq_score_raw) else None
    seq_sign = seq_sign_raw if math.isfinite(seq_sign_raw) else None
    seq_d1 = seq_d1_raw if math.isfinite(seq_d1_raw) else None
    seq_grad = seq_grad_raw if math.isfinite(seq_grad_raw) else None
    seq_ratio = seq_ratio_raw if math.isfinite(seq_ratio_raw) else None
    ann_score = ann_score_raw if math.isfinite(ann_score_raw) else None
    ann_sign = ann_sign_raw if math.isfinite(ann_sign_raw) else None
    ann_step = ann_step_raw if math.isfinite(ann_step_raw) else None
    ann_center = ann_center_raw if math.isfinite(ann_center_raw) else None
    ann_radius = ann_radius_raw if math.isfinite(ann_radius_raw) else None
    ann_thick = ann_thick_raw if math.isfinite(ann_thick_raw) else None
    ann_r_drift = ann_r_drift_raw if math.isfinite(ann_r_drift_raw) else None
    ann_t_drift = ann_t_drift_raw if math.isfinite(ann_t_drift_raw) else None

    score = 0.0
    # Primary objective: stable known-step reconstruction.
    score += 0.8 * gmf_obj
    if pass02 is not None:
        score += 80.0 * pass02
    if kpi_step_std is not None:
        score -= 8.0 * kpi_step_std
    if kpi_outlier is not None:
        score -= 10.0 * kpi_outlier
    if kpi_step_mean_err is not None:
        score -= 6.0 * kpi_step_mean_err
    if step_err is not None:
        score -= 2.0 * step_err
    if pos_std is not None:
        score -= 1.5 * pos_std

    # Secondary objective: edge realism/detail guard (only when available).
    if edge_w is not None:
        score -= 0.8 * max(0.0, edge_w - float(edge_target))
    if hf is not None:
        score -= 1500.0 * max(0.0, float(hf_floor) - hf)
    if seq_score is not None:
        score += 8.0 * seq_score
    if seq_sign is not None:
        score += 6.0 * seq_sign
    if seq_d1 is not None:
        score -= 4.0 * seq_d1
    if seq_grad is not None:
        score -= 2.5 * seq_grad
    if seq_ratio is not None:
        score -= 2.0 * seq_ratio
    if ann_score is not None:
        score += 18.0 * ann_score
    if ann_sign is not None:
        score += 10.0 * ann_sign
    if ann_step is not None:
        score -= 14.0 * ann_step
    if ann_center is not None:
        score -= 2.0 * ann_center
    if ann_radius is not None:
        score -= 10.0 * ann_radius
    if ann_thick is not None:
        score -= 12.0 * ann_thick
    if ann_r_drift is not None:
        score -= 6.0 * ann_r_drift
    if ann_t_drift is not None:
        score -= 6.0 * ann_t_drift

    # Hard feasibility guards.
    if (pass02 is not None) and (pass02 < 0.25):
        score -= 25.0
    if (kpi_step_std is not None) and (kpi_step_std > 1.5):
        score -= 40.0
    if (kpi_outlier is not None) and (kpi_outlier > 0.50):
        score -= 50.0
    if (kpi_step_mean_err is not None) and (kpi_step_mean_err > 1.0):
        score -= 40.0
    if (step_err is not None) and (step_err > 45.0):
        score -= 80.0
    if (pos_std is not None) and (pos_std > 45.0):
        score -= 80.0
    if (seq_sign is not None) and (seq_sign < 0.55):
        score -= 25.0
    if (seq_d1 is not None) and (seq_d1 > 1.20):
        score -= 20.0
    if (seq_ratio is not None) and (seq_ratio > 1.20):
        score -= 15.0
    if (ann_sign is not None) and (ann_sign < 0.55):
        score -= 25.0
    if (ann_step is not None) and (ann_step > 1.20):
        score -= 20.0
    if (ann_center is not None) and (ann_center > 2.0):
        score -= 15.0
    if (ann_thick is not None) and (ann_thick > 0.20):
        score -= 15.0

    return float(score)


def _run_one_candidate(
    *,
    candidate_name: str,
    candidate_tag: str,
    model_name_base: str,
    base_cfg_snapshot: Dict[str, Any],
    common_overrides: Dict[str, Any],
    candidate_overrides: Dict[str, Any],
    sweep_epochs: int,
    seed: int,
    deterministic: bool,
) -> Dict[str, Any]:
    _restore_cfg_from_snapshot(base_cfg_snapshot)
    common_cfg_overrides, common_auto_overrides = _split_cfg_and_auto_overrides(common_overrides)
    candidate_cfg_overrides, candidate_auto_overrides = _split_cfg_and_auto_overrides(candidate_overrides)
    candidate_sweep_epochs = int(
        min(
            int(sweep_epochs),
            int(candidate_auto_overrides.get(
            "AUTO_SWEEP_SWEEP_EPOCHS",
            common_auto_overrides.get("AUTO_SWEEP_SWEEP_EPOCHS", sweep_epochs),
            )),
        )
    )
    # Short sweeps should still be able to rank candidates before late-epoch collapse.
    best_epoch_min = 2 if int(candidate_sweep_epochs) >= 2 else max(1, int(candidate_sweep_epochs))
    best_epoch_max = max(best_epoch_min, int(candidate_sweep_epochs))

    sweep_runtime_overrides = {
        "SIMPLETEST_MODE": True,
        "SIMPLETEST_MAX_EPOCH": int(candidate_sweep_epochs),
        "LOAD_RESET_OPTIMIZER": True,
        "LOAD_RESET_EPOCH": True,
        "BEST_EPOCH_MIN": int(best_epoch_min),
        "BEST_EPOCH_MAX": int(best_epoch_max),
        "SAVE_MONITOR_EVERY_EPOCH": False,
        "FAST_MONITOR_EVERY_EPOCH": max(5, int(candidate_sweep_epochs)),
        "SAVE_LOSS_CURVE_EVERY_EPOCH": False,
        "SAVE_GMF_CURVE_EVERY_EPOCH": False,
        "SAVE_CKPT_EVERY_EPOCH": False,
        "SAVE_CKPT_EVERY_N_EPOCH": max(5, int(candidate_sweep_epochs)),
        "FAST_VAL_EVERY_EPOCH": 1,
        "EARLY_FAST_VAL_EVERY_EPOCH": 1,
        "EARLY_FAST_VAL_UNTIL_EPOCH": int(candidate_sweep_epochs),
        "EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 48,
        "EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(candidate_sweep_epochs),
        "GMF_VAL_NUM_FRAMES": 5,
        "FAST_IO_MODE": True,
        "FAST_DISABLE_PLOTS": True,
        "SEED_SWEEP_ENABLE": False,
    }
    _apply_runtime_override_map(sweep_runtime_overrides, common_auto_overrides, "AUTO_SWEEP")
    _apply_runtime_override_map(sweep_runtime_overrides, candidate_auto_overrides, "AUTO_SWEEP")
    _apply_overrides(common_cfg_overrides)
    _apply_overrides(candidate_cfg_overrides)
    _apply_overrides(sweep_runtime_overrides)

    run_model_name = f"{model_name_base}_SWP_{candidate_tag}"
    _set_model_name_base(run_model_name)

    args_ns = argparse.Namespace(
        attrib_window=None,
        attrib_every=None,
        seed_deterministic=bool(deterministic),
        force_fast_eval=False,
    )

    t0 = time.time()
    summary = train_mod.run_one_seed(int(seed), args=args_ns)
    dt = time.time() - t0

    score = _score_shift_first(summary)
    out = {
        "candidate": candidate_name,
        "model_name_base": run_model_name,
        "overrides": copy.deepcopy(candidate_overrides),
        "summary": summary,
        "score_shift_first": score,
        "duration_sec": float(dt),
        "effective_sweep_epochs": int(candidate_sweep_epochs),
        "progress_dir": str(train_mod.PROGRESS_DIR),
        "best_checkpoint_path": _resolve_run_best_checkpoint(str(train_mod.PROGRESS_DIR)),
    }

    if hasattr(train_mod, "torch") and hasattr(train_mod.torch, "cuda"):
        train_mod.torch.cuda.empty_cache()
    return out


def _run_final_training(
    *,
    best_candidate_name: str,
    best_candidate_tag: str,
    model_name_base: str,
    base_cfg_snapshot: Dict[str, Any],
    common_overrides: Dict[str, Any],
    best_candidate_overrides: Dict[str, Any],
    final_epochs: int,
    seed: int,
    deterministic: bool,
    init_checkpoint_path: str,
) -> Dict[str, Any]:
    _restore_cfg_from_snapshot(base_cfg_snapshot)
    common_cfg_overrides, common_auto_overrides = _split_cfg_and_auto_overrides(common_overrides)
    candidate_cfg_overrides, candidate_auto_overrides = _split_cfg_and_auto_overrides(best_candidate_overrides)
    short_final_cfg_overrides = _build_short_final_cfg_overrides(int(final_epochs), str(init_checkpoint_path))

    final_runtime_overrides = {
        "SIMPLETEST_MODE": True,
        "SIMPLETEST_MAX_EPOCH": int(final_epochs),
        "BEST_EPOCH_MIN": 1,
        "BEST_EPOCH_MAX": min(int(final_epochs), 6) if int(final_epochs) > 0 else 1,
        "BEST_EDGEW_TOL": 0.06,
        "BEST_HF_TOL": 0.03,
        "BEST_EDGEW_PENALTY": 18.0,
        "BEST_HF_PENALTY": 55.0,
        "SAVE_MONITOR_EVERY_EPOCH": True,
        "FAST_MONITOR_EVERY_EPOCH": max(2, min(4, int(final_epochs))),
        "SAVE_LOSS_CURVE_EVERY_EPOCH": True,
        "SAVE_GMF_CURVE_EVERY_EPOCH": True,
        "SAVE_CKPT_EVERY_EPOCH": True,
        "SAVE_CKPT_EVERY_N_EPOCH": 5,
        "FAST_VAL_EVERY_EPOCH": 1,
        "EARLY_FAST_VAL_EVERY_EPOCH": 1,
        "EARLY_FAST_VAL_UNTIL_EPOCH": int(final_epochs),
        "EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 72,
        "EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(final_epochs),
        "GMF_VALIDATE_EVERY_N": 1,
        "FAST_IO_MODE": True,
        "FAST_DISABLE_PLOTS": True,
        "SEED_SWEEP_ENABLE": False,
    }
    _apply_runtime_override_map(final_runtime_overrides, common_auto_overrides, "AUTO_FINAL")
    _apply_runtime_override_map(final_runtime_overrides, candidate_auto_overrides, "AUTO_FINAL")
    _apply_overrides(common_cfg_overrides)
    _apply_overrides(candidate_cfg_overrides)
    _apply_overrides(short_final_cfg_overrides)
    _apply_overrides(_build_short_final_refine_overrides())
    _apply_overrides(final_runtime_overrides)

    run_model_name = f"{model_name_base}_FIN_{best_candidate_tag}"
    _set_model_name_base(run_model_name)

    args_ns = argparse.Namespace(
        attrib_window=None,
        attrib_every=None,
        seed_deterministic=bool(deterministic),
        force_fast_eval=False,
    )

    t0 = time.time()
    summary = train_mod.run_one_seed(int(seed), args=args_ns)
    dt = time.time() - t0

    out = {
        "candidate": best_candidate_name,
        "model_name_base": run_model_name,
        "summary": summary,
        "score_shift_first": _score_shift_first(summary),
        "duration_sec": float(dt),
        "progress_dir": str(train_mod.PROGRESS_DIR),
        "init_checkpoint_path": str(init_checkpoint_path),
        "best_checkpoint_path": _resolve_run_best_checkpoint(str(train_mod.PROGRESS_DIR)),
    }
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=1261200)
    p.add_argument("--sweep-epochs", type=int, default=16)
    p.add_argument("--final-epochs", type=int, default=50)
    p.add_argument("--expect-dx", type=float, default=0.0)
    p.add_argument("--expect-dy", type=float, default=8.0)
    p.add_argument("--proxy-source", choices=["monitor_shift", "val_batch", "seq_val"], default="monitor_shift")
    p.add_argument("--candidate-filter", type=str, default="")
    p.add_argument("--deterministic", action="store_true")
    p.add_argument("--skip-final", action="store_true")
    p.add_argument(
        "--profile",
        choices=[
            "round2_seed_hold",
            "round3_gmf_guard",
            "round3_sharp_balance",
            "round4_refine_seed",
            "round5_extval_preserve",
            "round5_extval_data_probe",
            "round6_subpixel_guard",
            "round6_microstep_probe",
            "round7_sequence_microstep_probe",
            "round8_sequence_refine",
            "round9_sequence_val_align",
            "round10_crossscale_seqval",
            "round11_annulus_gmf_align",
            "round12_universal_annulus_align",
            "round13_universal_gated",
            "round14_corridor_midgate",
            "round15_centerlock_midgate",
            "round16_edgefit_centerlock",
            "round17_stepfix_centerlock",
            "round18_centerpush",
            "round19_absanchor",
            "round20_process_probe",
            "branchE_estimator_probe",
            "round21_hybrid_estimator_probe",
            "round22_pairmix_hybrid_probe",
            "round23_anchor_consistency_probe",
            "round24_single_abs_probe",
            "round25_scratch_abs",
            "round26_step_recovery_probe",
            "round27_step_mag_recovery",
            "round28_abs_center_sweep",
            "round29_step_mag_upper",
            "round30_architecture_breakthrough",
            "round31_b1_hyperparam",
        ],
        default="round2_seed_hold",
    )
    args = p.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    step_token = f"{float(args.expect_dy):g}".replace("-", "m").replace(".", "p")
    model_name_base = f"GESR_v1_v5_ST{step_token}"

    report_root = Path(train_mod.PROJECT_ROOT) / "Traing_Progress" / "auto_tune_reports"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / f"auto_tune_report_{ts}.json"

    base_cfg_snapshot = copy.deepcopy(vars(train_mod.TrainConfig()))
    _restore_cfg_from_snapshot(base_cfg_snapshot)

    seed_ckpt = _resolve_seed_checkpoint()

    common_overrides = {
        # Priority: 8px-step boundary-position reconstruction, with small-shift sensitivity retained.
        "TRAIN_EXCLUDE_SUBDIRS": (),
        "VAL_RATIO": 0.05,
        "VAL_BATCH_SIZE": 2,
        "EQ_PROB": 0.25,
        "EQ_WARMUP_OFF_E": 10,
        "EQ_RAMP_START_E": 11,
        "EQ_RAMP_END_E": 30,
        "W_EQ_GEOM": 0.26,
        "W_STAT": 0.03,
        "W_BAND": 0.03,
        "W_HF_LAP": 0.18,
        "W_EDGELOCAL_LAP_END": 0.08,
        "W_DETAIL_BASE": 0.018,
        # Keep some tiny-shift sensitivity, but explicitly train geometry consistency up to integer shifts.
        "SHIFT_MIX_TINY_P": 0.70,
        "SHIFT_MIX_MID_P": 0.20,
        "SHIFT_MIX_INT_P": 0.10,
        "SHIFT_TINY_RANGE": (0.01, 0.30),
        "SHIFT_MID_RANGE": (0.30, 1.50),
        "SHIFT_INT_RANGE": (1.0, 8.0),
        "EQ_SHIFT_MIX_TINY_P": 0.55,
        "EQ_SHIFT_MIX_MID_P": 0.25,
        "EQ_SHIFT_MIX_INT_P": 0.20,
        "EQ_SHIFT_TINY_RANGE": (0.01, 0.24),
        "EQ_SHIFT_MID_RANGE": (0.24, 1.25),
        "EQ_MAX_INT_SHIFT": 8,
        # Use a true known-step proxy instead of unrelated validation samples.
        "GMF_EXPECT_DX_PX": float(args.expect_dx),
        "GMF_EXPECT_DY_PX": float(args.expect_dy),
        "GMF_VALIDATE_SOURCE": str(args.proxy_source),
        "GMF_MONITOR_STEP_DX": float(args.expect_dx),
        "GMF_MONITOR_STEP_DY": float(args.expect_dy),
        "GMF_MONITOR_CENTER_REF": True,
        "GMF_W_STEP_STD": 2.2,
        "GMF_W_OUTLIER": 3.0,
        "GMF_W_STEP_ERR": 1.5,
        "GMF_W_GAIN_P10": 0.35,
        "GMF_W_PROXY_MEAN": 0.10,
        "GMF_OBJ_C": 0.80,
        "GMF_OBJ_D": 0.60,
        "GMF_OBJ_G": 3.0,
        "GMF_OBJ_H": 8.0,
        "GMF_OBJ_I": 4.0,
        "BEST_EDGEW_TOL": 0.06,
        "BEST_HF_TOL": 0.03,
        "BEST_EDGEW_PENALTY": 18.0,
        "BEST_HF_PENALTY": 55.0,
        # Avoid false GMF "bad streak" from early-epoch instability.
        "GMF_STEP_ERR_CAP": 80.0,
        "GMF_POS_STD_CAP": 80.0,
        "GMF_VALIDATE_EVERY_N": 1,
        "GMF_VAL_NUM_FRAMES": 7,
        "GMF_WEAK_PSF_BYPASS_EVAL": False,
        "PROXY_SEARCH_RADIUS": 28,
        "PROXY_COARSE_STRIDE": 2,
        "PROXY_FINE_STRIDE": 1,
        "EDGE_EXTRACT_Q_INIT": 0.93,
        "EDGE_TOPK_TARGET_DENSITY": 0.10,
        "EDGE_DENSITY_MAX": 0.18,
        "PROXY_EDGE_DENSITY_MAX": 0.20,
        "THICKEN_EDGEWIDTH_UP_REL": 0.07,
        "THICKEN_HF_DROP_REL": 0.05,
        "THICKEN_GUARD_MULT": 0.60,
        "THICKEN_GUARD_MIN_MULT": 0.35,
        "RESCUE_EDGEW_UP_REL": 0.07,
        "RESCUE_HF_DROP_REL": 0.05,
        "RESCUE_GMF_DROP_REL": 0.03,
        "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.08,
        "SELF_BAND_HF_PROXY_MIN_RATIO": 0.93,
    }

    candidates: List[Dict[str, Any]] = [
        {
            "name": "step8_seed_stage0_hold",
            "tag": "s0h",
            "overrides": {
                "LOAD_MODEL": True,
                "PRETRAINED_PATH": seed_ckpt,
                "TRAIN_INCLUDE_SUBDIRS": (
                    "stage_04_ellipses",
                    "stage_08_annulus_focus",
                    "stage_09_annulus_non_overlap",
                    "stage_10_annulus_overlap",
                    "stage_13_curve_clean_general",
                    "stage_14_annulus_edge_defect_focus",
                    "stage_15_annulus_sparse_clean",
                    "stage_16_annulus_sparse_defect_clean",
                ),
                "LR": 1.0e-5,
                "FREEZE_PHYSICS_EPOCH": 18,
                "PHYS_WARMUP_END": 18,
                "WEAK_PSF_STAGE0_EPOCHS": 18,
                "WEAK_PSF_STAGE1_EPOCHS": 28,
                "WEAK_PSF_ACTIVE_START_E": 19,
                "EQ_PROB": 0.12,
                "EQ_WARMUP_OFF_E": 16,
                "EQ_RAMP_START_E": 17,
                "EQ_RAMP_END_E": 30,
                "W_EQ_GEOM": 0.28,
                "W_GRADMAG": 1.06,
                "W_EDGE_ORI_SIMPLE": 0.54,
                "W_STAT": 0.010,
                "W_BAND": 0.010,
                "W_HF_LAP": 0.14,
                "W_EDGELOCAL_LAP_END": 0.05,
                "W_DETAIL_BASE": 0.012,
                "EQ_SHIFT_MIX_TINY_P": 0.44,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.32,
                "WEAK_PSF_BETA_SCALE_STAGE1": 0.03,
                "WEAK_PSF_BETA_SCALE_STAGE2": 0.06,
                "WEAK_PSF_BETA_SCALE_STAGE3": 0.06,
            },
        },
        {
            "name": "step8_seed_stage0_sharp",
            "tag": "s0s",
            "overrides": {
                "LOAD_MODEL": True,
                "PRETRAINED_PATH": seed_ckpt,
                "TRAIN_INCLUDE_SUBDIRS": (
                    "stage_02_circles",
                    "stage_04_ellipses",
                    "stage_08_annulus_focus",
                    "stage_09_annulus_non_overlap",
                    "stage_10_annulus_overlap",
                    "stage_13_curve_clean_general",
                    "stage_14_annulus_edge_defect_focus",
                    "stage_15_annulus_sparse_clean",
                    "stage_16_annulus_sparse_defect_clean",
                ),
                "LR": 1.0e-5,
                "FREEZE_PHYSICS_EPOCH": 18,
                "PHYS_WARMUP_END": 18,
                "WEAK_PSF_STAGE0_EPOCHS": 18,
                "WEAK_PSF_STAGE1_EPOCHS": 28,
                "WEAK_PSF_ACTIVE_START_E": 19,
                "EQ_PROB": 0.10,
                "EQ_WARMUP_OFF_E": 16,
                "EQ_RAMP_START_E": 17,
                "EQ_RAMP_END_E": 30,
                "W_EQ_GEOM": 0.30,
                "W_GRADMAG": 1.12,
                "W_EDGE_ORI_SIMPLE": 0.62,
                "W_STAT": 0.010,
                "W_BAND": 0.010,
                "W_HF_LAP": 0.16,
                "W_EDGELOCAL_LAP_END": 0.06,
                "W_DETAIL_BASE": 0.018,
                "EQ_SHIFT_MIX_TINY_P": 0.42,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.34,
                "WEAK_PSF_BETA_SCALE_STAGE1": 0.03,
                "WEAK_PSF_BETA_SCALE_STAGE2": 0.06,
                "WEAK_PSF_BETA_SCALE_STAGE3": 0.06,
            },
        },
        {
            "name": "step8_seed_no_weakpsf",
            "tag": "nwk",
            "overrides": {
                "LOAD_MODEL": True,
                "PRETRAINED_PATH": seed_ckpt,
                "TRAIN_INCLUDE_SUBDIRS": (
                    "stage_04_ellipses",
                    "stage_08_annulus_focus",
                    "stage_09_annulus_non_overlap",
                    "stage_10_annulus_overlap",
                    "stage_13_curve_clean_general",
                    "stage_14_annulus_edge_defect_focus",
                    "stage_15_annulus_sparse_clean",
                    "stage_16_annulus_sparse_defect_clean",
                ),
                "LR": 8.0e-6,
                "WEAK_PSF_ENABLE": True,
                "PHYS_FORWARD_ENABLE": False,
                "W_PHYS_MAX": 0.0,
                "FREEZE_PHYSICS_EPOCH": 18,
                "PHYS_WARMUP_END": 18,
                "WEAK_PSF_STAGE0_EPOCHS": 999,
                "WEAK_PSF_STAGE1_EPOCHS": 999,
                "WEAK_PSF_ACTIVE_START_E": 999,
                "WEAK_PSF_BETA_SCALE_STAGE1": 0.0,
                "WEAK_PSF_BETA_SCALE_STAGE2": 0.0,
                "WEAK_PSF_BETA_SCALE_STAGE3": 0.0,
                "EQ_PROB": 0.12,
                "EQ_WARMUP_OFF_E": 16,
                "EQ_RAMP_START_E": 17,
                "EQ_RAMP_END_E": 30,
                "W_EQ_GEOM": 0.30,
                "W_GRADMAG": 1.06,
                "W_EDGE_ORI_SIMPLE": 0.56,
                "W_STAT": 0.010,
                "W_BAND": 0.010,
                "W_HF_LAP": 0.12,
                "W_EDGELOCAL_LAP_END": 0.05,
                "W_DETAIL_BASE": 0.012,
                "EQ_SHIFT_MIX_TINY_P": 0.44,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.32,
            },
        },
        {
            "name": "step8_seed_hold_general",
            "tag": "s0g",
            "overrides": {
                "LOAD_MODEL": True,
                "PRETRAINED_PATH": seed_ckpt,
                "TRAIN_INCLUDE_SUBDIRS": (
                    "stage_02_circles",
                    "stage_04_ellipses",
                    "stage_06_mixed_simple",
                    "stage_08_annulus_focus",
                    "stage_09_annulus_non_overlap",
                    "stage_10_annulus_overlap",
                    "stage_13_curve_clean_general",
                    "stage_14_annulus_edge_defect_focus",
                    "stage_15_annulus_sparse_clean",
                    "stage_16_annulus_sparse_defect_clean",
                ),
                "LR": 1.0e-5,
                "FREEZE_PHYSICS_EPOCH": 16,
                "PHYS_WARMUP_END": 16,
                "WEAK_PSF_STAGE0_EPOCHS": 16,
                "WEAK_PSF_STAGE1_EPOCHS": 26,
                "WEAK_PSF_ACTIVE_START_E": 17,
                "EQ_PROB": 0.15,
                "EQ_WARMUP_OFF_E": 15,
                "EQ_RAMP_START_E": 16,
                "EQ_RAMP_END_E": 28,
                "W_EQ_GEOM": 0.28,
                "W_GRADMAG": 1.04,
                "W_EDGE_ORI_SIMPLE": 0.52,
                "W_STAT": 0.012,
                "W_BAND": 0.012,
                "W_HF_LAP": 0.14,
                "W_EDGELOCAL_LAP_END": 0.05,
                "W_DETAIL_BASE": 0.014,
                "EQ_SHIFT_MIX_TINY_P": 0.48,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.28,
                "WEAK_PSF_BETA_SCALE_STAGE1": 0.03,
                "WEAK_PSF_BETA_SCALE_STAGE2": 0.06,
                "WEAK_PSF_BETA_SCALE_STAGE3": 0.06,
            },
        },
    ]

    if args.profile == "round3_gmf_guard":
        common_overrides.update(
            {
                "EQ_PROB": 0.20,
                "EQ_WARMUP_OFF_E": 12,
                "EQ_RAMP_START_E": 13,
                "EQ_RAMP_END_E": 34,
                "W_EQ_GEOM": 0.30,
                "W_STAT": 0.020,
                "W_BAND": 0.020,
                "W_HF_LAP": 0.14,
                "W_EDGELOCAL_LAP_END": 0.05,
                "W_DETAIL_BASE": 0.012,
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.48,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.28,
                "THICKEN_GUARD_MULT": 0.55,
                "THICKEN_GUARD_MIN_MULT": 0.30,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.05,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.95,
                "GMF_W_STEP_STD": 2.6,
                "GMF_W_OUTLIER": 3.4,
                "GMF_W_STEP_ERR": 1.8,
            }
        )
        candidates = [
            {
                "name": "step8_gmf_hold_clean",
                "tag": "gmc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 8.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "EQ_PROB": 0.10,
                    "EQ_WARMUP_OFF_E": 18,
                    "EQ_RAMP_START_E": 19,
                    "EQ_RAMP_END_E": 34,
                    "W_GRADMAG": 1.00,
                    "W_EDGE_ORI_SIMPLE": 0.48,
                    "W_EQ_GEOM": 0.32,
                    "W_STAT": 0.010,
                    "W_BAND": 0.010,
                    "W_HF_LAP": 0.10,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.010,
                },
            },
            {
                "name": "step8_gmf_hold_no_weakpsf",
                "tag": "gnw",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 7.0e-6,
                    "WEAK_PSF_ENABLE": True,
                    "PHYS_FORWARD_ENABLE": False,
                    "W_PHYS_MAX": 0.0,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 999,
                    "WEAK_PSF_STAGE1_EPOCHS": 999,
                    "WEAK_PSF_ACTIVE_START_E": 999,
                    "WEAK_PSF_BETA_SCALE_STAGE1": 0.0,
                    "WEAK_PSF_BETA_SCALE_STAGE2": 0.0,
                    "WEAK_PSF_BETA_SCALE_STAGE3": 0.0,
                    "EQ_PROB": 0.10,
                    "EQ_WARMUP_OFF_E": 18,
                    "EQ_RAMP_START_E": 19,
                    "EQ_RAMP_END_E": 34,
                    "W_GRADMAG": 1.02,
                    "W_EDGE_ORI_SIMPLE": 0.50,
                    "W_EQ_GEOM": 0.32,
                    "W_STAT": 0.010,
                    "W_BAND": 0.010,
                    "W_HF_LAP": 0.10,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.010,
                },
            },
            {
                "name": "step8_gmf_hold_balanced",
                "tag": "gmb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 9.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "EQ_PROB": 0.12,
                    "EQ_WARMUP_OFF_E": 16,
                    "EQ_RAMP_START_E": 17,
                    "EQ_RAMP_END_E": 32,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.52,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.012,
                    "W_BAND": 0.012,
                    "W_HF_LAP": 0.12,
                    "W_EDGELOCAL_LAP_END": 0.05,
                    "W_DETAIL_BASE": 0.012,
                },
            },
        ]
    elif args.profile == "round3_sharp_balance":
        common_overrides.update(
            {
                "EQ_PROB": 0.18,
                "EQ_WARMUP_OFF_E": 12,
                "EQ_RAMP_START_E": 13,
                "EQ_RAMP_END_E": 32,
                "W_EQ_GEOM": 0.28,
                "W_STAT": 0.016,
                "W_BAND": 0.016,
                "W_HF_LAP": 0.20,
                "W_EDGELOCAL_LAP_END": 0.09,
                "W_DETAIL_BASE": 0.020,
                "SHIFT_MIX_TINY_P": 0.68,
                "SHIFT_MIX_MID_P": 0.20,
                "SHIFT_MIX_INT_P": 0.12,
                "EQ_SHIFT_MIX_TINY_P": 0.46,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.30,
                "THICKEN_GUARD_MULT": 0.58,
                "THICKEN_GUARD_MIN_MULT": 0.34,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.07,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.94,
            }
        )
        candidates = [
            {
                "name": "step8_sharp_curve_hold",
                "tag": "shc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                    ),
                    "LR": 1.0e-5,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "EQ_PROB": 0.10,
                    "EQ_WARMUP_OFF_E": 16,
                    "EQ_RAMP_START_E": 17,
                    "EQ_RAMP_END_E": 32,
                    "W_GRADMAG": 1.14,
                    "W_EDGE_ORI_SIMPLE": 0.64,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.012,
                    "W_BAND": 0.012,
                    "W_HF_LAP": 0.18,
                    "W_EDGELOCAL_LAP_END": 0.08,
                    "W_DETAIL_BASE": 0.020,
                },
            },
            {
                "name": "step8_sharp_general_hold",
                "tag": "shg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_06_mixed_simple",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 1.0e-5,
                    "FREEZE_PHYSICS_EPOCH": 17,
                    "PHYS_WARMUP_END": 17,
                    "WEAK_PSF_STAGE0_EPOCHS": 17,
                    "WEAK_PSF_STAGE1_EPOCHS": 27,
                    "WEAK_PSF_ACTIVE_START_E": 18,
                    "EQ_PROB": 0.12,
                    "EQ_WARMUP_OFF_E": 15,
                    "EQ_RAMP_START_E": 16,
                    "EQ_RAMP_END_E": 30,
                    "W_GRADMAG": 1.10,
                    "W_EDGE_ORI_SIMPLE": 0.58,
                    "W_EQ_GEOM": 0.28,
                    "W_STAT": 0.014,
                    "W_BAND": 0.014,
                    "W_HF_LAP": 0.18,
                    "W_EDGELOCAL_LAP_END": 0.08,
                    "W_DETAIL_BASE": 0.018,
                },
            },
            {
                "name": "step8_sharp_no_phys",
                "tag": "shn",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 9.0e-6,
                    "WEAK_PSF_ENABLE": True,
                    "PHYS_FORWARD_ENABLE": False,
                    "W_PHYS_MAX": 0.0,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 999,
                    "WEAK_PSF_STAGE1_EPOCHS": 999,
                    "WEAK_PSF_ACTIVE_START_E": 999,
                    "WEAK_PSF_BETA_SCALE_STAGE1": 0.0,
                    "WEAK_PSF_BETA_SCALE_STAGE2": 0.0,
                    "WEAK_PSF_BETA_SCALE_STAGE3": 0.0,
                    "EQ_PROB": 0.10,
                    "EQ_WARMUP_OFF_E": 16,
                    "EQ_RAMP_START_E": 17,
                    "EQ_RAMP_END_E": 32,
                    "W_GRADMAG": 1.12,
                    "W_EDGE_ORI_SIMPLE": 0.62,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.012,
                    "W_BAND": 0.012,
                    "W_HF_LAP": 0.16,
                    "W_EDGELOCAL_LAP_END": 0.08,
                    "W_DETAIL_BASE": 0.018,
                },
            },
        ]
    elif args.profile == "round4_refine_seed":
        common_overrides.update(
            {
                "EQ_PROB": 0.14,
                "EQ_WARMUP_OFF_E": 14,
                "EQ_RAMP_START_E": 15,
                "EQ_RAMP_END_E": 34,
                "W_EQ_GEOM": 0.28,
                "W_STAT": 0.014,
                "W_BAND": 0.014,
                "W_HF_LAP": 0.14,
                "W_EDGELOCAL_LAP_END": 0.05,
                "W_DETAIL_BASE": 0.012,
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.50,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.26,
                "THICKEN_GUARD_MULT": 0.56,
                "THICKEN_GUARD_MIN_MULT": 0.32,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.05,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.95,
                "GMF_W_STEP_STD": 2.4,
                "GMF_W_OUTLIER": 3.2,
                "GMF_W_STEP_ERR": 1.6,
            }
        )
        candidates = [
            {
                "name": "step8_refine_hold_clean",
                "tag": "rhc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 7.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 22,
                    "WEAK_PSF_STAGE1_EPOCHS": 32,
                    "WEAK_PSF_ACTIVE_START_E": 23,
                    "EQ_PROB": 0.08,
                    "EQ_WARMUP_OFF_E": 18,
                    "EQ_RAMP_START_E": 19,
                    "EQ_RAMP_END_E": 34,
                    "W_GRADMAG": 1.00,
                    "W_EDGE_ORI_SIMPLE": 0.48,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.010,
                    "W_BAND": 0.010,
                    "W_HF_LAP": 0.10,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.010,
                },
            },
            {
                "name": "step8_refine_hold_general",
                "tag": "rhg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_06_mixed_simple",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 8.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "EQ_PROB": 0.10,
                    "EQ_WARMUP_OFF_E": 17,
                    "EQ_RAMP_START_E": 18,
                    "EQ_RAMP_END_E": 32,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.52,
                    "W_EQ_GEOM": 0.28,
                    "W_STAT": 0.012,
                    "W_BAND": 0.012,
                    "W_HF_LAP": 0.12,
                    "W_EDGELOCAL_LAP_END": 0.05,
                    "W_DETAIL_BASE": 0.012,
                },
            },
            {
                "name": "step8_refine_hold_curve",
                "tag": "rhv",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                    ),
                    "LR": 8.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "EQ_PROB": 0.09,
                    "EQ_WARMUP_OFF_E": 17,
                    "EQ_RAMP_START_E": 18,
                    "EQ_RAMP_END_E": 32,
                    "W_GRADMAG": 1.08,
                    "W_EDGE_ORI_SIMPLE": 0.56,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.012,
                    "W_BAND": 0.012,
                    "W_HF_LAP": 0.14,
                    "W_EDGELOCAL_LAP_END": 0.06,
                    "W_DETAIL_BASE": 0.014,
                },
            },
            {
                "name": "step8_refine_no_phys_soft",
                "tag": "rnp",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 7.0e-6,
                    "WEAK_PSF_ENABLE": True,
                    "PHYS_FORWARD_ENABLE": False,
                    "W_PHYS_MAX": 0.0,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 999,
                    "WEAK_PSF_STAGE1_EPOCHS": 999,
                    "WEAK_PSF_ACTIVE_START_E": 999,
                    "WEAK_PSF_BETA_SCALE_STAGE1": 0.0,
                    "WEAK_PSF_BETA_SCALE_STAGE2": 0.0,
                    "WEAK_PSF_BETA_SCALE_STAGE3": 0.0,
                    "EQ_PROB": 0.08,
                    "EQ_WARMUP_OFF_E": 18,
                    "EQ_RAMP_START_E": 19,
                    "EQ_RAMP_END_E": 34,
                    "W_GRADMAG": 1.02,
                    "W_EDGE_ORI_SIMPLE": 0.50,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.010,
                    "W_BAND": 0.010,
                    "W_HF_LAP": 0.10,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.010,
                },
            },
        ]
    elif args.profile == "round5_extval_preserve":
        common_overrides.update(
            {
                "EQ_PROB": 0.10,
                "EQ_WARMUP_OFF_E": 16,
                "EQ_RAMP_START_E": 17,
                "EQ_RAMP_END_E": 36,
                "W_EQ_GEOM": 0.30,
                "W_STAT": 0.010,
                "W_BAND": 0.010,
                "W_HF_LAP": 0.10,
                "W_EDGELOCAL_LAP_END": 0.035,
                "W_DETAIL_BASE": 0.008,
                "SHIFT_MIX_TINY_P": 0.66,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.16,
                "EQ_SHIFT_MIX_TINY_P": 0.42,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.34,
                "THICKEN_GUARD_MULT": 0.54,
                "THICKEN_GUARD_MIN_MULT": 0.30,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.04,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.96,
                "GMF_W_STEP_STD": 2.8,
                "GMF_W_OUTLIER": 3.6,
                "GMF_W_STEP_ERR": 1.8,
            }
        )
        candidates = [
            {
                "name": "step8_ext_preserve_clean",
                "tag": "epc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                    ),
                    "LR": 5.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "EQ_PROB": 0.06,
                    "EQ_WARMUP_OFF_E": 20,
                    "EQ_RAMP_START_E": 21,
                    "EQ_RAMP_END_E": 38,
                    "W_GRADMAG": 1.02,
                    "W_EDGE_ORI_SIMPLE": 0.50,
                    "W_EQ_GEOM": 0.32,
                    "W_STAT": 0.008,
                    "W_BAND": 0.008,
                    "W_HF_LAP": 0.08,
                    "W_EDGELOCAL_LAP_END": 0.03,
                    "W_DETAIL_BASE": 0.008,
                },
            },
            {
                "name": "step8_ext_preserve_defect",
                "tag": "epd",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 5.5e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "EQ_PROB": 0.07,
                    "EQ_WARMUP_OFF_E": 20,
                    "EQ_RAMP_START_E": 21,
                    "EQ_RAMP_END_E": 38,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.52,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.009,
                    "W_BAND": 0.009,
                    "W_HF_LAP": 0.09,
                    "W_EDGELOCAL_LAP_END": 0.032,
                    "W_DETAIL_BASE": 0.008,
                },
            },
            {
                "name": "step8_ext_preserve_general",
                "tag": "epg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_06_mixed_simple",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 6.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 22,
                    "WEAK_PSF_STAGE1_EPOCHS": 32,
                    "WEAK_PSF_ACTIVE_START_E": 23,
                    "EQ_PROB": 0.08,
                    "EQ_WARMUP_OFF_E": 18,
                    "EQ_RAMP_START_E": 19,
                    "EQ_RAMP_END_E": 36,
                    "W_GRADMAG": 1.02,
                    "W_EDGE_ORI_SIMPLE": 0.50,
                    "W_EQ_GEOM": 0.30,
                    "W_STAT": 0.010,
                    "W_BAND": 0.010,
                    "W_HF_LAP": 0.09,
                    "W_EDGELOCAL_LAP_END": 0.032,
                    "W_DETAIL_BASE": 0.008,
                },
            },
        ]
    elif args.profile == "round5_extval_data_probe":
        common_overrides.update(
            {
                "EQ_PROB": 0.12,
                "EQ_WARMUP_OFF_E": 16,
                "EQ_RAMP_START_E": 17,
                "EQ_RAMP_END_E": 34,
                "W_EQ_GEOM": 0.30,
                "W_STAT": 0.012,
                "W_BAND": 0.012,
                "W_HF_LAP": 0.12,
                "W_EDGELOCAL_LAP_END": 0.05,
                "W_DETAIL_BASE": 0.010,
                "SHIFT_MIX_TINY_P": 0.64,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.18,
                "EQ_SHIFT_MIX_TINY_P": 0.40,
                "EQ_SHIFT_MIX_MID_P": 0.22,
                "EQ_SHIFT_MIX_INT_P": 0.38,
                "THICKEN_GUARD_MULT": 0.55,
                "THICKEN_GUARD_MIN_MULT": 0.32,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.05,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.95,
                "GMF_W_STEP_STD": 2.8,
                "GMF_W_OUTLIER": 3.6,
                "GMF_W_STEP_ERR": 1.8,
            }
        )
        candidates = [
            {
                "name": "step8_data_sparse_clean",
                "tag": "dsc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                    ),
                    "LR": 6.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 22,
                    "WEAK_PSF_STAGE1_EPOCHS": 32,
                    "WEAK_PSF_ACTIVE_START_E": 23,
                    "EQ_PROB": 0.08,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.52,
                    "W_HF_LAP": 0.10,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.010,
                },
            },
            {
                "name": "step8_data_sparse_defect",
                "tag": "dsd",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 6.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 22,
                    "WEAK_PSF_STAGE1_EPOCHS": 32,
                    "WEAK_PSF_ACTIVE_START_E": 23,
                    "EQ_PROB": 0.08,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.54,
                    "W_HF_LAP": 0.10,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.010,
                },
            },
            {
                "name": "step8_data_general_curve",
                "tag": "dsg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_06_mixed_simple",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ),
                    "LR": 7.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "EQ_PROB": 0.10,
                    "W_GRADMAG": 1.02,
                    "W_EDGE_ORI_SIMPLE": 0.52,
                    "W_HF_LAP": 0.12,
                    "W_EDGELOCAL_LAP_END": 0.045,
                    "W_DETAIL_BASE": 0.010,
                },
            },
        ]
    elif args.profile == "round6_subpixel_guard":
        common_overrides.update(
            {
                # Keep the final stage in a finer-grained regime longer; current evidence shows
                # later full-epoch phases often drift before they add useful GMF gains.
                "AUTO_FINAL_EARLY_FAST_VAL_UNTIL_EPOCH": min(10, int(args.final_epochs)),
                "AUTO_FINAL_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 72,
                "AUTO_FINAL_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": min(10, int(args.final_epochs)),
                "EQ_PROB": 0.14,
                "EQ_WARMUP_OFF_E": 16,
                "EQ_RAMP_START_E": 17,
                "EQ_RAMP_END_E": 36,
                "W_EQ_GEOM": 0.32,
                "W_STAT": 0.012,
                "W_BAND": 0.010,
                "W_HF_LAP": 0.10,
                "W_EDGELOCAL_LAP_END": 0.045,
                "W_DETAIL_BASE": 0.008,
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.005, 0.20),
                "SHIFT_MID_RANGE": (0.20, 1.20),
                "SHIFT_INT_RANGE": (0.80, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.52,
                "EQ_SHIFT_MIX_MID_P": 0.26,
                "EQ_SHIFT_MIX_INT_P": 0.22,
                "EQ_SHIFT_TINY_RANGE": (0.005, 0.16),
                "EQ_SHIFT_MID_RANGE": (0.16, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_VAL_NUM_FRAMES": 9,
                "PROXY_SEARCH_RADIUS": 20,
                "PROXY_COARSE_STRIDE": 1,
                "PROXY_FINE_STRIDE": 1,
                "THICKEN_GUARD_MULT": 0.50,
                "THICKEN_GUARD_MIN_MULT": 0.28,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.04,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.96,
                "GMF_W_STEP_STD": 3.0,
                "GMF_W_OUTLIER": 3.8,
                "GMF_W_STEP_ERR": 1.9,
            }
        )
        candidates = [
            {
                "name": "subpix_curve_clean",
                "tag": "spc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                    ),
                    "LR": 5.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "EQ_PROB": 0.10,
                    "W_GRADMAG": 1.06,
                    "W_EDGE_ORI_SIMPLE": 0.54,
                    "W_HF_LAP": 0.08,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.008,
                },
            },
            {
                "name": "subpix_curve_defect",
                "tag": "spd",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                    ),
                    "LR": 5.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "EQ_PROB": 0.10,
                    "W_GRADMAG": 1.06,
                    "W_EDGE_ORI_SIMPLE": 0.56,
                    "W_HF_LAP": 0.08,
                    "W_EDGELOCAL_LAP_END": 0.04,
                    "W_DETAIL_BASE": 0.008,
                },
            },
            {
                "name": "subpix_general_curve",
                "tag": "spg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_02_circles",
                        "stage_04_ellipses",
                        "stage_06_mixed_simple",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                    ),
                    "LR": 5.5e-6,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 22,
                    "WEAK_PSF_STAGE1_EPOCHS": 32,
                    "WEAK_PSF_ACTIVE_START_E": 23,
                    "EQ_PROB": 0.12,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.54,
                    "W_HF_LAP": 0.09,
                    "W_EDGELOCAL_LAP_END": 0.045,
                    "W_DETAIL_BASE": 0.008,
                },
            },
        ]
    elif args.profile == "round6_microstep_probe":
        common_overrides.update(
            {
                # 0.08px runs are even more prone to late-epoch drift; keep them in a tighter
                # micro-epoch schedule for most of the final continuation.
                "AUTO_FINAL_EARLY_FAST_VAL_UNTIL_EPOCH": min(10, int(args.final_epochs)),
                "AUTO_FINAL_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 72,
                "AUTO_FINAL_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": min(10, int(args.final_epochs)),
                "EQ_PROB": 0.18,
                "EQ_WARMUP_OFF_E": 18,
                "EQ_RAMP_START_E": 19,
                "EQ_RAMP_END_E": 40,
                "W_EQ_GEOM": 0.34,
                "W_STAT": 0.010,
                "W_BAND": 0.008,
                "W_HF_LAP": 0.08,
                "W_EDGELOCAL_LAP_END": 0.040,
                "W_DETAIL_BASE": 0.006,
                "SHIFT_MIX_TINY_P": 0.82,
                "SHIFT_MIX_MID_P": 0.12,
                "SHIFT_MIX_INT_P": 0.06,
                "SHIFT_TINY_RANGE": (0.002, 0.12),
                "SHIFT_MID_RANGE": (0.12, 0.80),
                "SHIFT_INT_RANGE": (0.80, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.68,
                "EQ_SHIFT_MIX_MID_P": 0.20,
                "EQ_SHIFT_MIX_INT_P": 0.12,
                "EQ_SHIFT_TINY_RANGE": (0.002, 0.10),
                "EQ_SHIFT_MID_RANGE": (0.10, 0.60),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_VAL_NUM_FRAMES": 11,
                "PROXY_SEARCH_RADIUS": 12,
                "PROXY_COARSE_STRIDE": 1,
                "PROXY_FINE_STRIDE": 1,
                "THICKEN_GUARD_MULT": 0.46,
                "THICKEN_GUARD_MIN_MULT": 0.26,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.03,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.97,
                "GMF_W_STEP_STD": 3.2,
                "GMF_W_OUTLIER": 4.0,
                "GMF_W_STEP_ERR": 2.2,
            }
        )
        candidates = [
            {
                "name": "micro_clean_focus",
                "tag": "mcf",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                    ),
                    "LR": 4.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 26,
                    "PHYS_WARMUP_END": 26,
                    "WEAK_PSF_STAGE0_EPOCHS": 26,
                    "WEAK_PSF_STAGE1_EPOCHS": 36,
                    "WEAK_PSF_ACTIVE_START_E": 27,
                    "EQ_PROB": 0.14,
                    "W_GRADMAG": 1.08,
                    "W_EDGE_ORI_SIMPLE": 0.58,
                    "W_HF_LAP": 0.06,
                    "W_EDGELOCAL_LAP_END": 0.035,
                    "W_DETAIL_BASE": 0.006,
                },
            },
            {
                "name": "micro_defect_balance",
                "tag": "mdb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                    ),
                    "LR": 4.2e-6,
                    "FREEZE_PHYSICS_EPOCH": 26,
                    "PHYS_WARMUP_END": 26,
                    "WEAK_PSF_STAGE0_EPOCHS": 26,
                    "WEAK_PSF_STAGE1_EPOCHS": 36,
                    "WEAK_PSF_ACTIVE_START_E": 27,
                    "EQ_PROB": 0.14,
                    "W_GRADMAG": 1.08,
                    "W_EDGE_ORI_SIMPLE": 0.60,
                    "W_HF_LAP": 0.06,
                    "W_EDGELOCAL_LAP_END": 0.035,
                    "W_DETAIL_BASE": 0.006,
                },
            },
            {
                "name": "micro_general_curve",
                "tag": "mgc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                    ),
                    "LR": 4.5e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "EQ_PROB": 0.16,
                    "W_GRADMAG": 1.06,
                    "W_EDGE_ORI_SIMPLE": 0.58,
                    "W_HF_LAP": 0.07,
                    "W_EDGELOCAL_LAP_END": 0.040,
                    "W_DETAIL_BASE": 0.006,
                },
            },
        ]
    elif args.profile == "round7_sequence_microstep_probe":
        common_overrides.update(
            {
                "EQ_PROB": 0.14,
                "EQ_WARMUP_OFF_E": 14,
                "EQ_RAMP_START_E": 15,
                "EQ_RAMP_END_E": 30,
                "W_EQ_GEOM": 0.32,
                "W_STAT": 0.010,
                "W_BAND": 0.008,
                "W_HF_LAP": 0.06,
                "W_EDGELOCAL_LAP_END": 0.035,
                "W_DETAIL_BASE": 0.006,
                "SHIFT_MIX_TINY_P": 0.82,
                "SHIFT_MIX_MID_P": 0.12,
                "SHIFT_MIX_INT_P": 0.06,
                "SHIFT_TINY_RANGE": (0.002, 0.12),
                "SHIFT_MID_RANGE": (0.12, 0.80),
                "SHIFT_INT_RANGE": (0.80, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.66,
                "EQ_SHIFT_MIX_MID_P": 0.22,
                "EQ_SHIFT_MIX_INT_P": 0.12,
                "EQ_SHIFT_TINY_RANGE": (0.002, 0.10),
                "EQ_SHIFT_MID_RANGE": (0.10, 0.60),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_VAL_NUM_FRAMES": 11,
                "PROXY_SEARCH_RADIUS": 12,
                "PROXY_COARSE_STRIDE": 1,
                "PROXY_FINE_STRIDE": 1,
                "THICKEN_GUARD_MULT": 0.46,
                "THICKEN_GUARD_MIN_MULT": 0.26,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.03,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.97,
                "GMF_W_STEP_STD": 3.4,
                "GMF_W_OUTLIER": 4.2,
                "GMF_W_STEP_ERR": 2.3,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                    "stage_21_annulus_gmf_sequence_clean",
                    "stage_22_annulus_gmf_sequence_defect",
                ),
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
            }
        )
        candidates = [
            {
                "name": "seq_clean_anchor",
                "tag": "sca",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_19_annulus_microstep_sequence_clean",
                    ),
                    "LR": 3.6e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.56,
                    "SEQ_LOSS_WEIGHT": 0.26,
                    "SEQ_GRAD_WEIGHT": 0.06,
                },
            },
            {
                "name": "seq_defect_balance",
                "tag": "sdb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.8e-6,
                    "FREEZE_PHYSICS_EPOCH": 24,
                    "PHYS_WARMUP_END": 24,
                    "WEAK_PSF_STAGE0_EPOCHS": 24,
                    "WEAK_PSF_STAGE1_EPOCHS": 34,
                    "WEAK_PSF_ACTIVE_START_E": 25,
                    "W_GRADMAG": 1.05,
                    "W_EDGE_ORI_SIMPLE": 0.58,
                    "SEQ_LOSS_WEIGHT": 0.28,
                    "SEQ_GRAD_WEIGHT": 0.08,
                },
            },
            {
                "name": "seq_general_curve",
                "tag": "sgc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 4.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 22,
                    "PHYS_WARMUP_END": 22,
                    "WEAK_PSF_STAGE0_EPOCHS": 22,
                    "WEAK_PSF_STAGE1_EPOCHS": 32,
                    "WEAK_PSF_ACTIVE_START_E": 23,
                    "W_GRADMAG": 1.04,
                    "W_EDGE_ORI_SIMPLE": 0.56,
                    "SEQ_LOSS_WEIGHT": 0.24,
                    "SEQ_GRAD_WEIGHT": 0.06,
                },
            },
        ]
    elif args.profile == "round8_sequence_refine":
        common_overrides.update(
            {
                "EQ_PROB": 0.16,
                "EQ_WARMUP_OFF_E": 10,
                "EQ_RAMP_START_E": 11,
                "EQ_RAMP_END_E": 24,
                "W_EQ_GEOM": 0.36,
                "W_STAT": 0.008,
                "W_BAND": 0.006,
                "W_HF_LAP": 0.05,
                "W_EDGELOCAL_LAP_END": 0.030,
                "W_DETAIL_BASE": 0.004,
                "SHIFT_MIX_TINY_P": 0.84,
                "SHIFT_MIX_MID_P": 0.10,
                "SHIFT_MIX_INT_P": 0.06,
                "SHIFT_TINY_RANGE": (0.002, 0.12),
                "SHIFT_MID_RANGE": (0.12, 0.80),
                "SHIFT_INT_RANGE": (0.80, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.70,
                "EQ_SHIFT_MIX_MID_P": 0.18,
                "EQ_SHIFT_MIX_INT_P": 0.12,
                "EQ_SHIFT_TINY_RANGE": (0.002, 0.10),
                "EQ_SHIFT_MID_RANGE": (0.10, 0.60),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_VAL_NUM_FRAMES": 11,
                "PROXY_SEARCH_RADIUS": 12,
                "PROXY_COARSE_STRIDE": 1,
                "PROXY_FINE_STRIDE": 1,
                "THICKEN_GUARD_MULT": 0.46,
                "THICKEN_GUARD_MIN_MULT": 0.26,
                "SELF_BAND_EDGE_WIDTH_MAX_RATIO": 1.03,
                "SELF_BAND_HF_PROXY_MIN_RATIO": 0.97,
                "GMF_W_STEP_STD": 3.6,
                "GMF_W_OUTLIER": 4.4,
                "GMF_W_STEP_ERR": 2.4,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                ),
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "seq_refine_defect_mid",
                "tag": "rdm",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.2e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.98,
                    "W_EDGE_ORI_SIMPLE": 0.46,
                    "SEQ_LOSS_WEIGHT": 0.34,
                    "SEQ_GRAD_WEIGHT": 0.10,
                },
            },
            {
                "name": "seq_refine_defect_strong",
                "tag": "rds",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.94,
                    "W_EDGE_ORI_SIMPLE": 0.42,
                    "SEQ_LOSS_WEIGHT": 0.42,
                    "SEQ_GRAD_WEIGHT": 0.14,
                },
            },
            {
                "name": "seq_refine_general_mid",
                "tag": "rgm",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.4e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.98,
                    "W_EDGE_ORI_SIMPLE": 0.44,
                    "SEQ_LOSS_WEIGHT": 0.30,
                    "SEQ_GRAD_WEIGHT": 0.08,
                },
            },
            {
                "name": "seq_refine_clean_strong",
                "tag": "rcs",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_19_annulus_microstep_sequence_clean",
                    ),
                    "LR": 3.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.92,
                    "W_EDGE_ORI_SIMPLE": 0.40,
                    "SEQ_LOSS_WEIGHT": 0.38,
                    "SEQ_GRAD_WEIGHT": 0.12,
                },
            },
        ]
    elif args.profile == "round9_sequence_val_align":
        common_overrides.update(
            {
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.14,
                "EQ_WARMUP_OFF_E": 8,
                "EQ_RAMP_START_E": 9,
                "EQ_RAMP_END_E": 20,
                "W_EQ_GEOM": 0.34,
                "W_STAT": 0.006,
                "W_BAND": 0.004,
                "W_HF_LAP": 0.040,
                "W_EDGELOCAL_LAP_END": 0.022,
                "W_DETAIL_BASE": 0.003,
                "GMF_VAL_NUM_FRAMES": 9,
                "GMF_W_STEP_STD": 3.8,
                "GMF_W_OUTLIER": 4.8,
                "GMF_W_STEP_ERR": 2.6,
                "GMF_OBJ_J": 10.0,
                "GMF_OBJ_K": 8.0,
                "GMF_OBJ_L": 2.2,
                "GMF_OBJ_M": 1.2,
                "GMF_OBJ_N": 1.4,
                "GMF_OBJ_O": 28.0,
                "GMF_OBJ_P": 12.0,
                "GMF_OBJ_Q": 16.0,
                "GMF_OBJ_R": 3.0,
                "GMF_OBJ_S": 10.0,
                "GMF_OBJ_T": 12.0,
                "GMF_OBJ_U": 6.0,
                "GMF_OBJ_V": 6.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                ),
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                    "stage_21_annulus_gmf_sequence_clean",
                    "stage_22_annulus_gmf_sequence_defect",
                ),
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 120,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 48,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "seqval_defect_anchor",
                "tag": "sva",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.2e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.94,
                    "W_EDGE_ORI_SIMPLE": 0.42,
                    "SEQ_LOSS_WEIGHT": 0.24,
                    "SEQ_GRAD_WEIGHT": 0.08,
                },
            },
            {
                "name": "seqval_clean_anchor",
                "tag": "svc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_21_annulus_gmf_sequence_clean",
                    ),
                    "LR": 3.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.90,
                    "W_EDGE_ORI_SIMPLE": 0.38,
                    "SEQ_LOSS_WEIGHT": 0.26,
                    "SEQ_GRAD_WEIGHT": 0.10,
                },
            },
            {
                "name": "seqval_general_bridge",
                "tag": "svg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                        "stage_21_annulus_gmf_sequence_clean",
                        "stage_22_annulus_gmf_sequence_defect",
                    ),
                    "LR": 3.4e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.98,
                    "W_EDGE_ORI_SIMPLE": 0.44,
                    "SEQ_LOSS_WEIGHT": 0.20,
                    "SEQ_GRAD_WEIGHT": 0.06,
                },
            },
            {
                "name": "seqval_sign_guard",
                "tag": "svs",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_14_annulus_edge_defect_focus",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                        "stage_21_annulus_gmf_sequence_clean",
                        "stage_22_annulus_gmf_sequence_defect",
                    ),
                    "LR": 2.8e-6,
                    "FREEZE_PHYSICS_EPOCH": 18,
                    "PHYS_WARMUP_END": 18,
                    "WEAK_PSF_STAGE0_EPOCHS": 18,
                    "WEAK_PSF_STAGE1_EPOCHS": 28,
                    "WEAK_PSF_ACTIVE_START_E": 19,
                    "W_GRADMAG": 0.88,
                    "W_EDGE_ORI_SIMPLE": 0.36,
                    "SEQ_LOSS_WEIGHT": 0.30,
                    "SEQ_GRAD_WEIGHT": 0.12,
                },
            },
        ]
    elif args.profile == "round10_crossscale_seqval":
        common_overrides.update(
            {
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.18,
                "EQ_WARMUP_OFF_E": 8,
                "EQ_RAMP_START_E": 9,
                "EQ_RAMP_END_E": 22,
                "W_EQ_GEOM": 0.40,
                "W_STAT": 0.008,
                "W_BAND": 0.006,
                "W_HF_LAP": 0.045,
                "W_EDGELOCAL_LAP_END": 0.026,
                "W_DETAIL_BASE": 0.004,
                "GMF_VAL_NUM_FRAMES": 9,
                "GMF_W_STEP_STD": 3.6,
                "GMF_W_OUTLIER": 4.6,
                "GMF_W_STEP_ERR": 2.4,
                "GMF_OBJ_J": 7.0,
                "GMF_OBJ_K": 6.0,
                "GMF_OBJ_L": 1.8,
                "GMF_OBJ_M": 1.0,
                "GMF_OBJ_N": 1.2,
                "GMF_OBJ_O": 24.0,
                "GMF_OBJ_P": 10.0,
                "GMF_OBJ_Q": 14.0,
                "GMF_OBJ_R": 2.5,
                "GMF_OBJ_S": 8.0,
                "GMF_OBJ_T": 10.0,
                "GMF_OBJ_U": 5.0,
                "GMF_OBJ_V": 5.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                ),
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 200,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                ),
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 120,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 48,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "crossscale_annulus_guard",
                "tag": "cag",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.4e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "W_GRADMAG": 0.96,
                    "W_EDGE_ORI_SIMPLE": 0.42,
                    "SEQ_LOSS_WEIGHT": 0.18,
                    "SEQ_GRAD_WEIGHT": 0.06,
                },
            },
            {
                "name": "crossscale_curve_general",
                "tag": "ccg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_04_ellipses",
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_13_curve_clean_general",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.6e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "W_GRADMAG": 1.00,
                    "W_EDGE_ORI_SIMPLE": 0.46,
                    "SEQ_LOSS_WEIGHT": 0.16,
                    "SEQ_GRAD_WEIGHT": 0.05,
                },
            },
            {
                "name": "crossscale_clean_precision",
                "tag": "ccp",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_13_curve_clean_general",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_19_annulus_microstep_sequence_clean",
                    ),
                    "LR": 3.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 20,
                    "PHYS_WARMUP_END": 20,
                    "WEAK_PSF_STAGE0_EPOCHS": 20,
                    "WEAK_PSF_STAGE1_EPOCHS": 30,
                    "WEAK_PSF_ACTIVE_START_E": 21,
                    "W_GRADMAG": 0.92,
                    "W_EDGE_ORI_SIMPLE": 0.38,
                    "SEQ_LOSS_WEIGHT": 0.22,
                    "SEQ_GRAD_WEIGHT": 0.08,
                },
            },
        ]
    elif args.profile == "round11_annulus_gmf_align":
        common_overrides.update(
            {
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.12,
                "EQ_WARMUP_OFF_E": 6,
                "EQ_RAMP_START_E": 7,
                "EQ_RAMP_END_E": 18,
                "W_EQ_GEOM": 0.38,
                "W_STAT": 0.006,
                "W_BAND": 0.004,
                "W_HF_LAP": 0.035,
                "W_EDGELOCAL_LAP_END": 0.020,
                "W_DETAIL_BASE": 0.003,
                "SHIFT_MIX_TINY_P": 0.78,
                "SHIFT_MIX_MID_P": 0.16,
                "SHIFT_MIX_INT_P": 0.06,
                "SHIFT_TINY_RANGE": (0.004, 0.20),
                "SHIFT_MID_RANGE": (0.20, 1.00),
                "SHIFT_INT_RANGE": (1.0, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.62,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.14,
                "EQ_SHIFT_TINY_RANGE": (0.004, 0.16),
                "EQ_SHIFT_MID_RANGE": (0.16, 0.80),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_VAL_NUM_FRAMES": 9,
                "PROXY_SEARCH_RADIUS": 18,
                "PROXY_COARSE_STRIDE": 1,
                "PROXY_FINE_STRIDE": 1,
                "GMF_W_STEP_STD": 3.6,
                "GMF_W_OUTLIER": 4.6,
                "GMF_W_STEP_ERR": 2.4,
                "GMF_OBJ_J": 4.0,
                "GMF_OBJ_K": 3.0,
                "GMF_OBJ_L": 1.2,
                "GMF_OBJ_M": 0.8,
                "GMF_OBJ_N": 0.8,
                "GMF_OBJ_O": 34.0,
                "GMF_OBJ_P": 14.0,
                "GMF_OBJ_Q": 18.0,
                "GMF_OBJ_R": 3.5,
                "GMF_OBJ_S": 12.0,
                "GMF_OBJ_T": 14.0,
                "GMF_OBJ_U": 8.0,
                "GMF_OBJ_V": 8.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                    "stage_21_annulus_gmf_sequence_clean",
                    "stage_22_annulus_gmf_sequence_defect",
                ),
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": (
                    "stage_19_annulus_microstep_sequence_clean",
                    "stage_20_annulus_microstep_sequence_defect",
                    "stage_21_annulus_gmf_sequence_clean",
                    "stage_22_annulus_gmf_sequence_defect",
                ),
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 120,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 48,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "annulus_lock_clean",
                "tag": "alc",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_15_annulus_sparse_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_19_annulus_microstep_sequence_clean",
                    ),
                    "LR": 2.8e-6,
                    "FREEZE_PHYSICS_EPOCH": 16,
                    "PHYS_WARMUP_END": 16,
                    "WEAK_PSF_STAGE0_EPOCHS": 16,
                    "WEAK_PSF_STAGE1_EPOCHS": 24,
                    "WEAK_PSF_ACTIVE_START_E": 17,
                    "W_GRADMAG": 0.90,
                    "W_EDGE_ORI_SIMPLE": 0.34,
                    "SEQ_LOSS_WEIGHT": 0.20,
                    "SEQ_GRAD_WEIGHT": 0.08,
                },
            },
            {
                "name": "annulus_lock_defect",
                "tag": "ald",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_17_annulus_microstep_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 3.0e-6,
                    "FREEZE_PHYSICS_EPOCH": 16,
                    "PHYS_WARMUP_END": 16,
                    "WEAK_PSF_STAGE0_EPOCHS": 16,
                    "WEAK_PSF_STAGE1_EPOCHS": 24,
                    "WEAK_PSF_ACTIVE_START_E": 17,
                    "W_GRADMAG": 0.94,
                    "W_EDGE_ORI_SIMPLE": 0.38,
                    "SEQ_LOSS_WEIGHT": 0.24,
                    "SEQ_GRAD_WEIGHT": 0.10,
                },
            },
            {
                "name": "annulus_sign_stable",
                "tag": "ass",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_14_annulus_edge_defect_focus",
                        "stage_16_annulus_sparse_defect_clean",
                        "stage_18_annulus_microstep_defect",
                        "stage_19_annulus_microstep_sequence_clean",
                        "stage_20_annulus_microstep_sequence_defect",
                    ),
                    "LR": 2.6e-6,
                    "FREEZE_PHYSICS_EPOCH": 16,
                    "PHYS_WARMUP_END": 16,
                    "WEAK_PSF_STAGE0_EPOCHS": 16,
                    "WEAK_PSF_STAGE1_EPOCHS": 24,
                    "WEAK_PSF_ACTIVE_START_E": 17,
                    "W_GRADMAG": 0.86,
                    "W_EDGE_ORI_SIMPLE": 0.32,
                    "SEQ_LOSS_WEIGHT": 0.30,
                    "SEQ_GRAD_WEIGHT": 0.12,
                },
            },
        ]
    elif args.profile == "round15_centerlock_midgate":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        micro_guard_dirs = (
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        macro_guard_dirs = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            primary_dirs = macro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.74,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.16,
                "EQ_SHIFT_MIX_INT_P": 0.78,
            }
        elif expect_dy >= 0.5:
            primary_dirs = mid_primary_dirs
            bridge_dirs = macro_guard_dirs + micro_guard_dirs
            seq_pair_budget = 240
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        else:
            primary_dirs = micro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 208
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.22,
                "SHIFT_MIX_INT_P": 0.06,
                "EQ_SHIFT_MIX_TINY_P": 0.66,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        primary_clean_dirs = tuple(s for s in primary_dirs if "defect" not in s)
        primary_defect_dirs = tuple(s for s in primary_dirs if "defect" in s)
        bridge_clean_dirs = tuple(s for s in bridge_dirs if "defect" not in s)
        bridge_defect_dirs = tuple(s for s in bridge_dirs if "defect" in s)
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "centerlock_pure",
                "tag": "clp",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.55e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.24,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.92,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.05,
                    "SEQ_GEOM_THICK_WEIGHT": 0.16,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.42,
                },
            },
            {
                "name": "centerlock_defectguard",
                "tag": "cld",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_14_annulus_edge_defect_focus",
                        "stage_16_annulus_sparse_defect_clean",
                    ) + primary_dirs + bridge_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_defect_dirs + bridge_defect_dirs,
                    "LR": 1.65e-6,
                    "W_GRADMAG": 0.76,
                    "W_EDGE_ORI_SIMPLE": 0.26,
                    "SEQ_LOSS_WEIGHT": 0.06,
                    "SEQ_GRAD_WEIGHT": 0.022,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.88,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.06,
                    "SEQ_GEOM_THICK_WEIGHT": 0.18,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.44,
                },
            },
            {
                "name": "centerlock_macroguard",
                "tag": "clm",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_dirs + macro_guard_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs + macro_guard_dirs,
                    "LR": 1.70e-6,
                    "W_GRADMAG": 0.75,
                    "W_EDGE_ORI_SIMPLE": 0.25,
                    "SEQ_LOSS_WEIGHT": 0.06,
                    "SEQ_GRAD_WEIGHT": 0.020,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.82,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.06,
                    "SEQ_GEOM_THICK_WEIGHT": 0.16,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                "name": "centerlock_balanced",
                "tag": "clb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_dirs + bridge_clean_dirs + bridge_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs + bridge_dirs,
                    "LR": 1.65e-6,
                    "W_GRADMAG": 0.77,
                    "W_EDGE_ORI_SIMPLE": 0.26,
                    "SEQ_LOSS_WEIGHT": 0.055,
                    "SEQ_GRAD_WEIGHT": 0.020,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.84,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.06,
                    "SEQ_GEOM_THICK_WEIGHT": 0.17,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
        ]
    elif args.profile == "round16_edgefit_centerlock":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        micro_guard_dirs = (
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        macro_guard_dirs = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            primary_dirs = macro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.74,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.16,
                "EQ_SHIFT_MIX_INT_P": 0.78,
            }
        elif expect_dy >= 0.5:
            primary_dirs = mid_primary_dirs
            bridge_dirs = macro_guard_dirs + micro_guard_dirs
            seq_pair_budget = 240
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        else:
            primary_dirs = micro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 208
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.22,
                "SHIFT_MIX_INT_P": 0.06,
                "EQ_SHIFT_MIX_TINY_P": 0.66,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        primary_clean_dirs = tuple(s for s in primary_dirs if "defect" not in s)
        primary_defect_dirs = tuple(s for s in primary_dirs if "defect" in s)
        bridge_clean_dirs = tuple(s for s in bridge_dirs if "defect" not in s)
        bridge_defect_dirs = tuple(s for s in bridge_dirs if "defect" in s)
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                # round15 result: sign_acc=1.0 (direction solved), focus is center magnitude
                # algebraic_fit confirmed 2x better center accuracy vs soft_centroid on real outputs
                "SEQ_GEOM_METHOD": "algebraic_fit",
                "SEQ_MONO_WEIGHT": 0.0,  # direction already solved, save budget for center
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        # round16 candidates redesigned based on round15 results:
        # - round15 sign_acc=1.0 (direction solved) -> mono_weight=0 to save gradient budget
        # - diagnostic confirms algebraic_fit 2x better center accuracy at 0.8px
        # - center_w raised vs round15 (better estimator allows stronger direct signal)
        # - diversity: two pure algebraic candidates + one edge+light_drift + one high_center
        candidates = [
            {
                # Primary: algebraic_fit, no mono (direction solved), high center focus
                "name": "r16_algfit_pure",
                "tag": "r16ap",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.55e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.24,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "algebraic_fit",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.85,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                # algebraic_fit, light mono guard (5%), still high center
                "name": "r16_algfit_lightmono",
                "tag": "r16al",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.58e-6,
                    "W_GRADMAG": 0.73,
                    "W_EDGE_ORI_SIMPLE": 0.24,
                    "SEQ_LOSS_WEIGHT": 0.052,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "algebraic_fit",
                    "SEQ_MONO_WEIGHT": 0.05,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.80,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.13,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
            {
                # edge_centroid, no mono, very high center_w (best 8px stability from diagnostic)
                "name": "r16_edge_highcenter",
                "tag": "r16eh",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.55e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.017,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.88,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.36,
                },
            },
            {
                # algebraic_fit, no mono, emphasise drift consistency to reduce frame-frame jitter
                "name": "r16_algfit_driftfocus",
                "tag": "r16ad",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.60e-6,
                    "W_GRADMAG": 0.73,
                    "W_EDGE_ORI_SIMPLE": 0.24,
                    "SEQ_LOSS_WEIGHT": 0.055,
                    "SEQ_GRAD_WEIGHT": 0.019,
                    "SEQ_GEOM_METHOD": "algebraic_fit",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.78,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.13,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.58,
                },
            },
        ]
    elif args.profile == "round17_stepfix_centerlock":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        micro_guard_dirs = (
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        macro_guard_dirs = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            primary_dirs = macro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.74,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.16,
                "EQ_SHIFT_MIX_INT_P": 0.78,
            }
        elif expect_dy >= 0.5:
            primary_dirs = mid_primary_dirs
            bridge_dirs = macro_guard_dirs + micro_guard_dirs
            seq_pair_budget = 240
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        else:
            primary_dirs = micro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 208
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.22,
                "SHIFT_MIX_INT_P": 0.06,
                "EQ_SHIFT_MIX_TINY_P": 0.66,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        primary_clean_dirs = tuple(s for s in primary_dirs if "defect" not in s)
        primary_defect_dirs = tuple(s for s in primary_dirs if "defect" in s)
        bridge_clean_dirs = tuple(s for s in bridge_dirs if "defect" not in s)
        bridge_defect_dirs = tuple(s for s in bridge_dirs if "defect" in s)
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                # round16 result: edge_centroid gives best training gradient for center_err
                # step_err regressed (0.2924->0.4358) due to high center_w dominating gradient
                # round17 goal: restore step_err<0.40 while keeping center_err<0.87
                "SEQ_GEOM_METHOD": "edge_centroid",
                "SEQ_MONO_WEIGHT": 0.0,  # direction solved (sign_acc=1.0)
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        # round17 candidates: all resume from r16_edge_highcenter checkpoint
        # Strategy: fix step_err regression by lowering center_w and/or adding step_mag loss
        candidates = [
            {
                # Baseline fix: reduce center_w to 0.80 (from 0.88), boost seq_grad for step signal
                "name": "r17_ec_balanced",
                "tag": "r17eb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.022,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.0,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.80,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                # Dedicated step magnitude loss + moderate center_w
                "name": "r17_ec_stepmag",
                "tag": "r17es",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.52e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.82,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                # algebraic_fit + step_mag loss: best measurement geom with dedicated step fix
                "name": "r17_af_stepmag",
                "tag": "r17as",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.55e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "algebraic_fit",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.82,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                # edge_centroid + boosted seq_grad + light step_mag: gradient-level step enforcement
                "name": "r17_ec_gradboost",
                "tag": "r17eg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.70,
                    "W_EDGE_ORI_SIMPLE": 0.22,
                    "SEQ_LOSS_WEIGHT": 0.055,
                    "SEQ_GRAD_WEIGHT": 0.030,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.20,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.80,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
        ]
    elif args.profile == "round18_centerpush":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        micro_guard_dirs = (
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        macro_guard_dirs = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            primary_dirs = macro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.74,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.16,
                "EQ_SHIFT_MIX_INT_P": 0.78,
            }
        elif expect_dy >= 0.5:
            primary_dirs = mid_primary_dirs
            bridge_dirs = macro_guard_dirs + micro_guard_dirs
            seq_pair_budget = 240
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        else:
            primary_dirs = micro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 208
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.22,
                "SHIFT_MIX_INT_P": 0.06,
                "EQ_SHIFT_MIX_TINY_P": 0.66,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        primary_clean_dirs = tuple(s for s in primary_dirs if "defect" not in s)
        primary_defect_dirs = tuple(s for s in primary_dirs if "defect" in s)
        bridge_clean_dirs = tuple(s for s in bridge_dirs if "defect" not in s)
        bridge_defect_dirs = tuple(s for s in bridge_dirs if "defect" in s)
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                # round17 result: ec_stepmag (center_w=0.82, step_mag_w=0.35) -> center_err=0.8508
                # round18 goal: push center_err below 0.82 threshold while keeping step_err<0.40
                "SEQ_GEOM_METHOD": "edge_centroid",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        # round18 candidates: all resume from r17_ec_stepmag checkpoint
        # Strategy: raise center_w to 0.83-0.86 while maintaining step_mag_w >= 0.30
        candidates = [
            {
                # Maximum center push: center_w=0.86 with step guard
                "name": "r18_ec_highcenter",
                "tag": "r18eh",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.52e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.30,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.86,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.36,
                },
            },
            {
                # Balanced push: center_w=0.84, same step_mag as r17 winner
                "name": "r18_ec_stepmag_up",
                "tag": "r18eu",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.84,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                # algebraic_fit + high center: best measurement geom with center push
                "name": "r18_af_highcenter",
                "tag": "r18ah",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.55e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "algebraic_fit",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.32,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.84,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                # Conservative push: center_w=0.83, higher step_mag for extra step protection
                "name": "r18_ec_balanced",
                "tag": "r18eb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.020,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_STEP_MAG_WEIGHT": 0.38,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.83,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
        ]
    elif args.profile == "branchE_estimator_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        round18_manifest = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "current_centerpush_seed.json"
        )
        round18_fallback = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = _resolve_manifest_checkpoint(round18_manifest, str(round18_fallback))
        if not seed_ckpt:
            raise FileNotFoundError(f"BranchE seed manifest unresolved: {round18_manifest}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "edge_centroid",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        train_dirs = static_annulus_core + tuple(s for s in mid_primary_dirs if "defect" not in s) + tuple(
            s for s in mid_primary_dirs if "defect" in s
        )
        base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": train_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.52e-6,
            "W_GRADMAG": 0.72,
            "W_EDGE_ORI_SIMPLE": 0.23,
            "SEQ_LOSS_WEIGHT": 0.05,
            "SEQ_GRAD_WEIGHT": 0.018,
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_STEP_MAG_WEIGHT": 0.30,
            "SEQ_GEOM_CENTER_WEIGHT": 0.86,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.36,
        }
        candidates = [
            {
                "name": "be_ctrl_edge",
                "tag": "bece",
                "overrides": {
                    **base_probe,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                },
            },
            {
                "name": "be_soft",
                "tag": "besc",
                "overrides": {
                    **base_probe,
                    "SEQ_GEOM_METHOD": "soft_centroid",
                },
            },
            {
                "name": "be_edge_band",
                "tag": "beeb",
                "overrides": {
                    **base_probe,
                    "SEQ_GEOM_METHOD": "edge_band_refine",
                },
            },
            {
                "name": "be_soft_band",
                "tag": "besb",
                "overrides": {
                    **base_probe,
                    "SEQ_GEOM_METHOD": "soft_band_refine",
                },
            },
            {
                "name": "be_edge_algfit",
                "tag": "beaf",
                "overrides": {
                    **base_probe,
                    "SEQ_GEOM_METHOD": "edge_algebraic_fit",
                },
            },
        ]
    elif args.profile == "round21_hybrid_estimator_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        round18_manifest = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "current_centerpush_seed.json"
        )
        round18_fallback = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = _resolve_manifest_checkpoint(round18_manifest, str(round18_fallback))
        if not seed_ckpt:
            raise FileNotFoundError(f"Round21 seed manifest unresolved: {round18_manifest}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "soft_band_refine",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.52e-6,
            "W_GRADMAG": 0.72,
            "W_EDGE_ORI_SIMPLE": 0.23,
            "SEQ_LOSS_WEIGHT": 0.05,
            "SEQ_GRAD_WEIGHT": 0.018,
            "SEQ_GEOM_METHOD": "soft_band_refine",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
        }
        candidates = [
            {
                "name": "r21_midsoft_ctrlguard",
                "tag": "r21mcg",
                "overrides": {
                    **base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.30,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.86,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.36,
                },
            },
            {
                "name": "r21_midsoft_stepup",
                "tag": "r21msu",
                "overrides": {
                    **base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.38,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.78,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                "name": "r21_midsoft_stephard",
                "tag": "r21msh",
                "overrides": {
                    **base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.45,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.72,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
        ]
    elif args.profile == "round22_pairmix_hybrid_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        round18_manifest = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "current_centerpush_seed.json"
        )
        round18_fallback = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = _resolve_manifest_checkpoint(round18_manifest, str(round18_fallback))
        if not seed_ckpt:
            raise FileNotFoundError(f"Round22 seed manifest unresolved: {round18_manifest}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
        }
        candidates = [
            {
                "name": "r22_pairmix_hold",
                "tag": "r22ph",
                "overrides": {
                    **base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.20,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.70,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
                },
            },
            {
                "name": "r22_pairmix_stepguard",
                "tag": "r22ps",
                "overrides": {
                    **base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.28,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.62,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.30,
                },
            },
            {
                "name": "r22_pairmix_consistency",
                "tag": "r22pc",
                "overrides": {
                    **base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.34,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.56,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.34,
                },
            },
        ]
    elif args.profile == "round23_anchor_consistency_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        round18_manifest = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "current_centerpush_seed.json"
        )
        round18_fallback = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = _resolve_manifest_checkpoint(round18_manifest, str(round18_fallback))
        if not seed_ckpt:
            raise FileNotFoundError(f"Round23 seed manifest unresolved: {round18_manifest}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
        }
        base_hold_probe = {
            **base_probe,
            "SEQ_STEP_MAG_WEIGHT": 0.20,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
        }
        candidates = [
            {
                "name": "r23_pac_w003",
                "tag": "r23w03",
                "overrides": {
                    **base_hold_probe,
                    "SEQ_ABS_CENTER_WEIGHT": 0.03,
                },
            },
            {
                "name": "r23_pac_w005",
                "tag": "r23w05",
                "overrides": {
                    **base_hold_probe,
                    "SEQ_ABS_CENTER_WEIGHT": 0.05,
                },
            },
            {
                "name": "r23_pac_w010",
                "tag": "r23w10",
                "overrides": {
                    **base_hold_probe,
                    "SEQ_ABS_CENTER_WEIGHT": 0.10,
                },
            },
        ]
    elif args.profile == "round24_single_abs_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        round22_hold_checkpoint = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260315"
            / "round22"
            / "archive"
            / "runs"
            / "training_progress_GESR_v1_v5_ST0p8_SWP_r22ph_20260315_225256"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = str(round22_hold_checkpoint) if round22_hold_checkpoint.exists() else ""
        if not seed_ckpt:
            raise FileNotFoundError(f"Round24 control baseline unresolved: {round22_hold_checkpoint}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.0,
        }
        base_hold_probe = {
            **base_probe,
            "SEQ_STEP_MAG_WEIGHT": 0.20,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
        }
        candidates = [
            {
                "name": "r24_sac_w010",
                "tag": "r24s10",
                "overrides": {
                    **base_hold_probe,
                    "SEQ_ABS_CENTER_WEIGHT": 0.0,
                    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
                },
            },
            {
                "name": "r24_sac_w030",
                "tag": "r24s30",
                "overrides": {
                    **base_hold_probe,
                    "SEQ_ABS_CENTER_WEIGHT": 0.0,
                    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.30,
                },
            },
            {
                "name": "r24_sac_w050",
                "tag": "r24s50",
                "overrides": {
                    **base_hold_probe,
                    "SEQ_ABS_CENTER_WEIGHT": 0.0,
                    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.50,
                },
            },
        ]
    elif args.profile == "round25_scratch_abs":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        r25_r18_seed_ckpt = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round18"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r18eh_20260313_141756"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = str(r25_r18_seed_ckpt) if r25_r18_seed_ckpt.exists() else ""
        if not seed_ckpt:
            raise FileNotFoundError(f"Round25 scratch seed unresolved: {r25_r18_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        r25_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_STEP_MAG_WEIGHT": 0.20,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.0,
        }
        candidates = [
            {
                "name": "r25_sw005",
                "tag": "r25sw005",
                "overrides": {
                    **r25_base_probe,
                    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.05,
                },
            },
            {
                "name": "r25_sw010",
                "tag": "r25sw010",
                "overrides": {
                    **r25_base_probe,
                    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
                },
            },
            {
                "name": "r25_sw020",
                "tag": "r25sw020",
                "overrides": {
                    **r25_base_probe,
                    "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.20,
                },
            },
        ]
    elif args.profile == "round26_step_recovery_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        if not Path(r26_r25_seed_ckpt).exists():
            raise FileNotFoundError(f"Round26 step recovery seed unresolved: {r26_r25_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        r26_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": r26_r25_seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
            "SEQ_STEP_MAG_WEIGHT": 0.20,
        }
        candidates = [
            {
                "name": "r26_sm025",
                "tag": "r26sm025",
                "overrides": {
                    **r26_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.25,
                },
            },
            {
                "name": "r26_sm030",
                "tag": "r26sm030",
                "overrides": {
                    **r26_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.30,
                },
            },
            {
                "name": "r26_sm035",
                "tag": "r26sm035",
                "overrides": {
                    **r26_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                },
            },
        ]
    elif args.profile == "round27_step_mag_recovery":
        # Round27: fine-tune from R26 sm035, sweep step_mag downward to recover 0.08px
        # R26 (step_mag=0.35) had 0.08px slight regression vs R25 (+9.4%).
        # Hypothesis: step_mag 0.25-0.30 recovers 0.08px while keeping 0.8px improvement.
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        if not Path(r27_r26_seed_ckpt).exists():
            raise FileNotFoundError(f"Round27 step mag recovery seed unresolved: {r27_r26_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        r27_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": r27_r26_seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
            "SEQ_STEP_MAG_WEIGHT": 0.28,
        }
        candidates = [
            {
                "name": "r27_sm025",
                "tag": "r27sm025",
                "overrides": {
                    **r27_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.25,
                },
            },
            {
                "name": "r27_sm028",
                "tag": "r27sm028",
                "overrides": {
                    **r27_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.28,
                },
            },
            {
                "name": "r27_sm030",
                "tag": "r27sm030",
                "overrides": {
                    **r27_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.30,
                },
            },
        ]
    elif args.profile == "round28_abs_center_sweep":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        if not Path(r28_r26_seed_ckpt).exists():
            raise FileNotFoundError(f"Round28 step_mag balance seed unresolved: {r28_r26_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        # Seed from R26 (not R27): R27 showed 0.8px regressed vs R26 at step_mag=0.28.
        # Sweet spot search: step_mag in [0.30, 0.32, 0.33] from R26 baseline.
        r28_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": r28_r26_seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
        }
        candidates = [
            {
                "name": "r28_sm030",
                "tag": "r28sm030",
                "overrides": {
                    **r28_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.30,
                },
            },
            {
                "name": "r28_sm032",
                "tag": "r28sm032",
                "overrides": {
                    **r28_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.32,
                },
            },
            {
                "name": "r28_sm033",
                "tag": "r28sm033",
                "overrides": {
                    **r28_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.33,
                },
            },
        ]
    elif args.profile == "round29_step_mag_upper":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        if not Path(r28_r26_seed_ckpt).exists():
            raise FileNotFoundError(f"Round29 step_mag upper seed unresolved: {r28_r26_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        # Seed from R26 sm035 (same as R28): exploring step_mag ABOVE 0.35.
        # Hypothesis: R25(0.20)->R26(0.35) improved 0.8px by 9.7%; continuing upper sweep
        # may push further. Candidates: 0.38, 0.40, 0.42.
        r29_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": r28_r26_seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
        }
        candidates = [
            {
                "name": "r29_sm038",
                "tag": "r29sm038",
                "overrides": {
                    **r29_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.38,
                },
            },
            {
                "name": "r29_sm040",
                "tag": "r29sm040",
                "overrides": {
                    **r29_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.40,
                },
            },
            {
                "name": "r29_sm042",
                "tag": "r29sm042",
                "overrides": {
                    **r29_base_probe,
                    "SEQ_STEP_MAG_WEIGHT": 0.42,
                },
            },
        ]

    elif args.profile == "round30_architecture_breakthrough":
        # Round 30: Architecture breakthrough — B1 + A1 + A5
        # New mechanisms (NOT hyperparam sweep):
        #   B1: Direction-oriented equivariance loss (EQ_GEOM_USE_DIRECTION)
        #   A1: Learnable anti-aliasing blur (LEARNABLE_BLUR)
        #   A5: Bottleneck SE attention (USE_BOTTLENECK_SE)
        # Seed: R26 sm035 (FINAL baseline)
        # Challenge target: 0.8px step_std < 0.191336
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        if not Path(r28_r26_seed_ckpt).exists():
            raise FileNotFoundError(f"Round30 seed unresolved: {r28_r26_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        # Base probe from R26: same hyperparams as R26 winner
        r30_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": r28_r26_seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
            "SEQ_STEP_MAG_WEIGHT": 0.35,  # R26 sweet spot
        }
        candidates = [
            {
                # Candidate 1: B1 only — direction equivariance, no arch changes
                "name": "r30_b1_dironly",
                "tag": "r30b1dir",
                "overrides": {
                    **r30_base_probe,
                    "EQ_GEOM_USE_DIRECTION": True,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
                    "W_EQ_GEOM": 0.26,
                },
            },
            {
                # Candidate 2: B1 + A1 — direction eq + learnable blur
                "name": "r30_b1a1_dir_lblur",
                "tag": "r30b1a1",
                "overrides": {
                    **r30_base_probe,
                    "EQ_GEOM_USE_DIRECTION": True,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
                    "W_EQ_GEOM": 0.26,
                    "LEARNABLE_BLUR": True,
                },
            },
            {
                # Candidate 3: B1 + A1 + A5 — full architecture breakthrough
                "name": "r30_b1a1a5_full",
                "tag": "r30full",
                "overrides": {
                    **r30_base_probe,
                    "EQ_GEOM_USE_DIRECTION": True,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
                    "W_EQ_GEOM": 0.26,
                    "LEARNABLE_BLUR": True,
                    "USE_BOTTLENECK_SE": True,
                    "BOTTLENECK_SE_REDUCTION": 4,
                },
            },
        ]

    elif args.profile == "round31_b1_hyperparam":
        # Round 31: B1 hyperparam tuning from the Round30 B1-only seed
        # Base config remains r30_b1_dironly:
        #   EQ_GEOM_USE_DIRECTION=True
        #   no LEARNABLE_BLUR
        #   no USE_BOTTLENECK_SE
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        if not Path(r31_r30_b1_seed_ckpt).exists():
            raise FileNotFoundError(f"Round31 seed unresolved: {r31_r30_b1_seed_ckpt}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "pairmix_algblend",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
                "BASELINE_ELIGIBLE_FOR_BEST": True,
                "BEST_PROXY_MIN_EPOCH": 0,
            }
        )
        r31_base_probe = {
            "LOAD_MODEL": True,
            "PRETRAINED_PATH": r31_r30_b1_seed_ckpt,
            "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + mid_primary_dirs,
            "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
            "LR": 1.10e-6,
            "W_GRADMAG": 0.70,
            "W_EDGE_ORI_SIMPLE": 0.22,
            "SEQ_LOSS_WEIGHT": 0.045,
            "SEQ_GRAD_WEIGHT": 0.016,
            "SEQ_GEOM_METHOD": "pairmix_algblend",
            "SEQ_MONO_WEIGHT": 0.0,
            "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
            "SEQ_GEOM_THICK_WEIGHT": 0.12,
            "SEQ_ABS_CENTER_WEIGHT": 0.0,
            "SEQ_GEOM_CENTER_WEIGHT": 0.70,
            "SEQ_GEOM_DRIFT_WEIGHT": 0.28,
            "SEQ_SINGLE_ABS_CENTER_WEIGHT": 0.10,
            "SEQ_STEP_MAG_WEIGHT": 0.35,
            "EQ_GEOM_USE_DIRECTION": True,
            "LEARNABLE_BLUR": False,
            "USE_BOTTLENECK_SE": False,
        }
        candidates = [
            {
                "name": "r31_eq_prob_up",
                "tag": "r31eqprobup",
                "overrides": {
                    **r31_base_probe,
                    "EQ_PROB": 0.12,
                    "W_EQ_GEOM": 0.26,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
                },
            },
            {
                "name": "r31_eq_weight_up",
                "tag": "r31eqweightup",
                "overrides": {
                    **r31_base_probe,
                    "EQ_PROB": 0.06,
                    "W_EQ_GEOM": 0.40,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
                },
            },
            {
                "name": "r31_eq_combo",
                "tag": "r31eqcombo",
                "overrides": {
                    **r31_base_probe,
                    "EQ_PROB": 0.10,
                    "W_EQ_GEOM": 0.35,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.5,
                },
            },
            {
                "name": "r31_edge_ratio_low",
                "tag": "r31edgerlow",
                "overrides": {
                    **r31_base_probe,
                    "EQ_PROB": 0.10,
                    "W_EQ_GEOM": 0.26,
                    "EQ_GEOM_DIR_EDGE_RATIO": 0.3,
                },
            },
        ]

    elif args.profile == "round20_process_probe":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        round17_manifest = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round17"
            / "selected"
            / "current_stepfix_seed.json"
        )
        round17_fallback = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round17"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r17es_20260313_130154"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = _resolve_manifest_checkpoint(round17_manifest, str(round17_fallback))
        if not seed_ckpt:
            raise FileNotFoundError(f"Round20 seed manifest unresolved: {round17_manifest}")

        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": 240,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": mid_primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": 240,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "edge_centroid",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
            }
        )
        candidates = [
            {
                "name": "r20_ctrl_r19aa",
                "tag": "r20ca",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + tuple(s for s in mid_primary_dirs if "defect" not in s) + tuple(s for s in mid_primary_dirs if "defect" in s),
                    "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.30,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.55,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                    "BASELINE_ELIGIBLE_FOR_BEST": True,
                    "BEST_PROXY_MIN_EPOCH": 0,
                    "AUTO_SWEEP_SWEEP_EPOCHS": 4,
                },
            },
            {
                "name": "r20_unlock_r19aa",
                "tag": "r20ua",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + tuple(s for s in mid_primary_dirs if "defect" not in s) + tuple(s for s in mid_primary_dirs if "defect" in s),
                    "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.30,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.55,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                    "BASELINE_ELIGIBLE_FOR_BEST": False,
                    "BEST_PROXY_MIN_EPOCH": 1,
                    "AUTO_SWEEP_SWEEP_EPOCHS": 4,
                    "AUTO_SWEEP_BEST_EPOCH_MIN": 1,
                    "AUTO_SWEEP_BEST_EPOCH_MAX": 4,
                },
            },
            {
                "name": "r20_unlocklong_r19aa",
                "tag": "r20ul",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + tuple(s for s in mid_primary_dirs if "defect" not in s) + tuple(s for s in mid_primary_dirs if "defect" in s),
                    "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.30,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.55,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                    "BASELINE_ELIGIBLE_FOR_BEST": False,
                    "BEST_PROXY_MIN_EPOCH": 1,
                    "AUTO_SWEEP_SWEEP_EPOCHS": 8,
                    "AUTO_SWEEP_BEST_EPOCH_MIN": 1,
                    "AUTO_SWEEP_BEST_EPOCH_MAX": 8,
                },
            },
            {
                "name": "r20_unlock_r19as",
                "tag": "r20us",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + tuple(s for s in mid_primary_dirs if "defect" not in s) + tuple(s for s in mid_primary_dirs if "defect" in s),
                    "SEQ_INCLUDE_SUBDIRS": mid_primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.50,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.45,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                    "BASELINE_ELIGIBLE_FOR_BEST": False,
                    "BEST_PROXY_MIN_EPOCH": 1,
                    "AUTO_SWEEP_SWEEP_EPOCHS": 8,
                    "AUTO_SWEEP_BEST_EPOCH_MIN": 1,
                    "AUTO_SWEEP_BEST_EPOCH_MAX": 8,
                },
            },
        ]
    elif args.profile == "round19_absanchor":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        micro_guard_dirs = (
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        macro_guard_dirs = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        round17_manifest = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round17"
            / "selected"
            / "current_stepfix_seed.json"
        )
        round17_fallback = (
            Path(train_mod.PROJECT_ROOT)
            / "Traing_Progress"
            / "organized_20260313"
            / "round17"
            / "selected"
            / "runs"
            / "training_progress_GESR_v1_v5_ST8_SWP_r17es_20260313_130154"
            / "weights"
            / "best_tradeoff.pth.tar"
        )
        seed_ckpt = _resolve_manifest_checkpoint(round17_manifest, str(round17_fallback))
        if not seed_ckpt:
            raise FileNotFoundError(f"Round19 seed manifest unresolved: {round17_manifest}")

        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            primary_dirs = macro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.74,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.16,
                "EQ_SHIFT_MIX_INT_P": 0.78,
            }
        elif expect_dy >= 0.5:
            primary_dirs = mid_primary_dirs
            bridge_dirs = macro_guard_dirs + micro_guard_dirs
            seq_pair_budget = 240
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.08,
                "SHIFT_MIX_MID_P": 0.82,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.06,
                "EQ_SHIFT_MIX_MID_P": 0.84,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        else:
            primary_dirs = micro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 208
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.72,
                "SHIFT_MIX_MID_P": 0.22,
                "SHIFT_MIX_INT_P": 0.06,
                "EQ_SHIFT_MIX_TINY_P": 0.66,
                "EQ_SHIFT_MIX_MID_P": 0.24,
                "EQ_SHIFT_MIX_INT_P": 0.10,
            }
        primary_clean_dirs = tuple(s for s in primary_dirs if "defect" not in s)
        primary_defect_dirs = tuple(s for s in primary_dirs if "defect" in s)
        bridge_clean_dirs = tuple(s for s in bridge_dirs if "defect" not in s)
        bridge_defect_dirs = tuple(s for s in bridge_dirs if "defect" in s)
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.06,
                "EQ_WARMUP_OFF_E": 4,
                "EQ_RAMP_START_E": 5,
                "EQ_RAMP_END_E": 12,
                "W_EQ_GEOM": 0.26,
                "W_STAT": 0.002,
                "W_BAND": 0.0015,
                "W_HF_LAP": 0.014,
                "W_EDGELOCAL_LAP_END": 0.010,
                "W_DETAIL_BASE": 0.0005,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.01, 0.28),
                "SHIFT_MID_RANGE": (0.28, 1.10),
                "SHIFT_INT_RANGE": (1.10, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.20),
                "EQ_SHIFT_MID_RANGE": (0.20, 0.90),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.6,
                "GMF_OBJ_K": 4.4,
                "GMF_OBJ_L": 1.0,
                "GMF_OBJ_M": 0.7,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 30.0,
                "GMF_OBJ_P": 22.0,
                "GMF_OBJ_Q": 34.0,
                "GMF_OBJ_R": 10.0,
                "GMF_OBJ_S": 16.0,
                "GMF_OBJ_T": 20.0,
                "GMF_OBJ_U": 18.0,
                "GMF_OBJ_V": 14.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                "SEQ_GEOM_METHOD": "edge_centroid",
                "SEQ_MONO_WEIGHT": 0.0,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 56,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "r19_abs_anchor",
                "tag": "r19aa",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.30,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.55,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
            {
                "name": "r19_abs_strong",
                "tag": "r19as",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.50,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.45,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.38,
                },
            },
            {
                "name": "r19_af_abs",
                "tag": "r19af",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.55e-6,
                    "W_GRADMAG": 0.72,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "algebraic_fit",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.35,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.50,
                    "SEQ_STEP_MAG_WEIGHT": 0.38,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.36,
                },
            },
            {
                "name": "r19_abs_only",
                "tag": "r19ao",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_clean_dirs + primary_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                    "LR": 1.50e-6,
                    "W_GRADMAG": 0.71,
                    "W_EDGE_ORI_SIMPLE": 0.23,
                    "SEQ_LOSS_WEIGHT": 0.05,
                    "SEQ_GRAD_WEIGHT": 0.018,
                    "SEQ_GEOM_METHOD": "edge_centroid",
                    "SEQ_MONO_WEIGHT": 0.0,
                    "SEQ_ABS_CENTER_WEIGHT": 0.65,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.00,
                    "SEQ_STEP_MAG_WEIGHT": 0.35,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.04,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.40,
                },
            },
        ]
    elif args.profile == "round14_corridor_midgate":
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        micro_guard_dirs = (
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        mid_primary_dirs = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
            "stage_27_annulus_gmf_sequence_midwide_clean",
            "stage_28_annulus_gmf_sequence_midwide_defect",
        )
        macro_guard_dirs = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            primary_dirs = macro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.10,
                "SHIFT_MIX_MID_P": 0.18,
                "SHIFT_MIX_INT_P": 0.72,
                "EQ_SHIFT_MIX_TINY_P": 0.08,
                "EQ_SHIFT_MIX_MID_P": 0.16,
                "EQ_SHIFT_MIX_INT_P": 0.76,
            }
        elif expect_dy >= 0.5:
            primary_dirs = mid_primary_dirs
            bridge_dirs = macro_guard_dirs + micro_guard_dirs
            seq_pair_budget = 224
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.12,
                "SHIFT_MIX_MID_P": 0.74,
                "SHIFT_MIX_INT_P": 0.14,
                "EQ_SHIFT_MIX_TINY_P": 0.10,
                "EQ_SHIFT_MIX_MID_P": 0.76,
                "EQ_SHIFT_MIX_INT_P": 0.14,
            }
        else:
            primary_dirs = micro_guard_dirs
            bridge_dirs = mid_primary_dirs
            seq_pair_budget = 208
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.70,
                "SHIFT_MIX_MID_P": 0.24,
                "SHIFT_MIX_INT_P": 0.06,
                "EQ_SHIFT_MIX_TINY_P": 0.64,
                "EQ_SHIFT_MIX_MID_P": 0.28,
                "EQ_SHIFT_MIX_INT_P": 0.08,
            }
        primary_clean_dirs = tuple(s for s in primary_dirs if "defect" not in s)
        primary_defect_dirs = tuple(s for s in primary_dirs if "defect" in s)
        bridge_clean_dirs = tuple(s for s in bridge_dirs if "defect" not in s)
        bridge_defect_dirs = tuple(s for s in bridge_dirs if "defect" in s)
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.08,
                "EQ_WARMUP_OFF_E": 5,
                "EQ_RAMP_START_E": 6,
                "EQ_RAMP_END_E": 14,
                "W_EQ_GEOM": 0.30,
                "W_STAT": 0.003,
                "W_BAND": 0.002,
                "W_HF_LAP": 0.020,
                "W_EDGELOCAL_LAP_END": 0.012,
                "W_DETAIL_BASE": 0.001,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.01, 0.30),
                "SHIFT_MID_RANGE": (0.30, 1.25),
                "SHIFT_INT_RANGE": (1.25, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.01, 0.24),
                "EQ_SHIFT_MID_RANGE": (0.24, 1.05),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 3.0,
                "GMF_OBJ_K": 4.0,
                "GMF_OBJ_L": 1.2,
                "GMF_OBJ_M": 0.8,
                "GMF_OBJ_N": 0.8,
                "GMF_OBJ_O": 34.0,
                "GMF_OBJ_P": 24.0,
                "GMF_OBJ_Q": 28.0,
                "GMF_OBJ_R": 8.0,
                "GMF_OBJ_S": 12.0,
                "GMF_OBJ_T": 18.0,
                "GMF_OBJ_U": 12.0,
                "GMF_OBJ_V": 12.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": primary_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 48,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "corridor_centerlock",
                "tag": "ccl",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_15_annulus_sparse_clean",
                    ) + primary_clean_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_clean_dirs,
                    "LR": 1.7e-6,
                    "W_GRADMAG": 0.78,
                    "W_EDGE_ORI_SIMPLE": 0.28,
                    "SEQ_LOSS_WEIGHT": 0.06,
                    "SEQ_GRAD_WEIGHT": 0.025,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.72,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.08,
                    "SEQ_GEOM_THICK_WEIGHT": 0.24,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.34,
                },
            },
            {
                "name": "corridor_defectguard",
                "tag": "cdg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_14_annulus_edge_defect_focus",
                        "stage_16_annulus_sparse_defect_clean",
                    ) + primary_defect_dirs + bridge_defect_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_defect_dirs + bridge_defect_dirs,
                    "LR": 1.8e-6,
                    "W_GRADMAG": 0.82,
                    "W_EDGE_ORI_SIMPLE": 0.30,
                    "SEQ_LOSS_WEIGHT": 0.08,
                    "SEQ_GRAD_WEIGHT": 0.035,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.64,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.10,
                    "SEQ_GEOM_THICK_WEIGHT": 0.28,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.36,
                },
            },
            {
                "name": "corridor_macrobridge",
                "tag": "cmb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_dirs + macro_guard_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs + macro_guard_dirs,
                    "LR": 1.9e-6,
                    "W_GRADMAG": 0.80,
                    "W_EDGE_ORI_SIMPLE": 0.29,
                    "SEQ_LOSS_WEIGHT": 0.07,
                    "SEQ_GRAD_WEIGHT": 0.03,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.58,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.09,
                    "SEQ_GEOM_THICK_WEIGHT": 0.20,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.26,
                },
            },
            {
                "name": "corridor_microbridge",
                "tag": "cib",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_dirs + micro_guard_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs + micro_guard_dirs,
                    "LR": 1.8e-6,
                    "W_GRADMAG": 0.84,
                    "W_EDGE_ORI_SIMPLE": 0.31,
                    "SEQ_LOSS_WEIGHT": 0.09,
                    "SEQ_GRAD_WEIGHT": 0.05,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.60,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.08,
                    "SEQ_GEOM_THICK_WEIGHT": 0.22,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.30,
                },
            },
            {
                "name": "corridor_balanced",
                "tag": "cbl",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + primary_dirs + bridge_dirs,
                    "SEQ_INCLUDE_SUBDIRS": primary_dirs + bridge_dirs,
                    "LR": 1.85e-6,
                    "W_GRADMAG": 0.81,
                    "W_EDGE_ORI_SIMPLE": 0.30,
                    "SEQ_LOSS_WEIGHT": 0.07,
                    "SEQ_GRAD_WEIGHT": 0.03,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.62,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.09,
                    "SEQ_GEOM_THICK_WEIGHT": 0.24,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.32,
                },
            },
        ]
    elif args.profile in ("round12_universal_annulus_align", "round13_universal_gated"):
        is_round13 = args.profile == "round13_universal_gated"
        static_annulus_core = (
            "stage_08_annulus_focus",
            "stage_09_annulus_non_overlap",
            "stage_10_annulus_overlap",
            "stage_14_annulus_edge_defect_focus",
            "stage_15_annulus_sparse_clean",
            "stage_16_annulus_sparse_defect_clean",
        )
        seq_train_dirs_micro = (
            "stage_17_annulus_microstep_clean",
            "stage_18_annulus_microstep_defect",
            "stage_19_annulus_microstep_sequence_clean",
            "stage_20_annulus_microstep_sequence_defect",
            "stage_21_annulus_gmf_sequence_clean",
            "stage_22_annulus_gmf_sequence_defect",
        )
        seq_train_dirs_mid = (
            "stage_23_annulus_gmf_sequence_mid_clean",
            "stage_24_annulus_gmf_sequence_mid_defect",
        )
        seq_train_dirs_macro = (
            "stage_25_annulus_gmf_sequence_macro_clean",
            "stage_26_annulus_gmf_sequence_macro_defect",
        )
        expect_dy = float(args.expect_dy)
        if expect_dy >= 7.5:
            seq_train_dirs = seq_train_dirs_macro
            seq_val_dirs = seq_train_dirs_macro
            seq_pair_budget = 160
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.20,
                "SHIFT_MIX_MID_P": 0.28,
                "SHIFT_MIX_INT_P": 0.52,
                "EQ_SHIFT_MIX_TINY_P": 0.14,
                "EQ_SHIFT_MIX_MID_P": 0.26,
                "EQ_SHIFT_MIX_INT_P": 0.60,
            }
        elif expect_dy >= 0.5:
            seq_train_dirs = seq_train_dirs_mid
            seq_val_dirs = seq_train_dirs_mid
            seq_pair_budget = 176
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.26,
                "SHIFT_MIX_MID_P": 0.56,
                "SHIFT_MIX_INT_P": 0.18,
                "EQ_SHIFT_MIX_TINY_P": 0.20,
                "EQ_SHIFT_MIX_MID_P": 0.58,
                "EQ_SHIFT_MIX_INT_P": 0.22,
            }
        else:
            seq_train_dirs = seq_train_dirs_micro
            seq_val_dirs = seq_train_dirs_micro
            seq_pair_budget = 192
            shift_mix = {
                "SHIFT_MIX_TINY_P": 0.62,
                "SHIFT_MIX_MID_P": 0.28,
                "SHIFT_MIX_INT_P": 0.10,
                "EQ_SHIFT_MIX_TINY_P": 0.56,
                "EQ_SHIFT_MIX_MID_P": 0.30,
                "EQ_SHIFT_MIX_INT_P": 0.14,
            }
        common_overrides.update(
            {
                "GMF_VALIDATE_ENABLE": False,
                "GMF_VALIDATE_SOURCE": "seq_val",
                "EQ_PROB": 0.12 if is_round13 else 0.10,
                "EQ_WARMUP_OFF_E": 6,
                "EQ_RAMP_START_E": 7,
                "EQ_RAMP_END_E": 18,
                "W_EQ_GEOM": 0.36 if is_round13 else 0.34,
                "W_STAT": 0.004,
                "W_BAND": 0.003,
                "W_HF_LAP": 0.025,
                "W_EDGELOCAL_LAP_END": 0.015,
                "W_DETAIL_BASE": 0.002,
                "SHIFT_MIX_TINY_P": shift_mix["SHIFT_MIX_TINY_P"],
                "SHIFT_MIX_MID_P": shift_mix["SHIFT_MIX_MID_P"],
                "SHIFT_MIX_INT_P": shift_mix["SHIFT_MIX_INT_P"],
                "SHIFT_TINY_RANGE": (0.004, 0.20),
                "SHIFT_MID_RANGE": (0.20, 1.00),
                "SHIFT_INT_RANGE": (1.0, 8.0),
                "EQ_SHIFT_MIX_TINY_P": shift_mix["EQ_SHIFT_MIX_TINY_P"],
                "EQ_SHIFT_MIX_MID_P": shift_mix["EQ_SHIFT_MIX_MID_P"],
                "EQ_SHIFT_MIX_INT_P": shift_mix["EQ_SHIFT_MIX_INT_P"],
                "EQ_SHIFT_TINY_RANGE": (0.004, 0.16),
                "EQ_SHIFT_MID_RANGE": (0.16, 0.80),
                "EQ_MAX_INT_SHIFT": 8,
                "GMF_OBJ_A": 0.0,
                "GMF_OBJ_B": 0.0,
                "GMF_OBJ_C": 0.0,
                "GMF_OBJ_D": 0.0,
                "GMF_OBJ_G": 0.0,
                "GMF_OBJ_H": 0.0,
                "GMF_OBJ_I": 0.0,
                "GMF_OBJ_J": 2.5,
                "GMF_OBJ_K": 3.0,
                "GMF_OBJ_L": 0.8,
                "GMF_OBJ_M": 0.6,
                "GMF_OBJ_N": 0.6,
                "GMF_OBJ_O": 36.0,
                "GMF_OBJ_P": 18.0 if is_round13 else 16.0,
                "GMF_OBJ_Q": 20.0 if is_round13 else 18.0,
                "GMF_OBJ_R": 5.0 if is_round13 else 4.0,
                "GMF_OBJ_S": 12.0,
                "GMF_OBJ_T": 15.0 if is_round13 else 14.0,
                "GMF_OBJ_U": 10.0,
                "GMF_OBJ_V": 10.0,
                "SEQ_ENABLE": True,
                "SEQ_INCLUDE_SUBDIRS": seq_train_dirs,
                "SEQ_EVERY_N_BATCH": 1,
                "SEQ_BATCH_SIZE": 2,
                "SEQ_MAX_PAIRS": seq_pair_budget,
                "SEQ_VAL_ENABLE": True,
                "SEQ_VAL_INCLUDE_SUBDIRS": seq_val_dirs,
                "SEQ_VAL_BATCH_SIZE": 2,
                "SEQ_VAL_MAX_PAIRS": seq_pair_budget,
                "SEQ_GEOM_ENABLE": True,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_PER_EPOCH": 48,
                "AUTO_SWEEP_EARLY_MAX_TRAIN_BATCHES_UNTIL_EPOCH": int(args.sweep_epochs),
                "AUTO_SWEEP_EARLY_FAST_VAL_UNTIL_EPOCH": int(args.sweep_epochs),
            }
        )
        candidates = [
            {
                "name": "universal_defect_anchor",
                "tag": "uda",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": static_annulus_core + seq_train_dirs,
                    "LR": 2.4e-6,
                    "W_GRADMAG": 0.88,
                    "W_EDGE_ORI_SIMPLE": 0.34,
                    "SEQ_LOSS_WEIGHT": 0.14,
                    "SEQ_GRAD_WEIGHT": 0.05,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.38,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.08,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.18,
                },
            },
            {
                "name": "universal_clean_anchor",
                "tag": "uca",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_15_annulus_sparse_clean",
                    ) + tuple(s for s in seq_train_dirs if "defect" not in s),
                    "LR": 2.2e-6,
                    "W_GRADMAG": 0.82,
                    "W_EDGE_ORI_SIMPLE": 0.30,
                    "SEQ_LOSS_WEIGHT": 0.12,
                    "SEQ_GRAD_WEIGHT": 0.04,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.34,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.06,
                    "SEQ_GEOM_THICK_WEIGHT": 0.10,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.14,
                },
            },
            {
                "name": "universal_sign_guard",
                "tag": "usg",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_14_annulus_edge_defect_focus",
                        "stage_16_annulus_sparse_defect_clean",
                    ) + tuple(s for s in seq_train_dirs if "defect" in s),
                    "LR": 2.0e-6,
                    "W_GRADMAG": 0.84,
                    "W_EDGE_ORI_SIMPLE": 0.32,
                    "SEQ_LOSS_WEIGHT": 0.10,
                    "SEQ_GRAD_WEIGHT": 0.04,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.42,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.08,
                    "SEQ_GEOM_THICK_WEIGHT": 0.14,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.22,
                },
            },
            {
                "name": "universal_balanced_bridge",
                "tag": "ubb",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_14_annulus_edge_defect_focus",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ) + seq_train_dirs,
                    "LR": 2.1e-6,
                    "W_GRADMAG": 0.84,
                    "W_EDGE_ORI_SIMPLE": 0.31,
                    "SEQ_LOSS_WEIGHT": 0.11,
                    "SEQ_GRAD_WEIGHT": 0.035,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.40,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.08,
                    "SEQ_GEOM_THICK_WEIGHT": 0.12,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.16,
                },
            },
            {
                "name": "universal_macro_lock",
                "tag": "uml",
                "overrides": {
                    "LOAD_MODEL": True,
                    "PRETRAINED_PATH": seed_ckpt,
                    "TRAIN_INCLUDE_SUBDIRS": (
                        "stage_08_annulus_focus",
                        "stage_09_annulus_non_overlap",
                        "stage_10_annulus_overlap",
                        "stage_15_annulus_sparse_clean",
                        "stage_16_annulus_sparse_defect_clean",
                    ) + seq_train_dirs,
                    "LR": 1.9e-6,
                    "W_GRADMAG": 0.80,
                    "W_EDGE_ORI_SIMPLE": 0.30,
                    "SEQ_LOSS_WEIGHT": 0.08,
                    "SEQ_GRAD_WEIGHT": 0.025,
                    "SEQ_GEOM_CENTER_WEIGHT": 0.46,
                    "SEQ_GEOM_RADIUS_WEIGHT": 0.10,
                    "SEQ_GEOM_THICK_WEIGHT": 0.16,
                    "SEQ_GEOM_DRIFT_WEIGHT": 0.24,
                },
            },
        ]
        if is_round13:
            candidates.append(
                {
                    "name": "universal_mid_guard",
                    "tag": "umg",
                    "overrides": {
                        "LOAD_MODEL": True,
                        "PRETRAINED_PATH": seed_ckpt,
                        "TRAIN_INCLUDE_SUBDIRS": (
                            "stage_08_annulus_focus",
                            "stage_09_annulus_non_overlap",
                            "stage_10_annulus_overlap",
                            "stage_15_annulus_sparse_clean",
                            "stage_16_annulus_sparse_defect_clean",
                        ) + seq_train_dirs,
                        "LR": 2.0e-6,
                        "W_GRADMAG": 0.82,
                        "W_EDGE_ORI_SIMPLE": 0.30,
                        "SEQ_LOSS_WEIGHT": 0.09,
                        "SEQ_GRAD_WEIGHT": 0.03,
                        "SEQ_GEOM_CENTER_WEIGHT": 0.44,
                        "SEQ_GEOM_RADIUS_WEIGHT": 0.07,
                        "SEQ_GEOM_THICK_WEIGHT": 0.15,
                        "SEQ_GEOM_DRIFT_WEIGHT": 0.20,
                    },
                }
            )

    candidate_filter = str(getattr(args, "candidate_filter", "") or "").strip()
    if candidate_filter:
        wanted = {s.strip() for s in candidate_filter.split(",") if s.strip()}
        candidates = [item for item in candidates if str(item.get("name")) in wanted]
        if not candidates:
            raise ValueError(f"--candidate-filter matched no candidates: {candidate_filter}")

    results = []
    print(
        f"[AUTO] sweep start | profile={args.profile} seed={args.seed} "
        f"sweep_epochs={args.sweep_epochs} final_epochs={args.final_epochs}"
    )
    effective_proxy_source = str(common_overrides.get("GMF_VALIDATE_SOURCE", args.proxy_source))
    print(
        f"[AUTO] objective: known-step GMF first (expect_dx={float(args.expect_dx):.3f}, "
        f"expect_dy={float(args.expect_dy):.3f}, source={effective_proxy_source}), "
        f"then boundary/texture realism."
    )
    for item in candidates:
        name = str(item["name"])
        tag = str(item["tag"])
        overrides = dict(item.get("overrides", {}))
        print(f"\n[AUTO][SWEEP] candidate={name} overrides={overrides}")
        try:
            res = _run_one_candidate(
                candidate_name=name,
                candidate_tag=tag,
                model_name_base=model_name_base,
                base_cfg_snapshot=base_cfg_snapshot,
                common_overrides=common_overrides,
                candidate_overrides=overrides,
                sweep_epochs=int(args.sweep_epochs),
                seed=int(args.seed),
                deterministic=bool(args.deterministic),
            )
            print(
                f"[AUTO][SWEEP][DONE] candidate={name} "
                f"score={res['score_shift_first']:.6f} "
                f"step_err={_safe_float(res['summary'].get('best_step_err', np.nan), np.nan):.6f} "
                f"pos_std={_safe_float(res['summary'].get('best_pos_std_sum', np.nan), np.nan):.6f} "
                f"pass02={_safe_float(res['summary'].get('best_pass02_estimate', np.nan), np.nan):.6f} "
                f"seq_score={_safe_float(res['summary'].get('best_seq_val_score', np.nan), np.nan):.6f} "
                f"seq_sign={_safe_float(res['summary'].get('best_seq_val_sign_acc', np.nan), np.nan):.6f} "
                f"ann_score={_safe_float(res['summary'].get('best_ann_seq_score', np.nan), np.nan):.6f} "
                f"ann_sign={_safe_float(res['summary'].get('best_ann_seq_sign_acc', np.nan), np.nan):.6f}"
            )
            results.append(res)
        except Exception as e:
            err = {
                "candidate": name,
                "overrides": overrides,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            }
            print(f"[AUTO][SWEEP][FAIL] candidate={name} err={err['error']}")
            results.append(err)

    valid = [r for r in results if "score_shift_first" in r]
    if not valid:
        report = {
            "timestamp": ts,
            "profile": str(args.profile),
            "seed": int(args.seed),
            "sweep_epochs": int(args.sweep_epochs),
            "final_epochs": int(args.final_epochs),
            "deterministic": bool(args.deterministic),
            "common_overrides": common_overrides,
            "candidates": results,
            "best_candidate": None,
            "final_run": None,
            "status": "all_candidates_failed",
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(_jsonable(report), f, indent=2)
        print(f"[AUTO] all candidates failed. report={report_path}")
        return

    valid.sort(key=lambda x: x["score_shift_first"], reverse=True)
    best = valid[0]
    best_name = str(best["candidate"])
    best_tag = ""
    best_overrides = {}
    for item in candidates:
        if str(item["name"]) == best_name:
            best_tag = str(item["tag"])
            best_overrides = dict(item.get("overrides", {}))
            break

    print(
        f"\n[AUTO] best candidate={best_name} "
        f"score={best['score_shift_first']:.6f} "
        f"progress_dir={best['progress_dir']} "
        f"best_ckpt={best.get('best_checkpoint_path', '')}"
    )

    final_run = None
    final_init_ckpt = str(best.get("best_checkpoint_path") or "")
    if not bool(args.skip_final):
        if not final_init_ckpt:
            raise FileNotFoundError(f"best checkpoint not found for candidate={best_name} progress_dir={best.get('progress_dir', '')}")
        print(f"[AUTO][FINAL] start candidate={best_name}")
        final_run = _run_final_training(
            best_candidate_name=best_name,
            best_candidate_tag=best_tag,
            model_name_base=model_name_base,
            base_cfg_snapshot=base_cfg_snapshot,
            common_overrides=common_overrides,
            best_candidate_overrides=best_overrides,
            final_epochs=int(args.final_epochs),
            seed=int(args.seed),
            deterministic=bool(args.deterministic),
            init_checkpoint_path=final_init_ckpt,
        )
        print(
            f"[AUTO][FINAL][DONE] score={final_run['score_shift_first']:.6f} "
            f"step_err={_safe_float(final_run['summary'].get('best_step_err', np.nan), np.nan):.6f} "
            f"pos_std={_safe_float(final_run['summary'].get('best_pos_std_sum', np.nan), np.nan):.6f} "
            f"pass02={_safe_float(final_run['summary'].get('best_pass02_estimate', np.nan), np.nan):.6f}"
        )
        print(
            f"[AUTO][FINAL] progress_dir={final_run['progress_dir']} "
            f"init_ckpt={final_run.get('init_checkpoint_path', '')} "
            f"best_ckpt={final_run.get('best_checkpoint_path', '')}"
        )

    recommended = _choose_recommended_candidate(
        {
            "name": best_name,
            "candidate": best_name,
            "score_shift_first": best["score_shift_first"],
            "progress_dir": best["progress_dir"],
            "best_checkpoint_path": best.get("best_checkpoint_path", ""),
        },
        final_run,
    )

    report = {
        "timestamp": ts,
        "profile": str(args.profile),
        "seed": int(args.seed),
        "sweep_epochs": int(args.sweep_epochs),
        "final_epochs": int(args.final_epochs),
        "deterministic": bool(args.deterministic),
        "common_overrides": common_overrides,
        "candidates": results,
        "best_candidate": {
            "name": best_name,
            "tag": best_tag,
            "score_shift_first": best["score_shift_first"],
            "overrides": best_overrides,
            "progress_dir": best["progress_dir"],
            "best_checkpoint_path": best.get("best_checkpoint_path", ""),
        },
        "final_run": final_run,
        "recommended_deploy": recommended,
        "status": "ok",
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(_jsonable(report), f, indent=2)
    print(f"[AUTO] report={report_path}")
    print(
        f"[AUTO] recommended_deploy kind={recommended.get('kind', '')} "
        f"score={_safe_float(recommended.get('score_shift_first'), np.nan):.6f} "
        f"ckpt={recommended.get('checkpoint_path', '')}"
    )


if __name__ == "__main__":
    main()
