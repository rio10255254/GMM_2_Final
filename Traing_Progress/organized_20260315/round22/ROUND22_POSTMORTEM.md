# ROUND22 Postmortem
Last updated: 2026-03-16

## Purpose

`Round22` 的目的不是再找新的 generic loss 掃描方向，而是驗證一件更窄但更關鍵的事：

- `pairmix_algblend` 這個 pairwise estimator policy
- 能不能在正式的 `0.8px` training probe 裡
- 同時保住 `absolute center` 與 `pairwise step`

這一步承接的是：

- `Round21` 否定了 `soft_band_refine + step-focused training` 這條路
- `pairwise delta reconciliation probe` 證明 `pairmix_algblend` 可以把 `0.8px center/step` 一起拉進 calibrated gate

所以 `Round22` 的真正問題不是「再試試看訓練會不會剛好變好」，而是：

- 這條 pairwise policy 是否足夠穩，值得進入下一個正式 external 驗證階段

## Setup

- scale: `0.8px only`
- mid estimator: `pairmix_algblend`
- macro guard estimator: `edge_band_refine`
- tiny scale: only record, non-blocking
- resume baseline: `Round18 / r18_ec_highcenter`

候選：

1. `r22_pairmix_hold`
2. `r22_pairmix_stepguard`
3. `r22_pairmix_consistency`

## Result

### Formal selected artifact

- selected candidate: `r22_pairmix_stepguard`
- confirmed: `true`
- selected checkpoint:
  `D:\GMM_2_Final\Traing_Progress\organized_20260315\round22\selected\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r22ps_20260315_225625\weights\best_tradeoff.pth.tar`

### Calibrated gate result

`0.8px`

- `center_err = 0.1845`
- `step_err = 0.0657`
- `center_improvement_ratio = 0.9785`

`8px macro guard`

- `step_err = 0.1155`
- `seq_sign_acc = 0.8157`

結論：

- calibrated `mid + macro` gate 通過
- `Round22` 是目前第一個正式通過 pairmix internal gate 的 training round

## Important Nuance

這一輪必須誠實記錄一個差異：

### Raw family summary

`ROUND22_PAIRMIX_HYBRID_SUMMARY_20260315_230314.md` 顯示：

- `best_family_candidate = r22_pairmix_hold`

而且 raw family 指標是：

- `r22_pairmix_hold`: `cbest = 0.1508`, `sbest = 0.0768`
- `r22_pairmix_stepguard`: `cbest = 0.1845`, `sbest = 0.0657`

### Raw mid audit

`ROUND22_PAIRMIX_HYBRID_AUDIT_0P8_SUMMARY_20260315_230314.md` 也顯示：

- `r22_pairmix_hold` 的 raw `center` 更好
- `r22_pairmix_stepguard` 的 raw `step` 更好

### Why the formal selected artifact is still `stepguard`

目前正式 decision chain 仍保留了比較保守的 step-first 傾向，因此：

- raw `mid-only` 最強行是 `hold`
- 但 formal selected artifact 仍落在 `stepguard`

這不是需要隱藏的矛盾，而是需要保留的工程事實：

- **`pairmix_algblend` 這條 policy 已經成立**
- 但 `Round22` 內部三個候選彼此之間的最終選擇，仍然帶有 decision policy 的權衡

## Interpretation

`Round22` 真正證明的不是：

- 訓練 schedule 本身多強

而是：

- `pairmix_algblend` 這種 `single-frame anchor + pairwise delta estimator` 分治方式
- 已經足以在 internal calibrated gate 內，同時保住 `mid center` 與 `mid step`

這個轉折很重要，因為它代表專案的主解方向已經從：

- generic loss scan

轉成：

- **pairwise geometry policy**

## What Round22 Does Not Prove

`Round22` 目前還沒有證明：

1. external GMF 一定會跟著過
2. `r22_pairmix_stepguard` 一定比 `r22_pairmix_hold` 更適合 external
3. 這條路已經是最終 universal solution

它目前只證明：

- internal calibrated route 已經打通
- 值得進到 external recon / GMF 驗證

## Next Step

下一步不該再回頭做 generic autotune，也不該再做同型 step-focused 掃描。

最合理的下一步是：

1. 用 `Round22` 正式候選做 external reconstruction
2. 跑三尺度 external GMF
3. 比較：
   - `Round18 baseline`
   - `Round22 pairmix`
4. 再決定：
   - `r22_pairmix_stepguard` 是否足以升級成 current adopted model
   - 或是否需要在 `stepguard` / `hold` 之間做更嚴格的 external tie-break
