from __future__ import annotations

import json
import math
import textwrap
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
PSF_FITTING_ROOT = SCRIPT_DIR.parents[1]
OUTPUT_DIR = SCRIPT_DIR / "PSF_parameter_sensitivity_20260625"

ROUND1_OUTPUTS = SCRIPT_DIR / "L0_newdata_round1" / "outputs"
ROUND1_MANIFEST = ROUND1_OUTPUTS / "manifest.json"
ROUND1_NOISE_FLOOR = ROUND1_OUTPUTS / "L0_newdata_noise_floor.json"
REFERENCE_STACK = ROUND1_OUTPUTS / "trial_01" / "PSF_fitted_2D_FOVstack.mat"
BASE_PSF_PATH = PSF_FITTING_ROOT / "SimulatePSF" / "psf_multi.mat"

LB = np.array(
    [-0.3, -0.3, -0.1, 0.0, -0.1, -0.05, -0.05, -0.05, -0.05, -0.01, -0.01, 0.0, -0.01, -0.01, 0.8],
    dtype=float,
)
UB = np.array(
    [0.3, 0.3, 0.1, 1.0, 0.1, 0.05, 0.05, 0.05, 0.05, 0.01, 0.01, 0.3, 0.01, 0.01, 1.25],
    dtype=float,
)

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

LEGACY_PAGE9_TRUSTED = {2, 3, 6, 7, 9, 10, 11}

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

COLOR_FAMILIES = {
    "blue": {"xlight": "#EAF1FE", "light": "#CEDFFE", "base": "#A3BEFA", "mid": "#5477C4", "dark": "#2E4780"},
    "gold": {"xlight": "#FFF4C2", "light": "#FFEA8F", "base": "#FFE15B", "mid": "#B8A037", "dark": "#736422"},
    "orange": {"xlight": "#FFEDDE", "light": "#FFBDA1", "base": "#F0986E", "mid": "#CC6F47", "dark": "#804126"},
    "olive": {"xlight": "#D8ECBD", "light": "#BEEB96", "base": "#A3D576", "mid": "#71B436", "dark": "#386411"},
}


@dataclass
class PsfModel:
    psf_f: np.ndarray
    rho: np.ndarray
    phi: np.ndarray


def use_chart_theme() -> None:
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": TOKENS["surface"],
            "figure.edgecolor": "none",
            "savefig.facecolor": TOKENS["surface"],
            "savefig.edgecolor": "none",
            "axes.facecolor": TOKENS["panel"],
            "axes.edgecolor": TOKENS["axis"],
            "axes.labelcolor": TOKENS["ink"],
            "axes.grid": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": TOKENS["grid"],
            "grid.linewidth": 0.8,
            "font.family": "sans-serif",
            "font.sans-serif": ["Aptos", "Segoe UI", "DejaVu Sans", "Arial", "sans-serif"],
            "font.monospace": ["Consolas", "DejaVu Sans Mono", "monospace"],
            "patch.linewidth": 1.0,
        },
    )


def add_chart_header(fig: plt.Figure, ax: plt.Axes, title: str, subtitle: str) -> None:
    ax.set_title("")
    fig.subplots_adjust(top=0.82)
    left = ax.get_position().x0
    fig.text(left, 0.98, title, ha="left", va="top", fontsize=13, fontweight="semibold", color=TOKENS["ink"])
    fig.text(left, 0.93, subtitle, ha="left", va="top", fontsize=9, color=TOKENS["muted"])
    sns.despine(ax=ax)


def format_pct_label(value: float) -> str:
    if abs(value) < 1e-12:
        return "0%"
    if abs(value) < 0.001:
        return "<0.001%"
    if abs(value) < 0.01:
        return f"{value:.3f}%"
    return f"{value:.2f}%"


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


def load_psf_model() -> PsfModel:
    psf_slice = np.asarray(sio.loadmat(BASE_PSF_PATH)["psf_multi"], dtype=float)
    h, w = psf_slice.shape
    pupil_res = int(math.floor((min(h, w) - 1) / 2))
    coords = np.arange(-pupil_res, pupil_res + 1)
    x_grid, y_grid = np.meshgrid(coords, coords)
    rho = np.hypot(x_grid, y_grid) / pupil_res / 2
    phi = np.arctan2(y_grid, x_grid)
    psf_f = np.fft.fftshift(np.fft.fft2(psf_slice))
    return PsfModel(psf_f=psf_f, rho=rho, phi=phi)


