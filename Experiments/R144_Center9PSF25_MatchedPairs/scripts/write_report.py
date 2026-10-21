"""Write the canonical R143 result after all evidence gates pass."""
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
    sem = pd.read_csv(comp / "SEM_comparison.csv")
    intervals = pd.read_csv(comp / "paired_scan_intervals.csv")
    runtime = pd.read_csv(ROOT / "results/reconstruction_runtime.csv")
    selected = ["Raw", "R129", "R137-WeakPSF", "R140v2-StableUNet", "R143-PSF25-MatchedPairs"]
    d = displacement[(displacement.model.isin(selected)) & (displacement.kind == "adjacent")].set_index("model").loc[selected].reset_index()
    long = displacement[(displacement.model.isin(selected)) & (displacement.kind == "start")].set_index("model").loc[selected].reset_index()
    g = geometry[geometry.model.isin(selected)].set_index("model").loc[selected].reset_index()
    s = sem[(sem.model.isin(selected)) & (sem.mapping_candidate == 1)].set_index("model").loc[selected].reset_index()
    p = intervals[(intervals.reference.isin(["Raw", "R129", "R137-WeakPSF", "R140v2-StableUNet"])) &
                  (intervals.metric.isin(["adjacent_mae_nm", "start_mae_nm", "diameter_repeat_sd_nm", "contour_repeat_sd_nm"]))]
    top1 = Counter()
    for f in load(ROOT / "evaluation/capture_plan.json")["frames"]:
        stem = f"{f['index'] + 1:02d}.json"
        receipt = load(ROOT / "results/reconstruction" / f["run"] / stem)
        top1[receipt["PSF_indices"][0]] += 1
    t = selector["splits"]["test"]
    text = f"""# R143 實測 PSF 配對資料完整訓練結果

完成時間：{now()}。本輪依使用者要求，以 R141 相同模型架構重新從零訓練，將合成配對的模糊來源改為模型所持有的 25 顆實測 PSF。清楚場景、位移、訓練／開發／測試分組、雜訊方法和固定量測讀法保留；已驗證 8192 次更新、930 張完整實拍及 8370 次圓輪廓量測。

## 資料和訓練

- 25 顆銀行 SHA-256：`{load(ROOT / 'data/manifest.json')['measured_psf_bank_sha256']}`。
- 母場景 512／128／128；非 identity 的 460／116／116 個場景均衡分配 25 顆。原本不模糊的 52／12／12 個場景保留。平坦場景不列為 PSF 分類真值。
- 兩張位移配對影像使用同一顆已知 PSF；其清楚答案逐陣列保持 R128 來源值。原始雜訊可逐張重播；正式訓練依原 R141 規則逐輪重新抽雜訊。
- 本輪將 101×101 PSF 銀行視為原尺寸相機像素核，卷積放在既有感測器面積取樣之後。這改變了原 R128 生成順序；銀行與目前拍攝條件的絕對物理尺度仍待校準。
- 最終 checkpoint SHA-256：`{audit['checkpoint_sha256']}`。生成測試平均重建損失：{test['mean_loss']:.4f}。
- 固定生成測試可辨識 PSF 影像 {t['labeled_frames']} 張；正確 PSF 第一名 {t['top1_correct']}/{t['labeled_frames']}（{100*t['top1_fraction']:.2f}%）；前四名包含正確 PSF {t['top4_contains_correct']}/{t['labeled_frames']}（{100*t['top4_fraction']:.2f}%）。兩張同場景影像相關，不能當作獨立樣本。測試集 PSF 標記來自模擬時的指定銀行索引，不是實拍 PSF 真值。

## 30 趟實拍短步位移（nm）

{table(d, ['model','mae_nm','repeatability_nm','maximum_error_nm'], ['方法','平均絕對差','重拍波動','最大差'])}

## 30 趟實拍起點相對位移（nm）

{table(long, ['model','mae_nm','repeatability_nm','maximum_error_nm'], ['方法','平均絕對差','重拍波動','最大差'])}

## 尺寸與輪廓重拍（nm）

{table(g, ['model','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm'], ['方法','直徑波動','輪廓波動','去尺寸形狀波動'])}

## 與既有 SEM 參照的尺寸差（方向候選 1；nm）

{table(s, ['model','mean_diameter_difference_nm','full_radial_difference_nm','de_size_shape_difference_nm'], ['方法','平均直徑差','完整輪廓差','去尺寸形狀差'])}

方向候選 2 的所有數值保留於 `results/comparison/SEM_comparison.csv`，不因本次新模型重選方向。既有 PSF 的 SEM 校準來源尚未證明與這份 SEM 比較完全獨立；表中是同讀法比較，不是獨立物理尺寸準確度證明。

## 整趟配對差與範圍

以下差值為 R143 減去參照；負值表示 R143 較低。95% 區間以完整 30 趟重抽樣，不把九顆圓或 720 個方向當作獨立趟數。

{table(p, ['reference','metric','difference_nm','ci95_low','ci95_high'], ['參照','指標','平均差','95% 下界','95% 上界'])}

## PSF 選擇與速度

- 930 張實拍入選第一名分布：`{dict(sorted(top1.items()))}`。實拍沒有逐張已知的正確 PSF 編號，故僅報使用分布，不計實拍選擇準確率。
- 930 張全尺寸推論的中位時間 {float(runtime.forward_seconds.median()):.3f} 秒；含單張讀寫中位 {float(runtime.end_to_end_seconds.median()):.3f} 秒。與舊輪次執行環境不完全控制，不作固有速度排名。
- `results/selector_evaluation.json` 保留生成資料的選擇明細及前 16 個測試場景關閉光學分支的後驗診斷；開關結果不能代替重新訓練的消融。

## 判讀限制

R143 和 R140v2 同時改變光學挑選架構與訓練影像的模糊來源，因此兩者的效果差不能只歸因於替換訓練 PSF。所用 25 顆核極為相近，且它們與本次 930 張實拍的逐位置對應尚無真值標記。930 張是已用過的同樣樣本與工作階段，不是新的獨立外部保留集。短步位移、長距離、輪廓穩定和尺寸偏差分別判讀；不因訓練或量測流程完成而自動升級正式基準。

資料製作在原尺寸影像上使用銀行核；R141 原架構的光學分支則在半解析度特徵上使用同一大小的核。本輪刻意保留原模型，沒有對兩處核的物理尺度另作轉換或標定，因此不能把新結果解讀為已物理精確配對的 PSF 反卷積效果。

## 完整性

`results/final_audit.json` 已核對 8192 筆更新、930 張重建及收據雜湊、30 趟共 8370 輪廓、8370 次獨立圓重擬合，並重現 Raw/R129 的固定參照算術。原 R141 與 R140v2 檔案未被修改。
"""
    dest = ROOT / "reports/R143_RESULTS.md"
    dest.write_text(text, encoding="utf-8")
    print("REPORT_SAVED", dest)


if __name__ == "__main__":
    main()
