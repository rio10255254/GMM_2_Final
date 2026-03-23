# PROJECT ARCHITECTURE AND DECISION MAP
Last updated: 2026-03-20

## Purpose

這份文件只描述**穩定架構與決策規則**。

它回答：

- 系統真正目標是什麼
- external truth 與 internal surrogate 的關係
- 目前正式 baseline policy 是什麼
- 什麼情況下才值得立新 round
- 升級 baseline 的必要條件是什麼

它**不**負責展開當前 round 的逐步進度，也**不**負責做跨入口 handoff。

## Layer A — External Truth

最終真值永遠是 external GMF 的 whole-annulus 幾何定位表現。

external GMF 真正在乎：

- whole-annulus 幾何支撐
- absolute center stability
- pairwise step geometry
- sign monotonicity

它不直接在乎一般視覺銳利度，也不接受 internal gate 直接替代。

## Layer B — Internal Surrogate

internal surrogate 是代理，不是 external GMF 本身。

目前穩定存在的 surrogate 類型：

1. `seq_val`
2. `ann_seq`
3. full deploy audit
4. process-audit harness
5. estimator benchmark
6. pairwise delta probe
7. GMF residual / anchor autocorr analysis
8. internal-external correlation analysis

### Stable interpretation

- full deploy audit：選 deploy candidate
- process-audit harness：驗證單一技術假說
- pairwise delta probe：驗證 `pairmix_algblend` 主線
- internal-external correlation：找 screening 指標，不可替代 external

## Layer C — Optimization Target

目前真正主 target 已收斂為：

1. 維持 `Round30 / r30_b1_dironly` 在 external 主戰場 `0.8px` 的優勢
2. 不犧牲 `8px` macro guard
3. 只在有新機制或高價值微調時再開新 round

## Stable Architecture Boundary

從 2026-03-20 起，這個 repo 的 stable boundary 明確分成兩層：

- **root shared mainline**
  - 維持 `R26 / R30 / shared stable workflow`
  - 不再繼續吸收 `R32` 專用 loader / audit / launcher / monitor
- **`Experiments\R32Sandbox\`**
  - `R32` 專用實驗分支
  - 自己維護訓練、profile、audit、runtime、external compare

這表示：

- `R32` 仍是 active 研究方向
- 但它已不再代表 root shared mainline 的運行面
- `R32 real_eq` 已被 external GMF 否定，因此 sandbox 若要續做，下一步必須是新分支 / 新機制

## Stable Artifact Map

### Shared mainline

- `Model\GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
- `Model\GeoEdgeAlignSR_v1_AutoTuneTrain.py`
- `Model\GeoEdgeAlignSR_v1_LongRunRound*.py`
- `Model\GeoEdgeAlignSR_v1_ProcessProbeAudit.py`
- `Model\GeoEdgeAlignSR_v1_ExternalGMF*.py`

### R32 sandbox

- `Experiments\R32Sandbox\Model\train_r32.py`
- `Experiments\R32Sandbox\Model\autotune_r32.py`
- `Experiments\R32Sandbox\Model\process_probe_audit_r32.py`
- `Experiments\R32Sandbox\Model\longrun_round32.py`
- `Experiments\R32Sandbox\Model\external_gmf_round32_compare.py`
- `Experiments\R32Sandbox\runtime\R32_STATUS.md`

## Current Baseline Policy

目前正式 baseline policy：

- `0.08px`: `edge_centroid`
- `0.8px`: `pairmix_algblend`
- `8px`: `edge_band_refine`
- baseline status: `final_production_baseline`
- current adopted production checkpoint: `Round30 / r30_b1_dironly`

唯一 machine-readable truth：

- `D:\GMM_2_Final\ESTIMATOR_POLICY.json`

## Confirmed Findings

### Confirmed effective

- `pairwise delta reconciliation` 是有效方向
- `pairmix_algblend` 已在 `Round25/26/30` 被 external GMF 支持
- `Round30 / r30_b1_dironly` 是 current production baseline
- `B1 dironly` 是已被 external 證實有效的新機制方向
- `center_err` 是目前最有價值的 Tier2 screening 指標

### Confirmed falsified

- `step_mag < 0.35` downsweep 不能改善 `R26`
- `step_mag > 0.35` upper sweep 也不能改善 `R26`
- `TTA C2` 不能改善主戰場 `0.8px`
- `A1 / A5 / S1` side-directions 未能擊敗 `B1 dironly`
- `Round31` measured B1 hyperparam candidates 未能擊敗 `Round30 / r30_b1_dironly`
- `R32 sandbox winner r32_real_eq_finetune` 未能通過 external final gate

### Confirmed caution

- internal gate 是必要條件，不是充分條件
- `step_err` 不能單獨預測 external GMF
- `center_err` 雖是目前最佳 Tier2 predictor，但不能替代 external
- 缺 artifact 的候選不能被硬寫成 external verdict
- external final gate 仍然是 **whole-annulus GMF**，不因 sandbox 化而改變

## Decision Rules

### Baseline adoption rule

只有同時滿足以下條件，才允許升級 current adopted baseline：

1. internal calibrated gate 通過
2. external GMF 主戰場 `0.8px` 明確不差於現 baseline
3. `8px` macro guard 不明顯退步
4. 若 side-scale 有 trade-off，必須有明確工程理由支持

### New round rule

新 round 只有在以下情況才值得立案：

- 有一個和既有失敗分支不同的新機制假說
- 或是在既有成功主線上做可驗證且成本合理的微調
- 目標是挑戰現 baseline
- 預計比較對象明確包含現 baseline

以下情況不應再立 round：

- 重掃已否定的 `step_mag < 0.35`
- 重掃已否定的 `step_mag > 0.35`
- 重開 `Round23/24` 型 fine-tune abs/anchor branch
- 只靠 internal gate 就預設 external 會變好

### Current stable decision boundary

截至 2026-03-20，穩定規則層只有一件事不變：

- 真正成功條件仍是：external `0.8px step std < 0.167862`

當前 `R32` 的執行細節與 process-level 狀態不寫在這份文件，請看：

- `PROJECT_CURRENT_STATE.md`
- `Experiments\R32Sandbox\runtime\R32_STATUS.md`

穩定規則層的最新判讀是：

- `R32 real_eq` 已 externally falsified
- `Round30 / r30_b1_dironly` 仍是唯一 production baseline
- 若要續做 `R32`，不應延用 `r32_real_eq_finetune` 當 current promising line

## Source of Truth Rules

- current truth:
  `PROJECT_CURRENT_STATE.md`
- cross-interface handoff:
  `PROJECT_SESSION_CONTINUITY.md`
- stable architecture / decision rules:
  `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- full historical narrative:
  `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
- machine-readable policy truth:
  `ESTIMATOR_POLICY.json`
