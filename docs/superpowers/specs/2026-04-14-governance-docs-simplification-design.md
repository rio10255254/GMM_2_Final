# Governance Docs Simplification Design

**Date:** 2026-04-14
**Owner:** GMM_2_Final governance
**Status:** Draft — pending user review

## 1. Purpose / 目的

這份 spec 定義「治理文件層精簡化」的目標結構與遷移計畫。目的是讓 AI agent 或人類在每次重大決策（baseline promote、alternate 核准、side track 關閉）時需要改動的文件數量大幅下降，同時消除文件之間的內容漂移（drift）。

This spec defines the target structure and migration plan for simplifying the governance documentation layer. The goal is to reduce the number of files touched on every major decision and eliminate content drift between docs.

## 2. Problem / 問題

專案目前有 **42 份以上需要維護的治理層文件 / 2924 行內容**，其中：

- **Tier 1 核心真相層 8 份 / 1714 行**：每次 baseline 變動都要更新，散文結構中充滿從 `ESTIMATOR_POLICY.json` 重複的事實
- **Tier 2 規則/政策層 14 份**：職責重疊嚴重（尤其 `docs/index/` 的 10 份）
- **Tier 4 證據鏡像 20 份**：`SOURCE_OF_TRUTH_POLICY.md` 規定改 canonical 後要手動同步 mirror

當前結構的根本問題是**組織軸線錯誤**——按「主題」切分文件會導致主題重疊（「交接」包含「現況」、「總覽」包含「架構摘要」），重複與漂移自然產生。

根據 `CLAUDE.md` 的 Documentation update policy，**每次 baseline 變動要改 7+ 份文件**。這個數字必須降下來。

## 3. Design Principles / 設計原則

### 3.1 單一更新理由原則（Single Update Reason）

每份文件只為「一個更新理由」存在：
- 如果兩份文件常為同一件事一起改 → 應該合併
- 如果一份文件為兩件不同的事被改 → 應該拆分
- 如果一份文件塞了它不該管的東西 → 應該重新定位

### 3.2 組織軸線：更新頻率 × 讀者

捨棄「按主題」組織，改用「更新頻率 × 讀者」組織：

| 軸線 | 代表文件 |
|------|---------|
| 高頻 × 機器 | `ESTIMATOR_POLICY.json` |
| 高頻 × 人類 | `PROJECT_STATE.md` |
| 低頻 × 人類 | `PROJECT_ARCHITECTURE.md`, `REPO_GOVERNANCE.md` |
| 極低頻 × AI | `CLAUDE.md`, `AGENTS.md` |
| 一次性 × 參考 | `docs/history/`, `docs/evidence/`, `docs/policy/` |

### 3.3 短讀屬性由機器保證，不靠人類自律

「Quick Handoff」這類短讀視圖的長度上限，應由 CI lint 強制，不靠人類記得。

### 3.4 不自動生成、不引入 AI 寫作代工

本 spec **不涉及自動生成散文文件**。AI agent 仍由人類決定內容。精簡化的收益來自「文件變少、每份各司其職」，不是「機器幫忙寫」。

## 4. Target Structure / 目標結構

```
d:\GMM_2_Final\
│
├── README.md                          # 入口：識別 + 目錄 + 第一次導航（~120 行）
├── PROJECT_STATE.md                   # 現況 + Quick Handoff + Working Rules（合 SESSION + CURRENT）
├── PROJECT_ARCHITECTURE.md            # 研究架構規則（瘦身版）
├── REPO_GOVERNANCE.md                 # Git/GitHub 治理（保持獨立）
├── ESTIMATOR_POLICY.json              # 機器真相
├── CLAUDE.md / AGENTS.md              # Agent 契約
├── CONTRIBUTING.md                    # 貢獻指南
│
├── Experiments/
│   ├── INDEX.md                       # 實驗導航（瘦身至 ~40 行）
│   └── R##_Description/               # 每實驗的 MANIFEST + README + reports/
│
└── docs/
    ├── README.md                      # docs 區入口
    │
    ├── operations/                    # 原 docs/index/ 重組
    │   ├── STARTING_NEW_EXPERIMENT.md # 合 SOP + NAMING + TEMPLATE
    │   ├── LEGACY_ROUNDS_OPERATIONS.md
    │   ├── QUIRKS.md                  # 原 QUIRKS_AND_CONVENTIONS
    │   ├── SOURCE_OF_TRUTH_POLICY.md  # 瘦身版
    │   └── PROJECT_CONTROL_CENTER.md
    │
    ├── analysis/RESEARCH_PATHS.md
    ├── evidence/                      # 保留，放寬同步要求
    ├── history/                       # 凍結
    ├── policy/                        # PSF 政策
    └── archive/                       # legacy runtime
```

