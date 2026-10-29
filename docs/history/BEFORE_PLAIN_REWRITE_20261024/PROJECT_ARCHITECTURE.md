# PROJECT ARCHITECTURE / 專案架構與決策地圖
Last updated: 2026-10-21

## 研究保存邊界（2026-10-21）

GitHub保存須包含理解與重做研究所需的實際來源、方法、模型、完整數字、重要影像及失敗脈絡。一般Git歷史與大型版本附件分工，內容核對與實際取回重做分別記錄；索引存在或H槽備份存在均不能代替GitHub驗證。無法精確重做的歷史輸入保存原檔，生成程式與種子本身不構成完整重做證據。

相同內容可集中保存，但須保留原用途、來源關係與可恢復的位置；複製品不增加獨立證據。不同歷史版本不覆蓋正式來源。原論文與活動訓練受保護，本輪GitHub整理不授權D槽清理，也不改變COMBO或論文採用身分。[保存與取回](docs/reproducibility/README.md)／[全內容核對](docs/reproducibility/project_completion/README.md)。

影像的儲存分類不能當成相機原拍證據。已查明用途按原位置及內容身分綁定原設計／生成紀錄；同名但不同內容不能繼承該用途。衍生裁切、數學平移、訓練品質預覽與模型輸出分開標示，重複區域不增加獨立拍攝數；原圖與較早分類留歷史。[用途證據](docs/reproducibility/project_completion/IMAGE_ROLE_EVIDENCE_20261021.json)。

目前專案內指向H槽的資料入口，須按其當前指向保留可恢復位置；不能只因實體資料位於H槽就當作較舊版本。較舊快照、現在工作來源與GitHub舊版若同名而不同，分別保存並明確列出來源，不能靠掃描順序決定覆蓋。

## 目前 MOSR 論文研究的驗證優先順序（2026-09-08）

依使用者指定，下一代模型每個短候選即以真實顯微影像與 SEM 對照、真實位移序列及真實困難結構作主要開發驗證。合成資料可作訓練與實作檢查，不能作為先贏合成才准看真實的選模關卡。SEM 材料幾何、光學細節與實際位移的答案資格分開；指標矛盾不能挑有利讀法，既有樣品不能重新命名為未見確認。正式 COMBO／approved alternates 的外部 GMF 升級規則仍屬下述正式使用路線。完整契約見 [R123 真實優先設計](Experiments/R123_RealFirstModelDesign/reports/R123_DATA_AND_VALIDATION.md)。

## 這份文件的用途 / Purpose

這份文件記錄**穩定不變的架構設計與決策規則**，它回答五個核心問題：

1. 這個系統真正的最終目標是什麼？
2. 外部真值（external truth）和內部代理指標（internal surrogate）的關係是什麼？
3. 目前正式 baseline policy 是哪份模型、哪個設定？
4. PSF（點擴散函數）在整個系統中扮演什麼角色？架構邊界怎麼劃分？
5. 什麼情況下才值得立新 round？升級 baseline 需要滿足哪些條件？

**這份文件不負責的事**：展開當前 round 的逐步進度、記錄即時執行狀態、或作為跨入口交接用途。那些事由 `PROJECT_STATE.md`（含 Quick Handoff 區與 Full Current State 區）負責。

This document records **stable architectural design and decision rules**. It answers five core questions: what the true system goal is; how external truth relates to internal surrogates; what the current baseline policy is; what role PSF plays and where the architecture boundaries are; and when a new round is worth starting or a baseline is worth promoting.

---

## Layer A — 外部真值 / External Truth

### 最終衡量標準是什麼

正式 baseline 與量測替代候選的最終真值**永遠只有一個**：外部 GMF 工具在 whole-annulus 真實資料上對模型輸出的幾何定位評分。

白話說：把訓練好的模型拿去重建真實顯微鏡影像，再用外部 GMF（幾何匹配函數）工具測量「重建後的影像，在三種不同位移尺度下，定位環形邊界的穩定度有多高」。分數越好（step std 越小），代表模型越有用。

The final truth is always the external GMF's whole-annulus geometric localization score on real-world data. In plain terms: take the trained model, reconstruct real microscope images, then measure with an external Geometric Matching Function (GMF) tool how stably the model's output localizes the annulus boundary across three displacement scales.

### 顯微結構通用目標與環形代理

專案真正關心的長期能力不是「只把環形重建好」，而是模型遇到各種顯微結構時，都能忠實重建邊界位置與細節：線條、格線、曲線、晶片區塊、缺口、刮痕、亮暗點、紋理與混合場景都算在內。

