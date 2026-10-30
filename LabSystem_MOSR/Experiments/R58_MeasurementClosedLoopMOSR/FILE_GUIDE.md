# Lab R58：只修一半的 SEM 答案

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R57](<../R57_GeometryConstrainedMOSR/FILE_GUIDE.md>) · [下一輪 Lab R59](<../R59_CDClosedLoopBoundaryLayer/FILE_GUIDE.md>) · [後來的根因分析 Lab R60](<../R60_SEMTruthBoundaryTraining/FILE_GUIDE.md>)

**一句話：** R57 發現直接把答案改成 SEM 半徑會修過頭，R58 就把答案設成「原圖量到的半徑往 SEM 走一半」，用全合成的圓形錨點訓練，並寫了自動跑完就量 CD 的流程。完整 30 輪後平均半徑誤差 53.69 nm，比原圖（38.59 nm）還差。

| | |
|---|---|
| 結果 | **分析**（刻意的部分修正，不期待到 SEM 外框；CD 比原圖差） |
| 時間 | 2026-06-21～06-22 |
| 實驗條件 | C：實驗室顯微系統；6/18 的 100MG 影像（69 nm/px）與同批樣品的 SEM |
| 訓練 | 8 輪短測；完整版 30 輪、每輪最多 512 批次 |

## 這輪在問什麼

R57.1 一次把答案拉到 SEM 半徑，結果孔和柱都修過頭。如果只修一半，模型能不能穩穩地往正確方向走？

## 怎麼做

- **答案：** `目標半徑 = 原圖半徑 + (SEM − 原圖半徑) × 0.5`。所以即使完美學會，孔仍比 SEM 小 33 nm，柱仍比 SEM 大 5.5 nm。
- **資料：** 4,096 組理想圓形的合成錨點（孔、柱各一半），加上模糊與雜訊，**沒有任何實拍裁切**；邊界、中心線、距離圖也從合成答案產生。
- **自動評分：** 每次訓練完自動重建 100MG、量 CD、跟原圖比。

## 結果

| 影像 | 平均 | 孔 | 柱 | 贏原圖 |
|---|---:|---:|---:|---|
| 原圖 | 38.59 | 66.13 | 11.04 | 基準 |
| R58 短測（8 輪） | 54.91 | 73.95 | 35.88 | 否 |
| R58 完整版（30 輪） | 53.69 | 75.08 | 32.30 | 否 |

（對 SEM 的平均絕對半徑誤差，nm。）完整版訓練到第 30 輪，驗證重建誤差和 SSIM（0.9916）一直在進步，但訓練程式選出的最佳保存點停在第 2 輪。

## 讀這些數字要知道的事

1. **問題不在 PSF。** 6/22 的根因檢查列出：答案只修一半、只有合成資料、模型只輸出一張灰階影像沒有直接的尺寸輸出、損失主要獎勵影像相似度與邊緣強度、內部挑選不看 CD。
2. **R59 的漂亮數字是建立在 R58 上的。** R59 在 R58 的重建影像上做同樣本校正，降到 2.55 nm；那不是 R58 模型本身的準確度。
3. R58 完整訓練用的資料包放在 `Training_Data/r60_full_power/` 下，資料夾名稱有 R60，但內容是 R58 的半修正答案。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動、自動評分程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 根因檢查、自動評分結果 | 本資料夾 [reports/](<reports>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 4,096 組合成錨點只在原電腦上，但可以用 `scripts/prepare_r58_measurement_dataset.py` 依同樣的 SEM 半徑重新產生。

## 原始報告

| 報告 | 內容 |
|---|---|
| [邊界根因檢查](<reports/r58_boundary_root_cause/R58_BOUNDARY_ROOT_CAUSE_20260622.md>) | 資料清單、答案偏差、損失組成、挑選方式與 CD 結果 |
| [自動評分狀態](<reports/r58_automated_rounds/R58_AUTOMATED_ROUNDS_STATUS.md>) | 完整版的 CD 排名 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R58_MeasurementClosedLoopMOSR.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
