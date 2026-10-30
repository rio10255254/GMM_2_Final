# Governance Docs Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把治理層文件從 18 份精簡到 10 份，消除內容漂移，並讓每次大決策只需改 5 份（原 7 份）。

**Architecture:** 合併 `PROJECT_SESSION_CONTINUITY.md` + `PROJECT_CURRENT_STATE.md` → `PROJECT_STATE.md`（靠 TOC + CI lint 保護短讀區）；重命名 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` → `PROJECT_ARCHITECTURE.md`；重組 `docs/index/` → `docs/operations/` 並三合一新實驗指南；放寬 `docs/evidence/` 同步規則。

**Tech Stack:** Python 3.11+（pytest、subprocess）、Git、Markdown。

**Reference spec:** `docs/superpowers/specs/2026-04-14-governance-docs-simplification-design.md`

**Execution branch:** `refactor/governance-docs-simplification`（從 `main` 切出）

---

## Pre-flight / 執行前準備

- [ ] **Pre-1: 切新分支並確認工作區乾淨**

Run:
```bash
cd /d/GMM_2_Final
git status --short
```
Expected: **No tracked-file modifications**. Untracked files allowed.

If dirty, stash or commit first. Then:
```bash
git checkout main
git pull origin main
git checkout -b refactor/governance-docs-simplification
```

- [ ] **Pre-2: 跑一次基線檢查確認現在是 PASS/WARN**

Run:
```bash
python Tools/project_control_center.py --view health --health-level standard
```
Expected: **PASS** or **WARN**（不可 FAIL）。記下輸出作為 baseline。

```bash
python -m pytest Tools/tests/ -q
```
Expected: **All pass**。

---

## Task 1: 建立 PROJECT_STATE.md（合併 SESSION + CURRENT）

**Files:**
- Rename: `PROJECT_CURRENT_STATE.md` → `PROJECT_STATE.md`
- Modify: `PROJECT_STATE.md`（在最前面 prepend Quick Handoff 區塊）
- Reference (讀取): `PROJECT_SESSION_CONTINUITY.md`（取 Working Rules）

- [ ] **Step 1.1: 用 git mv 重命名**

```bash
git mv PROJECT_CURRENT_STATE.md PROJECT_STATE.md
```

- [ ] **Step 1.2: 用 Read 工具讀 `PROJECT_STATE.md` 現有內容**，取得第一行標題與 cross-interface entry 提示句。

- [ ] **Step 1.3: 在 `PROJECT_STATE.md` 最開頭 prepend Quick Handoff 區塊**

在原檔案開頭（`# PROJECT CURRENT STATE...` 之前）插入以下內容：

```markdown
# PROJECT STATE / 專案狀態

Last updated: 2026-04-14 (merged from SESSION_CONTINUITY + CURRENT_STATE)

專案控制與整體巡檢請使用 `python Tools/project_control_center.py`。
機器真相：`ESTIMATOR_POLICY.json`。

<!-- QUICK_HANDOFF_START -->
## 🟢 Quick Handoff (3-min read)

### Current Formal Baseline
**COMBO / r38v2_8px_gate_p95** (effective 2026-04-08)

### Approved Alternates
- `R33 / r33_robust_p95` — GMF extreme alternate
- `R38v2 / r38v2_8px_gate` — visual priority alternate

### Former Baseline
`Round30 / r30_b1_dironly` — historical former baseline (歷史前任 baseline)

### Open Side Tracks
- `R26NewPSFCheck` (pending external GMF; **not** the active mainline)

### Closed Lines
`Round31`（external regression）、`Round32`（external FAIL）、`R34/R35/R37/R38/R33c`（falsified）

### Working Rules (6)
1. 先讀本檔 Quick Handoff 區完整理解現況
2. 以 repo 正式文件為準，不以 `.codex` / `.claude` 內部 session 檔為準
3. root prose current state 以 COMBO + approved alternates 為主，R26NewPSFCheck 不是 active mainline
4. legacy root runtime 快照已封存到 `docs/archive/legacy_runtime_status/`
5. baseline / verdict / taxonomy 有變時，優先更新本檔 + `ESTIMATOR_POLICY.json`
6. external FAIL 或 closed 的候選，不再以 promising / active 的語氣描述

### Canonical sandbox branch
`sandbox/r38v2`（COMBO 的 origin experiment branch）

<!-- QUICK_HANDOFF_END -->

---

```

接著原 PROJECT_CURRENT_STATE 的主體內容保留在 `---` 之後，並把第一個 `# PROJECT CURRENT STATE / 專案目前狀態` 標題改為 `## Full Current State / 完整現況`。

- [ ] **Step 1.4: 驗證 PROJECT_STATE.md 結構正確**

Run:
```bash
grep -n "QUICK_HANDOFF_START\|QUICK_HANDOFF_END" PROJECT_STATE.md
```
Expected 兩行輸出，Quick Handoff 區內容不超過 60 行（扣掉 marker 行）。

```bash
awk '/QUICK_HANDOFF_START/,/QUICK_HANDOFF_END/' PROJECT_STATE.md | wc -l
```
Expected: 兩條 marker 之間 ≤ 62 行（含兩條 marker）。

- [ ] **Step 1.5: Commit**

```bash
git add PROJECT_STATE.md
git status --short | grep "PROJECT_CURRENT_STATE.md"
```
Expected: 看到 `D PROJECT_CURRENT_STATE.md` 或 `R ... PROJECT_STATE.md`（git mv 的效果）。

```bash
git commit -m "refactor: create PROJECT_STATE.md by merging SESSION_CONTINUITY + CURRENT_STATE

- git mv PROJECT_CURRENT_STATE.md → PROJECT_STATE.md
- Prepend Quick Handoff block (~50 lines) with baseline summary + 6 working rules
- Full current state preserved as 'Full Current State' section
- Old SESSION_CONTINUITY.md still exists (removed in later task)
"
```

---

## Task 2: 更新 Tools/validate_project_structure.py 的常數

**Files:**
- Modify: `Tools/validate_project_structure.py:32-45`

- [ ] **Step 2.1: 改 `TRUTH_PLANE_DOCS`**

Edit `Tools/validate_project_structure.py` 行 32-37：

```python
TRUTH_PLANE_DOCS = [
    "PROJECT_STATE.md",
    "README.md",
    "PROJECT_ARCHITECTURE.md",
]
```

註：這裡同時把 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` 預先改成新名字，即使檔案尚未重命名——我們會在 Task 6 一併搬過去。**此時測試會暫時失敗，這在計畫中是預期的**，下一個 task 會處理。

- [ ] **Step 2.2: 改 `LEGACY_RUNTIME_FORMAL_DOCS`**

Edit 行 40-45：

```python
LEGACY_RUNTIME_FORMAL_DOCS = [
    "PROJECT_STATE.md",
    "README.md",
    "REPO_GOVERNANCE.md",
    "docs/operations/SOURCE_OF_TRUTH_POLICY.md",
]
```

註：`docs/operations/` 路徑尚未建立，同樣會暫時讓 validator 失敗——Task 12 會處理。

- [ ] **Step 2.3: 跑 validator 確認是否按預期失敗**

```bash
python Tools/validate_project_structure.py
```
Expected: **FAIL** with errors about missing `PROJECT_ARCHITECTURE.md` and `docs/operations/SOURCE_OF_TRUTH_POLICY.md`（這是暫時狀態，下面會修）。

- [ ] **Step 2.4: Commit**

```bash
git add Tools/validate_project_structure.py
git commit -m "refactor(validator): point constants to new doc paths