def build_fitted_psf(coef: np.ndarray, model: PsfModel, *, lock_tilt: bool = True) -> np.ndarray:
    coef = np.asarray(coef, dtype=float).ravel()
    z = np.zeros(15, dtype=float)
    z[1:15] = coef[:14]
    if lock_tilt:
        z[1] = 0.0
        z[2] = 0.0
    ac = coef[14]

    rho = model.rho
    phi = model.phi
    wave_phase = (
        z[0] * 1
        + z[1] * 2 * rho * np.sin(phi)
        + z[2] * 2 * rho * np.cos(phi)
        + z[3] * np.sqrt(6) * rho**2 * np.sin(2 * phi)
        + z[4] * np.sqrt(3) * (2 * rho**2 - 1)
        + z[5] * np.sqrt(6) * rho**2 * np.cos(2 * phi)
        + z[6] * np.sqrt(8) * rho**3 * np.sin(3 * phi)
        + z[7] * np.sqrt(8) * (3 * rho**2 - 2 * rho) * np.sin(phi)
        + z[8] * np.sqrt(8) * (3 * rho**2 - 2 * rho) * np.cos(phi)
        + z[9] * np.sqrt(8) * rho**3 * np.cos(3 * phi)
        + z[10] * np.sqrt(10) * rho**4 * np.sin(4 * phi)
        + z[11] * np.sqrt(10) * (4 * rho**4 - 3 * rho**2) * np.sin(2 * phi)
        + z[12] * np.sqrt(5) * (6 * rho**4 - 6 * rho**2 + 1)
        + z[13] * np.sqrt(10) * (4 * rho**4 - 3 * rho**2) * np.cos(2 * phi)
        + z[14] * np.sqrt(10) * rho**4 * np.cos(4 * phi)
    )
    fitted = np.abs(np.fft.ifft2(model.psf_f * np.exp(1j * 2 * np.pi * wave_phase) ** 2))
    fitted = fitted / fitted.sum()
    return ac * fitted


def normalized(psf: np.ndarray) -> np.ndarray:
    total = float(psf.sum())
    if total == 0:
        raise ValueError("PSF sum is zero")
    return psf / total


def psf_moments(psf: np.ndarray) -> dict[str, float]:
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
        "sigma_x": sx,
        "sigma_y": sy,
        "width_mean": (sx + sy) / 2.0,
        "peak": float(p.max()),
    }


def load_trial_tensors(manifest: dict[str, Any]) -> np.ndarray:
    tensors: list[np.ndarray] = []
    for trial_dir in manifest["trial_dirs"]:
        path = Path(trial_dir)
        if not path.is_absolute():
            path = (PSF_FITTING_ROOT / path).resolve()
        data = sio.loadmat(path / "PSF_fitted_2D_FOVstack.mat", squeeze_me=False)
        coef_grid = np.asarray(data["coef_grid"], dtype=float)
        if coef_grid.ndim == 3:
            coef_grid = coef_grid[:, 0, :]
        tensors.append(coef_grid)
    return np.stack(tensors, axis=0)


def verify_python_psf_builder(model: PsfModel) -> dict[str, float]:
    data = sio.loadmat(REFERENCE_STACK, squeeze_me=False)
    coef = np.asarray(data["coef_grid"][:, 0, 0], dtype=float)
    expected = np.asarray(data["psf_grid"][:, :, 0, 0], dtype=float)
    actual = build_fitted_psf(coef, model, lock_tilt=True)
    diff = actual - expected
    return {
        "rmse": float(np.sqrt(np.mean(diff**2))),
        "max_abs": float(np.max(np.abs(diff))),
        "relative_rmse_to_peak": float(np.sqrt(np.mean(diff**2)) / max(float(expected.max()), 1e-12)),
        "expected_sum": float(expected.sum()),
        "actual_sum": float(actual.sum()),
    }


