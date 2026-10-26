# Branch E Follow-up：校準門檻後重判 soft_band_refine

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一步 Branch E](<../../organized_20260314/branch_e/FILE_GUIDE.md>) · [同日的公式探針](<../estimator_formula_probe/FILE_GUIDE.md>) · [Round 21](<../round21/FILE_GUIDE.md>)

**一句話：** 2026-03-15 把 Branch E 的估計器候選延長探測（Phase 2）。原始決策是「未確認」，但那是沿用了舊的絕對 8 px 門檻（步長 ≤ 0.04），在這套流程稽核裡連控制組都過不了，方法上不成立。改成以控制組為準的相對門檻重判後：`soft_band_refine` 在 0.8 px 絕對中心上改善了 97.8%，8 px 也通過了；但 0.8 px 步長誤差 0.580，超過 0.45 的上限，所以 Round 21 仍然不能開。

| | |
|---|---|
| 結果 | **分析**（中心大幅改善是真的，但 0.8 px 步長沒過，Round 21 仍被擋） |
| 時間 | 2026-03-15 |
| 實驗條件 | A：環形影像 0.8 px 與 8 px 的流程稽核；沒有外部 GMF |
| 起點 | Branch E 的估計器候選 |

## 校準後的門檻與結果

| 項目 | 門檻 | soft_band_refine | 結果 |
|---|---|---:|---|
| 0.8 px 中心改善比例 | ≥ 25% | 97.83%（控制組 8.592 → 0.186） | 通過 |
| 0.8 px 步長誤差 | ≤ 0.45 | 0.580 | **未通過** |
| 8 px 步長誤差 | ≤ 控制組 + 0.12（0.2995） | 0.2889 | 通過 |
| 8 px 方向正確率 | ≥ 控制組 − 0.05（0.7559） | 0.8157 | 通過 |

## 讀這些內容要知道的事

1. **原始「未確認」與校準後重判分開保存**，兩份都在 `selected/reports/`。
2. **重判後凍結的估計器政策**：正式基準三個尺度都用 `edge_centroid`；暫定混合政策是 0.08 px 用 `edge_centroid`、0.8 px 用 `soft_band_refine`、8 px 用 `edge_band_refine`，但標記為還不能用於 Round 21。機器可讀版本寫在主專案的 `ESTIMATOR_POLICY.json`。
3. 報告的結論：下一步應該針對 `soft_band_refine` 調和步長或重新設計公式，而不是回頭掃中心權重或做外部重建。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_branch_e_phase2_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[Phase 2 事後檢討](<BRANCH_E_PHASE2_POSTMORTEM.md>)、[原始決策](<selected/reports/BRANCH_E_PHASE2_DECISION_20260315_154300.md>)、[校準後重判](<selected/reports/BRANCH_E_PHASE2_REEVALUATION_20260315_203359.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本面保存紀錄](<../../../docs/reproducibility/experiments/legacy__branch_e_followup.md>)。
