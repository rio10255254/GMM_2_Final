# GitHub Project Control Plane / GitHub 研究控制台

## Overview / 概覽

### 繁體中文

這份文件說明本 repo 在 GitHub 端如何使用 rulesets 與 Project，形成一個輕量但清楚的研究治理層。

### English

This document explains how the repository uses GitHub rulesets and a GitHub
Project as a lightweight but explicit research governance layer.

## Rulesets / 保護規則

### 繁體中文

以下 JSON 檔是 repository-level protection 的本地定義來源：

- `ruleset-main.json`
  - 保護 `main`
  - 阻止 force push 與刪除
  - 要求透過 pull request 更新
  - 仍保留 repository owner 的 bypass 能力
- `ruleset-baseline.json`
  - 保護 `baseline/*`
  - 把 baseline 里程碑保留為 reference namespace
  - 阻止隨意建立與一般更新
  - 同樣保留 repository owner 的 bypass 能力

截至 `2026-03-23`，GitHub 端已實際套用：

- `Protect main`
- `Protect baseline branches`

### English

The following JSON files are the local source of truth for repository-level
protection:

- `ruleset-main.json`
  - protects `main`
  - blocks force pushes and deletion
  - requires pull-request based updates
  - still allows repository-owner bypass when necessary
- `ruleset-baseline.json`
  - protects `baseline/*`
  - preserves baseline milestones as a reserved reference namespace
  - blocks ad-hoc creation and ordinary updates
  - still allows repository-owner bypass when necessary

As of `2026-03-23`, the following server-side rulesets are already applied on
GitHub:

- `Protect main`
- `Protect baseline branches`

## Project / Project 控制台

### 繁體中文

GitHub Project 的正式名稱是：

- `GMM Research Control Plane`

截至 `2026-03-23`，目前狀態是：

- rulesets 已套用到 GitHub
- GitHub Project 已建立
- project URL：`https://github.com/users/rio10255254/projects/1`
- 後續若要透過 automation 修改 Projects v2，仍需要具備 `project` / `read:project` scope 的 token

這個 Project 用來呈現**研究時間線**，不是用來承載完整證據鏈。

### English

The intended GitHub Project title is:

- `GMM Research Control Plane`

Current status as of `2026-03-23`:

- the repository rulesets are already applied on GitHub
- the GitHub Project has already been created
- project URL: `https://github.com/users/rio10255254/projects/1`
- future automated changes to Projects v2 still require a token with
  `project` / `read:project` scope

This Project is meant to visualize the **timeline** of the research program,
not to carry the full evidence chain by itself.

## Fields / 欄位設計

### 繁體中文

控制台目前使用的概念欄位如下：

- `Track`
  - `baseline`
  - `reconstructed`
  - `research`
  - `sandbox`
- `Status`
  - `active`
  - `completed`
  - `falsified`
  - `promoted`
  - `archived`
- `External Verdict`
  - `pass`
  - `fail`
  - `pending`
  - `missing_artifact`
  - `n/a`
- `Branch`
- `Round`
- `Milestone Date`
  - `YYYY-MM-DD` 文字參考欄位，適合表格快速排序與閱讀
- `Start Date`
  - GitHub Roadmap 真正使用的開始日期欄位
- `Target Date`
  - GitHub Roadmap 真正使用的結束日期欄位

### English

The Project currently uses the following conceptual fields:

- `Track`
  - `baseline`
  - `reconstructed`
  - `research`
  - `sandbox`
- `Status`
  - `active`
  - `completed`
  - `falsified`
  - `promoted`
  - `archived`
- `External Verdict`
  - `pass`
  - `fail`
  - `pending`
  - `missing_artifact`
  - `n/a`
- `Branch`
- `Round`
- `Milestone Date`
  - an ISO `YYYY-MM-DD` text field for quick reading and table sorting
- `Start Date`
  - the actual GitHub Roadmap start-date field
- `Target Date`
  - the actual GitHub Roadmap target-date field

## Current Timeline / 目前時間線

### 繁體中文

目前控制台保留 10 個高價值里程碑：

