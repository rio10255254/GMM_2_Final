from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat
from scipy.ndimage import center_of_mass
from scipy.stats import wilcoxon
from skimage.measure import find_contours


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
MASKS = RESULTS / "masks"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"
INPUTS = ROOT / "inputs" / "sem_paired_50x_exposure_stack"

RAW_COLOR = "#D97706"
R61_COLOR = "#2563EB"
TRUTH_COLOR = "#111827"
GRID_COLOR = "#CBD5E1"
TEXT_COLOR = "#111827"
PALE_DARK = "#FEF3C7"
SEED = 20260729

METRICS = {
    "iou": ("IoU", "higher", "Overlap (higher is better)"),
    "dice": ("Dice", "higher", "Dice overlap (higher is better)"),
    "mean_boundary_distance_pitch_pct": (
        "Mean boundary distance",
        "lower",
        "Mean boundary distance (% of pillar pitch; lower is better)",
    ),
    "hd95_pitch_pct": (
        "95th-percentile boundary distance",
        "lower",
        "Boundary HD95 (% of pillar pitch; lower is better)",
    ),
    "area_error_pct": ("Area error", "lower", "Absolute area error (%; lower is better)"),
    "perimeter_error_pct": (
        "Perimeter error",
        "lower",
        "Absolute perimeter error (%; lower is better)",
    ),
    "circularity_abs_error": (
        "Circularity error",
        "lower",
        "Absolute circularity error (lower is better)",
    ),
}


def improvement(raw: np.ndarray, r61: np.ndarray, direction: str) -> np.ndarray:
    return r61 - raw if direction == "higher" else raw - r61


