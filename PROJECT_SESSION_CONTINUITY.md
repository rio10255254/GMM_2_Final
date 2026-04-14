# PROJECT SESSION CONTINUITY / 專案會話銜接文件
Last updated: 2026-04-09

## Purpose / 用途

這份文件只負責跨入口 handoff。  
This file exists only for cross-interface handoff.

它回答三件事：  
It answers three questions:

1. 接手時應先讀哪幾份文件  
   Which files a new owner should read first
2. 目前最重要、最穩定的已確認事實是什麼  
   What the highest-value confirmed facts currently are
3. 接手時有哪些工作規則不能搞錯  
   Which operating rules must not be misunderstood during handoff

它**不**負責展開完整現況細節，也**不**負責定義穩定架構規則。  
It does **not** expand full current-state detail, and it does **not** define the stable architecture rules.

## Read Order / 閱讀順序

固定閱讀順序：  
Recommended fixed read order:

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

整體掌控與總體巡檢請使用 `python Tools/project_control_center.py`；它是官方控制入口，但不是新的 truth plane。

## Handoff Snapshot / 交接快照

- formal production baseline / 正式 production baseline: **`COMBO / r38v2_8px_gate_p95`**（effective 2026-04-08）
- former baseline / 前任 baseline: `Round30 / r30_b1_dironly`
- approved alternates / 核准特化候選:
  - `R33 / r33_robust_p95` — GMF extreme
  - `R38v2 / r38v2_8px_gate` — visual priority
- latest promotion decision / 最近正式決策: `COMBO` promoted from three externally verified candidates
- original winning experiment branch / 原始 winning experiment branch:
  `sandbox/r38v2`（the winning run came from this experiment branch; the required training/inference code is now present on `main`）
- COMBO checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\weights\best_tradeoff.pth.tar`
- R33 checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260405_091941\weights\best_tradeoff.pth.tar`
- R38v2 checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260406_235957\weights\best_tradeoff.pth.tar`
- current measurement caution / 目前量測注意事項:
  internal step_std is advisory-only once residual_std enters the low-noise regime; see `Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`
- open side track / 開放 side track:
  `R26NewPSFCheck` remains pending external GMF, but it is **not** the active mainline
- closed lines / 已關閉主線:
  `Round31` no upgrade, `Round32` external FAIL
- tracked legacy bridge copy / 已追蹤 legacy bridge 副本:
  `docs/archive/legacy_runtime_status/000_LONGRUN_ROUND32_STATUS.*`

## Conversation-Safe Verdict / 可安全沿用於對話的結論

- **`COMBO / r38v2_8px_gate_p95` is the formal production baseline** as of 2026-04-08
- `R33 / r33_robust_p95` remains the approved **GMF extreme** alternate
- `R38v2 / r38v2_8px_gate` remains the approved **visual priority** alternate
- `Round30 / r30_b1_dironly` is now the **historical former baseline**
- `Round31` did not produce an upgrade
- `Round32` completed the final external gate and failed
- the generic `step_mag` sweep is closed; the externally verified optimum within that line remains `0.35`
- the new Whole-FOV PSF is the current standard as of 2026-03-27
- `R26NewPSFCheck` is still pending external GMF, but it is an **open side track**, not the mainline

## Formal Entry Points / 正式入口

- current truth / 現況真相:
  `D:\GMM_2_Final\PROJECT_CURRENT_STATE.md`
- stable rules / 穩定規則:
  `D:\GMM_2_Final\PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- machine-readable decision control plane / 機器可讀決策控制面:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`
- formal baseline report / 正式 baseline 報告:
  `D:\GMM_2_Final\Experiments\R38v2SeqFixed\reports\COMBO_RESULTS.md`
- approved alternates / 特化候選入口:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\R33_EXPERIMENT_SUMMARY.md`
  `D:\GMM_2_Final\Experiments\R38v2SeqFixed\reports\R38v2_RESULTS.md`
- PSF policy transition / PSF 政策切換說明:
  `D:\GMM_2_Final\docs\policy\PSF_POLICY_TRANSITION_R26.md`
- machine-readable PSF policy / 機器可讀 PSF 政策:
  `D:\GMM_2_Final\docs\policy\PSF_STANDARD_POLICY.json`
- long history / 完整歷史:
  `D:\GMM_2_Final\docs\history\PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Current Working Rule / 目前工作規則

新的 assistant / agent 接手時，先遵守以下規則：  
When a new assistant or agent takes over, follow these rules first:

1. 先讀這份文件與 `PROJECT_CURRENT_STATE.md`  
   Read this file and `PROJECT_CURRENT_STATE.md` first.
2. 以 repo 內正式文件為準，不以 `.codex` 內部 session 檔為準  
   Treat the repository’s formal docs as the source of truth, not internal `.codex` session files.
3. root prose 的 current state 以 **COMBO + two approved alternates** 為主，不要再把 `R26NewPSFCheck` 描述成 active mainline
   Root prose current-state docs should center on **COMBO + two approved alternates**, not `R26NewPSFCheck` as an active mainline.
4. tracked 的 legacy root status 快照已封存到 `docs/archive/legacy_runtime_status/`；若 root 再出現 `000_LONGRUN_*`，視為本地 runtime 輸出  
   Tracked legacy root-status snapshots now live under `docs/archive/legacy_runtime_status/`; if `000_LONGRUN_*` reappears at the root, treat it as local runtime output.
5. baseline、verdict、alternate taxonomy 有變時，優先回寫這份文件、`PROJECT_CURRENT_STATE.md`、與 `ESTIMATOR_POLICY.json`
   When the baseline, verdict, or alternate taxonomy changes, update this file, `PROJECT_CURRENT_STATE.md`, and `ESTIMATOR_POLICY.json` first.
6. 當某條線被正式關閉或被降級為 side track 後，不要再用 active / promising line 的語言描述它
   Once a line is formally closed or downgraded to a side track, do not keep describing it as an active or promising mainline.
