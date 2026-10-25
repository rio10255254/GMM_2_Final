# R90：同一個物體在四種曝光下，輪廓要回到同一個位置

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R89](<../R89_MeasurementNativeScratch/FILE_GUIDE.md>) · [下一輪 R91](<../R91_DetailDecoupledScratch/FILE_GUIDE.md>) · [R89～R93 的設計演進](<../../docs/reproducibility/scratch_lineage/README.md>)

**一句話：** R89 的輪廓會隨曝光漂移，5× 還出現黑色描邊。R90 保留 R89 的切塊安全架構，讓低頻修正分支真正只能做低頻（畫不出窄黑邊），並讓同一個程式生成的結構在四種曝光下回到同一個輪廓位置，2026-08-11 從零訓練。第 50 輪起 5× 清楚出現黑邊退步，訓練停在第 55 輪；事後比較第 20～55 輪，第 45 輪是退步前最後一個可用的版本，但真實 SEM 的某個曝光下輪廓仍往外偏。

| | |
|---|---|
| 結果 | **中止**（停在第 55 輪；第 45 輪留作研究與 ONNX 可行性候選，不升級） |
| 時間 | 2026-08-11（10:43 啟動） |
| 實驗條件 | 純合成：1,280 個場景、5,120 個觀察；真實 5×、20×、50× 只提供匿名光學統計；384 個場景封存 |
| 起點 | 隨機初始化 |

## 改了什麼

- 低頻修正分支真正低通，不能畫窄的暗輪廓。
- 同一結構在四種相干曝光下觀察，訓練它回到同一個輪廓位置。
- 訓練輪流使用重疊切塊配對、跨觀察配對、有號位移配對；損失強度平滑上升，不突然切換。
- 保存點用連續的平衡分數排序，診斷參考只報告、不當二元門檻。

## 結果

第 45 輪：位移穩定、切塊重建逐像素一致，技術上可以匯出 ONNX；但真實 SEM 第 18 號曝光的輪廓往外擴，所以不能當通用的交付模型。第 50 輪開始，清楚的 5× 影像出現黑色描邊退步。

## 讀這些內容要知道的事

1. **專案正式基準仍是 COMBO**，應急交付仍是已驗證的 R61 ONNX；第 45 輪只是確認候選。
2. **事後的早停研究**（比較第 20～55 輪、確認第 45 輪、分支取捨診斷、ONNX 匯出與一致性）的程式與設定都在本資料夾，清單見 [MANIFEST](<MANIFEST.md>)。
3. 沒有任何 R89 的保存點或結果被複製進 R90。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 設計、光學統計、實作鎖定；模型、訓練、推論、資料生成、驗證與早停研究程式 | 本資料夾 [config/](<config>)、[model/](<model>)、[training/](<training>)、[inference/](<inference>)、[scripts/](<scripts>)，已在 GitHub；對照表見 [MANIFEST](<MANIFEST.md>) |
| 早停比較的圖 | [reports/early_stop_validation/](<reports/early_stop_validation>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 合成資料、封存集、權重與 ONNX 只在原電腦上；早停比較與確認的文字結論只寫在 README 與 MANIFEST，沒有獨立報告。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 改了什麼、資料隔離、停止後的結果 |
| [MANIFEST](<MANIFEST.md>) | 所有檔案的用途，包括事後早停研究 |
| [R89～R93 的設計演進](<../../docs/reproducibility/scratch_lineage/README.md>) | 這一輪在整條從零訓練線上的位置 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R90_ExposureCoherentScratch.md>)。
