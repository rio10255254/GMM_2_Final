# 交接：文件改寫與檔案樹整理（2026-10-24）

給在原本那台電腦（`D:\GMM_2_Final`）上接手的 Claude。這份是雲端 session 的工作交接：使用者要什麼、已經做了什麼、我對專案的理解、發現的問題、建議的策略，以及哪些事必須先問使用者。

> 雲端 session 只有 GitHub 上的 clone，沒有 D／H 槽、沒有 MATLAB、沒有外部 GmmVisionTool。所以凡是需要本機資料才能確認的事，都留給你。

---

## 1. 使用者要什麼（按對話順序）

1. 「專案裡有海量說明文件，因為是 Codex 寫的所以看不太懂，幫我理解整個架構並重新撰寫。」
2. 我先在 `docs/guide/` 另寫了一套新文件，使用者立刻糾正：**「我是要你完整改寫舊文件，不是要搞出一堆新的弄得更雜亂；整體文件架構由你思考安排。」** → 已撤掉 `docs/guide/`，改為直接改寫既有入口文件。
3. 「先仔細理解專案內所有內容與完整架構脈絡，思考後再規劃 GitHub 整體檔案樹架構。」
4. **最重要的一句：**「這整個專案是我過去數個月大量迭代實驗、換實驗系統、寫論文的結果，所以才會非常亂。**我不希望整理後當初的脈絡都不見了**，所以才希望你先好好理解。」
5. 「再仔細看看想想再去做行動。」
6. 現在：寫這份交接，讓本機的 Claude 接手。

**歸納：**使用者要的是「看得懂的文件」與「合理的檔案樹」，但**前提是任何歷史脈絡都不能遺失**。寧可慢、寧可少動，也不要為了整齊抹掉過去。

---

## 2. 已完成的工作

分支 `claude/vigilant-sagan-7zyae5`，草稿 PR：<https://github.com/rio10255254/GMM_2_Final/pull/47>（base `main` = `d12dd7e0`）。

| 提交 | 內容 |
|---|---|
| `94778090` | 改寫 7 份入口文件為白話版 |
| `4ed29d7a` | 7 份原文逐位元組存檔、補回文件契約測試要求的字樣、補充脈絡（公司端 vs 論文、µm↔px、四種實驗系統） |
| （本檔） | 交接文件 |

改寫後的文件分工：

| 文件 | 負責 |
|---|---|
| `README.md` | 這是什麼、結論、兩條線、去哪找 |
| `PROJECT_ARCHITECTURE.md` | 穩定設計：管線、兩代模型、評估與升級規則、保存原則 |
| `PROJECT_STATE.md` | 現況（Quick Handoff ≤60 行，validator 有檢查） |
| `docs/README.md` | 文件分工、衝突時優先順序、名詞表 |
| `docs/navigation/PROJECT_MAP.md` | 資料夾地圖 |
| `docs/reproducibility/EXPERIMENTS.md` | 四種實驗系統、八階段研究歷程、九個閱讀分區入口 |
| `Experiments/INDEX.md` | 只換掉開頭的收據堆，表格未動 |

**脈絡保全：**改寫前原文逐位元組存在 `docs/history/BEFORE_PLAIN_REWRITE_20261024/`（SHA-256 與 `d12dd7e0` 相同），每份新頁尾連回原文；`docs/history/README.md` 有入口。

**沒有動：**任何實驗資料夾、正式報告、數字、`ESTIMATOR_POLICY.json`、研究結論、採用判決、程式碼、`.gitignore`、CI 設定。

**驗證過：**
- `python Tools/validate_project_structure.py` → 0 errors, 0 warnings（`main` 上原本有 2 warnings）
- `Tools/tests/test_truth_plane_policy.py` → 3 passed（`main` 上這個測試是失敗的）
- 裝齊依賴後跑控制中心的 pytest 白名單：失敗名單與 `main` **完全相同**（25 failed / 197 passed / 1 error），沒有新增失敗
- 所有改寫頁與歷史頁的相對連結都能解析

**請你先做：**在本機確認 PR #47 的改寫內容符合事實，尤其第 3 節裡標「推斷」的地方。改寫是用 GitHub 上的檔案讀出來的，本機可能有更完整的資訊。

---

## 3. 我對專案的理解

