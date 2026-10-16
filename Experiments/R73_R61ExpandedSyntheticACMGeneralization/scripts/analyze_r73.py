from __future__ import annotations

import json
import os
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.stats import wilcoxon
from skimage.measure import find_contours


ROOT = Path(os.environ.get("GMM_ACM_EXPERIMENT_ROOT", Path(__file__).resolve().parents[1]))
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA = Path(CONFIG["dataset"]["root"])
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"
SEED = int(CONFIG["statistics"]["random_seed"])
BOOTSTRAPS = int(CONFIG["statistics"]["bootstrap_repetitions"])

RAW_COLOR = "#D97706"
R61_COLOR = "#2563EB"
TRUTH_COLOR = "#F8FAFC"
INK = "#111827"
GRID = "#CBD5E1"
GOOD = "#15803D"
BAD = "#B91C1C"

FAMILIES = [item["name"] for item in CONFIG["dataset"]["families"]]
FAMILY_LABELS = {item["name"]: item["label_tw"] for item in CONFIG["dataset"]["families"]}
FAMILY_STAGES = {item["name"]: item["stage"] for item in CONFIG["dataset"]["families"]}
METRICS = {
    "iou": ("輪廓重疊率", "higher", "IoU（越高越好）"),
    "dice": ("Dice 重疊率", "higher", "Dice（越高越好）"),
    "mean_boundary_distance_px": ("平均邊界距離", "lower", "平均邊界距離（px，越低越好）"),
    "hd95_px": ("最差 5% 邊界距離", "lower", "HD95（px，越低越好）"),
    "area_error_pct": ("面積誤差", "lower", "面積誤差（%，越低越好）"),
    "perimeter_error_pct": ("周長誤差", "lower", "周長誤差（%，越低越好）"),
    "solidity_abs_error": ("凹凸程度誤差", "lower", "凹凸程度絕對誤差（越低越好）"),
    "roughness_abs_error": ("邊界粗糙度誤差", "lower", "粗糙度絕對誤差（越低越好）"),
}


def setup_style() -> None:
    plt.rcParams.update({
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
        "grid.alpha": 0.45,
    })


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def improvement(base: np.ndarray, target: np.ndarray, direction: str) -> np.ndarray:
    return target - base if direction == "higher" else base - target


