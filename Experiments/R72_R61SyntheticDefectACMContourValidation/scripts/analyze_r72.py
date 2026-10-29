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
from scipy.stats import spearmanr, wilcoxon
from skimage.measure import find_contours
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
MASKS = RESULTS / "masks"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"
SEED = int(CONFIG["statistics"]["random_seed"])

RAW_COLOR = "#D97706"
COMBO_COLOR = "#C49A2C"
R61_COLOR = "#2563EB"
TRUTH_COLOR = "#F8FAFC"
INK = "#111827"
GRID = "#CBD5E1"
PALE_BLUE = "#BFDBFE"
PALE_ORANGE = "#FED7AA"

METHODS = ["Raw", "COMBO", "R61v16"]
METHOD_COLORS = {"Raw": RAW_COLOR, "COMBO": COMBO_COLOR, "R61v16": R61_COLOR}
METRICS = {
    "iou": ("輪廓重疊率", "higher", "IoU（越高越好）"),
    "dice": ("Dice 重疊率", "higher", "Dice（越高越好）"),
    "mean_boundary_distance_px": ("平均邊界距離", "lower", "平均邊界距離（px，越低越好）"),
    "hd95_px": ("最差 5% 邊界距離", "lower", "HD95（px，越低越好）"),
    "area_error_pct": ("面積誤差", "lower", "面積絕對誤差（%，越低越好）"),
    "perimeter_error_pct": ("周長誤差", "lower", "周長絕對誤差（%，越低越好）"),
    "circularity_abs_error": ("圓整程度誤差", "lower", "圓整程度絕對誤差（越低越好）"),
}


def chart_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft JhengHei", "Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": INK,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "grid.color": GRID,
            "grid.alpha": 0.55,
        }
    )


def metric_improvement(base: np.ndarray, target: np.ndarray, direction: str) -> np.ndarray:
    return target - base if direction == "higher" else base - target


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


def validate_inputs(primary: pd.DataFrame, sensitivity: pd.DataFrame) -> None:
    required = {"image_id", "method", "alignment", *METRICS}
    missing = sorted(required - set(primary.columns))
    if missing:
        raise ValueError(f"Primary ACM table is missing columns: {missing}")
    expected_ids = set(CONFIG["sources"]["image_ids"])
    if set(primary["image_id"].astype(int)) != expected_ids:
        raise ValueError("Primary ACM image IDs do not match the frozen set.")
    counts = primary.groupby(["alignment", "method"])["image_id"].nunique()
    for alignment in ("translation_only", "fixed_pixel_coordinates"):
        for method in METHODS:
            if int(counts.get((alignment, method), 0)) != 20:
                raise ValueError(f"Incomplete primary cell: {alignment}, {method}")
    numeric = primary[list(METRICS)].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Primary ACM metrics contain non-finite values.")
    expected_sensitivity = len(CONFIG["acm"]["sensitivity_image_ids"])
    sensitivity_counts = sensitivity.groupby(["preset", "method"])["image_id"].nunique()
    for preset in [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]:
        for method in METHODS:
            if int(sensitivity_counts.get((preset, method), 0)) != expected_sensitivity:
                raise ValueError(f"Incomplete sensitivity cell: {preset}, {method}")