### 3.1 核心問題
用神經網路重建顯微影像，目的**不是好看，而是讓位移、尺寸、輪廓量測更穩**。使用者 2026-03 的策略文件（`docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` §1、§19、§32）明白寫了：一開始誤把問題當成銳利度問題，後來才把「固定的外部定位工具的幾何偏好」納入問題定義。五個教訓都源於此。

### 3.2 兩條線（這是理解「為什麼有兩個目前模型」的關鍵）

| 用途 | 目前模型 | 評分方式 |
|---|---|---|
| 公司端量測部署 | **COMBO**（正式基準，2026-04-08；前任 R30） | 環形影像交給固定、不能改的外部 GmmVisionTool GMF；8／0.8／0.08 px ＝ 1／0.1／0.01 µm 三尺度 step_std。交付為 ONNX（`_deployment_package/`、`Deliverables/MOSR_ONNX*`），以均華 202 張實拍驗證（`Validations/MOSR_ONNX_JunHua/`） |
| 論文 | **R152（論文稱 MOSR）** 對 RAW | 2026-09-03 的 930 張 PI 位移重拍（30 趟 × 31 位置）、PI 回授、SEM |

`ESTIMATOR_POLICY.json` 只登記公司端那條線；論文採用另記在 `PROJECT_STATE.md` 與 R153 交接。

### 3.3 四種實驗系統（考試換了，數字不能互比）

| 系統 | 約略期間 | 代表 |
|---|---|---|
| A 公司端環形 + 外部 GMF | 2026-03～05 | R1–R45、COMBO、R39R40 |
| B 實拍樣品擴充與交付 | 約 2026-06～08 | Step、100MG、20×／5×、均華、主 R61 STEP 線、ONNX 交付 |
| C 實驗室顯微系統 LabSystem | 2026-06～07（V42 沿用到 9 月） | `Thesis_MOSR_Evidence/LabSystem_MOSR/`：Lab R39–R62、V41／V42 |
| D 9/3 PI 930 張重拍 | 2026-09～10 | R122 起的真實優先路線、R148v2 → R152、R153 十方法 |

**推斷、待本機確認：**930 張是在哪台顯微鏡上拍的（文件沒有明說）；均華在研究中的確切角色（從檔案看是提供實拍、接收 ONNX 交付的外部方）；B 系統的期間界線。

### 3.4 使用者的工作習慣（整理時必須尊重）
- **刻意保留失敗。**不採用、停止、撤回（R119）都完整留著，並寫明限制。
- **刻意保存「改動前的樣子」。**很多實驗資料夾有 `project_context_before/`、`mutable_context_before/`、`*_BEFORE_*` 檔；`.history/` 是**刻意追蹤**的編輯器快照（提交 `36f1c917`）。不要取消追蹤。
- **嚴格區分身分。**原拍、處理輸入、合成資料、模型輸出、量測座標各有名稱；best／latest／EMA 不互換；同號不同系統（主 R39 ≠ Lab R39；V42 ≠ R42；stage01–33 是資料類型）。
- **限制句是結論的一部分。**「重拍穩定不等於準確」「同樣本 SEM 只算一致性檢查」等句子不可刪。
- 9 月的設計回顧 `Thesis_MOSR_Evidence/Research_Design_Effect_Review_20260926/05_Cross_Round_Analysis/`（DESIGN_EVOLUTION、FAILURE_PATTERNS、RECOMMENDATIONS）是使用者自己的判斷整理，價值很高，只能加索引，不能改。

### 3.5 git 歷史的限制
GitHub 上的 git 歷史只有約 75 個提交，最早是 2026-04-14。**2026-03 及更早的脈絡只存在檔案內容**；刪除或覆寫而不留副本，就無法從 git 找回。本機的原始工作分支、索引、H 槽封存可能有更多，PROJECT_STATE 提到「原 D 工作分支／索引保護」。

---

## 4. 發現的問題（附證據）

