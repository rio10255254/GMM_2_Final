# PROJECT SESSION CONTINUITY / 專案會話銜接文件
Last updated: 2026-03-20

## Purpose / 用途

### 繁體中文

這份文件只負責跨入口 handoff。  
它回答三件事：

1. 接手時應先讀哪幾份文件
2. 目前最重要、最穩定的已確認事實是什麼
3. 接手時有哪些工作規則不能搞錯

它**不**負責展開完整現況細節，也**不**負責定義穩定架構規則。

### English

This file exists only for cross-interface handoff. It answers three questions:

1. Which files a new owner should read first
2. What the highest-value confirmed facts currently are
3. Which operating rules must not be misunderstood during handoff

It does **not** expand full current-state detail, and it does **not** define the
stable architecture rules.

## Read Order / 閱讀順序

### 繁體中文

固定閱讀順序：

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

### English

Recommended fixed read order:

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Handoff Snapshot / 交接快照

- current production baseline / 目前正式 production baseline: `Round30 / r30_b1_dironly`
- latest completed external compare / 最近完成的 external compare: `Round32 sandbox external GMF compare`
- latest verified verdict / 最近已驗證 verdict:
  `r32_real_eq_finetune` external FAIL；`Round30 / r30_b1_dironly` baseline unchanged
- current active direction / 目前 active 方向:
  `R32 post-falsification branch design`（若續做，需另立新分支 / 新機制）
- current sandbox verdict carrier / 目前 sandbox verdict carrier:
  `Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`
- current live runtime / 目前 live runtime:
  `Experiments\R32Sandbox\runtime\R32_STATUS.md`
- tracked legacy bridge copy / 已追蹤 legacy bridge 副本:
  `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.*`

## Conversation-Safe Verdict / 可安全沿用於對話的結論

- `Round30 / r30_b1_dironly` remains the formal production baseline / 仍是正式 production baseline
- `Round31` did not produce an upgrade; `r31_eq_combo` is missing an external artifact and must not be written as a measured verdict / 沒有形成升級；`r31_eq_combo` 缺 external artifact，不能硬寫成 measured verdict
- `Round32` internal winner completed the external gate, but the external verdict is FAIL / internal winner 已完成 external gate，但 external 結論是 FAIL
- `R32 real_eq` should now be treated as an externally falsified experimental branch / 這條線應視為 externally falsified experimental branch
- `A1 / A5 / S1 / TTA` are not current upgrade directions / 都不是目前升級方向
- the generic `step_mag` sweep is closed, and the externally verified optimum remains `0.35` / generic `step_mag` sweep 已封閉，externally verified optimum 仍是 `0.35`

## Formal Entry Points / 正式入口

- current truth / 現況真相:
  `D:\GMM_2_Final\PROJECT_CURRENT_STATE.md`
- stable rules / 穩定規則:
  `D:\GMM_2_Final\PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- machine-readable policy / 機器可讀政策:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`
- long history / 完整歷史:
  `D:\GMM_2_Final\docs\history\PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
- sandbox overview / sandbox 總入口:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- sandbox runtime / sandbox runtime:
  `D:\GMM_2_Final\Experiments\R32Sandbox\runtime\R32_STATUS.md`
- sandbox external compare verdict / sandbox external compare verdict:
  `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\README.md`

## Current Working Rule / 目前工作規則

### 繁體中文

新的 assistant / agent 接手時，先遵守以下規則：

1. 先讀這份文件與 `PROJECT_CURRENT_STATE.md`
2. 以 repo 內正式文件為準，不以 `.codex` 內部 session 檔為準
3. 不要把 live process-level 狀態手抄回 root prose；active sandbox 直接看 `Experiments\R32Sandbox\runtime\`
4. tracked 的 legacy root status 快照放在 `docs/runtime/legacy/root_status/`；若 root 再出現 `000_LONGRUN_*`，視為本地 runtime 輸出
5. baseline、verdict、active experiment 有變時，優先回寫這份文件與 `PROJECT_CURRENT_STATE.md`
6. 當某個 sandbox winner 已完成 external FAIL 後，不要再把它寫成 current promising line；下一步應改寫成 new branch / new mechanism required

### English

When a new assistant or agent takes over, follow these rules first:

1. Read this file and `PROJECT_CURRENT_STATE.md` first.
2. Treat the repository’s formal docs as the source of truth, not internal `.codex` session files.
3. Do not copy live process-level status back into root prose docs; for active sandbox status, read `Experiments\R32Sandbox\runtime\` directly.
4. Tracked legacy root-status snapshots live under `docs/runtime/legacy/root_status/`; if `000_LONGRUN_*` reappears at the root, treat it as local runtime output.
5. When the baseline, verdict, or active experiment changes, update this file and `PROJECT_CURRENT_STATE.md` first.
6. Once a sandbox winner has completed external FAIL, do not keep describing it as the current promising line; the next step must be reframed as a new branch or new mechanism.
