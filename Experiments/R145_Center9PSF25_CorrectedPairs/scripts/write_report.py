"""Write the canonical R145 result after all evidence gates pass."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now, sha
from evaluation_lock import verify as verify_evaluation_lock


def table(df: pd.DataFrame, columns: list[str], labels: list[str]) -> str:
    rows = ["| " + " | ".join(labels) + " |", "|" + "|".join(["---"] * len(labels)) + "|"]
    for _, row in df.iterrows():
        values = []
        for key in columns:
            value = row[key]
            values.append(f"{value:.3f}" if isinstance(value, (float, np.floating)) else str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def main() -> None:
    verify_evaluation_lock()
    audit = load(ROOT / "results/final_audit.json")
    assert audit["passed"]
    test = load(ROOT / "runs/formal_8192/test_final.json")
    selector = load(ROOT / "results/selector_evaluation.json")
    comp = ROOT / "results/comparison"
    displacement = pd.read_csv(comp / "displacement_summary.csv")
    geometry = pd.read_csv(comp / "shape_size_summary.csv")
    sem = pd.read_csv(comp / "SEM_corrected_size_summary.csv")
    historical_sem = pd.read_csv(comp / "SEM_comparison.csv")
    intervals = pd.read_csv(comp / "paired_scan_intervals.csv")
    runtime = pd.read_csv(ROOT / "results/reconstruction_runtime.csv")
    selected = ["Raw", "R129", "R137-WeakPSF", "R140v2-StableUNet", "R143-PSF25-MatchedPairs", "R145-Center9PSF25-CorrectedPairs"]
    d = displacement[(displacement.model.isin(selected)) & (displacement.kind == "adjacent")].set_index("model").loc[selected].reset_index()
    long = displacement[(displacement.model.isin(selected)) & (displacement.kind == "start")].set_index("model").loc[selected].reset_index()
    g = geometry[geometry.model.isin(selected)].set_index("model").loc[selected].reset_index()
    s = sem[sem.model.isin(selected)].set_index("model").loc[selected].reset_index()
    historical_sem_mean = float(historical_sem[(historical_sem.model == "Raw") & (historical_sem.mapping_candidate == 1)].SEM_mean_diameter_nm.iloc[0])
    fitting_sem_mean = float(s.SEM_mean_diameter_nm.iloc[0])
    p = intervals[(intervals.reference.isin(["Raw", "R129", "R137-WeakPSF", "R140v2-StableUNet", "R143-PSF25-MatchedPairs"])) &
                  (intervals.metric.isin(["adjacent_mae_nm", "start_mae_nm", "diameter_repeat_sd_nm", "contour_repeat_sd_nm"]))]
    top1 = Counter()
    for f in load(ROOT / "evaluation/capture_plan.json")["frames"]:
        stem = f"{f['index'] + 1:02d}.json"
        receipt = load(ROOT / "results/reconstruction" / f["run"] / stem)
        top1[receipt["PSF_indices"][0]] += 1
    t = selector["splits"]["test"]
    bank_lock = load(ROOT / "calibration/BANK_LOCK.json")
    text = f"""# R145 修正九顆方向後的實測 PSF 配對完整結果

完成時間：{now()}。本輪以 2026-09-24 重新核對九顆圓方向後的 25 顆正式 PSF，同時替換配對影像卷積和模型光學銀行；以與 R143 相同的架構、清楚場景、分組、逐場景 PSF 編號、初始種子及訓練規格，從零完成 8192 次更新。固定 930 張完整實拍與 8370 次圓量測亦全部完成。原 R143、R140v2 權重及影像不更改；先前方向錯誤的 R144 中止記錄分開保留。

## 資料和訓練

- 修正後來源 MAT SHA-256：`{bank_lock['source_mat_sha256']}`；本包 25 顆銀行 SHA-256：`{load(ROOT / 'data/manifest.json')['measured_psf_bank_sha256']}`。列優先 5×5，物面每像素 0.1725 µm。
- 母場景 512／128／128；非 identity 的 460／116／116 個場景均衡分配 25 顆。原本不模糊的 52／12／12 個場景保留。平坦場景不列為 PSF 分類真值。
- 兩張位移配對影像使用同一顆已知 PSF；其清楚答案逐陣列保持 R128 來源值。原始雜訊可逐張重播；正式訓練依原 R141 規則逐輪重新抽雜訊。
- 原 PSF 擬合使用已知 SEM 圓柱直徑來校準成像模糊；神經訓練的清楚答案仍是 R128 合成場景，沒有使用 SEM 直徑作神經標籤。資料卷積在原尺寸影像上；模型沿用 R143 架構，在半解析度特徵上使用 101×101 銀行，兩者物理尺度未另行調整。
- 最終 checkpoint SHA-256：`{audit['checkpoint_sha256']}`。生成測試平均重建損失：{test['mean_loss']:.4f}。
- 固定生成測試可辨識 PSF 影像 {t['labeled_frames']} 張；正確 PSF 第一名 {t['top1_correct']}/{t['labeled_frames']}（{100*t['top1_fraction']:.2f}%）；前四名包含正確 PSF {t['top4_contains_correct']}/{t['labeled_frames']}（{100*t['top4_fraction']:.2f}%）。兩張同場景影像相關，不能當作獨立樣本。測試集 PSF 標記來自模擬時的指定銀行索引，不是實拍 PSF 真值。

