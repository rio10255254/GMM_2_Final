# PROJECT ARCHITECTURE / 專案架構與決策地圖
Last updated: 2026-04-09

## 這份文件的用途 / Purpose

這份文件記錄**穩定不變的架構設計與決策規則**，它回答五個核心問題：

1. 這個系統真正的最終目標是什麼？
2. 外部真值（external truth）和內部代理指標（internal surrogate）的關係是什麼？
3. 目前正式 baseline policy 是哪份模型、哪個設定？
4. PSF（點擴散函數）在整個系統中扮演什麼角色？架構邊界怎麼劃分？
5. 什麼情況下才值得立新 round？升級 baseline 需要滿足哪些條件？

**這份文件不負責的事**：展開當前 round 的逐步進度、記錄即時執行狀態、或作為跨入口交接用途。那些事分別由 `PROJECT_CURRENT_STATE.md` 和 `PROJECT_SESSION_CONTINUITY.md` 負責。

This document records **stable architectural design and decision rules**. It answers five core questions: what the true system goal is; how external truth relates to internal surrogates; what the current baseline policy is; what role PSF plays and where the architecture boundaries are; and when a new round is worth starting or a baseline is worth promoting.

---

## Layer A — 外部真值 / External Truth

### 最終衡量標準是什麼

最終真值**永遠只有一個**：外部 GMF 工具在 whole-annulus 真實資料上對模型輸出的幾何定位評分。

白話說：把訓練好的模型拿去重建真實顯微鏡影像，再用外部 GMF（幾何匹配函數）工具測量「重建後的影像，在三種不同位移尺度下，定位環形邊界的穩定度有多高」。分數越好（step std 越小），代表模型越有用。

The final truth is always the external GMF's whole-annulus geometric localization score on real-world data. In plain terms: take the trained model, reconstruct real microscope images, then measure with an external Geometric Matching Function (GMF) tool how stably the model's output localizes the annulus boundary across three displacement scales.

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

**機器可讀 PSF 政策**：`D:\GMM_2_Final\docs\policy\PSF_STANDARD_POLICY.json`

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

## 目前正式 Baseline Policy / Current Baseline Policy

### 正式 production baseline

| 欄位 | 值 |
|------|-----|
| **Baseline 名稱** | `COMBO / r38v2_8px_gate_p95` |
| **Baseline 狀態** | `formal_production_baseline` |
| **0.08px 估測器** | `edge_centroid` |
| **0.8px 估測器** | `pairmix_algblend` |
| **8px 估測器** | `edge_band_refine` |
| **External 8px step std** | `0.154515` |
| **External 0.8px step std** | `0.131560` |
| **External 0.08px step std** | `0.099891` |
| **0.8px lag-1 autocorr** | `-0.5176` |
| **Role** | `most_balanced_formal_baseline` |

### 機器可讀 baseline truth

**唯一機器可讀來源**：`D:\GMM_2_Final\ESTIMATOR_POLICY.json`

所有文件、對話、自動化腳本在引用 baseline 數字時，最終以 `ESTIMATOR_POLICY.json` 為準。

### Baseline checkpoint 路徑

```
D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\
        weights\best_tradeoff.pth.tar
```

---

## 已確認結論 / Confirmed Findings

### 已確認有效的方向

| 結論 | 支持來源 |
|------|---------|
| `pairwise delta reconciliation` 是有效方向 | 多 round 持續支持 |
| `pairmix_algblend` 是 0.8px 主戰場最佳估測器 | Round 25/26/30 外部 GMF 支持 |
| `COMBO / r38v2_8px_gate_p95` 是 current formal production baseline | COMBO 結果 + promotion decision |
| `R33 / r33_robust_p95` 是 GMF extreme approved alternate | R33 外部比較確認 |
| `R38v2 / r38v2_8px_gate` 是 visual-priority approved alternate | R38v2 外部比較確認 |
| `B1 dironly` 機制（只保留方向性特徵）有效 | Round30 外部比較確認，首次擊敗 R26 |
| `Winsorize spatial loss` 機制有效（R33） | Round33 外部比較確認：0.8px -29%、8px -25%、0.08px -45% |
| `r33_robust_p95` 是首個在三尺度全面改善的候選 | 2026-04-05 外部 GMF 確認 |
| `Seq training with signal gate + warmup` 機制有效（R38v2） | 均衡型候選：GMF -20% + steepness +89%。2026-04-07 外部 GMF 確認 |
| R38v2 的三重修復（warmup + gate + 8px-only）是 seq training 成功的必要條件 | R38 原版（無修復）失敗；三者缺一不可 |
| 推理量化方式（截斷 vs 四捨五入）對 GMF 有可測量影響 | 修正後 R33 0.8px -1.7%（改善）、R38v2 0.8px +9.3%（退步）；steep edge 對量化更敏感 |
| COMBO（Winsorize + seq）的 residual_std 是所有候選中最低 | 0.8px inner 2.044（-29% vs R30）；低 residual 讓 GMF edgel detection 更精確 |
| Winsorize + seq training 可以同時使用且互補 | COMBO 在 0.8px 打敗純 R38v2（0.132 vs 0.134），同時保持 R38v2 的視覺品質 |
| **Internal step_std 不再適合作為硬門檻**（residual < 2.5 時） | Circle-fit 噪聲地板 ~0.17 px 主導 internal；COMBO internal 0.178 > 門檻 0.168 但 external 0.132 大幅通過。詳見分析報告。 |
| Circle-fit 精度是目前的量測瓶頸，不是模型品質 | 720-angle 已驗證可改善；weighted fit 可用但不是統一預設 |
| `center_err` 是目前最有價值的 Tier-2 screening 指標 | 內外部相關分析（Pearson r=0.5399） |
| 新 Whole-FOV PSF（2026-03-26）是目前物理上較合理的標準 | PSF_POLICY_TRANSITION_R26.md，pure_psf_control 驗證 |

