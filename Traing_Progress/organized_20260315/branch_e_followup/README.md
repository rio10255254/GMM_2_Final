# Branch E Follow-up

這個目錄承載 `Branch E` 的 follow-up probe、校準後重判，以及 `Round21` 前的最終 blocking 結論。

## What This Folder Means

`branch_e_followup` 不是新的正式 deploy round。

它的角色是：

1. 用延長版 `0.8px` probe 再測 estimator-side 候選
2. 對 `0.8px` 與 `8px` guard 做 process audit
3. 把原始 Phase2 結論和校準後 reevaluation 分開
4. 在真正立 `Round21` 前，明確回答 hybrid estimator policy 是否已可放行

## Current Conclusion

截至 2026-03-15：

- `soft_band_refine` 在 `0.8px` 的 absolute center 上有非常強的優勢
- 舊的 `8px step <= 0.04` guard 已被判定不適用於這套 process-audit harness
- control-relative guard 校準後，`soft_band_refine` 已通過 macro guard
- 但它仍未通過 `0.8px step_err <= 0.45`
- 所以 `Round21` 仍 blocked

## Main Artifacts

- original phase2 decision:
  `selected\reports\BRANCH_E_PHASE2_DECISION_20260315_154300.md`
- calibrated reevaluation:
  `selected\reports\BRANCH_E_PHASE2_REEVALUATION_20260315_203359.md`
- postmortem:
  `BRANCH_E_PHASE2_POSTMORTEM.md`
- machine-readable policy truth:
  `ESTIMATOR_POLICY.json`
- manifest:
  `selected\current_branch_e_phase2_seed.json`

## Layout

```text
branch_e_followup/
├── BRANCH_E_PHASE2_POSTMORTEM.md
├── selected/
│   ├── current_branch_e_phase2_seed.json
│   └── reports/
├── archive/
│   ├── runs/
│   ├── audit_runs/
│   └── smoke_runs/
└── pending/
    └── logs/
```