def compute_sensitivity(
    baselines: np.ndarray,
    model: PsfModel,
    fov_indices: list[int],
    classifications: list[dict[str, Any]],
    *,
    step_fraction: float = 0.10,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fov_pos, fov_index in enumerate(fov_indices):
        base_coef = baselines[:, fov_pos]
        base_psf = build_fitted_psf(base_coef, model, lock_tilt=True)
        base_norm = normalized(base_psf)
        base_moments = psf_moments(base_psf)
        base_peak_norm = max(base_moments["peak"], 1e-12)
        base_peak_abs = max(float(base_psf.max()), 1e-12)
        for coef_idx, label in enumerate(COEF_LABELS):
            span = float(UB[coef_idx] - LB[coef_idx])
            desired_step = step_fraction * span
            for direction in (-1, 1):
                candidate_coef = base_coef.copy()
                desired_value = base_coef[coef_idx] + direction * desired_step
                candidate_coef[coef_idx] = float(np.clip(desired_value, LB[coef_idx], UB[coef_idx]))
                actual_delta = float(candidate_coef[coef_idx] - base_coef[coef_idx])
                if abs(actual_delta) < 1e-12:
                    continue
                candidate_psf = build_fitted_psf(candidate_coef, model, lock_tilt=True)
                candidate_norm = normalized(candidate_psf)
                candidate_moments = psf_moments(candidate_psf)
                norm_diff = candidate_norm - base_norm
                abs_diff = candidate_psf - base_psf
                centroid_shift = math.hypot(
                    candidate_moments["centroid_x"] - base_moments["centroid_x"],
                    candidate_moments["centroid_y"] - base_moments["centroid_y"],
                )
                rows.append(
                    {
                        "fov_index": fov_index,
                        "fov_position": fov_pos + 1,
                        "coef_index": coef_idx,
                        "coef_number": coef_idx + 1,
                        "coef_label": label,
                        "status_round1": classifications[coef_idx]["status"],
                        "used_in_legacy_page9_7": coef_idx in LEGACY_PAGE9_TRUSTED,
                        "base_value": float(base_coef[coef_idx]),
                        "lb": float(LB[coef_idx]),
                        "ub": float(UB[coef_idx]),
                        "direction": "+" if direction > 0 else "-",
                        "actual_delta": actual_delta,
                        "actual_step_fraction_of_range": abs(actual_delta) / max(span, 1e-12),
                        "shape_rmse_vs_peak_pct": float(np.sqrt(np.mean(norm_diff**2)) / base_peak_norm * 100.0),
                        "shape_max_abs_vs_peak_pct": float(np.max(np.abs(norm_diff)) / base_peak_norm * 100.0),
                        "absolute_rmse_vs_peak_pct": float(np.sqrt(np.mean(abs_diff**2)) / base_peak_abs * 100.0),
                        "absolute_max_abs_vs_peak_pct": float(np.max(np.abs(abs_diff)) / base_peak_abs * 100.0),
                        "centroid_shift_px": float(centroid_shift),
                        "width_mean_abs_delta_pct": float(
                            abs(candidate_moments["width_mean"] - base_moments["width_mean"])
                            / max(base_moments["width_mean"], 1e-12)
                            * 100.0
                        ),
                        "peak_abs_delta_pct": float(
                            abs(candidate_moments["peak"] - base_moments["peak"]) / base_peak_norm * 100.0
                        ),
                    }
                )
    return pd.DataFrame(rows)


def summarize(detail_df: pd.DataFrame) -> pd.DataFrame:
    grouped = detail_df.groupby(["coef_index", "coef_number", "coef_label", "status_round1"], as_index=False)
    summary = grouped.agg(
        median_shape_rmse_vs_peak_pct=("shape_rmse_vs_peak_pct", "median"),
        p95_shape_rmse_vs_peak_pct=("shape_rmse_vs_peak_pct", lambda s: float(np.percentile(s, 95))),
        median_shape_max_abs_vs_peak_pct=("shape_max_abs_vs_peak_pct", "median"),
        median_absolute_rmse_vs_peak_pct=("absolute_rmse_vs_peak_pct", "median"),
        median_absolute_max_abs_vs_peak_pct=("absolute_max_abs_vs_peak_pct", "median"),
        median_centroid_shift_px=("centroid_shift_px", "median"),
        median_width_mean_abs_delta_pct=("width_mean_abs_delta_pct", "median"),
        median_peak_abs_delta_pct=("peak_abs_delta_pct", "median"),
        median_step_fraction_of_range=("actual_step_fraction_of_range", "median"),
    )
    summary["used_in_legacy_page9_7"] = summary["coef_index"].map(lambda idx: int(idx) in LEGACY_PAGE9_TRUSTED)
    summary["shape_rank"] = summary["median_shape_rmse_vs_peak_pct"].rank(method="first", ascending=False).astype(int)
    summary["absolute_rank"] = summary["median_absolute_rmse_vs_peak_pct"].rank(method="first", ascending=False).astype(int)
    return summary.sort_values("shape_rank").reset_index(drop=True)


def write_charts(detail_df: pd.DataFrame, summary_df: pd.DataFrame, model: PsfModel, baselines: np.ndarray) -> dict[str, str]:
    use_chart_theme()
    chart_paths: dict[str, str] = {}

    rank_df = summary_df.sort_values("median_shape_rmse_vs_peak_pct", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    blue = COLOR_FAMILIES["blue"]
    sns.barplot(
        data=rank_df,
        x="median_shape_rmse_vs_peak_pct",
        y="coef_label",
        color=blue["base"],
        edgecolor=blue["dark"],
        linewidth=1.0,
        ax=ax,
    )
    ax.set_xlabel("Median PSF shape change (% of baseline peak)")
    ax.set_ylabel("")
    for patch, value, status in zip(ax.patches, rank_df["median_shape_rmse_vs_peak_pct"], rank_df["status_round1"]):
        ax.text(
            patch.get_width() + max(rank_df["median_shape_rmse_vs_peak_pct"].max() * 0.01, 0.02),
            patch.get_y() + patch.get_height() / 2,
            f"{format_pct_label(float(value))} | {status}",
            va="center",
            fontsize=8,
            color=TOKENS["ink"],
        )
    ax.set_xlim(0, rank_df["median_shape_rmse_vs_peak_pct"].max() * 1.22 + 0.01)
    add_chart_header(
        fig,
        ax,
        "PSF shape sensitivity by fitted parameter",
        "Round1 formal L0: median across 9 FOV baselines; each parameter perturbed by up to 10% of its allowed range.",
    )
    out = OUTPUT_DIR / "parameter_shape_sensitivity_rank.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    chart_paths["shape_rank_png"] = str(out)

    abs_df = summary_df.sort_values("median_absolute_rmse_vs_peak_pct", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    orange = COLOR_FAMILIES["orange"]
    sns.barplot(
        data=abs_df,
        x="median_absolute_rmse_vs_peak_pct",
        y="coef_label",
        color=orange["base"],
        edgecolor=orange["dark"],
        linewidth=1.0,
        ax=ax,
    )
    ax.set_xlabel("Median absolute PSF image change (% of baseline peak)")
    ax.set_ylabel("")
    for patch, value in zip(ax.patches, abs_df["median_absolute_rmse_vs_peak_pct"]):
        ax.text(
            patch.get_width() + max(abs_df["median_absolute_rmse_vs_peak_pct"].max() * 0.01, 0.02),
            patch.get_y() + patch.get_height() / 2,
            format_pct_label(float(value)),
            va="center",
            fontsize=8,
            color=TOKENS["ink"],
        )
    ax.set_xlim(0, abs_df["median_absolute_rmse_vs_peak_pct"].max() * 1.18 + 0.01)
    add_chart_header(
        fig,
        ax,
        "Absolute fitted-PSF sensitivity including amplitude",
        "Same perturbation design; this view includes AC amplitude scaling, so x15 appears as a scale-only driver.",
    )
    out = OUTPUT_DIR / "parameter_absolute_sensitivity_rank.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    chart_paths["absolute_rank_png"] = str(out)

    heat_df = (
        detail_df.groupby(["coef_label", "fov_index"], as_index=False)["shape_rmse_vs_peak_pct"]
        .median()
        .merge(summary_df[["coef_label", "shape_rank"]], on="coef_label", how="left")
        .sort_values(["shape_rank", "fov_index"])
    )
    matrix = heat_df.pivot(index="coef_label", columns="fov_index", values="shape_rmse_vs_peak_pct")
    matrix = matrix.loc[summary_df.sort_values("shape_rank")["coef_label"]]
    fig, ax = plt.subplots(figsize=(10.8, 6.8))
    cmap = sns.blend_palette([TOKENS["panel"], blue["xlight"], blue["light"], blue["base"], blue["mid"]], as_cmap=True)
    sns.heatmap(matrix, ax=ax, cmap=cmap, linewidths=0.8, linecolor=TOKENS["panel"], cbar_kws={"label": "% of baseline peak"})
    ax.set_xlabel("FOV index")
    ax.set_ylabel("")
    add_chart_header(
        fig,
        ax,
        "Shape sensitivity is stable across the 9 L0 positions",
        "Cells show median PSF shape change after one-parameter perturbation; rows ordered by overall shape rank.",
    )
    out = OUTPUT_DIR / "parameter_shape_sensitivity_heatmap.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    chart_paths["shape_heatmap_png"] = str(out)

    center_fov_pos = 4  # fov index 61 in the current 9-point pattern.
    base_coef = baselines[:, center_fov_pos]
    base_psf = build_fitted_psf(base_coef, model, lock_tilt=True)
    base_norm = normalized(base_psf)
    top_params = summary_df.loc[summary_df["median_shape_rmse_vs_peak_pct"] > 1e-9].head(5)
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
        hspace=0.32,
    )
    axes = [fig.add_subplot(grid[row, col]) for row in range(2) for col in range(3)]
    cax = fig.add_subplot(grid[:, 3])
    im0 = axes[0].imshow(base_norm, cmap="magma")
    axes[0].set_title("Baseline FOV 61", fontsize=10)
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    im = None
    vmax = 0.0
    maps: list[tuple[int, str, np.ndarray, float]] = []
    for _, row in top_params.iterrows():
        coef_idx = int(row["coef_index"])
        span = float(UB[coef_idx] - LB[coef_idx])
        desired_step = 0.10 * span
        candidates: list[tuple[np.ndarray, float]] = []
        for direction in (-1, 1):
            coef2 = base_coef.copy()
            coef2[coef_idx] = float(np.clip(coef2[coef_idx] + direction * desired_step, LB[coef_idx], UB[coef_idx]))
            actual_delta = float(coef2[coef_idx] - base_coef[coef_idx])
            if abs(actual_delta) < 1e-12:
                continue
            diff = normalized(build_fitted_psf(coef2, model, lock_tilt=True)) - base_norm
            candidates.append((diff, actual_delta))
        if not candidates:
            continue
        diff, actual_delta = max(candidates, key=lambda item: float(np.max(np.abs(item[0]))))
        diff_pct = diff / max(float(base_norm.max()), 1e-12) * 100.0
        vmax = max(vmax, float(np.max(np.abs(diff_pct))))
        maps.append((coef_idx, str(row["coef_label"]), diff_pct, actual_delta))
    vmax = max(vmax, 1e-6)
    for ax, (coef_idx, label, diff_pct, actual_delta) in zip(axes[1:], maps):
        im = ax.imshow(diff_pct, cmap="coolwarm", vmin=-vmax, vmax=vmax)
        wrapped_label = textwrap.fill(label, width=18)
        ax.set_title(f"{wrapped_label}\nDelta {actual_delta:+.4g}", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
    for ax in axes[1 + len(maps) :]:
        ax.axis("off")
    if im is not None:
        fig.colorbar(im, cax=cax, label="% of baseline peak")
    else:
        cax.axis("off")
    fig.suptitle("Example PSF difference maps for the strongest shape parameters", x=0.06, y=0.99, ha="left", fontsize=13, fontweight="semibold", color=TOKENS["ink"])
    fig.text(0.06, 0.945, "FOV 61 baseline; each map shows the larger available +/- 10% range perturbation.", ha="left", fontsize=9, color=TOKENS["muted"])
    out = OUTPUT_DIR / "top_parameter_diff_maps_fov061.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    chart_paths["top_diff_maps_png"] = str(out)

    return chart_paths


def write_report(summary_df: pd.DataFrame, verification: dict[str, float], chart_paths: dict[str, str]) -> Path:
    top_shape = summary_df.sort_values("shape_rank").head(6)
    top_abs = summary_df.sort_values("absolute_rank").head(6)
    lines: list[str] = []
    lines.append("# PSF Parameter Sensitivity Analysis")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("- Baseline: Circle_Round1 formal L0, 9 FOV points, each represented by the median of 15 repeated fits.")
    lines.append("- Perturbation: one parameter at a time, up to 10% of its current search range, clipped to the current bounds.")
    lines.append("- Shape metric: normalized PSF RMSE divided by the baseline normalized PSF peak.")
    lines.append("- Absolute metric: fitted PSF image RMSE divided by the baseline fitted PSF peak; this includes AC amplitude.")
    lines.append("")
    lines.append("## Model verification")
    lines.append("")
    lines.append(
        f"- Python PSF builder vs saved MATLAB stack: RMSE={verification['rmse']:.3e}, "
        f"max_abs={verification['max_abs']:.3e}, relative RMSE to peak={verification['relative_rmse_to_peak']:.3e}."
    )
    lines.append("")
    lines.append("## Top shape drivers")
    lines.append("")
    lines.append("| Rank | Parameter | Status | Median shape change (% peak) | Centroid shift (px) | Width change (%) |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for _, row in top_shape.iterrows():
        lines.append(
            f"| {int(row['shape_rank'])} | {row['coef_label']} | {row['status_round1']} | "
            f"{row['median_shape_rmse_vs_peak_pct']:.3f} | {row['median_centroid_shift_px']:.4f} | "
            f"{row['median_width_mean_abs_delta_pct']:.3f} |"
        )
    lines.append("")
    lines.append("## Top absolute-image drivers")
    lines.append("")
    lines.append("| Rank | Parameter | Status | Median absolute change (% peak) | Notes |")
    lines.append("|---:|---|---|---:|---|")
    for _, row in top_abs.iterrows():
        note = "scale-only amplitude driver" if int(row["coef_index"]) == 14 else "shape/structure driver"
        lines.append(
            f"| {int(row['absolute_rank'])} | {row['coef_label']} | {row['status_round1']} | "
            f"{row['median_absolute_rmse_vs_peak_pct']:.3f} | {note} |"
        )
    lines.append("")
    lines.append("## Output files")
    lines.append("")
    for label, path in chart_paths.items():
        lines.append(f"- {label}: `{Path(path).name}`")
    lines.append("- Summary table: `parameter_sensitivity_summary.csv`")
    lines.append("- Detail table: `parameter_sensitivity_detail.csv`")
    lines.append("")
    lines.append("## Presentation interpretation")
    lines.append("")
    lines.append("- Use the shape-sensitivity ranking to explain which optical parameters materially change the fitted PSF shape.")
    lines.append("- Use the absolute-image ranking only when discussing amplitude/scale; otherwise x15 can dominate unfairly.")
    lines.append("- Locked tilt parameters should show zero shape impact under the current pipeline because the fitter sets tilt to zero when generating PSF.")
    lines.append("- Boundary-saturated parameters can still have physical PSF impact; this analysis separates impact from trustworthiness.")
    report_path = OUTPUT_DIR / "PSF_parameter_sensitivity_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = load_psf_model()
    verification = verify_python_psf_builder(model)
    if verification["max_abs"] > 1e-12:
        raise RuntimeError(f"Python PSF builder verification failed: {verification}")

    manifest = json.loads(ROUND1_MANIFEST.read_text(encoding="utf-8"))
    noise_floor = json.loads(ROUND1_NOISE_FLOOR.read_text(encoding="utf-8"))
    classifications = noise_floor["noise_floor"]["coef_classifications"]
    fov_indices = [int(value) for value in manifest["fov_indices"]]
    tensor = load_trial_tensors(manifest)
    baselines = np.median(tensor, axis=0)

    detail_df = compute_sensitivity(baselines, model, fov_indices, classifications)
    summary_df = summarize(detail_df)
    detail_path = OUTPUT_DIR / "parameter_sensitivity_detail.csv"
    summary_path = OUTPUT_DIR / "parameter_sensitivity_summary.csv"
    detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    chart_paths = write_charts(detail_df, summary_df, model, baselines)
    report_path = write_report(summary_df, verification, chart_paths)
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline": {
            "round": "Circle_Round1",
            "n_trials": int(tensor.shape[0]),
            "n_fov": int(tensor.shape[2]),
            "fov_indices": fov_indices,
            "representative_rule": "median coefficient value across the 15 repeated fits",
        },
        "perturbation": {
            "step_fraction_of_range": 0.10,
            "clipped_to_current_bounds": True,
            "lock_tilt": True,
        },
        "verification": verification,
        "outputs": {
            "detail_csv": str(detail_path),
            "summary_csv": str(summary_path),
            "report_md": str(report_path),
            **chart_paths,
        },
    }
    (OUTPUT_DIR / "analysis_metadata.json").write_text(json.dumps(json_ready(metadata), indent=2), encoding="utf-8")

    print(f"Wrote sensitivity analysis to: {OUTPUT_DIR}")
    print(f"Verification max_abs: {verification['max_abs']:.3e}")
    print("Top shape parameters:")
    for _, row in summary_df.head(6).iterrows():
        print(
            f"  #{int(row['shape_rank'])}: {row['coef_label']} "
            f"{row['median_shape_rmse_vs_peak_pct']:.3f}% ({row['status_round1']})"
        )


if __name__ == "__main__":
    main()
