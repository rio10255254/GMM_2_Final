# Round21 Branch Decision
Date: 2026-03-14

## Inputs

- round20 postmortem:
  `Traing_Progress/organized_20260314/round20/ROUND20_POSTMORTEM.md`
- diagnostic matrix summary:
  `Traing_Progress/organized_20260314/diagnostics/DIAGNOSTIC_MATRIX_SUMMARY_20260314_232403.md`

## Decision

下一步主分支鎖定為：

- **Branch E: estimator-side**

## Why

這次診斷不是看 internal deploy score，而是直接把現行訓練幾何估計器拿去對 generator replay 真值。

在主戰場 `0.8px` 上，最重要的事實是：

- `clean / edge_centroid`
  - `abs_center_err_px = 83.5683`
  - `delta_center_err_px = 1.1424`
- `convolved / edge_centroid`
  - `abs_center_err_px = 122.6426`
  - `delta_center_err_px = 3.0021`
- `clean / algebraic_fit`
  - `abs_center_err_px = 138.7895`
  - `delta_center_err_px = 0.7980`
- `convolved / algebraic_fit`
  - `abs_center_err_px = 138.7729`
  - `delta_center_err_px = 0.7976`

這表示：

1. 問題不是只在 SR 才出現
2. 問題不是先從 label-side 才開始
3. 現行訓練幾何 estimator 在 clean / convolved 上就已經明顯偏離真值

因此，`Round19` 和 `Round20` 前面那條以：

- `edge_centroid`
- `algebraic_fit`
- `center_w / abs_center_w`

為核心的訓練優化鏈，實際上是在對一個已經失真的上游幾何 proxy 做優化。

## What This Eliminates

這個結論讓以下方向不再是下一步主線：

- 再做 `center_w` 掃描
- 再做 `abs_center_w` 掃描
- 再做 process-probe round
- 先做 label-side / target-side round

## What Branch E Means

Branch E 不是直接再開訓練，而是先回答：

1. 目前的 annulus center estimator 為什麼在 clean / convolved 就失真
2. external / audit 真正需要的 center estimator，應該如何對齊
3. 訓練 loss 應該綁定哪個 estimator 或 estimator-aligned target

## Concrete Next Step

在真正立 `Round21` 之前，先做 estimator-side 診斷與替代方案比較：

1. 重檢 `edge_centroid` 的 edge source
2. 重檢 `algebraic_fit` 的輸入權重是否合理
3. 設計至少一個新的 estimator-aligned annulus center extractor
4. 用同一套 generator replay 真值，再跑一次 clean / convolved / SR 對照

只有當 estimator-side 替代方案在 clean / convolved 上先站住，才值得把它接進下一輪訓練。