TRUTH_PLANE_DOCS now references PROJECT_STATE.md + PROJECT_ARCHITECTURE.md.
LEGACY_RUNTIME_FORMAL_DOCS references docs/operations/SOURCE_OF_TRUTH_POLICY.md.

Tests will temporarily fail until Tasks 6 and 12 complete the renames.
"
```

---

## Task 3: 更新 Tools/project_control_center.py 的常數

**Files:**
- Modify: `Tools/project_control_center.py:21-40`, `:600-603`

- [ ] **Step 3.1: 改常數區塊**

Edit `Tools/project_control_center.py` 行 21-40：

```python
POLICY_PATH = REPO / "ESTIMATOR_POLICY.json"
CONTROL_CENTER_DOC = REPO / "docs" / "operations" / "PROJECT_CONTROL_CENTER.md"
ANALYSIS_INDEX_PATH = REPO / "AnalysisLab" / "index.json"
EVIDENCE_MAP_PATH = REPO / "docs" / "evidence" / "EVIDENCE_MAP.md"
WORKFLOW_PATH = REPO / ".github" / "workflows" / "validate-governance.yml"
LEGACY_RUNTIME_OLD_ROOT = "docs/runtime/legacy/root_status/"
LEGACY_RUNTIME_ARCHIVE_ROOT = "docs/archive/legacy_runtime_status/"
DOCS_SCAN_PATHS = [
    REPO / "PROJECT_STATE.md",
    REPO / "README.md",
    REPO / "REPO_GOVERNANCE.md",
    REPO / "docs" / "operations" / "SOURCE_OF_TRUTH_POLICY.md",
]
CORE_DOC_PATHS = [
    REPO / "PROJECT_STATE.md",
    REPO / "PROJECT_ARCHITECTURE.md",
    POLICY_PATH,
    EVIDENCE_MAP_PATH,
    ANALYSIS_INDEX_PATH,
    CONTROL_CENTER_DOC,
]
```

- [ ] **Step 3.2: 改 `build_truth_sources` 的 source_docs（行 599-605）**

Edit：

```python
        "source_docs": [
            {"label": "project state", "path": relpath(repo / "PROJECT_STATE.md")},
            {"label": "architecture", "path": relpath(repo / "PROJECT_ARCHITECTURE.md")},
            {"label": "evidence map", "path": relpath(EVIDENCE_MAP_PATH)},
            {"label": "analysis index", "path": relpath(ANALYSIS_INDEX_PATH)},
        ],
```

- [ ] **Step 3.3: Commit**

```bash
git add Tools/project_control_center.py
git commit -m "refactor(control-center): point constants to new doc paths

