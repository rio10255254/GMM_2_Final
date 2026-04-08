# PROJECT SESSION CONTINUITY / 專案會話銜接文件
Last updated: 2026-03-27

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

## Handoff Snapshot / 交接快照

- current production baseline / 目前正式 production baseline: `Round30 / r30_b1_dironly`（pending R33 promotion）
- latest completed external compare / 最近完成的 external compare: **`R38v2 external GMF — ALL PASS`** (2026-04-07)
- **three production candidates / 三個生產候選**:
  - **R33 hard_p95（GMF 極致型）**: 0.8px 0.119 (-29%), steepness -22%
  - **R38v2 8px_gate（視覺優先型）**: 0.8px 0.134 (-20%), steepness +89%
  - **COMBO 8px_gate_p95（最均衡型）**: 0.8px 0.132 (-22%), steepness +89%, residual_std 歷史最佳
- R33 checkpoint: `Traing_Progress/..._20260405_091941/weights/best_tradeoff.pth.tar`
- R38v2 checkpoint: `Traing_Progress/..._20260406_235957/weights/best_tradeoff.pth.tar`
- COMBO checkpoint: `Traing_Progress/..._20260408_003525/weights/best_tradeoff.pth.tar`
- falsified directions (R34-R37, R38, R33c): 5 rounds all failed to break sharpness-stability trade-off
- R38v2 success mechanism: warmup 15 epochs → signal gate 0.002 → 8px-only seq training
- PSF policy: 新 Whole-FOV PSF 自 2026-03-27 為 current standard
- previous sandbox: `R26NewPSFCheck`（PSF 已切換；外部 GMF 仍待定）
- **quantization fix (2026-04-08)**: 推理 denormalize 從截斷改為四捨五入（np.rint）
  - R33: 0.8px 0.119→0.117 改善；8px outlier 消除（更穩健）
  - R38v2: 8px 0.144→0.122 大幅改善；0.8px 0.134→0.147 退步（steep edge 對量化敏感）
- tracked legacy bridge copy / 已追蹤 legacy bridge 副本:
  `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.*`

## Conversation-Safe Verdict / 可安全沿用於對話的結論

- **`Round33 / r33_robust_p95` has passed external GMF on all three scales** (2026-04-05) / 已通過三尺度外部 GMF
- `Round30 / r30_b1_dironly` is still the formal production baseline pending R33 promotion / 在 R33 正式 promote 前仍是正式 baseline
- `Round33` mechanism: Winsorize spatial losses at 95th percentile (ROBUST_LOSS_PERCENTILE=0.95) / 機制：空間損失截尾
- `Round31` did not produce an upgrade / 沒有形成升級
- `Round32` internal winner completed the external gate, but the external verdict is FAIL / external 結論是 FAIL
- the generic `step_mag` sweep is closed; the externally verified optimum remains `0.35` / 已封閉
- the new Whole-FOV PSF is the `current standard` as of 2026-03-27 / 新 PSF 是 current standard
- `R26NewPSFCheck` external GMF results are still pending / 外部 GMF 結果仍待定
- R33 lag-1 autocorrelation is -0.55 (R30 was +0.27); noted but does not affect target / 已記錄但不影響目標

## Formal Entry Points / 正式入口

- current truth / 現況真相:
  `D:\GMM_2_Final\PROJECT_CURRENT_STATE.md`
- stable rules / 穩定規則:
  `D:\GMM_2_Final\PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
- machine-readable baseline policy / 機器可讀 baseline 政策:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`
- PSF policy transition / PSF 政策切換說明:
  `D:\GMM_2_Final\docs\policy\PSF_POLICY_TRANSITION_R26.md`
- machine-readable PSF policy / 機器可讀 PSF 政策:
  `D:\GMM_2_Final\docs\policy\PSF_STANDARD_POLICY.json`
- long history / 完整歷史:
  `D:\GMM_2_Final\docs\history\PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
- active sandbox overview / 目前 active sandbox 總入口:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\README.md`
- R32 sandbox overview（closed） / R32 sandbox 總入口（已關閉）:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- R32 external compare verdict（closed） / R32 外部比較 verdict（已關閉）:
  `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\README.md`

## Current Working Rule / 目前工作規則

新的 assistant / agent 接手時，先遵守以下規則：  
When a new assistant or agent takes over, follow these rules first:

1. 先讀這份文件與 `PROJECT_CURRENT_STATE.md`  
   Read this file and `PROJECT_CURRENT_STATE.md` first.
2. 以 repo 內正式文件為準，不以 `.codex` 內部 session 檔為準  
   Treat the repository’s formal docs as the source of truth, not internal `.codex` session files.
3. 不要把 live process-level 狀態手抄回 root prose；active sandbox 直接看 `Experiments\R26NewPSFCheck\`；R32 已關閉，看 `Experiments\R32Sandbox\runtime\` 只是查歷史
   Do not copy live process-level status back into root prose docs; for active sandbox status, read `Experiments\R26NewPSFCheck\` directly; `Experiments\R32Sandbox\runtime\` is historical only.
4. tracked 的 legacy root status 快照放在 `docs/runtime/legacy/root_status/`；若 root 再出現 `000_LONGRUN_*`，視為本地 runtime 輸出  
   Tracked legacy root-status snapshots live under `docs/runtime/legacy/root_status/`; if `000_LONGRUN_*` reappears at the root, treat it as local runtime output.
5. baseline、verdict、active experiment 有變時，優先回寫這份文件與 `PROJECT_CURRENT_STATE.md`  
   When the baseline, verdict, or active experiment changes, update this file and `PROJECT_CURRENT_STATE.md` first.
6. 當某個 sandbox winner 已完成 external FAIL 後，不要再把它寫成 current promising line；下一步應改寫成 new branch / new mechanism required  
   Once a sandbox winner has completed external FAIL, do not keep describing it as the current promising line; the next step must be reframed as a new branch or new mechanism.
