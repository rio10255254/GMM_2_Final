# R99：從原圖直通開始，依序學亮暗、輪廓、邊緣、紋理

[研究時間線](<../../docs/research/TIMELINE.md>) · [資料來源 R92](<../R92_PhysicalTransitionBalancedScratch/FILE_GUIDE.md>) · [前一輪 R98](<../R98_AggressiveTextureScratch/FILE_GUIDE.md>) · [下一輪 R100](<../R100_CausalOperatorScratch/FILE_GUIDE.md>)

**一句話：** R99 的模型一開始就是原圖的精確直通，再學四個有順序的動作：亮暗校正、有號的輪廓搬移、邊緣剖面修復、有原圖支撐的紋理恢復。資料改回唯讀使用 R92 的 5,000 個觀察（避免再複製約 17 GiB）。2026-08-14 從零訓練，計畫 48 輪，實際在第 41 輪停下。

| | |
|---|---|
| 結果 | **中止**（停在第 41 輪，計畫 48 輪） |
| 時間 | 2026-08-14（10:58 正式啟動） |
| 實驗條件 | R92 固定合成資料（依鎖定雜湊唯讀）；不使用 SEM、HS100MG、舊權重或老師 |
| 起點 | 隨機初始化，種子 990053；初始等同原圖 |

## 讀這些內容要知道的事

1. **這一輪沒有留下結果報告或停止紀錄**；「停在第 41 輪」來自 2026-10-16 的保存核對。原 README 是啟動前的說明。
2. **R99 用的是 R92 的資料，不是 R93 的。** 之後的 R100、R102～R104 也用 R92。
3. **訓練加速的做法**記在 README：先裁切再變形、可分離的固定濾波、BF16、channels-last、fused AdamW、實測批量，以及把昂貴的 896 px 切塊只穿插在最後階段。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 設計、門檻、執行策略；模型、訓練、推論、測試 | 本資料夾 [config/](<config>)、[model/](<model>)、[training/](<training>)、[inference/](<inference>)、[tests/](<tests>)，已在 GitHub |
| 共用資料 | 見 [R92](<../R92_PhysicalTransitionBalancedScratch/FILE_GUIDE.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 權重、訓練紀錄與加速測試只在原電腦上。

## 原始報告

[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R99_GeometryTextureCoherentScratch.md>)。