DOCS_SCAN_PATHS and CORE_DOC_PATHS now reference PROJECT_STATE.md,
PROJECT_ARCHITECTURE.md, and docs/operations/*.
build_truth_sources source_docs updated accordingly.
"
```

---

## Task 4: 更新 Tools/tests/test_truth_plane_policy.py

**Files:**
- Modify: `Tools/tests/test_truth_plane_policy.py:86-111`

- [ ] **Step 4.1: 改測試函式內容**

Edit 行 87-111 整個 `test_root_truth_docs_reflect_combo_promotion`：

```python
def test_root_truth_docs_reflect_combo_promotion():
    state = (REPO / "PROJECT_STATE.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    architecture = (REPO / "PROJECT_ARCHITECTURE.md").read_text(encoding="utf-8")

    for text in [state, readme, architecture]:
        assert "pending R33 promotion" not in text
        assert "360→720+" not in text

    # Quick Handoff 區必須含 COMBO + approved alternates + sandbox branch
    assert "COMBO" in state
    assert "approved alternates" in state or "特化候選" in state or "Approved Alternates" in state
    assert "sandbox/r38v2" in state
    assert "active sandbox overview" not in state
    assert "Experiments\\R26NewPSFCheck\\" not in state

    # Full current state 必須保留 formal production baseline 字樣
    assert "formal production baseline" in state
    assert "目前 active 沙盒：`R26NewPSFCheck`" not in state
    assert "沒有可直接挑戰 baseline 的 current winning line" not in state

    # README 保留一句話 stub
    assert "COMBO" in readme
    assert "historical former baseline" in readme or "歷史前任 baseline" in readme
```

- [ ] **Step 4.2: 跑測試確認通過（此時 PROJECT_STATE.md 已存在但 ARCHITECTURE.md 尚未重命名）**

```bash
python -m pytest Tools/tests/test_truth_plane_policy.py::test_root_truth_docs_reflect_combo_promotion -v
```

Expected: **FAIL** (PROJECT_ARCHITECTURE.md 不存在)——這是預期的，會在 Task 6 修掉。

- [ ] **Step 4.3: Commit**

```bash
git add Tools/tests/test_truth_plane_policy.py
git commit -m "refactor(tests): update truth-plane test to read PROJECT_STATE + PROJECT_ARCHITECTURE

Removes SESSION_CONTINUITY and CURRENT_STATE reads; all former assertions
are now applied to the merged PROJECT_STATE.md.

Test will temporarily fail on missing PROJECT_ARCHITECTURE.md until Task 6.
"
```

---

## Task 5: 更新 Tools/tests/test_validate_project_structure.py

**Files:**
- Modify: `Tools/tests/test_validate_project_structure.py:55-70`

- [ ] **Step 5.1: 讀取當前檔案**

用 Read 工具開啟 `Tools/tests/test_validate_project_structure.py` 行 55-70，確認目前的 constant 鏡像位置。

- [ ] **Step 5.2: 將鏡像常數同步為新值**

Edit 行 55-70：

```python
TRUTH_PLANE_DOCS = [
    "PROJECT_STATE.md",
    "README.md",
    "PROJECT_ARCHITECTURE.md",
]
LEGACY_RUNTIME_FORMAL_DOCS = [
    "PROJECT_STATE.md",
    "README.md",
    "REPO_GOVERNANCE.md",
    "docs/operations/SOURCE_OF_TRUTH_POLICY.md",
]
```

- [ ] **Step 5.3: Commit**

```bash
git add Tools/tests/test_validate_project_structure.py
git commit -m "refactor(tests): mirror validator constants to new doc paths"
```

---

## Task 6: 重命名 PROJECT_ARCHITECTURE_AND_DECISION_MAP.md

**Files:**
- Rename: `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` → `PROJECT_ARCHITECTURE.md`

- [ ] **Step 6.1: git mv**

```bash
git mv PROJECT_ARCHITECTURE_AND_DECISION_MAP.md PROJECT_ARCHITECTURE.md
```

- [ ] **Step 6.2: 用 Read 確認檔案第一行標題並更新**

用 Edit 工具把 `PROJECT_ARCHITECTURE.md` 第一行從 `# PROJECT ARCHITECTURE AND DECISION MAP / 專案架構與決策地圖` 改為 `# PROJECT ARCHITECTURE / 專案架構與決策地圖`。

- [ ] **Step 6.3: 跑 validator 確認通過**

```bash
python Tools/validate_project_structure.py
```
Expected: 現在應該只剩 `docs/operations/SOURCE_OF_TRUTH_POLICY.md` 缺失的 error（會在 Task 12 修掉）。`TRUTH_PLANE_DOCS` 檢查應通過。

- [ ] **Step 6.4: 跑 truth plane test 確認通過**

```bash
python -m pytest Tools/tests/test_truth_plane_policy.py::test_root_truth_docs_reflect_combo_promotion -v
```
Expected: **PASS**。

- [ ] **Step 6.5: Commit**

```bash
git add PROJECT_ARCHITECTURE.md
git commit -m "refactor: rename PROJECT_ARCHITECTURE_AND_DECISION_MAP.md → PROJECT_ARCHITECTURE.md

- Shorter filename for the stable architecture rules doc
- Section structure unchanged (will be trimmed in Task 10)
"
```

---

## Task 7: Sweep 所有 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` 引用

**Files:**
- Sweep: all tracked `*.md` files

- [ ] **Step 7.1: 先找出所有還引用舊檔名的地方**

```bash
git grep -l "PROJECT_ARCHITECTURE_AND_DECISION_MAP" -- ':!docs/superpowers/'
```
Expected: 列出一份檔案清單（應該有 ~8 份）。

- [ ] **Step 7.2: 批次 replace**

對每一份列出的檔案，用 Edit 工具的 `replace_all: true` 把所有 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` 替換成 `PROJECT_ARCHITECTURE.md`。

典型目標清單：
- `README.md`
- `REPO_GOVERNANCE.md`
- `CLAUDE.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `docs/README.md`
- `docs/index/PROJECT_DOCUMENT_INDEX.md`
- `docs/evidence/EVIDENCE_MAP.md`
- `docs/index/NEW_EXPERIMENT_SOP.md`
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`（前言）
- `PROJECT_STATE.md`（如果 Full State 區有自引用）
- `.github/governance/PROJECT_CONTROL_PLANE.md`
- `Experiments/INDEX.md`

對每份檔案操作後跑：
```bash
git grep "PROJECT_ARCHITECTURE_AND_DECISION_MAP" -- ':!docs/superpowers/'
```
Expected: 逐漸收斂到空輸出。

- [ ] **Step 7.3: 確認無殘留**

```bash
git grep "PROJECT_ARCHITECTURE_AND_DECISION_MAP" -- ':!docs/superpowers/'
```
Expected: **No output**。

- [ ] **Step 7.4: Commit**

```bash
git add -u
git commit -m "refactor: replace PROJECT_ARCHITECTURE_AND_DECISION_MAP → PROJECT_ARCHITECTURE across all docs"
```

---

## Task 8: 刪除 PROJECT_SESSION_CONTINUITY.md 並 sweep 引用

**Files:**
- Delete: `PROJECT_SESSION_CONTINUITY.md`
- Sweep: all `*.md`

- [ ] **Step 8.1: 刪除檔案**

```bash
git rm PROJECT_SESSION_CONTINUITY.md
```

- [ ] **Step 8.2: 找出所有 SESSION_CONTINUITY 引用**

```bash
git grep -l "PROJECT_SESSION_CONTINUITY" -- ':!docs/superpowers/'
```

- [ ] **Step 8.3: 對每份檔案判斷替換方式**

大部分情境 `PROJECT_SESSION_CONTINUITY.md` → `PROJECT_STATE.md`。

需要人工判斷的情境：
- **「請先讀 SESSION 再讀 CURRENT」這類並列句** → 改為「請讀 `PROJECT_STATE.md`」單一引用
- **「handoff truth 更新請回寫 SESSION」** → 改為「回寫 `PROJECT_STATE.md` 的 Quick Handoff 區」
- **Reading Order 列表** → 把 SESSION 那一項刪除（或合併為 PROJECT_STATE 一項）

預期檔案：
- `README.md`（多處 reading order、工作流程規則）
- `REPO_GOVERNANCE.md`
- `CLAUDE.md`
- `AGENTS.md`
- `CONTRIBUTING.md`
- `PROJECT_STATE.md`（Full State 區裡的自引用）
- `PROJECT_ARCHITECTURE.md`（如有）
- `docs/README.md`
- `docs/runtime/legacy/README.md`
- `docs/index/PROJECT_DOCUMENT_INDEX.md`
- `docs/index/PROJECT_CONTROL_CENTER.md`
- `docs/index/NEW_EXPERIMENT_SOP.md`
- `docs/index/SOURCE_OF_TRUTH_POLICY.md`
- `docs/index/LEGACY_ROUNDS_OPERATIONS.md`
- `docs/evidence/EVIDENCE_MAP.md`
- `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`（前言）
- `.github/governance/PROJECT_CONTROL_PLANE.md`

- [ ] **Step 8.4: 額外 sweep `PROJECT_CURRENT_STATE` 舊引用（Task 1 已改檔名但外部引用未清）**

```bash
git grep -l "PROJECT_CURRENT_STATE" -- ':!docs/superpowers/' ':!PROJECT_STATE.md'
```

對每份列出的檔案替換 `PROJECT_CURRENT_STATE.md` → `PROJECT_STATE.md`。

**例外：** `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 的 `2026-04-08 歷史延續說明` block 裡提到 `PROJECT_CURRENT_STATE.md` 是歷史記錄的一部分，保留不動（歷史文件的主體凍結）；只改前言裡「目前保存規則」那段的 `current truth 請先讀 PROJECT_CURRENT_STATE.md` 為 `PROJECT_STATE.md`。

- [ ] **Step 8.5: 最終確認無殘留**

```bash
git grep "PROJECT_SESSION_CONTINUITY" -- ':!docs/superpowers/' ':!docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md'
git grep "PROJECT_CURRENT_STATE" -- ':!docs/superpowers/' ':!docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md'
```
Expected: **No output** for both。

- [ ] **Step 8.6: 跑全部驗證**

```bash
python Tools/validate_project_structure.py 2>&1 | tail -20
python -m pytest Tools/tests/ -q
python Tools/project_control_center.py --view health --health-level standard
```
Expected: validator 只剩 `docs/operations/` 的 error；pytest 全過；control center 不 FAIL。

- [ ] **Step 8.7: Commit**

```bash
git add -u
git commit -m "refactor: remove PROJECT_SESSION_CONTINUITY.md and sweep all references to PROJECT_STATE

- Delete PROJECT_SESSION_CONTINUITY.md (merged into PROJECT_STATE.md Quick Handoff)
- Replace PROJECT_CURRENT_STATE.md references with PROJECT_STATE.md
- Update reading-order and working-rules narrative across all docs
- docs/history/ body preserved (frozen at 2026-03-12)
"
```

---

## Task 9: 瘦身 PROJECT_ARCHITECTURE.md（M3）

**Files:**
- Modify: `PROJECT_ARCHITECTURE.md`

- [ ] **Step 9.1: 讀 PROJECT_ARCHITECTURE.md 現有內容**

用 Read 工具讀整份 `PROJECT_ARCHITECTURE.md`，記下各 section 的行號。

- [ ] **Step 9.2: 刪除「目前正式 Baseline Policy」section（~行 190-220）**

找到該 section（通常 header 是 `## 目前正式 Baseline Policy / Current Baseline Policy`），整段刪除。

**替換為一行：**
```markdown
## 目前 Baseline

當前正式 baseline 名稱、數字、checkpoint 路徑以 `ESTIMATOR_POLICY.json` 與 `PROJECT_STATE.md` 為準。本檔只保留穩定規則。
```

- [ ] **Step 9.3: 壓縮「已確認結論」長表格**

找到 `## 已確認結論 / Confirmed Findings` section，把裡面的 3 個子表格（已確認有效、已確認被否定、已確認的注意事項）壓縮為一行：

```markdown
## 已確認結論

當前已確認的有效方向、被否定方向、與注意事項（caution）以 `PROJECT_STATE.md` §§2-6 與 `ESTIMATOR_POLICY.json` `notes` 欄位為準。本檔只保留方法論層面的穩定規則。
```

- [ ] **Step 9.4: 刪除「真相來源導覽」section（~行 310-337）**

找到 `## 真相來源導覽 / Source of Truth Map`，整段刪除（含「各文件的責任邊界」子段）。

替換為：
```markdown
## 真相來源導覽

見 `docs/README.md` 與 `docs/operations/PROJECT_CONTROL_CENTER.md`。
```

- [ ] **Step 9.5: 刪除「目前穩定判讀摘要」section**

找到 `## 目前穩定判讀摘要 / Current Stable-Rule Reading`，整段刪除。

- [ ] **Step 9.6: 驗證行數**

```bash
wc -l PROJECT_ARCHITECTURE.md
```
Expected: **~230 行（從 352 減少 ~35%）**。

- [ ] **Step 9.7: 跑 validator 確認沒破壞斷言**

```bash
python -m pytest Tools/tests/test_truth_plane_policy.py -v
```
Expected: **PASS**（`COMBO` 仍保留在 Layer C + PSF policy 摘要裡）。

- [ ] **Step 9.8: Commit**

```bash
git add PROJECT_ARCHITECTURE.md
git commit -m "refactor(arch): trim PROJECT_ARCHITECTURE.md duplicate sections

Removed:
- Current Baseline Policy section (duplicated PROJECT_STATE §1)
- Confirmed Findings long tables (duplicated PROJECT_STATE verdicts + policy notes)
- Source of Truth Map (duplicated docs/README.md)
- Current Stable-Rule Reading (duplicated PROJECT_STATE §3)

Kept: Layer A-F stable rules + decision rules.
~352 lines → ~230 lines.
"
```

---

## Task 10: 瘦身 README.md（M2）

**Files:**
- Modify: `README.md`

- [ ] **Step 10.1: 讀 README.md 現有內容**

用 Read 讀整份 README.md，記下 section 行號。

- [ ] **Step 10.2: 刪除「目前狀態快照」section（~60 行）**

找到 `## 目前狀態快照 / Current Status Snapshot`，整段刪除。

替換為（這是必須保留的 CI 合約 stub）：

```markdown
## 目前 Baseline / Current Baseline

Formal production baseline: **COMBO / r38v2_8px_gate_p95** (effective 2026-04-08).
Round30 is the historical former baseline (歷史前任 baseline).
See `PROJECT_STATE.md` for full current state, working rules, and numbers.
```

- [ ] **Step 10.3: 刪除「完整文件閱讀順序」section**

找到 `## 完整文件閱讀順序 / Canonical Reading Order`，整段刪除。

替換為：
```markdown
## 閱讀順序 / Reading Order

從 `PROJECT_STATE.md` 開始（含 Quick Handoff）。完整文件責任邊界見 `docs/README.md`。
```

- [ ] **Step 10.4: 刪除「研究歷程圖」section**

找到 `## 研究歷程圖 / Research Path Overview` section（含 Mermaid flowchart 與「已確認方向」清單），整段刪除。

替換為：
```markdown
## 研究歷程 / Research Path

完整 Mermaid 路徑圖與里程碑數字見 `docs/analysis/RESEARCH_PATHS.md`。
```

- [ ] **Step 10.5: 刪除「升級 Baseline 的條件」section**

找到 `## 升級 Baseline 的條件 / Baseline Promotion Rules`，整段刪除。

替換為：
```markdown
## 升級 Baseline 條件

完整條件（internal gate、external 0.8px 硬邊界、`8px` guard、side-scale trade-off）見 `PROJECT_ARCHITECTURE.md` 決策規則章節。
```

- [ ] **Step 10.6: 刪除「分支策略」section**

找到 `## 分支策略 / Branch Strategy`，整段刪除。

替換為：
```markdown
## 分支策略

見 `REPO_GOVERNANCE.md`（含 branch taxonomy、reconstructed branch 原則、GitHub 治理面）。
```

- [ ] **Step 10.7: 刪除「文件同步政策」section**

整段刪除，替換為：
```markdown
## 同步政策

見 `REPO_GOVERNANCE.md` 「Sync Cadence / Update Rules」章節。
```

- [ ] **Step 10.8: 刪除「文件導覽」section 與「工作流程規則」section**

兩段一併刪除。

工作流程規則替換為：
```markdown
## 工作流程規則

Agent 行為請讀 `CLAUDE.md` / `AGENTS.md`。現況與 working rules 請讀 `PROJECT_STATE.md`。
```

文件導覽替換為：
```markdown
## 文件導覽

見 `docs/README.md`。
```

- [ ] **Step 10.9: 驗證 CI 合約仍滿足**

```bash
grep -E "COMBO|historical former baseline|歷史前任 baseline" README.md
```
Expected: 至少三行輸出（CI 斷言需要）。

```bash
wc -l README.md
```
Expected: **~230 行**（從 520 減少 ~55%）。

- [ ] **Step 10.10: 跑測試確認無破壞**

```bash
python -m pytest Tools/tests/test_truth_plane_policy.py -v
python Tools/validate_project_structure.py
```
Expected: PASS（validator 可能仍有 `docs/operations/` 錯誤）。

- [ ] **Step 10.11: Commit**

```bash
git add README.md
git commit -m "refactor(readme): trim to ~230 lines, keep identity + orientation only

Removed duplicated sections (content lives in its proper home):
- Status snapshot → PROJECT_STATE.md
- Reading order → PROJECT_STATE.md + docs/README.md
- Research path → docs/analysis/RESEARCH_PATHS.md
- Baseline promotion rules → PROJECT_ARCHITECTURE.md
- Branch strategy / sync policy → REPO_GOVERNANCE.md
- Docs navigation → docs/README.md
- Operating rules → CLAUDE.md + PROJECT_STATE.md

Kept: identity, terminology, directory tree, pipeline, baseline stub
(satisfies CI keyword assertions).
"
```

---

## Task 11: 建立 docs/operations/ 目錄並搬移 4 份檔案

**Files:**
- Create dir: `docs/operations/`
- Move: `docs/index/QUIRKS_AND_CONVENTIONS.md` → `docs/operations/QUIRKS.md`
- Move: `docs/index/SOURCE_OF_TRUTH_POLICY.md` → `docs/operations/SOURCE_OF_TRUTH_POLICY.md`
- Move: `docs/index/LEGACY_ROUNDS_OPERATIONS.md` → `docs/operations/LEGACY_ROUNDS_OPERATIONS.md`
- Move: `docs/index/PROJECT_CONTROL_CENTER.md` → `docs/operations/PROJECT_CONTROL_CENTER.md`

- [ ] **Step 11.1: 建立目錄（透過移動第一個檔案自動建立）**

```bash
mkdir -p docs/operations
git mv docs/index/QUIRKS_AND_CONVENTIONS.md docs/operations/QUIRKS.md
git mv docs/index/SOURCE_OF_TRUTH_POLICY.md docs/operations/SOURCE_OF_TRUTH_POLICY.md
git mv docs/index/LEGACY_ROUNDS_OPERATIONS.md docs/operations/LEGACY_ROUNDS_OPERATIONS.md
git mv docs/index/PROJECT_CONTROL_CENTER.md docs/operations/PROJECT_CONTROL_CENTER.md
```

- [ ] **Step 11.2: 驗證搬移成功**

```bash
ls docs/operations/
```
Expected: 4 個檔案。

```bash
ls docs/index/
```
Expected: 剩下 `EXPERIMENT_TEMPLATE.md`、`NAMING_CONVENTIONS.md`、`NEW_EXPERIMENT_SOP.md`、`PROJECT_DOCUMENT_INDEX.md`（4 份，下面 Task 會處理）。

- [ ] **Step 11.3: 跑 validator 看結果**

```bash
python Tools/validate_project_structure.py 2>&1 | tail -10
```

可能還有 error 因為 `LEGACY_ROUNDS_OPERATIONS.md` 裡面引用了自身舊路徑。這沒關係，下面 Task 12 會 sweep。

- [ ] **Step 11.4: Commit**

```bash
git add docs/
git commit -m "refactor: move 4 docs/index/ files → docs/operations/

- QUIRKS_AND_CONVENTIONS.md → QUIRKS.md (rename)
- SOURCE_OF_TRUTH_POLICY.md → same name
- LEGACY_ROUNDS_OPERATIONS.md → same name
- PROJECT_CONTROL_CENTER.md → same name

docs/index/ still contains 4 files (handled in next tasks).
"
```

---

## Task 12: 建立 STARTING_NEW_EXPERIMENT.md（三合一）

**Files:**
- Create: `docs/operations/STARTING_NEW_EXPERIMENT.md`
- Read (取內容): `docs/index/NEW_EXPERIMENT_SOP.md`、`docs/index/NAMING_CONVENTIONS.md`、`docs/index/EXPERIMENT_TEMPLATE.md`

- [ ] **Step 12.1: 用 Read 取三份源文件內容**

分別用 Read 工具讀：
- `docs/index/NEW_EXPERIMENT_SOP.md`
- `docs/index/NAMING_CONVENTIONS.md`
- `docs/index/EXPERIMENT_TEMPLATE.md`

- [ ] **Step 12.2: Write 新檔**

建立 `docs/operations/STARTING_NEW_EXPERIMENT.md`，結構：

```markdown
# Starting a New Experiment / 新實驗完整指南

Last updated: 2026-04-14

這份文件彙整新實驗的**命名規則、目錄模板、與 SOP 流程**。以前分散在 `docs/index/` 的三份文件合併於此，目的是讓接手者只讀一份就能開新實驗。

---

## 1. Naming Conventions / 命名規範

[完整貼上 NAMING_CONVENTIONS.md 的所有段落：
 - Experiment 目錄
 - Experiment 子目錄結構
 - 報告檔名
 - Git Branch
 - 檔案命名通則]

---

## 2. Directory Template / 目錄結構模板

[完整貼上 EXPERIMENT_TEMPLATE.md 的所有段落：
 - 目錄結構
 - README.md 模板
 - Launcher 模板
 - 檢查清單]

---

## 3. SOP Steps / 標準作業流程

[完整貼上 NEW_EXPERIMENT_SOP.md 的所有段落 1-8：
 - Choose the right branch family
 - Create the branch
 - Open the tracking issue
 - Update the GitHub Project
 - Update formal docs only when truth changes
 - Open a PR
 - Trigger Codex review
 - Merge only after the line is clear]

---

## 4. Combined Checklist / 整合檢查清單

完成新實驗建立後確認：

- [ ] 目錄格式 `Experiments/R##_Description/`（或相容的歷史例外格式）
- [ ] `README.md` 寫了假說與設計
- [ ] `MANIFEST.md` 已建立
- [ ] Launcher 含 `trainer.MODEL_NAME_BASE = CFG.MODEL_NAME`
- [ ] 分支命名 `sandbox/r##` 或 `research/r##`
- [ ] Issue 用 `.github/ISSUE_TEMPLATE/research-round-proposal.yml` 建立
- [ ] GitHub Project `GMM Research Control Plane` 已新增 item
- [ ] 報告檔名用 `R##_TYPE.md` 格式
- [ ] 送外部 GMF 後 `results/external_gmf/` 含三尺度
- [ ] 完成後加入 `Experiments/INDEX.md`
- [ ] 更新 `PROJECT_STATE.md` 僅在 baseline/verdict/taxonomy 改變時

以上流程需要**更新正式 docs 的時機**：只在正式真相改變時（baseline、approved alternates、side track 狀態）才更新 `PROJECT_STATE.md` 與 `ESTIMATOR_POLICY.json`。日常 runtime 噪音不要碰 canonical docs。
```

**實作提示：** 上面的 `[完整貼上...]` 要真的把三份原文件的文字貼進來（保留代碼塊、表格、連結）。不要留下 placeholder。可以在 Edit 之前用 Read 確認三份原文件內容正確。

- [ ] **Step 12.3: Commit**

```bash
git add docs/operations/STARTING_NEW_EXPERIMENT.md
git commit -m "feat(docs): create STARTING_NEW_EXPERIMENT.md (merge SOP + NAMING + TEMPLATE)

Merges three docs/index/ files into one procedural guide:
- docs/index/NAMING_CONVENTIONS.md → Section 1
- docs/index/EXPERIMENT_TEMPLATE.md → Section 2
- docs/index/NEW_EXPERIMENT_SOP.md → Section 3
Plus a combined checklist as Section 4.

Old 3 files will be removed in the next task after sweep.
"
```

---

## Task 13: 刪除 docs/index/ 剩下 4 份 + sweep 引用

**Files:**
- Delete: `docs/index/NAMING_CONVENTIONS.md`, `docs/index/EXPERIMENT_TEMPLATE.md`, `docs/index/NEW_EXPERIMENT_SOP.md`, `docs/index/PROJECT_DOCUMENT_INDEX.md`

- [ ] **Step 13.1: 確認 Task 12 新檔已含完整內容後，刪除舊檔**

```bash
git rm docs/index/NAMING_CONVENTIONS.md
git rm docs/index/EXPERIMENT_TEMPLATE.md
git rm docs/index/NEW_EXPERIMENT_SOP.md
git rm docs/index/PROJECT_DOCUMENT_INDEX.md
```

- [ ] **Step 13.2: 移除空的 docs/index/ 目錄**

```bash
ls docs/index/ 2>/dev/null && rmdir docs/index/ 2>/dev/null
```
Expected: 目錄被刪或不存在（git 不追蹤空目錄，無需特別處理）。

- [ ] **Step 13.3: Sweep 所有舊 docs/index/ 引用**

```bash
git grep -l "docs/index/" -- ':!docs/superpowers/'
```

對每份檔案套用 replace 規則：

| 舊路徑 | 新路徑 |
|--------|--------|
| `docs/index/QUIRKS_AND_CONVENTIONS.md` | `docs/operations/QUIRKS.md` |
| `docs/index/SOURCE_OF_TRUTH_POLICY.md` | `docs/operations/SOURCE_OF_TRUTH_POLICY.md` |
| `docs/index/LEGACY_ROUNDS_OPERATIONS.md` | `docs/operations/LEGACY_ROUNDS_OPERATIONS.md` |
| `docs/index/PROJECT_CONTROL_CENTER.md` | `docs/operations/PROJECT_CONTROL_CENTER.md` |
| `docs/index/NAMING_CONVENTIONS.md` | `docs/operations/STARTING_NEW_EXPERIMENT.md` |
| `docs/index/EXPERIMENT_TEMPLATE.md` | `docs/operations/STARTING_NEW_EXPERIMENT.md` |
| `docs/index/NEW_EXPERIMENT_SOP.md` | `docs/operations/STARTING_NEW_EXPERIMENT.md` |
| `docs/index/PROJECT_DOCUMENT_INDEX.md` | `docs/README.md` |

**例外：** `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 的主體（非前言）若提到 `docs/index/` 是歷史時期的路徑，保留不動。

- [ ] **Step 13.4: 確認無殘留**

```bash
git grep "docs/index/" -- ':!docs/superpowers/' ':!docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md'
```
Expected: **No output**。

- [ ] **Step 13.5: 跑全部驗證**

```bash
python Tools/validate_project_structure.py
python -m pytest Tools/tests/ -q
python Tools/project_control_center.py --view health --health-level standard
```
Expected: 全部 PASS 或僅 WARN（不可 FAIL）。

- [ ] **Step 13.6: Commit**

```bash
git add -u
git commit -m "refactor: remove docs/index/ in favor of docs/operations/

- Delete docs/index/{NAMING_CONVENTIONS,EXPERIMENT_TEMPLATE,NEW_EXPERIMENT_SOP,PROJECT_DOCUMENT_INDEX}.md
- Sweep all references:
    - QUIRKS/SOURCE_OF_TRUTH/LEGACY_ROUNDS/PROJECT_CONTROL_CENTER → docs/operations/
    - NAMING+TEMPLATE+SOP → docs/operations/STARTING_NEW_EXPERIMENT.md
    - PROJECT_DOCUMENT_INDEX → docs/README.md
- Frozen history file body preserved as-is
"
```

---

## Task 14: 放寬 docs/evidence/ 同步規則（M4）

**Files:**
- Modify: `docs/operations/SOURCE_OF_TRUTH_POLICY.md`
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

- [ ] **Step 14.1: 在 SOURCE_OF_TRUTH_POLICY.md 加入放寬聲明**

用 Edit 工具，在 `docs/operations/SOURCE_OF_TRUTH_POLICY.md` 的「實驗報告」表格之後、「Legacy batches」表格之前，插入新段落：

```markdown
### docs/evidence/ 鏡像政策（2026-04-14 更新）

`docs/evidence/*` 下的 20 份 curated copy 是**可能與 canonical drift 的穩定引用錨點**，僅供論文、對外報告的穩定路徑使用。

- **以 canonical 為準**：任何分析結論要以 canonical source 為依據
- **不強制同步**：修改 canonical 後不需要同步 mirror（但可選擇性更新）
- **mirror 可落後**：當 mirror 與 canonical 差異顯著影響理解時，才手動 refresh
- canonical source 見下方各類型的 canonical location 欄位
```

- [ ] **Step 14.2: 更新 CLAUDE.md 的 Documentation update policy**

用 Edit 工具，把 `CLAUDE.md` 的 Documentation update policy section（行 40-49）改為：

```markdown
## Documentation update policy

When recording experiment results, update these 5 files:
- `ESTIMATOR_POLICY.json` (external compare + notes)
- `PROJECT_STATE.md` (Quick Handoff + relevant Full State section)
- `PROJECT_ARCHITECTURE.md` (findings + cautions, only if stable rules changed)
- `Experiments/INDEX.md` (experiment index)
- The relevant experiment's `reports/` canonical file

Optional (no longer mandatory):
- `docs/analysis/RESEARCH_PATHS.md` — update flowchart when a line is promoted/closed
- `docs/evidence/EVIDENCE_MAP.md` — update evidence pointers when canonical reports move
- `docs/evidence/*` mirrors — may drift; canonical is authoritative
```

並把原 Source of truth policy section（行 51-58）改為：

```markdown
## Source of truth policy

Read `docs/operations/SOURCE_OF_TRUTH_POLICY.md` before editing any file that might have copies elsewhere.
- For R33+ experiments, `Experiments/*/reports/` is the only editable location for experiment reports
- `docs/evidence/` contains curated copies used as stable citation anchors — may drift from canonical; canonical is authoritative
- `Model/GeoEdgeAlignSR_v1_Infer_v5_*.py` is canonical; deployment/package copies must be synced manually
- For legacy batches under `Experiments/Legacy/organized_20260313-20260316/`, use `docs/operations/LEGACY_ROUNDS_OPERATIONS.md` before editing legacy surfaces
- When in doubt about which copy is canonical, check the policy file or ask the user
```

