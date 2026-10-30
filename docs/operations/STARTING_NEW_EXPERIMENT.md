# Starting a New Experiment / 新實驗完整指南

Last updated: 2026-08-13

這份文件彙整新實驗的**命名規則、目錄模板、與 SOP 流程**。以前分散在 `docs/index/` 的三份文件（`NAMING_CONVENTIONS.md`、`EXPERIMENT_TEMPLATE.md`、`NEW_EXPERIMENT_SOP.md`）合併於此，目的是讓接手者只讀一份就能開新實驗。

---

## 1. Naming Conventions / 命名規範

### Experiment 目錄

**格式**: `Experiments/R##_Description/`

| 元素 | 規則 | 範例 |
|------|------|------|
| Round 編號 | `R` + 數字，無前導零 | `R33`, `R38`, `R42` |
| 版本變體 | 加 `v2`、`v3` 後綴 | `R38v2` |
| 描述 | PascalCase，用底線分隔詞組 | `RobustLoss`, `SeqFixed`, `FreqSplit` |
| 全名 | `R##[v#]_Description` | `R33_RobustLoss`, `R38v2_SeqFixed` |

**歷史例外**（保持原名，不重新命名）：
- `R26NewPSFCheck`（無底線，PascalCase 連寫）
- `R32Sandbox`（無底線）
- `R33RobustLoss`、`R33ContrastFix`（無底線，已定案）
- `R38SeqConsistency`、`R38v2SeqFixed`（無底線，已定案）

新實驗從下一輪起使用底線格式：`R39_Description`。

### 報告檔名

**格式**: `R##_TYPE.md` 或 `TOPIC_TYPE.md`

| TYPE | 用途 | 範例 |
|------|------|------|
| RESULTS | 完整實驗結果 | `R38v2_RESULTS.md` |
| SUMMARY | 實驗摘要（含多候選） | `R33_EXPERIMENT_SUMMARY.md` |
| AUDIT | 審計/盤查報告 | `DATA_FLOW_AUDIT.md` |
| METHODOLOGY | 方法論說明 | `GMF_STEP_STD_METHODOLOGY.md` |
| ANALYSIS | 深度分析 | `INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md` |

- 全部大寫（`RESULTS`），底線分隔
- Round 前綴用 `R##`（不用 `ROUND##`）
- 跨 Round 的報告用範圍：`R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`
- 不用時間戳命名（Git history 提供時間資訊）

**歷史例外**：`r33_robust_p90_results.md`（小寫，已定案不改）

### Git Branch

**格式**: `sandbox/r##` 或 `sandbox/r##-description`

| 用途 | 格式 | 範例 |
|------|------|------|
| 實驗 sandbox | `sandbox/r##` | `sandbox/r33`, `sandbox/r38v2` |
| 變體 | `sandbox/r##-description` | `sandbox/r33-contrast` |
| AI agent | `codex/*` | 合併後刪除 |
| Baseline | `baseline/*` | 永久保留 |
| 研究 | `research/*` | 永久保留 |

詳見 `REPO_GOVERNANCE.md` Branch Taxonomy。

### 檔案命名通則

- Markdown：`UPPER_SNAKE_CASE.md`（報告）或 `lower_snake_case.md`（README 等）
- Python：`lower_snake_case.py`（除 Model/ 以外，Model/ 用 PascalCase 前綴）
- JSON：`lower_snake_case.json` 或 `UPPER_SNAKE_CASE.json`（政策文件）
- 不在檔名中使用中文字元（目錄名可以，檔名不要）
- 新檔案絕對路徑超過 180 字元先縮短，超過 220 字元不得新增
- 單一檔名或資料夾名稱以 64 字元內為目標；完整參數與描述寫進 MANIFEST，不塞進路徑
- 不使用 `final_final`、`new_new`、`backup2`、`copy` 或 `old2` 這類身分不明名稱

---

## 2. Directory Template / 目錄結構模板

### 所有新實驗的固定核心

```
Experiments/R##_Description/
├── README.md                         # [必備] 假說、設計、結果摘要（見下方模板）
├── MANIFEST.md                       # [必備] 實驗識別與 handoff
├── scripts/
│   └── launch_r##.py                # [建議] 訓練啟動器（見下方模板）
├── reports/
│   └── R##_RESULTS.md               # [必備] 完整結果報告
└── results/
    └── ...                            # 依該輪研究內容命名
```

這五個入口是共同契約。不要預先建立不會使用的空分類。若 `results` 超過三個一級項目或 1 GiB，增加 `results/README.md`，寫清楚哪些是正式結果、代表成果、活動中輸出與 H 槽封存候選。

### 型態 A：共享主線實驗

適合沿用根層 `Model`、`Training_Data` 與 `Experiments/Training_Runs` 的實驗（`Model/` 訓練器的輸出預設寫到 `Experiments/Training_Runs/`；`Experiments/Legacy/` 是早期整理批次，不放新實驗）。該輪保留 launcher、報告與結果；共享模型和資料不複製進實驗。需要時可增加：

