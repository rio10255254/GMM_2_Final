# R130 Clean：拿掉光學與放大，改成原尺寸的純神經模型

[研究時間線](<../../docs/research/TIMELINE.md>) · [對照的 R129](<../R129_OpticalPriorHybrid/FILE_GUIDE.md>) · [同編號的另一件事：乾淨重訓 V42](<../R130_CleanV42Comparison/FILE_GUIDE.md>) · [930 張重拍的量測做法 R136](<../R136_PIRepeatability/FILE_GUIDE.md>)

**一句話：** 2026-09-20 依使用者規格做的對照：完全關掉 PSF（沒有光學核、沒有 FFT、沒有候選選擇），64 通道、四次共享更新，全程維持原尺寸，最後只在原圖上加受限的累積殘差。從零訓練 8,192 次，然後用 930 張 30 次重拍的原尺寸影像，跟 R129 走完全相同的 ACM、最大梯度、LSC、PI 與 SEM 讀法。結果是：位移穩定度跟 R129 幾乎一樣，速度快很多，但尺寸偏大的問題還在。

| | |
|---|---|
| 結果 | **研究候選**（快速、來源乾淨的純神經版本；位移與 R129 相近，尺寸偏大仍在） |
| 時間 | 2026-09-20 |
| 實驗條件 | 訓練用程式資料：R128 的 512／128／128 母場景（只取 source、noiseless、target 陣列）；評估用 D：均華 20× 物鏡加 PI 位移台的 930 張（30 次掃描 ×31 張），以及九顆柱的 SEM 對照 |
| 起點 | 隨機初始化 |

這跟 9/13 的 [R130（乾淨重訓 V42）](<../R130_CleanV42Comparison/FILE_GUIDE.md>) 是兩件不同的事，只是共用編號。

## 結果

**位移（930 張，對 PI 讀值的差，nm）：**

| 方法 | 短步平均差 | 短步重拍 | 短步最大差 | 距起點平均差 |
|---|---:|---:|---:|---:|
| Raw | 8.167 | 9.725 | 39.30 | 19.08 |
| R129 | 4.125 | 4.251 | **16.87** | 17.99 |
| R130 Clean | **4.121** | **4.184** | 20.41 | **17.95** |

短步平均跟 R129 只差 0.004 nm，區塊分組的範圍都包含零，應解讀為相近。

**尺寸與輪廓：**

| 方法 | 尺寸重拍波動 | 輪廓重拍波動 | SEM 平均直徑偏大 |
|---|---:|---:|---:|
| Raw | 32.75 nm | 63.76 nm | 185.2 nm |
| R129 | 19.23 nm | 18.44 nm | 224.5 nm |
| R130 Clean | **16.42 nm** | 18.58 nm | 219.4 nm |

**速度：** 完整 1544×2064 影像，純神經推論約 1.38 秒（含讀寫約 1.87 秒）；R129 歷史紀錄含讀寫約 11.2 秒。切塊模式（512 核心、96 周邊）約 2.6 秒，與整張輸出最大差 1.5×10⁻⁷。

## 讀這些數字要知道的事

1. **拿掉光學路徑並沒有讓尺寸偏大自然消失**（只少約 5 nm），但這次同時改了很多東西，不能當成 PSF 單項的因果實驗。
2. **SEM 的柱子方向對應還沒唯一確認**，所以兩種方向候選都列出；去尺寸形狀差在方向 1 改善、方向 2 退步，不能挑有利方向說全面改善。
3. **930 張是已用過的資料**，不是新的未知樣本；PI 位移台讀值是外部參照，R136 定義了這套量法。
4. `results/reconstruction` 在原電腦上是連到 H 槽的連結，930 張重建放在 H 槽。

## 拿資料與重做

`START_R130.cmd` 或 `scripts/launch_r130.py` 會先檢查資料與前置再訓練，最後跑 930 張驗證；單圖推論是 `infer_r130_clean.py --checkpoint runs/formal_8192/checkpoints/step08192.pth --input <影像> --output <輸出.npz> --mode full`。

| 需要什麼 | 在哪裡 |
|---|---|
| 模型、訓練、推論、評估程式與設定 | 本資料夾，已在 GitHub |
| 原圖九顆柱的基準圓心、比較結果摘要 | `evaluation/`、`results/`，已在 GitHub |
| 9/20 的論文交接資料 | [`Deliverables/Thesis_Handoffs/R130_Clean_Corrected_Corner9_Validation_Handoff_20260920/`](<../../Deliverables/Thesis_Handoffs/R130_Clean_Corrected_Corner9_Validation_Handoff_20260920>) |
| 權重、930 張重建 | 見下方說明 |

> 權重與大型輸出的位置：查 `python Tools/cloud_locator.py where Experiments/R130_Clean/<路徑>`。

## 原始報告

[完整結果](<reports/R130_CLEAN_RESULTS.md>)（含獨立複核後的決斷）、[訓練來源](<reports/TRAINING_PROVENANCE.md>)、[README](<README.md>)、[交付說明](<DELIVERY.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R130_Clean.md>)。