並把「Known quirks」section 裡的路徑引用更新：`docs/index/QUIRKS_AND_CONVENTIONS.md` → `docs/operations/QUIRKS.md`。

- [ ] **Step 14.3: AGENTS.md 同步**

`AGENTS.md` 與 `CLAUDE.md` 只差 2 行（主詞）。用 Read 確認 `AGENTS.md` 目前內容後，對應把同樣的 Documentation update policy、Source of truth policy、Known quirks 段落改為與 CLAUDE.md 一致（保留 AGENTS.md 既有的「agent」措辭）。

- [ ] **Step 14.4: 驗證 CLAUDE/AGENTS sync 檢查通過**

```bash
python Tools/validate_project_structure.py 2>&1 | grep -A2 "Check 4"
```
Expected: `Check 4: CLAUDE.md / AGENTS.md sync` 無 error。

- [ ] **Step 14.5: Commit**

```bash
git add docs/operations/SOURCE_OF_TRUTH_POLICY.md CLAUDE.md AGENTS.md
git commit -m "refactor: relax docs/evidence/ sync rule; update CLAUDE/AGENTS docs policy

- SOURCE_OF_TRUTH_POLICY: docs/evidence/* mirrors may drift; canonical authoritative
- CLAUDE.md/AGENTS.md Documentation update policy: 7 mandatory items → 5
- Evidence map + research paths moved to 'optional' category
- Path references updated to docs/operations/
"
```

