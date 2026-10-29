from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
os.environ["GMM_ACM_EXPERIMENT_ROOT"] = str(ROOT)
BASE_PATH = Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/scripts/analyze_r73.py'))
spec = importlib.util.spec_from_file_location("r73_analysis_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)

CONFIG = base.CONFIG
DATA = base.DATA
RESULTS = base.RESULTS
TABLES = base.TABLES
FIGURES = base.FIGURES
REPORTS = base.REPORTS
FAMILIES = base.FAMILIES
FAMILY_LABELS = base.FAMILY_LABELS
FAMILY_STAGES = base.FAMILY_STAGES
PRIMARY_METRICS = ("iou", "mean_boundary_distance_px")


def shape_summary(per_image: pd.DataFrame, manifest: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    shape_by_id = {row["image_id"]: row["shape_family"] for row in manifest["records"]}
    enriched = per_image.copy()
    enriched["shape_family"] = enriched["image_id"].map(shape_by_id)
    if enriched["shape_family"].isna().any():
        raise ValueError("Missing shape-family mapping for one or more frozen images")
    expected_shapes = list(CONFIG["dataset"]["shape_families"])
    rows: list[dict] = []
    for shape in expected_shapes:
        group = enriched.loc[enriched["shape_family"] == shape]
        if len(group) != 20:
            raise ValueError(f"Expected 20 images for shape family {shape}, got {len(group)}")
        for metric, (label, _, _) in base.METRICS.items():
            improvement = group[f"improvement_{metric}"].to_numpy(float)
            rows.append({
                "shape_family": shape,
                "metric": metric,
                "metric_label": label,
                "image_count": len(group),
                "raw_median": float(group[f"raw_{metric}"].median()),
                "r61_median": float(group[f"r61_{metric}"].median()),
                "median_improvement": float(np.median(improvement)),
                "improved_count": int(np.count_nonzero(improvement > 0)),
                "improved_fraction": float(np.mean(improvement > 0)),
            })
    return enriched, pd.DataFrame(rows)


def make_decision(summary: pd.DataFrame, sensitivity: pd.DataFrame, truth_qa: pd.DataFrame,
                  shapes: pd.DataFrame, difficulty: dict) -> dict:
    inherited = base.make_decision(summary, sensitivity, truth_qa)
    shape_primary = shapes.loc[shapes["metric"].isin(PRIMARY_METRICS)]
    shape_gate = bool((shape_primary["median_improvement"] > 0).all())
    shape_checks = {
        shape: {
            metric: float(shape_primary.loc[
                (shape_primary["shape_family"] == shape) & (shape_primary["metric"] == metric),
                "median_improvement",
            ].iloc[0])
            for metric in PRIMARY_METRICS
        }
        for shape in CONFIG["dataset"]["shape_families"]
    }
    difficulty_gate = bool(
        difficulty.get("passed")
        and not difficulty.get("uses_r61")
        and int(difficulty.get("image_count", 0)) == int(CONFIG["dataset"]["total_images"])
    )
    core_pass = all((
        difficulty_gate,
        inherited["truth_acm_extraction_gate"]["passed"],
        inherited["coarse_overall_gate"],
        inherited["family_consistency_gate"],
        shape_gate,
        inherited["sensitivity_gate"],
    ))
    if core_pass and inherited["fine_shape_gate"]:
        verdict = "PASS_HARD_ACM_GENERALIZATION"
    elif core_pass:
        verdict = "CONDITIONAL_HARD_ACM_PASS"
    else:
        verdict = "FAIL_HARD_ACM_GENERALIZATION"
    overall = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "overall")].set_index("metric")
    return {
        "experiment_id": CONFIG["experiment_id"],
        "verdict": verdict,
        "raw_only_difficulty_gate": {
            "passed": difficulty_gate,
            "uses_r61": bool(difficulty.get("uses_r61", True)),
            "overall_median_raw_iou": float(difficulty["overall_median_raw_iou"]),
            "informative_family_count": int(difficulty["informative_family_count"]),
        },
        "truth_acm_extraction_gate": inherited["truth_acm_extraction_gate"],
        "coarse_overall_gate": inherited["coarse_overall_gate"],
        "challenge_consistency_gate": inherited["family_consistency_gate"],
        "challenge_median_improvements": inherited["family_median_improvements"],
        "shape_consistency_gate": shape_gate,
        "shape_median_improvements": shape_checks,
        "sensitivity_gate": inherited["sensitivity_gate"],
        "sensitivity_checks": inherited["sensitivity_checks"],
        "fine_shape_gate": inherited["fine_shape_gate"],
        "fine_shape_checks": inherited["fine_shape_checks"],
        "baseline_ceiling_check": {
            "raw_iou_median": float(overall.loc["iou", "raw_median"]),
            "ceiling_effect": bool(float(overall.loc["iou", "raw_median"]) >= 0.98),
            "interpretation": "The Raw-only gate was frozen before R61 inference; an overall Raw IoU below 0.95 is treated as non-ceiling evidence.",
        },
        "interpretation_boundary": "This is a frozen synthetic hard-microscopy contour test across five acquisition challenges and five shape families; it does not prove universal performance for every real microscope or sample.",
    }


