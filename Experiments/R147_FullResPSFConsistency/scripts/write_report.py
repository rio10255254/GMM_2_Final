"""Write the canonical fixed-native-PSF experiment result after all gates pass."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now
from evaluation_lock import verify as verify_evaluation_lock


def table(df: pd.DataFrame, columns: list[str], labels: list[str]) -> str:
    rows = ["| " + " | ".join(labels) + " |", "|" + "|".join(["---"] * len(labels)) + "|"]
    for _, row in df.iterrows():
        rendered = []
        for key in columns:
            value = row[key]
            rendered.append(f"{value:.3f}" if isinstance(value, (float, np.floating)) else str(value))
        rows.append("| " + " | ".join(rendered) + " |")
    return "\n".join(rows)


def main() -> None:
    verify_evaluation_lock()
    audit = load(ROOT / "results/final_audit.json")
    assert audit["passed"] and audit["psf_mode"] == "fixed_bank_mean_native_pixel_data_consistency"
    test = load(ROOT / "runs/formal_8192/test_final.json")
    physics = load(ROOT / "results/physics_evaluation.json")
    real_effect = load(ROOT / "results/real_physics_effect_12.json")
    preflight = load(ROOT / "results/preflight.json")
    bank_lock = load(ROOT / "calibration/BANK_LOCK.json")
    comp = ROOT / "results/comparison"
    displacement = pd.read_csv(comp / "displacement_summary.csv")
    geometry = pd.read_csv(comp / "shape_size_summary.csv")
    sem = pd.read_csv(comp / "SEM_contour_size_summary.csv")
    excel = pd.read_csv(comp / "SEM_corrected_size_summary.csv")
    intervals = pd.read_csv(comp / "paired_scan_intervals.csv")
    runtime = pd.read_csv(ROOT / "results/reconstruction_runtime.csv")
    selected = ["Raw", "R129", "R137-WeakPSF", "R140v2-StableUNet",
                "R143-PSF25-MatchedPairs", "R145-Center9PSF25-CorrectedPairs",
                "R146-SEMCoreHaloPSF25-MatchedPairs", "R147-FullResPSFConsistency"]
    adjacent = displacement[(displacement.model.isin(selected)) &
                            (displacement.kind == "adjacent")].set_index("model").loc[selected].reset_index()
    long = displacement[(displacement.model.isin(selected)) &
                        (displacement.kind == "start")].set_index("model").loc[selected].reset_index()
    shape = geometry[geometry.model.isin(selected)].set_index("model").loc[selected].reset_index()
    contour = sem[sem.model.isin(selected)].set_index("model").loc[selected].reset_index()
    excel_size = excel[excel.model.isin(selected)].set_index("model").loc[selected].reset_index()
    paired = intervals[(intervals.reference.isin(selected[:-1])) &
                       (intervals.metric.isin(["adjacent_mae_nm", "start_mae_nm",
                                             "diameter_repeat_sd_nm", "contour_repeat_sd_nm"]))]
    source_contour_mean = float(contour.SEM_contour_mean_diameter_nm.iloc[0])
    source_excel_mean = float(excel_size.SEM_mean_diameter_nm.iloc[0])
    text = f"""# R147 原尺寸 PSF 成像一致性完整結果

完成時間：{now()}。本輪沿用 R146 的同一份研究版 25 顆 PSF、768 組清晰／模糊配對、資料分組、雜訊、初始種子、影像／梯度／配對位移目標及第 8192 次固定驗證點。明確改變的是**模型處理 PSF 的方法**：用 25 顆銀行的固定平均，在原尺寸影像上計算再成像與照片的差，將其回投信號交給四次共享網路並作有界物理修正；不訓練逐張選擇器。固定 930 張實拍與 8370 顆圓完成，稽核通過。原 R146、R145、原交付 PSF 與正式基準不更改。

## 來源、訓練與原生輸出

