# ROUND20 POSTMORTEM
Date: 2026-03-14

## Goal

Round20 不是新部署模型 round，而是流程驗證 round。

唯一要回答的問題：

- `round19` 沒突破，主因是不是 `Epoch 0 baseline` 直接佔住 `best_proxy / best_tradeoff`，讓新 loss 沒有機會成熟

## Design

固定只做 `0.8px` 單尺度 process probe。

候選：

- `r20_ctrl_r19aa`
  - baseline 可直接成為 best
  - 4 epochs
- `r20_unlock_r19aa`
  - baseline 不可直接成為 best
  - 4 epochs
- `r20_unlocklong_r19aa`
  - baseline 不可直接成為 best
  - 8 epochs
- `r20_unlock_r19as`
  - baseline 不可直接成為 best
  - 8 epochs

## Execution Notes

Round20 第一次啟動曾因程序生命週期問題中途中止。

之後已重新以真正分離的背景程序重啟，完整跑完。

失敗啟動 log 已收進：

- `archive/logs/longrun_round20_20260314_195659.failed.out.log`
- `archive/logs/longrun_round20_20260314_195659.failed.err.log`

## Final Result

正式狀態：

- `state: completed`
- `selected_candidate: r20_ctrl_r19aa`
- `supports_baseline_lock_hypothesis: false`

正式入口：

- root status:
  `000_LONGRUN_ROUND20_STATUS.md`
- process summary:
  `Experiments/Legacy/organized_20260314/round20/selected/reports/ROUND20_PROCESS_PROBE_SUMMARY_20260314_205446.md`
- audit summary:
  `Experiments/Legacy/organized_20260314/round20/selected/reports/ROUND20_PROCESS_PROBE_AUDIT_SUMMARY_20260314_205446.md`

## Key Numbers

Family summary：

- `r20_unlock_r19as`
  - `c0 = 0.7295`
  - `cbest = 0.7523`
  - `dc = +0.0229`
  - `sbest = 0.2078`
- `r20_unlock_r19aa`
  - `c0 = 0.7295`
  - `cbest = 0.7531`
  - `dc = +0.0237`
  - `sbest = 0.2079`
- `r20_unlocklong_r19aa`
  - `c0 = 0.7295`
  - `cbest = 0.7531`
  - `dc = +0.0237`
  - `sbest = 0.2079`
- `r20_ctrl_r19aa`
  - `c0 = 0.7295`
  - `cbest = 0.7295`
  - `dc = 0.0000`
  - `sbest = 0.2167`

Single-scale process audit：

- `r20_ctrl_r19aa`
  - `best_center_err = 0.6487`
  - `best_step_err = 0.2482`
- `r20_unlock_r19as`
  - `best_center_err = 0.6593`
  - `best_step_err = 0.2391`
- `r20_unlock_r19aa`
  - `best_center_err = 0.6598`
  - `best_step_err = 0.2398`
- `r20_unlocklong_r19aa`
  - `best_center_err = 0.6598`
  - `best_step_err = 0.2398`

最重要結果：

- `center_improvement_vs_control = 0.000000`

## Interpretation

Round20 否定了：

- `baseline 壟斷是 0.8px center_err 平台的主因`

原因：

1. unlock 類候選在 family summary 中看起來較好，是因為它們被刻意免除 baseline 直接成為 best 的規則影響。
2. 但真正重新 audit 後，control 仍然是最佳。
3. 更關鍵的是，audit 時四個候選最後都回到：
   - `best_epoch_is_baseline = true`
   - `best_minus_epoch0_center_err = 0.0`

這表示：

- 問題不是規則讓 baseline 被偏愛
- 而是後續訓練出的 checkpoint 本身沒有真的超越 baseline

## What Round20 Eliminated

Round20 讓以下方向的優先級大幅下降：

- 再調 `BASELINE_ELIGIBLE_FOR_BEST`
- 再調 `BEST_PROXY_MIN_EPOCH`
- 再做 `4 epoch vs 8 epoch` 類 process probe

這些不再是主要突破口。

## What Remains

Round20 之後，真正值得優先驗證的只剩兩類：

1. estimator-side
   - `edge_centroid` 是否存在 absolute center bias floor
   - `algebraic_fit` 是否在 absolute center 更穩

2. label-side
   - GT / clean / convolved / SR 的 center supervision 是否 mismatch
   - 模型是否只學到 delta-center，而沒有學到 absolute center

## Decision

Round21 不應直接繼續訓練。

下一步應先做診斷矩陣，回答：

- 在 GT / clean / convolved / SR 上，absolute center error 的 floor 到底來自 estimator 還是 label/target

只有在這個診斷表完成後，才決定：

- Branch E: estimator-side
- Branch L: label-side
