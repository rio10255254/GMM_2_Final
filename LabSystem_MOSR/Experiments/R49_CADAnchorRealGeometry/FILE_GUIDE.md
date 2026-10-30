# Lab R49：用實拍棋盤配 CAD 答案

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R48](<../R48_RealCornerTransfer/FILE_GUIDE.md>) · [下一輪 Lab R50](<../R50_PSFControlDiagnosis/FILE_GUIDE.md>)

**一句話：** R48 的合成角點資料沒用，R49 改用真的實拍：從 6/13 拍的 36 組棋盤配 CAD 參考，切出可信區域內用 CAD 當答案、區域外保留原圖的錨點資料，混進 4,000 組裡訓練 100 輪。結果是這條線最差的一輪：best 的角點中位偏移 14.2 px，latest 有 85% 的角點偏移超過 5 px。

| | |
|---|---|
| 結果 | **未採用**（角點退步；CAD 答案修正量太大，又只佔一成資料） |
| 時間 | 2026-06-14 |
| 實驗條件 | C：實驗室顯微系統；錨點來自 6/13 的棋盤／CAD 參考，驗證用 2025-06-05 的實拍棋盤序列（20×，51 張、358 個角點） |
| 起點 | Lab R40 的 `best_tradeoff`，訓練 100 輪 |

## 這輪在問什麼

用少量真實的實拍影像、配上 CAD 推得的銳利答案，能不能修正 R48 的圓角問題？

## 怎麼做

訓練 4,000 組：圓環、形狀、顯微各 700，邊界 1,000，實拍紋理 500，R48 實拍角點重播 500，格線交點 300，角點 PSF 壓力 200，**CAD 錨點 400**；另有 120 組 CAD 錨點當驗證。CAD 錨點只在可信遮罩內用 CAD 答案，遮罩外保留原圖，避免學到不可信的背景。

## 結果

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 | 對原圖的平均改動 |
|---|---:|---:|---:|---:|
| 原圖 | 1.414 | 2.236 | 1.7% | 0 |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% | 1.39 |
| Lab R48 最好 | 6.708 | 9.220 | 61.5% | 1.66 |
| R49 best（第 50 輪） | 14.213 | 20.025 | 64.5% | 1.44 |
| R49 latest（第 100 輪） | 9.000 | 9.055 | 85.5% | 5.95 |

內部驗證一路進步：PSNR 從第 2 輪 24.25 到第 100 輪 27.74。

## 讀這些數字要知道的事

1. **R49 只有兩種行為。** best 和 detail-guarded 兩個檔案雜湊不同，但重建結果完全一樣。best 幾乎不改影像，卻把角點反應弄弱（邊緣強度低於原圖）；latest 改動大、出現黑白光暈，大部分角點被推走。
2. **失敗分析列出的原因：** CAD 答案跟原圖在遮罩內的差距約 0.21～0.22（正規化灰階），等於要模型把真實邊緣推成硬黑白；錨點只佔一成，被其他合成資料稀釋；6/13 的 CAD 參考和 6/5 的驗證序列不是同一個目標；挑選保存點沒有用到實拍角點指標。
3. 失敗分析裡有一段「我應該怎麼做不同」的自我檢討，原樣保留。
4. 之後 R53 的資料建置會讀 `Training_Data/r49_cad_anchor_source`，重建 R53 前要先從封存恢復這個資料夾。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 完整歷史（22,751 檔、11.2 GiB）2026-08-09 已移到外接硬碟封存，見 [封存入口](<ARCHIVE_POINTER_R49_20260809.md>)。

## 原始報告

| 報告 | 內容 |
|---|---|
| [R49 結果](<reports/R49_RESULTS_20260614.md>) | 訓練與角點結果 |
| [實拍棋盤驗證](<reports/R49_CHECKBOARD_VALIDATION_20260614.md>) | 包含 R40～R48 的完整角點表與資料組成 |
| [失敗分析](<reports/R49_FAILURE_ANALYSIS_20260614.md>) | 兩種行為、五個原因、自我檢討 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 資料、封存經過與驗證 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R49_CADAnchorRealGeometry.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
