# New Experiment SOP / 新增實驗作業流程

Use this checklist whenever you want to add a new experiment or research line.  
當你要新增一條實驗線或研究分支時，請使用這份清單。

## 1. Choose the right branch family / 選對 branch 類型

- Use `research/*` for new strategy attempts, tuning lines, or analysis-driven follow-up work.  
  新的策略嘗試、微調路線、或分析驅動的後續工作，請用 `research/*`。
- Use `sandbox/*` for isolated execution surfaces that should not be treated as baseline candidates yet.  
  如果這條線需要隔離執行、且暫時不應視為 baseline 候選，請用 `sandbox/*`。
- Do **not** use `baseline/*` for new work. That namespace is reserved for approved baseline milestones only.  
  **不要**把 `baseline/*` 當成新工作分支。這個命名空間只保留給已核准的 baseline 里程碑。

## 2. Create the branch / 建立分支

- Start from `main`.  
  從 `main` 開始。
- Name the branch to match the work.  
  分支名稱要能對應工作內容。
  - `research/<round-or-topic>`
  - `sandbox/<round-or-topic>`

## 3. Open the tracking issue / 建立追蹤 issue

- Use the existing issue template:  
  使用既有的 issue template：
  - `.github/ISSUE_TEMPLATE/research-round-proposal.yml`
- In that issue, capture the following:  
  在 issue 裡至少記錄：
  - round / branch name  
    round 或 branch 名稱
  - hypothesis  
    研究假設
  - comparison target  
    比較對象
  - success condition  
    成功條件
  - expected external verdict path  
    預期的 external verdict 路徑或落點

## 4. Update the GitHub Project / 更新 GitHub Project

Open `GMM Research Control Plane` and add or update an item with:  
打開 `GMM Research Control Plane`，新增或更新一個 item，至少填：

- `Track`
- `Research Status`
- `External Verdict`
- `Branch`
- `Round`
- `Milestone Date`
- `Start Date`
- `Target Date`

Use the following defaults when the line is still in progress:  
當研究線仍在進行中，建議先用這些預設值：

- `Research Status = active`
- `External Verdict = pending`

## 5. Update formal docs only when truth changes / 只有在正式真相改變時才更新核心文件

Update these docs when the work crosses a formal boundary:  
當工作跨過正式決策邊界時，再更新下列文件：

- `PROJECT_CURRENT_STATE.md`
  - when current truth, adopted baseline, or next decision boundary changes  
    當 current truth、adopted baseline、或下一個決策邊界改變時
- `PROJECT_SESSION_CONTINUITY.md`
  - when handoff truth or canonical entry points change  
    當 handoff 真相或 canonical 入口改變時
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
  - when stable rules or branch/governance policy change  
    當穩定規則、branch policy、或治理規則改變時

Do not update canonical docs for day-to-day runtime noise.  
不要因為日常 runtime 噪音去改 canonical docs。

## 6. Open a PR / 開 Pull Request

- Keep the PR limited to tracked source, docs, or governance files.  
  PR 只應包含受追蹤的 source、docs、或 governance 檔案。
- Use `.github/PULL_REQUEST_TEMPLATE.md`.  
  請使用 `.github/PULL_REQUEST_TEMPLATE.md`。

## 7. Trigger Codex review manually for non-trivial PRs / 對非 trivial PR 手動觸發 Codex review

For any non-trivial PR, after opening it or marking it ready for review, leave:  
只要 PR 不是很 trivial，在建立後或從 draft 轉成 ready 後，請手動留言：

`@codex review`

If Codex leaves actionable comments, follow up in the PR with:  
如果 Codex 留下可執行的意見，請在同一個 PR 裡接著留言：

`@codex address that feedback`

## 8. Merge only after the line is clear / 確認路線清楚後再合併

- `main` and `baseline/*` are protected.  
  `main` 與 `baseline/*` 都受保護。
- New experiment work should merge through PR, not direct pushes.  
  新實驗工作應透過 PR 合併，不要直接推進正式分支。
- Keep bulk artifacts, logs, weights, reconstructions, and runtime noise out of Git.  
  請把 bulk artifacts、logs、weights、reconstructions、以及 runtime 噪音留在 Git 之外。
