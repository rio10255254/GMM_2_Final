# Repository Governance / 倉庫治理說明

## Purpose / 目的

這份文件說明 `D:\GMM_2_Final` 這個 repository 的 Git / GitHub 治理方式。  
This document defines the Git / GitHub governance model for `D:\GMM_2_Final`.

這個 repo **不是**磁碟工作目錄的完整鏡像。  
This repository is **not** a byte-for-byte mirror of the working directory on disk.

它的目標是追蹤：  
Its purpose is to track:

- 原始碼
- 正式 project truth 文件
- 治理與工作流程政策
- 人類可讀的輕量報告與 manifest
- 少量、刻意保留、可核對的 canonical sample fixtures

它刻意**不**追蹤以下大型或可重現 payload：

- 訓練資料
- model checkpoints
- reconstruction outputs
- raw GMF result dumps
- packaged runtimes / deployment bundles
- backup / archive directories

若某些小型 sample fixture 能穩定支撐程式、文件或 review 的討論，可以保留在 repo 中。  
Small sample fixtures may remain in the repository when they provide stable, auditable reference inputs for code, docs, or review.

例如：`Model/Test_Image/VisionTop_20251029182653732.bmp`。  
Example: `Model/Test_Image/VisionTop_20251029182653732.bmp`.

## Tracked Surface / 追蹤範圍

預期會被追蹤的內容：  
Expected tracked content:

- root 的正式文件與政策檔
- `docs/` 內的導航、歷史、分析、證據層與 curated legacy references
- `Model/`
- `Tools/`（不含打包輸出與本地 watcher state）
- `PSF_Fitting/`
- `PSF_Fitting/PSF_Fitting_ValidationLab/outputs/` 中少量刻意保留的 smoke fixtures、aggregate fixtures 與 current-standard evidence
  - 例如 `candidate_smoke/`、`reasonable_smoke/`、`experiments/`、`final_candidate_full100/`
- `AnalysisLab/` 中按版本收納的常駐分析腳本、測試、結果與報告
- `Experiments/R32Sandbox/` 中的程式、說明、runtime status、manifest 與輕量報告（已關閉沙盒）
- `Experiments/R26NewPSFCheck/` 中的程式、說明、audit、報告與輕量 artifacts（目前 active 沙盒）
- `docs/policy/` 中的正式政策文件（PSF policy 等）

預期不追蹤的內容：  
Expected untracked content:

- `Traing_Progress/`
- `Training_Data/`
- `_deployment_package/`
- 各類 backup / archive
  backup / archive directories
- `weights/`、`artifacts/`、`logs/`、`reconstructions/`、`gmf_results/` 等 bulk 子目錄
  bulk subdirectories such as `weights/`, `artifacts/`, `logs/`, `reconstructions/`, and `gmf_results/`
- `PSF_Fitting/PSF_Fitting_ValidationLab/outputs/` 的 bulk 內容
  except for the curated smoke fixtures and current-standard evidence listed above
- `AnalysisLab/` 內的 `__pycache__/`、`.pytest_cache/` 等執行快取
  execution caches inside the permanent analysis tree
- root 再生成的 `000_LONGRUN_*` runtime outputs
  regenerated root runtime outputs such as `000_LONGRUN_*`

## Documentation Layout / 文件分層

這個 repo 的 root 被刻意維持在「入口層」，避免首頁變成文件堆。  
The repository root is intentionally kept as an entry surface rather than a document dump.

- root
  - 入口文件、治理文件、machine-readable policy、核心程式資料夾
- `docs/history/`
  - 長篇歷史敘事
- `docs/index/`
  - 文件責任邊界與導航索引
- `docs/analysis/`
  - 研究路徑圖與分析摘要
- `docs/evidence/`
  - 小型正式證據副本與 evidence chain
- `docs/policy/`
  - 正式政策文件，如 PSF 政策切換說明與機器可讀 PSF policy
- `docs/runtime/legacy/`
  - legacy root runtime status 的 curated tracked copies

如果舊 launcher 在 root 再生成 `000_LONGRUN_*`，請把它們當作本地執行輸出，不要當成 canonical tracked docs。  
If older launchers recreate `000_LONGRUN_*` files at the repository root, treat them as local execution outputs only.

Git-tracked 版本放在 `docs/runtime/legacy/root_status/`。  
The Git-tracked copies live under `docs/runtime/legacy/root_status/`.

## Branch Taxonomy / 分支分類

- `main`
  - 整理後的 shared mainline  
  - the curated shared mainline
- `snapshot/initial-import-2026-03-23`
  - `2026-03-23` 的第一次 curated Git import  
  - the first curated Git import from `2026-03-23`
  - 它是 repository snapshot，不是磁碟完整鏡像  
  - this is a repository snapshot, not a full disk mirror