1. `2026-03-07 | First usable baseline scaffold established`
2. `2026-03-09 | External GMF became the final gate`
3. `2026-03-11 | Round14 corridor identified 0.8px as the bottleneck`
4. `2026-03-12 | Round15 center-lock narrowed the target`
5. `2026-03-14 | Round20 process probe falsified the baseline-lock hypothesis`
6. `2026-03-17 | R26 sm035 confirmed as the generic step_mag optimum`
7. `2026-03-18 | Round30 architecture breakthrough promoted r30_b1_dironly`
8. `2026-03-19 | Round31 B1 hyperparameter tuning regressed externally`
9. `2026-03-20 | Round32 sandbox winner failed external compare`
10. `2026-03-20 | Post-R32 new sandbox branch is required`

每個 item 都帶有日期前綴，並同時填入：

- `Milestone Date`
- `Start Date`
- `Target Date`

如果你在 table view 看 Project，`Milestone Date` 最適合拿來快速排序。  
如果你切到 roadmap view，GitHub 會使用 `Start Date` / `Target Date`。

### English

The current Project intentionally keeps a 10-item high-value timeline:

1. `2026-03-07 | First usable baseline scaffold established`
2. `2026-03-09 | External GMF became the final gate`
3. `2026-03-11 | Round14 corridor identified 0.8px as the bottleneck`
4. `2026-03-12 | Round15 center-lock narrowed the target`
5. `2026-03-14 | Round20 process probe falsified the baseline-lock hypothesis`
6. `2026-03-17 | R26 sm035 confirmed as the generic step_mag optimum`
7. `2026-03-18 | Round30 architecture breakthrough promoted r30_b1_dironly`
8. `2026-03-19 | Round31 B1 hyperparameter tuning regressed externally`
9. `2026-03-20 | Round32 sandbox winner failed external compare`
10. `2026-03-20 | Post-R32 new sandbox branch is required`

Each item is date-prefixed and also carries:

- `Milestone Date`
- `Start Date`
- `Target Date`

In table view, `Milestone Date` is the easiest quick-sort field.  
In roadmap view, GitHub uses `Start Date` and `Target Date`.

## Timeline vs Evidence Chain / 時間線與證據鏈的分工

### 繁體中文

Project 負責回答：

- 什麼時候發生了什麼
- 哪條研究線在什麼時間點被 promotion / falsification

真正的 evidence chain 請看：

- `docs/evidence/EVIDENCE_MAP.md`

那份文件會說明哪些 curated evidence files 支撐：

- current baseline
- historical baseline path
- falsified lines
- side-direction rejections
- analysis conclusions
- runtime truth snapshots

### English

The Project answers:

- what happened when
- which line was promoted or falsified at which point in time

The repository evidence chain itself should be read through:

- `docs/evidence/EVIDENCE_MAP.md`

That file explains which curated evidence files support:

- the current baseline
- the historical baseline path
- falsified lines
- side-direction rejections
- analytical conclusions
- runtime truth snapshots

## Manual Unblock For Future Automation / 未來自動化的解除條件

### 繁體中文

若未來還要用 automation 建立或修改 GitHub Project，本機使用的 token 必須具備 `project` scope。  
目前 Project 已經存在，所以額外權限只在未來自動修改時才需要。

### English

To create or modify the GitHub Project from automation in future sessions, the
token used on this machine must include the `project` scope. The current
Project already exists, so that extra scope is only needed for future automated
changes.

## Sync Rule / 同步規則

### 繁體中文

只有以下內容應該同步到 GitHub：

- 重大 branch 建立
- 有明確設計改變的策略嘗試
- 重要分析與 decision memos
- baseline / verdict 變更
- 治理與文件更新

不要把日常 runtime 噪音、bulk logs、artifacts 或可重現 payload 推進 Git history。

### English

Only sync the following to GitHub:

- major branch creation
- strategy attempts with meaningful design changes
- important analyses and decision memos
- baseline / verdict changes
- governance and documentation updates

Do not push day-to-day runtime noise, bulk logs, artifacts, or reproducible
payloads into Git history.
