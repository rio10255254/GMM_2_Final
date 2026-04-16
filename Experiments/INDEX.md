# 實驗索引 / Experiment Index

Last updated: 2026-04-14

一頁式快速索引——完整數字、checkpoint 路徑、外部 GMF 結果見 `ESTIMATOR_POLICY.json` 與各實驗 `reports/`。

視覺 demo 圖（每輪代表性重建圖 / 指標圖）見 `RECON_GALLERY.md`。

---

## Active（formal baseline + approved alternates）

| Round | 目錄 | Branch | 角色 | 關鍵報告 |
|-------|------|--------|------|---------|
| **COMBO** | `R38v2SeqFixed/` | `sandbox/r38v2` | formal production baseline | `R38v2SeqFixed/reports/COMBO_RESULTS.md` |
| **R33** | `R33RobustLoss/` | `sandbox/r33` | GMF extreme alternate | `R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md` |
| **R38v2** | `R38v2SeqFixed/` | `sandbox/r38v2` | visual priority alternate | `R38v2SeqFixed/reports/R38v2_RESULTS.md` |

## Open Side Track

| Round | 目錄 | 狀態 |
|-------|------|------|
| R26 PSF | `R26NewPSFCheck/` | pending external GMF; not active mainline |

## Closed / Falsified

| Round | 目錄 | Branch | Verdict |
|-------|------|--------|---------|
| R32 | `R32Sandbox/` | `sandbox/r32` | external FAIL, 0.8px +97.7% |
| R33c | `R33ContrastFix/` | `sandbox/r33-contrast` | contrast fix did not recover |
| R34 / R35 / R37 | (sandbox only) | `sandbox/r34` / `r35` / `r37` | all failed to restore sharpness |
| R38 | `R38SeqConsistency/` | `sandbox/r38` | seq all-stages noise corrupted 0.8px |

Round31（legacy batch）亦 closed，見 `Traing_Progress/organized_20260316/round31/`。

## 完整系列報告

R33 → R38v2 → COMBO 的 12 候選 / 7 輪完整系列見 `R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`。

## 規範文件

- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 命名、模板、SOP 三合一
- `docs/operations/QUIRKS.md` — 歷史遺留事項