def plot_examples(masks: dict, inference: dict) -> Path:
    fig, axes = plt.subplots(len(FAMILIES), 3, figsize=(10.8, 15.5))
    for row_index, family in enumerate(FAMILIES):
        stage = FAMILY_STAGES[family]
        global_index = row_index * 20
        raw = base.read_gray(DATA / "src" / stage / "0000.bmp")
        r61 = base.read_gray(Path(inference["output_dirs"][family]) / "0000.bmp")
        exact = masks["exact_masks"][:, :, global_index].astype(bool)
        raw_mask = masks["raw_masks"][:, :, global_index].astype(bool)
        r61_mask = masks["r61_masks"][:, :, global_index].astype(bool)
        for col, (image, title) in enumerate(((raw, "原始影像"), (r61, "R61 重建"), (r61, "輪廓重疊"))):
            ax = axes[row_index, col]
            ax.imshow(image, cmap="gray", vmin=0, vmax=255)
            if col == 0:
                base.contour(ax, exact, base.TRUTH_COLOR, 1.8)
                base.contour(ax, raw_mask, base.RAW_COLOR, 1.4)
            elif col == 1:
                base.contour(ax, exact, base.TRUTH_COLOR, 1.8)
                base.contour(ax, r61_mask, base.R61_COLOR, 1.4)
            else:
                base.contour(ax, exact, base.TRUTH_COLOR, 2.0)
                base.contour(ax, raw_mask, base.RAW_COLOR, 1.3, "--")
                base.contour(ax, r61_mask, base.R61_COLOR, 1.3)
            if row_index == 0:
                ax.set_title(title, fontsize=12, weight="bold")
            if col == 0:
                ax.set_ylabel(FAMILY_LABELS[family], fontsize=11, weight="bold")
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("五種困難拍攝條件：精確形狀（白）、Raw ACM（橘）、R61 ACM（藍）", fontsize=16, weight="bold", y=.995)
    fig.tight_layout(rect=(0, 0, 1, .985))
    path = FIGURES / "01_hard_condition_contour_examples.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def plot_difficulty(difficulty_family: pd.DataFrame) -> Path:
    rows = difficulty_family.set_index("family").loc[FAMILIES]
    values = rows["median_raw_iou_translation"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.axhspan(.65, .95, color="#DCFCE7", alpha=.65, label="有效難度區間 0.65–0.95")
    ax.axhline(.97, color=base.BAD, linestyle="--", linewidth=1.2, label="每組上限 0.97")
    bars = ax.bar([FAMILY_LABELS[name] for name in FAMILIES], values, color=base.RAW_COLOR)
    ax.set_ylim(0, 1.02); ax.set_ylabel("Raw ACM 輪廓重疊率中位數")
    ax.tick_params(axis="x", rotation=16); ax.grid(axis="y"); ax.set_axisbelow(True)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, value + .018, f"{value:.3f}", ha="center", fontsize=10)
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("R61 進場前已凍結的 Raw 難度", fontsize=15, weight="bold")
    fig.tight_layout()
    path = FIGURES / "00_raw_difficulty_gate.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def build_report(summary: pd.DataFrame, truth_qa: pd.DataFrame, shapes: pd.DataFrame,
                 difficulty_family: pd.DataFrame, decision: dict) -> None:
    overall = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "overall")].set_index("metric")
    challenge = summary.loc[(summary["alignment"] == "translation_only") & (summary["scope"] == "family")]
    verdict_tw = {
        "PASS_HARD_ACM_GENERALIZATION": "通過這一輪困難顯微輪廓測試",
        "CONDITIONAL_HARD_ACM_PASS": "主要輪廓通過，但細部形狀仍有條件",
        "FAIL_HARD_ACM_GENERALIZATION": "未通過這一輪困難顯微輪廓門檻",
    }[decision["verdict"]]
    lines = [
        "# R74：R61 困難顯微影像 ACM 泛化測試",
        "",
        f"## 結論：{verdict_tw}",
        "",
        "這 100 張影像在 R61 完全未參與的情況下，先用 Raw 的 ACM 結果校正難度並凍結。五種困難條件各 20 張，且每組都平均包含五種形狀；凍結後才執行 R61 重建。",
        "",
        f"Raw 整體輪廓重疊率中位數為 {decision['raw_only_difficulty_gate']['overall_median_raw_iou']:.4f}，不再有上一輪接近 1.0 的天花板。乾淨真值的 ACM 最低重疊率為 {truth_qa['iou'].min():.4f}，表示評分工具本身仍可靠。",
        "",
        "## 整體結果",
        "",
        "| 比較項目 | Raw 中位數 | R61 中位數 | R61 較好的張數 | 中位數方向 |",
        "|---|---:|---:|---:|---|",
    ]
    for metric in ("iou", "mean_boundary_distance_px", "area_error_pct", "perimeter_error_pct", "solidity_abs_error", "roughness_abs_error"):
        row = overall.loc[metric]
        lines.append(f"| {base.METRICS[metric][0]} | {base.format_metric(row['raw_median'], metric)} | {base.format_metric(row['r61_median'], metric)} | {int(row['improved_count'])}/100 | {'改善' if row['median_improvement'] > 0 else '未改善'} |")
    lines += ["", "## 五種困難條件", "", "| 條件 | Raw → R61 輪廓重疊率 | Raw → R61 邊界距離 | 兩項中位數都改善 |", "|---|---:|---:|---|"]
    for name in FAMILIES:
        iou = challenge.loc[(challenge["family"] == name) & (challenge["metric"] == "iou")].iloc[0]
        boundary = challenge.loc[(challenge["family"] == name) & (challenge["metric"] == "mean_boundary_distance_px")].iloc[0]
        passed = iou["median_improvement"] > 0 and boundary["median_improvement"] > 0
        lines.append(f"| {FAMILY_LABELS[name]} | {iou['raw_median']:.4f} → {iou['r61_median']:.4f} | {boundary['raw_median']:.2f} → {boundary['r61_median']:.2f} px | {'是' if passed else '否'} |")
    lines += ["", "## 五種形狀的一致性", "", "| 形狀 | IoU 改善中位數 | 邊界距離減少中位數 | 兩項都改善 |", "|---|---:|---:|---|"]
    for shape in CONFIG["dataset"]["shape_families"]:
        iou = shapes.loc[(shapes["shape_family"] == shape) & (shapes["metric"] == "iou")].iloc[0]
        boundary = shapes.loc[(shapes["shape_family"] == shape) & (shapes["metric"] == "mean_boundary_distance_px")].iloc[0]
        passed = iou["median_improvement"] > 0 and boundary["median_improvement"] > 0
        lines.append(f"| {shape} | {iou['median_improvement']:+.4f} | {boundary['median_improvement']:+.2f} px | {'是' if passed else '否'} |")
    lines += [
        "",
        "## 門檻結果",
        "",
        f"- Raw 難度先校正並凍結：{'通過' if decision['raw_only_difficulty_gate']['passed'] else '未通過'}。",
        f"- ACM 對乾淨真值的抽取品質：{'通過' if decision['truth_acm_extraction_gate']['passed'] else '未通過'}。",
        f"- 全部 100 張的輪廓重疊率與邊界距離都要至少 60% 改善，且不確定範圍仍為正：{'通過' if decision['coarse_overall_gate'] else '未通過'}。",
        f"- 五種困難條件的兩項中位數都要改善：{'通過' if decision['challenge_consistency_gate'] else '未通過'}。",
        f"- 五種形狀的兩項中位數都要改善：{'通過' if decision['shape_consistency_gate'] else '未通過'}。",
        f"- 三組 ACM 平滑設定方向一致：{'通過' if decision['sensitivity_gate'] else '未通過'}。",
        f"- 面積、周長、凹凸程度與粗糙度四項細節都穩定改善：{'通過' if decision['fine_shape_gate'] else '未通過'}。",
        "",
        "## 解讀限制",
        "",
        "這一輪能回答 R61 是否能處理五種特別設計的困難顯微成像干擾，不能直接外推成任何顯微鏡、任何倍率或任何真實樣品都一定有效。真實 50 倍與 SEM 結果仍是另一層必要證據。",
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "R74_RESULTS_TW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    base.setup_style(); FIGURES.mkdir(parents=True, exist_ok=True); TABLES.mkdir(parents=True, exist_ok=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    truth_qa = pd.read_csv(TABLES / "truth_acm_geometry_qa.csv")
    sensitivity_raw = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    base.validate_inputs(primary, truth_qa, sensitivity_raw)
    summary, per_image = base.summarize_primary(primary)
    sensitivity = base.summarize_sensitivity(sensitivity_raw)
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    per_image, shapes = shape_summary(per_image, manifest)
    difficulty = json.loads((TABLES / "raw_difficulty_summary.json").read_text(encoding="utf-8"))
    difficulty_family = pd.read_csv(TABLES / "raw_difficulty_family_summary.csv")
    decision = make_decision(summary, sensitivity, truth_qa, shapes, difficulty)
    summary.to_csv(TABLES / "paired_metric_summary.csv", index=False)
    per_image.to_csv(TABLES / "per_image_paired_metrics.csv", index=False)
    sensitivity.to_csv(TABLES / "acm_sensitivity_summary.csv", index=False)
    shapes.to_csv(TABLES / "shape_family_summary.csv", index=False)
    truth_qa.groupby("family", as_index=False).agg(image_count=("image_id", "count"), minimum_iou=("iou", "min"), median_iou=("iou", "median"), maximum_iou=("iou", "max")).to_csv(TABLES / "truth_acm_qa_summary.csv", index=False)
    (RESULTS / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    masks = loadmat(RESULTS / "masks" / "acm_primary_masks.mat")
    inference = json.loads((RESULTS / "inference_manifest.json").read_text(encoding="utf-8"))
    chart_paths = [
        plot_difficulty(difficulty_family), plot_examples(masks, inference),
        base.plot_family_metrics(summary), base.plot_paired(per_image),
        base.plot_sensitivity(sensitivity), base.plot_fine_shape(summary),
        base.plot_worst(per_image, masks, inference),
    ]
    (RESULTS / "chart_map.json").write_text(json.dumps({path.stem: str(path) for path in chart_paths}, ensure_ascii=False, indent=2), encoding="utf-8")
    build_report(summary, truth_qa, shapes, difficulty_family, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