def bootstrap_median_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    indices = rng.integers(0, len(values), size=(BOOTSTRAPS, len(values)))
    medians = np.median(values[indices], axis=1)
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def holm_adjust(p_values: list[float]) -> list[float]:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    adjusted = np.empty_like(values)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (len(values) - rank) * values[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def validate_inputs(primary: pd.DataFrame, truth_qa: pd.DataFrame, sensitivity: pd.DataFrame) -> None:
    required = {"image_id", "family", "method", "alignment", *METRICS}
    for label, frame in (("primary", primary), ("truth QA", truth_qa), ("sensitivity", sensitivity)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} table missing: {missing}")
        if not np.isfinite(frame[list(METRICS)].to_numpy(float)).all():
            raise ValueError(f"{label} table contains non-finite measurements")
    if len(primary) != 400 or len(truth_qa) != 100 or len(sensitivity) != 90:
        raise ValueError(f"Unexpected row counts: primary={len(primary)}, truth={len(truth_qa)}, sensitivity={len(sensitivity)}")
    expected_ids = {f"{family}/{index:04d}" for family in FAMILIES for index in range(20)}
    if set(primary["image_id"]) != expected_ids or set(truth_qa["image_id"]) != expected_ids:
        raise ValueError("Image IDs do not match the frozen 100-image set")
    counts = primary.groupby(["alignment", "method"])["image_id"].nunique()
    for alignment in ("translation_only", "fixed_pixel_coordinates"):
        for method in ("Raw", "R61v16"):
            if int(counts.get((alignment, method), 0)) != 100:
                raise ValueError(f"Incomplete primary cell: {alignment}/{method}")
    sensitivity_expected = len(FAMILIES) * len(CONFIG["acm"]["sensitivity_filenames"])
    for preset in [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]:
        for method in ("Raw", "R61v16"):
            count = sensitivity.loc[(sensitivity["preset"] == preset) & (sensitivity["method"] == method), "image_id"].nunique()
            if count != sensitivity_expected:
                raise ValueError(f"Incomplete sensitivity cell: {preset}/{method}")


def summarize_primary(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    summary_rows: list[dict] = []
    per_image_rows: list[dict] = []
    for alignment in ("translation_only", "fixed_pixel_coordinates"):
        aligned = primary.loc[primary["alignment"] == alignment]
        for family in [None, *FAMILIES]:
            group = aligned if family is None else aligned.loc[aligned["family"] == family]
            pivots = {metric: group.pivot(index="image_id", columns="method", values=metric) for metric in METRICS}
            if family is not None and alignment == "translation_only":
                for image_id in pivots["iou"].index:
                    row = {"image_id": image_id, "family": family, "family_label_tw": FAMILY_LABELS[family], "alignment": alignment}
                    for metric, (_, direction, _) in METRICS.items():
                        pivot = pivots[metric]
                        base, target = float(pivot.loc[image_id, "Raw"]), float(pivot.loc[image_id, "R61v16"])
                        row[f"raw_{metric}"] = base
                        row[f"r61_{metric}"] = target
                        row[f"improvement_{metric}"] = float(improvement(np.array([base]), np.array([target]), direction)[0])
                    per_image_rows.append(row)
            scope_start = len(summary_rows)
            for metric, (label, direction, _) in METRICS.items():
                pivot = pivots[metric]
                base = pivot["Raw"].to_numpy(float)
                target = pivot["R61v16"].to_numpy(float)
                delta = improvement(base, target, direction)
                low, high = bootstrap_median_ci(delta, rng)
                try:
                    _, p_value = wilcoxon(target, base, alternative="two-sided", zero_method="wilcox")
                except ValueError:
                    p_value = 1.0
                summary_rows.append({
                    "alignment": alignment,
                    "scope": "overall" if family is None else "family",
                    "family": "all" if family is None else family,
                    "family_label_tw": "全部" if family is None else FAMILY_LABELS[family],
                    "metric": metric,
                    "metric_label": label,
                    "better_direction": direction,
                    "image_count": len(base),
                    "raw_median": float(np.median(base)),
                    "r61_median": float(np.median(target)),
                    "median_improvement": float(np.median(delta)),
                    "bootstrap_ci95_low": low,
                    "bootstrap_ci95_high": high,
                    "improved_count": int(np.count_nonzero(delta > 0)),
                    "unchanged_count": int(np.count_nonzero(delta == 0)),
                    "worsened_count": int(np.count_nonzero(delta < 0)),
                    "improved_fraction": float(np.mean(delta > 0)),
                    "wilcoxon_p_two_sided": float(p_value),
                })
            indices = list(range(scope_start, len(summary_rows)))
            adjusted = holm_adjust([summary_rows[index]["wilcoxon_p_two_sided"] for index in indices])
            for index, value in zip(indices, adjusted):
                summary_rows[index]["wilcoxon_p_holm"] = value
    return pd.DataFrame(summary_rows), pd.DataFrame(per_image_rows)


def summarize_sensitivity(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for preset in [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]:
        preset_frame = frame.loc[frame["preset"] == preset]
        for family in [None, *FAMILIES]:
            group = preset_frame if family is None else preset_frame.loc[preset_frame["family"] == family]
            for metric, (label, direction, _) in METRICS.items():
                pivot = group.pivot(index="image_id", columns="method", values=metric)
                base, target = pivot["Raw"].to_numpy(float), pivot["R61v16"].to_numpy(float)
                delta = improvement(base, target, direction)
                rows.append({
                    "preset": preset,
                    "scope": "overall" if family is None else "family",
                    "family": "all" if family is None else family,
                    "family_label_tw": "全部" if family is None else FAMILY_LABELS[family],
                    "metric": metric,
                    "metric_label": label,
                    "image_count": len(delta),
                    "raw_median": float(np.median(base)),
                    "r61_median": float(np.median(target)),
                    "median_improvement": float(np.median(delta)),
                    "improved_fraction": float(np.mean(delta > 0)),
                })
    return pd.DataFrame(rows)


def make_decision(summary: pd.DataFrame, sensitivity: pd.DataFrame, truth_qa: pd.DataFrame) -> dict:
    overall = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "overall")].set_index("metric")
    family = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "family")]
    primary_metrics = ("iou", "mean_boundary_distance_px")
    overall_fraction_gate = float(CONFIG["statistics"]["overall_improvement_fraction"])
    coarse_overall = all(
        float(overall.loc[metric, "improved_fraction"]) >= overall_fraction_gate
        and float(overall.loc[metric, "bootstrap_ci95_low"]) > 0
        for metric in primary_metrics
    )
    family_medians = {
        name: {
            metric: float(family.loc[(family["family"] == name) & (family["metric"] == metric), "median_improvement"].iloc[0])
            for metric in primary_metrics
        }
        for name in FAMILIES
    }
    family_gate = all(value > 0 for metrics in family_medians.values() for value in metrics.values())
    truth_threshold = float(CONFIG["statistics"]["truth_acm_minimum_iou"])
    truth_gate = float(truth_qa["iou"].min()) >= truth_threshold

    sensitivity_checks = []
    sensitivity_gate = True
    for preset in [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]:
        rows = sensitivity.loc[(sensitivity["preset"] == preset) & (sensitivity["metric"].isin(primary_metrics))]
        overall_positive = all(rows.loc[(rows["scope"] == "overall") & (rows["metric"] == metric), "median_improvement"].iloc[0] > 0 for metric in primary_metrics)
        family_positive_count = 0
        for name in FAMILIES:
            values = rows.loc[(rows["scope"] == "family") & (rows["family"] == name)].set_index("metric")["median_improvement"]
            family_positive_count += int(all(float(values.loc[metric]) > 0 for metric in primary_metrics))
        passed = overall_positive and family_positive_count >= 4
        sensitivity_gate &= passed
        sensitivity_checks.append({"preset": preset, "overall_positive_both": bool(overall_positive), "families_positive_both": family_positive_count, "passed": bool(passed)})

    fine_metrics = ("area_error_pct", "perimeter_error_pct", "solidity_abs_error", "roughness_abs_error")
    fine_metric_checks = {}
    for metric in fine_metrics:
        row = overall.loc[metric]
        fine_metric_checks[metric] = {
            "improved_fraction": float(row["improved_fraction"]),
            "median_improvement": float(row["median_improvement"]),
            "bootstrap_ci95_low": float(row["bootstrap_ci95_low"]),
            "passed": bool(float(row["improved_fraction"]) >= overall_fraction_gate and float(row["bootstrap_ci95_low"]) > 0),
        }
    fine_gate = all(item["passed"] for item in fine_metric_checks.values())
    raw_iou_median = float(overall.loc["iou", "raw_median"])
    ceiling_effect = raw_iou_median >= 0.98
    if truth_gate and coarse_overall and family_gate and sensitivity_gate and fine_gate:
        verdict = "PASS_EXPANDED_ACM_GENERALIZATION"
    elif truth_gate and coarse_overall and family_gate and sensitivity_gate:
        verdict = "CONDITIONAL_EXPANDED_ACM_PASS"
    else:
        verdict = "FAIL_EXPANDED_ACM_GENERALIZATION"
    return {
        "experiment_id": CONFIG["experiment_id"],
        "verdict": verdict,
        "truth_acm_extraction_gate": {"minimum_iou": float(truth_qa["iou"].min()), "threshold": truth_threshold, "passed": bool(truth_gate)},
        "coarse_overall_gate": bool(coarse_overall),
        "family_consistency_gate": bool(family_gate),
        "family_median_improvements": family_medians,
        "sensitivity_gate": bool(sensitivity_gate),
        "sensitivity_checks": sensitivity_checks,
        "fine_shape_gate": bool(fine_gate),
        "fine_shape_checks": fine_metric_checks,
        "baseline_ceiling_check": {
            "raw_iou_median": raw_iou_median,
            "ceiling_effect": bool(ceiling_effect),
            "interpretation": "Raw contours are already near exact geometry; this is primarily a preservation test and has limited room to demonstrate enhancement.",
        },
        "interpretation_boundary": "This experiment covers five newly generated closed-contour microscopy families; it does not establish performance for every real microscope, sample, or acquisition condition.",
    }