def bootstrap_median_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    indices = rng.integers(0, len(values), size=(20_000, len(values)))
    medians = np.median(values[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def holm_adjust(p_values: list[float]) -> list[float]:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    adjusted = np.empty_like(values)
    running = 0.0
    count = len(values)
    for rank, index in enumerate(order):
        candidate = (count - rank) * values[index]
        running = max(running, candidate)
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def paired_statistics(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    medians = primary.groupby(["pillar_id", "method"])[list(METRICS)].median().unstack("method")
    summary_rows: list[dict[str, object]] = []
    pillar_rows: list[dict[str, object]] = []

    mapping = (
        primary[["pillar_id", "grid_row", "grid_col", "truth_circularity"]]
        .drop_duplicates("pillar_id")
        .set_index("pillar_id")
    )
    for pillar_id in sorted(primary["pillar_id"].unique()):
        row: dict[str, object] = {
            "pillar_id": int(pillar_id),
            "grid_row": int(mapping.loc[pillar_id, "grid_row"]),
            "grid_col": int(mapping.loc[pillar_id, "grid_col"]),
            "truth_circularity": float(mapping.loc[pillar_id, "truth_circularity"]),
        }
        for metric, (_, direction, _) in METRICS.items():
            raw = float(medians.loc[pillar_id, (metric, "Raw")])
            r61 = float(medians.loc[pillar_id, (metric, "R61v16")])
            delta = float(improvement(np.array([raw]), np.array([r61]), direction)[0])
            row[f"raw_{metric}"] = raw
            row[f"r61v16_{metric}"] = r61
            row[f"improvement_{metric}"] = delta
        pillar_rows.append(row)

    for metric, (label, direction, _) in METRICS.items():
        raw = medians[(metric, "Raw")].to_numpy(dtype=float)
        r61 = medians[(metric, "R61v16")].to_numpy(dtype=float)
        delta = improvement(raw, r61, direction)
        ci_low, ci_high = bootstrap_median_ci(delta, rng)
        try:
            _, p_value = wilcoxon(r61, raw, alternative="two-sided", zero_method="wilcox")
        except ValueError:
            p_value = 1.0
        summary_rows.append(
            {
                "metric": metric,
                "label": label,
                "better_direction": direction,
                "independent_pillar_count": len(raw),
                "raw_median": float(np.median(raw)),
                "r61v16_median": float(np.median(r61)),
                "median_improvement": float(np.median(delta)),
                "bootstrap_ci95_low": ci_low,
                "bootstrap_ci95_high": ci_high,
                "improved_pillar_count": int(np.count_nonzero(delta > 0)),
                "unchanged_pillar_count": int(np.count_nonzero(delta == 0)),
                "worsened_pillar_count": int(np.count_nonzero(delta < 0)),
                "improved_fraction": float(np.mean(delta > 0)),
                "wilcoxon_p_two_sided": float(p_value),
            }
        )

    summary = pd.DataFrame(summary_rows)
    summary["wilcoxon_p_holm"] = holm_adjust(summary["wilcoxon_p_two_sided"].tolist())
    return pd.DataFrame(pillar_rows), summary


def exposure_statistics(primary: pd.DataFrame) -> pd.DataFrame:
    brightness = {}
    for exposure in sorted(primary["exposure"].unique()):
        image = np.asarray(Image.open(INPUTS / f"{exposure}.bmp").convert("L"), dtype=float)
        brightness[int(exposure)] = float(image.mean())

    rows: list[dict[str, object]] = []
    for exposure, group in primary.groupby("exposure", sort=True):
        row: dict[str, object] = {
            "exposure": int(exposure),
            "raw_mean_intensity_0_255": brightness[int(exposure)],
        }
        for metric, (_, direction, _) in METRICS.items():
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            delta = improvement(
                pivot["Raw"].to_numpy(dtype=float),
                pivot["R61v16"].to_numpy(dtype=float),
                direction,
            )
            row[f"raw_median_{metric}"] = float(pivot["Raw"].median())
            row[f"r61v16_median_{metric}"] = float(pivot["R61v16"].median())
            row[f"median_improvement_{metric}"] = float(np.median(delta))
            row[f"improved_count_{metric}"] = int(np.count_nonzero(delta > 0))
            row[f"improved_fraction_{metric}"] = float(np.mean(delta > 0))
        rows.append(row)
    return pd.DataFrame(rows)


def sensitivity_statistics(sensitivity: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (preset, exposure), group in sensitivity.groupby(["preset", "exposure"], sort=False):
        row: dict[str, object] = {"preset": preset, "exposure": int(exposure)}
        for metric in ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]:
            direction = METRICS[metric][1]
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            delta = improvement(
                pivot["Raw"].to_numpy(dtype=float),
                pivot["R61v16"].to_numpy(dtype=float),
                direction,
            )
            row[f"raw_median_{metric}"] = float(pivot["Raw"].median())
            row[f"r61v16_median_{metric}"] = float(pivot["R61v16"].median())
            row[f"median_improvement_{metric}"] = float(np.median(delta))
            row[f"improved_count_{metric}"] = int(np.count_nonzero(delta > 0))
        rows.append(row)
    return pd.DataFrame(rows)


def matlab_round(value: np.ndarray) -> np.ndarray:
    return np.where(value >= 0, np.floor(value + 0.5), np.ceil(value - 0.5)).astype(int)


def shift_binary(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask, dtype=bool)
    src_x1 = max(0, -dx)
    src_x2 = min(width, width - dx)
    src_y1 = max(0, -dy)
    src_y2 = min(height, height - dy)
    if src_x1 < src_x2 and src_y1 < src_y2:
        shifted[src_y1 + dy : src_y2 + dy, src_x1 + dx : src_x2 + dx] = mask[
            src_y1:src_y2, src_x1:src_x2
        ]
    return shifted


def align_to_truth(predicted: np.ndarray, truth: np.ndarray) -> np.ndarray:
    truth_center = np.asarray(center_of_mass(truth), dtype=float)
    pred_center = np.asarray(center_of_mass(predicted), dtype=float)
    dy, dx = matlab_round(truth_center - pred_center)
    return shift_binary(predicted, int(dy), int(dx))


def draw_contour(ax: plt.Axes, mask: np.ndarray, color: str, linewidth: float = 1.4, linestyle: str = "-") -> None:
    for contour in find_contours(mask.astype(float), 0.5):
        ax.plot(contour[:, 1], contour[:, 0], color=color, linewidth=linewidth, linestyle=linestyle)


def style_image_axis(ax: plt.Axes, side: int) -> None:
    ax.set_xlim(7, side - 8)
    ax.set_ylim(side - 8, 7)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def make_figures(primary: pd.DataFrame, per_pillar: pd.DataFrame, per_exposure: pd.DataFrame, sensitivity_summary: pd.DataFrame) -> dict[str, int]:
    data = loadmat(
        MASKS / "acm_primary_masks.mat",
        squeeze_me=True,
        variable_names=[
            "truth_cells",
            "truth_masks",
            "raw_cells",
            "raw_masks",
            "recon_cells",
            "recon_masks",
            "exposures",
            "global_index",
        ],
    )
    truth_cells = data["truth_cells"]
    truth_masks = data["truth_masks"].astype(bool)
    raw_cells = data["raw_cells"]
    raw_masks = data["raw_masks"].astype(bool)
    recon_cells = data["recon_cells"]
    recon_masks = data["recon_masks"].astype(bool)
    exposures = np.asarray(data["exposures"]).astype(int).ravel()
    global_index = np.asarray(data["global_index"]).astype(int)
    side = truth_cells.shape[0]

    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.edgecolor": GRID_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "text.color": TEXT_COLOR,
            "xtick.color": "#475569",
            "ytick.color": "#475569",
        }
    )

    mbd_col = "improvement_mean_boundary_distance_pitch_pct"
    representative_id = int(
        per_pillar.iloc[(per_pillar[mbd_col] - per_pillar[mbd_col].median()).abs().argmin()]["pillar_id"]
    )
    representative_exposure = 18
    exposure_index = int(np.where(exposures == representative_exposure)[0][0])
    pillar_index = representative_id - 1
    truth = truth_masks[:, :, pillar_index]
    raw = raw_masks[:, :, pillar_index, exposure_index]
    r61 = recon_masks[:, :, pillar_index, exposure_index]
    aligned_raw = align_to_truth(raw, truth)
    aligned_r61 = align_to_truth(r61, truth)

    fig = plt.figure(figsize=(12, 8), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1, 1.15])
    top = [
        (truth_cells[:, :, pillar_index], truth, TRUTH_COLOR, "SEM truth"),
        (raw_cells[:, :, pillar_index, exposure_index], raw, RAW_COLOR, "Raw optical"),
        (recon_cells[:, :, pillar_index, exposure_index], r61, R61_COLOR, "R61v16 reconstruction"),
    ]
    for col, (image, mask, color, title) in enumerate(top):
        ax = fig.add_subplot(grid[0, col])
        ax.imshow(image, cmap="gray", vmin=0, vmax=255)
        draw_contour(ax, mask, color, 2.0)
        ax.set_title(title, fontsize=12, fontweight="bold")
        style_image_axis(ax, side)
    ax = fig.add_subplot(grid[1, :])
    ax.imshow(truth_cells[:, :, pillar_index], cmap="gray", vmin=0, vmax=255)
    draw_contour(ax, truth, TRUTH_COLOR, 2.2)
    draw_contour(ax, aligned_raw, RAW_COLOR, 1.9, "--")
    draw_contour(ax, aligned_r61, R61_COLOR, 1.9)
    ax.set_title("Shape-only overlay on SEM (translation alignment only)", fontsize=12, fontweight="bold")
    style_image_axis(ax, side)
    ax.legend(
        handles=[
            Line2D([0], [0], color=TRUTH_COLOR, lw=2.2, label="SEM"),
            Line2D([0], [0], color=RAW_COLOR, lw=1.9, ls="--", label="Raw"),
            Line2D([0], [0], color=R61_COLOR, lw=1.9, label="R61v16"),
        ],
        loc="lower right",
        frameon=True,
    )
    fig.suptitle(
        f"ACM contour validation — pillar {representative_id}, exposure {representative_exposure}\n"
        "Deterministic representative: pillar nearest the median overall improvement",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "01_acm_method_overview.png", dpi=200, facecolor="white")
    plt.close(fig)

    overlay_exposure = 18
    overlay_index = int(np.where(exposures == overlay_exposure)[0][0])
    fig, axes = plt.subplots(6, 6, figsize=(14, 14), constrained_layout=True)
    for row in range(6):
        for col in range(6):
            pillar_id = int(global_index[row, col])
            index = pillar_id - 1
            truth = truth_masks[:, :, index]
            raw = align_to_truth(raw_masks[:, :, index, overlay_index], truth)
            r61 = align_to_truth(recon_masks[:, :, index, overlay_index], truth)
            ax = axes[row, col]
            ax.imshow(truth_cells[:, :, index], cmap="gray", vmin=0, vmax=255)
            draw_contour(ax, truth, TRUTH_COLOR, 1.35)
            draw_contour(ax, raw, RAW_COLOR, 1.05, "--")
            draw_contour(ax, r61, R61_COLOR, 1.05)
            ax.set_title(f"ID {pillar_id}", fontsize=8, fontweight="bold")
            style_image_axis(ax, side)
    fig.suptitle(
        f"Center-36 SEM contour overlay — exposure {overlay_exposure}\n"
        "Black: SEM · orange dashed: Raw · blue: R61v16; translation only",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "02_center36_contour_overlay_exp18.png", dpi=190, facecolor="white")
    plt.close(fig)

    panel_metrics = ["iou", "mean_boundary_distance_pitch_pct", "area_error_pct", "perimeter_error_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for ax, metric in zip(axes.ravel(), panel_metrics):
        _, _, ylabel = METRICS[metric]
        raw_values = per_pillar[f"raw_{metric}"].to_numpy()
        r61_values = per_pillar[f"r61v16_{metric}"].to_numpy()
        for raw_value, r61_value in zip(raw_values, r61_values):
            ax.plot([0, 1], [raw_value, r61_value], color="#CBD5E1", lw=0.8, zorder=1)
        ax.scatter(np.zeros_like(raw_values), raw_values, color=RAW_COLOR, s=28, alpha=0.85, zorder=2)
        ax.scatter(np.ones_like(r61_values), r61_values, color=R61_COLOR, s=28, alpha=0.85, zorder=2)
        ax.plot([0, 1], [np.median(raw_values), np.median(r61_values)], color=TRUTH_COLOR, lw=2.3, zorder=3)
        ax.set_xticks([0, 1], ["Raw", "R61v16"])
        ax.set_xlim(-0.35, 1.35)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", color="#E2E8F0", lw=0.8)
        ax.grid(axis="x", visible=False)
        ax.set_title(METRICS[metric][0], fontweight="bold")
        ax.text(
            0.02,
            0.98,
            f"median: {np.median(raw_values):.3f} → {np.median(r61_values):.3f}",
            transform=ax.transAxes,
            va="top",
            fontsize=9,
        )
    fig.suptitle(
        "Paired contour accuracy across 36 physical pillars\nEach point is the pillar median across 12 exposures",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "03_paired_metric_comparison.png", dpi=200, facecolor="white")
    plt.close(fig)

    x = per_exposure["exposure"].to_numpy()
    raw_y = per_exposure["raw_median_mean_boundary_distance_pitch_pct"].to_numpy()
    r61_y = per_exposure["r61v16_median_mean_boundary_distance_pitch_pct"].to_numpy()
    fraction = per_exposure["improved_fraction_mean_boundary_distance_pitch_pct"].to_numpy()
    intensity = per_exposure["raw_mean_intensity_0_255"].to_numpy()
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]}, constrained_layout=True)
    for ax in axes:
        ax.axvspan(22.5, 24.5, color=PALE_DARK, alpha=0.75, zorder=0)
        ax.grid(axis="y", color="#E2E8F0", lw=0.8)
    axes[0].plot(x, raw_y, color=RAW_COLOR, marker="o", lw=2.0, label="Raw")
    axes[0].plot(x, r61_y, color=R61_COLOR, marker="o", lw=2.0, label="R61v16")
    axes[0].set_ylabel("Median boundary distance (% pitch)")
    axes[0].legend(frameon=False, ncol=2)
    axes[0].set_title("Boundary accuracy by exposure", fontweight="bold")
    bar_colors = [R61_COLOR if value >= 0.5 else RAW_COLOR for value in fraction]
    axes[1].bar(x, 100 * fraction, color=bar_colors, width=0.68)
    for exposure_value, fraction_value in zip(x, fraction):
        if fraction_value < 0.05:
            axes[1].text(exposure_value, 3, "0%", ha="center", va="bottom", color=RAW_COLOR, fontweight="bold")
    axes[1].axhline(50, color="#64748B", ls="--", lw=1)
    axes[1].set_ylabel("Pillars improved (%)")
    axes[1].set_ylim(0, 105)
    axes[1].set_xticks(x, [f"{e}\n{b:.0f}" for e, b in zip(x, intensity)])
    axes[1].set_xlabel("Exposure image number / raw mean intensity (0–255)")
    axes[1].text(23.5, 99, "darkest", ha="center", va="top", fontsize=9)
    fig.suptitle(
        "R61v16 contour accuracy is exposure-dependent",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(FIGURES / "04_exposure_stability.png", dpi=200, facecolor="white")
    plt.close(fig)

    normal = primary[primary["exposure"].between(13, 22)]
    dark = primary[primary["exposure"].between(23, 24)]

    def pillar_improvement_for(group: pd.DataFrame) -> pd.Series:
        pivot = group.pivot_table(
            index="pillar_id",
            columns="method",
            values="mean_boundary_distance_pitch_pct",
            aggfunc="median",
        )
        return pivot["Raw"] - pivot["R61v16"]

    map_values = [pillar_improvement_for(normal), pillar_improvement_for(dark)]
    max_abs = max(float(np.abs(values).max()) for values in map_values)
    cmap = LinearSegmentedColormap.from_list("orange_white_blue", [RAW_COLOR, "#FFFFFF", R61_COLOR])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
    for ax, values, title in zip(
        axes,
        map_values,
        ["Exposures 13–22", "Darkest exposures 23–24"],
    ):
        matrix = np.zeros((6, 6), dtype=float)
        for row in range(6):
            for col in range(6):
                pillar_id = int(global_index[row, col])
                matrix[row, col] = values.loc[pillar_id]
        image = ax.imshow(matrix, cmap=cmap, vmin=-max_abs, vmax=max_abs)
        for row in range(6):
            for col in range(6):
                pillar_id = int(global_index[row, col])
                value = matrix[row, col]
                ax.text(col, row, f"ID {pillar_id}\n{value:+.3f}", ha="center", va="center", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontweight="bold")
    colorbar = fig.colorbar(image, ax=axes, shrink=0.85, pad=0.02)
    colorbar.set_label("Raw − R61 mean boundary distance (% pitch); blue = R61 better")
    fig.suptitle("Pillar-by-pillar contour improvement changes in the darkest images", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "05_pillar_improvement_maps.png", dpi=200, facecolor="white")
    plt.close(fig)

    preset_order = ["less_smooth", "primary", "more_smooth"]
    preset_labels = ["Less smooth", "Primary", "More smooth"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), sharey=True, constrained_layout=True)
    for ax, exposure in zip(axes, [13, 18, 24]):
        subset = sensitivity_summary[sensitivity_summary["exposure"] == exposure].set_index("preset").loc[preset_order]
        ax.plot(
            range(3),
            subset["raw_median_mean_boundary_distance_pitch_pct"],
            color=RAW_COLOR,
            marker="o",
            lw=2,
            label="Raw",
        )
        ax.plot(
            range(3),
            subset["r61v16_median_mean_boundary_distance_pitch_pct"],
            color=R61_COLOR,
            marker="o",
            lw=2,
            label="R61v16",
        )
        ax.set_xticks(range(3), preset_labels, rotation=15)
        ax.set_title(f"Exposure {exposure}", fontweight="bold")
        ax.grid(axis="y", color="#E2E8F0", lw=0.8)
    axes[0].set_ylabel("Median boundary distance (% pitch)")
    axes[-1].legend(frameon=False)
    fig.suptitle("ACM-setting sensitivity audit", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "06_acm_sensitivity.png", dpi=200, facecolor="white")
    plt.close(fig)

    shape = per_pillar.sort_values("truth_circularity")
    selected_ids = [
        int(shape.iloc[0]["pillar_id"]),
        int(shape.iloc[(shape["truth_circularity"] - shape["truth_circularity"].median()).abs().argmin()]["pillar_id"]),
        int(shape.iloc[-1]["pillar_id"]),
    ]
    fig = plt.figure(figsize=(12, 7), constrained_layout=True)
    grid = fig.add_gridspec(2, 3, height_ratios=[1.25, 0.9])
    labels = ["Least circular", "Nearest median", "Most circular"]
    for col, (pillar_id, label) in enumerate(zip(selected_ids, labels)):
        ax = fig.add_subplot(grid[0, col])
        index = pillar_id - 1
        ax.imshow(truth_cells[:, :, index], cmap="gray", vmin=0, vmax=255)
        draw_contour(ax, truth_masks[:, :, index], TRUTH_COLOR, 2)
        value = float(per_pillar.set_index("pillar_id").loc[pillar_id, "truth_circularity"])
        ax.set_title(f"{label}: ID {pillar_id}\nCircularity {value:.3f}", fontweight="bold")
        style_image_axis(ax, side)
    ax = fig.add_subplot(grid[1, :])
    sorted_values = shape["truth_circularity"].to_numpy()
    ax.scatter(range(1, 37), sorted_values, color=TRUTH_COLOR, s=32)
    ax.axhline(1.0, color="#64748B", ls="--", lw=1, label="Perfect circle = 1")
    ax.axhline(np.median(sorted_values), color=R61_COLOR, ls=":", lw=1.5, label=f"Median = {np.median(sorted_values):.3f}")
    ax.set_xlim(0, 37)
    ax.set_ylim(min(0.90, sorted_values.min() - 0.01), 1.01)
    ax.set_xlabel("36 SEM pillars sorted by circularity")
    ax.set_ylabel("Circularity")
    ax.grid(axis="y", color="#E2E8F0", lw=0.8)
    ax.legend(frameon=False, ncol=2)
    fig.suptitle("SEM pillars are close to round, but not perfect circles", fontsize=15, fontweight="bold")
    fig.savefig(FIGURES / "07_sem_shape_spectrum.png", dpi=200, facecolor="white")
    plt.close(fig)

    return {
        "representative_pillar_id": representative_id,
        "representative_exposure": representative_exposure,
        "least_circular_pillar_id": selected_ids[0],
        "median_circularity_pillar_id": selected_ids[1],
        "most_circular_pillar_id": selected_ids[2],
    }