---

## Task 15: 瘦身 Experiments/INDEX.md（M6）

**Files:**
- Modify: `Experiments/INDEX.md`

- [ ] **Step 15.1: 讀現況**

用 Read 讀 `Experiments/INDEX.md`（69 行）。

- [ ] **Step 15.2: 重寫為精簡版**

用 Write 把內容替換為：

```markdown
# 實驗索引 / Experiment Index

Last updated: 2026-04-14

一頁式快速索引——完整數字、checkpoint 路徑、外部 GMF 結果見 `ESTIMATOR_POLICY.json` 與各實驗 `reports/`。

---

## Active（formal baseline + approved alternates）

| Round | 目錄 | Branch | 角色 | 關鍵報告 |
|-------|------|--------|------|---------|
| **COMBO** | `R38v2SeqFixed/` | `sandbox/r38v2` | formal production baseline | `R38v2SeqFixed/reports/COMBO_RESULTS.md` |
| **R33** | `R33RobustLoss/` | `sandbox/r33` | GMF extreme alternate | `R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md` |
| **R38v2** | `R38v2SeqFixed/` | `sandbox/r38v2` | visual priority alternate | `R38v2SeqFixed/reports/R38v2_RESULTS.md` |

## Open Side Track

| Round | 目錄 | 狀態 |
|-------|------|------|
| R26 PSF | `R26NewPSFCheck/` | pending external GMF, not active mainline |

## Closed / Falsified

| Round | 目錄 | Branch | Verdict |
|-------|------|--------|---------|
| R32 | `R32Sandbox/` | `sandbox/r32` | external FAIL, 0.8px +97.7% |
| R33c | `R33ContrastFix/` | `sandbox/r33-contrast` | contrast fix did not recover |
| R34/R35/R37 | (sandbox only) | `sandbox/r34` etc. | all failed to restore sharpness |
| R38 | `R38SeqConsistency/` | `sandbox/r38` | seq all-stages noise corrupted 0.8px |

Round31（legacy batch）亦 closed，見 `Experiments/Legacy/organized_20260316/round31/`。

## 規範文件

- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 命名、模板、SOP 三合一
- `docs/operations/QUIRKS.md` — 歷史遺留事項
```

