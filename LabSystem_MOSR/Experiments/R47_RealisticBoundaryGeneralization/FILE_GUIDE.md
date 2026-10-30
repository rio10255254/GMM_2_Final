# Lab R47：加入更真實的邊界與背景，訓練 200 輪

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R46](<../R46_CornerAwareFineTune/FILE_GUIDE.md>) · [下一輪 Lab R48](<../R48_RealCornerTransfer/FILE_GUIDE.md>)

**一句話：** R46 的理想棋盤角點資料轉不到實拍上，R47 改加更多更真實的邊界：硬角、交點、PSF 壓力，以及實拍棋盤的背景風格（2,700 張新答案，共 4,000 組），從 Lab R39 起步訓練 200 輪。內部驗證一路進步，但實拍角點兩個保存點都比 R40、R46 差；訓練程式挑的第 33 輪甚至最差（75% 的角點偏移超過 5 px）。

| | |
|---|---|
| 結果 | **未採用**（200 輪仍沒修好，訓練更久不等於有效） |
| 時間 | 2026-06-12～06-13 |
| 實驗條件 | C：實驗室顯微系統、Lab 25 位置 BADS PSF；驗證用 2025-06-05 的實拍棋盤序列（20×，51 張、358 個角點） |
| 起點 | Lab R39 的 latest；200 輪，每輪 900 批次 |

## 這輪在問什麼

理想的棋盤資料不夠，那加入看起來更像實拍的邊界和背景，模型能不能學到真實角點？

## 怎麼做

訓練 4,000 組：圓環、形狀、顯微各 700，邊界 1,200，實拍背景 700（另按類型分：棋盤角點 600、交點 400、實拍背景邊界 700、PSF 壓力 200）；另有 800 組驗證。新答案放在 Lab 生成資料的第 49～52 類，再用共用的 Lab PSF 程式產生模糊輸入。

## 結果

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 |
|---|---:|---:|---:|
| 原圖 | 1.414 | 2.236 | 1.7% |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% |
| Lab R46 | 4.243 | 8.485 | 48.6% |
| R47 best（第 33 輪） | 7.211 | 9.220 | 75.4% |
| R47 latest（第 200 輪） | 5.000 | 9.220 | 49.4% |

**內部驗證：** PSNR 從第 0 輪 26.46 進步到第 190 輪的 30.99，SSIM 到 0.9649。

## 讀這些數字要知道的事

1. **訓練程式在第 60 輪後就不再更新最佳保存點。** 挑選視窗設定在第 10～60 輪，之後 149 次「跳過更新」；所以 best 停在第 33 輪。
2. **後段一直在觸發邊界防護。** 200 輪中有 89 輪標記過度平滑、29 輪標記邊緣變粗、188 輪觸發邊界修正；影像越乾淨，角點越不對。
3. **外部 GMF 沒有做。** 重建影像已備妥但沒有送去計分，報告也說即使有分數也應該跟角點表一起看。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 資料報告 | [R47 真實邊界資料報告](<../../Training_Data/reports/LAB_R47_REALISTIC_BOUNDARY_DATA_20260612.md>) |
| 精簡保留包（資料清單、訓練紀錄、三個代表模型、角點驗證） | 說明在 [results/archive_retained_20260824/](<results/archive_retained_20260824/README.md>)；模型見 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 與 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 完整訓練資料、所有原始訓練與逐張重建 2026-08-24 已移到外接硬碟封存，見 [封存入口](<ARCHIVE_POINTER_20260824.md>)。

## 原始報告

| 報告 | 內容 |
|---|---|
| [R47 結果](<reports/R47_RESULTS_20260613.md>) | 200 輪訓練的指標、防護訊號與判讀 |
| [實拍棋盤驗證](<reports/R47_CHECKBOARD_VALIDATION_20260613.md>) | 角點表、資料組成與外部 GMF 狀態 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 資料與輸出位置 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R47_RealisticBoundaryGeneralization.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