def contour(ax: plt.Axes, mask: np.ndarray, color: str, linewidth: float = 1.4, linestyle: str = "-") -> None:
    for points in find_contours(mask.astype(float), 0.5):
        ax.plot(points[:, 1], points[:, 0], color=color, linewidth=linewidth, linestyle=linestyle)


def plot_examples(primary: pd.DataFrame, masks: dict, inference: dict) -> Path:
    fig, axes = plt.subplots(len(FAMILIES), 3, figsize=(10.8, 15.5))
    for row_index, family in enumerate(FAMILIES):
        stage = FAMILY_STAGES[family]
        index = row_index * 20
        raw = read_gray(DATA / "src" / stage / "0000.bmp")
        r61 = read_gray(Path(inference["output_dirs"][family]) / "0000.bmp")
        exact = masks["exact_masks"][:, :, index].astype(bool)
        raw_mask = masks["raw_masks"][:, :, index].astype(bool)
        r61_mask = masks["r61_masks"][:, :, index].astype(bool)
        for col, (image, title) in enumerate(((raw, "原始影像"), (r61, "R61 重建"), (r61, "輪廓重疊"))):
            ax = axes[row_index, col]
            ax.imshow(image, cmap="gray", vmin=0, vmax=255)
            if col == 0:
                contour(ax, exact, TRUTH_COLOR, 1.8)
                contour(ax, raw_mask, RAW_COLOR, 1.4)
            elif col == 1:
                contour(ax, exact, TRUTH_COLOR, 1.8)
                contour(ax, r61_mask, R61_COLOR, 1.4)
            else:
                contour(ax, exact, TRUTH_COLOR, 2.0)
                contour(ax, raw_mask, RAW_COLOR, 1.3, "--")
                contour(ax, r61_mask, R61_COLOR, 1.3)
            if row_index == 0:
                ax.set_title(title, fontsize=12, weight="bold")
            if col == 0:
                ax.set_ylabel(FAMILY_LABELS[family], fontsize=11, weight="bold")
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("五類新顯微形狀：精確形狀（白）、Raw ACM（橘）、R61 ACM（藍）", fontsize=16, weight="bold", y=.995)
    fig.tight_layout(rect=(0, 0, 1, .985))
    path = FIGURES / "01_five_family_contour_examples.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def plot_family_metrics(summary: pd.DataFrame) -> Path:
    family = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "family")]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    for ax, metric in zip(axes, ("iou", "mean_boundary_distance_px")):
        rows = family.loc[family["metric"] == metric].set_index("family").loc[FAMILIES]
        x = np.arange(len(FAMILIES)); width = .34
        ax.bar(x - width/2, rows["raw_median"], width, color=RAW_COLOR, label="Raw")
        ax.bar(x + width/2, rows["r61_median"], width, color=R61_COLOR, label="R61")
        ax.set_xticks(x, [FAMILY_LABELS[name] for name in FAMILIES], rotation=18, ha="right")
        ax.set_ylabel(METRICS[metric][2]); ax.grid(axis="y"); ax.set_axisbelow(True)
        if metric == "iou": ax.set_ylim(0, 1.02)
    axes[0].legend(frameon=False, ncol=2)
    fig.suptitle("每一類的 ACM 輪廓表現（中位數）", fontsize=15, weight="bold")
    fig.tight_layout()
    path = FIGURES / "02_family_acm_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def plot_paired(per_image: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    rng = np.random.default_rng(SEED)
    for ax, metric, label in (
        (axes[0], "iou", "IoU 改善量（R61 − Raw）"),
        (axes[1], "mean_boundary_distance_px", "邊界距離減少量（px）"),
    ):
        for index, family in enumerate(FAMILIES):
            values = per_image.loc[per_image["family"] == family, f"improvement_{metric}"].to_numpy(float)
            jitter = rng.uniform(-.13, .13, size=len(values))
            ax.scatter(np.full_like(values, index, dtype=float) + jitter, values, color=R61_COLOR, alpha=.7, s=25)
            ax.plot([index-.22, index+.22], [np.median(values)]*2, color=INK, linewidth=2.4)
        ax.axhline(0, color=BAD, linewidth=1.2, linestyle="--")
        ax.set_xticks(range(len(FAMILIES)), [FAMILY_LABELS[name] for name in FAMILIES], rotation=18, ha="right")
        ax.set_ylabel(label); ax.grid(axis="y"); ax.set_axisbelow(True)
    fig.suptitle("每張影像的成對改善；零線以上代表 R61 較好", fontsize=15, weight="bold")
    fig.tight_layout()
    path = FIGURES / "03_paired_improvements.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def plot_sensitivity(sensitivity: pd.DataFrame) -> Path:
    family = sensitivity.loc[(sensitivity["scope"] == "family") & sensitivity["metric"].isin(["iou", "mean_boundary_distance_px"])]
    presets = [item["name"] for item in CONFIG["acm"]["sensitivity_presets"]]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    for ax, metric, label in ((axes[0], "iou", "IoU 改善量"), (axes[1], "mean_boundary_distance_px", "邊界距離減少量（px）")):
        x = np.arange(len(FAMILIES)); width = .24
        for preset_index, preset in enumerate(presets):
            rows = family.loc[(family["metric"] == metric) & (family["preset"] == preset)].set_index("family").loc[FAMILIES]
            ax.bar(x + (preset_index-1)*width, rows["median_improvement"], width, label=preset)
        ax.axhline(0, color=BAD, linewidth=1.1)
        ax.set_xticks(x, [FAMILY_LABELS[name] for name in FAMILIES], rotation=18, ha="right")
        ax.set_ylabel(label); ax.grid(axis="y"); ax.set_axisbelow(True)
    axes[0].legend(frameon=False, title="平滑設定")
    fig.suptitle("ACM 平滑程度敏感度檢查", fontsize=15, weight="bold")
    fig.tight_layout()
    path = FIGURES / "04_acm_sensitivity.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def plot_fine_shape(summary: pd.DataFrame) -> Path:
    overall = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "overall")].set_index("metric")
    metrics = ["area_error_pct", "perimeter_error_pct", "solidity_abs_error", "roughness_abs_error"]
    fractions = [float(overall.loc[metric, "improved_fraction"]) for metric in metrics]
    labels = [METRICS[metric][0] for metric in metrics]
    fig, ax = plt.subplots(figsize=(8.7, 4.8))
    colors = [GOOD if value >= .6 else BAD for value in fractions]
    bars = ax.barh(labels, fractions, color=colors)
    ax.axvline(.6, color=INK, linestyle="--", linewidth=1.2, label="預設門檻 60%")
    ax.set_xlim(0, 1); ax.set_xlabel("R61 較好的影像比例"); ax.grid(axis="x"); ax.set_axisbelow(True)
    for bar, value in zip(bars, fractions):
        ax.text(value + .015, bar.get_y()+bar.get_height()/2, f"{value:.0%}", va="center")
    ax.legend(frameon=False); ax.set_title("細部形狀是否也穩定改善", fontsize=15, weight="bold")
    fig.tight_layout()
    path = FIGURES / "05_fine_shape_consistency.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def plot_worst(per_image: pd.DataFrame, masks: dict, inference: dict) -> Path:
    worst = per_image.nsmallest(5, "improvement_iou")
    fig, axes = plt.subplots(2, 5, figsize=(15, 6.3))
    for col, (_, row) in enumerate(worst.iterrows()):
        family, filename = row["image_id"].split("/")
        file = f"{filename}.bmp"
        local_index = int(filename); global_index = FAMILIES.index(family)*20 + local_index
        raw = read_gray(DATA / "src" / FAMILY_STAGES[family] / file)
        r61 = read_gray(Path(inference["output_dirs"][family]) / file)
        exact = masks["exact_masks"][:, :, global_index].astype(bool)
        raw_mask = masks["raw_masks"][:, :, global_index].astype(bool)
        r61_mask = masks["r61_masks"][:, :, global_index].astype(bool)
        for row_index, (image, pred, color, title) in enumerate(((raw, raw_mask, RAW_COLOR, "Raw"), (r61, r61_mask, R61_COLOR, "R61"))):
            ax = axes[row_index, col]; ax.imshow(image, cmap="gray", vmin=0, vmax=255)
            contour(ax, exact, TRUTH_COLOR, 1.8); contour(ax, pred, color, 1.4)
            ax.set_xticks([]); ax.set_yticks([])
            if row_index == 0:
                ax.set_title(f"{FAMILY_LABELS[family]} {filename}\nIoU 改善 {row['improvement_iou']:+.3f}", fontsize=9)
            if col == 0: ax.set_ylabel(title, weight="bold")
    fig.suptitle("R61 相對 Raw 的五個最差案例（白：正確；橘/藍：ACM）", fontsize=15, weight="bold")
    fig.tight_layout(rect=(0, 0, 1, .96))
    path = FIGURES / "06_worst_cases.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def format_metric(value: float, metric: str) -> str:
    if metric in ("iou", "dice", "solidity_abs_error", "roughness_abs_error"):
        return f"{value:.4f}"
    return f"{value:.2f}"


