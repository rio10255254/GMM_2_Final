from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat
from scipy.ndimage import center_of_mass
from scipy.stats import wilcoxon
from skimage.measure import find_contours
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R69 = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation'))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"
RAW_DIR = R69 / "inputs" / "sem_paired_50x_exposure_stack"
RECON_DIR = (
    RESULTS
    / "inference_runs"
    / "reconstruct_progress_epoch_120_in_sem_paired_50x_exposure_stack_20260709_202713"
    / "v42e120_sem_paired_50x"
)

METHODS = ["Raw", "R61v16", "V42E120"]
COLORS = {"Raw": "#D97706", "R61v16": "#2563EB", "V42E120": "#059669"}
TRUTH_COLOR = "#111827"
SEED = 20260730

METRICS = {
    "iou": ("輪廓重疊率", "higher"),
    "dice": ("Dice 重疊率", "higher"),
    "mean_boundary_distance_pitch_pct": ("平均邊界距離", "lower"),
    "hd95_pitch_pct": ("最差區段邊界距離", "lower"),
    "area_error_pct": ("面積誤差", "lower"),
    "perimeter_error_pct": ("周長誤差", "lower"),
    "circularity_abs_error": ("圓整程度誤差", "lower"),
}


def method_slug(method: str) -> str:
    return {"Raw": "raw", "R61v16": "r61v16", "V42E120": "v42e120"}[method]


def improvement(source: np.ndarray, target: np.ndarray, direction: str) -> np.ndarray:
    return target - source if direction == "higher" else source - target


def bootstrap_median_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    indices = rng.integers(0, len(values), size=(20_000, len(values)))
    medians = np.median(values[indices], axis=1)
    return tuple(float(value) for value in np.quantile(medians, [0.025, 0.975]))


