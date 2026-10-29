from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat
from scipy.ndimage import center_of_mass
from scipy.stats import wilcoxon
from skimage.measure import find_contours
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R69 = Path(PROJECT_ROOT / CONFIG["paired_evidence"]["r69_root"])
R70 = Path(PROJECT_ROOT / CONFIG["paired_evidence"]["r70_root"])
RAW_DIR = Path(PROJECT_ROOT / CONFIG["paired_evidence"]["raw_input_dir"])
RECON_DIR = Path(PROJECT_ROOT / CONFIG["inference"]["reconstruction_dir"])
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"

METHODS = ["Raw", "R61v16", "V42E120", "R75"]
COLORS = {
    "Raw": "#D97706",
    "R61v16": "#2563EB",
    "V42E120": "#059669",
    "R75": "#DC2626",
}
TRUTH_COLOR = "#111827"
SEED = int(CONFIG["statistics"]["random_seed"])
BOOTSTRAP_REPETITIONS = int(CONFIG["statistics"]["bootstrap_repetitions"])
MIN_IMPROVED_FRACTION = float(CONFIG["statistics"]["coarse_gate_min_improved_fraction"])

METRICS = {
    "iou": ("輪廓重疊率", "higher"),
    "dice": ("Dice 重疊率", "higher"),
    "mean_boundary_distance_pitch_pct": ("平均邊界距離（柱距百分比）", "lower"),
    "hd95_pitch_pct": ("較差區段邊界距離（柱距百分比）", "lower"),
    "area_error_pct": ("面積誤差（%）", "lower"),
    "perimeter_error_pct": ("周長誤差（%）", "lower"),
    "circularity_abs_error": ("圓整程度誤差", "lower"),
}


def method_slug(method: str) -> str:
    return {
        "Raw": "raw",
        "R61v16": "r61v16",
        "V42E120": "v42e120",
        "R75": "r75",
    }[method]


def improvement(source: np.ndarray, target: np.ndarray, direction: str) -> np.ndarray:
    return target - source if direction == "higher" else source - target