目前外部 GMF 仍以環形資料作為正式守門，原因是它有穩定的真實資料、連續位移序列與長期可比較的歷史數字。也就是說，環形 GMF 是正式量測流程的代理測試，不等於專案全部科學目標。R39-R43 的定位就是在不動正式 baseline 的前提下，探索通用顯微邊界忠實度。

### 外部 GMF 真正優化的是什麼

| 評估面向 | 說明 |
|---------|------|
| whole-annulus 幾何支撐 | 整個環形邊界都能被穩定定位，不只是局部清晰 |
| absolute center stability | 中心位置的絕對誤差穩定 |
| pairwise step geometry | 連續幀之間位移的幾何一致性 |
| sign monotonicity | 方向符號在連續幀中保持單調 |

### 關鍵原則

- 外部 GMF **不直接在乎**視覺上「看起來清晰」。一張圖視覺上銳利，不等於幾何定位更準。
- Internal 稽核的通過結果**不能替代** external GMF 的最終裁決。Internal 只是入場資格，external 才是最終判斷。

---

## Layer B — 內部代理指標 / Internal Surrogates

### 什麼是 surrogate

Internal surrogate 是代理工具——它們可以在不跑外部 GMF 的情況下，快速篩選出有潛力的模型，或測試單一技術假說是否成立。但它們不是 external GMF 的替代品。

Internal surrogates are proxies for rapid candidate filtering and hypothesis testing. They are not substitutes for the external GMF final gate.

### 目前穩定存在的 surrogate 類型

| 類型 | 說明 | 適合用途 |
|------|------|---------|
| `seq_val` | 訓練期間即時序列驗證分數 | 訓練早期快速淘汰 |
| `ann_seq` | annulus 序列追蹤分數 | 模型選取初篩 |
| full deploy audit | 完整 deploy 稽核（候選整批評估） | 選 deploy candidate |
| process-audit harness | 以合成資料探針驗證單一技術假說 | 驗證機制假說是否成立 |
| estimator benchmark | 比較不同 estimator（edge_centroid / pairmix_algblend / edge_band_refine） | 估測器選取 |
| pairwise delta probe | 驗證 pairmix_algblend 在 0.8px 主戰場的表現 | 驗證 pairmix 主線 |
| GMF residual / anchor autocorr analysis | 分析 GMF residual 與 anchor 自相關 | 診斷工具 |
| internal-external correlation analysis | 找哪個 internal 指標最能預測 external 結果 | 改善 surrogate 品質 |

### 穩定解讀原則

- **full deploy audit** → 選 deploy candidate，不是判定升級資格
- **process-audit harness** → 驗證特定技術機制假說（例如「B1 dironly 是否有效」）
- **pairwise delta probe** → 驗證 pairmix_algblend 主線是否維持優勢
- **internal-external correlation（center_err）** → 找更好的 screening 指標，不可用來取代 external 驗收
- **任何 surrogate 都只是篩選工具**，通過 internal gate 是進入 external 驗收的必要條件，但絕不是充分條件

---

## Layer C — 目前優化目標 / Current Optimization Target

目前真正的主要優化目標已收斂為三件事：

1. **維持正式 baseline `COMBO / r38v2_8px_gate_p95` 的平衡優勢**
2. **在 deployment-specific 需求下，明確區分 formal baseline 與 approved alternates（R33 / R38v2）**
3. **只在有新機制或新部署條件**時才開新 round，不做已完成 promotion 決策的重複掃描

The current optimization target is narrow and practical: preserve the balanced advantage of the formal COMBO baseline, keep the alternate taxonomy explicit for deployment-specific needs, and only open new rounds when there is a genuinely new mechanism or deployment requirement.

研究層面另有一條已確認方向：通用顯微結構邊界忠實度。這條線可以允許環形代理測試出現有限退步來換取多特徵能力，但若要進入正式量測替代，仍必須回到外部 GMF 與專案 owner 的升級判斷。

---

## Layer D — PSF 角色與架構邊界 / PSF Role and Architecture Boundary

### PSF 在系統中的地位

PSF（點擴散函數，Point Spread Function）描述顯微鏡對一個極小光點成像時的模糊形狀，是整個系統物理先驗（physics prior）的唯一來源。

整個 pipeline 的依賴關係如下：

```
PSF 擬合（MATLAB）
    ↓  PSF_fitted_2D_FOVstack.mat
模型訓練（Python）  ← PSF 注入物理反捲積層（PSFDeconvPhysics）
    ↓  best_tradeoff.pth.tar
外部 GMF 比較（最終裁判）
```