```text
├── tests/
└── runs/
    └── launcher_logs/
        └── active_formal_run.json
```

### 型態 B：自包含實驗

適合需要隔離完整模型架構與訓練系統的研究。除了固定核心，可以增加：

```text
├── config/                            # 鎖定設計與執行設定
├── model/                             # 本輪專屬模型
├── training/                          # 本輪專屬訓練程式
├── inference/                         # 本輪唯一推論入口
├── tests/                             # 架構與行為回歸測試
├── data/                              # payload、程序化資料或共享來源指標
├── runs/launcher_logs/                # 活動標記與執行紀錄
├── weights/                           # 活動 checkpoint 與收尾後精選權重
└── logs/                              # 只有無法合理放進 runs 時才增加
```

README 或 MANIFEST 必須聲明採用哪一種型態。若有 `data`，必須說明它是實際 payload、可重新產生的資料，還是指向共享資料；連續輪次不得因複製方便而各存一份相同大型 payload。兩輪以上確實共用時，才提升為 `Training_Data` 的共享資料。

正式工作開始前，兩種型態都要完成容量登錄並建立 `runs/launcher_logs/active_formal_run.json`。程序消失不代表完成；必須核對預定輪數、完成摘要與必要輸出後才收尾。

### README.md 模板

```markdown
# Round ## — [實驗名稱]

## 假說

[一句話描述這個實驗要驗證什麼]

## 設計

[核心機制、和先前 Round 的差異、為什麼這樣設計]

## 候選

| Tag | 關鍵參數 | 說明 |
|-----|---------|------|
| `r##_candidate_name` | PARAM=VALUE | 主候選 |

## 結果

