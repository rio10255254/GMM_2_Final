# Repository Governance / 倉庫治理說明

## Purpose / 目的

這份文件說明 `D:\GMM_2_Final` 這個 repository 的 Git / GitHub 治理方式。  
This document defines the Git / GitHub governance model for `D:\GMM_2_Final`.

## GitHub研究保存（2026-10-21）

一般Git歷史保存程式、正式報告與閱讀導引；GitHub版本附件保存必要原拍、固定訓練來源、模型與完整數據。下文「不追蹤大型payload」指一般Git歷史，不表示這些研究內容可以從GitHub保存範圍省略。[保存與取回入口](docs/reproducibility/README.md)記錄已完成驗證，[本機全內容核對](docs/reproducibility/project_completion/README.md)另列本輪進度。

相同內容共用物件時仍保留原位置、輪次與用途。較舊或不同的版本不得覆蓋目前正式來源；成功、失敗、草稿與未完成工作各自保留身分。保存分支、歷史分支與固定版本標記是長期引用入口，不適用一般工作分支「合併後刪除」慣例。

正式模型仍為COMBO，R30是前任基準。論文目前採用與最新交接依`PROJECT_STATE.md`及原實驗報告；較早的目錄或分支說明按其歷史日期閱讀。

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

## Documentation Design Principles / 文件設計原則

這套文件組織跟著三條原則走。任何未來重構都應該先對照這三條，不要無意間違背。
The documentation layout follows three principles. Any future refactor should check against these before changing structure.

### 1. Single Update Reason / 單一更新理由

每份文件只為**一個更新理由**存在。
Each file exists for exactly **one update reason**.

- 若兩份文件常為同一件事一起改 → 應該合併
  If two files are regularly edited together for the same reason, they should be merged.
- 若一份文件為兩件不同的事被改 → 應該拆分
  If one file is edited for two distinct reasons, it should be split.
- 若一份文件塞了它不該管的事 → 應該重新定位
  If a file has absorbed content outside its purpose, that content should move.

`PROJECT_STATE.md` 的「Quick Handoff + Full Current State」是例外：兩者本質是同一件事（現況），只是對不同注意力預算服務。以 TOC 分段 + CI lint 守門保證「短讀版本」不會膨脹。
`PROJECT_STATE.md` keeps a Quick Handoff + Full Current State together because they are the *same* reason (current truth) served at two attention budgets; a CI lint (`check_quick_handoff_length`) enforces the short-read contract.

### 2. Axis = Update Frequency × Audience / 以更新頻率 × 讀者分層

文件**不**按主題切分（交接、現況、架構、治理 ...），那會導致主題重疊與內容漂移。
Documents are **not** sliced by topic (handoff, state, architecture, governance ...); topics overlap, causing duplication and drift.

正確切分軸線：
The correct axis:

| 軸線 / Axis | 代表文件 / Files |
|------|------|
| 高頻 × 機器 / high-frequency × machine | `ESTIMATOR_POLICY.json` |
| 高頻 × 人類 / high-frequency × human | `PROJECT_STATE.md` |
| 低頻 × 人類 / low-frequency × human | `PROJECT_ARCHITECTURE.md`, `REPO_GOVERNANCE.md` |
| 極低頻 × AI / very-low-frequency × AI | `CLAUDE.md`, `AGENTS.md` |
| 一次性 × 參考 / one-time × reference | `docs/history/`, `docs/evidence/`, `docs/policy/` |

### 3. Short-Read Guarantee = Machine / 短讀屬性靠機器，不靠自律

若某區段需要「維持精短」（例如 handoff），**不要**靠人類記得——應由 CI lint 強制。
Any "must stay short" region (handoff summaries, TOC stubs) is **enforced by CI lint**, never by human discipline.

目前的實作：`Tools/validate_project_structure.py` 的 `check_quick_handoff_length()` 把 `PROJECT_STATE.md` 的 `QUICK_HANDOFF_START/END` 區硬限制在 60 行。
Current implementation: `check_quick_handoff_length()` hard-caps the `PROJECT_STATE.md` Quick Handoff region at 60 interior lines.

### Red Flags When Designing New Docs / 新文件的警示燈

在新增或合併文件前，先檢查：
Before adding or merging a document, check:

- 是否會跟某份既有文件為同一件事被改？→ 合併，不新增
  Will it be edited together with an existing file for the same reason? Merge instead of adding.
- 事實性內容是否已經在 `ESTIMATOR_POLICY.json`？→ 引用，不複製
  Is the factual content already in `ESTIMATOR_POLICY.json`? Reference, don't copy.
