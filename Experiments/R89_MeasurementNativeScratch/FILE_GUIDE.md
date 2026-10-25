# R89：拿掉信心閘，讓模型真的去修

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一輪 R88](<../R88_MeasurementFaithfulScratch/FILE_GUIDE.md>) · [下一輪 R90](<../R90_ExposureCoherentScratch/FILE_GUIDE.md>) · [R89～R93 的設計演進](<../../docs/reproducibility/scratch_lineage/README.md>)

**一句話：** R88 太保守，幾乎照抄原圖。R89 保留同樣的架構，但拿掉輸出信心閘，直接訓練一個有上限的重建，2026-08-11 從零跑完 100 輪。合成資料上的平均改善是真的（位移誤差減半），大圖切塊也逐像素一致；但它把模糊邊緣壓成強烈、平坦、高對比的輪廓，清楚的影像被改出假邊界，真實 SEM 輪廓 36 顆中有 35 顆變差，在主要模型裡排最後。

| | |
|---|---|
| 結果 | **未採用**（沒有任何輪次通過全部安全門檻） |
| 時間 | 2026-08-11（00:57 鎖定實作後啟動，100 輪） |
| 實驗條件 | 純合成資料；真實 5×、20×、50× 只提供匿名的雜訊與照明統計；384 個場景封存到權重固定後才打開 |
| 起點 | 隨機初始化，只有這一次正式訓練 |

## 結果

**封存測試集（384 場景、1,504 配對）：** 困難輪廓誤差約為原圖的 43.6%，位移平均誤差 0.537 → 0.271 px；但位移第 95 百分位 0.871 px（上限 0.20），x／y 系統偏差 +0.146／−0.106 px（上限 0.04），清楚影像平均被改 4.33 灰階，新增 131 次原本不存在的結構錯誤。

**真實 50×：** 兩種切塊大小的輸出逐像素相同；但平均改動 13.6 灰階，45% 像素改動超過 10 階，看得到深色輪廓與亮暈邊。1 µm 位移序列的步進標準差跟原圖幾乎相同（9.312 對 9.314 nm），但引入約 2.1 nm 的固定偏差。

**36 顆柱 SEM（12 張曝光）：**

| 模型 | 輪廓 IoU 中位數 |
|---|---:|
| Lab R61 v16 | 0.9584 |
| R75v2 第 100 輪 | 0.9582 |
| V42 第 120 輪 | 0.9531 |
| 原圖 | 0.9490 |
| **R89 第 100 輪** | **0.9451**（35/36 顆變差） |

**第 55 輪：** 跨曝光中位數最好（0.964，36/36 顆改善），但最差曝光只有 0.816；第 18 號曝光會抓到外圈，面積比 SEM 大約 22.5%。

## 讀這些數字要知道的事

1. **為什麼合成變好、真實變差：** 報告的判讀是真實影像的模糊帶本身就帶有邊界位置資訊，過強的內外暈邊讓 ACM 收斂到錯誤位置；看起來更清楚，形狀卻更不準。
2. **可以保留的是流程：** 192 px 上下文的切塊重建、大圖逐像素一致、全新從零與封存驗證、固定區域的位移驗證、SEM–ACM 最終驗證。
3. **正式前作廢過兩次資料**：一次是 Windows 進度檔被鎖，一次是答案形狀的逐像素截斷洩漏；兩份都完整移到失敗證據，沒有重用。
4. 第 55 輪只當研究候選，因為有明顯曝光敏感性，其他安全檢查也沒全過。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 鎖定設計、門檻、光學統計摘要、實作雜湊；模型、訓練、推論、資料生成、測試 | 本資料夾 [config/](<config>)、[model/](<model>)、[training/](<training>)、[inference/](<inference>)、[scripts/](<scripts>)、[tests/](<tests>)，已在 GitHub；指令見 [README](<README.md>) |
| 最終驗證與各階段分析 | [reports/final_validation/](<reports/final_validation/R89_FINAL_VALIDATION_TW.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 合成資料與封存集影像只在原電腦上。正式與短測的權重、封存集評估結果（`reports/final_validation/`）不在 GitHub 程式樹上，在 Release [`research-results-models-20261016`](https://github.com/rio10255254/GMM_2_Final/releases/tag/research-results-models-20261016) 的壓縮包裡。

## 原始報告

| 文件 | 內容 |
|---|---|
| [第 100 輪最終驗證](<reports/final_validation/R89_FINAL_VALIDATION_TW.md>) | 內部、封存、真實 50×、位移、SEM、根因 |
| [各階段 SEM 輪廓與 5×／20×](<reports/final_validation/stage_weight_analysis/R89_STAGE_WEIGHT_FINDINGS_TW.md>) | 第 55 輪與第 100 輪的比較 |
| [正式前檢查](<reports/R89_PREFLIGHT_SUMMARY.md>)、[鎖定時間線](<reports/R89_LOCK_TIMELINE.md>) | 作廢的兩次資料與最後的鎖定 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R89_MeasurementNativeScratch.md>)。
