# PROJECT CURRENT STATE / 專案目前狀態
Last updated: 2026-04-09 (COMBO promoted to formal baseline)

Cross-interface entry / 跨入口入口：`PROJECT_SESSION_CONTINUITY.md`

## 1. Current Formal Baseline / 目前正式 baseline

目前正式 baseline：**COMBO / `r38v2_8px_gate_p95`**
The formal production baseline is now **COMBO / `r38v2_8px_gate_p95`**.

升級生效日期 / Promotion effective date：**2026-04-08**

| 指標 | COMBO |
|------|-------|
| external `8px step std` | `0.154515` |
| external `0.8px step std` | `0.131560` |
| external `0.08px step std` | `0.099891` |
| `0.8px` lag-1 autocorr | `-0.5176` |
| edge steepness vs R30 | `+89.4%` |
| contrast std vs R30 | `-6.6%` |
| gradient magnitude vs R30 | `-19.7%` |
| residual std (`0.8px` inner) | `2.044` |

正式入口 / Formal entry points：

- checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\weights\best_tradeoff.pth.tar`
- promoted baseline report:
  `D:\GMM_2_Final\Experiments\R38v2SeqFixed\reports\COMBO_RESULTS.md`
- complete series context:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`
- machine-readable truth:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`

COMBO 之所以被升級，不是因為它在單一 GMF 指標上最極端，而是因為它在 `0.8px` 主戰場、`8px` 宏觀守門、視覺 steepness、以及 residual_std 四個面向同時最均衡。
COMBO was promoted not because it is the most extreme on any single metric, but because it best balances the `0.8px` battlefield, the `8px` guard, visual steepness, and residual quality.

### Former Baseline / 前任 baseline

前任正式 baseline：**Round30 / `r30_b1_dironly`**
Former formal baseline: **Round30 / `r30_b1_dironly`**.

| 指標 | R30 former baseline |
|------|---------------------|
| external `8px step std` | `0.205193` |
| external `0.8px step std` | `0.167862` |
| external `0.08px step std` | `0.157720` |
| `0.8px` lag-1 autocorr | `0.267027` |

## 2. Approved Alternates / 已核准特化候選

### R33 / r33_robust_p95 — GMF Extreme Alternate

一句話定位：**GMF 極致型特化候選；不是正式 baseline。**
One-line role: **GMF-extreme approved alternate; not the formal baseline.**

| 指標 | R33 |
|------|-----|
| external `8px step std` | `0.153343` |
| external `0.8px step std` | `0.119049` |
| external `0.08px step std` | `0.086274` |
| `0.8px` lag-1 autocorr | `-0.5549` |
| edge steepness vs R30 | `-22%` |

適用場景 / Recommended use：
- 以 GMF 幾何精度為唯一主目標
- 可以接受視覺邊界更柔

正式入口 / Formal entry points：
- report:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\R33_EXPERIMENT_SUMMARY.md`
- checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260405_091941\weights\best_tradeoff.pth.tar`

### R38v2 / r38v2_8px_gate — Visual Priority Alternate

一句話定位：**視覺優先型特化候選；不是正式 baseline。**
One-line role: **visual-priority approved alternate; not the formal baseline.**

| 指標 | R38v2 |
|------|-------|
| external `8px step std` | `0.143988` |
| external `0.8px step std` | `0.134205` |
| external `0.08px step std` | `0.106457` |
| `0.8px` lag-1 autocorr | `-0.5459` |
| edge steepness vs R30 | `+89.4%` |

適用場景 / Recommended use：
- 需要外部 GMF 改善，同時維持接近 R30 的視覺銳度
- 視覺品質比極致 GMF 更重要

正式入口 / Formal entry points：
- report:
  `D:\GMM_2_Final\Experiments\R38v2SeqFixed\reports\R38v2_RESULTS.md`
- checkpoint:
  `D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260406_235957\weights\best_tradeoff.pth.tar`

## 3. Current Promoted State / 目前正式狀態

目前 mainline 狀態是 / The current mainline state is：

- **formal production baseline 已升級為 COMBO**
- `R33` 與 `R38v2` 已收斂為 approved alternates，而不是 open challengers
- **目前沒有開放中的 baseline challenger**
- `Round31` 已關閉，`Round32` 已關閉
- `R26NewPSFCheck` 仍保留為 **open side track**，但不是 active mainline

### Closed Follow-up: Round31

一句話 verdict：**measured B1 hyperparam candidates external 全部退步；沒有形成升級。**
One-line verdict: **all measured Round31 B1 hyperparameter candidates regressed externally; no upgrade was produced.**

正式入口 / Formal entry points：

- decision:
  `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
- external compare:
  `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_EXTERNAL_COMPARE.md`

measured candidates / 已量測候選：

| candidate | external `0.8px step std` | vs former baseline `R30` |
|------|-----------|-----------|
| `r31_eq_prob_up` | `0.184867` | `+10.1%` |
| `r31_eq_weight_up` | `0.185458` | `+10.5%` |
| `r31_edge_ratio_low` | `0.179347` | `+6.8%` |