| # | 問題 | 證據 | 影響 |
|---|---|---|---|
| 1 | 入口文件幾乎都是保存流水帳 | 舊 `PROJECT_STATE.md` 約 16 萬字，大多是 10-16～10-22 的補件／取回／清理收據 | 已改寫，原文已存檔 |
| 2 | `docs/reproducibility/` 混了兩種東西 | 877 檔；研究閱讀（lineage、177 張閱讀卡、各 GUIDE）和保存收據（`project_completion/` 282 檔、`round_source_*`、`priority_sources_*`、`verification/`…）放在一起 | 讀者分不出什麼可略過 |
| 3 | 根目錄約 37 項、角色混雜 | 程式、實驗、證據、日期型分析、7 個封存／底線資料夾、`trial_README.md` 並列 | 看不出結構 |
| 4 | `Thesis_MOSR_Evidence/` 是雜物間 | `LabSystem_MOSR` 1,717 檔（自帶 Experiments／Traing_Progress／Model_Packages，等於第二個專案）；另有 20 多個子資料夾，部分只是早期設想（如 `visual_vs_metric_decoupling` 1 檔） | 看不出哪些是實質證據 |
| 5 | **路徑高度寫死** | `git grep` 統計：1,109 個程式／設定檔含 `D:\GMM_2_Final`；約 800 個提到 `Traing_Progress`／`PSF_Fitting`／`Training_Data`；514 個提到 `Thesis_MOSR_Evidence`；日期型分析資料夾各有 160–170 個外部引用 | **大規模搬動會同時弄壞程式、報告、還原工具與已發布核對紀錄** |
| 6 | CI 從 2026-04-18 起每次都紅 | `Validate Governance` 跑 `project_control_center.py --view health --health-level standard`；(a) `AnalysisLab/index.json` 從未被提交（`git log --all` 查無；README、`AnalysisLab/tests/test_analysis_lab_layout.py`、控制中心都要它）；(b) workflow 只裝 pytest，但檢查要 torch、torchmetrics、cv2、pandas、requests、nbformat；(c) 白名單測試有 25 failed + 1 error，全是寫死 `D:\GMM_2_Final` 或只在本機存在的檔案 | GitHub runner 上**不可能變綠**；它實際上是「本機健康檢查」 |
| 7 | 3 月策略史有控制字元 | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` 有 20 個控制字元（13 個 NUL、`\x08`、`\x1b`），grep 把它當二進位。成因是 PowerShell 雙引號字串吃掉反引號：`` `0 ``→NUL、`` `b ``→退格、`` `e ``→ESC。反推可還原，例如 `` `0.8px` ``、`` `be_soft_band_refine` ``、`` `edge_centroid` ``（`be_soft_band` 是確實存在的候選名）。從 GitHub 第一個提交 `04cd52ba` 起就是壞的 | 使用者最重要的敘事文件之一，閱讀時有缺字 |
| 8 | GMF、MOSR 沒有統一定義 | GMF 全名在檔案中有 Geometric Matching Feature／Function、Gaussian Mixture Field 三種；MOSR 沒有全名 | 名詞表已照實標註 |
| 9 | 同批資料不同口徑的數字 | R152 紀錄 RAW 10.200 nm（九顆取中位數），R153 表 RAW 8.781 nm（算術平均） | 已在文件中說明不可跨表比 |

---

## 5. 硬規則（整理時不可違反）

1. **不刪檔，不改寫原報告與當時的敘事。**只能加導讀，或搬動並留位置對照。
2. **任何搬動都要有 `舊路徑 → 新路徑` 帳本**，舊位置留 README 指路，並用腳本改寫所有引用。改完跑連結檢查器與 `validate_project_structure.py`。
3. **不動寫死路徑的區域：**`Experiments/`、`Model/`、`PSF_Fitting/`、`Training_Data/`、`Traing_Progress/`（拼字是歷史，不可改名）、`Thesis_MOSR_Evidence/`、日期型分析資料夾。
4. **研究保存檔保留原始位元組**（PROJECT_ARCHITECTURE §6；`.gitattributes`）。修正第 4 節 #7 這類問題前必須問使用者。
5. 遵守 `CLAUDE.md`／`AGENTS.md`、`docs/operations/SOURCE_OF_TRUTH_POLICY.md`、`docs/operations/QUIRKS.md`。各輪正式報告只在該輪 `reports/` 編輯。
6. 不改 `ESTIMATOR_POLICY.json` 的身分；不啟動訓練或推論；不清 D／H 槽（除非使用者當次明確授權）。
7. `CLAUDE.md` 與 `AGENTS.md` 要保持同步（validator Check 4）。
8. 提交與 PR 不要寫入模型名稱或版本。

---

## 6. 建議策略（按順序，每步一個 PR）

本機的優勢：D／H 槽可讀，可以真的跑控制中心、MATLAB smoke test、外部工具，也可以找回從未提交的檔案。