[簡要結果摘要，詳見 reports/R##_RESULTS.md]

## 資料

- Experiment profile: `shared-mainline` 或 `self-contained`
- Training data: 實際 payload、可重建方式或共享來源與核對值
- Checkpoint: `Experiments/Legacy/.../weights/...` 或本輪 `weights/...`
- External GMF: `results/external_gmf/`（有送外部驗證時）
- Closeout: D 槽保留內容、H 槽封存候選與恢復入口

## 分支

`sandbox/r##`
```

### 共享主線 Launcher 模板

下例適用於沿用根層 `Model` 的型態 A。型態 B 使用本輪 `training` 內的唯一 launcher，但仍必須保留明確的 artifact identity，不能讓設定名稱與輸出模型名稱分離。

```python
"""Round ## — [Description] Launcher"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "Model"))

CANDIDATES = {
    "r##_candidate_name": {
        # config overrides
    },
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, choices=list(CANDIDATES.keys()))
    parser.add_argument("--num-epoch", type=int, default=100)
    parser.add_argument("--device", type=str, default="cuda:0")
    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    import GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest as trainer
    CFG = trainer.CFG
    for key, val in CANDIDATES[args.candidate].items():
        setattr(CFG, key, val)
    CFG.MODEL_NAME = f"GESR_v1_v5_ST0p8_SWP_{args.candidate}"
    trainer.MODEL_NAME_BASE = CFG.MODEL_NAME  # ensure artifact identity
    CFG.NUM_EPOCH = args.num_epoch
    CFG.DEVICE = args.device
    trainer.main()

if __name__ == "__main__":
    main()
```

---

## 3. SOP Steps / 標準作業流程

### Step 1. Choose the right branch family / 選對 branch 類型

- 新的策略嘗試、微調路線、或分析驅動的後續工作，請用 `research/*`。
  Use `research/*` for new strategy attempts, tuning lines, or analysis-driven follow-up work.
- 如果這條線需要隔離執行、且暫時不應視為 baseline 候選，請用 `sandbox/*`。
  Use `sandbox/*` for isolated execution surfaces that should not be treated as baseline candidates yet.
- **不要**把 `baseline/*` 當成新工作分支。這個命名空間只保留給已核准的 baseline 里程碑。
  Do **not** use `baseline/*` for new work. That namespace is reserved for approved baseline milestones only.

### Step 2. Create the branch / 建立分支

- 從 `main` 開始。
  Start from `main`.
- 分支名稱要能對應工作內容。
  Name the branch to match the work.
  - `research/<round-or-topic>`
  - `sandbox/<round-or-topic>`

### Step 3. Open the tracking issue / 建立追蹤 issue

- 使用既有的 issue template：
  Use the existing issue template:
  - `.github/ISSUE_TEMPLATE/research-round-proposal.yml`
- 在 issue 裡至少記錄：
  In that issue, capture the following:
  - round 或 branch 名稱 / round / branch name
  - 研究假設 / hypothesis
  - 比較對象 / comparison target
  - 成功條件 / success condition
  - 預期的 external verdict 路徑或落點 / expected external verdict path

### Step 4. Update the GitHub Project / 更新 GitHub Project

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

### Step 5. Update formal docs only when truth changes / 只有在正式真相改變時才更新核心文件

當工作跨過正式決策邊界時，再更新下列文件：
Update these docs when the work crosses a formal boundary:

- `PROJECT_STATE.md` — 當 current truth、handoff 快照、adopted baseline、或下一個決策邊界改變時
- `PROJECT_ARCHITECTURE.md` — 當穩定規則、branch policy、或治理規則改變時
- `ESTIMATOR_POLICY.json` — 當 formal baseline / alternates / closed lines 清單改變時

不要因為日常 runtime 噪音去改 canonical docs。
Do not update canonical docs for day-to-day runtime noise.

### Step 6. Open a PR / 開 Pull Request

- PR 只應包含受追蹤的 source、docs、或 governance 檔案。
  Keep the PR limited to tracked source, docs, or governance files.
- 請使用 `.github/PULL_REQUEST_TEMPLATE.md`。
  Use `.github/PULL_REQUEST_TEMPLATE.md`.

### Step 7. Trigger Codex review manually for non-trivial PRs / 對非 trivial PR 手動觸發 Codex review

只要 PR 不是很 trivial，在建立後或從 draft 轉成 ready 後，請手動留言：
For any non-trivial PR, after opening it or marking it ready for review, leave:

`@codex review`

如果 Codex 留下可執行的意見，請在同一個 PR 裡接著留言：
If Codex leaves actionable comments, follow up in the PR with:

`@codex address that feedback`

### Step 8. Merge only after the line is clear / 確認路線清楚後再合併

- `main` 與 `baseline/*` 都受保護。
  `main` and `baseline/*` are protected.
- 新實驗工作應透過 PR 合併，不要直接推進正式分支。
  New experiment work should merge through PR, not direct pushes.
- 請把 bulk artifacts、logs、weights、reconstructions、以及 runtime 噪音留在 Git 之外。
  Keep bulk artifacts, logs, weights, reconstructions, and runtime noise out of Git.

---

## 4. Combined Checklist / 整合檢查清單

新實驗建立後確認：

- [ ] 目錄格式 `Experiments/R##_Description/`（或相容的歷史例外格式）
- [ ] 已在 README 或 MANIFEST 聲明「共享主線」或「自包含」型態
- [ ] `README.md` 寫了假說與設計
- [ ] `MANIFEST.md` 已建立
- [ ] Launcher 含 `trainer.MODEL_NAME_BASE = CFG.MODEL_NAME`（確保 artifact identity）
- [ ] 正式工作開始前已在 `docs/operations/PROJECT_STORAGE_REGISTRY.json` 登記容量身分、預估容量與保留規則
- [ ] 正式訓練與每次續訓都會更新 `runs/launcher_logs/active_formal_run.json`；程序退出後先核對預定輪數、完成摘要與必要輸出，再把標記改成完成
- [ ] `data` 已聲明為 payload、可重建資料或共享來源指標，沒有無理由複製上一輪大型資料
- [ ] `results` 超過三個一級項目或 1 GiB 時已有 `results/README.md` 與 D/H 保留說明
- [ ] 新路徑沒有超過 220 字元，單一名稱以 64 字元內為目標
- [ ] 分支命名 `sandbox/r##` 或 `research/r##`
- [ ] Issue 用 `.github/ISSUE_TEMPLATE/research-round-proposal.yml` 建立
- [ ] GitHub Project `GMM Research Control Plane` 已新增 item
- [ ] 報告檔名用 `R##_TYPE.md` 格式
- [ ] 送外部 GMF 後 `results/external_gmf/` 含三尺度
- [ ] 完成後加入 `Experiments/INDEX.md`
- [ ] 更新 `PROJECT_STATE.md` 僅在 baseline / verdict / taxonomy 改變時
- [ ] PR 透過 `@codex review` 觸發非 trivial review
- [ ] **（強烈建議，非 mandatory）** 若本輪產生可展示的視覺輸出（recon 圖、指標對比圖等），在根目錄的 `RECON_GALLERY.md` 新增一個 section 收錄代表圖——demo / 會議時會省下翻 `results/` 子樹的時間
  - 格式嚴格要求**純 markdown**（`![]()`、`###`、`>` alert、pipe table、bullet list）
  - 不得引入 HTML block 標籤（`<table>`、`<tr>`、`<td>`、`<p>`、`<div>`、`<details>`、`<summary>`、`<img>`、`<a>`）
  - 違規會被 `Tools/validate_project_structure.py` 的 `check_recon_gallery_format()` 擋下，pre-commit hook 也會 fail
  - 圖表連結請用中文標籤（例如「中心軌跡」而非 `01_center_trajectory`）

以上流程需要**更新正式 docs 的時機**：只在正式真相改變時（baseline、approved alternates、side track 狀態）才更新 `PROJECT_STATE.md` 與 `ESTIMATOR_POLICY.json`。日常 runtime 噪音不要碰 canonical docs。
