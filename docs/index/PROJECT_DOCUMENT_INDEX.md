# PROJECT DOCUMENT INDEX

Last updated: 2026-03-20

這份文件只做一件事：把 **canonical docs**、**sandbox docs**、**archive docs** 的責任邊界講清楚。

## Canonical Core Surface

這五份是接手主入口：

1. `README.md`
2. `PROJECT_SESSION_CONTINUITY.md`
3. `PROJECT_CURRENT_STATE.md`
4. `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
5. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

分工：

- `README.md`
  入口、閱讀順序、root 入口層與 docs 導航
- `PROJECT_SESSION_CONTINUITY.md`
  跨入口 handoff
- `PROJECT_CURRENT_STATE.md`
  現在真相
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
  穩定規則
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`
  完整歷史脈絡

## Docs Surface

- `docs/README.md`
  docs 區入口與子目錄導覽
- `docs/analysis/RESEARCH_PATHS.md`
  研究路徑圖、Mermaid 可視化入口
- `docs/index/PROJECT_DOCUMENT_INDEX.md`
  文件責任邊界與導覽索引
- `docs/runtime/legacy/README.md`
  legacy runtime / root status curated copies 的保存規則

## Sandbox Surface

`R32` 專用入口：

- `Experiments\R32Sandbox\README.md`
  sandbox 的總入口
- `Experiments\R32Sandbox\runtime\R32_STATUS.md`
  sandbox runtime truth
- `Experiments\R32Sandbox\external_compare\README.md`
  external compare 流程與 final verdict carrier

## Machine-Readable Policy

- `ESTIMATOR_POLICY.json`

這份檔案仍是 shared mainline 的 machine-readable policy truth。

## Legacy Bridge

- `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.md`
- `docs/runtime/legacy/root_status/000_LONGRUN_ROUND32_STATUS.json`

這兩份目前只保留為 **tracked legacy bridge copy**，不再是長期 canonical runtime state，也不應用來判讀 `R32` external verdict。若舊腳本在 root 再生成同名檔案，視為本地 runtime 輸出，不再進 Git。

## Archive / Non-Core

- `Project_Archive\`
  conversation scan、maintenance artifact 等非核心文件
- `_deployment_package\`
  外部交付鏡像
- `Trash_Archive\`
  淘汰內容
