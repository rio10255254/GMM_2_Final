from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


EXPERIMENT = Path(__file__).resolve().parent
EVALUATION = EXPERIMENT / "evaluation"
METHODS = ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"]


def format_number(value: float, digits: int = 1) -> str:
    if not np.isfinite(value):
        return "—"
    return f"{value:.{digits}f}"


def markdown_table(frame: pd.DataFrame, formats: dict[str, int] | None = None) -> str:
    formats = formats or {}
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in frame.itertuples(index=False, name=None):
        values: list[str] = []
        for column, value in zip(columns, row):
            if column in formats and isinstance(value, (float, int, np.floating, np.integer)):
                values.append(format_number(float(value), formats[column]))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def method_rank(table: pd.DataFrame, metric: str) -> str:
    valid = table.loc[table[metric].notna()].sort_values(metric)
    return str(valid.iloc[0]["Method"]) if not valid.empty else "—"


def main() -> None:
    qa = json.loads((EVALUATION / "QA_REPORT.json").read_text(encoding="utf-8"))
    if qa["status"] != "PASS":
        raise RuntimeError("Final QA must pass before the report is generated")

    circular = pd.read_csv(
        EVALUATION / "circular_cd_sharpness" / "circular_feature_method_summary.csv"
    )
    displacement = pd.read_csv(
        EVALUATION / "displacement" / "displacement_pooled_common_valid.csv"
    )
    line_sharp = pd.read_csv(EVALUATION / "line" / "tables" / "line_sharpness_summary.csv")
    line_disp = pd.read_csv(EVALUATION / "line" / "tables" / "line_displacement_pooled.csv")
    runtime = pd.read_csv(EVALUATION / "runtime" / "computational_performance.csv")
    crop_manifest = pd.read_csv(EVALUATION / "images" / "crop_manifest.csv")
    via_sem = pd.read_csv(EVALUATION / "via_reference" / "via_center9_sem_reference.csv")

    circular_view = circular.loc[
        :,
        [
            "magnification",
            "morphology",
            "method",
            "midpoint_mae_nm",
            "mean_cd_interval_width_nm",
            "mean_edge_width_nm",
            "mean_ringing_ratio",
        ],
    ].copy()
    circular_view.columns = [
        "Magnification",
        "Morphology",
        "Method",
        "CD midpoint MAE (nm)",
        "CD interval width (nm)",
        "Edge width (nm)",
        "Ringing ratio",
    ]
    circular_view["Morphology"] = circular_view["Morphology"].str.title()

    displacement_view = displacement.loc[
        :,
        ["morphology", "method", "n", "mae_nm", "error_sd_nm", "mean_within_grid_nm"],
    ].copy()
    displacement_view.columns = [
        "Morphology",
        "Method",
        "Common steps",
        "MAE vs PI (nm)",
        "Error SD (nm)",
        "Within-grid disagreement (nm)",
    ]
    displacement_view["Morphology"] = displacement_view["Morphology"].str.title()

    line_sharp_view = line_sharp.loc[
        :,
        ["orientation", "method", "median_transition_width_nm", "median_overshoot_ratio"],
    ].copy()
    line_sharp_view.columns = ["Line orientation", "Method", "Edge width (nm)", "Overshoot ratio"]
    line_sharp_view["Line orientation"] = (
        line_sharp_view["Line orientation"].str.replace("_", " ").str.title()
    )

    line_disp_view = line_disp.loc[
        :,
        ["method", "step_count", "boundary_mae_nm", "boundary_error_sd_nm", "median_within_edge_mad_nm"],
    ].copy()
    line_disp_view.columns = [
        "Method",
        "Steps",
        "Boundary MAE (nm)",
        "Boundary error SD (nm)",
        "Within-edge MAD (nm)",
    ]

    runtime_view = runtime.loc[
        :,
        ["method", "parameter_count", "full_median_ms", "full_peak_gpu_memory_mb", "full_median_megapixels_per_second"],
    ].copy()
    runtime_view["parameter_count"] = runtime_view["parameter_count"] / 1e6
    runtime_view.columns = [
        "Method",
        "Parameters (M)",
        "Full-frame median (ms)",
        "Peak GPU memory (MB)",
        "Throughput (MP/s)",
    ]

    intensity_view = (
        crop_manifest.groupby("method", as_index=False)
        .agg(
            median_native_sd=("native_std", "median"),
            maximum_low_clip_percent=("clipped_low_percent", "max"),
            maximum_high_clip_percent=("clipped_high_percent", "max"),
        )
        .rename(
            columns={
                "method": "Method",
                "median_native_sd": "Median native SD",
                "maximum_low_clip_percent": "Max low clipping (%)",
                "maximum_high_clip_percent": "Max high clipping (%)",
            }
        )
    )
    intensity_view["Method"] = pd.Categorical(
        intensity_view["Method"], categories=METHODS, ordered=True
    )
    intensity_view = intensity_view.sort_values("Method").reset_index(drop=True)
    intensity_view["Method"] = intensity_view["Method"].astype(str)

    sem_mean = float(via_sem["sem_diameter_nm"].mean())
    sem_min = float(via_sem["sem_diameter_nm"].min())
    sem_max = float(via_sem["sem_diameter_nm"].max())

    raw_20_via = circular.loc[
        circular["magnification"].eq("20x")
        & circular["morphology"].eq("via")
        & circular["method"].eq("Raw")
    ].iloc[0]
    mosr_20_via = circular.loc[
        circular["magnification"].eq("20x")
        & circular["morphology"].eq("via")
        & circular["method"].eq("MOSR")
    ].iloc[0]
    via_mae_reduction = 100.0 * (
        1.0 - float(mosr_20_via["midpoint_mae_nm"]) / float(raw_20_via["midpoint_mae_nm"])
    )
    via_edge_reduction = 100.0 * (
        1.0 - float(mosr_20_via["mean_edge_width_nm"]) / float(raw_20_via["mean_edge_width_nm"])
    )

    def displacement_row(morphology: str, method: str) -> pd.Series:
        return displacement.loc[
            displacement["morphology"].eq(morphology)
            & displacement["method"].eq(method)
        ].iloc[0]

    raw_pillar_disp = displacement_row("pillar", "Raw")
    mosr_pillar_disp = displacement_row("pillar", "MOSR")
    raw_via_disp = displacement_row("via", "Raw")
    mosr_via_disp = displacement_row("via", "MOSR")
    pillar_disp_mae_reduction = 100.0 * (
        1.0 - float(mosr_pillar_disp["mae_nm"]) / float(raw_pillar_disp["mae_nm"])
    )
    via_disp_mae_reduction = 100.0 * (
        1.0 - float(mosr_via_disp["mae_nm"]) / float(raw_via_disp["mae_nm"])
    )
    pillar_grid_reduction = 100.0 * (
        1.0
        - float(mosr_pillar_disp["mean_within_grid_nm"])
        / float(raw_pillar_disp["mean_within_grid_nm"])
    )
    via_grid_reduction = 100.0 * (
        1.0
        - float(mosr_via_disp["mean_within_grid_nm"])
        / float(raw_via_disp["mean_within_grid_nm"])
    )

    line_learned = line_disp_view.loc[line_disp_view["Method"] != "Raw"]
    line_best = method_rank(line_learned, "Boundary MAE (nm)")
    line_raw_mae = float(
        line_disp_view.loc[line_disp_view["Method"].eq("Raw"), "Boundary MAE (nm)"].iloc[0]
    )
    line_best_learned_mae = float(
        line_learned.sort_values("Boundary MAE (nm)").iloc[0]["Boundary MAE (nm)"]
    )

    report = f"""# 三形貌現代模型比較：正式結果報告

## 核心結論

本次比較已把原本的 pillar 與 line 擴充為 pillar、via、line 三種形貌。Via 使用 SEM 表中的九筆半徑，全部先乘以二再作為 CD 參考；九顆 via 的平均 SEM 直徑為 {sem_mean:.1f} nm，範圍為 {sem_min:.1f}–{sem_max:.1f} nm。50× 與 20× 的樣品方向分開處理，20× 採上下反向配對。

所有方法使用同一批 Raw 預先鎖定的位移步數、同一組位置、同一個邊界規則與原生灰階。現代模型加入參數量匹配的 Compact NAFNet 與 EDSR-x1，並與 Raw、基礎 U-Net、MOSR 比較。兩個對照模型均由頭訓練，不使用外部預訓練權重；灰階輸入、輸出尺寸、資料切分、損失函數、有效批次與最佳權重規則一致。NAFNet 跑滿 30 回合，EDSR-x1 在第 15 回合驗證改善已趨緩後停止；正式推論均使用各自最低驗證誤差的權重。這項實驗比較的是架構本身，而不是以大型模型容量取得優勢。它支持的是同一樣品與同一顯微系統下的跨形貌量測轉移，不把它寫成跨樣品或跨設備的完整泛化。

20× via 是本次最清楚的新增證據：MOSR 相對 Raw 的 CD 中點 MAE 降低 {via_mae_reduction:.1f}%，10%–90% 邊界寬度降低 {via_edge_reduction:.1f}%。這代表原本因低倍率取樣而縮小、模糊的亮孔邊界，經重建後更接近 SEM 尺寸且更容易定位。另一方面，環狀振鈴也同步列出，避免把銳利化直接等同於量測正確。

位移方面，MOSR 相對 Raw 的 pillar MAE 改善 {pillar_disp_mae_reduction:.1f}%，via MAE 改善 {via_disp_mae_reduction:.1f}%；九宮格內不一致量則分別降低 {pillar_grid_reduction:.1f}% 與 {via_grid_reduction:.1f}%。不過 Base U-Net 與 EDSR 在部分位移指標更低，因此這組結果支持的是 MOSR 相對 Raw 的穩定改善，而不是所有指標全面第一。CD 也具有形貌與倍率差異：50× via 以 Base U-Net／EDSR 較接近 SEM，20× pillar 則 Raw 與 NAFNet 較接近 SEM；MOSR 的最明確優勢集中在模糊較重的 20× via。

在線寬位移的學習式方法中，邊界 MAE 最低的是 {line_best}（{line_best_learned_mae:.2f} nm），但 Raw 仍略低（{line_raw_mae:.2f} nm）。基礎 U-Net 往往得到最窄的邊界，但其對比與銳化幅度也最大，因此不能只以邊界寬度判定整體方法最好；需同時看 CD、位移、局部一致性與振鈴。

## SEM 參考與 CD、銳利度

CD 不採單一 50% 門檻作為唯一答案，而是固定掃描局部對比的 35%–65%，以上下界表示門檻敏感性。表中的 CD 中點 MAE 是上下界中點相對 SEM 的誤差；CD interval width 越小，表示邊界位置對門檻越不敏感；edge width 越小表示影像越銳利；ringing ratio 越小表示額外亮暗振盪越少。

{markdown_table(circular_view, {"CD midpoint MAE (nm)": 1, "CD interval width (nm)": 1, "Edge width (nm)": 1, "Ringing ratio": 3})}

## Pillar 與 via 位移

每個倍率與步距均只使用 Raw 運動品質排序後固定選出的 30 步。表中為五種方法共同有效步數的交集，PI 命令位移作為實驗位置參考。MAE 反映與參考步距的接近程度，error SD 反映逐步穩定性，within-grid disagreement 反映同一九宮格內九個結構是否得到一致位移。

{markdown_table(displacement_view, {"MAE vs PI (nm)": 2, "Error SD (nm)": 2, "Within-grid disagreement (nm)": 2})}

## Line 形貌

Line 沒有獨立 SEM CD，因此不宣稱絕對線寬正確；本區只比較原生邊界寬度、過衝與 60 個鎖定位移步的定位表現。

{markdown_table(line_sharp_view, {"Edge width (nm)": 1, "Overshoot ratio": 3})}

{markdown_table(line_disp_view, {"Boundary MAE (nm)": 2, "Boundary error SD (nm)": 2, "Within-edge MAD (nm)": 2})}

## 原生灰階與對比

所有比較影像均保留原生 8-bit 灰階，沒有逐張自動拉伸。Base U-Net、NAFNet 與 EDSR 的原生灰階標準差明顯高於 Raw，表示其高對比來自模型輸出，而不是顯示處理；各方法的極端灰階截斷比例仍很低。目視上，EDSR 在部分 via 與 line 背景出現光暈或紋理，NAFNet／EDSR 的 20× pillar 有較明顯稜角化；MOSR 大致保留圓形，但 20× via 形成明顯環狀輪廓。因此，20× via 的 CD 改善應解讀為外側邊界位置更接近 SEM，而不是整個灰階形貌已完全忠實還原。

{markdown_table(intensity_view, {"Median native SD": 2, "Max low clipping (%)": 3, "Max high clipping (%)": 3})}

## 計算效能

四個學習式模型的參數量均控制在約四百萬。完整影像速度以 2048×1536 影像、相同 RTX A6000、相同自動混合精度量測；基礎 U-Net、NAFNet 與 EDSR 使用正式的重疊分塊推論，MOSR 使用正式的整張影像推論，因此數字代表實際部署路徑，而不是只比較單一網路層的理論速度。

{markdown_table(runtime_view, {"Parameters (M)": 3, "Full-frame median (ms)": 1, "Peak GPU memory (MB)": 1, "Throughput (MP/s)": 2})}

## 對教授意見的實際補強程度

- 「形貌與量測目標過度專一」：已由單一 pillar 擴充到暗圓柱、亮孔洞與線條三種形貌，其中 pillar 與 via 均有 SEM CD，line 有位移與銳利度。這提供了跨亮暗極性與非圓形邊界的實驗證據，但仍屬同平台、同一樣品的形貌轉移。
- 「缺少現代深度學習比較」：已加入 Compact NAFNet 與 EDSR-x1。兩者重新使用相同資料與相同輸出尺寸由頭訓練，且參數量與基礎 U-Net、MOSR 接近，因此屬容量受控的架構比較。這已補上兩個代表性架構，但不宣稱已完成所有大型方法的全面排行。
- 「缺少計算效能」：已補上模型大小、256×256 延遲、完整 2048×1536 影像延遲、吞吐量與峰值 GPU 記憶體。
- 「PSF 漂移」：依本次範圍未做。
- 「不確定度」：留待後續，不在本次結果中擴張結論。

## 圖表使用建議

正文優先放：20× via CD 上下界、50× 三形貌邊界寬度、pillar/via 位移穩定性、line 位移、完整影像速度。各方法的原生灰階單張影像可放在對應結果前後；基礎 U-Net 的極端高對比與 MOSR 的 via 振鈴應保留，並用數值解釋其取捨。
"""
    (EVALUATION / "RESULTS_REPORT_ZH_TW.md").write_text(report, encoding="utf-8")

    overview = pd.concat(
        [
            circular_view.assign(Section="Circular CD and sharpness"),
            displacement_view.assign(Section="Displacement"),
        ],
        ignore_index=True,
        sort=False,
    )
    overview.to_csv(EVALUATION / "thesis_result_overview.csv", index=False, encoding="utf-8-sig")
    print(report)


if __name__ == "__main__":
    main()
