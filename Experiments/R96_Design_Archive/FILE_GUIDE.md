# R96 舊設計：正式 R96 之前的診斷與方案

[研究時間線](<../../docs/research/TIMELINE.md>) · [正式的 R96](<../R96_LocalizedEvidenceProtectedScratch/FILE_GUIDE.md>) · [前一輪 R95](<../R95_CounterfactualGateRepairScratch/FILE_GUIDE.md>)

**一句話：** 這個資料夾保存正式 R96 之前的設計工作，主要是一組診斷程式：R93 資料能不能重用、各分支實際介入了多少、模型內部狀態、輔助目標與完整分支之間的梯度衝突、稀疏分支的監督量，以及一份第 32 輪記憶體中斷的恢復準備。它是設計歷史，不是正式訓練結果。

| | |
|---|---|
| 結果 | **分析**（設計歷史，不等於正式訓練結果） |
| 時間 | 2026-08-13 前後（R95 完成到 R96 正式啟動之間） |
| 內容 | 9 支診斷程式、GPU 批量校正與中斷恢復設定 |

## 裡面有什麼

| 檔案 | 用途 |
|---|---|
| `scripts/analyze_r93_reuse.py` | 檢查 R93 固定資料能否被下一輪重用 |
| `scripts/analyze_branch_interventions.py`、`analyze_model_internals.py` | 各分支實際施加的修正、模型內部狀態 |
| `scripts/audit_*_gradient_conflicts.py`（三支） | 輔助目標、完整分支、各目標之間的梯度衝突 |
| `scripts/audit_sparse_branch_supervision.py` | 稀疏分支拿到多少監督 |
| `scripts/formal_internal_audit.py`、`summarize_internal_analysis.py` | 正式內部稽核與彙整 |
| `scripts/prepare_epoch32_memory_recovery.py`、`config/interruption_recovery.json` | 第 32 輪記憶體中斷的恢復準備 |
| `config/gpu_batch_calibration.json` | GPU 批量校正 |

## 讀這些內容要知道的事

1. **沒有結果報告**；這些診斷的發現反映在正式 R96 的設計（逐通道控制、分支私有目標保護、清楚的反事實樣本）裡。
2. 程式的輸出不在 GitHub 上。

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

## 原始報告

[README](<README.md>)、[MANIFEST](<MANIFEST.md>) 是 2026-10-16 補建的入口。2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R96_Design_Archive.md>)。
