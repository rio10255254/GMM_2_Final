# PROJECT DOCUMENT INDEX / 文件索引

Last updated: 2026-03-20

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
  - 繁中：總入口、閱讀順序、root 入口層與 docs 導航。
  - English: Top-level entry point, reading order, root surface, and docs navigation.
- `PROJECT_SESSION_CONTINUITY.md`
  - 繁中：跨入口 handoff。
  - English: Cross-interface handoff.
- `PROJECT_CURRENT_STATE.md`
  - 繁中：目前真相。
  - English: Current truth.
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
  - 繁中：穩定規則。
  - English: Stable rules and decision boundaries.
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
  - 繁中：完整歷史脈絡。
  - English: Full historical narrative and strategy context.

## Docs Surface / 導航文件層

- `docs/README.md`
  - 繁中：docs 區入口與子目錄導覽。
  - English: Entry point and directory guide for the `docs/` area.
- `docs/analysis/RESEARCH_PATHS.md`
  - 繁中：研究路徑圖與 Mermaid 可視化入口。
  - English: Research-path map and Mermaid visualization entry.
- `docs/evidence/README.md`
  - 繁中：精選實驗證據層的入口與用途說明。
  - English: Entry point and purpose guide for the curated evidence layer.
- `docs/evidence/EVIDENCE_MAP.md`
  - 繁中：一頁式證據鏈地圖，回答每份 evidence 支撐哪個 baseline、falsified line、或 analysis 結論。
  - English: A one-page evidence-chain map showing which evidence supports which baseline, falsified line, or analytical conclusion.
- `docs/index/PROJECT_DOCUMENT_INDEX.md`
  - 繁中：文件責任邊界與導航索引。
  - English: Documentation responsibility map and navigation index.
- `docs/index/NEW_EXPERIMENT_SOP.md`
  - 繁中：新增實驗時的 branch、issue、Project、doc、與 PR 操作清單。
  - English: The operational checklist for adding a new experiment, including branches, issues, Project updates, docs, and PRs.
- `docs/runtime/legacy/README.md`
  - 繁中：legacy runtime / root status curated copies 的保存規則。
  - English: Preservation rules for legacy runtime and root-status curated copies.

## Sandbox Surface / Sandbox 文件層

`R32` 專用入口：  
The `R32`-specific entry surface is:

- `Experiments\R32Sandbox\README.md`
  - 繁中：sandbox 的總入口。
  - English: Main entry point for the sandbox.
- `Experiments\R32Sandbox\runtime\R32_STATUS.md`
  - 繁中：sandbox runtime truth。
  - English: Sandbox runtime truth.
- `Experiments\R32Sandbox\external_compare\README.md`
  - 繁中：external compare 流程與 final verdict carrier。
  - English: External compare flow and final-verdict carrier.

## Machine-Readable Policy / 機器可讀政策層

- `ESTIMATOR_POLICY.json`

這份檔案仍是 shared mainline 的 machine-readable policy truth。  
This file remains the machine-readable policy truth for the shared mainline.

## Evidence Surface / 證據文件層

- `docs/evidence/README.md`
  - 繁中：curated tracked copies 的總入口。
  - English: Main entry for curated tracked copies.
- `docs/evidence/baseline/`
  - 繁中：支撐目前 baseline promotion 的核心證據。
  - English: Core evidence supporting the current baseline promotion.
- `docs/evidence/historical_baselines/`
  - 繁中：支撐 `R18/R22 -> Round25 -> R26 -> Round29` 的歷史 baseline path 證據。
  - English: Evidence supporting the historical baseline path from `R18/R22` through `Round25`, `R26`, and `Round29`.
- `docs/evidence/falsified/`
  - 繁中：支撐 Round31 / Round32 等正式否定性結果的核心證據。
  - English: Core evidence supporting formally falsified results such as Round31 and Round32.
- `docs/evidence/side_directions/`
  - 繁中：支撐 `TTA C2` 等重要 side-direction falsifications。
  - English: Evidence supporting important side-direction falsifications such as `TTA C2`.
- `docs/evidence/analysis/`
  - 繁中：支撐 correlation / screening 等綜合分析證據。
  - English: Evidence for analytical conclusions such as correlation and screening logic.
- `docs/evidence/runtime/`
  - 繁中：小型 canonical runtime truth snapshots。
  - English: Small canonical runtime-truth snapshots.

## Legacy Bridge / Legacy 橋接層

- `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.md`
- `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.json`

這兩份目前只保留為 **tracked legacy bridge copy**，不再是長期 canonical runtime state，也不應用來判讀 `R32` external verdict。若舊腳本在 root 再生成同名檔案，視為本地 runtime 輸出，不再進 Git。  
These files are kept only as tracked legacy bridge copies. They are no longer the canonical runtime state and should not be used to interpret the `R32` external verdict. If old scripts recreate same-named files at the root, treat them as local runtime outputs rather than tracked Git content.

## Archive / Non-Core / 歸檔與非核心層

- `Project_Archive\`
  - 繁中：conversation scan、maintenance artifact 等非核心文件。
  - English: Non-core material such as conversation scans and maintenance artifacts.
- `_deployment_package\`
  - 繁中：外部交付鏡像。
  - English: External delivery/package mirror.
- `Trash_Archive\`
  - 繁中：淘汰內容。
  - English: Retired and discarded material.