### 已確認被否定的方向

| 結論 | 說明 |
|------|------|
| `step_mag < 0.35` downsweep | 無法改善 R26 |
| `step_mag > 0.35` upper sweep | Round29 確認，`r29_sm042` external 0.8px = 0.21731，不如 R30 |
| `TTA C2`（Test-Time Augmentation） | `r26_tta_cross5` 在主戰場 0.8px 退步 |
| `A1 / A5 / S1` side-direction | 均未擊敗 B1 dironly |
| Round31 B1 hyperparam 微調（全部） | 三個候選外部 0.8px 全部退步（+6.8% ~ +10.5%） |
| `R32 sandbox r32_real_eq_finetune` | 外部 0.8px 惡化 +97.7%，FAIL |

### 已確認的注意事項（Caution）

| 注意事項 | 原因 |
|---------|------|
| Internal gate 是必要條件，不是充分條件 | R32 全過 internal 但 external 大失敗即為反例 |
| `step_err` 不能單獨預測 external GMF | 相關分析顯示 Pearson r = -0.3251，預測力弱 |
| `center_err` 雖是目前最佳 Tier-2 predictor，但不能替代 external | Pearson r = 0.5399，樣本 n=5，僅供初篩 |
| 缺 artifact 的候選不能被硬寫成 external verdict | `r31_eq_combo` 案例：artifact missing ≠ measured regression |
| External final gate 仍然是 whole-annulus GMF | Sandbox 化不改變這個原則 |
| 內外部��分布差異可導致 internal pass / external fail | R32 案例；但 R33 證明合理的 loss 調整可以 internal/external 同步改善 |
| R33 lag-1 autocorrelation 翻轉為負值（-0.55） | 步伐交替震盪模式；step_std 已達標但趨勢形態不同於 R30（+0.27） |
| R33 視覺銳度退步但 GMF 定位改善 | gradient magnitude -32%、Laplacian -47%、對比度 -24%；更柔的邊界在幀間更一致，GMF 在乎位置穩定而非邊緣銳度 |

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

## 真相來源導覽 / Source of Truth Map

| 問題 | 去看哪份文件 |
|------|------------|
| 我現在要快速接手，先讀什麼？ | `PROJECT_SESSION_CONTINUITY.md` |
| 現在的數字和結論是什麼？ | `PROJECT_CURRENT_STATE.md` |
| 穩定架構規則和決策邊界是什麼？ | **這份文件**（`PROJECT_ARCHITECTURE.md`） |
| 機器可讀的 baseline policy 在哪？ | `ESTIMATOR_POLICY.json` |
| PSF 政策切換的細節？ | `docs/policy/PSF_POLICY_TRANSITION_R26.md` |
| 機器可讀的 PSF policy？ | `docs/policy/PSF_STANDARD_POLICY.json` |
| 完整研究歷史敘事？ | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` |
| R32 完整實驗記錄？ | `Experiments/R32Sandbox/README.md` |
| R26 新 PSF 驗證沙盒現況？ | `Experiments/R26NewPSFCheck/README.md` |
| 研究路徑圖與里程碑演進？ | `docs/analysis/RESEARCH_PATHS.md` |
| 完整歷史敘事（策略脈絡）？ | `docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md` |

### 各文件的責任邊界（白話版）

- **`PROJECT_SESSION_CONTINUITY.md`**：你接手一個 session 時最先讀的。它給你三分鐘的快照——現在 baseline 是誰、最近的 verdict 是什麼、有哪些工作規則不能搞錯。

- **`PROJECT_CURRENT_STATE.md`**：現況細節的完整清單。有表格、有數字、有正式入口路徑。比 session continuity 更完整，但不定義規則。

- **這份文件**：穩定規則層。架構怎麼設計、各層指標的解讀方式、決策條件、已確認的結論清單。不隨 round 進度動，只在重大結構決策改變時更新。

- **`ESTIMATOR_POLICY.json`**：機器可讀的 baseline policy。程式碼引用 baseline 數字時，唯一可信來源。

- **`docs/policy/PSF_POLICY_TRANSITION_R26.md`**：PSF 政策切換的正式記錄（2026-03-27）。說明為什麼切換、如何切換、舊 baseline 的定位。

---

## 目前穩定判讀摘要 / Current Stable-Rule Reading

截至 2026-04-09，穩定規則層的判讀如下：

1. `COMBO / r38v2_8px_gate_p95` 是唯一 formal production baseline
2. `R33` 與 `R38v2` 是 approved alternates，不是 pending promotion
3. `Round30 / r30_b1_dironly` 是歷史前任 baseline
4. `R32 real_eq` 已 externally falsified，**不應再被描述成 promising line**
5. R26 的 PSF 正式標準已切換為新 Whole-FOV PSF（current standard），`R26NewPSFCheck` 只保留為 open side track
6. 若要挑戰 baseline，必須：新機制或新部署需求 + external final gate 明確勝出
7. 已否定的方向（step_mag sweep、TTA C2、A1/A5/S1、R31/R32 當前線）不應重開

The stable rules as of 2026-04-09: COMBO is the only formal production baseline; R33 and R38v2 are approved alternates; Round30 is the former baseline; R32 real_eq is externally falsified; the new Whole-FOV PSF remains the current standard while R26NewPSFCheck is only an open side track; any future challenger must justify itself with a new mechanism or deployment-specific need and still clear the external final gate.