- 是否引入新的「必須同步的鏡像」？→ 不要做，或規則放寬為「可 drift」
  Does it create a "must-sync mirror"? Don't; or relax the rule to "may drift".
- 短讀 / 摘要型區段有沒有機器守門？→ 沒有就加 CI lint
  Any short-read / summary region without a machine check? Add a CI lint.

### Local Enforcement / 本地驗證

安裝 pre-commit hook（只需要做一次）：
Install the pre-commit hook (one-time per clone):

```bash
python Tools/install_hooks.py
```

這會把 `Tools/hooks/pre-commit` 複製到 `.git/hooks/pre-commit`，每次 `git commit` 會自動跑 `python Tools/project_control_center.py --view health --health-level standard`，不通過就擋下。
It copies `Tools/hooks/pre-commit` into `.git/hooks/pre-commit`. Every `git commit` then runs `python Tools/project_control_center.py --view health --health-level standard` and blocks on failures.

`Tools/validate_project_structure.py` 仍然保留，但現在是這條官方日常檢查裡的一個子檢查，不再是單獨對外的主要守門入口。
`Tools/validate_project_structure.py` still remains in use, but it is now one sub-check inside the official standard-health path rather than the standalone public gate.

緊急情況可用 `git commit --no-verify` 繞過；但請在後續 commit 修正，不要讓 main 帶著違規狀態。
In emergencies use `git commit --no-verify`; fix the violation in a follow-up commit — don't let `main` carry a broken state.

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
- `Experiments/R26NewPSFCheck/` 中的程式、說明、audit、報告與輕量 artifacts（open side track，pending external GMF）
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
- `docs/operations/`
  - 操作指引層（新實驗 SOP、quirks、source-of-truth 政策、legacy 操作、控制中心說明）
- `docs/analysis/`
  - 研究路徑圖與分析摘要
- `docs/evidence/`
  - 小型正式證據副本與 evidence chain
- `docs/policy/`
  - 正式政策文件，如 PSF 政策切換說明與機器可讀 PSF policy
- `docs/archive/legacy_runtime_status/`
  - archived legacy root runtime status snapshots
- `docs/runtime/legacy/`
  - relocation note for the retired legacy runtime location

如果舊 launcher 在 root 再生成 `000_LONGRUN_*`，請把它們當作本地執行輸出，不要當成 canonical tracked docs。  
If older launchers recreate `000_LONGRUN_*` files at the repository root, treat them as local execution outputs only.

Git-tracked 版本已封存到 `docs/archive/legacy_runtime_status/`。  
The Git-tracked copies now live under `docs/archive/legacy_runtime_status/`.

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
  - 歷史前任 production baseline 的保留參照
  - preserved reference for the former production baseline
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
  - `R33RobustLoss` GMF 極致型候選（外部 GMF 通過：0.8px -29%，銳度 -22%）
  - R33 GMF-extreme candidate (external pass: 0.8px -29%, steepness -22%)
- `sandbox/r33-contrast`
  - R33 對比度修復嘗試（否定）
  - R33 contrast fix attempt (falsified)
- `sandbox/r34` / `sandbox/r35` / `sandbox/r37`
  - R34-R37 銳度恢復嘗試（全部否定）
  - R34-R37 sharpness recovery attempts (all falsified)
- `sandbox/r38`
  - R38 seq training 全 stages（部分成功，8px 好但 0.8px 弱）
  - R38 seq training all stages (partial: 8px good, 0.8px weak)
- `sandbox/r38v2`
  - R38v2 均衡型候選（外部 GMF 通過：0.8px -20%，銳度 +89%）
  - R38v2 balanced candidate (external pass: 0.8px -20%, steepness +89%)
- `codex/*`
  - 一般AI工作分支於合併後依需要清理；research-preservation、research-recovery及history保存分支持續保留
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

1. 更新 `PROJECT_STATE.md`（包含 Quick Handoff 區與 Full Current State 區；handoff / current truth / next decision boundary 皆在此）
   update `PROJECT_STATE.md` (covers both Quick Handoff and Full Current State — handoff, current truth, and next decision boundary all live here)
2. 更新 `PROJECT_ARCHITECTURE.md`（若穩定規則改變）
   update `PROJECT_ARCHITECTURE.md` if stable rules changed
3. 更新 `ESTIMATOR_POLICY.json`（若 formal baseline / alternates / closed lines 清單改變）
   update `ESTIMATOR_POLICY.json` if the formal baseline / alternates / closed-lines taxonomy changed
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
