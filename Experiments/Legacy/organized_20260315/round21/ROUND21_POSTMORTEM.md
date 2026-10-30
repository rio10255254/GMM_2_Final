# ROUND21 POSTMORTEM
Last updated: 2026-03-15 22:40:24

## Purpose

Round21 的目標是驗證：

- 若固定 `soft_band_refine` 為 `0.8px` 的 mid estimator
- 再用較高的 `SEQ_STEP_MAG_WEIGHT`
- 是否就能把 `soft_band` 的 center 優勢保留，同時把 `step_err` 拉回 calibrated gate

## What Was Tried

候選固定 3 個：

1. `r21_midsoft_ctrlguard`
2. `r21_midsoft_stepup`
3. `r21_midsoft_stephard`

共同點：
- `SEQ_GEOM_METHOD = soft_band_refine`
- `0.8px only`
- `skip-final = true`
- `deterministic = true`

## Result

三個候選最後在 calibrated audit 裡都回到同一個 baseline：

- `best_epoch = 0`
- `best_epoch_is_baseline = true`
- `0.8px center_err = 0.1862`
- `0.8px step_err = 0.5804`

同時：
- `8px` macro guard 通過
- 失敗點只剩 `0.8px step_err > 0.45`

## What Round21 Falsified

Round21 否定了這條主假說：

- **只要把 `soft_band_refine` 當成 mid estimator，再提高 step-focused training，訓練就能把 mid-step 自動拉回 gate。**

## Practical Meaning

Round21 的失敗不代表 estimator-side 錯。
它代表的是：

- `soft_band_refine` 的 center 優勢是真實的
- 但單幀 estimator + 同型訓練權重調整，不足以修復 pairwise step

## Why The Next Step Became Pairwise Probe

Round21 最重要的訊號是：

- 問題不再像是單幀 absolute center 不夠準
- 而像是 pairwise delta 的重建方式本身有系統性 jitter / bias

因此後續轉向：
- 保留 `soft_band_refine` 作為 absolute anchor
- 另外為 pairwise delta 找更穩的 estimator

## Current Successor

Round21 的直接 successor 不是 `Round21b`。
而是：

- `pairwise delta reconciliation probe`
- winner: `pairmix_algblend`
- 結論：`Round22` 已可立案
