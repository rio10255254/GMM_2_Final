# 20260309 Restart 批次

## 啟動方式

- 先跑 `round4_refine_seed`
- 再由 supervisor 依序接：
  1. `round3_gmf_guard`
  2. `round3_sharp_balance`

## 設計理由

- `round4_refine_seed`：更貼近現有 seed，做小幅保守微調
- `round3_gmf_guard`：主攻已知 8px 步長穩定度
- `round3_sharp_balance`：在不大幅傷 GMF 的前提下補邊界銳利感

## 修正點

- 先前 `no_weakpsf` 類候選會因模型結構與 seed 權重不相容而失敗
- 已改成保留 weak-PSF 結構，但在 runtime 幾乎關閉其作用，避免浪費候選