### 步驟 0：先對齊本機狀態（不要跳過）
- `git status`、`git log`：確認本機 `main` 與 GitHub 的 `d12dd7e0` 是否一致，有沒有未推送或未提交的工作。**本機若有未提交的變更，不要覆蓋。**
- 把 PR #47 拉下來讀：`git fetch origin claude/vigilant-sagan-7zyae5`。在本機核對第 3 節的推斷。

### 步驟 1：CI（需使用者決定方向）
- 在本機找原本的 `AnalysisLab/index.json`（D 槽工作區、H 封存）。找得到就提交原檔；找不到，README 第 89 行與 `test_analysis_lab_layout.py` 定義了它的結構，可依此重建（要標明是重建的）。雲端曾依此暫時重建並驗證 `docs` 模組可通過，但沒有提交。
- 讓使用者二選一：
  - (a) CI 改成 GitHub runner 能跑的部分：`validate_project_structure.py`、`Tools/tests/test_truth_plane_policy.py`、`AnalysisLab/tests`。完整 standard health 留給本機。**建議這個。**
  - (b) 維持現狀，當本機健康檢查用。

  不要用跳過或停用測試的方式讓 CI 變綠。

### 步驟 2：Tier 1，只加導覽，不動路徑
- 每個根資料夾 README 開頭加一行：屬於哪個系統（A–D）、角色（程式／實驗／原始資料／證據／分析／交付／封存），以及「日常需不需要打開」。
- `Thesis_MOSR_Evidence/README.md` 標明哪些子資料夾是實質證據、哪些是早期設想或已取代（如 `Archive/`、`Research_Round_Library_20260926_ABORTED_OVERSIZED/`）。
- `docs/reproducibility/README.md` 把子資料夾分成「研究閱讀」與「保存收據（可略過）」兩欄，先不搬。

### 步驟 3：Tier 2，搬低耦合封存區（需使用者點頭）
- 候選：`Historical_Archive`（外部引用 12）、`Project_Archive`（13）、`Trash_Archive`（5）、`_MOSR_Project_Archive_20260624`（8）、`_portable_env_sim_20260318`（5）、`_build153`（5）→ 新的 `archive/`。數字是 `git grep -lF <名稱>` 在該資料夾外的檔案數。
- 注意：其中幾個在 `.gitignore` 但有被追蹤的檔案，搬動時要一併調整 `.gitignore` 與 `research_preservation_exclusions.py` 之類的工具。另外先查 `Tools/restore_*`、`*_MANIFEST.json`、各種 `*VERIFIED*.json` 是否以路徑登記這些檔案；有的話要同步，或乾脆不搬。
- `trial_README.md` 的去處先問使用者（它是單一模型試用入口）。

### 步驟 4：Tier 3，docs 分「研究」與「保存」（需使用者點頭）
- `docs/reproducibility/` 拆成研究閱讀與保存收據兩區。引用數以百計，要用腳本改寫並逐一驗證。`Tools/build_research_recovery.py`、`build_project_restore_index.py`、`project_reproducibility_audit.py` 會讀 `docs/reproducibility/experiment_index.json` 等固定路徑，必須一起改，並在本機實跑。

### 不建議做的
- 大幅重排程式與實驗（例如 `src/`、`data/` 化）：路徑寫死的數量太多，風險遠大於收益。
- 把日期型分析資料夾搬進 `analyses/`：外部引用 170+，用 Tier 1 的導覽解決即可。

---

## 7. 待使用者決定（雲端已問過，尚未得到答覆）

1. CI 要選 6-步驟1 的 (a) 還是 (b)？
2. 3 月策略史的控制字元：原地修正，還是保留原檔、旁邊放一份修好的閱讀版？
3. 整理範圍：先只做 Tier 1？Tier 2／3 要不要做？
4. 3 月以前還有沒有存在 repo 以外的重要紀錄（E 槽 GMM_Software、H 封存、其他電腦），需要一起處理？
5. 有沒有絕對不能動的文件或資料夾，要加進硬規則？

---

## 8. 常用驗證指令

```powershell
python Tools/validate_project_structure.py
python -m pytest -q Tools/tests/test_truth_plane_policy.py AnalysisLab/tests
python Tools/project_control_center.py --view health --health-level standard
```

連結檢查：雲端用一段小腳本掃 markdown 的 `](相對路徑)` 並確認目標存在，沒有存成檔案；需要時可放進 `Tools/`，前提是之後會重複使用。

PR #47 已訂閱 GitHub 事件。之後若在本機推送到同一分支，CI 的結果仍會通知到雲端 session。
