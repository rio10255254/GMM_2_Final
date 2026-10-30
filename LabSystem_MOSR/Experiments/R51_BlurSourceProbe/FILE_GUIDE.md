# Lab R51：換成高斯、弱 BADS 或混合模糊來訓練

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R50](<../R50_PSFControlDiagnosis/FILE_GUIDE.md>) · [下一輪 Lab R52](<../R52_CornerStabilityGuard/FILE_GUIDE.md>)

**一句話：** R50 發現正式 BADS 模糊比實拍更軟，R51 就做了三個短測：角點資料改用高斯、BADS 減半，或三種混合，其餘的圓環、形狀、顯微資料不變，都從 Lab R40 起步訓練 12 輪。混合版的角點中位偏移最好（2.83 px，R40 是 4.24 px），但超過 5 px 的大偏移角點從 24.6% 增加到 36.9%，所以沒過門檻。

| | |
|---|---|
| 結果 | **未採用**（典型角點改善，但大偏移比例上升） |
| 時間 | 2026-06-14 |
| 實驗條件 | C：實驗室顯微系統；驗證用 2025-06-05 的實拍棋盤序列（20×，51 張、358 個角點） |
| 訓練 | 三個短測，各 12 輪、每輪 80 批次，從 Lab R40 的 `best_tradeoff` 起步 |

## 這輪在問什麼

只換訓練資料裡角點的模糊來源，能不能讓實拍角點更準？

## 怎麼做

三個資料包各 1,550 組：圓環 550、形狀 350、顯微 250、角點 400；只有角點的模糊來源不同（高斯、BADS 強度 0.50，或正式 BADS／高斯／弱 BADS 各三分之一）。另有 100 組混合角點當驗證。三個短測的其他設定都一樣，比較的只是模糊來源。

## 結果

**實拍棋盤角點**（門檻跟 Lab R40 比：中位數要更好，大偏移比例不能更差）：

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 |
|---|---:|---:|---:|
| 原圖 | 1.414 | 2.236 | 1.7% |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% |
| 高斯 best | 3.606 | 9.220 | 38.0% |
| 弱 BADS best | 3.606 | 9.220 | 37.2% |
| **混合 best** | **2.828** | 9.220 | 36.9% |
| 混合 latest | 2.828 | 9.899 | 41.6% |

**外部 GMF**（6/18 同一序列，Y 方向步距標準差）：混合 best 0.2596 px，略好於原圖 0.2639 px，但跟 R40 對照（0.2581 px）差不多。

## 讀這些數字要知道的事

1. **中位數和大偏移往不同方向走。** 典型角點更接近原圖了，但更多角點被推到遠處。報告的解讀是這已經不只是模糊來源的問題，還需要訓練或挑選上的限制。
2. **R51 的驗證表裡也列出 R46～R49 的結果**，可以看到那幾輪大偏移比例在 46%～85% 之間。
3. 下一輪 R52 從混合 best 起步，加上實拍角點穩定資料，訓練 100 輪。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動、重建程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 外部 GMF 分數 | [R51～R56 外部 GMF 摘要](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/Y_DISPLACEMENT_SUMMARY.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 三個 1,550 組的資料包與重建影像只在原電腦上；資料可用 `scripts/r51_blur_source_data.py` 從 Lab 基礎資料重新組出。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R51 結果](<reports/R51_RESULTS.md>) | 三種模糊來源的設計、訓練與判讀 |
| [實拍棋盤驗證](<reports/R51_CHECKBOARD_VALIDATION.md>) | 包含 R40、R46～R49 的完整角點表與資料組成 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 資料包、訓練資料夾與驗證項目 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R51_BlurSourceProbe.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
