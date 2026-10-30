# Lab R46：第一次針對棋盤角點加資料

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [起點 Lab R39](<../R39_ShapeGeneralization/FILE_GUIDE.md>) · [下一輪 Lab R47](<../R47_RealisticBoundaryGeneralization/FILE_GUIDE.md>)

**一句話：** 6/11 第一次拿實拍棋盤做驗證，發現 Lab R39、R40 會把直角的角點位置移走，而且訓練資料裡根本沒有棋盤。R46 新增 500 張理想的棋盤角點答案，混進圓環、形狀、顯微資料（共 1,550 組），從 Lab R39 保守地訓練 25 輪。訓練本身有效，但實拍角點沒有比 R40 好：中位數一樣是 4.24 px，超過 5 px 的角點反而從 24.6% 增加到 48.6%。

| | |
|---|---|
| 結果 | **未採用**（25 輪有效但沒修好實體圓角） |
| 時間 | 2026-06-12 |
| 實驗條件 | C：實驗室顯微系統、Lab 25 位置 BADS PSF；驗證用 2025-06-05 的實拍棋盤序列（20×，51 張、358 個角點） |
| 起點 | Lab R39 的 latest（驗證品質最好的保存點） |

主專案也有一個 R46（從 R39R40 a025 起步的邊緣強化微調），跟這裡是不同的實驗；Lab R46 只借用了它的教訓：角點覆蓋很重要，但太激進的高頻調整會傷害位移穩定。

## 在研究裡的位置

Lab 的 R39、R40 是 6/8～6/9 把 COMBO 的權重搬到 Lab 光學條件上訓練出來的。6/11 的外部 GMF 在實拍棋盤上只改善 1～2%，角點驗證又發現重建會移動角點，而 R39、R40 的訓練資料裡沒有任何棋盤資料。R46 是補這個缺口的第一步，之後一路到 R56 都在修實拍角點。

## 這輪在問什麼

只要訓練資料裡有直角棋盤，模型就能保住實拍棋盤的角點嗎？

## 怎麼做

- 新增 500 張乾淨棋盤角點答案（Lab 生成資料第 48 類），各自產生 BADS PSF 與高斯兩種模糊輸入。
- 訓練 1,550 組：圓環重播 550、R39 形狀 350、R40 顯微 250、棋盤角點 400；另有 100 組棋盤角點驗證。
- 25 輪保守微調。

## 結果

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 |
|---|---:|---:|---:|
| 原圖 | 1.414 | 2.236 | 1.7% |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% |
| R46 best（第 17 輪） | 4.243 | 8.485 | 48.6% |
| R46 detail-guarded（第 15 輪） | 4.243 | 8.485 | 46.1% |
| R46 latest（第 25 輪） | 5.831 | 7.211 | 52.8% |

內部驗證：第 22 輪 PSNR 31.22、SSIM 0.9544；重建、梯度、邊緣方向損失從第 1 到第 25 輪都在下降。

## 讀這些數字要知道的事

1. **理想的合成棋盤跟實拍不一樣。** 報告的下一步是先修正棋盤資料的樣子，再談更長的訓練；R47 就是加入更真實的邊界與背景。
2. **R40 是之後所有 Lab 角點門檻的對照。** R46～R56 的「門檻」都是跟 R40 tradeoff 比，不是跟原圖比；原圖的角點最準。
3. R46 的驗證報告放在共用的 [Lab reports 資料夾](<../reports/LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md>)，不在本資料夾。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 角點資料建置、啟動程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 資料報告 | [R46 棋盤角點資料報告](<../../Training_Data/reports/LAB_R46_CHECKBOARD_CORNER_DATA_20260612.md>) |
| 精簡保留包（資料清單、訓練紀錄、三個代表模型、角點驗證） | 說明在 [results/archive_retained_20260824/](<results/archive_retained_20260824/README.md>)；模型見 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 與 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 完整訓練資料、原始訓練與逐張重建 2026-08-24 已移到外接硬碟封存，見 [封存入口](<ARCHIVE_POINTER_20260824.md>)。

## 原始報告

| 報告 | 內容 |
|---|---|
| [R46 結果](<reports/R46_RESULTS_20260612.md>) | 25 輪訓練、內部驗證與三個候選保存點 |
| [R46 實拍角點驗證](<../reports/LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md>) | 角點表與訓練資料覆蓋稽核 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 資料與輸出位置 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R46_CornerAwareFineTune.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
