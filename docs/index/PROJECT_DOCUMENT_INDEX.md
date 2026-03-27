# 文件索引 / PROJECT DOCUMENT INDEX

Last updated: 2026-03-27

這份文件只做一件事：把 **canonical docs**、**sandbox docs**、**evidence docs**、與 **archive docs** 的責任邊界講清楚。  
This file does one job: clarify the responsibility boundaries between the canonical docs, sandbox docs, evidence docs, and archive docs.

## Canonical Core Surface / 核心正式文件層

這五份是接手主入口：  
These five files are the main handoff entry surface:

1. `README.md`
2. `PROJECT_SESSION_CONTINUITY.md`
3. `PROJECT_CURRENT_STATE.md`
4. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
5. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

分工如下：  
Their roles are:

- `README.md`
  總入口、閱讀順序、root 入口層與 docs 導航。  
  Top-level entry point, reading order, root surface, and docs navigation.
- `PROJECT_SESSION_CONTINUITY.md`
  跨入口 handoff。  
  Cross-interface handoff.
- `PROJECT_CURRENT_STATE.md`
  目前真相。  
  Current truth.
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
  穩定規則。  
  Stable rules and decision boundaries.
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
  完整歷史脈絡。  
  Full historical narrative and strategy context.

## Docs Surface / 導航文件層

- `docs/README.md`
  docs 區入口與子目錄導覽。
  Entry point and directory guide for the `docs/` area.
- `docs/analysis/RESEARCH_PATHS.md`
  研究路徑圖與 Mermaid 可視化入口（含里程碑數字表格）。
  Research-path map and Mermaid visualization entry (including milestone numbers table).
- `docs/evidence/README.md`
  精選實驗證據層的入口與用途說明。
  Entry point and purpose guide for the curated evidence layer.
- `docs/evidence/EVIDENCE_MAP.md`
  一頁式證據鏈地圖，回答每份 evidence 支撐哪個 baseline、falsified line、或 analysis 結論。
  A one-page evidence-chain map showing which evidence supports which baseline, falsified line, or analytical conclusion.
- `docs/policy/PSF_POLICY_TRANSITION_R26.md`
  R26 PSF 政策切換說明（2026-03-27）；說明新 PSF 成為 current standard 的理由與舊 PSF 的 legacy 定位。
  R26 PSF policy transition rationale (2026-03-27); explains why the new PSF is now the current standard and the legacy role of the old PSF.
- `docs/policy/PSF_STANDARD_POLICY.json`
  機器可讀的 PSF policy。
  Machine-readable PSF policy.
- `docs/index/PROJECT_DOCUMENT_INDEX.md`
  文件責任邊界與導航索引。
  Documentation responsibility map and navigation index.
- `docs/index/NEW_EXPERIMENT_SOP.md`
  新增實驗時的 branch、issue、Project、doc、與 PR 操作清單。
  The operational checklist for adding a new experiment, including branches, issues, Project updates, docs, and PRs.
- `docs/runtime/legacy/README.md`
  legacy runtime / root status curated copies 的保存規則。
  Preservation rules for legacy runtime and root-status curated copies.

## Sandbox Surface / Sandbox 文件層

### R26NewPSFCheck（目前 active sandbox）

- `Experiments\R26NewPSFCheck\README.md`
  sandbox 完整說明（流程、目錄結構、執行方式）。
  Full sandbox description including workflow, directory structure, and how to run.
- `Experiments\R26NewPSFCheck\reports\STATUS_20260326.md`
  整體進度摘要（2026-03-26 快照）。
  Overall progress summary (snapshot as of 2026-03-26).
- `Experiments\R26NewPSFCheck\formal_newpsf_candidate\reports\NEW_PSF_FORMAL_R26_COMPARE.md`
  新 PSF same-recipe promote 比較報告（verdict：PROMOTE，2026-03-27）。
  New PSF same-recipe promote comparison report (verdict: PROMOTE, 2026-03-27).
- `Experiments\R26NewPSFCheck\psf_audit\PSF_FORMAL_AUDIT_20260326.md`
  PSF 正式擬合流程的完整審核記錄。
  Complete audit record for the PSF formal fitting workflow.

### R32 Sandbox（已關閉，external FAIL 2026-03-20）

- `Experiments\R32Sandbox\README.md`
  sandbox 的總入口與完整歷史記錄。
  Main entry point and full historical record for the sandbox.
- `Experiments\R32Sandbox\runtime\R32_STATUS.md`
  sandbox 最終 runtime truth（已定案）。
  Final sandbox runtime truth (closed).
- `Experiments\R32Sandbox\external_compare\README.md`
  external compare 流程與 final verdict carrier（FAIL）。
  External compare flow and final-verdict carrier (FAIL).

## Machine-Readable Policy / 機器可讀政策層

- `ESTIMATOR_POLICY.json`
  shared mainline 的 machine-readable baseline policy truth。
  Machine-readable baseline policy truth for the shared mainline.
- `docs/policy/PSF_STANDARD_POLICY.json`
  R26 PSF 政策的 machine-readable truth（current standard vs. legacy empirical baseline）。
  Machine-readable PSF policy truth for R26 (current standard vs. legacy empirical baseline).

## Evidence Surface / 證據文件層

- `docs/evidence/README.md`
  curated tracked copies 的總入口。  
  Main entry for curated tracked copies.
- `docs/evidence/baseline/`
  支撐目前 baseline promotion 的核心證據。  
  Core evidence supporting the current baseline promotion.
- `docs/evidence/historical_baselines/`
  支撐 `R18/R22 -> Round25 -> R26 -> Round29` 的歷史 baseline path 證據。  
  Evidence supporting the historical baseline path from `R18/R22` through `Round25`, `R26`, and `Round29`.
- `docs/evidence/falsified/`
  支撐 Round31 / Round32 等正式否定性結果的核心證據。  
  Core evidence supporting formally falsified results such as Round31 and Round32.
- `docs/evidence/side_directions/`
  支撐 `TTA C2` 等重要 side-direction falsifications。  
  Evidence supporting important side-direction falsifications such as `TTA C2`.
- `docs/evidence/analysis/`
  支撐 correlation / screening 等綜合分析證據。  
  Evidence for analytical conclusions such as correlation and screening logic.
- `docs/evidence/runtime/`
  小型 canonical runtime truth snapshots。  
  Small canonical runtime-truth snapshots.

## Legacy Bridge / Legacy 橋接層

- `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.md`
- `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.json`

這兩份目前只保留為 **tracked legacy bridge copy**，不再是長期 canonical runtime state，也不應用來判讀 `R32` external verdict。若舊腳本在 root 再生成同名檔案，視為本地 runtime 輸出，不再進 Git。  
These files are kept only as tracked legacy bridge copies. They are no longer the canonical runtime state and should not be used to interpret the `R32` external verdict. If old scripts recreate same-named files at the root, treat them as local runtime outputs rather than tracked Git content.

## Archive / Non-Core / 歸檔與非核心層

- `Project_Archive\`
  conversation scan、maintenance artifact 等非核心文件。  
  Non-core material such as conversation scans and maintenance artifacts.
- `_deployment_package\`
  外部交付鏡像。  
  External delivery/package mirror.
- `Trash_Archive\`
  淘汰內容。  
  Retired and discarded material.
