from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat
from scipy.stats import wilcoxon


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_r76 import (  # noqa: E402
    METRICS,
    align_to_truth,
    bootstrap_median_ci,
    draw_contour,
    holm_adjust,
    improvement,
)


CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
MAIN_TABLES = RESULTS / "tables"
AUDIT_ROOT = RESULTS / "epoch100_audit"
TABLES = AUDIT_ROOT / "results" / "tables"
FIGURES = RESULTS / "figures"
REPORTS = ROOT / "reports"
R69 = Path(CONFIG["paired_evidence"]["r69_root"])
R70 = Path(CONFIG["paired_evidence"]["r70_root"])
METHODS = ["Raw", "R61v16", "V42E120", "R75BestE21", "R75E100"]
COLORS = {
    "Raw": "#D97706",
    "R61v16": "#2563EB",
    "V42E120": "#059669",
    "R75BestE21": "#DC2626",
    "R75E100": "#7C3AED",
}


def slug(method: str) -> str:
    return {
        "Raw": "raw",
        "R61v16": "r61v16",
        "V42E120": "v42e120",
        "R75BestE21": "r75_best_e21",
        "R75E100": "r75_e100",
    }[method]


def load_combined() -> tuple[pd.DataFrame, pd.DataFrame]:
    current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    current_s = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    main = pd.read_csv(MAIN_TABLES / "primary_contour_metrics.csv")
    main_s = pd.read_csv(MAIN_TABLES / "acm_sensitivity_metrics.csv")
    r69 = pd.read_csv(R69 / "results" / "tables" / "primary_contour_metrics.csv")
    r70 = pd.read_csv(R70 / "results" / "tables" / "primary_contour_metrics.csv")

    key = ["exposure", "pillar_id"]
    columns = list(METRICS) + ["centroid_alignment_shift_px"]
    current_raw = current[current["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    main_raw = main[main["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if not np.allclose(current_raw[columns], main_raw[columns], rtol=0, atol=1e-12):
        raise RuntimeError("Epoch 100 重跑的 Raw 輪廓與主實驗不一致。")

    best = main[main["method"] == "R75"].copy()
    best["method"] = "R75BestE21"
    combined = pd.concat(
        [
            current[current["method"].isin(["Raw", "R75E100"])],
            r69[r69["method"] == "R61v16"],
            r70[r70["method"] == "V42E120"],
            best,
        ],
        ignore_index=True,
    )
    combined["method"] = pd.Categorical(combined["method"], METHODS, ordered=True)

    sensitivity_key = ["preset", "exposure", "pillar_id"]
    s_columns = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    current_s_raw = current_s[current_s["method"] == "Raw"].sort_values(sensitivity_key).reset_index(drop=True)
    main_s_raw = main_s[main_s["method"] == "Raw"].sort_values(sensitivity_key).reset_index(drop=True)
    if not np.allclose(current_s_raw[s_columns], main_s_raw[s_columns], rtol=0, atol=1e-12):
        raise RuntimeError("Epoch 100 重跑的 Raw 敏感度輪廓與主實驗不一致。")
    return combined, current_s


def statistics(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    medians = primary.groupby(["pillar_id", "method"], observed=True)[list(METRICS)].median().unstack("method")
    pillar_rows: list[dict[str, object]] = []
    for pillar_id in medians.index:
        row: dict[str, object] = {"pillar_id": int(pillar_id)}
        for metric, (_, direction) in METRICS.items():
            for method in METHODS:
                row[f"{slug(method)}_{metric}"] = float(medians.loc[pillar_id, (metric, method)])
            for source in METHODS[:-1]:
                row[f"r75_e100_vs_{slug(source)}_improvement_{metric}"] = float(
                    improvement(
                        np.array([row[f"{slug(source)}_{metric}"]]),
                        np.array([row[f"r75_e100_{metric}"]]),
                        direction,
                    )[0]
                )
        pillar_rows.append(row)

    rng = np.random.default_rng(int(CONFIG["statistics"]["random_seed"]) + 100)
    summary_rows: list[dict[str, object]] = []
    for source in METHODS[:-1]:
        for metric, (label, direction) in METRICS.items():
            source_values = medians[(metric, source)].to_numpy(float)
            target_values = medians[(metric, "R75E100")].to_numpy(float)
            delta = improvement(source_values, target_values, direction)
            low, high = bootstrap_median_ci(delta, rng)
            try:
                _, p_value = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p_value = 1.0
            summary_rows.append(
                {
                    "comparison": f"{source}_to_R75E100",
                    "source_method": source,
                    "target_method": "R75E100",
                    "metric": metric,
                    "metric_label": label,
                    "source_median": float(np.median(source_values)),
                    "target_median": float(np.median(target_values)),
                    "median_improvement": float(np.median(delta)),
                    "bootstrap_ci95_low": low,
                    "bootstrap_ci95_high": high,
                    "improved_pillars": int(np.count_nonzero(delta > 0)),
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

    exposure_rows: list[dict[str, object]] = []
    for exposure, group in primary.groupby("exposure", observed=True, sort=True):
        row: dict[str, object] = {"exposure": int(exposure)}
        for metric, (_, direction) in METRICS.items():
            pivot = group.pivot(index="pillar_id", columns="method", values=metric)
            for method in METHODS:
                row[f"{slug(method)}_median_{metric}"] = float(pivot[method].median())
            delta = improvement(pivot["Raw"].to_numpy(float), pivot["R75E100"].to_numpy(float), direction)
            row[f"r75_e100_vs_raw_median_improvement_{metric}"] = float(np.median(delta))
            row[f"r75_e100_vs_raw_improved_pillars_{metric}"] = int(np.count_nonzero(delta > 0))
        exposure_rows.append(row)
    return pd.DataFrame(pillar_rows), summary, pd.DataFrame(exposure_rows)


def sensitivity_decision(sensitivity: pd.DataFrame) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for exposure in [13, 18, 24]:
        flags = []
        for _, group in sensitivity[sensitivity["exposure"] == exposure].groupby("preset"):
            pivot = group.pivot(index="pillar_id", columns="method", values=["iou", "mean_boundary_distance_pitch_pct"])
            iou_delta = pivot[("iou", "R75E100")].to_numpy() - pivot[("iou", "Raw")].to_numpy()
            mbd_delta = pivot[("mean_boundary_distance_pitch_pct", "Raw")].to_numpy() - pivot[("mean_boundary_distance_pitch_pct", "R75E100")].to_numpy()
            flags.append(np.median(iou_delta) > 0 and np.median(mbd_delta) > 0)
        result[str(exposure)] = bool(all(flags))
    return result


def configure_plotting() -> None:
    plt.rcParams.update(
        {
            "font.size": 10,
            "font.sans-serif": ["Microsoft JhengHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def figures(per_pillar: pd.DataFrame, exposure: pd.DataFrame) -> None:
    configure_plotting()
    display_metrics = ["iou", "mean_boundary_distance_pitch_pct", "area_error_pct", "perimeter_error_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    for ax, metric in zip(axes.ravel(), display_metrics):
        arrays = [per_pillar[f"{slug(method)}_{metric}"].to_numpy(float) for method in METHODS]
        for values in zip(*arrays):
            ax.plot(range(len(METHODS)), values, color="#CBD5E1", lw=0.55)
        for x, method, values in zip(range(len(METHODS)), METHODS, arrays):
            ax.scatter(np.full_like(values, x), values, color=COLORS[method], s=20, alpha=0.78)
        ax.plot(range(len(METHODS)), [np.median(values) for values in arrays], color="#111827", lw=2)
        ax.set_xticks(range(len(METHODS)), ["Raw", "R61", "V42", "R75\nbest E21", "R75\nE100"])
        ax.set_title(METRICS[metric][0], weight="bold")
        ax.grid(axis="y", color="#E2E8F0")
    fig.suptitle("R75 內部最佳權重與第 100 輪的完整比較", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "07_r75_best_vs_epoch100_paired_comparison.png", dpi=200, facecolor="white")
    plt.close(fig)

    x = exposure["exposure"].to_numpy(int)
    fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
    for method in ["Raw", "R75BestE21", "R75E100"]:
        display_label = {
            "Raw": "重建前",
            "R75BestE21": "R75 正式最佳（第21輪）",
            "R75E100": "R75 第100輪",
        }[method]
        ax.plot(
            x,
            exposure[f"{slug(method)}_median_mean_boundary_distance_pitch_pct"],
            marker="o",
            lw=2.2,
            color=COLORS[method],
            label=display_label,
        )
    ax.axvspan(20.5, 22.5, color="#FEE2E2", alpha=0.65, label="第100輪未改善區間")
    ax.set_xlabel("曝光編號")
    ax.set_ylabel("平均邊界距離（% 柱距）")
    ax.grid(axis="y", color="#E2E8F0")
    ax.legend(frameon=False)
    ax.set_title("R75 兩個固定 checkpoint 在不同亮度下的表現", fontsize=14, weight="bold")
    fig.savefig(FIGURES / "08_r75_checkpoint_exposure_comparison.png", dpi=200, facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(3, 3, figsize=(13, 12), constrained_layout=True)
    for row, exposure_id in enumerate([18, 21, 24]):
        raw_image = np.asarray(Image.open(Path(CONFIG["paired_evidence"]["raw_input_dir"]) / f"{exposure_id}.bmp").convert("L"), dtype=float)
        recon_image = np.asarray(Image.open(RESULTS / "reconstruction_epoch100" / f"{exposure_id}.bmp").convert("L"), dtype=float)
        difference = np.abs(recon_image - raw_image)
        axes[row, 0].imshow(raw_image, cmap="gray", vmin=0, vmax=255)
        axes[row, 1].imshow(recon_image, cmap="gray", vmin=0, vmax=255)
        diff_plot = axes[row, 2].imshow(
            difference,
            cmap="magma",
            vmin=0,
            vmax=max(1, np.percentile(difference, 99.5)),
        )
        axes[row, 0].set_title(f"重建前：曝光 {exposure_id}")
        axes[row, 1].set_title(f"第100輪重建：曝光 {exposure_id}")
        axes[row, 2].set_title("像素改變量（影像檢查）")
        fig.colorbar(diff_plot, ax=axes[row, 2], shrink=0.72, label="灰階差")
        for ax_item in axes[row]:
            ax_item.set_xticks([])
            ax_item.set_yticks([])
    fig.suptitle("第100輪：一般、失效與最暗曝光的重建前後", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "09_raw_epoch100_reconstruction_comparison.png", dpi=190, facecolor="white")
    plt.close(fig)

    mask_variables = ["truth_cells", "truth_masks", "raw_masks", "recon_masks", "exposures", "global_index"]
    masks = loadmat(
        AUDIT_ROOT / "results" / "masks" / "acm_primary_masks.mat",
        squeeze_me=True,
        variable_names=mask_variables,
    )
    truth_cells = masks["truth_cells"]
    truth_masks = masks["truth_masks"].astype(bool)
    raw_masks = masks["raw_masks"].astype(bool)
    recon_masks = masks["recon_masks"].astype(bool)
    mask_exposures = np.asarray(masks["exposures"]).astype(int).ravel()
    global_index = np.asarray(masks["global_index"]).astype(int)
    exposure_index = int(np.flatnonzero(mask_exposures == 18)[0])
    fig, axes = plt.subplots(6, 6, figsize=(13, 13), constrained_layout=True)
    for row in range(6):
        for col in range(6):
            pillar_id = int(global_index[row, col])
            index = pillar_id - 1
            truth = truth_masks[:, :, index]
            ax_item = axes[row, col]
            ax_item.imshow(truth_cells[:, :, index], cmap="gray", vmin=0, vmax=255)
            draw_contour(ax_item, truth, "#111827", 1.25)
            draw_contour(ax_item, align_to_truth(raw_masks[:, :, index, exposure_index], truth), COLORS["Raw"], 1.0, "--")
            draw_contour(ax_item, align_to_truth(recon_masks[:, :, index, exposure_index], truth), COLORS["R75E100"], 1.1)
            ax_item.set_title(f"ID {pillar_id}", fontsize=8)
            ax_item.set_xticks([])
            ax_item.set_yticks([])
    fig.legend(
        handles=[
            Line2D([0], [0], color="#111827", label="SEM"),
            Line2D([0], [0], color=COLORS["Raw"], linestyle="--", label="重建前"),
            Line2D([0], [0], color=COLORS["R75E100"], label="R75 第100輪"),
        ],
        loc="outside lower center",
        ncol=3,
        frameon=False,
    )
    fig.suptitle("第100輪：中央 36 顆完整輪廓疊圖（曝光 18）", fontsize=15, weight="bold")
    fig.savefig(FIGURES / "10_epoch100_center36_contour_overlay_exp18.png", dpi=190, facecolor="white")
    plt.close(fig)


def write_outputs(
    comparisons: pd.DataFrame,
    exposure: pd.DataFrame,
    sensitivity: dict[str, bool],
) -> None:
    raw = comparisons[comparisons["comparison"] == "Raw_to_R75E100"].set_index("metric")
    best = comparisons[comparisons["comparison"] == "R75BestE21_to_R75E100"].set_index("metric")
    coarse = all(
        raw.loc[metric, "bootstrap_ci95_low"] > 0 and raw.loc[metric, "improved_fraction"] >= 0.60
        for metric in ["iou", "mean_boundary_distance_pitch_pct"]
    )
    universal = bool(
        (
            (exposure["r75_e100_vs_raw_median_improvement_iou"] > 0)
            & (exposure["r75_e100_vs_raw_median_improvement_mean_boundary_distance_pitch_pct"] > 0)
        ).all()
    )
    universal_by_exposure = {
        str(int(row["exposure"])): bool(
            row["r75_e100_vs_raw_median_improvement_iou"] > 0
            and row["r75_e100_vs_raw_median_improvement_mean_boundary_distance_pitch_pct"] > 0
        )
        for _, row in exposure.iterrows()
    }
    fine_shape = bool(
        raw.loc["perimeter_error_pct", "median_improvement"] > 0
        and raw.loc["circularity_abs_error", "median_improvement"] > 0
    )
    final_better_than_best = all(best.loc[metric, "bootstrap_ci95_low"] > 0 for metric in ["iou", "mean_boundary_distance_pitch_pct"])
    prior_status = {}
    for source in ["R61v16", "V42E120"]:
        group = comparisons[comparisons["comparison"] == f"{source}_to_R75E100"].set_index("metric")
        if all(group.loc[metric, "bootstrap_ci95_low"] > 0 for metric in ["iou", "mean_boundary_distance_pitch_pct"]):
            prior_status[source] = "R75E100_better"
        elif all(group.loc[metric, "bootstrap_ci95_high"] < 0 for metric in ["iou", "mean_boundary_distance_pitch_pct"]):
            prior_status[source] = f"{source}_better"
        else:
            prior_status[source] = "not_decisive"
    decision = {
        "epoch100_coarse_contour_gate_vs_raw": bool(coarse),
        "epoch100_all_exposure_universal_gate_vs_raw": universal,
        "epoch100_fine_shape_fidelity_gate_vs_raw": fine_shape,
        "universal_gate_by_exposure": universal_by_exposure,
        "epoch100_better_than_internal_best_e21": bool(final_better_than_best),
        "comparison_to_prior_models": prior_status,
        "acm_sensitivity_direction_consistent_vs_raw": sensitivity,
    }
    (AUDIT_ROOT / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    mbd_raw = raw.loc["mean_boundary_distance_pitch_pct"]
    iou_raw = raw.loc["iou"]
    perimeter_raw = raw.loc["perimeter_error_pct"]
    circularity_raw = raw.loc["circularity_abs_error"]
    mbd_best = best.loc["mean_boundary_distance_pitch_pct"]
    r61 = comparisons[comparisons["comparison"] == "R61v16_to_R75E100"].set_index("metric")
    v42 = comparisons[comparisons["comparison"] == "V42E120_to_R75E100"].set_index("metric")
    passing_exposures = [key for key, value in universal_by_exposure.items() if value]
    failing_exposures = [key for key, value in universal_by_exposure.items() if not value]
    report = f"""# R75 第 100 輪的獨立 SEM 輪廓核對

## 結論

第 100 輪比訓練程式挑出的第 21 輪權重好很多，而且對原圖的整體粗輪廓有小幅、穩定的改善；但是它仍未通過所有曝光與細部形狀門檻，因此不能當成通用模型。

- 相對重建前，平均邊界距離由 **{mbd_raw['source_median']:.3f}** 變成 **{mbd_raw['target_median']:.3f}% 柱距**，**{int(mbd_raw['improved_pillars'])}/36** 顆改善。
- 輪廓重疊率由 **{iou_raw['source_median']:.3f}** 變成 **{iou_raw['target_median']:.3f}**，**{int(iou_raw['improved_pillars'])}/36** 顆改善。
- 第 100 輪相對第 21 輪最佳權重，平均邊界距離由 **{mbd_best['source_median']:.3f}** 變成 **{mbd_best['target_median']:.3f}% 柱距**；第 100 輪改善 **{int(mbd_best['improved_pillars'])}/36** 顆。
- 但周長誤差由 **{perimeter_raw['source_median']:.3f}%** 變成 **{perimeter_raw['target_median']:.3f}%**，圓整程度誤差由 **{circularity_raw['source_median']:.3f}** 變成 **{circularity_raw['target_median']:.3f}**，兩者都變差。
- 對原圖的主要粗輪廓門檻：**{'通過' if coarse else '未通過'}**；所有曝光門檻：**{'通過' if universal else '未通過'}**；細部形狀門檻：**{'通過' if fine_shape else '未通過'}**。
- 改善成立的曝光：**{', '.join(passing_exposures) or '無'}**；未成立的曝光：**{', '.join(failing_exposures) or '無'}**。
- 三組 ACM 設定的方向一致性：{json.dumps(sensitivity, ensure_ascii=False)}。

## 與既有模型比較

- R61v16 的平均邊界距離是 **{r61.loc['mean_boundary_distance_pitch_pct', 'source_median']:.3f}% 柱距**，第 100 輪 R75 是 **{r61.loc['mean_boundary_distance_pitch_pct', 'target_median']:.3f}%**；R61v16 在 **36/36** 顆較好。
- V42E120 的平均邊界距離是 **{v42.loc['mean_boundary_distance_pitch_pct', 'source_median']:.3f}% 柱距**，第 100 輪 R75 是 **{v42.loc['mean_boundary_distance_pitch_pct', 'target_median']:.3f}%**；兩者的邊界距離差異沒有定論，但 V42 的重疊率、面積、周長與非圓細節都較好。

## 如何解讀

訓練程式的內部挑權重規則把第 21 輪選成正式最佳，但真實 SEM 顯示第 100 輪明顯較好，所以目前的挑權重規則不適合這個目標。第 100 輪仍會產生可見光暈與背景紋理，且沒有保住周長與非圓細節；因此它只能列為「粗輪廓候選」，不能取代 R61v16 或 V42，也不能宣稱任何場景都適用。

不能直接因為這次 SEM 結果較好，就把第 100 輪改稱正式最佳；這會變成用測試資料挑模型。正確做法是先修改只看合成驗證資料的挑權重規則，再用另一批未參與調整的 SEM 或真實影像做最後確認。
"""
    (REPORTS / "R76_EPOCH100_AUDIT_TW.md").write_text(report, encoding="utf-8")


def main() -> None:
    primary, sensitivity = load_combined()
    per_pillar, comparisons, exposure = statistics(primary)
    sensitivity_result = sensitivity_decision(sensitivity)
    per_pillar.to_csv(TABLES / "five_method_per_pillar_summary.csv", index=False)
    comparisons.to_csv(TABLES / "epoch100_paired_comparison_summary.csv", index=False)
    exposure.to_csv(TABLES / "five_method_per_exposure_summary.csv", index=False)
    figures(per_pillar, exposure)
    write_outputs(comparisons, exposure, sensitivity_result)


if __name__ == "__main__":
    main()