- `baseline/*`
  - 保留的 reference namespace，只用於已核准 baseline 里程碑  
  - a reserved reference namespace for approved baseline milestones
- `baseline/r30-b1-dironly`
  - 目前正式 production baseline  
  - the current production baseline
- `reconstructed/r26-sm035`
  - 有證據支撐的前一代 baseline  
  - the evidence-backed predecessor baseline
- `reconstructed/round30-architecture-breakthrough`
  - `Round30 / r30_b1_dironly` 被採納為 baseline 的里程碑  
  - the milestone where `Round30 / r30_b1_dironly` became the adopted baseline
- `research/round31-b1-hparam`
  - external regression 的正式微調線  
  - the measured follow-up line that regressed externally
- `sandbox/r32`
  - `R32Sandbox` 的隔離執行面  
  - the isolated `R32Sandbox` execution surface
- `research/r32-post-falsification`
  - `R32` 外部失敗後的下一步語意分支
  - the semantic next-step branch after the `R32` external fail
- `sandbox/r33`
  - `R33RobustLoss` 的隔離執行面（外部 GMF 已通過，pending baseline promotion）
  - the `R33RobustLoss` execution surface (external GMF passed, pending baseline promotion)
- `codex/*`
  - AI agent 工作分支，合併後即刪除
  - AI agent working branches, deleted after merge

## Reconstruction Honesty Rule / reconstructed 分支誠實原則

這個 repo 並不是從完整 git 歷史開始建立的。  
This repository did not start from a preserved original git history.

因此：  
Therefore:

- reconstructed branches 必須清楚說明自己是 reconstructed governance/reference branches
  reconstructed branches must explicitly identify themselves as reconstructed governance/reference branches
- semantic branches 必須清楚說明自己是 semantic
  semantic branches must explicitly identify themselves as semantic
- 任何 branch 都不能假裝自己是原始歷史 git state，除非有直接證據
  no branch should claim to be the original historical git state or a recovered historical tree without direct evidence
- 新研究工作預設應使用 `research/*` 或 `sandbox/*`
  new research work should normally use `research/*` or `sandbox/*`
- `baseline/*` 只保留給已核准 baseline 里程碑
  `baseline/*` is reserved for approved baseline milestones only

## Sync Cadence / 同步節奏

以下情況值得推到 GitHub：  
Push changes to GitHub when:

- 重大 branch 建立或方向被重新定義
- 某個策略嘗試正式成為 tracked docs
- baseline、verdict、active direction 改變
- 重要實驗分析或 decision memo 新增
- repository information architecture 或治理規則改動

不要為了讓雲端「看起來很活」而把日常 runtime log spam、watcher 輸出或暫時性執行噪音推上去。  
Do not push day-to-day runtime log spam, watcher output, or temporary execution noise just to make the cloud copy look “live”.

## Update Rules / 更新規則

當 project truth 有變時：  
When project truth changes:

1. 更新 `PROJECT_SESSION_CONTINUITY.md`（若 handoff truth 改變）  
   update `PROJECT_SESSION_CONTINUITY.md` if cross-interface handoff truth changed
2. 更新 `PROJECT_CURRENT_STATE.md`（若 current truth 或 next decision boundary 改變）  
   update `PROJECT_CURRENT_STATE.md` if current truth or the next decision boundary changed
3. 更新 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`（若穩定規則改變）  
   update `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` if stable rules changed
4. 更新這份文件（若 tracked surface 或 branch taxonomy 改變）  
   update this file if the tracked surface or branch taxonomy changed

## GitHub Governance Surface / GitHub 端治理介面

以下檔案定義了 GitHub 端的治理規格：  
The following files define the intended GitHub-side governance surface:

- `.github/governance/ruleset-main.json`
- `.github/governance/ruleset-baseline.json`
- `.github/governance/PROJECT_CONTROL_PLANE.md`

它們的作用是讓本地說明與 GitHub server-side rules/project 模型保持一致，即使某個 session 沒有直接打 GitHub API。  
They keep local documentation aligned with GitHub server-side rulesets and the project control plane even when a given session does not directly call the GitHub API.

目前狀態：  
Current status:

- `main` 與 `baseline/*` 的 rulesets 已經套用在 GitHub 上
  repository rulesets for `main` and `baseline/*` are already applied on GitHub
- `baseline/*` 已被視為保留的 reference namespace，不是一般 collaboration branch family
  `baseline/*` is treated as a reserved reference namespace rather than a normal collaboration branch family
- GitHub Project `GMM Research Control Plane` 已存在：`https://github.com/users/rio10255254/projects/1`
  the GitHub Project `GMM Research Control Plane` exists at `https://github.com/users/rio10255254/projects/1`
- 之後若還要自動修改 Project，仍需要具有 `project` / `read:project` scope 的 token
  future automated Project changes still require a token with `project` / `read:project` scope
