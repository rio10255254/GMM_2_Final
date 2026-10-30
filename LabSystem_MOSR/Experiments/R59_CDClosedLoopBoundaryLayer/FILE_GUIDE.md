# Lab R59：在同一張影像上量尺寸、再把邊界搬過去

[研究時間線](<../../../docs/research/TIMELINE.md>) · [LabSystem 全線](<../../../docs/reproducibility/lineage/LAB_SYSTEM.md>) · [前一輪 Lab R58](<../R58_MeasurementClosedLoopMOSR/FILE_GUIDE.md>) · [下一輪 Lab R60](<../R60_SEMTruthBoundaryTraining/FILE_GUIDE.md>)

**一句話：** R58 重建後的 100MG 影像，孔偏小、柱偏大，而且偏得很穩定。R59 在重建影像上量出兩類特徵各自的平均偏差，再把孔的邊界往外推約 1 px、柱往內收約 0.5 px。修正後平均半徑誤差從 53.69 nm 降到 2.55 nm，但這是在同一張影像上校正，不是模型學會了。

| | |
|---|---|
| 結果 | **分析**（同樣本後處理校正；數字變好不代表網路學會邊界） |
| 時間 | 2026-06-21～06-22 |
| 實驗條件 | C：實驗室顯微系統；6/18 的 100MG 影像與同批樣品的 SEM |
| 套用對象 | R58 的 8 輪短測與 30 輪完整版重建結果 |

這一輪沒有訓練新的網路，只有一個後處理程式。

## 這輪在問什麼

如果模型的邊界偏差是穩定的，能不能在重建後用一層簡單的邊界移動把 CD 拉回 SEM？

## 怎麼做

1. 在 R58 的重建影像上量出每顆孔、柱的半徑，跟 SEM 比，算出兩類各自的中位數偏差。
2. 把偏差換成像素位移（孔約 +1.03 px，柱約 −0.46 px），只在邊界附近移動。
3. 用 R57 的 CD 量測工具重新量一次修正後的影像。

## 結果

| 影像 | 平均 | 孔 | 柱 |
|---|---:|---:|---:|
| 原圖 | 38.59 | 66.13 | 11.04 |
| R58 完整版（30 輪） | 53.69 | 75.08 | 32.30 |
| R58 完整版＋R59 修正 | 2.55 | 3.36 | 1.75 |

（對 SEM 的平均絕對半徑誤差，nm。）R58 的 8 輪短測版套用後也從 54.91 降到 2.23 nm。

## 讀這些數字要知道的事

1. **量的和修的是同一張影像。** 偏差是從這張影像量出來、再用回同一張影像，SEM 也來自同一批樣品。這只能證明「R58 的偏差很穩定」，不能證明模型準、也不能證明換一個樣品還有效。
2. **R60 的稽核明確寫了不能把它當成模型的準確度。** 之後的研究改回從訓練資料下手，見 [Lab R60](<../R60_SEMTruthBoundaryTraining/FILE_GUIDE.md>)。
3. 報告資料夾裡有一份檔名叫 `R60_FULL_POWER_R58_R59_REPORT.md`，那是 6/22 凌晨把 R58 完整版與 R59 一起跑的結果，放在 R59 這邊，不是 R60 的正式報告。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 修正程式與測試 | 本資料夾 [scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub |
| 兩次修正的狀態與結果報告 | 本資料夾 [reports/](<reports>) |
| R58 的重建影像 | 只在原電腦上；要重做須先取得 R58 模型並重建，見 [Lab R58](<../R58_MeasurementClosedLoopMOSR/FILE_GUIDE.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

| 報告 | 內容 |
|---|---|
| [R58 完整版＋R59 結果](<reports/r59_cd_closed_loop/r58_frac050_full_e030_mtb512_20260621_2300/R60_FULL_POWER_R58_R59_REPORT.md>) | CD 表、學到的位移量、修正影像位置 |
| [完整版修正狀態](<reports/r59_cd_closed_loop/r58_frac050_full_e030_mtb512_20260621_2300/R59_CD_CLOSED_LOOP_STATUS.md>)、[短測版修正狀態](<reports/r59_cd_closed_loop/r58_frac050_e8_best/R59_CD_CLOSED_LOOP_STATUS.md>) | 每類特徵的位移與修正前誤差 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../docs/reproducibility/experiments/lab__R59_CDClosedLoopBoundaryLayer.md>)與 [Lab 逐輪必要來源核對](<../../../docs/reproducibility/round_source_reviews/LAB_SYSTEM_20261023.md>)。
