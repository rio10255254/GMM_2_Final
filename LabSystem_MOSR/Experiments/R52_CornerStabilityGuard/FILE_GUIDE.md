# Lab R52：混合模糊加上實拍角點穩定資料，訓練 100 輪

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R51](<../R51_BlurSourceProbe/FILE_GUIDE.md>) · [下一輪 Lab R53](<../R53_RealisticDatasetCalibration/FILE_GUIDE.md>)

**一句話：** 延續 R51 的混合模糊方向，再加入 R48 的實拍角點、格線與 PSF 壓力邊界資料（共 4,000 組，每組附幾何圖），從 R51 混合 best 起步正式訓練 100 輪。latest 的大偏移角點降到 30.4%，比 R51 好，但仍比 R40 的 24.6% 差；逐角點看，它修好了一些 R51 的大錯，同時又弄壞了很多 R51 原本正確的角點。

| | |
|---|---|
| 結果 | **未採用**（100 輪後大偏移仍多） |
| 時間 | 2026-06-14 開始，06-15 完成 |
| 實驗條件 | C：實驗室顯微系統；驗證用 2025-06-05 的實拍棋盤序列（20×，51 張、358 個角點） |
| 起點 | Lab R51 混合模糊的 `best_tradeoff` |

## 這輪在問什麼

R51 的混合模糊讓典型角點變好、大偏移變多。如果把實拍角點的穩定資料加進來、訓練得更完整，能不能把大偏移壓下來？

## 怎麼做

訓練 4,000 組：圓環 550、形狀 350、顯微 250、混合模糊角點 400、實拍角點／格線／PSF 壓力邊界 1,800、實拍紋理角點 650；另有 700 組驗證。所有資料都附邊界幾何圖。100 輪正式訓練，內部 `best_tradeoff` 停在第 23 輪，最後一輪 PSNR 27.12、SSIM 0.9495。

## 結果

**實拍棋盤角點**：

| 模型 | 中位數 | 第 75 百分位 | 超過 5 px 的比例 |
|---|---:|---:|---:|
| 原圖 | 1.414 | 2.236 | 1.7% |
| Lab R40（對照） | 4.243 | 5.000 | 24.6% |
| Lab R51 混合 best | 2.828 | 9.220 | 36.9% |
| R52 best（第 23 輪） | 3.924 | 9.220 | 49.2% |
| **R52 latest（第 100 輪）** | 3.606 | 8.485 | 30.4% |

**跟 R51 混合 best 逐角點比：** 100 個原本超過 5 px 的角點被修好，77 個原本正常的角點被推到 5 px 以外。

**外部 GMF**（6/18 同一序列，Y 方向步距標準差）：R52 latest 0.2683 px，比原圖 0.2639 px 略差，在 11 個候選中排第 9。

## 讀這些數字要知道的事

1. **這次 latest 比 best 好。** 跟 R53 之後的輪次相反；內部挑選在第 23 輪就停了，跟實拍角點的結果不一致。
2. **不是加更多角點資料就好。** 報告的結論是需要一個更強的機制，阻止模型把角點的峰值移到旁邊另一條邊上。之後 R53 改走資料多樣化，R54 再回頭診斷。
3. **原報告寫「沒有外部 GMF 分數」**，那是 6/15 的狀態；6/18 的外部 GMF 包裡有 R52 latest 的分數（上面那一行）。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動、角點門檻、重建程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 精簡保留包：資料清單、訓練紀錄與曲線、三個代表模型、完整角點驗證 | 說明與資料清單在 GitHub 的 [results/archive_retained_20260813/](<results/archive_retained_20260813/README.md>)；另有 21 個檔案（173 MB）在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，分散在 7 個附件裡，目前要下載約 8.6 GB；監看圖與角點對照圖等 15 個檔案只在原電腦上 |
| 外部 GMF 分數 | [R51～R56 外部 GMF 摘要](<../../Reconstruct_Progress/20250605_checkboard_external_gmf_prepare/external_gmf_packages/20260618_recent_lab_models_r51_r56/analysis_y_displacement/Y_DISPLACEMENT_SUMMARY.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 完整的資料、訓練與重建歷史（23,858 檔、11.9 GiB）2026-08 已移到外接硬碟封存，見 [封存入口](<ARCHIVE_POINTER_R52_20260813.md>)。

## 原始報告

| 文件 | 內容 |
|---|---|
| [R52 結果](<reports/R52_RESULTS.md>) | 訓練、門檻判讀、逐角點比較、當時的外部 GMF 狀態 |
| [實拍棋盤驗證](<reports/R52_CHECKBOARD_VALIDATION.md>) | 包含 R40～R51 的完整角點表 |
| [README](<README.md>)、[MANIFEST](<MANIFEST.md>) | 資料組成、封存經過、所有輸出位置 |
| [封存入口](<ARCHIVE_POINTER_R52_20260813.md>) | 怎麼從封存恢復完整歷史 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R52_CornerStabilityGuard.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
