# PROJECT SESSION CONTINUITY
Last updated: 2026-03-20

## Purpose

這份文件只做跨入口 handoff。

它回答三件事：

1. 現在應該先讀哪幾份文件
2. 目前已確認的最高價值事實是什麼
3. 接手時有哪些工作規則不能搞錯

它**不**展開完整現況細節，也**不**負責寫穩定架構規則。

## Read Order

固定閱讀順序：

1. `PROJECT_SESSION_CONTINUITY.md`
2. `PROJECT_CURRENT_STATE.md`
3. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
4. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Handoff Snapshot

- current production baseline: `Round30 / r30_b1_dironly`
- latest completed external compare: `Round32 sandbox external GMF compare`
- latest verified verdict: `r32_real_eq_finetune` external FAIL；`Round30 / r30_b1_dironly` baseline 不變
- current active direction: `R32 post-falsification branch design`（若續做，需另立新分支 / 新機制）
- current sandbox verdict carrier: `Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`
- current live runtime: `Experiments\R32Sandbox\runtime\R32_STATUS.md`
- tracked legacy bridge copy：
  `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.*`

## Conversation-Safe Verdict

- `Round30 / r30_b1_dironly` 仍是正式 production baseline
- `Round31` 沒有形成升級；`r31_eq_combo` 缺 external artifact，不能硬寫成 measured verdict
- `Round32` internal winner 已完成 external gate，但 external 結論是 FAIL
- `R32 real_eq` 這條線現在應視為 externally falsified experimental branch
- `A1/A5/S1/TTA` 都不是目前升級方向
- generic `step_mag` sweep 已封閉，externally verified optimum 仍是 `0.35`

## Formal Entry Points

- current truth:
  `D:\GMM_2_Final\PROJECT_CURRENT_STATE.md`
- stable rules:
  `D:\GMM_2_Final\PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- machine-readable policy:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`
- long history:
  `D:\GMM_2_Final\docs\history\PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
- sandbox overview:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- sandbox runtime:
  `D:\GMM_2_Final\Experiments\R32Sandbox\runtime\R32_STATUS.md`
- sandbox external compare verdict:
  `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\README.md`

## Current Working Rule

若有新的 assistant / agent 接手，先遵守：

1. 先讀這份文件與 `PROJECT_CURRENT_STATE.md`
2. 以 repo 內正式文件為準，不以 `.codex` 內部 session 檔為準
3. live process-level 狀態不要手抄回 root prose；active sandbox 直接看 `Experiments\R32Sandbox\runtime\`
4. tracked 的 legacy root status 快照放在 `docs/runtime/legacy/root_status/`；若 root 再出現 `000_LONGRUN_*`，視為本地 runtime 輸出
5. baseline、verdict、active experiment 有變時，優先回寫這份文件與 `PROJECT_CURRENT_STATE.md`
6. 當某個 sandbox winner 已完成 external FAIL 後，不要再把它寫成 current promising line；下一步應改寫成 new branch / new mechanism required
