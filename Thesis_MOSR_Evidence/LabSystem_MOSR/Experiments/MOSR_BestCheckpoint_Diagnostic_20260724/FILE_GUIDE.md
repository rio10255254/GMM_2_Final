# 保存點診斷之一：換成第 10 輪會不會比較好

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [V42](<../V42_SoftLabelSNR/FILE_GUIDE.md>) · [EDSR／NAFNet 對照](<../Modern_Restoration_Benchmarks_20260719/FILE_GUIDE.md>) · [另一個診斷：推論設定與根因](<../MOSR_CheckpointConfig_Diagnostic_20260724/FILE_GUIDE.md>)

**一句話：** EDSR 在位移上小贏 V42，懷疑之一是用錯了保存點：正式比較用的是 V42 第 120 輪，但訓練程式選的 `best_tradeoff` 是第 10 輪。2026-07-24 只把 V42 換成第 10 輪、其他完全不動重跑一次位移比較，結果正式平均誤差沒有改善，所以第 120 輪不是 EDSR 領先的原因。

| | |
|---|---|
| 結果 | **分析** |
| 時間 | 2026-07-24 |
| 實驗條件 | C：實驗室顯微系統；與 EDSR／NAFNet 正式比較相同的 7 月位移序列、相同的 Raw 鎖定 30 步 |
| 換掉的部分 | 只有 MOSR：V42 第 120 輪 → V42 訓練程式選出的第 10 輪平滑保存點 |

## 結果

結論寫在[另一份診斷報告](<../MOSR_CheckpointConfig_Diagnostic_20260724/diagnosis/DIAGNOSTIC_REPORT_zh-TW.md>)的「已排除的解釋」：最佳第 10 輪重新推論沒有改善正式平均誤差。本資料夾保留的是這次重跑的原始量測表：

| 檔案 | 內容 |
|---|---|
| [evaluation/displacement_summary.csv](<evaluation/displacement_summary.csv>) | 各方法、各序列的位移摘要 |
| [evaluation/displacement_pooled_common_valid.csv](<evaluation/displacement_pooled_common_valid.csv>) | 共同有效步次的合併結果 |
| [evaluation/displacement_step_measurements.csv](<evaluation/displacement_step_measurements.csv>) | 逐步量測 |
| [evaluation/displacement_availability.csv](<evaluation/displacement_availability.csv>) | 每個方法的有效步數 |
| [evaluation_manifest_best_checkpoint.json](<evaluation_manifest_best_checkpoint.json>) | 重跑的設定：各方法的影像來源、挑步與有效規則 |

## 讀這些數字要知道的事

1. **第 10 輪的身分。** 它是 V42 完整訓練資料夾裡的 `best_tradeoff`，是平滑（EMA）狀態，不是第 10 輪當下的網路，見 [V42 卡片](<../V42_SoftLabelSNR/FILE_GUIDE.md>)的「V42 不是單一個檔案」。
2. **V42 訓練 120 輪裡有 105 次過度平滑警示**，最佳權重在第 10 輪後就沒再更新；這也是為什麼要回頭檢查第 10 輪。

> **目前的限制：** 第 10 輪的重建影像只在原電腦上。

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../../../docs/reproducibility/experiments/lab__MOSR_BestCheckpoint_Diagnostic_20260724.md>)。
