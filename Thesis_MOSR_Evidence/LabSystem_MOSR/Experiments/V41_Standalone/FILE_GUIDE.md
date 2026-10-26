# V41：把 R62 的探索整理成一次正式訓練

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [起點 Lab R61](<../R61_BoundaryGeneralizationUniversal/FILE_GUIDE.md>) · [資料來源 Lab R62](<../R62_TargetSampleBoost/FILE_GUIDE.md>) · [下一步 V42](<../V42_SoftLabelSNR/FILE_GUIDE.md>) · [V41 到 V42 的完整歷史](<../../../../docs/reproducibility/lab_comparisons/V42_HISTORY.md>)

**一句話：** R62 的候選是一個接一個續訓出來的（V20 → V28 → V35 → V41），模型來歷很難講清楚。V41_Standalone 改成乾淨的兩段式：從 R61 v16 起步，用 R62 累積的 11,254 組資料一次訓練 16 輪。結果 CD 比原圖好約 20%，位移只小幅改善，而且都略輸探索版的舊 V41。它的第 16 輪成了 V42 的起點。

| | |
|---|---|
| 結果 | **研究候選**（沒有直接當論文模型；V42 從它起步） |
| 時間 | 2026-07-08 完整 16 輪訓練；7/9 另試了 3 輪的 V41.1 微調 |
| 實驗條件 | C：實驗室顯微系統；驗證用 6/18 的 100MG 影像（CD）與 7/2、7/4 的位移序列 |
| 起點 | Lab R61 v16 最佳權重（不是從 R62 的 V20、V35 或探索版 V41 續訓） |
| 資料 | R62 資料包 v13 `measurement_view_safe_teacher`，11,254 組 |

這是 LabSystem 的 V41，跟主專案的 R41（環形蒸餾）無關。

## 在研究裡的位置

R62 在 7/6 跑到探索版 V41（從 V20 起步，加安全量測外圍守門）。7/7 第六章的 CD 圖曾用探索版 V41 畫過（見[封存的第六章 CD 圖](<../../../Archive/Final_Data_Figures_Superseded_20260713/20260707_chapter6_visual_cd_v41/README.md>)）。為了讓論文能講清楚模型怎麼來，7/8 開了這個獨立版本；7/9 V42 就從它的第 16 輪開始。

## 這輪在問什麼

不靠一串續訓，只從通用邊界模型（R61 v16）出發，用最終整理好的資料一次訓練，能不能得到跟探索鏈差不多的模型？

## 怎麼做

- **資料：** 資料包 v13 保留了舊的通用資料，也收了 R62 新增的目標樣品資料：SEM／實體邊界錨點、序列守門、合成位移與紋理位移、目標樣品假邊界、真實位移配對、GMF ROI 自我位移、低倍率方塊／點、多倍率原圖位移守門、穩定與形狀老師。
- **訓練：** 學習率 1.2e-7，16 輪，批次 4，AMP 關閉，Huber 為主的組合損失。

## 結果

**CD**（100MG 中心 6×6 柱與孔，平均誤差，nm）：

| 特徵 | 原圖 | 探索版 V41 | V41_Standalone | 對原圖 | 對探索版 |
|---|---:|---:|---:|---:|---:|
| 柱 | 81.26 | 59.55 | 64.60 | +20.5% | −8.5% |
| 孔 | 314.11 | 235.64 | 243.14 | +22.6% | −3.2% |

**位移**（GMF 量法標準差，5× 用方塊 ROI）：六組中五組比原圖好一點，改善大多在 1% 以內；20× 1 µm 最多 +0.92%。邊界敏感 ROI 量法下，100MG 1 µm 的步距穩定度比原圖改善約 16%，跟探索版 V41（16.75%）差不多。

**V41.1**（7/9，3 輪小學習率微調）：跟正式 V41 幾乎一樣，差異都在 1% 以內，沒有再往下用。

## 讀這些數字要知道的事

1. **「兩段式訓練」是描述方式，不代表完全獨立。** 起點 R61 v16 與 11,254 組資料都繼承了 SEM 錨點、目標樣品、位移與老師答案；SEM 也來自同一批樣品。
2. **CD 的結果比位移強。** 驗證報告自己寫，GMF 類量法是內部比較用，不能單靠它宣稱全面優於原圖；5× 兩組的結果有好有壞，應當作限制。
3. **最佳就是最後一輪。** 16 輪每一輪的綜合分數都在進步，第 16 輪是最佳，也表示訓練還沒有收斂；V42 從這裡繼續。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 訓練設計、啟動程式、測試、訓練紀錄 | 本資料夾 [V41_STANDALONE_DESIGN.md](<V41_STANDALONE_DESIGN.md>)、[scripts/](<scripts>)、[tests/](<tests>)、[logs/](<logs>)，已在 GitHub |
| V41 最佳與最終權重 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)；V42 完整包裡也有同內容的 V41 起點 |
| 驗證報告與圖表 | 封存區 [V41 完整驗證](<../../../Archive/Final_Data_Figures_Superseded_20260713/20260708_v41_standalone_full_validation/README.md>)、[V41.1 驗證](<../../../Archive/Final_Data_Figures_Superseded_20260713/20260709_v41_1_quick_finetune_validation/V41_1_LOCAL_EDGE_VALIDATION_REPORT.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 11,254 組訓練資料只在原電腦上；GitHub 有生成與增補程式（在 [Lab R62 的 scripts/](<../R62_TargetSampleBoost/scripts/README.md>)），但沒有重跑 16 輪訓練。

## 原始報告

| 報告 | 內容 |
|---|---|
| [V41 訓練設計](<V41_STANDALONE_DESIGN.md>) | 為什麼要獨立一版、資料包內容、超參數 |
| [V41 完整驗證](<../../../Archive/Final_Data_Figures_Superseded_20260713/20260708_v41_standalone_full_validation/VALIDATION_REPORT.md>) | 7/8 的 CD、GMF 與邊界敏感 ROI 位移結果 |
| [V41.1 局部邊緣驗證](<../../../Archive/Final_Data_Figures_Superseded_20260713/20260709_v41_1_quick_finetune_validation/V41_1_LOCAL_EDGE_VALIDATION_REPORT.md>) | 7/9 的 3 輪微調比較 |

封存區的資料夾是 2026-07-13 被新版論文圖表取代後原樣移過去的。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__V41_Standalone.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