def build_decision(
    paired: pd.DataFrame,
    per_exposure: pd.DataFrame,
    per_pillar: pd.DataFrame,
    sensitivity_summary: pd.DataFrame,
    representatives: dict[str, int],
) -> dict[str, object]:
    metrics = paired.set_index("metric")
    mbd = metrics.loc["mean_boundary_distance_pitch_pct"]
    iou = metrics.loc["iou"]
    perimeter = metrics.loc["perimeter_error_pct"]
    circularity = metrics.loc["circularity_abs_error"]
    exposure_pass = per_exposure.set_index("exposure")["improved_fraction_mean_boundary_distance_pitch_pct"]
    sensitivity_pass = sensitivity_summary.assign(
        r61_better=lambda frame: frame["median_improvement_mean_boundary_distance_pitch_pct"] > 0
    )
    decision = {
        "status": "conditional_pass_not_universal",
        "primary_coarse_contour_gate": bool(
            mbd["improved_fraction"] >= 0.60
            and mbd["bootstrap_ci95_low"] > 0
            and iou["bootstrap_ci95_low"] > 0
        ),
        "all_exposure_universal_gate": bool((exposure_pass >= 0.50).all()),
        "fine_shape_fidelity_gate": bool(
            perimeter["median_improvement"] > 0 and circularity["median_improvement"] > 0
        ),
        "normal_exposure_range_pass": bool((exposure_pass.loc[13:22] >= 0.50).all()),
        "darkest_exposures_pass": bool((exposure_pass.loc[[23, 24]] >= 0.50).all()),
        "acm_sensitivity_direction_consistent": {
            str(exposure): bool(
                sensitivity_pass[sensitivity_pass["exposure"] == exposure]["r61_better"].all()
            )
            for exposure in [13, 18, 24]
        },
        "sem_truth_circularity": {
            "median": float(per_pillar["truth_circularity"].median()),
            "minimum": float(per_pillar["truth_circularity"].min()),
            "maximum": float(per_pillar["truth_circularity"].max()),
        },
        "representatives": representatives,
        "recommended_claim": (
            "R61v16 improves coarse full-contour agreement for exposures 13–22, "
            "but is not universally accurate in the two darkest exposures and does not "
            "reliably preserve fine non-circular edge detail."
        ),
    }
    return decision