**治理層文件數變化：**
- Tier 1 root: 8 → **5**
- docs/index/ → docs/operations/: 10 → **5**
- 合計：18 → **10 份文件**（-44%）
- `CLAUDE.md` Documentation update policy 項目：7 → **5**

## 5. Per-File Responsibility / 每份文件職責

| 文件 | 單一職責 | 更新觸發 |
|------|---------|---------|
| `README.md` | 這是什麼專案、第一次來該去哪 | 專案定位改變（極少）|
| `PROJECT_STATE.md` | 現在什麼是真的、怎麼接手、6 條 working rules | 決策改變 |
| `PROJECT_ARCHITECTURE.md` | 穩定研究規則（Layer A-F + 升級條件）| 架構層決策（很少）|
| `REPO_GOVERNANCE.md` | Git 分支、追蹤範圍、同步節奏 | 治理規則變 |
| `ESTIMATOR_POLICY.json` | 結構化機器真相 | 每次決策 |
| `CLAUDE.md` / `AGENTS.md` | Agent 行為契約 | 合作模式改變 |
| `Experiments/INDEX.md` | 實驗清單導航 | 新實驗建立 |
| `docs/operations/STARTING_NEW_EXPERIMENT.md` | 開新實驗的完整指引 | SOP 變化 |
| `docs/operations/LEGACY_ROUNDS_OPERATIONS.md` | Legacy batch 操作指引 | legacy 面變化 |
| `docs/operations/QUIRKS.md` | 歷史遺留技術債清單 | 發現新 quirk |
| `docs/operations/SOURCE_OF_TRUTH_POLICY.md` | canonical vs mirror 定義 | 鏡像政策變 |
| `docs/operations/PROJECT_CONTROL_CENTER.md` | 控制中心使用說明 | 控制中心功能變 |

## 6. Migration Moves / 遷移動作

### M1 — SESSION_CONTINUITY + CURRENT_STATE → PROJECT_STATE.md

**做法：**

建立新檔 `PROJECT_STATE.md`，結構如下：

```markdown
# PROJECT_STATE.md

<!-- QUICK_HANDOFF_START: keep under 50 lines -->
## 🟢 Quick Handoff (3-min read)

### Current Baseline
COMBO / r38v2_8px_gate_p95 (effective 2026-04-08)

### Approved Alternates
- R33 / r33_robust_p95 — GMF extreme
- R38v2 / r38v2_8px_gate — visual priority

### Open Side Tracks
- R26NewPSFCheck (pending external GMF)

### Working Rules (6)
1. 先讀本檔 Quick Handoff 區完整理解現況
2. 以 repo 正式文件為準，不以 `.codex` / `.claude` 內部 session 檔為準
3. root prose current state 以 COMBO + approved alternates 為主，R26NewPSFCheck 不是 active mainline
4. legacy root runtime 快照已封存到 `docs/archive/legacy_runtime_status/`
5. baseline / verdict / taxonomy 有變時，優先更新本檔 + `ESTIMATOR_POLICY.json`
6. external FAIL 或 closed 的候選，不再以 promising / active 的語氣描述
<!-- QUICK_HANDOFF_END -->

---

## Full Current State

### §1 Formal Baseline
[完整數字表 + 敘事，從原 CURRENT_STATE §1]

### §2 Approved Alternates
[從原 CURRENT_STATE §2]

... §3 to §7 ...
```

**合併後的內容來源對應：**
- 原 `SESSION_CONTINUITY.md` 的 Handoff Snapshot → Quick Handoff 區的短版
- 原 `SESSION_CONTINUITY.md` 的 6 Working Rules → Quick Handoff 區的 Working Rules 小節
- 原 `CURRENT_STATE.md` 全部內容 → Full Current State 區