def bootstrap_median_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    indices = rng.integers(0, len(values), size=(BOOTSTRAP_REPETITIONS, len(values)))
    medians = np.median(values[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def holm_adjust(values: list[float]) -> list[float]:
    p_values = np.asarray(values, dtype=float)
    order = np.argsort(p_values)
    adjusted = np.empty_like(p_values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p_values) - rank) * p_values[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def assert_same_raw(current: pd.DataFrame, prior: pd.DataFrame, sensitivity: bool = False) -> None:
    key = ["preset", "exposure", "pillar_id"] if sensitivity else ["exposure", "pillar_id"]
    metric_columns = (
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
        if sensitivity
        else list(METRICS) + ["centroid_alignment_shift_px"]
    )
    a = current[current["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    b = prior[prior["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if len(a) != len(b) or not np.allclose(a[metric_columns], b[metric_columns], rtol=0, atol=1e-12):
        raise RuntimeError("重新擷取的 Raw 輪廓與鎖定的 R69 結果不一致。")


def load_combined() -> tuple[pd.DataFrame, pd.DataFrame]:
    current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    r69 = pd.read_csv(R69 / "results" / "tables" / "primary_contour_metrics.csv")
    r70 = pd.read_csv(R70 / "results" / "tables" / "primary_contour_metrics.csv")
    current_s = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    r69_s = pd.read_csv(R69 / "results" / "tables" / "acm_sensitivity_metrics.csv")
    r70_s = pd.read_csv(R70 / "results" / "tables" / "acm_sensitivity_metrics.csv")

    assert_same_raw(current, r69)
    assert_same_raw(current_s, r69_s, sensitivity=True)

    combined = pd.concat(
        [
            current[current["method"].isin(["Raw", "R75"])],
            r69[r69["method"] == "R61v16"],
            r70[r70["method"] == "V42E120"],
        ],
        ignore_index=True,
    )
    combined["method"] = pd.Categorical(combined["method"], METHODS, ordered=True)
    combined = combined.sort_values(["exposure", "pillar_id", "method"]).reset_index(drop=True)

    combined_s = pd.concat(
        [
            current_s[current_s["method"].isin(["Raw", "R75"])],
            r69_s[r69_s["method"] == "R61v16"],
            r70_s[r70_s["method"] == "V42E120"],
        ],
        ignore_index=True,
    )
    combined_s["method"] = pd.Categorical(combined_s["method"], METHODS, ordered=True)
    combined_s = combined_s.sort_values(["preset", "exposure", "pillar_id", "method"]).reset_index(drop=True)

    expected_primary = 12 * 36 * len(METHODS)
    expected_sensitivity = 3 * 3 * 36 * len(METHODS)
    if len(combined) != expected_primary or combined.isna().any().any():
        raise RuntimeError("四方法主要比較表不完整。")
    if len(combined_s) != expected_sensitivity or combined_s.isna().any().any():
        raise RuntimeError("四方法敏感度比較表不完整。")
    if combined.groupby(["exposure", "pillar_id", "method"], observed=True).size().max() != 1:
        raise RuntimeError("主要比較表含有重複的曝光、柱子與方法組合。")
    return combined, combined_s


def paired_statistics(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    medians = primary.groupby(["pillar_id", "method"], observed=True)[list(METRICS)].median().unstack("method")
    mapping = (
        primary[["pillar_id", "grid_row", "grid_col", "truth_circularity"]]
        .drop_duplicates("pillar_id")
        .set_index("pillar_id")
    )
    pillar_rows: list[dict[str, object]] = []
    for pillar_id in medians.index:
        row: dict[str, object] = {
            "pillar_id": int(pillar_id),
            "grid_row": int(mapping.loc[pillar_id, "grid_row"]),
            "grid_col": int(mapping.loc[pillar_id, "grid_col"]),
            "truth_circularity": float(mapping.loc[pillar_id, "truth_circularity"]),
        }
        for metric, (_, direction) in METRICS.items():
            for method in METHODS:
                row[f"{method_slug(method)}_{metric}"] = float(medians.loc[pillar_id, (metric, method)])
            for source in METHODS[:-1]:
                source_value = row[f"{method_slug(source)}_{metric}"]
                target_value = row[f"r75_{metric}"]
                row[f"r75_vs_{method_slug(source)}_improvement_{metric}"] = float(
                    improvement(np.array([source_value]), np.array([target_value]), direction)[0]
                )
        pillar_rows.append(row)

    summary_rows: list[dict[str, object]] = []
    for source in METHODS[:-1]:
        for metric, (label, direction) in METRICS.items():
            source_values = medians[(metric, source)].to_numpy(float)
            target_values = medians[(metric, "R75")].to_numpy(float)
            delta = improvement(source_values, target_values, direction)
            ci_low, ci_high = bootstrap_median_ci(delta, rng)
            try:
                _, p_value = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p_value = 1.0
            summary_rows.append(
                {
                    "comparison": f"{source}_to_R75",
                    "source_method": source,
                    "target_method": "R75",
                    "metric": metric,
                    "metric_label": label,
                    "better_direction": direction,
                    "independent_pillars": len(source_values),
                    "source_median": float(np.median(source_values)),
                    "target_median": float(np.median(target_values)),
                    "median_improvement": float(np.median(delta)),
                    "bootstrap_ci95_low": ci_low,
                    "bootstrap_ci95_high": ci_high,
                    "improved_pillars": int(np.count_nonzero(delta > 0)),
                    "unchanged_pillars": int(np.count_nonzero(delta == 0)),
                    "worsened_pillars": int(np.count_nonzero(delta < 0)),
                    "improved_fraction": float(np.mean(delta > 0)),
                    "wilcoxon_p_two_sided": float(p_value),
                }
            )
    summary = pd.DataFrame(summary_rows)
    summary["wilcoxon_p_holm_within_comparison"] = np.nan
    for _, indices in summary.groupby("comparison").groups.items():
        summary.loc[indices, "wilcoxon_p_holm_within_comparison"] = holm_adjust(
            summary.loc[indices, "wilcoxon_p_two_sided"].tolist()
        )
    return pd.DataFrame(pillar_rows), summary


def exposure_statistics(primary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for exposure, group in primary.groupby("exposure", observed=True, sort=True):
        image = np.asarray(Image.open(RAW_DIR / f"{int(exposure)}.bmp").convert("L"), dtype=float)
        row: dict[str, object] = {
            "exposure": int(exposure),
            "raw_mean_intensity_0_255": float(image.mean()),
        }
        for metric, (_, direction) in METRICS.items():
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            for method in METHODS:
                row[f"{method_slug(method)}_median_{metric}"] = float(pivot[method].median())
            for source in METHODS[:-1]:
                delta = improvement(pivot[source].to_numpy(float), pivot["R75"].to_numpy(float), direction)
                prefix = f"r75_vs_{method_slug(source)}"
                row[f"{prefix}_median_improvement_{metric}"] = float(np.median(delta))
                row[f"{prefix}_improved_pillars_{metric}"] = int(np.count_nonzero(delta > 0))
                row[f"{prefix}_improved_fraction_{metric}"] = float(np.mean(delta > 0))
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity_statistics(sensitivity: pd.DataFrame) -> pd.DataFrame:
    metrics = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    rows: list[dict[str, object]] = []
    for (preset, exposure), group in sensitivity.groupby(["preset", "exposure"], observed=True, sort=False):
        row: dict[str, object] = {"preset": str(preset), "exposure": int(exposure)}
        for metric in metrics:
            direction = METRICS[metric][1]
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            for method in METHODS:
                row[f"{method_slug(method)}_median_{metric}"] = float(pivot[method].median())
            for source in METHODS[:-1]:
                delta = improvement(pivot[source].to_numpy(float), pivot["R75"].to_numpy(float), direction)
                prefix = f"r75_vs_{method_slug(source)}"
                row[f"{prefix}_median_improvement_{metric}"] = float(np.median(delta))
                row[f"{prefix}_improved_pillars_{metric}"] = int(np.count_nonzero(delta > 0))
        rows.append(row)
    return pd.DataFrame(rows)


def matlab_round(values: np.ndarray) -> np.ndarray:
    return np.where(values >= 0, np.floor(values + 0.5), np.ceil(values - 0.5)).astype(int)


def shift_binary(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask, dtype=bool)
    src_x1, src_x2 = max(0, -dx), min(width, width - dx)
    src_y1, src_y2 = max(0, -dy), min(height, height - dy)
    if src_x1 < src_x2 and src_y1 < src_y2:
        shifted[src_y1 + dy : src_y2 + dy, src_x1 + dx : src_x2 + dx] = mask[src_y1:src_y2, src_x1:src_x2]
    return shifted


def align_to_truth(predicted: np.ndarray, truth: np.ndarray) -> np.ndarray:
    dy, dx = matlab_round(np.asarray(center_of_mass(truth)) - np.asarray(center_of_mass(predicted)))
    return shift_binary(predicted, int(dy), int(dx))


def draw_contour(
    ax: plt.Axes,
    mask: np.ndarray,
    color: str,
    linewidth: float = 1.4,
    linestyle: str = "-",
) -> None:
    for contour in find_contours(mask.astype(float), 0.5):
        ax.plot(contour[:, 1], contour[:, 0], color=color, linewidth=linewidth, linestyle=linestyle)


def configure_plotting() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 10,
            "font.sans-serif": ["Microsoft JhengHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def make_identity_figure() -> None:
    mapping = pd.read_csv(TABLES / "verified_pillar_mapping.csv")
    configure_plotting()
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), constrained_layout=True)

    p_grid = [["P-07", "P-08", "P-09"], ["P-06", "P-05", "P-04"], ["P-01", "P-02", "P-03"]]
    for row in range(3):
        for col in range(3):
            axes[0].add_patch(Rectangle((col, 2 - row), 1, 1, facecolor="#E0F2FE", edgecolor="#0369A1", lw=2))
            axes[0].text(col + 0.5, 2.5 - row, p_grid[row][col], ha="center", va="center", fontsize=16, weight="bold")
    axes[0].set_xlim(0, 3)
    axes[0].set_ylim(0, 3)
    axes[0].set_aspect("equal")
    axes[0].set_title("九張 P 系列 SEM 的實際空間順序", fontsize=14, weight="bold")
    axes[0].axis("off")

    corner_short = {"top_left": "左上", "top_right": "右上", "bottom_left": "左下", "bottom_right": "右下"}
    for row in range(6):
        for col in range(6):
            item = mapping[(mapping["grid_row"] == row + 1) & (mapping["grid_col"] == col + 1)].iloc[0]
            axes[1].add_patch(Rectangle((col, 5 - row), 1, 1, facecolor="#F8FAFC", edgecolor="#64748B", lw=1))
            axes[1].text(col + 0.5, 5.63 - row, f"ID {int(item['pillar_id'])}", ha="center", va="center", fontsize=10, weight="bold")
            axes[1].text(col + 0.5, 5.31 - row, f"{Path(item['sem_file']).stem} {corner_short[item['sem_corner']]}", ha="center", va="center", fontsize=7.5)
    axes[1].set_xlim(0, 6)
    axes[1].set_ylim(0, 6)
    axes[1].set_aspect("equal")
    axes[1].set_title("中央 6×6：每一顆的編號與 SEM 來源", fontsize=14, weight="bold")
    axes[1].axis("off")
    fig.suptitle("36 顆實體 pillar 的已驗證對應關係", fontsize=17, weight="bold")
    fig.savefig(FIGURES / "00_verified_sem_pillar_identity_map.png", dpi=210, facecolor="white")
    plt.close(fig)


def make_figures(
    per_pillar: pd.DataFrame,
    per_exposure: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> dict[str, int]:
    configure_plotting()
    make_identity_figure()
    mask_variables = [
        "truth_cells",
        "truth_masks",
        "raw_cells",
        "raw_masks",
        "recon_cells",
        "recon_masks",
        "exposures",
        "global_index",
    ]
    current = loadmat(RESULTS / "masks" / "acm_primary_masks.mat", squeeze_me=True, variable_names=mask_variables)
    r69 = loadmat(R69 / "results" / "masks" / "acm_primary_masks.mat", squeeze_me=True, variable_names=mask_variables)
    r70 = loadmat(R70 / "results" / "masks" / "acm_primary_masks.mat", squeeze_me=True, variable_names=mask_variables)
    truth_cells = current["truth_cells"]
    truth_masks = current["truth_masks"].astype(bool)
    raw_cells = current["raw_cells"]
    raw_masks = current["raw_masks"].astype(bool)
    r75_cells = current["recon_cells"]
    r75_masks = current["recon_masks"].astype(bool)
    r61_cells = r69["recon_cells"]
    r61_masks = r69["recon_masks"].astype(bool)
    v42_cells = r70["recon_cells"]
    v42_masks = r70["recon_masks"].astype(bool)
    exposures = np.asarray(current["exposures"]).astype(int).ravel()
    global_index = np.asarray(current["global_index"]).astype(int)

    fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
    for row, exposure in enumerate([18, 24]):
        raw = np.asarray(Image.open(RAW_DIR / f"{exposure}.bmp").convert("L"), dtype=float)
        recon = np.asarray(Image.open(RECON_DIR / f"{exposure}.bmp").convert("L"), dtype=float)
        difference = np.abs(recon - raw)
        axes[row, 0].imshow(raw, cmap="gray", vmin=0, vmax=255)
        axes[row, 1].imshow(recon, cmap="gray", vmin=0, vmax=255)
        diff_plot = axes[row, 2].imshow(
            difference,
            cmap="magma",
            vmin=0,
            vmax=max(1, np.percentile(difference, 99.5)),
        )
        axes[row, 0].set_title(f"重建前：曝光 {exposure}")
        axes[row, 1].set_title(f"R75 重建後：曝光 {exposure}")
        axes[row, 2].set_title("像素改變量（只作影像檢查）")
        fig.colorbar(diff_plot, ax=axes[row, 2], shrink=0.72, label="灰階差")
        for ax in axes[row]:
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("R75 重建前後對比：一般亮度與最暗影像", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "01_raw_r75_reconstruction_comparison.png", dpi=190, facecolor="white")
    plt.close(fig)

    exposure_index = int(np.flatnonzero(exposures == 18)[0])
    fig, axes = plt.subplots(6, 6, figsize=(13, 13), constrained_layout=True)
    for row in range(6):
        for col in range(6):
            pillar_id = int(global_index[row, col])
            index = pillar_id - 1
            ax = axes[row, col]
            truth = truth_masks[:, :, index]
            ax.imshow(truth_cells[:, :, index], cmap="gray", vmin=0, vmax=255)
            draw_contour(ax, truth, TRUTH_COLOR, 1.25)
            draw_contour(ax, align_to_truth(raw_masks[:, :, index, exposure_index], truth), COLORS["Raw"], 1.0, "--")
            draw_contour(ax, align_to_truth(r75_masks[:, :, index, exposure_index], truth), COLORS["R75"], 1.1)
            ax.set_title(f"ID {pillar_id}", fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
    fig.legend(
        handles=[
            Line2D([0], [0], color=TRUTH_COLOR, label="SEM"),
            Line2D([0], [0], color=COLORS["Raw"], linestyle="--", label="重建前"),
            Line2D([0], [0], color=COLORS["R75"], label="R75"),
        ],
        loc="outside lower center",
        ncol=3,
        frameon=False,
    )
    fig.suptitle("中央 36 顆完整輪廓疊圖（曝光 18）", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "02_center36_contour_overlay_exp18.png", dpi=190, facecolor="white")
    plt.close(fig)

    display_metrics = ["iou", "mean_boundary_distance_pitch_pct", "area_error_pct", "perimeter_error_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for ax, metric in zip(axes.ravel(), display_metrics):
        arrays = [per_pillar[f"{method_slug(method)}_{metric}"].to_numpy(float) for method in METHODS]
        for values in zip(*arrays):
            ax.plot(range(len(METHODS)), values, color="#CBD5E1", lw=0.6, zorder=1)
        for x, method, values in zip(range(len(METHODS)), METHODS, arrays):
            ax.scatter(np.full_like(values, x), values, color=COLORS[method], s=22, alpha=0.78, zorder=2)
        ax.plot(range(len(METHODS)), [np.median(values) for values in arrays], color=TRUTH_COLOR, lw=2.0, zorder=3)
        ax.set_xticks(range(len(METHODS)), METHODS)
        ax.set_title(METRICS[metric][0], weight="bold")
        ax.grid(axis="y", color="#E2E8F0")
    fig.suptitle("36 顆實體 pillar 的四方法配對比較", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "03_four_method_paired_comparison.png", dpi=200, facecolor="white")
    plt.close(fig)

    x_values = per_exposure["exposure"].to_numpy(int)
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for method in METHODS:
        slug = method_slug(method)
        axes[0].plot(
            x_values,
            per_exposure[f"{slug}_median_mean_boundary_distance_pitch_pct"],
            marker="o",
            lw=2,
            color=COLORS[method],
            label=method,
        )
        axes[1].plot(
            x_values,
            per_exposure[f"{slug}_median_area_error_pct"],
            marker="o",
            lw=2,
            color=COLORS[method],
            label=method,
        )
    for ax in axes:
        ax.axvspan(22.5, 24.5, color="#FEF3C7", alpha=0.75)
        ax.grid(axis="y", color="#E2E8F0")
        ax.legend(frameon=False, ncol=4)
    axes[0].set_ylabel("平均邊界距離（% 柱距）")
    axes[1].set_ylabel("面積誤差（%）")
    axes[1].set_xticks(
        x_values,
        [f"{exposure}\n{brightness:.0f}" for exposure, brightness in zip(x_values, per_exposure["raw_mean_intensity_0_255"])],
    )
    axes[1].set_xlabel("曝光編號 / 原圖平均亮度")
    fig.suptitle("不同亮度下的輪廓準確度", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "04_exposure_stability.png", dpi=200, facecolor="white")
    plt.close(fig)

    improvements = per_pillar["r75_vs_raw_improvement_mean_boundary_distance_pitch_pct"]
    representative_id = int(per_pillar.iloc[(improvements - improvements.median()).abs().argmin()]["pillar_id"])
    representative_index = representative_id - 1
    fig, axes = plt.subplots(2, 5, figsize=(16, 7), constrained_layout=True)
    for row, exposure in enumerate([18, 24]):
        exposure_index = int(np.flatnonzero(exposures == exposure)[0])
        truth = truth_masks[:, :, representative_index]
        panels = [
            (truth_cells[:, :, representative_index], truth, "SEM", TRUTH_COLOR),
            (raw_cells[:, :, representative_index, exposure_index], raw_masks[:, :, representative_index, exposure_index], "重建前", COLORS["Raw"]),
            (r61_cells[:, :, representative_index, exposure_index], r61_masks[:, :, representative_index, exposure_index], "R61v16", COLORS["R61v16"]),
            (v42_cells[:, :, representative_index, exposure_index], v42_masks[:, :, representative_index, exposure_index], "V42E120", COLORS["V42E120"]),
            (r75_cells[:, :, representative_index, exposure_index], r75_masks[:, :, representative_index, exposure_index], "R75", COLORS["R75"]),
        ]
        for col, (cell, mask, title, color) in enumerate(panels):
            ax = axes[row, col]
            ax.imshow(cell, cmap="gray", vmin=0, vmax=255)
            draw_contour(ax, truth, TRUTH_COLOR, 1.1 if col else 1.6)
            if col:
                draw_contour(ax, align_to_truth(mask, truth), color, 1.5)
            ax.set_title(f"{title}\n曝光 {exposure}" if col else f"{title}\nID {representative_id}")
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("同一顆 pillar：一般亮度與最暗曝光", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "05_normal_dark_contour_comparison.png", dpi=210, facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), sharey=True, constrained_layout=True)
    preset_order = ["less_smooth", "primary", "more_smooth"]
    for ax, exposure in zip(axes, [13, 18, 24]):
        subset = sensitivity[sensitivity["exposure"] == exposure].set_index("preset").loc[preset_order]
        for method in METHODS:
            ax.plot(
                range(3),
                subset[f"{method_slug(method)}_median_mean_boundary_distance_pitch_pct"],
                marker="o",
                lw=2,
                color=COLORS[method],
                label=method,
            )
        ax.set_xticks(range(3), ["較少平滑", "主要設定", "較多平滑"], rotation=12)
        ax.set_title(f"曝光 {exposure}")
        ax.grid(axis="y", color="#E2E8F0")
    axes[0].set_ylabel("平均邊界距離（% 柱距）")
    axes[-1].legend(frameon=False)
    fig.suptitle("ACM 設定改變後，結論是否穩定", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "06_contour_setting_sensitivity.png", dpi=200, facecolor="white")
    plt.close(fig)
    return {"representative_pillar_id": representative_id}


def build_decision(
    comparisons: pd.DataFrame,
    exposure: pd.DataFrame,
    sensitivity: pd.DataFrame,
    representatives: dict[str, int],
) -> dict[str, object]:
    raw = comparisons[comparisons["comparison"] == "Raw_to_R75"].set_index("metric")
    coarse_metrics = ["iou", "mean_boundary_distance_pitch_pct"]
    coarse_gate = all(
        raw.loc[metric, "bootstrap_ci95_low"] > 0
        and raw.loc[metric, "improved_fraction"] >= MIN_IMPROVED_FRACTION
        for metric in coarse_metrics
    )
    universal_by_exposure: dict[str, bool] = {}
    for _, row in exposure.iterrows():
        exposure_id = str(int(row["exposure"]))
        universal_by_exposure[exposure_id] = bool(
            row["r75_vs_raw_median_improvement_iou"] > 0
            and row["r75_vs_raw_median_improvement_mean_boundary_distance_pitch_pct"] > 0
        )
    universal_gate = all(universal_by_exposure.values())
    fine_gate = bool(
        raw.loc["perimeter_error_pct", "median_improvement"] > 0
        and raw.loc["circularity_abs_error", "median_improvement"] > 0
    )
    sensitivity_direction: dict[str, bool] = {}
    for exposure_id in [13, 18, 24]:
        rows = sensitivity[sensitivity["exposure"] == exposure_id]
        sensitivity_direction[str(exposure_id)] = bool(
            (rows["r75_vs_raw_median_improvement_iou"] > 0).all()
            and (rows["r75_vs_raw_median_improvement_mean_boundary_distance_pitch_pct"] > 0).all()
        )

    comparisons_to_prior: dict[str, str] = {}
    for source in ["R61v16", "V42E120"]:
        group = comparisons[comparisons["comparison"] == f"{source}_to_R75"].set_index("metric")
        if all(group.loc[metric, "bootstrap_ci95_low"] > 0 for metric in coarse_metrics):
            result = "R75_better"
        elif all(group.loc[metric, "bootstrap_ci95_high"] < 0 for metric in coarse_metrics):
            result = f"{source}_better"
        else:
            result = "not_decisive"
        comparisons_to_prior[source] = result

    if coarse_gate and universal_gate and fine_gate:
        status = "pass_universal_full_shape"
    elif coarse_gate and universal_gate:
        status = "pass_coarse_universal_fine_shape_not_proven"
    elif coarse_gate:
        status = "conditional_pass_not_universal"
    else:
        status = "coarse_improvement_not_proven"
    truth_circularity = pd.read_csv(TABLES / "primary_contour_metrics.csv").drop_duplicates("pillar_id")["truth_circularity"]
    return {
        "status": status,
        "primary_coarse_contour_gate": bool(coarse_gate),
        "all_exposure_universal_gate": bool(universal_gate),
        "fine_shape_fidelity_gate": bool(fine_gate),
        "universal_gate_by_exposure": universal_by_exposure,
        "acm_sensitivity_direction_consistent": sensitivity_direction,
        "comparison_to_prior_models": comparisons_to_prior,
        "sem_truth_circularity": {
            "median": float(truth_circularity.median()),
            "minimum": float(truth_circularity.min()),
            "maximum": float(truth_circularity.max()),
        },
        "representatives": representatives,
    }


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def pass_text(value: bool) -> str:
    return "通過" if value else "未通過"


def write_report(comparisons: pd.DataFrame, exposure: pd.DataFrame, decision: dict[str, object]) -> None:
    groups = {
        source: comparisons[comparisons["comparison"] == f"{source}_to_R75"].set_index("metric")
        for source in ["Raw", "R61v16", "V42E120"]
    }
    raw = groups["Raw"]
    mbd = raw.loc["mean_boundary_distance_pitch_pct"]
    iou = raw.loc["iou"]
    area = raw.loc["area_error_pct"]
    perimeter = raw.loc["perimeter_error_pct"]
    circularity = raw.loc["circularity_abs_error"]
    passing_exposures = [key for key, value in decision["universal_gate_by_exposure"].items() if value]
    failing_exposures = [key for key, value in decision["universal_gate_by_exposure"].items() if not value]

    if decision["primary_coarse_contour_gate"]:
        headline = "R75 的主要完整輪廓改善已成立。"
    else:
        headline = "R75 尚未證明能穩定改善主要完整輪廓。"
    if decision["all_exposure_universal_gate"]:
        universal_sentence = "十二個曝光都維持改善，因此通過目前測到的亮度範圍。"
    else:
        universal_sentence = f"改善成立的曝光為 {', '.join(passing_exposures) or '無'}；未成立的曝光為 {', '.join(failing_exposures) or '無'}，所以不能宣稱任何亮度都適用。"

    prior_lines = []
    for source in ["R61v16", "V42E120"]:
        group = groups[source]
        metric = group.loc["mean_boundary_distance_pitch_pct"]
        prior_lines.append(
            f"- 相對 {source}：平均邊界距離由 **{fmt(metric['source_median'])}** 變成 **{fmt(metric['target_median'])}% 柱距**，"
            f"R75 在 **{int(metric['improved_pillars'])}/36** 顆較好；95% 範圍為 **{fmt(metric['bootstrap_ci95_low'])}–{fmt(metric['bootstrap_ci95_high'])}**。"
        )

    exposure_rows = []
    for exposure_id in [13, 18, 23, 24]:
        row = exposure[exposure["exposure"] == exposure_id].iloc[0]
        exposure_rows.append(
            f"| {exposure_id} | {row['raw_mean_intensity_0_255']:.1f} | "
            f"{row['raw_median_mean_boundary_distance_pitch_pct']:.3f} | "
            f"{row['r61v16_median_mean_boundary_distance_pitch_pct']:.3f} | "
            f"{row['v42e120_median_mean_boundary_distance_pitch_pct']:.3f} | "
            f"{row['r75_median_mean_boundary_distance_pitch_pct']:.3f} | "
            f"{int(row['r75_vs_raw_improved_pillars_mean_boundary_distance_pitch_pct'])}/36 |"
        )

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = f"""# R76：R75 對 SEM 的 ACM 完整輪廓驗證

## 結論先行

**{headline}** {universal_sentence}

- 36 顆柱子跨 12 個曝光取中位數後，平均邊界距離由重建前的 **{fmt(mbd['source_median'])}% 柱距**變成 R75 的 **{fmt(mbd['target_median'])}% 柱距**；**{int(mbd['improved_pillars'])}/36** 顆改善，改善量的 95% 範圍為 **{fmt(mbd['bootstrap_ci95_low'])}–{fmt(mbd['bootstrap_ci95_high'])}% 柱距**。
- 輪廓重疊率由 **{fmt(iou['source_median'])}** 變成 **{fmt(iou['target_median'])}**；**{int(iou['improved_pillars'])}/36** 顆改善。
- 面積誤差由 **{fmt(area['source_median'], 2)}%** 變成 **{fmt(area['target_median'], 2)}%**。
- 周長誤差由 **{fmt(perimeter['source_median'], 2)}%** 變成 **{fmt(perimeter['target_median'], 2)}%**；圓整程度誤差由 **{fmt(circularity['source_median'])}** 變成 **{fmt(circularity['target_median'])}**。細部形狀門檻：**{pass_text(bool(decision['fine_shape_fidelity_gate']))}**。
- 主要粗輪廓門檻：**{pass_text(bool(decision['primary_coarse_contour_gate']))}**；全部曝光門檻：**{pass_text(bool(decision['all_exposure_universal_gate']))}**。

## 與先前模型比較

{chr(10).join(prior_lines)}

## 不同亮度下的結果

| 曝光 | 原圖平均亮度 | 重建前邊界距離 | R61v16 | V42E120 | R75 | R75 優於原圖的柱子 |
|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(exposure_rows)}

## 哪一顆是哪一顆

九張 P 系列 SEM 的空間順序已由舊研究程式還原，並以兩個獨立來源交叉確認。每張圖內的四顆固定按左上、右上、左下、右下排列。完整的 36 顆表與圖都保存在本實驗；這不是依外觀相似度猜出的結果。

## 公平性與可信度檢查

- H 槽目前的 18 張 P/V SEM 與當年配對資料逐張完全相同。
- 十二張光學影像與當年來源逐張完全相同，確定是同一個 6×6 區域的 12 次亮度觀察。
- R75 權重只由合成訓練資料的內部驗證挑選，SEM 沒有參與挑 epoch。
- 四個方法都對照相同的 SEM 外框，只能平移對準中心，不能替任何方法調大小或旋轉。
- 獨立樣本是 36 顆實體柱；12 個曝光是重複觀察，沒有被誤當成 432 顆獨立柱。
- ACM 會利用明暗反差找出邊界，但最後的 IoU、邊界距離、面積與周長比較都只針對二值形狀，不直接比較亮度值。
- 曝光 13、18、24 各用三組平滑程度重做；方向一致性為：{json.dumps(decision['acm_sensitivity_direction_consistent'], ensure_ascii=False)}。

## 圖表

1. `00_verified_sem_pillar_identity_map.png`：九張 SEM 的位置與 36 顆編號。
2. `01_raw_r75_reconstruction_comparison.png`：一般亮度與最暗影像的重建前後。
3. `02_center36_contour_overlay_exp18.png`：36 顆 SEM、重建前、R75 輪廓疊圖。
4. `03_four_method_paired_comparison.png`：Raw、R61v16、V42E120、R75 的逐顆比較。
5. `04_exposure_stability.png`：曝光 13–24 的穩定性。
6. `05_normal_dark_contour_comparison.png`：同一顆在一般與最暗曝光下的五方比較。
7. `06_contour_setting_sensitivity.png`：ACM 設定改變後的結果。

## 使用限制

這個結果能支持的是：R75 對這批「有明確 SEM 配對證據」的 50 倍中央 36 顆柱子是否改善。它不能單獨證明所有倍率、所有材質、所有缺陷或所有顯微鏡條件都一定適用；那些仍需另外的外部資料集驗證。
"""
    (REPORTS / "R76_RESULTS_TW.md").write_text(report, encoding="utf-8")


def main() -> None:
    primary, sensitivity = load_combined()
    per_pillar, comparisons = paired_statistics(primary)
    per_exposure = exposure_statistics(primary)
    sensitivity_summary = sensitivity_statistics(sensitivity)

    primary.to_csv(TABLES / "four_method_primary_contour_metrics.csv", index=False)
    per_pillar.to_csv(TABLES / "four_method_per_pillar_summary.csv", index=False)
    comparisons.to_csv(TABLES / "r75_paired_comparison_summary.csv", index=False)
    per_exposure.to_csv(TABLES / "four_method_per_exposure_summary.csv", index=False)
    sensitivity_summary.to_csv(TABLES / "four_method_sensitivity_summary.csv", index=False)

    representatives = make_figures(per_pillar, per_exposure, sensitivity_summary)
    decision = build_decision(comparisons, per_exposure, sensitivity_summary, representatives)
    (RESULTS / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(comparisons, per_exposure, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
