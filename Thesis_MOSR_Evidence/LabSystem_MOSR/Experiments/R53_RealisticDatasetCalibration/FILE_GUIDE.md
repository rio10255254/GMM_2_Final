# Lab R53：資料改回主專案的比例，從零訓練 100 輪

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R52](<../R52_CornerStabilityGuard/FILE_GUIDE.md>) · [下一輪 Lab R54](<../R54_GeometryRootCauseProbe/FILE_GUIDE.md>)

**一句話：** R46～R52 一直往資料裡塞棋盤和角點，資料越來越偏。R53 把資料包改回接近主專案的組成（圓環、形狀、顯微細節、真實邊界與背景、少量角點和 CAD 錨點，共 6,000 組），從零訓練 100 輪。過程中記憶體不足、太慢、顯示卡記憶體爆掉換了五次設定才跑完。內部驗證一路進步到最後，實拍角點卻沒過門檻，latest 更是最差之一。

| | |
|---|---|
| 結果 | **未採用**（實拍角點門檻沒過；記憶體不足等過程問題也是脈絡） |
| 時間 | 2026-06-16 |
| 實驗條件 | C：實驗室顯微系統、Lab 25 位置 PSF；驗證用 2025-06-05 的實拍棋盤序列（20×，51 張、358 個角點） |
| 訓練 | 從零 100 輪，批次 16、4 個資料讀取程序，PSF 前向損失關閉 |

## 這輪在問什麼

不再專攻角點，而是把資料調回主專案那種多樣的組成，模型的實拍角點會不會反而變好？

## 怎麼做

**資料組成**（訓練 6,000 組，另有 1,740 組驗證，確認來源沒有重疊）：

| 類型 | 數量 |
|---|---:|
| 圓環 | 700 |
| 形狀 | 700 |
| 顯微細節 | 900 |
| 混合光學角點（正式 BADS、高斯、弱 BADS 各 100） | 300 |
| 真實邊界 | 2,050 |
| 真實背景與紋理 | 950 |
| 遮罩 CAD 錨點（沿用 R49 的可信區域規則） | 400 |

**訓練過程換了五次設定：** 批次 48 顯示卡記憶體不足 → 批次 32、8 個讀取程序在第 2 輪驗證時 Windows 記憶體不足 → 4 個讀取程序、開啟 PSF 前向損失，到第 11 輪損失啟動後慢到無法接受 → 關掉 PSF 前向損失，到第 11 輪平移等變損失啟動時顯示卡記憶體又爆 → 最後批次降到 16 才完整跑完。

## 結果

**實拍棋盤角點**（門檻跟 Lab R40 比）：

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 | 門檻 |
|---|---:|---:|---:|---|
| 原圖 | 1.414 | 2.236 | 1.7% | — |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% | 基準 |
| Lab R51 混合光學 best | 2.828 | 9.220 | 36.9% | 未過 |
| Lab R52 latest | 3.606 | 8.485 | 30.4% | 未過 |
| R53 best | 3.606 | 9.899 | 40.8% | 未過 |
| R53 latest | 9.220 | 9.899 | 58.9% | 未過 |

內部驗證到第 100 輪還在進步（PSNR 26.39、SSIM 0.9353）；訓練程式挑的 `best_tradeoff` 停在第 15 輪，因為挑選視窗在第 60 輪就關了，所以 best 和 latest 都拿去重建驗證。

**外部 GMF**（6/18 同一序列）：R53 best 0.2609 px，略好於原圖的 0.2639 px；R53 latest 有 13 張沒被 GMF 計分。

## 讀這些數字要知道的事

1. **更真實的資料讓內部驗證更好看，但沒有轉移到實拍角點。** R54 把這一點列為「更多通用資料就夠」這個假設的反證。
2. **內部最好的 latest 在實拍上最危險。** 這個現象在 R55、R56 又出現了。
3. **過程問題本身也是紀錄。** 最後的設定是為了跑得完而降級（關 PSF 前向損失、批次 16），不是事先設計好的最佳設定。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動、重建、角點門檻程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub；指令見 [MANIFEST](<MANIFEST.md>) |
| 資料稽核、訓練紀錄、保留的結果 | 本資料夾 [results/](<results>) |
| 外部 GMF 分數 | [R51～R56 外部 GMF 摘要](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/Y_DISPLACEMENT_SUMMARY.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 7,740 組訓練與驗證資料只在原電腦或外接硬碟的封存上；R55、R56 用的是這批資料的修補版本。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 資料組成、五次設定的來龍去脈、最終結果 |
| [MANIFEST](<MANIFEST.md>) | 每一次訓練嘗試的資料夾與失敗原因 |
| [R53 結果](<reports/R53_RESULTS.md>) | 為什麼做這輪、CAD 與 PSF 的規則、門檻判讀 |
| [實拍棋盤驗證](<reports/R53_CHECKBOARD_VALIDATION.md>) | 完整角點表與逐角點比較 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R53_RealisticDatasetCalibration.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