**刪除：** `PROJECT_SESSION_CONTINUITY.md`

**保護短讀屬性：** 在 `Tools/validate_project_structure.py` 加一個 `check_quick_handoff_length()`，讀 `PROJECT_STATE.md`，統計 `<!-- QUICK_HANDOFF_START -->` 和 `<!-- QUICK_HANDOFF_END -->` 之間的行數（不含兩條 marker），**硬上限 60 行**，超過即 error（非 warning）。這是機器強制的短讀合約，不靠人類自律。

### M2 — 瘦身 README.md (520 → ~120 行)

**保留段落：**
- 白話版說明 + Technical Version
- 核心名詞速查（術語表）
- 目錄結構樹
- 系統整體流程（pipeline 圖）
- **一句話狀態 stub**（滿足 CI 關鍵字檢查）

**刪除段落：**
- 目前狀態快照（→ PROJECT_STATE）
- 完整文件閱讀順序（→ PROJECT_STATE）
- 研究歷程圖 + 確認方向清單（→ `docs/analysis/RESEARCH_PATHS.md`）
- 升級 baseline 條件（→ PROJECT_ARCHITECTURE）
- 分支策略（→ REPO_GOVERNANCE）
- 文件同步政策（→ REPO_GOVERNANCE）
- 文件導覽（→ docs/README.md）
- 工作流程規則（→ PROJECT_STATE）

**保留的一句話狀態 stub 範例：**

```markdown
## Current Baseline

Formal production baseline: **COMBO / r38v2_8px_gate_p95** (effective 2026-04-08).
Round30 is the historical former baseline.
See `PROJECT_STATE.md` for full current state and working rules.
```

此 stub 同時滿足 `test_truth_plane_policy.py` 對 README 的三條斷言：含 `COMBO`、含 `historical former baseline` 或 `歷史前任 baseline`、不含 5 條 forbidden phrase。

### M3 — 瘦身 PROJECT_ARCHITECTURE.md (352 → ~230 行)

