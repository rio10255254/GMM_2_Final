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


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
EVIDENCE = CONFIG["paired_evidence"]
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
E100_TABLES = RESULTS / "epoch100_audit" / "results" / "tables"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"
RAW_DIR = Path(EVIDENCE["raw_input_dir"])
R69 = Path(EVIDENCE["r69_root"])
R70 = Path(EVIDENCE["r70_root"])
R76 = Path(EVIDENCE["r76_root"])
BEST_LABEL = CONFIG["contour"]["best_method_label"]
E100_LABEL = CONFIG["contour"]["epoch100_method_label"]
METHODS = ["Raw", "R61v16", "V42E120", "R75Old", BEST_LABEL, E100_LABEL]
COLORS = {
    "Raw": "#D97706",
    "R61v16": "#2563EB",
    "V42E120": "#059669",
    "R75Old": "#94A3B8",
    BEST_LABEL: "#DC2626",
    E100_LABEL: "#7C3AED",
}
METRICS = {
    "iou": ("Contour IoU", "higher"),
    "dice": ("Dice", "higher"),
    "mean_boundary_distance_pitch_pct": ("Mean boundary distance (% pitch)", "lower"),
    "hd95_pitch_pct": ("HD95 (% pitch)", "lower"),
    "area_error_pct": ("Area error (%)", "lower"),
    "perimeter_error_pct": ("Perimeter error (%)", "lower"),
    "circularity_abs_error": ("Circularity error", "lower"),
}
BOOTSTRAP = int(CONFIG["statistics"]["bootstrap_repetitions"])
SEED = int(CONFIG["statistics"]["random_seed"])
MIN_FRACTION = float(CONFIG["statistics"]["coarse_gate_min_improved_fraction"])


def slug(value: str) -> str:
    return {
        "Raw": "raw",
        "R61v16": "r61v16",
        "V42E120": "v42e120",
        "R75Old": "r75_old",
        BEST_LABEL: "r75v2_best_e84",
        E100_LABEL: "r75v2_e100",
    }[value]


def improvement(source: np.ndarray, target: np.ndarray, direction: str) -> np.ndarray:
    return target - source if direction == "higher" else source - target


def bootstrap_median_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    indices = rng.integers(0, len(values), size=(BOOTSTRAP, len(values)))
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


