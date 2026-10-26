# Lab R57：第一次拿 SEM 半徑約束 100MG 的尺寸

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R56](<../R56_LabelCoreRepairTraining/FILE_GUIDE.md>) · [起點 Lab R55](<../R55_SourceStyleRealisticTraining/FILE_GUIDE.md>) · [下一輪 Lab R58](<../R58_MeasurementClosedLoopMOSR/FILE_GUIDE.md>)

**一句話：** R55 通過了 Lab 的角點門檻，但拿 6/18 拍的 100MG 樣品去量 CD，孔變太小、柱變太大，比原圖離 SEM 更遠。R57 從 R55 起步，加入依 SEM 半徑畫的合成圓形錨點和邊界幾何監督，試了四種做法，沒有一種在孔和柱上都贏過原圖。

| | |
|---|---|
| 結果 | **未採用**（100MG CD 門檻沒過；SEM 同時當答案和比較，也不能算獨立驗證） |
| 時間 | 2026-06-20 |
| 實驗條件 | C：實驗室顯微系統；6/18 的 100MG 影像（50×，69 nm/px），SEM 半徑：柱 1,321.9 nm、孔 1,642.0 nm |
| 起點 | Lab R55 的 `best_tradeoff` |

## 在研究裡的位置

這是 LabSystem 研究從「修角點」轉到「修尺寸」的第一輪。R46～R56 用的是實拍棋盤；從 R57 開始，論文的主樣品換成 100MG，評分改用對 SEM 的 CD。R58、R59、R60 都沿用 R57 寫的 CD 量測工具和門檻。

## 這輪在問什麼

把 100MG 的 SEM 半徑做成訓練錨點、加強邊界附近的幾何監督，能不能把 R55 的尺寸偏差拉回來，同時保持位移表現？

## 怎麼做

- **資料：** R55 的 6,000 組資料加上 2,048 組依 SEM 半徑畫的孔、柱合成錨點，共 8,048 組，每組都附邊界、中心線、距離圖。
- **四種試法：** 混合資料直接訓練；只用錨點短訓（anchor-focus）；只用錨點後再回到混合資料；R57.1 把「原圖量到的偏差」直接當答案（孔放大、柱縮小）。
- **門檻：** 孔和柱的 CD 誤差都不能比原圖差，位移檢查也要維持在 R55 的範圍內。PSF 前向損失關閉，因為這個樣品還沒重新校正 PSF。

## 結果

| 影像／模型 | 孔 | 柱 | 平均 | 門檻 |
|---|---:|---:|---:|---|
| 原圖 | 66.13 | 11.04 | 38.59 | 基準 |
| R55（PSF 關） | 80.28 | 43.41 | 61.84 | 未過 |
| R57 混合訓練 | 84.01 | 44.27 | 64.14 | 未過 |
| **R57 只用錨點（最好）** | 72.88 | 25.34 | 49.11 | 未過 |
| R57 錨點後回到混合 | 75.02 | 33.38 | 54.20 | 未過 |
| R57.1 直接修正偏差 | 106.97 | 74.17 | 90.57 | 未過 |

（對 SEM 的平均絕對半徑誤差，nm。）只用錨點的版本方向是對的，比 R55 好了 12.7 nm，但還是比原圖差。R57.1 往反方向修過頭，孔和柱都變得更差。

## 讀這些數字要知道的事

1. **SEM 不是獨立的驗證。** 錨點的半徑和 CD 門檻都來自同一批樣品的 SEM。
2. **R57.1 有一個已修正的資料錯誤。** 第一次跑時合成的輸入和答案圓心沒有對齊；修好、重新產生資料再訓練後，仍然沒過門檻。表裡是修好之後的數字。
3. **原圖本身就很難贏。** 原圖的柱誤差只有 11 nm，任何讓柱子往外擴的改動都會輸；後來 R60 才發現柱子需要的修正只有約 0.14 px，很容易被一般的影像損失洗掉。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料建置、啟動、CD 量測、CD 門檻程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub；指令見 [README](<README.md>) |
| 原始設計與狀態 | [README](<README.md>)、[MANIFEST](<MANIFEST.md>)、[試訓狀態](<reports/R57_PILOT_TRAINING_STATUS.md>) |
| 代表模型 | Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016)，見 [Lab 代表模型清單](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 8,048 組訓練資料只在原電腦上；2,048 組錨點可以用 `scripts/prepare_r57_geometry_dataset.py` 重新產生，6,000 組 R55 資料要從 R53／R55 的資料生成程式取得。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 為什麼開這輪、資料與訓練計畫、採用規則 |
| [MANIFEST](<MANIFEST.md>) | 樣品尺寸、各次試訓與目前最好的探索候選 |
| [試訓狀態](<reports/R57_PILOT_TRAINING_STATUS.md>) | 四種做法的 CD 結果與判讀 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__R57_GeometryConstrainedMOSR.md>)與 [Lab 逐輪必要來源核對](<../../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
