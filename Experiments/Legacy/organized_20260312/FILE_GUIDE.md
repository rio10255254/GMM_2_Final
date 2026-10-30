# 2026-03-12 批次：Round 15 中心鎖定長跑

[研究時間線](<../../../docs/research/TIMELINE.md>) · [早期輪次對照](<../../../docs/reproducibility/lineage/EARLY_ROUNDS.md>) · [R12～R15 的選擇讀法](<../../../docs/reproducibility/legacy_multiscale/README.md>) · [前一個批次 3/11](<../organized_20260311/FILE_GUIDE.md>) · [下一輪 Round 16](<../organized_20260313/round16/FILE_GUIDE.md>)

**一句話：** 2026-03-12 凌晨的中心鎖定（center-lock）長跑：以 0.8 px 的中心穩定度當主要關卡、8 px 不退步當守門、0.08 px 當次要依據，四個候選。家族排名與保存點稽核都選 `centerlock_pure`；四個候選的稽核部署分數都是 −125.821，同分時沿用原排序。這條「先看 0.8 px 中心穩定度」的選法，延續到後面的 Round 16～19。

| | |
|---|---|
| 結果 | **研究候選**（`centerlock_pure` 是當時精選，不是正式模型） |
| 時間 | 2026-03-12 |
| 實驗條件 | A：環形影像三尺度的內部評分；外部重建保存在 H 槽 |
| 起點 | 當時的訓練線 |

## 結果

| 候選 | 家族分數 | 部署分數 | 選中的保存點 |
|---|---:|---:|---|
| **centerlock_pure** | 366.564 | −125.821 | 0.8 px 那個 |
| centerlock_defectguard | 365.002 | −125.821 | 0.8 px 那個 |
| centerlock_balanced | 360.481 | −125.821 | 0.08 px 那個 |
| centerlock_macroguard | 360.283 | −125.821 | 0.08 px 那個 |

## 讀這些內容要知道的事

1. **四個候選的部署分數同分**，最後依原排序選 `centerlock_pure`（[R12～R15 選擇讀法](<../../../docs/reproducibility/legacy_multiscale/README.md>)有說明）。
2. **代表模型**：`selected_checkpoint/centerlock_pure_best_tradeoff.pth.tar`（約 20.4 MB，SHA-256 開頭 `2ad1a1bc`）。
3. **大型內容已移到 H 槽**（2026-08-01）：完整 1,152 個檔、3.83 GiB 在 H 槽快照，D 槽保留 13 份報告與種子、1 份代表模型。恢復方式見 [ARCHIVE_POINTER](<ARCHIVE_POINTER.md>)。

## 原始報告

[Round 15 多尺度摘要](<selected/reports/ROUND15_CENTERLOCK_MULTISCALE_SUMMARY_20260312_022742.md>)、[Round 15 保存點稽核摘要](<selected/reports/ROUND15_CENTERLOCK_CHECKPOINT_AUDIT_SUMMARY_20260312_022742.md>)、[代表模型說明](<selected_checkpoint/README.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本批次保存紀錄](<../../../docs/reproducibility/experiments/legacy__organized_20260312.md>)。
