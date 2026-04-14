# R26 — New PSF Check

| 欄位 | 值 |
|------|---|
| Round | 26 |
| Branch | — (PSF policy merged to main via PR #20-25) |
| Status | Completed: PSF policy switched 2026-03-27; external GMF pending |
| Mechanism | Whole-FOV PSF retrain + formal audit + pure PSF control |
| External GMF | Pending（R26NewPSFCheck 的 GMF 結果從未回填） |
| Checkpoint | `Traing_Progress/organized_20260316/round26/...` (multiple) |
| Key Reports | `reports/STATUS_20260326.md`, `psf_audit/PSF_FORMAL_AUDIT_20260326.md` |

## Start Here

此目錄有 16 個子目錄，結構複雜。入口：
1. `README.md` — 完整流程說明（含目錄結構圖 line 115+）
2. `reports/STATUS_20260326.md` — 整體進度摘要
3. `psf_audit/PSF_FORMAL_AUDIT_20260326.md` — PSF 流程審核結果
4. `formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md` — promote 比較

**新實驗不需要模仿此結構**。見 `docs/operations/STARTING_NEW_EXPERIMENT.md`。