- [ ] **Step 15.3: 驗證行數 + validator**

```bash
wc -l Experiments/INDEX.md
```
Expected: **~40 行**（從 69 減少）。

```bash
python Tools/validate_project_structure.py 2>&1 | grep -A3 "Check 2"
```
Expected: `Check 2: INDEX.md references` 無 error（每個實驗目錄仍在表格中被提及）。

- [ ] **Step 15.4: Commit**

```bash
git add Experiments/INDEX.md
git commit -m "refactor: trim Experiments/INDEX.md to ~40 lines

- Removed duplicated numeric tables (now only in ESTIMATOR_POLICY.json)
- Removed checkpoint cross-reference table (in policy.json)
- Kept: active/side/closed categorization + one-line verdict + report pointer
- References updated to docs/operations/STARTING_NEW_EXPERIMENT.md
"
```

---

## Task 16: 新增 check_quick_handoff_length() lint（TDD）

**Files:**
- Modify: `Tools/validate_project_structure.py`
- Modify: `Tools/tests/test_validate_project_structure.py`

- [ ] **Step 16.1: 寫 failing test**

用 Edit 工具，在 `Tools/tests/test_validate_project_structure.py` 最後加入：

```python
def test_quick_handoff_region_within_limit(tmp_path, monkeypatch):
    """PROJECT_STATE.md 的 QUICK_HANDOFF 區間必須 ≤ 60 行（不含兩條 marker）。"""
    # Prepare a fake PROJECT_STATE.md under tmp_path
    repo_dir = tmp_path
    (repo_dir / "PROJECT_STATE.md").write_text(
        "# state\n"
        "<!-- QUICK_HANDOFF_START -->\n"
        + "line\n" * 30
        + "<!-- QUICK_HANDOFF_END -->\n"
        "rest\n",
        encoding="utf-8",
    )

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "vps", REPO / "Tools" / "validate_project_structure.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "REPO", repo_dir)
    module.ERRORS.clear()
    module.WARNINGS.clear()
    module.check_quick_handoff_length()
    assert not module.ERRORS, f"30 lines should pass, got errors: {module.ERRORS}"


def test_quick_handoff_region_exceeds_limit(tmp_path, monkeypatch):
    """超過 60 行應 error。"""
    repo_dir = tmp_path
    (repo_dir / "PROJECT_STATE.md").write_text(
        "# state\n"
        "<!-- QUICK_HANDOFF_START -->\n"
        + "line\n" * 70
        + "<!-- QUICK_HANDOFF_END -->\n",
        encoding="utf-8",
    )

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "vps", REPO / "Tools" / "validate_project_structure.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "REPO", repo_dir)
    module.ERRORS.clear()
    module.WARNINGS.clear()
    module.check_quick_handoff_length()
    assert any("Quick Handoff" in err for err in module.ERRORS), \
        f"Expected Quick Handoff error, got: {module.ERRORS}"
```

