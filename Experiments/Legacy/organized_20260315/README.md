# organized_20260315

這個目錄收斂了 `2026-03-15` 的 estimator-side 主線。

目前裡面的主要分支是：

## branch_e_followup

用途：

- 對 `Branch E Phase2` 做 calibrated reevaluation
- 把 `8px` guard 從舊 absolute threshold 改成 control-relative guard

重要入口：

- `branch_e_followup\BRANCH_E_PHASE2_POSTMORTEM.md`

## estimator_formula_probe

用途：

- 早期 estimator formula 嘗試
- 現在主要作為歷史中繼，不是現行主線

## pairwise_delta_probe

用途：

- 驗證 `single-frame absolute anchor + pairwise delta estimator` 的分治策略

重要入口：

- `pairwise_delta_probe\selected\reports\PAIRWISE_DELTA_PROBE_SUMMARY_20260315_224024.md`

這一步的核心結論是：

- `pairmix_algblend` 通過了 calibrated `0.8px + 8px` internal gate

## round21

用途：

- 驗證 `soft_band_refine` + step-focused training 是否足以解 mid-step

重要入口：

- `round21\ROUND21_POSTMORTEM.md`

核心結論：

- 這條路失敗
- 問題不只是再加 step loss 就能解

## round22

用途：

- 正式驗證 `pairmix_algblend` 是否能在 training probe 中保住 pairwise probe 的優勢

重要入口：

- `round22\ROUND22_POSTMORTEM.md`
- `round22\selected\reports\ROUND22_PAIRMIX_HYBRID_DECISION_20260315_230456.md`
- `round22\selected\current_round22_pairmix_seed.json`

目前這是 `20260315` 目錄下最重要的 round。

## 閱讀順序

如果你只想掌握這一天的主線：

1. `..\..\..\PROJECT_STATE.md`
2. `round21\ROUND21_POSTMORTEM.md`
3. `pairwise_delta_probe\selected\reports\PAIRWISE_DELTA_PROBE_SUMMARY_20260315_224024.md`
4. `round22\ROUND22_POSTMORTEM.md`

## Legacy Governance Entry Points

若要安全回頭操作這個 batch，請另外使用：

1. `MANIFEST.md`
2. `..\..\..\docs\index\LEGACY_ROUNDS_OPERATIONS.md`
3. `round21\README.md`
4. `round22\README.md`
5. `pairwise_delta_probe\README.md`
6. `branch_e_followup\README.md`
7. `estimator_formula_probe\README.md`

這些治理檔是後補導引層，不會重新組織原始 probe 與 archive 內容。