def paired_summaries(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    comparisons = [
        ("r61_vs_raw", "Raw", "R61v16"),
        ("r61_vs_combo", "COMBO", "R61v16"),
    ]
    summary_rows: list[dict[str, object]] = []
    image_rows: list[dict[str, object]] = []
    for alignment in ("translation_only", "fixed_pixel_coordinates"):
        aligned = primary.loc[primary["alignment"] == alignment]
        pivots = {metric: aligned.pivot(index="image_id", columns="method", values=metric) for metric in METRICS}
        for image_id in sorted(aligned["image_id"].unique()):
            row: dict[str, object] = {"image_id": int(image_id), "alignment": alignment}
            for metric, (_, direction, _) in METRICS.items():
                pivot = pivots[metric]
                for method in METHODS:
                    row[f"{method.lower()}_{metric}"] = float(pivot.loc[image_id, method])
                row[f"r61_vs_raw_improvement_{metric}"] = float(
                    metric_improvement(
                        np.array([pivot.loc[image_id, "Raw"]]),
                        np.array([pivot.loc[image_id, "R61v16"]]),
                        direction,
                    )[0]
                )
            image_rows.append(row)

        for comparison, base_method, target_method in comparisons:
            comparison_start = len(summary_rows)
            for metric, (label, direction, _) in METRICS.items():
                pivot = pivots[metric]
                base = pivot[base_method].to_numpy(dtype=float)
                target = pivot[target_method].to_numpy(dtype=float)
                delta = metric_improvement(base, target, direction)
                ci_low, ci_high = bootstrap_median_ci(delta, rng)
                try:
                    _, p_value = wilcoxon(target, base, alternative="two-sided", zero_method="wilcox")
                except ValueError:
                    p_value = 1.0
                summary_rows.append(
                    {
                        "alignment": alignment,
                        "comparison": comparison,
                        "base_method": base_method,
                        "target_method": target_method,
                        "metric": metric,
                        "metric_label": label,
                        "better_direction": direction,
                        "independent_image_count": len(base),
                        "base_median": float(np.median(base)),
                        "target_median": float(np.median(target)),
                        "median_improvement": float(np.median(delta)),
                        "bootstrap_ci95_low": ci_low,
                        "bootstrap_ci95_high": ci_high,
                        "improved_count": int(np.count_nonzero(delta > 0)),
                        "unchanged_count": int(np.count_nonzero(delta == 0)),
                        "worsened_count": int(np.count_nonzero(delta < 0)),
                        "improved_fraction": float(np.mean(delta > 0)),
                        "wilcoxon_p_two_sided": float(p_value),
                    }
                )
            indices = list(range(comparison_start, len(summary_rows)))
            adjusted = holm_adjust([float(summary_rows[index]["wilcoxon_p_two_sided"]) for index in indices])
            for index, p_adjusted in zip(indices, adjusted):
                summary_rows[index]["wilcoxon_p_holm"] = p_adjusted
    return pd.DataFrame(summary_rows), pd.DataFrame(image_rows)


def sensitivity_summary(sensitivity: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for preset, group in sensitivity.groupby("preset", sort=False):
        for comparison, base_method, target_method in (
            ("r61_vs_raw", "Raw", "R61v16"),
            ("r61_vs_combo", "COMBO", "R61v16"),
        ):
            for metric, (label, direction, _) in METRICS.items():
                pivot = group.pivot(index="image_id", columns="method", values=metric)
                base = pivot[base_method].to_numpy(dtype=float)
                target = pivot[target_method].to_numpy(dtype=float)
                delta = metric_improvement(base, target, direction)
                rows.append(
                    {
                        "preset": preset,
                        "comparison": comparison,
                        "metric": metric,
                        "metric_label": label,
                        "image_count": len(delta),
                        "base_median": float(np.median(base)),
                        "target_median": float(np.median(target)),
                        "median_improvement": float(np.median(delta)),
                        "improved_count": int(np.count_nonzero(delta > 0)),
                        "improved_fraction": float(np.mean(delta > 0)),
                    }
                )
    return pd.DataFrame(rows)


def brightness_check(primary: pd.DataFrame, per_image: pd.DataFrame) -> pd.DataFrame:
    translation = primary.loc[primary["alignment"] == "translation_only"]
    raw_brightness = translation.loc[translation["method"] == "Raw", ["image_id", "mean_intensity_0_255", "std_intensity_0_255"]]
    improvement_rows = per_image.loc[per_image["alignment"] == "translation_only"]
    merged = improvement_rows.merge(raw_brightness, on="image_id", validate="one_to_one")
    rows = []
    for brightness_field in ("mean_intensity_0_255", "std_intensity_0_255"):
        for metric in ("iou", "mean_boundary_distance_px"):
            improvement_field = f"r61_vs_raw_improvement_{metric}"
            rho, p_value = spearmanr(merged[brightness_field], merged[improvement_field])
            rows.append(
                {
                    "brightness_field": brightness_field,
                    "contour_metric": metric,
                    "spearman_rho": float(rho),
                    "p_value_two_sided": float(p_value),
                    "image_count": len(merged),
                }
            )
    return pd.DataFrame(rows)


def decide(summary: pd.DataFrame, sensitivity: pd.DataFrame) -> dict[str, object]:
    primary = summary.loc[
        (summary["alignment"] == "translation_only") & (summary["comparison"] == "r61_vs_raw")
    ].set_index("metric")

    def gate(metric: str) -> dict[str, object]:
        row = primary.loc[metric]
        passed = bool(row["improved_fraction"] >= 0.60 and row["bootstrap_ci95_low"] > 0)
        return {
            "pass": passed,
            "base_median": float(row["base_median"]),
            "target_median": float(row["target_median"]),
            "median_improvement": float(row["median_improvement"]),
            "bootstrap_ci95_low": float(row["bootstrap_ci95_low"]),
            "bootstrap_ci95_high": float(row["bootstrap_ci95_high"]),
            "improved_count": int(row["improved_count"]),
            "improved_fraction": float(row["improved_fraction"]),
            "wilcoxon_p_holm": float(row["wilcoxon_p_holm"]),
        }

    iou_gate = gate("iou")
    distance_gate = gate("mean_boundary_distance_px")
    perimeter_gate = gate("perimeter_error_pct")
    circularity_gate = gate("circularity_abs_error")
    coarse_pass = bool(iou_gate["pass"] and distance_gate["pass"])
    fine_pass = bool(perimeter_gate["pass"] and circularity_gate["pass"])
    sensitivity_primary = sensitivity.loc[sensitivity["comparison"] == "r61_vs_raw"]
    sensitivity_checks = []
    for preset in [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]:
        subset = sensitivity_primary.loc[sensitivity_primary["preset"] == preset].set_index("metric")
        check = {
            "preset": preset,
            "iou_median_improvement": float(subset.loc["iou", "median_improvement"]),
            "distance_median_improvement_px": float(subset.loc["mean_boundary_distance_px", "median_improvement"]),
        }
        check["pass"] = bool(
            check["iou_median_improvement"] > 0 and check["distance_median_improvement_px"] > 0
        )
        sensitivity_checks.append(check)
    sensitivity_pass = all(item["pass"] for item in sensitivity_checks)
    if coarse_pass and sensitivity_pass and fine_pass:
        verdict = "PASS_ACM_CONTOUR"
    elif coarse_pass and sensitivity_pass:
        verdict = "CONDITIONAL_COARSE_CONTOUR_PASS"
    else:
        verdict = "FAIL_ACM_CONTOUR"
    return {
        "verdict": verdict,
        "primary_population": "20 independently generated unseen edge-defect images",
        "primary_alignment": "translation_only; no scale or rotation fitting",
        "coarse_contour_pass": coarse_pass,
        "fine_shape_pass": fine_pass,
        "sensitivity_pass": sensitivity_pass,
        "gates": {
            "iou": iou_gate,
            "mean_boundary_distance_px": distance_gate,
            "perimeter_error_pct": perimeter_gate,
            "circularity_abs_error": circularity_gate,
        },
        "sensitivity_checks": sensitivity_checks,
        "interpretation_boundary": (
            "A paired synthetic full-contour test of one closed jagged-defect family; "
            "not a universal claim for open grids, textures, multi-object fields, real SEM, or all exposures."
        ),
    }


def matlab_round(values: np.ndarray) -> np.ndarray:
    return np.where(values >= 0, np.floor(values + 0.5), np.ceil(values - 0.5)).astype(int)


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


def draw_contour(axis: plt.Axes, mask: np.ndarray, color: str, linewidth: float = 1.4, linestyle: str = "-") -> None:
    for contour in find_contours(mask.astype(float), 0.5):
        axis.plot(contour[:, 1], contour[:, 0], color=color, linewidth=linewidth, linestyle=linestyle)


def read_image(directory_key: str, image_id: int) -> np.ndarray:
    path = Path(PROJECT_ROOT / CONFIG["sources"][directory_key]) / f"{image_id:04d}.bmp"
    return np.asarray(Image.open(path).convert("L"), dtype=np.uint8)


def style_image_axis(axis: plt.Axes, side: int = 512) -> None:
    axis.set_xlim(35, side - 36)
    axis.set_ylim(side - 36, 35)
    axis.set_xticks([])
    axis.set_yticks([])
    for spine in axis.spines.values():
        spine.set_visible(False)


def load_masks() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    content = loadmat(MASKS / "acm_primary_masks.mat")
    image_ids = np.ravel(content["image_ids"]).astype(int)
    masks = {
        "Truth": content["truth_masks"].astype(bool),
        "Raw": content["raw_masks"].astype(bool),
        "COMBO": content["combo_masks"].astype(bool),
        "R61v16": content["r61_masks"].astype(bool),
    }
    return image_ids, masks


def make_figures(primary: pd.DataFrame, per_image: pd.DataFrame, sensitivity: pd.DataFrame) -> dict[str, int]:
    FIGURES.mkdir(parents=True, exist_ok=True)
    chart_style()
    image_ids, masks = load_masks()
    index_for = {int(image_id): index for index, image_id in enumerate(image_ids)}
    translation_rows = per_image.loc[per_image["alignment"] == "translation_only"].copy()
    distance_field = "r61_vs_raw_improvement_mean_boundary_distance_px"
    sorted_rows = translation_rows.sort_values(distance_field)
    chosen_ids = [
        int(sorted_rows.iloc[0]["image_id"]),
        int(sorted_rows.iloc[len(sorted_rows) // 2]["image_id"]),
        int(sorted_rows.iloc[-1]["image_id"]),
    ]

    fig, axes = plt.subplots(4, 5, figsize=(15, 12), constrained_layout=True)
    qa_ids = [80, 84, 88, 92, 96]
    for column, image_id in enumerate(qa_ids):
        index = index_for[image_id]
        truth_image = read_image("truth_dir", image_id)
        axes[0, column].imshow(truth_image, cmap="gray", vmin=0, vmax=255)
        draw_contour(axes[0, column], masks["Truth"][:, :, index], R61_COLOR, 1.8)
        axes[0, column].set_title(f"{image_id:04d}")
        style_image_axis(axes[0, column])
        for row, method in enumerate(METHODS, start=1):
            directory_key = {"Raw": "raw_dir", "COMBO": "combo_dir", "R61v16": "r61_dir"}[method]
            image = read_image(directory_key, image_id)
            predicted = align_to_truth(masks[method][:, :, index], masks["Truth"][:, :, index])
            axes[row, column].imshow(image, cmap="gray", vmin=0, vmax=255)
            draw_contour(axes[row, column], masks["Truth"][:, :, index], TRUTH_COLOR, 1.5)
            draw_contour(axes[row, column], predicted, METHOD_COLORS[method], 1.4)
            style_image_axis(axes[row, column])
            if column == 0:
                axes[row, column].set_ylabel(method)
    axes[0, 0].set_ylabel("乾淨答案")
    fig.suptitle("ACM 擷取品質：白色為正確外框，彩色為各方法外框", fontsize=15)
    fig.savefig(FIGURES / "00_truth_and_method_acm_qa.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(3, 4, figsize=(13, 10), constrained_layout=True)
    column_methods = ["Truth", "Raw", "COMBO", "R61v16"]
    column_titles = ["乾淨答案", "重建前", "舊基準", "R61v16"]
    for row, image_id in enumerate(chosen_ids):
        index = index_for[image_id]
        for column, method in enumerate(column_methods):
            if method == "Truth":
                image = read_image("truth_dir", image_id)
                axes[row, column].imshow(image, cmap="gray", vmin=0, vmax=255)
                draw_contour(axes[row, column], masks["Truth"][:, :, index], R61_COLOR, 1.8)
            else:
                directory_key = {"Raw": "raw_dir", "COMBO": "combo_dir", "R61v16": "r61_dir"}[method]
                image = read_image(directory_key, image_id)
                predicted = align_to_truth(masks[method][:, :, index], masks["Truth"][:, :, index])
                axes[row, column].imshow(image, cmap="gray", vmin=0, vmax=255)
                draw_contour(axes[row, column], masks["Truth"][:, :, index], TRUTH_COLOR, 1.7)
                draw_contour(axes[row, column], predicted, METHOD_COLORS[method], 1.5)
            style_image_axis(axes[row, column])
            if row == 0:
                axes[row, column].set_title(column_titles[column])
        label = ["最差", "中位", "最佳"][row]
        delta = float(translation_rows.set_index("image_id").loc[image_id, distance_field])
        axes[row, 0].set_ylabel(f"{label} {image_id:04d}\n改善 {delta:+.3f}px")
    fig.suptitle("ACM 完整輪廓代表案例（白：正確外框；彩色：方法外框）", fontsize=15)
    fig.savefig(FIGURES / "01_acm_contour_examples.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    translation = primary.loc[primary["alignment"] == "translation_only"]
    metric_panels = [
        ("iou", "輪廓重疊率", "IoU"),
        ("mean_boundary_distance_px", "平均邊界距離", "px"),
        ("area_error_pct", "面積誤差", "%"),
        ("perimeter_error_pct", "周長誤差", "%"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for axis, (metric, title, ylabel) in zip(axes.ravel(), metric_panels):
        data = [translation.loc[translation["method"] == method, metric].to_numpy() for method in METHODS]
        box = axis.boxplot(data, tick_labels=["Raw", "COMBO", "R61"], patch_artist=True, showfliers=True)
        for patch, method in zip(box["boxes"], METHODS):
            patch.set_facecolor(METHOD_COLORS[method])
            patch.set_alpha(0.55)
            patch.set_edgecolor(INK)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="x", visible=False)
    fig.suptitle("20 張鋸齒缺陷影像的 ACM 形狀分數", fontsize=15)
    fig.savefig(FIGURES / "02_acm_metric_comparison.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), constrained_layout=True)
    ordered = translation_rows.sort_values(distance_field)
    x = np.arange(len(ordered))
    distance_delta = ordered[distance_field].to_numpy()
    iou_delta = ordered["r61_vs_raw_improvement_iou"].to_numpy()
    colors_distance = np.where(distance_delta >= 0, R61_COLOR, PALE_ORANGE)
    colors_iou = np.where(iou_delta >= 0, R61_COLOR, PALE_ORANGE)
    axes[0].bar(x, distance_delta, color=colors_distance, edgecolor=INK, linewidth=0.5)
    axes[1].bar(x, iou_delta, color=colors_iou, edgecolor=INK, linewidth=0.5)
    for axis, title, ylabel in (
        (axes[0], "每張影像的平均邊界距離改善", "Raw 減 R61（px）"),
        (axes[1], "每張影像的輪廓重疊改善", "R61 減 Raw（IoU）"),
    ):
        axis.axhline(0, color=INK, linewidth=1.1)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.set_xlabel("20 張影像，依邊界距離改善排序")
        axis.set_xticks([])
        axis.grid(axis="x", visible=False)
    fig.savefig(FIGURES / "03_paired_contour_improvement.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    presets = [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]
    sensitivity_primary = sensitivity.loc[sensitivity["comparison"] == "r61_vs_raw"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)
    for axis, metric, title, ylabel in (
        (axes[0], "iou", "輪廓重疊的參數敏感度", "R61 減 Raw（IoU）"),
        (axes[1], "mean_boundary_distance_px", "邊界距離的參數敏感度", "Raw 減 R61（px）"),
    ):
        values = [
            float(sensitivity_primary.loc[(sensitivity_primary["preset"] == preset) & (sensitivity_primary["metric"] == metric), "median_improvement"].iloc[0])
            for preset in presets
        ]
        axis.bar(np.arange(len(presets)), values, color=R61_COLOR, edgecolor=INK)
        axis.axhline(0, color=INK, linewidth=1.1)
        axis.set_xticks(np.arange(len(presets)), ["低平滑", "主設定", "高平滑"])
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="x", visible=False)
    fig.suptitle("六張預先固定影像、三組 ACM 設定", fontsize=14)
    fig.savefig(FIGURES / "04_acm_sensitivity.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    worst_ids = [int(value) for value in sorted_rows.head(5)["image_id"]]
    fig, axes = plt.subplots(5, 2, figsize=(8, 15), constrained_layout=True)
    for row, image_id in enumerate(worst_ids):
        index = index_for[image_id]
        for column, method in enumerate(("Raw", "R61v16")):
            directory_key = "raw_dir" if method == "Raw" else "r61_dir"
            image = read_image(directory_key, image_id)
            predicted = align_to_truth(masks[method][:, :, index], masks["Truth"][:, :, index])
            axes[row, column].imshow(image, cmap="gray", vmin=0, vmax=255)
            draw_contour(axes[row, column], masks["Truth"][:, :, index], TRUTH_COLOR, 1.7)
            draw_contour(axes[row, column], predicted, METHOD_COLORS[method], 1.5)
            style_image_axis(axes[row, column])
            if row == 0:
                axes[row, column].set_title("重建前" if method == "Raw" else "R61v16")
        delta = float(translation_rows.set_index("image_id").loc[image_id, distance_field])
        axes[row, 0].set_ylabel(f"{image_id:04d}\n改善 {delta:+.3f}px")
    fig.suptitle("R61 邊界距離改善最小的五張影像", fontsize=15)
    fig.savefig(FIGURES / "05_worst_acm_cases.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    fixed = per_image.loc[per_image["alignment"] == "fixed_pixel_coordinates"].set_index("image_id")
    aligned = per_image.loc[per_image["alignment"] == "translation_only"].set_index("image_id")
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), constrained_layout=True)
    for axis, metric, title, label in (
        (axes[0], "iou", "平移前後的輪廓重疊改善", "IoU 改善"),
        (axes[1], "mean_boundary_distance_px", "平移前後的邊界距離改善", "距離改善（px）"),
    ):
        field = f"r61_vs_raw_improvement_{metric}"
        x_values = fixed[field].to_numpy()
        y_values = aligned[field].to_numpy()
        lower = min(float(x_values.min()), float(y_values.min()))
        upper = max(float(x_values.max()), float(y_values.max()))
        padding = max((upper - lower) * 0.08, 1e-4)
        axis.scatter(x_values, y_values, s=44, color=R61_COLOR, edgecolor=INK, linewidth=0.6)
        axis.plot([lower - padding, upper + padding], [lower - padding, upper + padding], color=INK, linestyle="--")
        axis.axhline(0, color=GRID, linewidth=1)
        axis.axvline(0, color=GRID, linewidth=1)
        axis.set_xlim(lower - padding, upper + padding)
        axis.set_ylim(lower - padding, upper + padding)
        axis.set_xlabel(f"固定座標的{label}")
        axis.set_ylabel(f"只平移後的{label}")
        axis.set_title(title)
        axis.grid(False)
    fig.savefig(FIGURES / "06_alignment_effect.png", dpi=190, bbox_inches="tight")
    plt.close(fig)

    chart_map = [
        {"figure": "00_truth_and_method_acm_qa.png", "question": "Are the extracted contours visually valid?", "type": "image overlay grid", "fields": ["image", "truth_contour", "method_contour"], "claim": "The fixed-seed ACM follows the intended closed body for truth and all methods."},
        {"figure": "01_acm_contour_examples.png", "question": "What do worst, median, and best full-contour cases look like?", "type": "representative image grid", "fields": ["case_rank", "truth", "raw", "combo", "r61"], "claim": "R61 improves coarse placement in typical cases while retaining visibly rough edges."},
        {"figure": "02_acm_metric_comparison.png", "question": "How do shape metrics differ across methods?", "type": "box plot", "fields": ["method", "iou", "mean_boundary_distance_px", "area_error_pct", "perimeter_error_pct"], "claim": "R61 improves overlap, boundary distance, and area but worsens perimeter fidelity."},
        {"figure": "03_paired_contour_improvement.png", "question": "How consistent is R61 improvement image by image?", "type": "paired delta bars", "fields": ["image_id", "distance_improvement", "iou_improvement"], "claim": "Nineteen of twenty images improve on both coarse primary metrics."},
        {"figure": "04_acm_sensitivity.png", "question": "Does the result survive ACM setting changes?", "type": "bar chart", "fields": ["preset", "median_improvement"], "claim": "All three fixed presets retain positive median coarse-contour improvement."},
        {"figure": "05_worst_acm_cases.png", "question": "What are the weakest contour cases?", "type": "failure-case overlay grid", "fields": ["image_id", "truth_contour", "raw_contour", "r61_contour"], "claim": "The single coarse-metric regression and smallest gains are visible rather than hidden by aggregates."},
        {"figure": "06_alignment_effect.png", "question": "Does translation alignment create the conclusion?", "type": "paired scatter", "fields": ["fixed_coordinate_improvement", "translation_aligned_improvement"], "claim": "The direction remains positive for eighteen of twenty images even without alignment."},
    ]
    (RESULTS / "chart_map.json").write_text(json.dumps(chart_map, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"representative_worst": chosen_ids[0], "representative_median": chosen_ids[1], "representative_best": chosen_ids[2]}


def format_p(value: float) -> str:
    return f"{value:.2e}" if value < 0.001 else f"{value:.3f}"


def write_report(summary: pd.DataFrame, sensitivity: pd.DataFrame, brightness: pd.DataFrame, decision: dict[str, object]) -> None:
    primary = summary.loc[
        (summary["alignment"] == "translation_only") & (summary["comparison"] == "r61_vs_raw")
    ].set_index("metric")
    fixed = summary.loc[
        (summary["alignment"] == "fixed_pixel_coordinates") & (summary["comparison"] == "r61_vs_raw")
    ].set_index("metric")
    combo = summary.loc[
        (summary["alignment"] == "translation_only") & (summary["comparison"] == "r61_vs_combo")
    ].set_index("metric")
    iou = primary.loc["iou"]
    distance = primary.loc["mean_boundary_distance_px"]
    area = primary.loc["area_error_pct"]
    perimeter = primary.loc["perimeter_error_pct"]
    circularity = primary.loc["circularity_abs_error"]
    fixed_distance = fixed.loc["mean_boundary_distance_px"]
    combo_distance = combo.loc["mean_boundary_distance_px"]
    sensitivity_primary = sensitivity.loc[
        (sensitivity["comparison"] == "r61_vs_raw")
        & sensitivity["metric"].isin(["iou", "mean_boundary_distance_px"])
    ]
    preset_passes = sum(
        bool(group.set_index("metric").loc["iou", "median_improvement"] > 0)
        and bool(group.set_index("metric").loc["mean_boundary_distance_px", "median_improvement"] > 0)
        for _, group in sensitivity_primary.groupby("preset")
    )
    rho_iou_mean = brightness.loc[
        (brightness["brightness_field"] == "mean_intensity_0_255") & (brightness["contour_metric"] == "iou"),
        "spearman_rho",
    ].iloc[0]
    verdict_text = {
        "PASS_ACM_CONTOUR": "通過完整輪廓與細部形狀門檻",
        "CONDITIONAL_COARSE_CONTOUR_PASS": "粗外框有條件通過，但細部形狀未通過",
        "FAIL_ACM_CONTOUR": "未通過完整輪廓門檻",
    }[str(decision["verdict"])]

    report = f"""# R72：R61 合成顯微缺陷的 ACM 完整輪廓驗證

## 結論先行

**判定：{verdict_text}。** 這次改用與先前 SEM 驗證同類的 Chan–Vese ACM，直接比較完整、不規則的封閉外框；一般邊緣偵測不再作為主要形狀判定。

- 只平移、不縮放也不旋轉後，輪廓重疊率由 Raw 的 **{iou['base_median']:.4f}** 提升到 R61 的 **{iou['target_median']:.4f}**。配對中位改善 **{iou['median_improvement']:+.4f}**，20 張中 **{int(iou['improved_count'])}/20** 張改善；95% 重抽樣範圍 **{iou['bootstrap_ci95_low']:.4f}–{iou['bootstrap_ci95_high']:.4f}**。
- 平均邊界距離由 **{distance['base_median']:.3f}px** 降到 **{distance['target_median']:.3f}px**。配對中位改善 **{distance['median_improvement']:+.3f}px**，同樣是 **{int(distance['improved_count'])}/20** 張改善；95% 範圍 **{distance['bootstrap_ci95_low']:.3f}–{distance['bootstrap_ci95_high']:.3f}px**，校正後 p={format_p(float(distance['wilcoxon_p_holm']))}。
- 面積誤差由 **{area['base_median']:.3f}%** 降到 **{area['target_median']:.3f}%**，**{int(area['improved_count'])}/20** 張改善。
- 但周長誤差由 **{perimeter['base_median']:.2f}%** 增加到 **{perimeter['target_median']:.2f}%**；圓整程度誤差由 **{circularity['base_median']:.3f}** 增加到 **{circularity['target_median']:.3f}**。這表示 R61 把主要外框位置變準，卻沒有忠實保留所有細小鋸齒。

因此，ACM 結果與先前 SEM 結果方向一致：**R61 的粗外框更準，但細部邊緣被平滑。**

## 這次為什麼才算形狀比較

每張影像先用 ACM 得到一張只有內外之分的形狀遮罩，後續分數只看這些遮罩的重疊、邊界距離、面積、周長與圓整程度，不再比較灰階亮度。亮度與對比只參與「從影像找出外框」這一步，而且每張圖在找輪廓前都各自做相同的對比正規化。

所有方法都從同一個固定大矩形開始收縮到物體邊界。這個起點沒有使用每張乾淨答案的輪廓，因此不會替 R61 預先描好形狀。亮度均值與輪廓重疊改善的等級相關為 **{rho_iou_mean:+.2f}**；這只作為檢查，不能解讀成亮度對 ACM 完全沒有影響。

![ACM 擷取品質](../results/figures/00_truth_and_method_acm_qa.png)

## 代表性完整輪廓

下圖不是只挑最好看的影像，而是依 R61 的邊界距離改善選出最差、中位與最佳案例。白線是正確外框，彩色線是 Raw、COMBO 或 R61 的 ACM 外框。

![代表性 ACM 完整輪廓](../results/figures/01_acm_contour_examples.png)

## 粗外框改善，細小鋸齒退步

R61 的重疊率、平均邊界距離與面積誤差整體優於 Raw，也明顯優於舊 COMBO；COMBO 的平均邊界距離中位數為 **{combo_distance['base_median']:.3f}px**，R61 為 **{combo_distance['target_median']:.3f}px**。但 R61 的周長與圓整程度誤差增加，代表外框更貼近正確位置，不等於每個微小凹凸都被真實恢復。

![ACM 分數比較](../results/figures/02_acm_metric_comparison.png)

![逐張輪廓改善](../results/figures/03_paired_contour_improvement.png)

## 不是靠平移或單一 ACM 設定得到的結果

主要結果只允許平移，和 R69/R70 的形狀比較規則一致。更嚴格地完全不平移時，平均邊界距離仍由 Raw 的 **{fixed_distance['base_median']:.3f}px** 降到 R61 的 **{fixed_distance['target_median']:.3f}px**，20 張中 **{int(fixed_distance['improved_count'])}/20** 張改善。

三組預先固定的 ACM 平滑設定，在六張固定影像上全部保留正向的輪廓重疊與邊界距離中位改善（{preset_passes}/3 組通過）。

![ACM 設定敏感度](../results/figures/04_acm_sensitivity.png)

![平移影響](../results/figures/06_alignment_effect.png)

## 最弱案例沒有被平均值藏起來

20 張中有一張在主要粗外框分數上退步。下圖列出改善最小的五張，包含該失敗案例。

![最弱 ACM 案例](../results/figures/05_worst_acm_cases.png)

## 測試範圍與限制

- 主要樣本是 R71 測試集中 20 張未參與 R61 訓練的 `edge_defects` 影像；每張都是獨立產生，且有一個明確、封閉、刻意不規則的主物體。
- 格網、隨機紋理和多物件混合影像沒有唯一封閉外框，硬用單一 ACM 輪廓會比較不同東西，因此沒有放進這個主要形狀結論。
- 乾淨答案、Raw、COMBO 與 R61 都使用 MATLAB Chan–Vese ACM。主要設定為 200 次、平滑 1.0；沒有縮放、旋轉或套圓。
- 這是合成真值下的完整形狀壓力測試，不是新的真實 SEM 樣品，也不能單獨證明所有位置與所有曝光都會成功。

## 下一步

1. R61 可以保留為目前最新基準，但論文應寫成「主要外框改善、細部鋸齒未完全保留」，不能寫成所有形狀都忠實恢復。
2. 下一批真實 SEM／光學配對資料應沿用相同 ACM 指標，並把周長與局部凹凸列為獨立失敗檢查。
3. 若要擴充合成測試，應另外建立有明確物件身分的多物件真值，而不是把單一輪廓強套到格網或隨機紋理。

## 仍待回答的問題

- 合成影像中被平滑掉的鋸齒，在真實 HS100MG 或 SEM 外框上是否也會出現？
- 能否在維持目前粗外框改善的同時，降低周長與局部凹凸誤差？
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "R72_RESULTS_TW.md").write_text(report, encoding="utf-8")


def main() -> int:
    TABLES.mkdir(parents=True, exist_ok=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    sensitivity_raw = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    validate_inputs(primary, sensitivity_raw)
    summary, per_image = paired_summaries(primary)
    sensitivity = sensitivity_summary(sensitivity_raw)
    brightness = brightness_check(primary, per_image)
    decision = decide(summary, sensitivity)
    summary.to_csv(TABLES / "paired_metric_summary.csv", index=False, encoding="utf-8-sig")
    per_image.to_csv(TABLES / "per_image_paired_metrics.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(TABLES / "acm_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    brightness.to_csv(TABLES / "brightness_association_check.csv", index=False, encoding="utf-8-sig")
    representatives = make_figures(primary, per_image, sensitivity)
    decision["representatives"] = representatives
    (RESULTS / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(summary, sensitivity, brightness, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