- [ ] **Step 16.2: 跑測試確認失敗**

```bash
python -m pytest Tools/tests/test_validate_project_structure.py::test_quick_handoff_region_within_limit Tools/tests/test_validate_project_structure.py::test_quick_handoff_region_exceeds_limit -v
```
Expected: **FAIL** with `AttributeError: module 'vps' has no attribute 'check_quick_handoff_length'`。

- [ ] **Step 16.3: 實作 check_quick_handoff_length()**

用 Edit 工具，在 `Tools/validate_project_structure.py` 的 `check_legacy_runtime_archive_paths` 之後加入：

```python
QUICK_HANDOFF_MAX_LINES = 60


def check_quick_handoff_length():
    """驗證 PROJECT_STATE.md 的 Quick Handoff 區間 ≤ 60 行（不含兩條 marker）。"""
    print("=== Check 10: PROJECT_STATE Quick Handoff region length ===")
    state_path = REPO / "PROJECT_STATE.md"
    if not state_path.exists():
        error("PROJECT_STATE.md does not exist")
        return

    text = state_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if "QUICK_HANDOFF_START" in line and start_idx is None:
            start_idx = i
        elif "QUICK_HANDOFF_END" in line and end_idx is None:
            end_idx = i

    if start_idx is None or end_idx is None:
        error(
            "PROJECT_STATE.md missing QUICK_HANDOFF_START or QUICK_HANDOFF_END marker"
        )
        return

    interior_lines = end_idx - start_idx - 1
    if interior_lines > QUICK_HANDOFF_MAX_LINES:
        error(
            f"PROJECT_STATE.md Quick Handoff region has {interior_lines} lines, "
            f"exceeds limit {QUICK_HANDOFF_MAX_LINES}. Trim before committing."
        )
```

