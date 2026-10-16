from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.io as sio
import seaborn as sns


SCRIPT_DIR = Path(__file__).resolve().parent
PSF_ROOT = SCRIPT_DIR.parents[1]
OUTPUT_DIR = SCRIPT_DIR / "PSF_SAF_sensitivity_20260625"

ROUND1_OUTPUTS = SCRIPT_DIR / "L0_newdata_round1" / "outputs"
ROUND1_INPUTS = SCRIPT_DIR / "L0_newdata_round1" / "inputs_primary"
ROUND1_MANIFEST = ROUND1_OUTPUTS / "manifest.json"

PURE_EVAL_DIR = OUTPUT_DIR / "matlab_eval_pure_unlocked"
BEST_EVAL_DIR = OUTPUT_DIR / "matlab_eval_best_fit_locked"
REFIT_DIR = OUTPUT_DIR / "matlab_refit_fov061_formal_locked"

REL_STEP = 0.10
NOMINAL_SHAPE_COEF = 0.01
NEAR_ZERO_COEF = 1e-8
NEAR_ZERO_OUTPUT = 1e-12

COEF_LABELS = [
    "x1 -> Z2 Y-tilt",
    "x2 -> Z3 X-tilt",
    "x3 -> Z4 astig 45deg",
    "x4 -> Z5 defocus",
    "x5 -> Z6 astig 0deg",
    "x6 -> Z7 trefoil",
    "x7 -> Z8 coma Y",
    "x8 -> Z9 coma X",
    "x9 -> Z10 trefoil",
    "x10 -> Z11 quadrafoil",
    "x11 -> Z12 sec astig",
    "x12 -> Z13 spherical",
    "x13 -> Z14 sec astig",
    "x14 -> Z15 quadrafoil",
    "x15 -> AC amplitude",
]

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

COLORS = {
    "blue": "#A3BEFA",
    "blue_dark": "#2E4780",
    "orange": "#F0986E",
    "orange_dark": "#804126",
    "green": "#A3D576",
    "green_dark": "#386411",
}


@dataclass
class EvalOutput:
    table: pd.DataFrame
    psf_grid: np.ndarray


def use_chart_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "savefig.facecolor": TOKENS["surface"],
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "grid.color": TOKENS["grid"],
            "font.family": "sans-serif",
            "font.sans-serif": ["Aptos", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
            "axes.spines.top": False,
            "axes.spines.right": False,
        },
    )


def add_header(fig: plt.Figure, ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=0.82)
    left = ax.get_position().x0
    fig.text(left, 0.98, title, ha="left", va="top", fontsize=13, fontweight="semibold", color=TOKENS["ink"])
    fig.text(left, 0.93, subtitle, ha="left", va="top", fontsize=9, color=TOKENS["muted"])
    sns.despine(ax=ax)