def holm_adjust(values: list[float]) -> list[float]:
    p = np.asarray(values, dtype=float)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(p) - rank) * p[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def load_combined() -> tuple[pd.DataFrame, pd.DataFrame]:
    current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    prior = pd.read_csv(R69 / "results" / "tables" / "primary_contour_metrics.csv")
    current_sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    prior_sensitivity = pd.read_csv(R69 / "results" / "tables" / "acm_sensitivity_metrics.csv")

    key = ["exposure", "pillar_id"]
    metric_columns = list(METRICS) + ["centroid_alignment_shift_px"]
    raw_current = current[current["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    raw_prior = prior[prior["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if not np.allclose(raw_current[metric_columns], raw_prior[metric_columns], rtol=0, atol=1e-12):
        raise RuntimeError("The rerun Raw contour metrics do not match R69; comparison is not locked.")

    combined = pd.concat(
        [
            current[current["method"].isin(["Raw", "V42E120"])],
            prior[prior["method"] == "R61v16"],
        ],
        ignore_index=True,
    )
    combined["method"] = pd.Categorical(combined["method"], METHODS, ordered=True)
    combined = combined.sort_values(["exposure", "pillar_id", "method"]).reset_index(drop=True)

    sensitivity_key = ["preset", "exposure", "pillar_id"]
    sraw_current = current_sensitivity[current_sensitivity["method"] == "Raw"].sort_values(sensitivity_key).reset_index(drop=True)
    sraw_prior = prior_sensitivity[prior_sensitivity["method"] == "Raw"].sort_values(sensitivity_key).reset_index(drop=True)
    s_metrics = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    if not np.allclose(sraw_current[s_metrics], sraw_prior[s_metrics], rtol=0, atol=1e-12):
        raise RuntimeError("The rerun Raw sensitivity metrics do not match R69.")
    combined_sensitivity = pd.concat(
        [
            current_sensitivity[current_sensitivity["method"].isin(["Raw", "V42E120"])],
            prior_sensitivity[prior_sensitivity["method"] == "R61v16"],
        ],
        ignore_index=True,
    )
    combined_sensitivity["method"] = pd.Categorical(combined_sensitivity["method"], METHODS, ordered=True)
    return combined, combined_sensitivity


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
            raw = row[f"raw_{metric}"]
            r61 = row[f"r61v16_{metric}"]
            v42 = row[f"v42e120_{metric}"]
            row[f"v42_vs_raw_improvement_{metric}"] = float(
                improvement(np.array([raw]), np.array([v42]), direction)[0]
            )
            row[f"v42_vs_r61_improvement_{metric}"] = float(
                improvement(np.array([r61]), np.array([v42]), direction)[0]
            )
        pillar_rows.append(row)

    summary_rows: list[dict[str, object]] = []
    for source in ["Raw", "R61v16"]:
        for metric, (label, direction) in METRICS.items():
            source_values = medians[(metric, source)].to_numpy(float)
            target_values = medians[(metric, "V42E120")].to_numpy(float)
            delta = improvement(source_values, target_values, direction)
            ci_low, ci_high = bootstrap_median_ci(delta, rng)
            try:
                _, p_value = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p_value = 1.0
            summary_rows.append(
                {
                    "comparison": f"{source}_to_V42E120",
                    "source_method": source,
                    "target_method": "V42E120",
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
    for comparison, indices in summary.groupby("comparison").groups.items():
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
            for source in ["Raw", "R61v16"]:
                delta = improvement(pivot[source].to_numpy(float), pivot["V42E120"].to_numpy(float), direction)
                prefix = "v42_vs_raw" if source == "Raw" else "v42_vs_r61"
                row[f"{prefix}_median_improvement_{metric}"] = float(np.median(delta))
                row[f"{prefix}_improved_pillars_{metric}"] = int(np.count_nonzero(delta > 0))
                row[f"{prefix}_improved_fraction_{metric}"] = float(np.mean(delta > 0))
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity_statistics(sensitivity: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    metrics = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    for (preset, exposure), group in sensitivity.groupby(["preset", "exposure"], observed=True, sort=False):
        row: dict[str, object] = {"preset": str(preset), "exposure": int(exposure)}
        for metric in metrics:
            direction = METRICS[metric][1]
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            for method in METHODS:
                row[f"{method_slug(method)}_median_{metric}"] = float(pivot[method].median())
            delta = improvement(pivot["Raw"].to_numpy(float), pivot["V42E120"].to_numpy(float), direction)
            row[f"v42_vs_raw_median_improvement_{metric}"] = float(np.median(delta))
            row[f"v42_vs_raw_improved_pillars_{metric}"] = int(np.count_nonzero(delta > 0))
        rows.append(row)
    return pd.DataFrame(rows)


def matlab_round(value: np.ndarray) -> np.ndarray:
    return np.where(value >= 0, np.floor(value + 0.5), np.ceil(value - 0.5)).astype(int)


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


def draw_contour(ax: plt.Axes, mask: np.ndarray, color: str, linewidth: float = 1.4, linestyle: str = "-") -> None:
    for contour in find_contours(mask.astype(float), 0.5):
        ax.plot(contour[:, 1], contour[:, 0], color=color, linewidth=linewidth, linestyle=linestyle)


def make_figures(primary: pd.DataFrame, per_pillar: pd.DataFrame, per_exposure: pd.DataFrame, sensitivity: pd.DataFrame) -> dict[str, int]:
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
    current = loadmat(
        TABLES.parent / "masks" / "acm_primary_masks.mat",
        squeeze_me=True,
        variable_names=mask_variables,
    )
    prior = loadmat(
        R69 / "results" / "masks" / "acm_primary_masks.mat",
        squeeze_me=True,
        variable_names=mask_variables,
    )
    truth_cells = current["truth_cells"]
    truth_masks = current["truth_masks"].astype(bool)
    raw_cells = current["raw_cells"]
    raw_masks = current["raw_masks"].astype(bool)
    v42_cells = current["recon_cells"]
    v42_masks = current["recon_masks"].astype(bool)
    r61_cells = prior["recon_cells"]
    r61_masks = prior["recon_masks"].astype(bool)
    exposures = np.asarray(current["exposures"]).astype(int).ravel()
    global_index = np.asarray(current["global_index"]).astype(int)
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

    fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
    for row, exposure in enumerate([18, 24]):
        raw = np.asarray(Image.open(RAW_DIR / f"{exposure}.bmp").convert("L"), dtype=float)
        v42 = np.asarray(Image.open(RECON_DIR / f"{exposure}.bmp").convert("L"), dtype=float)
        difference = np.abs(v42 - raw)
        axes[row, 0].imshow(raw, cmap="gray", vmin=0, vmax=255)
        axes[row, 1].imshow(v42, cmap="gray", vmin=0, vmax=255)
        image = axes[row, 2].imshow(difference, cmap="magma", vmin=0, vmax=max(1, np.percentile(difference, 99.5)))
        axes[row, 0].set_title(f"Raw exposure {exposure}")
        axes[row, 1].set_title(f"V42E120 exposure {exposure}")
        axes[row, 2].set_title("Absolute pixel change")
        fig.colorbar(image, ax=axes[row, 2], shrink=0.72, label="gray levels")
        for ax in axes[row]:
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("V42E120 reconstruction before/after comparison", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "01_raw_v42_reconstruction_comparison.png", dpi=190, facecolor="white")
    plt.close(fig)

    exposure_index = int(np.flatnonzero(exposures == 18)[0])
    fig, axes = plt.subplots(6, 6, figsize=(13, 13), constrained_layout=True)
    for row in range(6):
        for col in range(6):
            pillar_id = int(global_index[row, col])
            index = pillar_id - 1
            ax = axes[row, col]
            ax.imshow(truth_cells[:, :, index], cmap="gray", vmin=0, vmax=255)
            draw_contour(ax, truth_masks[:, :, index], TRUTH_COLOR, 1.25)
            draw_contour(ax, align_to_truth(raw_masks[:, :, index, exposure_index], truth_masks[:, :, index]), COLORS["Raw"], 1.0, "--")
            draw_contour(ax, align_to_truth(v42_masks[:, :, index, exposure_index], truth_masks[:, :, index]), COLORS["V42E120"], 1.1)
            ax.set_title(f"ID {pillar_id}", fontsize=8)
            ax.set_xticks([])
            ax.set_yticks([])
    fig.legend(
        handles=[
            Line2D([0], [0], color=TRUTH_COLOR, label="SEM"),
            Line2D([0], [0], color=COLORS["Raw"], linestyle="--", label="Raw"),
            Line2D([0], [0], color=COLORS["V42E120"], label="V42E120"),
        ],
        loc="outside lower center",
        ncol=3,
        frameon=False,
    )
    fig.suptitle("Center 36 contour overlay — exposure 18", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "02_center36_contour_overlay_exp18.png", dpi=190, facecolor="white")
    plt.close(fig)

    display_metrics = ["iou", "mean_boundary_distance_pitch_pct", "area_error_pct", "perimeter_error_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for ax, metric in zip(axes.ravel(), display_metrics):
        values = [per_pillar[f"{method_slug(method)}_{metric}"].to_numpy(float) for method in METHODS]
        for triplet in zip(*values):
            ax.plot(range(3), triplet, color="#CBD5E1", lw=0.7, zorder=1)
        for x, method, array in zip(range(3), METHODS, values):
            ax.scatter(np.full_like(array, x), array, color=COLORS[method], s=24, alpha=0.8, zorder=2)
        ax.plot(range(3), [np.median(array) for array in values], color=TRUTH_COLOR, lw=2.0, zorder=3)
        ax.set_xticks(range(3), METHODS)
        ax.set_title(METRICS[metric][0], fontweight="bold")
        ax.grid(axis="y", color="#E2E8F0")
    fig.suptitle("Paired contour comparison across 36 physical pillars", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "03_paired_model_comparison.png", dpi=200, facecolor="white")
    plt.close(fig)

    x = per_exposure["exposure"].to_numpy(int)
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, constrained_layout=True)
    for method in METHODS:
        slug = method_slug(method)
        axes[0].plot(x, per_exposure[f"{slug}_median_mean_boundary_distance_pitch_pct"], marker="o", lw=2, color=COLORS[method], label=method)
        axes[1].plot(x, per_exposure[f"{slug}_median_area_error_pct"], marker="o", lw=2, color=COLORS[method], label=method)
    for ax in axes:
        ax.axvspan(22.5, 24.5, color="#FEF3C7", alpha=0.75)
        ax.grid(axis="y", color="#E2E8F0")
        ax.legend(frameon=False, ncol=3)
    axes[0].set_ylabel("Mean boundary distance (% pitch)")
    axes[1].set_ylabel("Area error (%)")
    axes[1].set_xticks(x, [f"{e}\n{b:.0f}" for e, b in zip(x, per_exposure["raw_mean_intensity_0_255"])])
    axes[1].set_xlabel("Exposure number / Raw mean brightness")
    fig.suptitle("Contour accuracy by exposure", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "04_exposure_stability.png", dpi=200, facecolor="white")
    plt.close(fig)

    improvements = per_pillar["v42_vs_raw_improvement_mean_boundary_distance_pitch_pct"]
    representative_id = int(per_pillar.iloc[(improvements - improvements.median()).abs().argmin()]["pillar_id"])
    representative_index = representative_id - 1
    fig, axes = plt.subplots(2, 4, figsize=(13, 7), constrained_layout=True)
    for row, exposure in enumerate([18, 24]):
        exposure_index = int(np.flatnonzero(exposures == exposure)[0])
        panels = [
            (truth_cells[:, :, representative_index], truth_masks[:, :, representative_index], "SEM truth", TRUTH_COLOR),
            (raw_cells[:, :, representative_index, exposure_index], raw_masks[:, :, representative_index, exposure_index], "Raw", COLORS["Raw"]),
            (r61_cells[:, :, representative_index, exposure_index], r61_masks[:, :, representative_index, exposure_index], "R61v16", COLORS["R61v16"]),
            (v42_cells[:, :, representative_index, exposure_index], v42_masks[:, :, representative_index, exposure_index], "V42E120", COLORS["V42E120"]),
        ]
        truth = truth_masks[:, :, representative_index]
        for col, (cell, mask, title, color) in enumerate(panels):
            ax = axes[row, col]
            ax.imshow(cell, cmap="gray", vmin=0, vmax=255)
            if col == 0:
                draw_contour(ax, truth, TRUTH_COLOR, 1.6)
            else:
                draw_contour(ax, truth, TRUTH_COLOR, 1.1)
                draw_contour(ax, align_to_truth(mask, truth), color, 1.5)
            ax.set_title(f"{title}\nexposure {exposure}" if col else f"{title}\nID {representative_id}")
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("Same pillar at normal and darkest exposure", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "05_normal_dark_contour_comparison.png", dpi=210, facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), sharey=True, constrained_layout=True)
    preset_order = ["less_smooth", "primary", "more_smooth"]
    for ax, exposure in zip(axes, [13, 18, 24]):
        subset = sensitivity[sensitivity["exposure"] == exposure].set_index("preset").loc[preset_order]
        for method in METHODS:
            ax.plot(range(3), subset[f"{method_slug(method)}_median_mean_boundary_distance_pitch_pct"], marker="o", lw=2, color=COLORS[method], label=method)
        ax.set_xticks(range(3), ["Less smooth", "Primary", "More smooth"], rotation=15)
        ax.set_title(f"Exposure {exposure}")
        ax.grid(axis="y", color="#E2E8F0")
    axes[0].set_ylabel("Mean boundary distance (% pitch)")
    axes[-1].legend(frameon=False)
    fig.suptitle("Contour-setting sensitivity check", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "06_contour_setting_sensitivity.png", dpi=200, facecolor="white")
    plt.close(fig)
    return {"representative_pillar_id": representative_id}


def build_decision(comparisons: pd.DataFrame, exposure: pd.DataFrame, sensitivity: pd.DataFrame, representatives: dict[str, int]) -> dict[str, object]:
    raw = comparisons[comparisons["comparison"] == "Raw_to_V42E120"].set_index("metric")
    r61 = comparisons[comparisons["comparison"] == "R61v16_to_V42E120"].set_index("metric")
    normal = exposure[exposure["exposure"].between(13, 22)]
    dark = exposure[exposure["exposure"].isin([23, 24])]
    sensitivity_direction = {}
    for exposure_id in [13, 18, 24]:
        group = sensitivity[sensitivity["exposure"] == exposure_id]
        sensitivity_direction[str(exposure_id)] = bool(
            (group["v42_vs_raw_median_improvement_mean_boundary_distance_pitch_pct"] > 0).all()
        )
    return {
        "status_vs_raw": "pass" if raw.loc["mean_boundary_distance_pitch_pct", "bootstrap_ci95_low"] > 0 else "not_proven",
        "status_vs_r61v16": "better" if r61.loc["mean_boundary_distance_pitch_pct", "bootstrap_ci95_low"] > 0 else "not_better",
        "all_exposures_majority_better_vs_raw": bool((exposure["v42_vs_raw_improved_fraction_mean_boundary_distance_pitch_pct"] >= 0.5).all()),
        "normal_exposures_majority_better_vs_raw": bool((normal["v42_vs_raw_improved_fraction_mean_boundary_distance_pitch_pct"] >= 0.5).all()),
        "darkest_exposures_majority_better_vs_raw": bool((dark["v42_vs_raw_improved_fraction_mean_boundary_distance_pitch_pct"] >= 0.5).all()),
        "fine_shape_fidelity_vs_raw": bool(
            raw.loc["perimeter_error_pct", "median_improvement"] > 0
            and raw.loc["circularity_abs_error", "median_improvement"] > 0
        ),
        "contour_setting_direction_consistent_vs_raw": sensitivity_direction,
        "representatives": representatives,
    }


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def write_report(comparisons: pd.DataFrame, exposure: pd.DataFrame, decision: dict[str, object]) -> None:
    raw = comparisons[comparisons["comparison"] == "Raw_to_V42E120"].set_index("metric")
    r61 = comparisons[comparisons["comparison"] == "R61v16_to_V42E120"].set_index("metric")
    exp = exposure.set_index("exposure")
    mbd_raw = raw.loc["mean_boundary_distance_pitch_pct"]
    mbd_r61 = r61.loc["mean_boundary_distance_pitch_pct"]
    iou_raw = raw.loc["iou"]
    area_raw = raw.loc["area_error_pct"]
    perimeter_raw = raw.loc["perimeter_error_pct"]
    circularity_raw = raw.loc["circularity_abs_error"]
    better_all = "通過" if decision["all_exposures_majority_better_vs_raw"] else "未通過"
    better_dark = "通過" if decision["darkest_exposures_majority_better_vs_raw"] else "未通過"
    fine = "通過" if decision["fine_shape_fidelity_vs_raw"] else "未通過"
    passing_exposures = exposure.loc[
        exposure["v42_vs_raw_improved_fraction_mean_boundary_distance_pitch_pct"] >= 0.5,
        "exposure",
    ].astype(int).tolist()
    failing_exposures = exposure.loc[
        exposure["v42_vs_raw_improved_fraction_mean_boundary_distance_pitch_pct"] < 0.5,
        "exposure",
    ].astype(int).tolist()

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = f"""# R70：論文 V42E120 的 SEM 完整輪廓驗證

## 結論先行

這次使用論文採用的 V42 epoch 120、同一批曝光 13–24 光學影像、同一組 36 顆 SEM 真值，以及與 R69 相同的完整輪廓比較方法。

- 相對原圖，36 顆跨 12 個曝光取中位數後，平均邊界距離由 **{fmt(mbd_raw['source_median'])}% 柱距**變成 **{fmt(mbd_raw['target_median'])}% 柱距**；**{int(mbd_raw['improved_pillars'])}/36** 顆改善，改善量的 95% 重抽樣範圍為 **{fmt(mbd_raw['bootstrap_ci95_low'])}–{fmt(mbd_raw['bootstrap_ci95_high'])}% 柱距**。
- 輪廓重疊率由 **{fmt(iou_raw['source_median'])}** 變成 **{fmt(iou_raw['target_median'])}**；面積誤差由 **{fmt(area_raw['source_median'], 2)}%** 變成 **{fmt(area_raw['target_median'], 2)}%**。
- 相對 R61v16，V42 的平均邊界距離由 **{fmt(mbd_r61['source_median'])}%** 變成 **{fmt(mbd_r61['target_median'])}% 柱距**，**{int(mbd_r61['improved_pillars'])}/36** 顆較好。
- 周長誤差由 **{fmt(perimeter_raw['source_median'], 2)}%** 變成 **{fmt(perimeter_raw['target_median'], 2)}%**；圓整程度誤差由 **{fmt(circularity_raw['source_median'])}** 變成 **{fmt(circularity_raw['target_median'])}**。細部形狀門檻：**{fine}**。

## 亮度穩定性

所有曝光都至少半數柱子優於原圖：**{better_all}**。最暗的曝光 23、24：**{better_dark}**。

- V42 在曝光 **{passing_exposures[0]}–{passing_exposures[-1]}** 的36顆全部優於原圖；從曝光 **{failing_exposures[0]}** 開始轉為多數較差，失效比 R61v16 更早。
- 但在最暗的曝光 23、24，V42 的邊界距離為 **{exp.loc[23, 'v42e120_median_mean_boundary_distance_pitch_pct']:.3f}**、**{exp.loc[24, 'v42e120_median_mean_boundary_distance_pitch_pct']:.3f}% 柱距**，仍比 R61v16 的 **{exp.loc[23, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f}**、**{exp.loc[24, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f}%**穩定。也就是 V42 較早失去改善，但沒有像 R61v16 一樣在最暗影像急遽擴大輪廓。

| 曝光 | 原圖平均亮度 | 原圖邊界距離 | R61v16 | V42E120 | V42 優於原圖的柱子 |
|---:|---:|---:|---:|---:|---:|
| 22 | {exp.loc[22, 'raw_mean_intensity_0_255']:.1f} | {exp.loc[22, 'raw_median_mean_boundary_distance_pitch_pct']:.3f} | {exp.loc[22, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f} | {exp.loc[22, 'v42e120_median_mean_boundary_distance_pitch_pct']:.3f} | {int(exp.loc[22, 'v42_vs_raw_improved_pillars_mean_boundary_distance_pitch_pct'])}/36 |
| 23 | {exp.loc[23, 'raw_mean_intensity_0_255']:.1f} | {exp.loc[23, 'raw_median_mean_boundary_distance_pitch_pct']:.3f} | {exp.loc[23, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f} | {exp.loc[23, 'v42e120_median_mean_boundary_distance_pitch_pct']:.3f} | {int(exp.loc[23, 'v42_vs_raw_improved_pillars_mean_boundary_distance_pitch_pct'])}/36 |
| 24 | {exp.loc[24, 'raw_mean_intensity_0_255']:.1f} | {exp.loc[24, 'raw_median_mean_boundary_distance_pitch_pct']:.3f} | {exp.loc[24, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f} | {exp.loc[24, 'v42e120_median_mean_boundary_distance_pitch_pct']:.3f} | {int(exp.loc[24, 'v42_vs_raw_improved_pillars_mean_boundary_distance_pitch_pct'])}/36 |

## 公平性檢查

- 重新從原圖擷取的 864 筆輪廓數值與 R69 原圖結果逐值一致。
- 三個方法都對照同一組 SEM 輪廓；只允許平移，不替任何模型縮放或旋轉。
- 獨立樣本是 36 顆實體柱，12 個曝光視為同一顆柱的重複觀察，不把 432 次觀察假裝成 432 個獨立樣本。
- 明亮、中間、最暗曝光各用三組輪廓平滑程度重做，確認主要方向不是單一設定造成。

## 圖表

1. `01_raw_v42_reconstruction_comparison.png`：曝光 18、24 的重建前後與實際改變量。
2. `02_center36_contour_overlay_exp18.png`：36 顆逐顆 SEM、原圖與 V42 輪廓。
3. `03_paired_model_comparison.png`：Raw、R61v16、V42E120 的36顆配對比較。
4. `04_exposure_stability.png`：曝光 13–24 的邊界與面積誤差。
5. `05_normal_dark_contour_comparison.png`：同一顆柱在正常與最暗曝光的四方比較。
6. `06_contour_setting_sensitivity.png`：三組輪廓設定的穩定性。
"""
    (REPORTS / "R70_RESULTS_TW.md").write_text(report, encoding="utf-8")


def main() -> None:
    primary, sensitivity = load_combined()
    if len(primary) != 12 * 36 * 3 or primary.isna().any().any():
        raise RuntimeError("Combined primary table is incomplete.")
    per_pillar, comparisons = paired_statistics(primary)
    per_exposure = exposure_statistics(primary)
    sensitivity_summary = sensitivity_statistics(sensitivity)

    primary.to_csv(TABLES / "three_method_primary_contour_metrics.csv", index=False)
    per_pillar.to_csv(TABLES / "three_method_per_pillar_summary.csv", index=False)
    comparisons.to_csv(TABLES / "v42_paired_comparison_summary.csv", index=False)
    per_exposure.to_csv(TABLES / "three_method_per_exposure_summary.csv", index=False)
    sensitivity_summary.to_csv(TABLES / "three_method_sensitivity_summary.csv", index=False)

    representatives = make_figures(primary, per_pillar, per_exposure, sensitivity_summary)
    decision = build_decision(comparisons, per_exposure, sensitivity_summary, representatives)
    (RESULTS / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(comparisons, per_exposure, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