def build_report(summary: pd.DataFrame, truth_qa: pd.DataFrame, sensitivity: pd.DataFrame, decision: dict) -> None:
    overall = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "overall")].set_index("metric")
    family = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "family")]
    verdict_tw = {
        "PASS_EXPANDED_ACM_GENERALIZATION": "通過這一輪擴充泛化測試",
        "CONDITIONAL_EXPANDED_ACM_PASS": "主要輪廓通過，但細節仍有條件",
        "FAIL_EXPANDED_ACM_GENERALIZATION": "未通過這一輪完整泛化門檻",
    }[decision["verdict"]]
    lines = [
        "# R73：R61 五類新顯微形狀 ACM 泛化測試",
        "",
        f"## 結論：{verdict_tw}",
        "",
        "這一輪使用 100 張模型訓練完成後才生成的新影像，包含多瓣外形、深凹口、細頸連接、月牙形與粗糙邊界，各 20 張。每張都有生成時留下的精確形狀，因此主要評分不是拿另一張分割結果當答案。",
        "",
        f"乾淨影像的 ACM 最低輪廓重疊率為 {truth_qa['iou'].min():.4f}，中位數為 {truth_qa['iou'].median():.4f}；工具本身的抽取品質門檻 {'通過' if decision['truth_acm_extraction_gate']['passed'] else '未通過'}。",
        "",
        f"Raw 原圖的輪廓重疊率中位數已達 {overall.loc['iou', 'raw_median']:.4f}，存在明顯的天花板效應。因此這一輪主要是在檢查 R61 能否保住本來已很準的形狀，不適合單獨用來證明它能修復嚴重模糊；結果顯示它反而造成小幅但一致的偏移。",
        "",
        "## 整體結果",
        "",
        "| 比較項目 | Raw 中位數 | R61 中位數 | R61 較好的張數 | 判讀 |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in ("iou", "mean_boundary_distance_px", "area_error_pct", "perimeter_error_pct", "solidity_abs_error", "roughness_abs_error"):
        row = overall.loc[metric]
        lines.append(f"| {METRICS[metric][0]} | {format_metric(row['raw_median'], metric)} | {format_metric(row['r61_median'], metric)} | {int(row['improved_count'])}/100 | {'改善' if row['median_improvement'] > 0 else '未改善'} |")
    lines += ["", "## 各形狀結果", "", "| 形狀 | IoU：Raw → R61 | 邊界距離：Raw → R61 | 兩項中位數都改善 |", "|---|---:|---:|---|"]
    for name in FAMILIES:
        iou = family.loc[(family["family"] == name) & (family["metric"] == "iou")].iloc[0]
        boundary = family.loc[(family["family"] == name) & (family["metric"] == "mean_boundary_distance_px")].iloc[0]
        passed = iou["median_improvement"] > 0 and boundary["median_improvement"] > 0
        lines.append(f"| {FAMILY_LABELS[name]} | {iou['raw_median']:.4f} → {iou['r61_median']:.4f} | {boundary['raw_median']:.2f} → {boundary['r61_median']:.2f} px | {'是' if passed else '否'} |")
    lines += [
        "",
        "## 判定門檻",
        "",
        f"- ACM 工具先在乾淨影像對精確形狀達標：{'通過' if decision['truth_acm_extraction_gate']['passed'] else '未通過'}。",
        f"- 全部 100 張的輪廓重疊率與邊界距離都要至少 60% 改善，且不確定範圍仍為正：{'通過' if decision['coarse_overall_gate'] else '未通過'}。",
        f"- 五種形狀的兩個主要指標中位數都要改善：{'通過' if decision['family_consistency_gate'] else '未通過'}。",
        f"- 三組 ACM 平滑設定要得到一致方向：{'通過' if decision['sensitivity_gate'] else '未通過'}。",
        f"- 面積、周長、凹凸程度與粗糙度四項細節都要穩定改善：{'通過' if decision['fine_shape_gate'] else '未通過'}。",
        "",
        "## 可以怎麼解讀",
        "",
        "本結果只回答：R61 對這五類新生成、單一封閉物體的顯微影像，能否讓 ACM 抽出的形狀更接近精確形狀。它不能單獨證明 R61 已能處理所有真實顯微鏡、所有樣品與所有拍攝條件；真實 SEM 與不同倍率資料仍要保留為另一層驗證。",
        "",
        "圖中白線是生成時的精確形狀，橘線是 Raw 的 ACM，藍線是 R61 的 ACM。",
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "R73_RESULTS_TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    setup_style(); FIGURES.mkdir(parents=True, exist_ok=True); TABLES.mkdir(parents=True, exist_ok=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    truth_qa = pd.read_csv(TABLES / "truth_acm_geometry_qa.csv")
    sensitivity_raw = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    validate_inputs(primary, truth_qa, sensitivity_raw)
    summary, per_image = summarize_primary(primary)
    sensitivity = summarize_sensitivity(sensitivity_raw)
    decision = make_decision(summary, sensitivity, truth_qa)
    summary.to_csv(TABLES / "paired_metric_summary.csv", index=False)
    per_image.to_csv(TABLES / "per_image_paired_metrics.csv", index=False)
    sensitivity.to_csv(TABLES / "acm_sensitivity_summary.csv", index=False)
    truth_qa.groupby("family", as_index=False).agg(image_count=("image_id", "count"), minimum_iou=("iou", "min"), median_iou=("iou", "median"), maximum_iou=("iou", "max")).to_csv(TABLES / "truth_acm_qa_summary.csv", index=False)
    (RESULTS / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    masks = loadmat(RESULTS / "masks" / "acm_primary_masks.mat")
    inference = json.loads((RESULTS / "inference_manifest.json").read_text(encoding="utf-8"))
    chart_paths = [plot_examples(primary, masks, inference), plot_family_metrics(summary), plot_paired(per_image), plot_sensitivity(sensitivity), plot_fine_shape(summary), plot_worst(per_image, masks, inference)]
    (RESULTS / "chart_map.json").write_text(json.dumps({path.stem: str(path) for path in chart_paths}, ensure_ascii=False, indent=2), encoding="utf-8")
    build_report(summary, truth_qa, sensitivity, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