def json_ready(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    return value


def matlab_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def run_matlab_batch(batch: str, *, timeout_s: int = 600) -> None:
    completed = subprocess.run(
        ["matlab", "-batch", batch],
        cwd=PSF_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s,
        check=False,
    )
    log_path = OUTPUT_DIR / "matlab_command_log.txt"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n===== MATLAB batch =====\n")
        handle.write(batch)
        handle.write("\n===== Output =====\n")
        handle.write(completed.stdout)
        handle.write("\n")
    if completed.returncode != 0:
        raise RuntimeError(f"MATLAB command failed. See {log_path}\n{completed.stdout}")


def run_formal_refit_smoke() -> None:
    if (REFIT_DIR / "PSF_fitted_2D_FOVstack.mat").is_file():
        return
    REFIT_DIR.mkdir(parents=True, exist_ok=True)
    batch = (
        "addpath(fullfile(pwd,'PSF_Fitting_ValidationLab','scripts')); "
        "rng(260625); "
        "HDR_fitting_2D_WholeFOV_reasonable_v1("
        "'subset_indices',61,"
        f"'input_folder','{matlab_path(ROUND1_INPUTS)}',"
        f"'gt_path','{matlab_path(ROUND1_INPUTS / 'GT' / 'GT_901_with_Block_proc.bmp')}',"
        f"'loss_mask_path','{matlab_path(ROUND1_INPUTS / 'GT' / 'circle_edge_mask.bmp')}',"
        "'grid_rows',11,'grid_cols',11,"
        "'warm_start',false,'pre_alignment',false,'lock_tilt',true,'use_gpu',false,"
        f"'output_root','{matlab_path(REFIT_DIR)}');"
    )
    run_matlab_batch(batch, timeout_s=300)


def load_best_fit_table() -> pd.DataFrame:
    manifest = json.loads(ROUND1_MANIFEST.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for trial_pos, trial_dir_str in enumerate(manifest["trial_dirs"], start=1):
        trial_dir = Path(trial_dir_str)
        if not trial_dir.is_absolute():
            trial_dir = (PSF_ROOT / trial_dir).resolve()
        batch = pd.read_csv(trial_dir / "batch_results.csv")
        mat = sio.loadmat(trial_dir / "PSF_fitted_2D_FOVstack.mat", squeeze_me=False)
        coef_grid = np.asarray(mat["coef_grid"], dtype=float)
        if coef_grid.ndim == 3:
            coef_grid = coef_grid[:, 0, :]
        for row_idx, row in batch.iterrows():
            payload = {
                "trial": trial_pos,
                "row_in_trial": row_idx,
                "fov_index": int(row["file_index"]),
                "filename": row["filename"],
                "fval": float(row["fval"]),
            }
            for coef_idx in range(15):
                payload[f"x{coef_idx + 1}"] = float(coef_grid[coef_idx, row_idx])
            rows.append(payload)
    all_fits = pd.DataFrame(rows)
    best = (
        all_fits.sort_values(["fov_index", "fval", "trial"])
        .groupby("fov_index", as_index=False)
        .first()
        .sort_values("fov_index")
        .reset_index(drop=True)
    )
    best.to_csv(OUTPUT_DIR / "best_fit_points_from_round1_repeats.csv", index=False, encoding="utf-8-sig")
    return best


def write_case_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["case_id", "file_index"] + [f"x{i}" for i in range(1, 16)]
    df[columns].to_csv(path, index=False, encoding="utf-8-sig")


def make_pure_cases() -> tuple[pd.DataFrame, pd.DataFrame]:
    case_rows: list[dict[str, Any]] = []
    meta_rows: list[dict[str, Any]] = []

    def append_case(case_id: str, coef: np.ndarray, parameter_number: int | None, case_type: str, x_value: float) -> None:
        row = {"case_id": case_id, "file_index": 61}
        row.update({f"x{i + 1}": float(coef[i]) for i in range(15)})
        case_rows.append(row)
        meta_rows.append(
            {
                "case_id": case_id,
                "analysis": "pure_parameter_unlocked",
                "parameter_number": parameter_number,
                "coef_label": "" if parameter_number is None else COEF_LABELS[parameter_number - 1],
                "case_type": case_type,
                "x0": x_value,
                "relative_step": REL_STEP,
                "lock_tilt": False,
            }
        )

    ideal = np.zeros(15, dtype=float)
    ideal[14] = 1.0
    append_case("pure_ideal", ideal.copy(), None, "ideal", 0.0)

    for param_idx in range(15):
        base = np.zeros(15, dtype=float)
        base[14] = 1.0
        nominal = 1.0 if param_idx == 14 else NOMINAL_SHAPE_COEF
        base[param_idx] = nominal
        append_case(f"pure_x{param_idx + 1:02d}_base", base.copy(), param_idx + 1, "base", nominal)
        for label, factor in [("minus", 1.0 - REL_STEP), ("plus", 1.0 + REL_STEP)]:
            coef = base.copy()
            coef[param_idx] = nominal * factor
            append_case(f"pure_x{param_idx + 1:02d}_{label}", coef, param_idx + 1, label, nominal * factor)

    cases = pd.DataFrame(case_rows)
    meta = pd.DataFrame(meta_rows)
    write_case_csv(cases, OUTPUT_DIR / "pure_parameter_cases_unlocked.csv")
    meta.to_csv(OUTPUT_DIR / "pure_parameter_case_metadata.csv", index=False, encoding="utf-8-sig")
    return cases, meta


def make_best_fit_cases(best: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    case_rows: list[dict[str, Any]] = []
    meta_rows: list[dict[str, Any]] = []
    reference_scales = np.array([NOMINAL_SHAPE_COEF] * 14 + [1.0], dtype=float)

    def append_case(case_id: str, file_index: int, coef: np.ndarray, meta: dict[str, Any]) -> None:
        row = {"case_id": case_id, "file_index": int(file_index)}
        row.update({f"x{i + 1}": float(coef[i]) for i in range(15)})
        case_rows.append(row)
        meta_rows.append({"case_id": case_id, **meta})

    for _, fit in best.iterrows():
        fov_index = int(fit["fov_index"])
        base_coef = np.array([float(fit[f"x{i}"]) for i in range(1, 16)], dtype=float)
        baseline_id = f"best_fov{fov_index:03d}_baseline"
        append_case(
            baseline_id,
            fov_index,
            base_coef.copy(),
            {
                "analysis": "best_fit_operating_locked",
                "fov_index": fov_index,
                "trial": int(fit["trial"]),
                "parameter_number": np.nan,
                "coef_label": "",
                "case_type": "baseline",
                "x0": np.nan,
                "saf_defined": False,
                "relative_step": REL_STEP,
                "absolute_probe_delta": np.nan,
                "lock_tilt": True,
            },
        )
        for param_idx in range(15):
            x0 = float(base_coef[param_idx])
            saf_defined = abs(x0) >= NEAR_ZERO_COEF
            if saf_defined:
                values = {
                    "minus": x0 * (1.0 - REL_STEP),
                    "plus": x0 * (1.0 + REL_STEP),
                }
                absolute_probe_delta = abs(x0) * REL_STEP
            else:
                absolute_probe_delta = reference_scales[param_idx] * REL_STEP
                values = {
                    "minus": x0 - absolute_probe_delta,
                    "plus": x0 + absolute_probe_delta,
                }
            for case_type, value in values.items():
                coef = base_coef.copy()
                coef[param_idx] = value
                append_case(
                    f"best_fov{fov_index:03d}_x{param_idx + 1:02d}_{case_type}",
                    fov_index,
                    coef,
                    {
                        "analysis": "best_fit_operating_locked",
                        "fov_index": fov_index,
                        "trial": int(fit["trial"]),
                        "parameter_number": param_idx + 1,
                        "coef_label": COEF_LABELS[param_idx],
                        "case_type": case_type,
                        "x0": x0,
                        "saf_defined": saf_defined,
                        "relative_step": REL_STEP,
                        "absolute_probe_delta": absolute_probe_delta,
                        "lock_tilt": True,
                    },
                )

    cases = pd.DataFrame(case_rows)
    meta = pd.DataFrame(meta_rows)
    write_case_csv(cases, OUTPUT_DIR / "best_fit_operating_cases_locked.csv")
    meta.to_csv(OUTPUT_DIR / "best_fit_operating_case_metadata.csv", index=False, encoding="utf-8-sig")
    return cases, meta


def run_coefficient_evaluation(coef_csv: Path, eval_dir: Path, *, lock_tilt: bool) -> None:
    eval_csv = eval_dir / "coefficient_evaluation.csv"
    eval_mat = eval_dir / "PSF_evaluated_coefficients.mat"
    if eval_mat.is_file() and eval_csv.is_file():
        try:
            existing_columns = pd.read_csv(eval_csv, nrows=1).columns
            if "x1" in existing_columns and "x15" in existing_columns:
                return
        except Exception:
            pass
    if eval_dir.exists():
        shutil.rmtree(eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)
    lock_value = "true" if lock_tilt else "false"
    batch = (
        "addpath(fullfile(pwd,'PSF_Fitting_ValidationLab','scripts')); "
        "HDR_fitting_2D_WholeFOV_candidate_prealign("
        "'mode','evaluate_coefficients',"
        f"'coefficient_csv_path','{matlab_path(coef_csv)}',"
        f"'input_folder','{matlab_path(ROUND1_INPUTS)}',"
        f"'gt_path','{matlab_path(ROUND1_INPUTS / 'GT' / 'GT_901_with_Block_proc.bmp')}',"
        f"'loss_mask_path','{matlab_path(ROUND1_INPUTS / 'GT' / 'circle_edge_mask.bmp')}',"
        "'grid_rows',11,'grid_cols',11,"
        "'pre_alignment',false,"
        f"'lock_tilt',{lock_value},"
        "'use_gpu',false,"
        f"'output_root','{matlab_path(eval_dir)}');"
    )
    run_matlab_batch(batch, timeout_s=900)


def load_eval_output(eval_dir: Path) -> EvalOutput:
    table = pd.read_csv(eval_dir / "coefficient_evaluation.csv")
    if "x1" not in table.columns:
        if eval_dir == PURE_EVAL_DIR:
            coef_input = pd.read_csv(OUTPUT_DIR / "pure_parameter_cases_unlocked.csv")
        elif eval_dir == BEST_EVAL_DIR:
            coef_input = pd.read_csv(OUTPUT_DIR / "best_fit_operating_cases_locked.csv")
        else:
            coef_input = pd.DataFrame()
        if not coef_input.empty:
            table = table.merge(coef_input, on=["case_id", "file_index"], how="left")
    mat = sio.loadmat(eval_dir / "PSF_evaluated_coefficients.mat", squeeze_me=False)
    psf_grid = np.asarray(mat["psf_grid"], dtype=float)
    return EvalOutput(table=table, psf_grid=psf_grid)


def normalized(psf: np.ndarray) -> np.ndarray:
    total = float(psf.sum())
    if abs(total) < NEAR_ZERO_OUTPUT:
        raise ValueError("PSF sum is zero")
    return psf / total


def moments(psf: np.ndarray) -> dict[str, float]:
    p = normalized(psf)
    h, w = p.shape
    x, y = np.meshgrid(np.arange(w, dtype=float), np.arange(h, dtype=float))
    cx = float((x * p).sum())
    cy = float((y * p).sum())
    sx = float(np.sqrt(((x - cx) ** 2 * p).sum()))
    sy = float(np.sqrt(((y - cy) ** 2 * p).sum()))
    return {
        "centroid_x": cx,
        "centroid_y": cy,
        "centroid_radius": math.hypot(cx - (w - 1) / 2.0, cy - (h - 1) / 2.0),
        "width_mean": (sx + sy) / 2.0,
        "peak_norm": float(p.max()),
        "peak_abs": float(psf.max()),
    }


def psf_at(eval_output: EvalOutput, case_id: str) -> np.ndarray:
    matches = np.flatnonzero(eval_output.table["case_id"].astype(str).to_numpy() == case_id)
    if len(matches) != 1:
        raise KeyError(f"Expected one case_id={case_id}, got {len(matches)}")
    return eval_output.psf_grid[:, :, 0, int(matches[0])]


def row_at(eval_output: EvalOutput, case_id: str) -> pd.Series:
    matches = eval_output.table[eval_output.table["case_id"].astype(str) == case_id]
    if len(matches) != 1:
        raise KeyError(f"Expected one case_id={case_id}, got {len(matches)}")
    return matches.iloc[0]


def shape_metrics_against(psf: np.ndarray, ref: np.ndarray) -> dict[str, float]:
    p = normalized(psf)
    r = normalized(ref)
    ref_peak = max(float(r.max()), NEAR_ZERO_OUTPUT)
    diff = p - r
    p_mom = moments(psf)
    r_mom = moments(ref)
    return {
        "shape_rmse_vs_ref_peak_pct": float(np.sqrt(np.mean(diff**2)) / ref_peak * 100.0),
        "shape_max_abs_vs_ref_peak_pct": float(np.max(np.abs(diff)) / ref_peak * 100.0),
        "centroid_shift_px": float(
            math.hypot(p_mom["centroid_x"] - r_mom["centroid_x"], p_mom["centroid_y"] - r_mom["centroid_y"])
        ),
        "width_abs_delta_pct": float(abs(p_mom["width_mean"] - r_mom["width_mean"]) / max(r_mom["width_mean"], NEAR_ZERO_OUTPUT) * 100.0),
        "peak_norm_abs_delta_pct": float(abs(p_mom["peak_norm"] - r_mom["peak_norm"]) / ref_peak * 100.0),
        "peak_abs": p_mom["peak_abs"],
        "peak_norm": p_mom["peak_norm"],
        "centroid_radius": p_mom["centroid_radius"],
        "width_mean": p_mom["width_mean"],
    }


def sensitivity_coefficient(y_plus: float, y_minus: float, x_plus: float, x_minus: float) -> float:
    denom = x_plus - x_minus
    if abs(denom) < NEAR_ZERO_COEF:
        return float("nan")
    return float((y_plus - y_minus) / denom)


def saf(y_plus: float, y_minus: float, y0: float, x_plus: float, x_minus: float, x0: float) -> float:
    if abs(y0) < NEAR_ZERO_OUTPUT or abs(x0) < NEAR_ZERO_COEF:
        return float("nan")
    rel_x = (x_plus - x_minus) / x0
    if abs(rel_x) < NEAR_ZERO_OUTPUT:
        return float("nan")
    return float(((y_plus - y_minus) / y0) / rel_x)


def analyze_pure(pure_eval: EvalOutput) -> pd.DataFrame:
    ideal_psf = psf_at(pure_eval, "pure_ideal")
    rows: list[dict[str, Any]] = []
    for param_idx, label in enumerate(COEF_LABELS, start=1):
        ids = {
            "base": f"pure_x{param_idx:02d}_base",
            "minus": f"pure_x{param_idx:02d}_minus",
            "plus": f"pure_x{param_idx:02d}_plus",
        }
        base_psf = psf_at(pure_eval, ids["base"])
        minus_psf = psf_at(pure_eval, ids["minus"])
        plus_psf = psf_at(pure_eval, ids["plus"])
        base_metrics = shape_metrics_against(base_psf, ideal_psf)
        minus_metrics = shape_metrics_against(minus_psf, ideal_psf)
        plus_metrics = shape_metrics_against(plus_psf, ideal_psf)
        base_row = row_at(pure_eval, ids["base"])
        minus_row = row_at(pure_eval, ids["minus"])
        plus_row = row_at(pure_eval, ids["plus"])
        x0 = float(base_row[f"x{param_idx}"])
        x_minus = float(minus_row[f"x{param_idx}"])
        x_plus = float(plus_row[f"x{param_idx}"])
        rows.append(
            {
                "parameter_number": param_idx,
                "coef_label": label,
                "x0": x0,
                "x_minus": x_minus,
                "x_plus": x_plus,
                "base_shape_impact_pct": base_metrics["shape_rmse_vs_ref_peak_pct"],
                "base_shape_max_abs_pct": base_metrics["shape_max_abs_vs_ref_peak_pct"],
                "base_centroid_shift_px": base_metrics["centroid_shift_px"],
                "base_width_abs_delta_pct": base_metrics["width_abs_delta_pct"],
                "base_peak_norm_abs_delta_pct": base_metrics["peak_norm_abs_delta_pct"],
                "base_loss": float(base_row["loss"]),
                "sensitivity_coefficient_shape": sensitivity_coefficient(
                    plus_metrics["shape_rmse_vs_ref_peak_pct"],
                    minus_metrics["shape_rmse_vs_ref_peak_pct"],
                    x_plus,
                    x_minus,
                ),
                "saf_shape": saf(
                    plus_metrics["shape_rmse_vs_ref_peak_pct"],
                    minus_metrics["shape_rmse_vs_ref_peak_pct"],
                    base_metrics["shape_rmse_vs_ref_peak_pct"],
                    x_plus,
                    x_minus,
                    x0,
                ),
                "sensitivity_coefficient_loss": sensitivity_coefficient(
                    float(plus_row["loss"]),
                    float(minus_row["loss"]),
                    x_plus,
                    x_minus,
                ),
                "saf_loss": saf(float(plus_row["loss"]), float(minus_row["loss"]), float(base_row["loss"]), x_plus, x_minus, x0),
            }
        )
    summary = pd.DataFrame(rows)
    summary["shape_impact_rank"] = summary["base_shape_impact_pct"].rank(method="first", ascending=False).astype(int)
    summary["abs_saf_shape_rank"] = summary["saf_shape"].abs().rank(method="first", ascending=False, na_option="bottom").astype(int)
    summary = summary.sort_values("shape_impact_rank").reset_index(drop=True)
    summary.to_csv(OUTPUT_DIR / "pure_parameter_saf_summary.csv", index=False, encoding="utf-8-sig")
    return summary


def analyze_best(best_eval: EvalOutput, meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows: list[dict[str, Any]] = []
    for fov_index in sorted(meta.loc[meta["case_type"] == "baseline", "fov_index"].dropna().unique()):
        fov_index = int(fov_index)
        baseline_id = f"best_fov{fov_index:03d}_baseline"
        baseline_psf = psf_at(best_eval, baseline_id)
        baseline_row = row_at(best_eval, baseline_id)
        baseline_moments = moments(baseline_psf)
        for param_idx, label in enumerate(COEF_LABELS, start=1):
            minus_id = f"best_fov{fov_index:03d}_x{param_idx:02d}_minus"
            plus_id = f"best_fov{fov_index:03d}_x{param_idx:02d}_plus"
            minus_psf = psf_at(best_eval, minus_id)
            plus_psf = psf_at(best_eval, plus_id)
            minus_row = row_at(best_eval, minus_id)
            plus_row = row_at(best_eval, plus_id)
            minus_meta = meta.loc[meta["case_id"] == minus_id].iloc[0]
            plus_meta = meta.loc[meta["case_id"] == plus_id].iloc[0]
            x0 = float(minus_meta["x0"])
            x_minus = float(minus_row[f"x{param_idx}"])
            x_plus = float(plus_row[f"x{param_idx}"])
            plus_shape = shape_metrics_against(plus_psf, baseline_psf)
            minus_shape = shape_metrics_against(minus_psf, baseline_psf)
            plus_mom = moments(plus_psf)
            minus_mom = moments(minus_psf)
            saf_defined = bool(minus_meta["saf_defined"])
            detail_rows.append(
                {
                    "fov_index": fov_index,
                    "parameter_number": param_idx,
                    "coef_label": label,
                    "x0": x0,
                    "x_minus": x_minus,
                    "x_plus": x_plus,
                    "saf_defined": saf_defined,
                    "baseline_loss": float(baseline_row["loss"]),
                    "loss_minus": float(minus_row["loss"]),
                    "loss_plus": float(plus_row["loss"]),
                    "sensitivity_coefficient_loss": sensitivity_coefficient(
                        float(plus_row["loss"]),
                        float(minus_row["loss"]),
                        x_plus,
                        x_minus,
                    ),
                    "saf_loss": saf(float(plus_row["loss"]), float(minus_row["loss"]), float(baseline_row["loss"]), x_plus, x_minus, x0)
                    if saf_defined
                    else float("nan"),
                    "sensitivity_coefficient_peak_norm": sensitivity_coefficient(
                        plus_mom["peak_norm"],
                        minus_mom["peak_norm"],
                        x_plus,
                        x_minus,
                    ),
                    "saf_peak_norm": saf(
                        plus_mom["peak_norm"],
                        minus_mom["peak_norm"],
                        baseline_moments["peak_norm"],
                        x_plus,
                        x_minus,
                        x0,
                    )
                    if saf_defined
                    else float("nan"),
                    "sensitivity_coefficient_width": sensitivity_coefficient(
                        plus_mom["width_mean"],
                        minus_mom["width_mean"],
                        x_plus,
                        x_minus,
                    ),
                    "saf_width": saf(
                        plus_mom["width_mean"],
                        minus_mom["width_mean"],
                        baseline_moments["width_mean"],
                        x_plus,
                        x_minus,
                        x0,
                    )
                    if saf_defined
                    else float("nan"),
                    "shape_response_plus_pct": plus_shape["shape_rmse_vs_ref_peak_pct"],
                    "shape_response_minus_pct": minus_shape["shape_rmse_vs_ref_peak_pct"],
                    "shape_response_mean_pct": float(
                        (plus_shape["shape_rmse_vs_ref_peak_pct"] + minus_shape["shape_rmse_vs_ref_peak_pct"]) / 2.0
                    ),
                }
            )
    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby(["parameter_number", "coef_label"], as_index=False)
        .agg(
            median_abs_saf_loss=("saf_loss", lambda s: float(np.nanmedian(np.abs(s)))),
            median_abs_saf_peak_norm=("saf_peak_norm", lambda s: float(np.nanmedian(np.abs(s)))),
            median_abs_saf_width=("saf_width", lambda s: float(np.nanmedian(np.abs(s)))),
            median_shape_response_pct=("shape_response_mean_pct", "median"),
            saf_defined_count=("saf_defined", "sum"),
            fov_count=("fov_index", "count"),
        )
        .reset_index(drop=True)
    )
    summary["loss_saf_rank"] = summary["median_abs_saf_loss"].rank(method="first", ascending=False, na_option="bottom").astype(int)
    summary["shape_response_rank"] = summary["median_shape_response_pct"].rank(method="first", ascending=False).astype(int)
    summary = summary.sort_values("loss_saf_rank").reset_index(drop=True)
    detail.to_csv(OUTPUT_DIR / "best_fit_operating_saf_detail.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / "best_fit_operating_saf_summary.csv", index=False, encoding="utf-8-sig")
    return detail, summary


def write_charts(pure_summary: pd.DataFrame, best_summary: pd.DataFrame, pure_eval: EvalOutput) -> dict[str, str]:
    use_chart_theme()
    chart_paths: dict[str, str] = {}

    def bar_chart(df: pd.DataFrame, value_col: str, label_col: str, title: str, subtitle: str, out_name: str, color: str, edge: str, xlabel: str) -> None:
        plot_df = df.sort_values(value_col, ascending=True).copy()
        fig, ax = plt.subplots(figsize=(10.8, 7.2))
        sns.barplot(data=plot_df, x=value_col, y=label_col, color=color, edgecolor=edge, linewidth=1.0, ax=ax)
        max_value = float(np.nanmax(plot_df[value_col].to_numpy(dtype=float))) if len(plot_df) else 0.0
        for patch, value in zip(ax.patches, plot_df[value_col]):
            text = "NA" if pd.isna(value) else f"{float(value):.3g}"
            ax.text(
                patch.get_width() + max(max_value * 0.012, 0.001),
                patch.get_y() + patch.get_height() / 2,
                text,
                va="center",
                fontsize=8,
                color=TOKENS["ink"],
            )
        ax.set_xlabel(xlabel)
        ax.set_ylabel("")
        ax.set_xlim(0, max_value * 1.20 + 0.001)
        add_header(fig, ax, title, subtitle)
        out = OUTPUT_DIR / out_name
        fig.savefig(out, dpi=220, bbox_inches="tight")
        fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
        plt.close(fig)
        chart_paths[out_name] = str(out)

    bar_chart(
        pure_summary.sort_values("shape_impact_rank"),
        "base_shape_impact_pct",
        "coef_label",
        "Pure PSF shape impact at equal nonzero coefficient",
        "All Zernike terms use x0=0.01 with tilt unlocked; this ranks physical PSF shape impact, not current search bounds.",
        "pure_nominal_shape_impact_rank.png",
        COLORS["blue"],
        COLORS["blue_dark"],
        "PSF shape difference from ideal (% of ideal peak)",
    )

    saf_plot = pure_summary.assign(abs_saf_shape=pure_summary["saf_shape"].abs())
    bar_chart(
        saf_plot,
        "abs_saf_shape",
        "coef_label",
        "SAF for pure PSF shape response",
        "SAF is relative output change divided by relative input change; NA means the baseline output is effectively zero.",
        "pure_shape_saf_rank.png",
        COLORS["green"],
        COLORS["green_dark"],
        "|SAF| for PSF shape response",
    )

    best_loss_plot = best_summary.assign(abs_loss_saf=best_summary["median_abs_saf_loss"])
    bar_chart(
        best_loss_plot,
        "abs_loss_saf",
        "coef_label",
        "Real fitted-point SAF for the formal loss",
        "Round1 best-of-15 BADS fit per FOV; locked-tilt formal pipeline; rows with zero fitted input have NA SAF.",
        "best_fit_loss_saf_rank.png",
        COLORS["orange"],
        COLORS["orange_dark"],
        "Median |SAF| for formal fitting loss",
    )

    bar_chart(
        best_summary.sort_values("shape_response_rank"),
        "median_shape_response_pct",
        "coef_label",
        "Local PSF shape response around best fitted points",
        "This is not SAF because baseline shape difference is zero; it shows image-level response to the local probe.",
        "best_fit_shape_response_rank.png",
        COLORS["blue"],
        COLORS["blue_dark"],
        "Median local PSF shape response (% of fitted peak)",
    )

    ideal = psf_at(pure_eval, "pure_ideal")
    ideal_norm = normalized(ideal)
    top_params = pure_summary.sort_values("shape_impact_rank").head(5)
    fig = plt.figure(figsize=(12.4, 7.4))
    grid = fig.add_gridspec(
        2,
        4,
        width_ratios=[1, 1, 1, 0.05],
        left=0.055,
        right=0.90,
        top=0.86,
        bottom=0.08,
        wspace=0.22,
        hspace=0.36,
    )
    axes = [fig.add_subplot(grid[row, col]) for row in range(2) for col in range(3)]
    cax = fig.add_subplot(grid[:, 3])
    axes[0].imshow(ideal_norm, cmap="magma")
    axes[0].set_title("Ideal PSF", fontsize=10)
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    maps: list[tuple[str, np.ndarray]] = []
    vmax = 0.0
    for _, row in top_params.iterrows():
        param_number = int(row["parameter_number"])
        psf = psf_at(pure_eval, f"pure_x{param_number:02d}_base")
        diff_pct = (normalized(psf) - ideal_norm) / max(float(ideal_norm.max()), NEAR_ZERO_OUTPUT) * 100.0
        vmax = max(vmax, float(np.max(np.abs(diff_pct))))
        maps.append((str(row["coef_label"]), diff_pct))
    vmax = max(vmax, 1e-6)
    im = None
    for ax, (label, diff_pct) in zip(axes[1:], maps):
        im = ax.imshow(diff_pct, cmap="coolwarm", vmin=-vmax, vmax=vmax)
        ax.set_title(label.replace(" -> ", "\n"), fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
    for ax in axes[1 + len(maps) :]:
        ax.axis("off")
    if im is not None:
        fig.colorbar(im, cax=cax, label="% of ideal peak")
    fig.suptitle("Pure parameter PSF difference maps", x=0.06, y=0.99, ha="left", fontsize=13, fontweight="semibold", color=TOKENS["ink"])
    fig.text(0.06, 0.945, "Each map turns on one parameter at x0=0.01; tilt is unlocked for this pure optical comparison.", ha="left", fontsize=9, color=TOKENS["muted"])
    out = OUTPUT_DIR / "pure_top_parameter_diff_maps.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    chart_paths["pure_top_parameter_diff_maps.png"] = str(out)

    return chart_paths


def write_reports(pure_summary: pd.DataFrame, best_summary: pd.DataFrame, chart_paths: dict[str, str]) -> None:
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "method": {
            "sensitivity_coefficient": "SC = (Y_plus - Y_minus) / (X_plus - X_minus)",
            "saf": "SAF = ((Y_plus - Y_minus) / Y0) / ((X_plus - X_minus) / X0)",
            "relative_step": REL_STEP,
            "zero_rule": "SAF is undefined when X0 or Y0 is effectively zero; SC and local absolute response are still reported.",
        },
        "inputs": {
            "round1_outputs": str(ROUND1_OUTPUTS),
            "round1_inputs": str(ROUND1_INPUTS),
            "baseline_for_operating_analysis": "best fval per FOV selected from the 15 existing real BADS Round1 repeats",
            "pure_parameter_reference": f"x1-x14 nominal {NOMINAL_SHAPE_COEF}; x15 nominal 1.0",
            "formal_refit_smoke": str(REFIT_DIR),
        },
        "outputs": {
            "pure_summary": str(OUTPUT_DIR / "pure_parameter_saf_summary.csv"),
            "best_fit_summary": str(OUTPUT_DIR / "best_fit_operating_saf_summary.csv"),
            "best_fit_detail": str(OUTPUT_DIR / "best_fit_operating_saf_detail.csv"),
            "charts": chart_paths,
        },
    }
    (OUTPUT_DIR / "analysis_metadata.json").write_text(json.dumps(json_ready(metadata), indent=2), encoding="utf-8")

    top_pure = pure_summary.sort_values("shape_impact_rank").head(8)
    top_best = best_summary.sort_values("loss_saf_rank").head(8)
    lines = [
        "# PSF SAF Sensitivity Analysis",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        "- Real MATLAB fitting code was used for coefficient evaluation through `HDR_fitting_2D_WholeFOV_candidate_prealign`.",
        "- A focused FOV61 formal refit is also run through `HDR_fitting_2D_WholeFOV_reasonable_v1` as a real-BADS execution check.",
        "- Sensitivity coefficient: `SC = (Y_plus - Y_minus) / (X_plus - X_minus)`.",
        "- SAF: `((Y_plus - Y_minus) / Y0) / ((X_plus - X_minus) / X0)`.",
        "- SAF is intentionally left as NA when the input or output baseline is effectively zero.",
        "",
        "## Pure Parameter Result",
        "",
        "| Rank | Parameter | Shape impact (% ideal peak) | SAF shape | SC shape |",
        "|---:|---|---:|---:|---:|",
    ]
    for _, row in top_pure.iterrows():
        lines.append(
            f"| {int(row['shape_impact_rank'])} | {row['coef_label']} | {row['base_shape_impact_pct']:.4f} | "
            f"{row['saf_shape']:.3g} | {row['sensitivity_coefficient_shape']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Best-Fit Operating Result",
            "",
            "| Rank | Parameter | Median abs SAF loss | Median local shape response (% fitted peak) | SAF-defined FOV count |",
            "|---:|---|---:|---:|---:|",
        ]
    )
    for _, row in top_best.iterrows():
        saf_text = "NA" if pd.isna(row["median_abs_saf_loss"]) else f"{row['median_abs_saf_loss']:.3g}"
        lines.append(
            f"| {int(row['loss_saf_rank'])} | {row['coef_label']} | {saf_text} | "
            f"{row['median_shape_response_pct']:.4f} | {int(row['saf_defined_count'])}/{int(row['fov_count'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The pure-parameter view ranks physical PSF impact without using the current search bounds.",
            "- The operating-point view tells which fitted coefficients the real loss is locally sensitive to near the best real BADS outputs.",
            "- Parameters with zero or near-zero fitted values cannot have a standard SAF at the operating point; their local absolute response is still reported.",
            "- AC amplitude should be interpreted as intensity scaling, not PSF shape.",
        ]
    )
    (OUTPUT_DIR / "PSF_SAF_sensitivity_report.md").write_text("\n".join(lines), encoding="utf-8")

    zh_lines = [
        "# PSF SAF敏感度分析：簡報用重點",
        "",
        "## 這次和上一版最大的差別",
        "",
        "這次沒有用目前上下界的10%去比較。新版分成兩個問題：",
        "",
        "1. 每個參數本身如果用同樣大小打開，PSF會變多少。",
        "2. 在真實BADS擬合出的最佳點附近，參數變動會讓真實loss和PSF指標變多少。",
        "",
        "## 使用的公式",
        "",
        "Sensitivity Coefficient 是輸出變化量除以輸入變化量。",
        "",
        "`SC = (Y_plus - Y_minus) / (X_plus - X_minus)`",
        "",
        "SAF 是標準化後的敏感度，也就是輸出變化百分比除以輸入變化百分比。",
        "",
        "`SAF = ((Y_plus - Y_minus) / Y0) / ((X_plus - X_minus) / X0)`",
        "",
        "如果某個參數本來就是0，標準SAF不能硬算，因為分母會變成0。這種情況我保留SC和局部PSF反應，但把SAF標成NA。",
        "",
        "## 簡報上可以怎麼說",
        "",
        "「我們先不用人為上下界來決定誰重要，而是用同一個非零尺度把每個參數單獨打開，先看它對PSF本身造成什麼形狀改變。接著再回到真實BADS最佳擬合點附近，用標準SAF公式看實際loss對各參數的敏感度。這樣可以把『參數的物理影響力』和『目前資料中是否真的穩定可估』分開。」",
        "",
        "## 主要提醒",
        "",
        "- 純參數影響排序比較適合說明每個參數對PSF形狀的物理作用。",
        "- 真實最佳擬合點附近的SAF比較適合說明目前這批資料和loss最在意哪些參數。",
        "- 若參數在最佳點附近是0，標準SAF不能硬算；這不是偷懶，而是公式本身不允許。",
        "- AC振幅主要是亮度尺度，不要和PSF形狀參數混在同一句結論裡。",
    ]
    (OUTPUT_DIR / "PSF_SAF_sensitivity_takeaways_zh.md").write_text("\n".join(zh_lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if (OUTPUT_DIR / "matlab_command_log.txt").exists():
        (OUTPUT_DIR / "matlab_command_log.txt").unlink()

    run_formal_refit_smoke()
    best = load_best_fit_table()
    pure_cases, _ = make_pure_cases()
    _, best_meta = make_best_fit_cases(best)

    run_coefficient_evaluation(OUTPUT_DIR / "pure_parameter_cases_unlocked.csv", PURE_EVAL_DIR, lock_tilt=False)
    run_coefficient_evaluation(OUTPUT_DIR / "best_fit_operating_cases_locked.csv", BEST_EVAL_DIR, lock_tilt=True)

    pure_eval = load_eval_output(PURE_EVAL_DIR)
    best_eval = load_eval_output(BEST_EVAL_DIR)
    pure_summary = analyze_pure(pure_eval)
    _, best_summary = analyze_best(best_eval, best_meta)
    chart_paths = write_charts(pure_summary, best_summary, pure_eval)
    write_reports(pure_summary, best_summary, chart_paths)

    print(f"Wrote SAF sensitivity analysis to: {OUTPUT_DIR}")
    print("Top pure PSF shape impacts:")
    for _, row in pure_summary.sort_values("shape_impact_rank").head(6).iterrows():
        print(f"  #{int(row['shape_impact_rank'])}: {row['coef_label']} {row['base_shape_impact_pct']:.4f}%")
    print("Top real fitted-point loss SAF:")
    for _, row in best_summary.sort_values("loss_saf_rank").head(6).iterrows():
        value = "NA" if pd.isna(row["median_abs_saf_loss"]) else f"{row['median_abs_saf_loss']:.3g}"
        print(f"  #{int(row['loss_saf_rank'])}: {row['coef_label']} {value}")


if __name__ == "__main__":
    main()