並在 `run_validator()` 函式裡，在 `check_legacy_runtime_archive_paths()` 呼叫之後加入：

```python
    check_quick_handoff_length()
```

- [ ] **Step 16.4: 跑測試確認通過**

```bash
python -m pytest Tools/tests/test_validate_project_structure.py::test_quick_handoff_region_within_limit Tools/tests/test_validate_project_structure.py::test_quick_handoff_region_exceeds_limit -v
```
Expected: **PASS（2 tests）**。

- [ ] **Step 16.5: 跑完整 validator 確認對目前 PROJECT_STATE.md 通過**

```bash
python Tools/validate_project_structure.py
```
Expected: **全過**（Check 10 對目前 PROJECT_STATE.md 應 PASS，因為 Quick Handoff 區 ≤ 60 行）。

如果 Check 10 FAIL，表示 Task 1 建立的 Quick Handoff 區超過 60 行——回頭瘦身。

- [ ] **Step 16.6: Commit**

```bash
git add Tools/validate_project_structure.py Tools/tests/test_validate_project_structure.py
git commit -m "feat(validator): add check_quick_handoff_length() lint

- Enforces PROJECT_STATE.md Quick Handoff region ≤ 60 lines
- Machine guarantee of the 'short-read' contract
- Two tests cover within-limit PASS and over-limit FAIL
"
```

---

## Task 17: 歷史長河文件前言更新

**Files:**
- Modify: `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`（前言內兩處引用）

- [ ] **Step 17.1: 讀前言段落**

```bash
head -40 docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md
```

確認目前前言含：
- `current truth 請先讀 PROJECT_CURRENT_STATE.md`
- `穩定規則請讀 PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`

- [ ] **Step 17.2: 用 Edit 更新兩處引用**

```
Old: current truth 請先讀 `PROJECT_CURRENT_STATE.md`
New: current truth 請先讀 `PROJECT_STATE.md`
```

```
Old: 穩定規則請讀 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md`
New: 穩定規則請讀 `PROJECT_ARCHITECTURE.md`
```

（Task 8 的 Step 8.4 可能已處理——若已處理，此 task 無 change，跳到 Step 17.3 驗證即可。）

- [ ] **Step 17.3: 確認 diff**

```bash
git diff docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md
```
Expected: 只有前言兩行變動；主體 4900+ 行不變。

- [ ] **Step 17.4: Commit（如有 diff）**

```bash
git add docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md
git commit -m "docs(history): update preface references to new doc filenames

- PROJECT_CURRENT_STATE.md → PROJECT_STATE.md
- PROJECT_ARCHITECTURE_AND_DECISION_MAP.md → PROJECT_ARCHITECTURE.md

Main body (frozen at 2026-03-14) unchanged. Per user decision (2026-04-14),
this history file continues to accept body additions in the future — no
chapter-splitting required.
"
```

---

## Task 18: 最終驗收

**Files:**
- Read-only: all.

- [ ] **Step 18.1: 確認無殘留舊路徑字串**

```bash
git grep -l "PROJECT_SESSION_CONTINUITY\|PROJECT_CURRENT_STATE\|PROJECT_ARCHITECTURE_AND_DECISION_MAP\|docs/index/" \
  -- ':!docs/superpowers/' ':!docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md'
```
Expected: **No output**。

如果歷史文件以外還有任何檔案命中，回頭修改該檔案再 commit。

- [ ] **Step 18.2: 驗證所有 CI 檢查通過**

```bash
python Tools/validate_project_structure.py
```
Expected: **All checks passed** 或僅 WARNINGS。

```bash
python -m pytest Tools/tests/ -q
```
Expected: **All tests pass**。

```bash
python Tools/project_control_center.py --view health --health-level standard
```
Expected: status **PASS** 或 **WARN**（不可 FAIL；若 WARN 僅是 worktree dirty 或新 tracked changes，可接受）。

- [ ] **Step 18.3: 驗證成功條件清單**

確認以下 spec §9 條件全部符合：

1. `python Tools/validate_project_structure.py` ✅（含 check_quick_handoff_length）
2. `python -m pytest Tools/tests/` ✅
3. control center `--view health --health-level standard` 不 FAIL ✅
4. `git grep` 無舊路徑殘留（見 Step 18.1）✅
5. CLAUDE.md Documentation update policy 項目數 = 5 ✅
6. Tier 1 root governance 檔案數 = 5（README, PROJECT_STATE, PROJECT_ARCHITECTURE, REPO_GOVERNANCE, ESTIMATOR_POLICY.json）✅
7. PROJECT_STATE.md Quick Handoff 區 ≤ 60 行 ✅

驗證第 5 條：
```bash
awk '/## Documentation update policy/,/## Source of truth policy/' CLAUDE.md | grep "^- " | wc -l
```
Expected: **5**（`ESTIMATOR_POLICY.json` + `PROJECT_STATE.md` + `PROJECT_ARCHITECTURE.md` + `Experiments/INDEX.md` + experiment reports）。

驗證第 6 條：
```bash
ls *.md *.json | grep -E "^(README|PROJECT_STATE|PROJECT_ARCHITECTURE|REPO_GOVERNANCE|ESTIMATOR_POLICY)\." | wc -l
```
Expected: **5**。

驗證第 7 條：
```bash
awk '/QUICK_HANDOFF_START/,/QUICK_HANDOFF_END/' PROJECT_STATE.md | wc -l
```
Expected: **≤ 62**（含兩條 marker）。

- [ ] **Step 18.4: 產生最終 diff 摘要**

```bash
git log --oneline main..HEAD | wc -l  # commit 數
git diff --stat main..HEAD | tail -1  # 檔案變動總量
```

記下這兩個數字作為 PR 摘要資料。

- [ ] **Step 18.5: Push 分支並開 PR**

```bash
git push -u origin refactor/governance-docs-simplification
```

開 PR（用 `gh pr create`）：
- Title: `refactor: simplify governance docs (18 files → 10, CLAUDE update policy 7→5)`
- Body 摘要：引用本 plan + spec，列出 6 個遷移動作 M1-M6 的結果

---

## Post-flight / 收尾

遷移完成後：

1. PR merge 到 main
2. 刪除分支：`git push origin --delete refactor/governance-docs-simplification`
3. 更新 `Experiments/INDEX.md` 若有新實驗記錄
4. 在下次 session 驗證 `CLAUDE.md` 的新 reading order 實際有效

**Rollback 策略（如果合併後發現嚴重問題）：**

```bash
git revert <merge-commit-sha>
```

由於每個 task 都獨立 commit，也可以只 revert 特定 task 的 commit。

---

**End of implementation plan.**