artifact caveat / artifact 注意事項：
- `r31_eq_combo` 缺 `GMF_score.txt`
- 判定：**artifact missing**，不是 measured regression

### Closed Sandbox: Round32

一句話 verdict：**`R32Sandbox` internal winner external FAIL；sandbox 已關閉。**
One-line verdict: **the `R32Sandbox` internal winner failed the final external gate; the sandbox is closed.**

正式入口 / Formal entry points：

- sandbox README:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- decision memo:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
- final external compare:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`

核心數字 / Core numbers：

| scale | former baseline `R30` | `r32_real_eq_finetune` | delta |
|------|-----------|-----------|-----------|
| `8px` | `0.205193` | `0.319667` | `+0.114475` |
| `0.8px` | `0.167862` | `0.331821` | `+0.163960` |
| `0.08px` | `0.157720` | `0.230119` | `+0.072399` |

## 4. Open Side Track / 開放中的 side track

### R26NewPSFCheck

一句話定位：**PSF 驗證 side track；pending external GMF；不是 active mainline。**
One-line role: **PSF-validation side track; pending external GMF; not the active mainline.**

| 項目 | 狀態 |
|------|------|
| 新 Whole-FOV PSF 擬合 | ✓ 完成（2026-03-26） |
| 新 PSF 重訓模型 checkpoint | ✓ 已建立 |
| 外部三尺度重建（external recon） | ✓ 已完成 |
| PSF 正式流程審核 | ✓ 已完成 |
| pure_psf_control 對照實驗 | ✓ 已完成 |
| formal_newpsf_candidate promote | ✓ 已完成，verdict：PROMOTE |
| 外部 GMF 結果 | ⏳ 等待中 |

正式入口 / Formal entry points：

- sandbox README:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\README.md`
- status:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\reports\STATUS_20260326.md`
- PSF audit:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\psf_audit\PSF_FORMAL_AUDIT_20260326.md`
- promote compare:
  `D:\GMM_2_Final\Experiments\R26NewPSFCheck\formal_newpsf_candidate\reports\NEW_PSF_FORMAL_R26_COMPARE.md`

## 5. Measurement Policy Status / 量測政策狀態

目前穩定結論 / Current stable conclusion：

- **external GMF remains the final gate**
- internal step_std **不再適合作為硬門檻**，尤其在 residual_std 進入低噪聲區後
- 720-angle unweighted circle fit 已驗證能降低 internal/external gap
- weighted fit 可用，但不是統一預設

正式入口 / Formal entry points：

- divergence analysis:
  `D:\GMM_2_Final\Experiments\R33RobustLoss\reports\INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`
- machine-readable policy:
  `D:\GMM_2_Final\ESTIMATOR_POLICY.json`

量化修復狀態 / Quantization policy：

- canonical inference now uses `np.rint`
- R33 修復後 `0.8px` 改善，R38v2 修復後 `8px` 改善但 `0.8px` 退步
- 這個差異被視為 **model-dependent quantization sensitivity**，不推翻 COMBO promotion

## 6. PSF Policy Status / PSF 政策狀態（2026-03-27）

R26 研究線的 PSF 已於 2026-03-27 正式完成政策切換。

| 身份 | PSF | 說明 |
|------|-----|------|
| **current standard** | 新 Whole-FOV PSF（2026-03-26 完成） | 物理上較合理；same-recipe 對照確認不引發崩壞；為目前研究採用的正式 PSF |
| **legacy empirical baseline** | 舊 PSF | 歷史上取得較好經驗數值；保留用於引用與對照，不刪除，不再作為正式預設 |

機器可讀 PSF 政策 / Machine-readable PSF policy：
`D:\GMM_2_Final\docs\policy\PSF_STANDARD_POLICY.json`

詳細說明 / Full details：
`D:\GMM_2_Final\docs\policy\PSF_POLICY_TRANSITION_R26.md`

## 7. Next Decision Boundary / 下一個決策邊界

下一個決策邊界已經不再是「三候選誰升級」，因為這件事已完成。
The next decision boundary is no longer “which of the three candidates gets promoted,” because that decision is now closed.

接下來只在以下情況才值得立新 round：

1. 有明確新機制，不是 R33/R38v2/COMBO 的微幅重掃
2. 有 deployment-specific 需求，足以合理地偏向某個 alternate 或新線
3. 能同時說清楚 external GMF 目標、`8px` guard、與視覺取捨

不再合理的下一步 / What is no longer a sensible next step：

- 把 `R26NewPSFCheck` 寫成 active mainline
- 把 `R33` 或 `R38v2` 繼續寫成 pending promotion
- 把 720-angle 當成未完成 action item

目前真正的決策邊界是：
**若要再開新 round，必須是新的機制或新的 deployment 條件，而不是重複討論已完成的 baseline promotion。**