def assert_same_raw(reference: pd.DataFrame, candidate: pd.DataFrame, sensitivity: bool = False) -> None:
    key = ["preset", "exposure", "pillar_id"] if sensitivity else ["exposure", "pillar_id"]
    columns = (
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
        if sensitivity
        else list(METRICS) + ["centroid_alignment_shift_px"]
    )
    a = reference[reference["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    b = candidate[candidate["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if len(a) != len(b) or not np.allclose(a[columns], b[columns], rtol=0, atol=1e-12):
        raise RuntimeError("Raw contour extraction does not reproduce exactly across experiments")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    best = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    best_s = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    e100 = pd.read_csv(E100_TABLES / "primary_contour_metrics.csv")
    e100_s = pd.read_csv(E100_TABLES / "acm_sensitivity_metrics.csv")
    r69 = pd.read_csv(R69 / "results" / "tables" / "primary_contour_metrics.csv")
    r70 = pd.read_csv(R70 / "results" / "tables" / "primary_contour_metrics.csv")
    r76 = pd.read_csv(R76 / "results" / "tables" / "primary_contour_metrics.csv")
    r69_s = pd.read_csv(R69 / "results" / "tables" / "acm_sensitivity_metrics.csv")

    for item in [e100, r69, r70, r76]:
        assert_same_raw(best, item)
    assert_same_raw(best_s, e100_s, sensitivity=True)
    assert_same_raw(best_s, r69_s, sensitivity=True)

    old = r76[r76["method"] == "R75"].copy()
    old["method"] = "R75Old"
    combined = pd.concat(
        [
            best[best["method"].isin(["Raw", BEST_LABEL])],
            e100[e100["method"] == E100_LABEL],
            r69[r69["method"] == "R61v16"],
            r70[r70["method"] == "V42E120"],
            old,
        ],
        ignore_index=True,
    )
    combined["method"] = pd.Categorical(combined["method"], METHODS, ordered=True)
    combined = combined.sort_values(["exposure", "pillar_id", "method"]).reset_index(drop=True)
    if len(combined) != 12 * 36 * len(METHODS) or combined.isna().any().any():
        raise RuntimeError("Combined primary contour table is incomplete")

    sensitivity = pd.concat(
        [
            best_s[best_s["method"].isin(["Raw", BEST_LABEL])],
            e100_s[e100_s["method"] == E100_LABEL],
        ],
        ignore_index=True,
    )
    if sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity table contains missing values")
    return combined, sensitivity, best, e100


def calculate_statistics(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    medians = primary.groupby(["pillar_id", "method"], observed=True)[list(METRICS)].median().unstack("method")
    mapping = primary[["pillar_id", "grid_row", "grid_col", "truth_circularity"]].drop_duplicates("pillar_id").set_index("pillar_id")
    pillar_rows: list[dict[str, object]] = []
    for pillar_id in medians.index:
        row: dict[str, object] = {
            "pillar_id": int(pillar_id),
            "grid_row": int(mapping.loc[pillar_id, "grid_row"]),
            "grid_col": int(mapping.loc[pillar_id, "grid_col"]),
            "truth_circularity": float(mapping.loc[pillar_id, "truth_circularity"]),
        }
        for metric in METRICS:
            for method in METHODS:
                row[f"{slug(method)}_{metric}"] = float(medians.loc[pillar_id, (metric, method)])
        pillar_rows.append(row)

    rng = np.random.default_rng(SEED)
    comparisons: list[dict[str, object]] = []
    for target in [BEST_LABEL, E100_LABEL]:
        for source in METHODS:
            if source == target:
                continue
            for metric, (label, direction) in METRICS.items():
                source_values = medians[(metric, source)].to_numpy(float)
                target_values = medians[(metric, target)].to_numpy(float)
                delta = improvement(source_values, target_values, direction)
                low, high = bootstrap_median_ci(delta, rng)
                try:
                    _, p_value = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
                except ValueError:
                    p_value = 1.0
                comparisons.append(
                    {
                        "comparison": f"{source}_to_{target}",
                        "source_method": source,
                        "target_method": target,
                        "metric": metric,
                        "metric_label": label,
                        "better_direction": direction,
                        "independent_pillars": len(delta),
                        "source_median": float(np.median(source_values)),
                        "target_median": float(np.median(target_values)),
                        "median_improvement": float(np.median(delta)),
                        "bootstrap_ci95_low": low,
                        "bootstrap_ci95_high": high,
                        "improved_pillars": int(np.count_nonzero(delta > 0)),
                        "unchanged_pillars": int(np.count_nonzero(delta == 0)),
                        "worsened_pillars": int(np.count_nonzero(delta < 0)),
                        "improved_fraction": float(np.mean(delta > 0)),
                        "wilcoxon_p_two_sided": float(p_value),
                    }
                )
    comparison_frame = pd.DataFrame(comparisons)
    comparison_frame["wilcoxon_p_holm_within_comparison"] = np.nan
    for _, indices in comparison_frame.groupby("comparison").groups.items():
        comparison_frame.loc[indices, "wilcoxon_p_holm_within_comparison"] = holm_adjust(
            comparison_frame.loc[indices, "wilcoxon_p_two_sided"].tolist()
        )

    exposure_rows: list[dict[str, object]] = []
    for exposure, group in primary.groupby("exposure", sort=True, observed=True):
        raw_image = np.asarray(Image.open(RAW_DIR / f"{int(exposure)}.bmp").convert("L"), dtype=float)
        row: dict[str, object] = {"exposure": int(exposure), "raw_mean_intensity": float(raw_image.mean())}
        for metric, (_, direction) in METRICS.items():
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            for method in METHODS:
                row[f"{slug(method)}_median_{metric}"] = float(pivot[method].median())
            for target in [BEST_LABEL, E100_LABEL]:
                delta = improvement(pivot["Raw"].to_numpy(float), pivot[target].to_numpy(float), direction)
                row[f"{slug(target)}_vs_raw_median_improvement_{metric}"] = float(np.median(delta))
                row[f"{slug(target)}_vs_raw_improved_pillars_{metric}"] = int(np.count_nonzero(delta > 0))
        exposure_rows.append(row)
    return pd.DataFrame(pillar_rows), comparison_frame, pd.DataFrame(exposure_rows)


def sensitivity_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    metrics = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    for (preset, exposure), group in frame.groupby(["preset", "exposure"], sort=False):
        for target in [BEST_LABEL, E100_LABEL]:
            row: dict[str, object] = {"preset": str(preset), "exposure": int(exposure), "target_method": target}
            for metric in metrics:
                direction = METRICS[metric][1]
                pivot = group.pivot(index="pillar_id", columns="method", values=metric)
                delta = improvement(pivot["Raw"].to_numpy(float), pivot[target].to_numpy(float), direction)
                row[f"median_improvement_{metric}"] = float(np.median(delta))
                row[f"improved_fraction_{metric}"] = float(np.mean(delta > 0))
            rows.append(row)
    return pd.DataFrame(rows)


def assess_target(target: str, comparisons: pd.DataFrame, exposure: pd.DataFrame, sensitivity: pd.DataFrame) -> dict[str, object]:
    group = comparisons[comparisons["comparison"] == f"Raw_to_{target}"].set_index("metric")
    coarse_metrics = ["iou", "mean_boundary_distance_pitch_pct"]
    coarse = all(group.loc[m, "bootstrap_ci95_low"] > 0 and group.loc[m, "improved_fraction"] >= MIN_FRACTION for m in coarse_metrics)
    universal_by_exposure = {
        str(int(row["exposure"])): bool(
            row[f"{slug(target)}_vs_raw_median_improvement_iou"] > 0
            and row[f"{slug(target)}_vs_raw_median_improvement_mean_boundary_distance_pitch_pct"] > 0
        )
        for _, row in exposure.iterrows()
    }
    sensitivity_result = {
        str(exposure_id): bool(
            (
                sensitivity[(sensitivity["target_method"] == target) & (sensitivity["exposure"] == exposure_id)][
                    ["median_improvement_iou", "median_improvement_mean_boundary_distance_pitch_pct"]
                ]
                > 0
            ).all(axis=None)
        )
        for exposure_id in [13, 18, 24]
    }
    prior = {}
    for source in ["R61v16", "V42E120", "R75Old"]:
        comp = comparisons[comparisons["comparison"] == f"{source}_to_{target}"].set_index("metric")
        if all(comp.loc[m, "bootstrap_ci95_low"] > 0 for m in coarse_metrics):
            prior[source] = f"{target}_better"
        elif all(comp.loc[m, "bootstrap_ci95_high"] < 0 for m in coarse_metrics):
            prior[source] = f"{source}_better"
        else:
            prior[source] = "not_decisive"
    return {
        "coarse_contour_gate_vs_raw": bool(coarse),
        "all_exposure_universal_gate_vs_raw": bool(all(universal_by_exposure.values())),
        "fine_shape_gate_vs_raw": bool(
            group.loc["perimeter_error_pct", "median_improvement"] > 0
            and group.loc["circularity_abs_error", "median_improvement"] > 0
        ),
        "universal_gate_by_exposure": universal_by_exposure,
        "acm_sensitivity_direction_consistent": sensitivity_result,
        "comparison_to_prior_models": prior,
    }


def checkpoint_comparison(comparisons: pd.DataFrame) -> str:
    group = comparisons[comparisons["comparison"] == f"{BEST_LABEL}_to_{E100_LABEL}"].set_index("metric")
    coarse = ["iou", "mean_boundary_distance_pitch_pct"]
    if all(group.loc[m, "bootstrap_ci95_low"] > 0 for m in coarse):
        return "epoch100_better_on_sem"
    if all(group.loc[m, "bootstrap_ci95_high"] < 0 for m in coarse):
        return "epoch84_better_on_sem"
    return "not_decisive_or_metric_mixed"


def matlab_round(values: np.ndarray) -> np.ndarray:
    return np.where(values >= 0, np.floor(values + 0.5), np.ceil(values - 0.5)).astype(int)


def shift_binary(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    height, width = mask.shape
    shifted = np.zeros_like(mask, dtype=bool)
    x1, x2 = max(0, -dx), min(width, width - dx)
    y1, y2 = max(0, -dy), min(height, height - dy)
    if x1 < x2 and y1 < y2:
        shifted[y1 + dy : y2 + dy, x1 + dx : x2 + dx] = mask[y1:y2, x1:x2]
    return shifted


def align_to_truth(predicted: np.ndarray, truth: np.ndarray) -> np.ndarray:
    dy, dx = matlab_round(np.asarray(center_of_mass(truth)) - np.asarray(center_of_mass(predicted)))
    return shift_binary(predicted, int(dy), int(dx))


def draw_contour(ax: plt.Axes, mask: np.ndarray, color: str, linewidth: float, linestyle: str = "-") -> None:
    for contour in find_contours(mask.astype(float), 0.5):
        ax.plot(contour[:, 1], contour[:, 0], color=color, linewidth=linewidth, linestyle=linestyle)


def make_figures(per_pillar: pd.DataFrame, exposure: pd.DataFrame) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    display_metrics = ["iou", "mean_boundary_distance_pitch_pct", "perimeter_error_pct", "circularity_abs_error"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    labels = ["Raw", "R61", "V42", "Old R75", "R75-v2 E84", "R75-v2 E100"]
    for ax, metric in zip(axes.ravel(), display_metrics):
        arrays = [per_pillar[f"{slug(method)}_{metric}"].to_numpy(float) for method in METHODS]
        for values in zip(*arrays):
            ax.plot(range(len(METHODS)), values, color="#CBD5E1", linewidth=0.55)
        ax.plot(range(len(METHODS)), [np.median(values) for values in arrays], color="#111827", linewidth=2.2, marker="o")
        for x, method, values in zip(range(len(METHODS)), METHODS, arrays):
            ax.scatter(np.full(len(values), x), values, color=COLORS[method], s=16, alpha=0.65)
        ax.set_xticks(range(len(METHODS)), labels, rotation=18, ha="right")
        ax.set_title(METRICS[metric][0])
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Paired SEM contour comparison across 36 physical pillars", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "01_all_models_paired_comparison.png", dpi=190, facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    x = exposure["exposure"].to_numpy(int)
    for method, label in zip(METHODS, labels):
        ax.plot(x, exposure[f"{slug(method)}_median_mean_boundary_distance_pitch_pct"], marker="o", linewidth=2, color=COLORS[method], label=label)
    ax.set_xlabel("Exposure index")
    ax.set_ylabel("Median boundary distance (% pitch)")
    ax.set_title("Contour stability across the 12 paired optical exposures")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=3)
    fig.savefig(FIGURES / "02_exposure_stability.png", dpi=190, facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for ax, metric in zip(axes, ["iou", "mean_boundary_distance_pitch_pct"]):
        best = per_pillar[f"{slug(BEST_LABEL)}_{metric}"].to_numpy(float)
        final = per_pillar[f"{slug(E100_LABEL)}_{metric}"].to_numpy(float)
        ax.scatter(best, final, color="#7C3AED", s=34, alpha=0.75)
        limits = [min(best.min(), final.min()), max(best.max(), final.max())]
        ax.plot(limits, limits, color="#111827", linestyle="--")
        ax.set_xlabel("Epoch 84")
        ax.set_ylabel("Epoch 100")
        ax.set_title(METRICS[metric][0])
        ax.grid(alpha=0.2)
    fig.suptitle("R75-v2 checkpoint comparison by physical pillar", fontsize=14, weight="bold")
    fig.savefig(FIGURES / "03_checkpoint_comparison.png", dpi=190, facecolor="white")
    plt.close(fig)

    best_dir = Path(CONFIG["inference"]["best_reconstruction_dir"])
    final_dir = Path(CONFIG["inference"]["epoch100_reconstruction_dir"])
    fig, axes = plt.subplots(3, 3, figsize=(13, 13), constrained_layout=True)
    for row, exposure_id in enumerate([18, 21, 24]):
        for col, (title, directory) in enumerate([("Raw", RAW_DIR), ("R75-v2 E84", best_dir), ("R75-v2 E100", final_dir)]):
            image = np.asarray(Image.open(directory / f"{exposure_id}.bmp").convert("L"))
            axes[row, col].imshow(image, cmap="gray", vmin=0, vmax=255)
            axes[row, col].set_title(f"{title} | exposure {exposure_id}")
            axes[row, col].axis("off")
    fig.suptitle("Reconstruction comparison at normal, transition, and darkest exposures", fontsize=14, weight="bold")
    fig.savefig(FIGURES / "04_raw_best_e100_image_comparison.png", dpi=180, facecolor="white")
    plt.close(fig)

    variables = ["truth_cells", "truth_masks", "raw_masks", "recon_masks", "exposures", "global_index"]
    best_masks = loadmat(RESULTS / "masks" / "acm_primary_masks.mat", squeeze_me=True, variable_names=variables)
    final_masks = loadmat(RESULTS / "epoch100_audit" / "results" / "masks" / "acm_primary_masks.mat", squeeze_me=True, variable_names=variables)
    truth_cells = best_masks["truth_cells"]
    truth = best_masks["truth_masks"].astype(bool)
    raw = best_masks["raw_masks"].astype(bool)
    best = best_masks["recon_masks"].astype(bool)
    final = final_masks["recon_masks"].astype(bool)
    exposures = np.asarray(best_masks["exposures"]).astype(int).ravel()
    global_index = np.asarray(best_masks["global_index"]).astype(int)
    exposure_index = int(np.flatnonzero(exposures == 18)[0])
    fig, axes = plt.subplots(6, 6, figsize=(13, 13), constrained_layout=True)
    for row in range(6):
        for col in range(6):
            pillar_id = int(global_index[row, col])
            index = pillar_id - 1
            ax = axes[row, col]
            ax.imshow(truth_cells[:, :, index], cmap="gray", vmin=0, vmax=255)
            draw_contour(ax, truth[:, :, index], "#111827", 1.2)
            draw_contour(ax, align_to_truth(raw[:, :, index, exposure_index], truth[:, :, index]), COLORS["Raw"], 0.9, "--")
            draw_contour(ax, align_to_truth(best[:, :, index, exposure_index], truth[:, :, index]), COLORS[BEST_LABEL], 1.0)
            draw_contour(ax, align_to_truth(final[:, :, index, exposure_index], truth[:, :, index]), COLORS[E100_LABEL], 1.0, ":")
            ax.set_title(f"ID {pillar_id}", fontsize=7)
            ax.axis("off")
    fig.legend(
        handles=[
            Line2D([0], [0], color="#111827", label="SEM"),
            Line2D([0], [0], color=COLORS["Raw"], linestyle="--", label="Raw"),
            Line2D([0], [0], color=COLORS[BEST_LABEL], label="R75-v2 E84"),
            Line2D([0], [0], color=COLORS[E100_LABEL], linestyle=":", label="R75-v2 E100"),
        ],
        loc="outside lower center",
        ncol=4,
        frameon=False,
    )
    fig.suptitle("Complete contour overlay for the central 36 pillars (exposure 18)", fontsize=14, weight="bold")
    fig.savefig(FIGURES / "05_center36_contour_overlay_exp18.png", dpi=190, facecolor="white")
    plt.close(fig)


def format_comparison(comparisons: pd.DataFrame, source: str, target: str, metric: str) -> pd.Series:
    return comparisons[(comparisons["comparison"] == f"{source}_to_{target}") & (comparisons["metric"] == metric)].iloc[0]


def write_report(comparisons: pd.DataFrame, decision: dict[str, object]) -> None:
    best_raw = {m: format_comparison(comparisons, "Raw", BEST_LABEL, m) for m in METRICS}
    final_raw = {m: format_comparison(comparisons, "Raw", E100_LABEL, m) for m in METRICS}
    best_r61 = format_comparison(comparisons, "R61v16", BEST_LABEL, "mean_boundary_distance_pitch_pct")
    best_v42 = format_comparison(comparisons, "V42E120", BEST_LABEL, "mean_boundary_distance_pitch_pct")
    checkpoint = format_comparison(comparisons, BEST_LABEL, E100_LABEL, "mean_boundary_distance_pitch_pct")
    best_decision = decision["best_e84"]
    final_decision = decision["final_e100"]
    report = f"""# R77：R75-v2 完成訓練後的 SEM／ACM 輪廓驗證

## 結論先行

R75-v2 已完成 100 輪訓練，訓練內部選出的正式候選是 **第 84 輪**。這份驗證使用 36 顆實體柱、12 個曝光及同一套 SEM 真值，只允許平移對準，不允許調整大小或旋轉。

- 第 84 輪相對 Raw：IoU 由 **{best_raw['iou']['source_median']:.4f}** 變成 **{best_raw['iou']['target_median']:.4f}**；平均邊界距離由 **{best_raw['mean_boundary_distance_pitch_pct']['source_median']:.4f}** 變成 **{best_raw['mean_boundary_distance_pitch_pct']['target_median']:.4f}% 柱距**。
- 第 84 輪在平均邊界距離上有 **{int(best_raw['mean_boundary_distance_pitch_pct']['improved_pillars'])}/36** 顆優於 Raw，95% 範圍為 **{best_raw['mean_boundary_distance_pitch_pct']['bootstrap_ci95_low']:.4f} 至 {best_raw['mean_boundary_distance_pitch_pct']['bootstrap_ci95_high']:.4f}**。
- 第 100 輪相對 Raw：IoU 為 **{final_raw['iou']['target_median']:.4f}**，平均邊界距離為 **{final_raw['mean_boundary_distance_pitch_pct']['target_median']:.4f}% 柱距**。
- 第 100 輪相對第 84 輪的平均邊界距離改善量為 **{checkpoint['median_improvement']:.4f}% 柱距**；兩個輪次的 SEM 比較判定為 **{decision['checkpoint_comparison']}**。

## 是否通過目前的真實影像門檻

| 檢查 | 第 84 輪 | 第 100 輪 |
|---|---:|---:|
| 相對 Raw 的主要粗輪廓 | {'通過' if best_decision['coarse_contour_gate_vs_raw'] else '未通過'} | {'通過' if final_decision['coarse_contour_gate_vs_raw'] else '未通過'} |
| 12 個曝光全部成立 | {'通過' if best_decision['all_exposure_universal_gate_vs_raw'] else '未通過'} | {'通過' if final_decision['all_exposure_universal_gate_vs_raw'] else '未通過'} |
| 周長與非圓細節 | {'通過' if best_decision['fine_shape_gate_vs_raw'] else '未通過'} | {'通過' if final_decision['fine_shape_gate_vs_raw'] else '未通過'} |

## 與既有模型比較

- R61v16 的平均邊界距離中位數為 **{best_r61['source_median']:.4f}% 柱距**，R75-v2 第 84 輪為 **{best_r61['target_median']:.4f}%**；判定為 **{best_decision['comparison_to_prior_models']['R61v16']}**。
- V42E120 的平均邊界距離中位數為 **{best_v42['source_median']:.4f}% 柱距**，R75-v2 第 84 輪為 **{best_v42['target_median']:.4f}%**；判定為 **{best_decision['comparison_to_prior_models']['V42E120']}**。
- 舊 R75 也使用完全相同的 Raw 與 SEM 輪廓重新納入比較，避免不同資料或不同 ACM 結果混在一起。

## 這次比較代表什麼

這裡比較的是完整二值外框，不是假設柱子為圓形後再量半徑。ACM 只負責從影像取得外框；IoU、邊界距離、面積、周長與圓整程度誤差都在外框上計算，不直接把亮度差當成形狀差。

36 顆柱子才是獨立樣本；12 個曝光是同一批柱子的重複觀察。每個模型都對照相同 SEM，只能平移中心，不能縮放或旋轉。第 84 輪由合成驗證資料在看 SEM 前選定，第 100 輪也是預先固定的完成點，因此沒有用 SEM 任意挑選最漂亮的輪次。

## 使用限制

這份結果能回答的是同一批 50 倍中央 36 顆柱子的真實 SEM 對照。它不能單獨證明其他倍率、材質、缺陷或顯微鏡條件都會相同；模型是否升級為整個專案基準，仍需一起看內部測試與先前凍結的外部合成形狀測試。
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "R77_RESULTS_TW.md").write_text(report, encoding="utf-8")


def main() -> int:
    primary, sensitivity, _, _ = load_data()
    per_pillar, comparisons, per_exposure = calculate_statistics(primary)
    sensitivity_stats = sensitivity_summary(sensitivity)
    decision = {
        "status": "complete",
        "training_selected_checkpoint_epoch": 84,
        "sem_used_for_checkpoint_selection": False,
        "best_e84": assess_target(BEST_LABEL, comparisons, per_exposure, sensitivity_stats),
        "final_e100": assess_target(E100_LABEL, comparisons, per_exposure, sensitivity_stats),
        "checkpoint_comparison": checkpoint_comparison(comparisons),
        "sem_truth_circularity": {
            "median": float(primary.drop_duplicates("pillar_id")["truth_circularity"].median()),
            "minimum": float(primary.drop_duplicates("pillar_id")["truth_circularity"].min()),
            "maximum": float(primary.drop_duplicates("pillar_id")["truth_circularity"].max()),
        },
    }
    per_pillar.to_csv(TABLES / "six_method_per_pillar_summary.csv", index=False)
    comparisons.to_csv(TABLES / "r75v2_paired_comparison_summary.csv", index=False)
    per_exposure.to_csv(TABLES / "six_method_per_exposure_summary.csv", index=False)
    sensitivity_stats.to_csv(TABLES / "r75v2_sensitivity_summary.csv", index=False)
    primary.to_csv(TABLES / "six_method_primary_contour_metrics.csv", index=False)
    (RESULTS / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    make_figures(per_pillar, per_exposure)
    write_report(comparisons, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