（新檔名為 `PROJECT_ARCHITECTURE.md`，原檔名 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` 太長）

**保留段落：**
- Layer A External Truth
- Layer B Internal Surrogates
- Layer C Current Optimization Target
- Layer D PSF Role and Architecture Boundary
- 穩定架構邊界（Root / R32 / R26 Side）
- 決策規則（baseline 升級條件 + 新 round 立案規則）

**刪除段落：**
- 「目前正式 Baseline Policy」（30 行；重複 PROJECT_STATE §1）
- 「已確認結論」長表格（壓縮成「詳見 PROJECT_STATE 與 policy.notes」）
- 「真相來源導覽」表（重複 docs/README 的導覽）
- 「目前穩定判讀摘要」（重複 PROJECT_STATE §3）

### M4 — docs/evidence/ 放寬同步規則

**不刪除任何 mirror 檔。** 保留 20 份 mirror 的理由是提供「穩定引用錨點」—— canonical source 在 `Traing_Progress/organized_*/` 這層不建議直接編輯的歷史面下。

**改動：**
- `docs/operations/SOURCE_OF_TRUTH_POLICY.md` 新增一段：「`docs/evidence/*` 的 mirror 以 canonical 為準，不保證同步；mirror 僅供論文、對外報告的穩定引用錨點使用」
- `CLAUDE.md` / `AGENTS.md` 的 Source of truth policy 段，移除「先改 canonical → 再同步 mirror」的硬要求
- `CLAUDE.md` 的 Documentation update policy 從 7 項變 5 項（移除 `docs/evidence/EVIDENCE_MAP.md` 與 `docs/analysis/RESEARCH_PATHS.md` 的強制更新項，改為建議性）

### M5 — docs/index/ → docs/operations/ 重組

**檔案改動：**

| 動作 | 原路徑 | 新路徑 |
|------|--------|--------|
| 移動 | `docs/index/LEGACY_ROUNDS_OPERATIONS.md` | `docs/operations/LEGACY_ROUNDS_OPERATIONS.md` |
| 移動並重命名 | `docs/index/QUIRKS_AND_CONVENTIONS.md` | `docs/operations/QUIRKS.md` |
| 移動 | `docs/index/SOURCE_OF_TRUTH_POLICY.md` | `docs/operations/SOURCE_OF_TRUTH_POLICY.md`（並瘦身） |
| 移動 | `docs/index/PROJECT_CONTROL_CENTER.md` | `docs/operations/PROJECT_CONTROL_CENTER.md` |
| 三合一 | `docs/index/NEW_EXPERIMENT_SOP.md` + `docs/index/NAMING_CONVENTIONS.md` + `docs/index/EXPERIMENT_TEMPLATE.md` | `docs/operations/STARTING_NEW_EXPERIMENT.md` |
| 刪除 | `docs/index/PROJECT_DOCUMENT_INDEX.md` | 職責由 `README.md` + `docs/README.md` 接手 |

**`STARTING_NEW_EXPERIMENT.md` 結構：**

```markdown
# Starting a New Experiment

## 1. Branch & Naming
[原 NAMING_CONVENTIONS 內容]

## 2. Directory Template
[原 EXPERIMENT_TEMPLATE 內容]

## 3. SOP Steps
[原 NEW_EXPERIMENT_SOP 內容]

## 4. Checklist
[三份各自的 checklist 彙整]
```

### M6 — Experiments/INDEX.md 瘦身 (69 → ~40 行)

**保留：** 實驗名、目錄、branch、一句話狀態、主要報告連結
**刪除：** 與 `ESTIMATOR_POLICY.json` 重複的完整數字表、checkpoint 對照表（這些在 policy.json 裡）

## 7. Interface Preservation / 介面保留策略

本節列出所有硬引用舊路徑的程式與 CI，以及對應的更新動作。

### 7.1 `Tools/validate_project_structure.py`

| 原位置 | 原內容 | 新內容 |
|--------|--------|--------|
| L26-29 `CANONICAL_INFERENCE_SCRIPTS` | 不變 | 不變 |
| L32-37 `TRUTH_PLANE_DOCS` | 含 `PROJECT_SESSION_CONTINUITY.md` + 原 ARCH 檔名 | 移除 SESSION，改為 `PROJECT_STATE.md`；ARCH 改新檔名 |
| L40-45 `LEGACY_RUNTIME_FORMAL_DOCS` | 含 SESSION | 移除 SESSION，改為 `PROJECT_STATE.md` |
| L175 `check_claude_agents_sync` | 檢查 4 section 同步 | 不變（CLAUDE / AGENTS 維持獨立）|
| L344 `check_truth_plane` 迴圈 | 遍歷 TRUTH_PLANE_DOCS | 已由上述 constant 變更自動覆蓋 |
| 新增 | — | `check_quick_handoff_length()`：驗證 `PROJECT_STATE.md` 的 `QUICK_HANDOFF_START/END` 區間 ≤ 60 行 |

### 7.2 `Tools/project_control_center.py`

| 原位置 | 新內容 |
|--------|--------|
| L20 `POLICY_PATH` | 不變 |
| L21 `CONTROL_CENTER_DOC` | `REPO / "docs" / "operations" / "PROJECT_CONTROL_CENTER.md"` |
| L23 `EVIDENCE_MAP_PATH` | 不變 |
| L28-32 `DOCS_SCAN_PATHS` | 移除 `PROJECT_SESSION_CONTINUITY.md`，改為 `PROJECT_STATE.md`；`SOURCE_OF_TRUTH_POLICY.md` 路徑改為 `docs/operations/` |
| L34-40 `CORE_DOC_PATHS` | 移除 SESSION + 舊 ARCH 路徑；新增 `PROJECT_STATE.md` + 新 ARCH 路徑 |
| L600-603 `build_truth_sources` 的 source_docs | 同上 |

### 7.3 `Tools/tests/test_truth_plane_policy.py`

| 原位置 | 新內容 |
|--------|--------|
| L88-91 讀四份文件 | 從 `SESSION + CURRENT + README + ARCH` → `PROJECT_STATE + README + PROJECT_ARCHITECTURE`（3 份）|
| L93-94 forbidden phrase 檢查 | 遍歷範圍改為新的 3 份 |
| L97-101 SESSION 專屬斷言 | 搬到 PROJECT_STATE 的斷言，檢查 Quick Handoff 區含 `COMBO` + `approved alternates`/`特化候選` + `sandbox/r38v2` |
| L103-106 CURRENT 專屬斷言 | 搬到 PROJECT_STATE 的斷言 |
| L108-110 README 斷言 | 不變（README 仍保留一句話 stub）|

### 7.4 `Tools/tests/test_validate_project_structure.py`

L57-68 的兩個 constant 鏡像 `validate_project_structure.py`，同步更新。

### 7.5 CLAUDE.md / AGENTS.md

- L5-8 「Before planning... 1. SESSION 2. CURRENT」→ 改為單一 `PROJECT_STATE.md`
- L31 引用 `docs/index/NAMING_CONVENTIONS.md` 與 `docs/index/EXPERIMENT_TEMPLATE.md` → 改為 `docs/operations/STARTING_NEW_EXPERIMENT.md`
- L40-49 Documentation update policy 七項 → 五項（移除 RESEARCH_PATHS 與 EVIDENCE_MAP 的強制項）
- L53 引用 `docs/index/SOURCE_OF_TRUTH_POLICY.md` → `docs/operations/SOURCE_OF_TRUTH_POLICY.md`
- L57 引用 `docs/index/LEGACY_ROUNDS_OPERATIONS.md` → `docs/operations/LEGACY_ROUNDS_OPERATIONS.md`
- L62 引用 `docs/index/QUIRKS_AND_CONVENTIONS.md` → `docs/operations/QUIRKS.md`
- AGENTS.md 同步所有變動

### 7.6 其他引用更新

根據 `git grep` 結果，下列 20 個檔案含舊路徑字串，需批次 replace：

`REPO_GOVERNANCE.md`, `CONTRIBUTING.md`, `docs/README.md`, `docs/archive/README.md`, `docs/evidence/README.md`, `docs/runtime/legacy/README.md`, `docs/evidence/EVIDENCE_MAP.md`, `docs/analysis/RESEARCH_PATHS.md`, `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`, `.github/governance/PROJECT_CONTROL_PLANE.md`, `Experiments/INDEX.md`, `Experiments/R##_*/README.md` 等。

**Replace 規則（分兩類）：**

純路徑字串替換（可機器執行）：
- `PROJECT_CURRENT_STATE.md` → `PROJECT_STATE.md`
- `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` → `PROJECT_ARCHITECTURE.md`
- `docs/index/QUIRKS_AND_CONVENTIONS.md` → `docs/operations/QUIRKS.md`
- `docs/index/SOURCE_OF_TRUTH_POLICY.md` → `docs/operations/SOURCE_OF_TRUTH_POLICY.md`
- `docs/index/LEGACY_ROUNDS_OPERATIONS.md` → `docs/operations/LEGACY_ROUNDS_OPERATIONS.md`
- `docs/index/PROJECT_CONTROL_CENTER.md` → `docs/operations/PROJECT_CONTROL_CENTER.md`

需要人工審閱再替換（因為前後文可能要調整）：
- `PROJECT_SESSION_CONTINUITY.md` → `PROJECT_STATE.md`
  - 原句若是「請先讀 SESSION_CONTINUITY 再讀 CURRENT_STATE」這類兩文件並提，需改寫為單一引用，不能單純 replace
  - 原句若是「handoff truth 請回寫 SESSION_CONTINUITY」這類更新指示，改為「回寫 PROJECT_STATE 的 Quick Handoff 區」
- `docs/index/NAMING_CONVENTIONS.md`、`docs/index/NEW_EXPERIMENT_SOP.md`、`docs/index/EXPERIMENT_TEMPLATE.md` → `docs/operations/STARTING_NEW_EXPERIMENT.md`
  - 如果原文同時引用其中兩份，合併為單一引用
- `docs/index/PROJECT_DOCUMENT_INDEX.md` → `docs/README.md`
  - 原文若用作「文件目錄入口」，改指 `docs/README.md`；若用作「治理文件責任表」，改指 `README.md`

## 8. Out of Scope / 不在本 spec 範圍

- **自動化生成散文文件**：AI 仍由人類決定寫什麼，不引入 policy → doc 的生成器
- **Transaction-style 操作腳本**：未在本 spec 規劃；若未來要做，是獨立 spec
- **合併 `PROJECT_ARCHITECTURE.md` 與 `REPO_GOVERNANCE.md`**：兩者職責不同（研究規則 vs git 治理），不合併
- **刪除 `docs/evidence/*` mirror**：保留作為引用錨點，只放寬同步規則
- **更動 `docs/policy/`、`docs/archive/`**：本次不處理
- **`docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 繼續使用**：僅更新其前言內的兩處檔名引用（`PROJECT_CURRENT_STATE.md` → `PROJECT_STATE.md`、`PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` → `PROJECT_ARCHITECTURE.md`）；未來新歷史可直接寫進本檔，檔案大小不設限，不再刻意分章節
- **更動實驗內部的 `Experiments/*/reports/` 結構**：本 spec 只處理 root 治理層

## 9. Success Criteria / 成功條件

遷移完成後必須同時滿足：

1. `python Tools/validate_project_structure.py` 通過（含新加的 `check_quick_handoff_length`）
2. `python -m pytest Tools/tests/` 全通過
3. `python Tools/project_control_center.py --view health --health-level standard` 回報 PASS 或 WARN（不能 FAIL）
4. `git grep` 找不到舊路徑字串（`PROJECT_SESSION_CONTINUITY`、舊 `docs/index/` 子路徑等）殘留在 tracked 檔案
5. `CLAUDE.md` 的 Documentation update policy 項目數 = 5
6. Tier 1 root governance 檔案數 = 5（不含 CONTRIBUTING / CLAUDE / AGENTS）
7. `PROJECT_STATE.md` 的 Quick Handoff 區 ≤ 60 行

## 10. Risks / 風險

| 風險 | 評估 | 緩解 |
|------|------|------|
| 合併後 Quick Handoff 區會被慢慢塞爆 | 中 | `check_quick_handoff_length()` 強制機器守門 |
| Replace 掃描漏改某份文件 | 中 | 遷移 PR 前跑 `git grep` 全倉掃描，CI 加入「禁止出現舊路徑字串」檢查 |
| 外部引用（論文草稿、OneDrive 筆記）指到舊路徑 | 低-中 | 在 `docs/README.md` 加「檔案改名對照表」供追溯；舊路徑本來就不穩定 |
| `docs/evidence/` 放寬同步後，mirror 與 canonical 差異變大 | 低 | 明示「以 canonical 為準」；論文引用可走 canonical 或 mirror 皆可 |
| 遷移時中斷其他工作 | 中 | 切 `refactor/governance-docs-simplification` 分支，一次 PR 合併，合併前確保主線無進行中實驗 |

## 11. Migration Order / 遷移順序

建議的執行順序（每步都可獨立 commit、獨立測試）：

1. **Step 1**：新增 `PROJECT_STATE.md`（複製 CURRENT_STATE 全部 + 新增 Quick Handoff 區 + 併入 SESSION 的 Working Rules）；保留舊檔不刪
2. **Step 2**：更新 `validate_project_structure.py`、`project_control_center.py`、`test_truth_plane_policy.py` 的 constants 指向新檔；跑測試確認通過
3. **Step 3**：刪除 `PROJECT_SESSION_CONTINUITY.md`；跑 `git grep` 清理所有引用
4. **Step 4**：重命名 `PROJECT_ARCHITECTURE_AND_DECISION_MAP.md` → `PROJECT_ARCHITECTURE.md`，同步更新引用（含 `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 前言裡的兩處檔名引用）
5. **Step 5**：執行 M3（瘦身 ARCHITECTURE）
6. **Step 6**：執行 M2（瘦身 README）
7. **Step 7**：執行 M5（重組 docs/index/ → docs/operations/）；三合一 `STARTING_NEW_EXPERIMENT.md`；刪除 `PROJECT_DOCUMENT_INDEX.md`
8. **Step 8**：執行 M4（放寬 evidence 同步規則 + 調整 CLAUDE/AGENTS 的 update policy）
9. **Step 9**：執行 M6（瘦身 `Experiments/INDEX.md`）
10. **Step 10**：新增 `check_quick_handoff_length()`；最終 CI 驗收

每一步完成後 `python Tools/project_control_center.py` 都必須回報 PASS/WARN，不能 FAIL。

---

**End of Design Spec.**