- 指定研究 MAT SHA-256：`{bank_lock['source_mat_sha256']}`；R146 與 R147 相同銀行 SHA-256：`{bank_lock['bank_sha256']}`，`research_only=1`。九顆 SEM 真實外框校準了 PSF，沒有作神經清晰答案；後者仍是原合成場景。
- `data/manifest.json` 與 R146 完全同一份，768 組清晰及模糊影像不重做；`results/preflight.json` 核對所有檔案、來源和模型可微分路徑。第 8192 次權重 SHA-256：`{audit['checkpoint_sha256']}`。
- 原尺寸 PSF 運算與獨立卷積的最大差 {load(ROOT / 'results/native_psf_operator_validation.json')['max_full_resolution_scipy_difference']:.2e}；平坦亮度不變，中央測試點保留在中央。初始物理步長 0.3 在 40 組合成 dev 中全部改善原圖到清晰目標的差，沒有用 930 張實拍挑值。
- 最終生成測試的平均重建損失 {test['mean_loss']:.4f}。已訓練模型在 32 組固定生成測試上的後驗開關：PSF 開啟平均目標 {physics['mean_on_objective']:.4f}，關閉 {physics['mean_off_objective']:.4f}；輸出差中位 {physics['median_on_off_core_RMS_gray']:.4f} 灰階。此開關是固定模型診斷，不等於分開從零重訓。
- 最終四次物理步長：`{[round(v,4) for v in audit['physical_step_strengths']]}`。浮點重建為模型直接輸出，無影像後置處理；測量讀法只從這份輸出取圓心及輪廓。

## 30 趟實拍相鄰短步位移（nm）

{table(adjacent, ['model','mae_nm','repeatability_nm','maximum_error_nm'], ['方法','平均絕對差','重拍波動','最大差'])}

## 30 趟實拍起點相對位移（nm）

{table(long, ['model','mae_nm','repeatability_nm','maximum_error_nm'], ['方法','平均絕對差','重拍波動','最大差'])}

## 直徑及輪廓重拍（nm）

{table(shape, ['model','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'], ['方法','直徑波動','輪廓波動','去尺寸形狀波動'])}

## 同九顆 SEM 外框點位參照的尺寸差（nm）

{table(contour, ['model','mean_diameter_difference_nm','mean_absolute_pillar_difference_nm'], ['方法','平均直徑差','逐顆絕對差平均'])}

SEM 外框點位參照九顆平均直徑 {source_contour_mean:.3f} nm；先前 Excel 圓盤表平均 {source_excel_mean:.3f} nm，兩者相差 {source_excel_mean-source_contour_mean:.3f} nm。以下分開列 Excel 版本；兩者均是同九顆實物的校準條件對照，不是獨立尺寸準確度證明。

{table(excel_size, ['model','mean_diameter_difference_nm'], ['方法','平均直徑減 Excel SEM'])}

## 與完整掃描配對參照的差（nm）

以下差值為 R147 減去參照；負值表示 R147 較低。95% 區間以完整 30 趟重抽樣，不把九顆圓或輪廓方向當成獨立趟數。

{table(paired, ['reference','metric','difference_nm','ci95_low','ci95_high'], ['參照','指標','平均差','95% 下界','95% 上界'])}

## PSF 實際作用與速度

- 模式固定為 25 顆研究銀行的平均；**沒有逐張選 PSF**，因此沒有選擇準確率。跨早、中、晚 12 張實拍的同模型開關，輸出差中位 {real_effect['median_image_RMS_difference_gray']:.3f} 灰階，逐顆圓心最大差 {real_effect['max_center_difference_nm']:.3f} nm、直徑最大差 {real_effect['max_diameter_difference_nm']:.3f} nm。這是後驗開關，不等於重新訓練消融。
- 930 張全尺寸推論中位 {float(runtime.forward_seconds.median()):.3f} 秒；含單張讀寫中位 {float(runtime.end_to_end_seconds.median()):.3f} 秒。與舊輪次執行環境並非完全控制，不作固有速度排名。

## 判讀邊界與完整性

R147 相對 R146 同時改了 PSF 運算位置、使用平面、選擇方式和提供給主網路的光學信號，因此此比較評估的是**這套新處理方式的合併效果**，不能把改善或退步精確分派給其中單一步驟。固定的 930 張在多輪使用，不稱全新外部保留集；同九顆 SEM 外框參與 PSF 校準，尺寸對照不作獨立絕對準確度宣稱。是否升級任何用途需按短步、長距離、尺寸、輪廓分別決定，完成訓練不自動取代正式基準。

`results/final_audit.json` 已核對 8192 筆更新、930 張浮點重建及收據、30 趟共 8370 圓的獨立重擬合、R146 基線逐檔和算術重現。單張推論入口另與批次浮點輸出逐值比較。使用者指定研究 MAT、原交付 PSF、R146 及其他既有結果均不由本輪覆寫。
"""
    destination = ROOT / "reports/R147_RESULTS.md"
    destination.write_text(text, encoding="utf-8")
    print("REPORT_SAVED", destination)


if __name__ == "__main__":
    main()
