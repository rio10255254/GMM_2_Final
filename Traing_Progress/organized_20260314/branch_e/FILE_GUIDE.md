# Branch E：換估計器的第一輪探針

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [選擇它的診斷矩陣](<../diagnostics/FILE_GUIDE.md>) · [後續 Branch E Follow-up](<../../organized_20260315/branch_e_followup/FILE_GUIDE.md>)

**一句話：** 診斷矩陣選定「先修估計器」之後的六小時自動化流程（2026-03-14～03-15）：先對多種估計器做基準比較，自動挑出探針候選，在 0.8 px 跑估計器探針，再做流程稽核與決策。基準比較中最好的非控制估計器是 `edge_band_refine`，稽核後最好的候選是 `be_soft_band`，中心誤差比控制組改善 7.64；但沒有通過稽核關卡，所以 Branch E 維持進行、先繼續改估計器公式，不開新輪。

| | |
|---|---|
| 結果 | **分析**（非控制估計器在家族排名勝出，但沒過稽核關卡；Branch E 繼續） |
| 時間 | 2026-03-14 晚間～03-15 下午 |
| 實驗條件 | A：環形影像 0.8 px 的估計器探針與流程稽核；沒有外部 GMF |
| 起點 | 沿用 Round 18 的路線 |

## 讀這些內容要知道的事

1. **四個探針候選**：`be_ctrl_edge`（控制組）、`be_edge_band`、`be_soft_band`、`be_soft`。
2. **「沒過稽核關卡」後來被重新判讀**：[Branch E Follow-up](<../../organized_20260315/branch_e_followup/FILE_GUIDE.md>) 發現當時沿用的 8 px 絕對門檻連控制組都過不了，改成以控制組為準的相對門檻後重判。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_branch_e_probe_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[探針決策](<selected/reports/BRANCH_E_ESTIMATOR_PROBE_DECISION_20260315_152909.md>)、[探針摘要](<selected/reports/BRANCH_E_ESTIMATOR_PROBE_SUMMARY_20260315_152742.md>)、[稽核摘要](<selected/reports/BRANCH_E_ESTIMATOR_PROBE_AUDIT_SUMMARY_20260315_152742.md>)、[估計器基準比較](<benchmark/BRANCH_E_ESTIMATOR_BENCHMARK_SUMMARY_20260315_151702.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本面保存紀錄](<../../../docs/reproducibility/experiments/legacy__branch_e.md>)。
