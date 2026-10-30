# 2026-03-11 批次：Round 12～14 的通用多尺度長跑與保存點稽核

[研究時間線](<../../../docs/research/TIMELINE.md>) · [早期輪次對照](<../../../docs/reproducibility/lineage/EARLY_ROUNDS.md>) · [R12～R15 的選擇讀法](<../../../docs/reproducibility/legacy_multiscale/README.md>) · [前一個批次 3/10](<../organized_20260310/FILE_GUIDE.md>) · [下一個批次 3/12（R15）](<../organized_20260312/FILE_GUIDE.md>)

**一句話：** 2026-03-11 的通用（universal）多尺度路線。Round 12 長跑五個候選，選中 `universal_sign_guard`（優先用它的 0.8 px 保存點）；Round 13 改成「家族初排之後，再對固定的單份模型在 0.08／0.8／8 px 三個保存點逐一稽核」，同樣是 `universal_sign_guard` 勝出（部署分數 −87.2，其他候選 −115.8、−121.5）。這一段最重要的發現是：家族初排第一名，不一定是最後該採用的那份模型。

| | |
|---|---|
| 結果 | **分析**（建立「先初排、再固定模型稽核」的選法；R14 初排第一與最後採用不同） |
| 時間 | 2026-03-11 |
| 實驗條件 | A：環形影像三尺度的內部評分；外部重建保存在 H 槽 |
| 起點 | 當時的訓練線 |

## Round 12 家族排名

| 候選 | 0.08 px | 0.8 px | 8 px | 通用分數 |
|---|---:|---:|---:|---:|
| **universal_sign_guard** | 16.690 | 21.728 | 22.527 | **38.449** |
| universal_clean_anchor | 11.358 | 11.358 | 11.358 | 32.477 |
| universal_defect_anchor | 11.285 | 11.285 | 11.285 | 32.259 |
| universal_balanced_bridge | 11.285 | 11.285 | 11.285 | 32.259 |
| universal_macro_lock | 11.327 | 13.408 | 12.950 | 27.762 |

## 讀這些內容要知道的事

1. **好幾個候選三個尺度的分數完全一樣**（例如 11.358），表示它們在各尺度選到的是同一份保存點。
2. **R14 的報告**：README 說保留了 Round 12～14 的報告，但 git 上看得到的是 R12 與 R13；R14 的選擇讀法整理在 [R12～R15 選擇讀法](<../../../docs/reproducibility/legacy_multiscale/README.md>)。
3. **大型內容已移到 H 槽**（2026-08-01）：完整 6,912 個檔、31.6 GiB 在 H 槽快照，D 槽保留 `selected/` 的 60 個精選檔、2 份代表模型與少量紀錄。恢復方式見 [ARCHIVE_POINTER](<ARCHIVE_POINTER.md>)。

## 原始報告

[Round 12 多尺度摘要](<selected/reports/ROUND12_UNIVERSAL_MULTISCALE_SUMMARY_20260311_023449.md>)、[Round 13 保存點稽核摘要](<selected/reports/ROUND13_UNIVERSAL_CHECKPOINT_AUDIT_SUMMARY_20260311_150225.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本批次保存紀錄](<../../../docs/reproducibility/experiments/legacy__organized_20260311.md>)。