PSF 的準確性直接影響模型訓練品質。Whole-FOV PSF（全視野 100 個格點位置的 PSF 集合）比單張版更能反映真實顯微鏡的位置相依光學像差。

### PSF 政策（2026-03-27 切換）

自 2026-03-27 起，R26 研究線的 PSF 政策如下：

| 身份 | 說明 | 後續處理 |
|------|------|---------|
| **current standard**（新 PSF） | 2026-03-26 完成的 Whole-FOV PSF；物理上更合理；已驗證 same-recipe 下不引發崩壞 | 作為目前研究採用的正式 PSF；對應 same-recipe replacement checkpoint |
| **legacy empirical baseline**（舊 PSF） | 歷史上取得較好經驗數值的舊版；物理合理性較低 | 保留用於歷史報告引用與對照，不刪除，不再作為正式預設 |

**切換理由**：
- 新舊 PSF 的差異主要是對齊語意，不是模糊核變寬
- 先前「新 PSF 重訓崩壞」的根因是 PSF 變更 + recipe drift 共同造成，而不是純 PSF 因子
- pure_psf_control 實驗已確認 old_recipe + new_psf 到 epoch 40 沒有重現崩壞
- physics-first 原則下，較合理的物理 PSF 應成為目前標準

**機器可讀 PSF 政策**：`docs/policy/PSF_STANDARD_POLICY.json`

### 注意事項

- 不應再把舊 PSF 寫成唯一正式標準
- 不應寫成新 PSF 已在所有 downstream 指標都更好（尚有待外部 GMF 結果確認）
- slight regression 若未構成 clear breakage，視為政策切換成本，不自動回退
- 舊 baseline 必須保留，不得刪除

---

## 穩定架構邊界 / Stable Architecture Boundary

從 2026-03-20 起，這個 repo 的穩定架構邊界明確分成三層：

### Root Shared Mainline（根目錄共用主線）

**維護範圍**：R26 / R30 的穩定工作流程，包含訓練、推論、稽核、外部比較腳本

**不再吸收**：R32 專用 loader / audit / launcher / monitor；任何實驗性的沙盒修改

核心 artifact 清單：

| 檔案 | 功能 |
|------|------|
| `Model/GeoEdgeAlignSR_v1_ModelA_v5_NoCoord.py` | 模型定義（U-Net + PSFDeconvPhysics + WeakPSFDeconvBlock） |
| `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py` | 標準訓練入口 |
| `Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py` | 超參數自動掃描訓練 |
| `Model/GeoEdgeAlignSR_v1_LongRunRound*.py` | 長跑訓練流程 |
| `Model/GeoEdgeAlignSR_v1_ProcessProbeAudit.py` | 內部探針稽核 |
| `Model/GeoEdgeAlignSR_v1_ExternalGMF*.py` | 外部 GMF 比較腳本群 |
| `PSF_Fitting/HDR_fitting_2D_WholeFOV.m` | 正式 Whole-FOV PSF 擬合入口 |
| `PSF_Fitting/Crop_circle_FreqFiltered/Fits/PSF_fitted_2D_FOVstack.mat` | 正式 PSF 輸出 |

### R32 Sandbox（已關閉）

**位置**：`Experiments/R32Sandbox/`

**狀態**：external FAIL 已確認（2026-03-20），沙盒已關閉

**存在意義**：保留 R32 完整的實驗鏈（訓練、稽核、外部比較報告），供日後引用與學習

R32 sandbox-specific artifact 清單：

| 檔案 | 功能 |
|------|------|
| `Experiments/R32Sandbox/Model/train_r32.py` | R32 訓練引擎 |
| `Experiments/R32Sandbox/Model/autotune_r32.py` | R32 自動掃描 |
| `Experiments/R32Sandbox/Model/process_probe_audit_r32.py` | R32 稽核器 |
| `Experiments/R32Sandbox/Model/longrun_round32.py` | R32 端到端流程 |
| `Experiments/R32Sandbox/Model/external_gmf_round32_compare.py` | R32 外部比較腳本 |
| `Experiments/R32Sandbox/runtime/R32_STATUS.md` | R32 runtime 最終狀態（human-readable） |
| `Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md` | R32 外部比較最終報告 |

### R26NewPSFCheck Side Track（開放中，但非主線）

**位置**：`Experiments/R26NewPSFCheck/`

**狀態**：2026-03-26 啟動，外部 GMF 結果等待中；保留為 open side track

**研究問題**：
1. 使用 2026-03-26 新 Whole-FOV PSF 從頭重訓的模型，效果是否優於舊版 R26 封包？
2. `PSF_Fitting/` 正式流程是否有執行層面的問題？

