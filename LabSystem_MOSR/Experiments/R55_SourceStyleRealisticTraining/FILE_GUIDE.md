# Lab R55：把答案改回原圖的灰階風格

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R54](<../R54_GeometryRootCauseProbe/FILE_GUIDE.md>) · [下一輪 Lab R56](<../R56_LabelCoreRepairTraining/FILE_GUIDE.md>) · [從這裡起步的 Lab R57](<../R57_GeometryConstrainedMOSR/FILE_GUIDE.md>)

**一句話：** 6/17 的資料稽核發現，之前很多答案影像是硬的黑白或 CAD 風格，跟原圖的灰階差太多。R55 重建了全部 23 個資料包（51,654 組，其中 2,186 組被修），讓答案保留原圖的灰階風格、只用舊答案找邊界位置，再用 R53 的 6,000 組資料從零訓練 50 輪。best 是這條線第一個通過實拍角點門檻的模型，latest 則明顯退步；但外部 GMF 上 best 反而比原圖差一點。R57 從這個 best 起步。

| | |
|---|---|
| 結果 | **研究候選**（best 通過角點門檻、latest 退步；外部 GMF 沒有贏原圖；作為 R57 的起點） |
| 時間 | 2026-06-17 資料重建；06-18 訓練與驗證 |
| 實驗條件 | C：實驗室顯微系統；驗證用 2025-06-05 拍的實拍棋盤序列（20×，51 張、358 個角點） |
| 訓練 | 從零 50 輪，批次 16，PSF 前向損失關閉，開啟邊界幾何監督 |

## 在研究裡的位置

R46～R54 一路修角點都沒成功，R54 確認模型學得會局部 CAD 邊緣，但會把實拍影像改得太多。R55 換個角度：也許問題出在答案影像本身的風格就不像真的顯微影像。

## 這輪在問什麼

把答案改成原圖的灰階風格（不是硬的黑白），能不能改善實拍棋盤的邊緣和角點？

## 怎麼做

- **重建答案：** 所有 Lab 資料包重新產生答案，CAD 或舊答案只用來定位邊界帶，答案本身保留原圖的灰階。重建後再稽核一次，沒有任何資料包被判為高風險。
- **訓練：** 先只用 R53 那 6,000 組（修補後版本），較大的 51k 資料池先不混進來，方便跟 R53 直接比較。

## 結果

**實拍棋盤角點**（門檻是跟 Lab R40 比：中位數要更好，大偏移比例和第 75 百分位不能更差）：

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 | 門檻 |
|---|---:|---:|---:|---|
| 原圖 | 1.414 | 2.236 | 1.7% | — |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% | 基準 |
| Lab R53 best | 3.606 | 9.899 | 40.8% | 未過 |
| **R55 best** | **2.828** | **3.606** | **21.8%** | **通過** |
| R55 latest | 8.485 | 9.220 | 51.4% | 未過 |

R55 best 對 R40 的逐角點比較：59.5% 的角點更好，中位數差 −0.64 px。

**外部 GMF**（6/18 同一序列，Y 方向步距標準差）：R55 best 0.2667 px，比原圖 0.2639 px 略差，在 11 個候選中排第 8；R55 latest 0.2642 px，跟原圖差不多。

## 讀這些數字要知道的事

1. **通過的是相對門檻。** 門檻跟 R40 比；跟原圖比，R55 best 的大偏移角點仍是 21.8% 對 1.7%。
2. **角點通過不代表 GMF 變好。** 原 README 寫「準備做外部 GMF」，而 6/18 的外部 GMF 結果是 R55 best 沒有贏原圖，同一包裡角點沒過的 R56 best 反而最好（見 [Lab R56](<../R56_LabelCoreRepairTraining/FILE_GUIDE.md>)）。
3. **latest 不能用。** 訓練紀錄已經警告過度平滑，內部 PSNR／SSIM 進步的同時實拍角點退步。
4. **換到 100MG 樣品就不行了。** R57 拿 R55 best 去量 6/18 的 100MG CD，孔偏小、柱偏大，比原圖更遠離 SEM，這是 Lab 研究從角點轉到尺寸的起點。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 啟動、幾何準備、重建、角點驗證程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 答案重建工具與摘要 | [`Training_Data/scripts/rebuild_source_style_training_data.py`](<../../Training_Data/scripts/rebuild_source_style_training_data.py>)、[重建摘要](<../../Training_Data/r55_source_style_rebuild/REBUILD_SUMMARY.md>)、[重建後的風格稽核](<../../Reconstruct_Progress/20260617_r55_source_style_rebuild_audit/TRAINING_DATA_STYLE_AUDIT.md>) |
| 訓練紀錄、答案模糊稽核 | 本資料夾 [results/](<results>) |
| 外部 GMF 分數 | [R51～R56 外部 GMF 摘要](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/Y_DISPLACEMENT_SUMMARY.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 重建後的 51,654 組資料只在原電腦上；GitHub 有重建程式、摘要與清單。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 設計、資料包與訓練路徑 |
| [R55 結果](<reports/R55_RESULTS.md>) | 為什麼做這輪、門檻結果 |
| [實拍棋盤驗證](<reports/R55_CHECKBOARD_VALIDATION.md>) | 完整角點表、門檻與逐角點比較 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R55_SourceStyleRealisticTraining.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