def format_p(value: float) -> str:
    return f"{value:.2e}" if value < 0.001 else f"{value:.3f}"


def write_report(
    paired: pd.DataFrame,
    per_exposure: pd.DataFrame,
    per_pillar: pd.DataFrame,
    decision: dict[str, object],
) -> None:
    metrics = paired.set_index("metric")
    mbd = metrics.loc["mean_boundary_distance_pitch_pct"]
    iou = metrics.loc["iou"]
    area = metrics.loc["area_error_pct"]
    perimeter = metrics.loc["perimeter_error_pct"]
    circularity = metrics.loc["circularity_abs_error"]
    exposure = per_exposure.set_index("exposure")
    circ_median = per_pillar["truth_circularity"].median()
    circ_min = per_pillar["truth_circularity"].min()
    circ_max = per_pillar["truth_circularity"].max()

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = f"""# R69：R61v16 的 SEM–ACM 完整輪廓驗證

## 結論先行

R61v16 **能改善一般亮度下的主要外框位置，但不能宣稱在所有場景都準，也還沒有證明能忠實重建細微的不圓整邊緣**。

- 在每顆柱跨 12 個曝光取中位數後，平均邊界距離由原圖的 **{mbd['raw_median']:.3f}% 柱距**降到 **{mbd['r61v16_median']:.3f}% 柱距**；36 顆中 **{int(mbd['improved_pillar_count'])}/36** 顆改善，改善量的 95% 重抽樣範圍為 **{mbd['bootstrap_ci95_low']:.3f}–{mbd['bootstrap_ci95_high']:.3f}% 柱距**，配對檢定校正後 p={format_p(float(mbd['wilcoxon_p_holm']))}。
- 輪廓重疊率由 **{iou['raw_median']:.3f}** 提升到 **{iou['r61v16_median']:.3f}**；面積誤差由 **{area['raw_median']:.2f}%** 降到 **{area['r61v16_median']:.2f}%**。
- 但周長誤差由 **{perimeter['raw_median']:.2f}%** 增加到 **{perimeter['r61v16_median']:.2f}%**，36 顆中只有 **{int(perimeter['improved_pillar_count'])}/36** 顆改善；圓整程度誤差也由 **{circularity['raw_median']:.3f}** 增加到 **{circularity['r61v16_median']:.3f}**。這表示重建影像的粗外框更接近 SEM，但邊緣細節較粗糙，不能把它解讀成真實微小形變已被還原。
- 曝光 13–22 的 36 顆全部都改善；最暗的曝光 23、24 則全部惡化。曝光 23 的中位邊界距離由 **{exposure.loc[23, 'raw_median_mean_boundary_distance_pitch_pct']:.3f}** 變成 **{exposure.loc[23, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f}% 柱距**，曝光 24 由 **{exposure.loc[24, 'raw_median_mean_boundary_distance_pitch_pct']:.3f}** 變成 **{exposure.loc[24, 'r61v16_median_mean_boundary_distance_pitch_pct']:.3f}% 柱距**。

因此，本次判定是：**有條件通過，不是全場景通過**。

## 教授對「樣品不圓」的質疑怎麼看

SEM 的 36 顆柱圓整程度中位數為 **{circ_median:.3f}**，範圍 **{circ_min:.3f}–{circ_max:.3f}**；1 才是完美圓。也就是說，教授說「不是完美圓」在嚴格意義上是對的，但這批柱仍然相當接近圓。

所以不需要把過去的 CD 全部推翻：

- **CD 繼續回答尺寸有沒有變大或變小。** 對接近圓的柱體仍然有意義。
- **ACM 完整輪廓回答外形是否貼近 SEM。** 它能補上 CD 看不到的局部扁平、凹凸或不對稱。
- 論文最穩妥的寫法是把兩者並列：CD 作尺寸主指標，平均邊界距離與輪廓重疊率作形狀驗證；目前不要用周長或細微不圓整宣稱模型已恢復真實邊緣細節。

## 這次實際比較的是什麼

主要驗證使用舊有紀錄中能和 P-01 到 P-09 SEM 逐顆對上的 12 張光學曝光影像，對應中心 36 顆柱。舊資料夾沒有留下可直接查證的倍率標籤，因此本報告不替它補寫成 50 倍；它的關鍵價值是逐顆 SEM 身分可被舊程式直接證明。這 12 張原圖重新以凍結的 R61v16、與近期 50 倍測試相同的關閉 PSF 設定完成重建。

每一顆都用主動輪廓找完整外框，再把光學輪廓只做平移後疊到對應 SEM；**沒有替每顆縮放、旋轉，也沒有套圓或半徑**。主要比較輪廓重疊、平均邊界距離、最差一段邊界距離、面積、周長與圓整程度。

2026 年近期的 50 倍位移影像雖然是真實拍攝、也可用來做外部泛化觀察，但目前沒有證據證明它和這 36 顆 SEM 是同一片樣品、同一顆柱，因此沒有拿它冒充逐顆 SEM 真值。

## 穩定性檢查

ACM 使用三種不同的平滑程度，分別重做明亮曝光 13、中間曝光 18、最暗曝光 24。三種設定都得到相同方向：13、18 是 R61v16 較好，24 是 R61v16 較差。這表示「正常曝光改善、極暗曝光失敗」不是單一輪廓參數偶然造成的。

## 論文可用的判斷

| 問題 | 判定 | 可寫的結論 |
|---|---:|---|
| 一般曝光的主要外框是否更準 | 通過 | 曝光 13–22 的平均邊界距離與重疊率改善 |
| 所有曝光是否都更準 | 不通過 | 曝光 23–24 明顯惡化，不能宣稱全場景 |
| 細微不圓整邊緣是否忠實恢復 | 不通過 | 周長與圓整程度誤差增加 |
| CD 是否應完全取消 | 不建議 | 保留 CD 看尺寸，新增 ACM 看完整形狀 |

## 圖表索引

1. `01_acm_method_overview.png`：單顆 SEM／原圖／重建圖及疊圖方法。
2. `02_center36_contour_overlay_exp18.png`：36 顆逐顆輪廓疊圖。
3. `03_paired_metric_comparison.png`：36 顆配對後的總體結果。
4. `04_exposure_stability.png`：從明到暗的失效轉折。
5. `05_pillar_improvement_maps.png`：正常曝光和最暗曝光的逐顆差異。
6. `06_acm_sensitivity.png`：三種輪廓設定的穩定性。
7. `07_sem_shape_spectrum.png`：SEM 形狀由最不圓到最接近圓的分布。

## 限制與下一步

這是同一批中心 36 顆柱在 12 個曝光下的重複觀察，獨立樣本數是 36，不是 432。要支持「任何樣品、任何位置都能用」，下一步仍需新增一批可逐顆對應的獨立 SEM／50 倍光學樣品，並特別補強目前失敗的極暗曝光。建議把曝光 23–24 先列為不可信區，或建立低亮度拒收條件，再決定是否重訓。
"""
    (REPORTS / "R69_RESULTS_TW.md").write_text(report, encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")

    expected_primary = 12 * 36 * 2
    expected_sensitivity = 3 * 3 * 36 * 2
    if len(primary) != expected_primary or len(sensitivity) != expected_sensitivity:
        raise RuntimeError(
            f"Unexpected row counts: primary={len(primary)}, sensitivity={len(sensitivity)}"
        )
    if primary.isna().any().any() or sensitivity.isna().any().any():
        raise RuntimeError("ACM metric tables contain missing values.")
    if not primary["truth_circularity"].between(0, 1).all():
        raise RuntimeError("Circularity must stay in the physical 0-to-1 range.")

    per_pillar, paired = paired_statistics(primary)
    per_exposure = exposure_statistics(primary)
    sensitivity_summary = sensitivity_statistics(sensitivity)

    per_pillar.to_csv(TABLES / "per_pillar_summary.csv", index=False)
    paired.to_csv(TABLES / "paired_metric_summary.csv", index=False)
    per_exposure.to_csv(TABLES / "per_exposure_summary.csv", index=False)
    sensitivity_summary.to_csv(TABLES / "acm_sensitivity_summary.csv", index=False)

    representatives = make_figures(primary, per_pillar, per_exposure, sensitivity_summary)
    decision = build_decision(paired, per_exposure, per_pillar, sensitivity_summary, representatives)
    (RESULTS / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(paired, per_exposure, per_pillar, decision)

    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
