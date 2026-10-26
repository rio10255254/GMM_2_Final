# R72：合成缺陷改用完整輪廓比

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R71](<../R71_R61SyntheticMicroscopyDefectGeneralization/FILE_GUIDE.md>) · [下一輪 R73](<../R73_R61ExpandedSyntheticACMGeneralization/FILE_GUIDE.md>) · [同方法的 SEM 驗證 R69](<../R69_ACMContourSEMValidation/FILE_GUIDE.md>)

**一句話：** R71 的邊緣偵測分數會受門檻影響，所以 2026-07-30 改用跟 R69、R70 同一類的 Chan–Vese ACM，只拿 R71 裡 20 張有單一封閉、刻意不規則外框的「邊緣缺損」影像，直接比完整外形。R61 的主要外框在 19/20 張更準（平均邊界距離 0.757 → 0.541 px），但周長誤差從 1.85% 增加到 6.55%：**粗外框更準、細小鋸齒被平滑**，跟 SEM 驗證的方向一致。

| | |
|---|---|
| 結果 | **分析**（粗外框有條件通過，細部形狀未通過） |
| 時間 | 2026-07-30 |
| 實驗條件 | 合成資料：R71 測試集中 20 張 `edge_defects` 影像 |
| 模型 | Lab R61 v16；COMBO 當舊參考 |

## 結果

| 指標 | 原圖 | R61 | 改善張數 |
|---|---:|---:|---:|
| 輪廓重疊率 | 0.9902 | **0.9920** | 19/20 |
| 平均邊界距離 | 0.757 px | **0.541 px** | 19/20 |
| 面積誤差 | 0.823% | **0.703%** | 20/20 |
| 周長誤差 | **1.85%** | 6.55% | — |
| 圓整度誤差 | **0.033** | 0.081 | — |

COMBO 的平均邊界距離是 1.445 px，比原圖還差。完全不平移時，R61 仍從 0.766 降到 0.615 px（18/20 張改善）；三組預先固定的 ACM 平滑設定都維持正向。

## 讀這些數字要知道的事

1. **為什麼只用 20 張：** 格網、隨機紋理、多物件混合沒有唯一封閉外框，硬套單一輪廓會比較不同東西。
2. **起點不偷看答案。** 所有方法都從同一個固定大矩形開始收縮，不用乾淨答案的輪廓當起點。
3. **最弱的五張有列出來**，包括唯一退步的那張。
4. 這是合成真值的形狀壓力測試，不是新的真實 SEM 樣品。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 執行、分析、ACM 抽取（MATLAB）程式與測試、設定 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)、[config/experiment.json](<config/experiment.json>)，已在 GitHub |
| 7 張圖 | [results/figures/](<results/figures>)，已在 GitHub |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** README 提到的 `results/tables/` 與 `results/masks/`（逐張量測、ACM 遮罩）不在 git 裡。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R72 結果](<reports/R72_RESULTS_TW.md>) | 結論、為什麼這才算形狀比較、代表輪廓、穩健性、限制與下一步 |
| [README](<README.md>) | 方法與執行方式 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R72_R61SyntheticDefectACMContourValidation.md>)。
