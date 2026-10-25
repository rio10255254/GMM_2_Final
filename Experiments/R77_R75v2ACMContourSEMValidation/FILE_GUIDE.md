# R77：R75v2 的 SEM 完整輪廓驗證

[研究時間線](<../../docs/research/TIMELINE.md>) · [被驗證的 R75v2](<../R75v2_R61ArchitectureScratchGeneralization/FILE_GUIDE.md>) · [前一輪 R76](<../R76_R75ACMContourSEMValidation/FILE_GUIDE.md>) · [下一輪 R78](<../R78_R75v2_BroadRealMicroscopeGeneralization/FILE_GUIDE.md>)

**一句話：** 2026-08-01 用跟 R69、R76 同一套 36 顆柱、12 張曝光的 SEM 完整輪廓比較檢查 R75v2。兩個預先固定的權重（合成驗證選出的第 84 輪、完成點第 100 輪）都讓 36 顆全部比原圖更接近 SEM，而且 12 張曝光全部成立；R61 v16 的平均邊界距離仍略好，周長與非圓細節兩個權重都沒過。

| | |
|---|---|
| 結果 | **分析**（粗輪廓與全曝光都通過；細形狀未通過；R61 v16 略好） |
| 時間 | 2026-08-01 |
| 實驗條件 | 與 R69 相同：12 張曝光光學影像、中心 36 顆柱與對應 SEM |
| 被驗證的模型 | R75v2 第 84 輪、第 100 輪；對照原圖、R61 v16、V42 第 120 輪、舊 R75 |

## 結果

| 檢查 | 第 84 輪 | 第 100 輪 |
|---|---|---|
| 輪廓重疊（原圖 0.9490） | 0.9570 | 0.9582 |
| 平均邊界距離（原圖 0.5697% 柱距） | 0.4561 | 0.4469 |
| 相對原圖的主要粗輪廓 | 通過（36/36） | 通過 |
| 12 張曝光全部成立 | 通過 | 通過 |
| 周長與非圓細節 | 未通過 | 未通過 |

R61 v16 的平均邊界距離 0.4413% 柱距，判定為 R61 較好；V42 是 0.5228%，判定為 R75v2 較好。第 100 輪比第 84 輪好 0.0139% 柱距。

## 讀這些數字要知道的事

1. **沒有用 SEM 挑輪次。** 第 84 輪是看 SEM 前由合成驗證選定的，第 100 輪是預先固定的完成點。
2. **舊 R75 也重新放進同一個比較**，用完全相同的原圖與 SEM 輪廓，避免不同資料或不同 ACM 結果混在一起。
3. 跟 R69 一樣，獨立樣本是 36 顆柱，12 張曝光是重複觀察。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 執行與分析程式、測試、設定 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)、[config/experiment.json](<config/experiment.json>)，已在 GitHub |
| 5 張圖 | [results/figures/](<results/figures>)，已在 GitHub |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 第 84 輪、第 100 輪各 864 筆主輪廓與 648 筆敏感度結果的表格不在 git 裡（R75v2 的完成分析確認過它們是完整的）。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R77 結果](<reports/R77_RESULTS_TW.md>) | 結論、門檻、與既有模型比較、使用限制 |
| [R75v2 完成分析](<../R75v2_R61ArchitectureScratchGeneralization/reports/COMPLETED_TRAINING_ANALYSIS_TW.md>) | 同一批數字放在訓練全貌裡的解讀 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R77_R75v2ACMContourSEMValidation.md>)。