## 30 趟實拍短步位移（nm）

{table(d, ['model','mae_nm','repeatability_nm','maximum_error_nm'], ['方法','平均絕對差','重拍波動','最大差'])}

## 30 趟實拍起點相對位移（nm）

{table(long, ['model','mae_nm','repeatability_nm','maximum_error_nm'], ['方法','平均絕對差','重拍波動','最大差'])}

## 尺寸與輪廓重拍（nm）

{table(g, ['model','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'], ['方法','直徑波動','輪廓波動','去尺寸形狀波動'])}

## 與 PSF 校準所用同九顆 SEM 參照的尺寸差（修正編號；nm）

{table(s, ['model','mean_diameter_difference_nm','mean_absolute_pillar_difference_nm','max_absolute_pillar_difference_nm'], ['方法','平均直徑差','逐顆絕對差平均','逐顆絕對差最大'])}

九顆圓按已核對的影像位置對應 SEM 編號 36、35、34／30、29、28／24、23、22；逐顆結果見 `results/comparison/SEM_corrected_size_by_pillar.csv`。舊輪廓方向候選留在 `results/comparison/SEM_comparison.csv`，不拿來取代本表的已確認編號。SEM 直徑是新 PSF 擬合的合理校準輸入，**不是神經訓練標籤**；此處使用同九顆的同一 SEM 表，屬校準條件下的同樣本尺寸對照，不是獨立外部尺寸準確度證明。

本輪 PSF 擬合所讀的 Excel 九顆平均直徑為 {fitting_sem_mean:.3f} nm；舊輪廓參照點位與原比例換算所得為 {historical_sem_mean:.3f} nm，兩者相差 {fitting_sem_mean-historical_sem_mean:.3f} nm。故上表採本輪實際校準值；沿用舊參照所得的尺寸差仍保留在 `SEM_comparison.csv`，不能將兩者視為同一數值來源。

## 整趟配對差與範圍

以下差值為 R145 減去參照；負值表示 R145 較低。95% 區間以完整 30 趟重抽樣，不把九顆圓或 720 個方向當作獨立趟數。

{table(p, ['reference','metric','difference_nm','ci95_low','ci95_high'], ['參照','指標','平均差','95% 下界','95% 上界'])}

## PSF 選擇與速度

- 930 張實拍入選第一名分布：`{dict(sorted(top1.items()))}`。實拍沒有逐張已知的正確 PSF 編號，故僅報使用分布，不計實拍選擇準確率。
- 930 張全尺寸推論的中位時間 {float(runtime.forward_seconds.median()):.3f} 秒；含單張讀寫中位 {float(runtime.end_to_end_seconds.median()):.3f} 秒。與舊輪次執行環境不完全控制，不作固有速度排名。
- `results/selector_evaluation.json` 保留生成資料的選擇明細及前 16 個測試場景關閉光學分支的後驗診斷；開關結果不能代替重新訓練的消融。

## 判讀限制

R145 與 R143 的模型架構、清楚答案及 PSF 索引指派相同，故兩者的比較較能檢查更換銀行及相應模糊資料的合併效果；仍不是單獨檢驗 PSF 校準每一項擬合選擇。新 PSF 的九顆 SEM 直徑校準、同樣本大小比較以及沒有逐張實拍 PSF 真值，均限制絕對尺寸與選擇準確率的宣稱。固定 930 張曾在多輪使用，不能稱全新外部保留集。短步位移、長距離、輪廓穩定和尺寸對照分開判讀，不因程序完成自動升級正式基準。

資料製作在原尺寸影像上使用銀行核；原 R141 架構的光學分支在半解析度特徵上使用同一大小的核。本輪為保持與 R143 可比而保留原架構，沒有對兩處核的物理尺度另作轉換，因此不能把新結果解讀為已物理精確配對的 PSF 反卷積效果。

## 完整性

`results/final_audit.json` 已核對 8192 筆更新、930 張重建及收據雜湊、30 趟共 8370 輪廓、8370 次獨立圓重擬合，並重現 Raw/R129 的固定參照算術。新 PSF 的原始 MAT、R143 與 R140v2 檔案均不由本輪更改。
"""
    dest = ROOT / "reports/R145_RESULTS.md"
    dest.write_text(text, encoding="utf-8")
    print("REPORT_SAVED", dest)


if __name__ == "__main__":
    main()