**注意**：本 sandbox 的 PSF 政策（current standard / legacy baseline 切換）已在 2026-03-27 正式決定，詳見 `docs/policy/PSF_POLICY_TRANSITION_R26.md`。

---

## 目前 Baseline

當前正式 baseline 名稱、數字、checkpoint 路徑以 `ESTIMATOR_POLICY.json` 與 `PROJECT_STATE.md` 為準。本檔只保留穩定規則。

---

## Layer E — 容量與歷史保存 / Storage Lifecycle

專案資料固定分成四層：活動中、正式保留、歷史封存、可重建內容。

- 活動中工作不可移動、改名或刪除，必須同時檢查活動標記與實際程序。
- 正式訓練、續訓、長時間重建與大量資料產生必須在啟動前登記目前程序；程序退出後要先核對預定工作與輸出完整性，才能解除大型整理阻擋。
- 正式 baseline、核准替代模型、原始影像、正式 PSF、論文採用證據及其來源數據永久保護。
- 已完成或失敗的實驗保留正式報告、manifest、採用權重、代表圖、原始輸入位置與重做方法；完整過程可在驗證後移到外部封存。
- 測試快取、臨時渲染與可重建候選輸出只有在沒有程序使用、正式替代品存在且重做條件完整時才能刪除。
- 外部封存必須先建立含雜湊值的清單，複製後驗證通過，再另外確認原工作區的刪除目標。
- D 槽剩餘容量低於 300 GiB 進入警告；低於 150 GiB 時不開始新的長訓練。

完整規則與巡檢入口見 `docs/operations/PROJECT_STORAGE_AND_ARCHIVE_POLICY.md`。

---

## 已確認結論

當前已確認的有效方向、被否定方向、與注意事項（caution）以 `PROJECT_STATE.md` §§2-6 與 `ESTIMATOR_POLICY.json` `notes` 欄位為準。本檔只保留方法論層面的穩定規則。

---

## 決策規則 / Decision Rules

### Baseline 採納規則（必須同時滿足）

只有**同時**滿足以下四個條件，才允許升級 current adopted baseline：

| 條件 | 細節 |
|------|------|
| **1. Internal calibrated gate 通過** | pairmix_algblend 探針：`mid_center ratio > 0.25` 且 `mid_step < 0.45`；edge_band_refine 探針：`macro_step < 0.2995` 且 `macro_seq_sign > 0.7559` |
| **2. External 0.8px 硬邊界** | `external 0.8px step std < current formal baseline 0.131560`，或在 deployment-specific 條件下提出明確 alternate-selection 理由 |
| **3. 8px macro guard 不明顯退步** | 大尺度追蹤穩定性不能為了換主戰場而犧牲 |
| **4. Side-scale trade-off 需有工程理由** | `0.08px` 改善不能補償 `0.8px` 主戰場退步 |

### 新 Round 立案規則

**值得立案的情況**：
- 有一個和現有失敗分支**不同**的新機制假說（例如：全新架構組件、不同訓練信號來源）
- 在既有成功主線上做**可驗證且成本合理**的微調
- 比較對象明確包含現 baseline
- 預期挑戰現 baseline 的 0.8px 硬邊界

**不應立案的情況**：
- 重掃已否定的 `step_mag < 0.35` 或 `> 0.35` 範圍
- 重開 Round23/24 型 fine-tune abs/anchor branch
- 只靠 internal gate 就預設 external 會變好
- 延用已 external FAIL 的方向（如 `r32_real_eq_finetune`）做修補

### 硬邊界（截至 2026-04-09）

```
任何候選要升級 baseline，必須：
  external 0.8px step std < 0.131560
```

這個數字只有在新 baseline 被正式採納後才會更新。

---

## 真相來源導覽

見 `docs/README.md` 與 `docs/operations/PROJECT_CONTROL_CENTER.md`。

## 共用來源與GitHub研究保存（2026-10-16）

共用相機與儀器原件、SEM及固定光學來源依內容核對值集中保存一次；各輪仍保留原檔名、用途、分組、實際模型與完整結果的對應。大型必要來源及固定模型隨私人GitHub版本附件保存，一般倉庫保留方法、索引、完整表格及代表性比較影像。

原始拍攝、裁切或轉換、凍結生成資料、模型重建、後來恢復的副本分別標示；相同內容不抹去取得來源。附件恢復須核對完整檔案內容，任何已有的不同檔案不能覆蓋。

研究保存檔保留原始位元組，不在Git存取時自動轉換換行，以維持既有來源鎖與全檔案核對。這項存放規則不變更正式基準、採用身分或科學指標。逐輪入口與驗證見[研究保存](docs/reproducibility/README.md)。
