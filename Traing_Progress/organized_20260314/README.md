# organized_20260314

這個日期入口目前主要承載：

- `round20`
- `diagnostics`
- `branch_e`

Round20 不是新模型競賽，而是流程驗證 round。

目的：

- 驗證 `round19` 沒突破，主因是不是 `Epoch 0 baseline` 壟斷選模

目前結論：

- `baseline-lock hypothesis not supported`
- 也就是說，plateau 不是 baseline 壟斷造成的主因

快速入口：

- round root:
  `D:\GMM_2_Final\Traing_Progress\organized_20260314\round20`
- round20 postmortem:
  `D:\GMM_2_Final\Traing_Progress\organized_20260314\round20\ROUND20_POSTMORTEM.md`
- selected audit summary:
  `D:\GMM_2_Final\Traing_Progress\organized_20260314\round20\selected\reports\ROUND20_PROCESS_PROBE_AUDIT_SUMMARY_20260314_205446.md`
- diagnostic matrix summary:
  `D:\GMM_2_Final\Traing_Progress\organized_20260314\diagnostics\DIAGNOSTIC_MATRIX_SUMMARY_20260314_232403.md`
- round21 branch decision:
  `D:\GMM_2_Final\Traing_Progress\organized_20260314\diagnostics\ROUND21_BRANCH_DECISION.md`

最新方向：

- `baseline-lock` 已被否定
- 下一步主分支已鎖定為：
  - `Branch E: estimator-side`

結構規格仍沿用：

```text
roundNN/
├── selected/
│   ├── runs/
│   ├── reports/
│   └── current_*_seed.json
├── archive/
│   ├── runs/
│   ├── audit_runs/
│   ├── logs/
│   └── status_legacy/
└── pending/
    └── logs/
```

## Legacy Governance Entry Points

若要安全回頭操作這個 batch，請另外使用：

1. `MANIFEST.md`
2. `..\..\docs\index\LEGACY_ROUNDS_OPERATIONS.md`
3. `round20\README.md`
4. `diagnostics\README.md`
5. `branch_e\README.md`

這些治理檔是後補導引層，不改動原始 probe、decision 或 archive 內容。
