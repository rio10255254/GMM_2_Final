# 新增實驗作業流程 / New Experiment SOP

當你要新增一條實驗線或研究分支時，請使用這份清單。  
Use this checklist whenever you want to add a new experiment or research line.

## 1. Choose the right branch family / 選對 branch 類型

- 新的策略嘗試、微調路線、或分析驅動的後續工作，請用 `research/*`。  
  Use `research/*` for new strategy attempts, tuning lines, or analysis-driven follow-up work.
- 如果這條線需要隔離執行、且暫時不應視為 baseline 候選，請用 `sandbox/*`。  
  Use `sandbox/*` for isolated execution surfaces that should not be treated as baseline candidates yet.
- **不要**把 `baseline/*` 當成新工作分支。這個命名空間只保留給已核准的 baseline 里程碑。  
  Do **not** use `baseline/*` for new work. That namespace is reserved for approved baseline milestones only.

## 2. Create the branch / 建立分支

- 從 `main` 開始。  
  Start from `main`.
- 分支名稱要能對應工作內容。  
  Name the branch to match the work.
  - `research/<round-or-topic>`
  - `sandbox/<round-or-topic>`

## 3. Open the tracking issue / 建立追蹤 issue

- 使用既有的 issue template：  
  Use the existing issue template:
  - `.github/ISSUE_TEMPLATE/research-round-proposal.yml`
- 在 issue 裡至少記錄：  
  In that issue, capture the following:
  - round 或 branch 名稱  
    round / branch name
  - 研究假設  
    hypothesis
  - 比較對象  
    comparison target
  - 成功條件  
    success condition
  - 預期的 external verdict 路徑或落點  
    expected external verdict path

## 4. Update the GitHub Project / 更新 GitHub Project

打開 `GMM Research Control Plane`，新增或更新一個 item，至少填：  
Open `GMM Research Control Plane` and add or update an item with:

- `Track`
- `Research Status`
- `External Verdict`
- `Branch`
- `Round`
- `Milestone Date`
- `Start Date`
- `Target Date`

當研究線仍在進行中，建議先用這些預設值：  
Use the following defaults when the line is still in progress:

- `Research Status = active`
- `External Verdict = pending`

## 5. Update formal docs only when truth changes / 只有在正式真相改變時才更新核心文件

當工作跨過正式決策邊界時，再更新下列文件：  
Update these docs when the work crosses a formal boundary:

- `PROJECT_STATE.md`
  當 current truth、adopted baseline、或下一個決策邊界改變時。  
  Update it when current truth, the adopted baseline, or the next decision boundary changes.
- `PROJECT_STATE.md`
  當 handoff 真相或 canonical 入口改變時。  
  Update it when handoff truth or canonical entry points change.
- `PROJECT_ARCHITECTURE.md`
  當穩定規則、branch policy、或治理規則改變時。  
  Update it when stable rules or branch/governance policy changes.

不要因為日常 runtime 噪音去改 canonical docs。  
Do not update canonical docs for day-to-day runtime noise.

## 6. Open a PR / 開 Pull Request

- PR 只應包含受追蹤的 source、docs、或 governance 檔案。  
  Keep the PR limited to tracked source, docs, or governance files.
- 請使用 `.github/PULL_REQUEST_TEMPLATE.md`。  
  Use `.github/PULL_REQUEST_TEMPLATE.md`.

## 7. Trigger Codex review manually for non-trivial PRs / 對非 trivial PR 手動觸發 Codex review

只要 PR 不是很 trivial，在建立後或從 draft 轉成 ready 後，請手動留言：  
For any non-trivial PR, after opening it or marking it ready for review, leave:

`@codex review`

如果 Codex 留下可執行的意見，請在同一個 PR 裡接著留言：  
If Codex leaves actionable comments, follow up in the PR with:

`@codex address that feedback`

## 8. Merge only after the line is clear / 確認路線清楚後再合併

- `main` 與 `baseline/*` 都受保護。  
  `main` and `baseline/*` are protected.
- 新實驗工作應透過 PR 合併，不要直接推進正式分支。  
  New experiment work should merge through PR, not direct pushes.
- 請把 bulk artifacts、logs、weights、reconstructions、以及 runtime 噪音留在 Git 之外。  
  Keep bulk artifacts, logs, weights, reconstructions, and runtime noise out of Git.
