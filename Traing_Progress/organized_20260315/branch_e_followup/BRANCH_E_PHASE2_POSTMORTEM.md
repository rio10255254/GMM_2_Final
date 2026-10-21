# BRANCH_E_PHASE2 POSTMORTEM
Last updated: 2026-03-15

## Scope

這份文件只講 `Branch E Phase2`：

- 原始 follow-up probe 做了什麼
- 為什麼原始 `not_confirmed` 不能直接當最後結論
- 校準後 reevaluation 如何改寫 guard 規則
- 到底什麼已被證實，什麼仍未被證實
- 為什麼 `Round21` 目前仍 blocked

## 1. Original Phase2 Goal

`Branch E Phase2` 的原始目標不是直接產生 deploy model，而是回答：

- 如果把 estimator-side 候選延長 probe，`0.8px` 優勢是否能站穩
- 這些候選是否能同時守住 `8px` macro 行為

原始候選主體是：

- `be_ctrl_edge`
- `be_edge_band`
- `be_soft_band`

## 2. Original Phase2 Result

原始 decision memo：

- `selected\reports\BRANCH_E_PHASE2_DECISION_20260315_154300.md`

原始結論是：

- `not_confirmed`

但這個結論當時有一個關鍵限制：

- 它沿用了舊式的絕對 `8px step <= 0.04` guard

在新的 process-audit harness 裡，這個門檻連 control 自己都過不了，
因此它不能再被當成 Phase2 的最終否決依據。

## 3. Why Reevaluation Was Necessary

校準前最大的問題是：

- `full deploy audit` 的歷史絕對 guard
- 被直接拿來套在 `process-audit harness`

這在方法論上不成立。

因此後續重判改成：

- 以 `be_ctrl_edge` 在同一套 `8px process audit` 下的結果當 guard baseline
- 用 control-relative margin，而不是歷史絕對值

## 4. Calibrated Guard Rules

校準後 guard 規則固定為：

### Mid-scale (`0.8px`)

- `center improvement ratio >= 25%`
- `step_err <= 0.45`

### Macro guard (`8px`)

- `step_err <= control_guard_step + 0.12`
- `sign_acc >= control_guard_sign - 0.05`

本次 control baseline：

- `control_guard_step = 0.179484`
- `guard_step_limit = 0.299484`
- `control_guard_sign = 0.805935`
- `guard_sign_floor = 0.755935`

## 5. Calibrated Reevaluation Result

正式 reevaluation：

- `selected\reports\BRANCH_E_PHASE2_REEVALUATION_20260315_203359.md`

關鍵數字：

### `0.8px`

- control `center_err = 8.592463`
- `be_soft_band center_err = 0.186192`
- absolute improvement = `8.406270`
- improvement ratio = `97.8331%`

### `0.8px step`

- `be_soft_band step_err = 0.580409`
- target limit = `0.45`
- 結果：**未通過**

### `8px guard`

- `be_soft_band step_err = 0.288858`
- calibrated guard limit = `0.299484`
- `be_soft_band seq_sign = 0.815655`
- calibrated sign floor = `0.755935`
- 結果：**已通過**

## 6. What Phase2 Actually Proved

Phase2 現在真正證實的是：

1. `soft_band_refine` 對 `0.8px absolute center` 的改善是真實且巨大的
2. `soft_band_refine` 並不是因為 macro 行為完全崩壞才失敗
3. 原始 `not_confirmed` 的理由過度依賴了不相容的絕對 `8px` guard

## 7. What Phase2 Did NOT Prove

Phase2 也同樣證明：

1. `soft_band_refine` 還不能直接變成下一個正式 training round 的唯一 estimator policy
2. 它目前仍沒有把 `0.8px step_err` 壓到可接受區間
3. 因此不能因為 center 大幅改善，就跳過 step gate 直接立 `Round21`

## 8. Frozen Estimator Policy After Reevaluation

截至這份 postmortem：

### Active baseline policy

- `0.08px`: `edge_centroid`
- `0.8px`: `edge_centroid`
- `8px`: `edge_centroid`

### Provisional hybrid policy

- `0.08px`: `edge_centroid`
- `0.8px`: `soft_band_refine`
- `8px`: `edge_band_refine`

但這份 hybrid policy 目前狀態仍然是：

- `round21_ready = false`

正式 machine-readable truth：

- `D:\GMM_2_Final\ESTIMATOR_POLICY.json`

## 9. Final Decision

`Round21` 現在不應啟動。

不是因為 estimator-side 被否定，
而是因為 estimator-side 已經證明有用，但還**沒有被調和成可放行的 mid-scale policy**。

目前唯一正確的下一步是：

- **針對 `soft_band_refine` 做 estimator-side step reconciliation / formula redesign**

而不是：

- 回頭做 `center_w / abs_center_w` 掃描
- 再開新的 generic autotune round
- 直接做 external recon
