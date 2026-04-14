# Contributing / 協作指南

## Repository Scope / 倉庫範圍

這個 repository 是一個經過策展的研究程式碼倉庫，不是磁碟工作目錄的完整鏡像。  
This repository is a curated research-code repository, not a full mirror of the working directory on disk.

會被追蹤的內容包括：  
Tracked content includes:

- `Model/`、`Tools/` 與選定的 `Experiments/R32Sandbox/` 程式與說明文件
  code and docs in `Model/`, `Tools/`, and selected `Experiments/R32Sandbox/`
- root 的 project truth 文件與治理文件
  project-truth and governance docs at the repository root
- `docs/` 內的導航、分析、歷史敘事與 curated legacy references
  navigation, analysis, historical narrative, and curated legacy references under `docs/`
- 用來說明正式決策的輕量報告、manifest 與政策文件
  lightweight reports, manifests, and policy files that explain formal decisions
- PSF fitting 的原始碼與輔助說明
  PSF fitting source and supporting documentation

刻意**不**追蹤的內容包括：  
Intentionally untracked content includes:

- `Traing_Progress/`
- `Training_Data/`
- `_deployment_package/`
- 大量 artifact，例如 `weights/`、`artifacts/`、`logs/`、`reconstructions/`、`gmf_results/`
  bulk artifacts such as `weights/`, `artifacts/`, `logs/`, `reconstructions/`, and `gmf_results/`
- portable runtimes、備份資料夾與編輯器本地狀態
  portable runtimes, backup folders, and editor-local state

只要某個結果能由已追蹤程式重現，或更適合放在外部儲存，就不要把它放進 Git history。  
If a result can be reproduced from tracked code or belongs in external storage, keep it out of Git history.

## Canonical Reading Order / 正式閱讀順序

新接手時請依照這個順序閱讀：  
When taking over the project, read these files in order:

1. `PROJECT_STATE.md`
2. `PROJECT_ARCHITECTURE.md`
3. `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`

## Branch Strategy / 分支策略

- `main`：目前整理後的 shared mainline，放追蹤中的程式、說明與治理內容
  `main`: the curated shared mainline for tracked code, docs, and governance
- `baseline/*`：保留的 reference namespace，只用來放已核准的 baseline 里程碑
  `baseline/*`: a reserved reference namespace for approved baseline milestones
- `reconstructed/*`：建立在 `2026-03-23` curated import 之上的 reconstructed governance/reference branches
  `reconstructed/*`: evidence-backed reconstructed governance/reference branches built on top of the curated `2026-03-23` import
- `research/*`：新研究與策略嘗試的主要分支類型
  `research/*`: the default branch family for new research and strategy work
- `sandbox/*`：像 `R32` 這類需要隔離的實驗面
  `sandbox/*`: isolated experimental surfaces such as `R32`

新的研究工作預設應該使用 `research/*` 或 `sandbox/*`。  
Use `research/*` or `sandbox/*` for new work by default.

`baseline/*` 是受保護的命名空間，不是新實驗的預設 branch family。  
Treat `baseline/*` as a protected namespace, not as the normal branch family for new experiments.

若你需要一步一步的實驗流程，請直接看 `docs/operations/STARTING_NEW_EXPERIMENT.md`。  
For the step-by-step experiment workflow, see `docs/operations/STARTING_NEW_EXPERIMENT.md`.

不要把 reconstructed branch 寫成原始歷史 git state，除非那個狀態真的被完整保留，或之後已經 file-for-file 復原。  
Do not describe a reconstructed branch as the original historical git state or a recovered historical tree unless that state is verifiably preserved or later restored file-for-file.

## Pull Requests / Pull Request 規則

建立 PR 前，請先確認：  
Before opening a PR:

1. 沒有把 bulk artifacts 或資料一起 stage 進去  
   Verify that no bulk artifacts or data are staged.
2. 若 baseline、verdict、active experiment 或 repository information architecture 有變，對應正式文件都已更新  
   Update the relevant formal docs if the baseline, verdict, active experiment, or repository information architecture changed.
3. PR 說明有交代這次改動和 external GMF truth、baseline policy、branch taxonomy 的關係  
   Explain the change in terms of external GMF truth, baseline policy, and branch taxonomy where relevant.
4. 若改動只屬於日常 runtime 輸出或 log noise，請留在本地，不要推上 GitHub  
   Keep day-to-day runtime output and log noise local instead of pushing it.
5. 若 PR 不是 trivial，開 PR 後或把 draft 轉成 ready 後，請手動留言 `@codex review`  
   For non-trivial PRs, manually comment `@codex review` after opening the PR or marking it ready for review.

## Issues / Issue 使用方式

- 新 branch 或新 round，請使用研究 round proposal template
  Use the research round proposal template for new branches or rounds.
- tracked source、docs 或治理問題，請使用 bug report template
  Use the bug report template for defects in tracked source, docs, or governance.
- 大型檔案不要直接丟 GitHub；請改連外部報告或正式 evidence
  Link to external reports or curated evidence instead of uploading large files directly into GitHub.
