# PROJECT CURRENT STATE / 專案目前狀態
Last updated: 2026-04-05

Cross-interface entry / 跨入口入口：`PROJECT_SESSION_CONTINUITY.md`

## 1. Current Adopted Baseline / 目前正式 baseline

目前正式 baseline：**Round30 / `r30_b1_dironly`**  
The current adopted baseline is **Round30 / `r30_b1_dironly`**.

| 指標 | R30 B1 dironly |
|------|-----------|
| internal `0.8px center_err` | `0.0804` |
| internal `0.8px step_err` | `0.0693` |
| external `8px step std` | `0.205193` |
| external `0.8px step std` | `0.167862` |
| external `0.08px step std` | `0.157720` |
| `0.8px` lag-1 autocorr | `0.267027` |

正式入口 / Formal entry points：

- seed: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round30\selected\current_round30_arch_breakthrough_seed.json`
- internal decision: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round30\selected\reports\ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md`
- external compare: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round30\selected\reports\ROUND30_EXTERNAL_COMPARE.md`

這三份檔案分別對應目前正式 baseline 的 seed、internal decision 與 external compare 證據。  
These three files are the formal seed, internal decision, and external compare artifacts for the currently adopted baseline.

## 2. Latest Verified Outcomes / 最近已驗證結果

### Round31 / Round31

一句話 verdict：**measured B1 hyperparam candidates external 全部退步；baseline 維持 `Round30 / r30_b1_dironly`。**  
One-line verdict: **all measured Round31 B1 hyperparameter candidates regressed externally; the baseline remains `Round30 / r30_b1_dironly`.**

正式入口 / Formal entry points：

- decision: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
- external compare: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_EXTERNAL_COMPARE.md`

Round31 是沿 B1 主線做的正式 follow-up，但 measured candidates 在 external `0.8px` battlefield 全部退步。  
Round31 is a formal B1-line follow-up, but its measured candidates regressed on the external `0.8px` battlefield.

measured candidates / 已量測候選：

| candidate | external `0.8px step std` | vs `R30` |
|------|-----------|-----------|
| `r31_eq_prob_up` | `0.184867` | `+10.1%` |
| `r31_eq_weight_up` | `0.185458` | `+10.5%` |
| `r31_edge_ratio_low` | `0.179347` | `+6.8%` |

artifact caveat / artifact 注意事項：

- `r31_eq_combo` 缺 `GMF_score.txt`
- 判定：**external artifact missing**，不是 measured regression

`r31_eq_combo` 被明確記為 artifact missing，而不是 measured failure。  
`r31_eq_combo` is explicitly tracked as an artifact-missing case, not as a measured failure.

### Round32 / Round32

一句話 verdict：**`Round32` 已切到 `Experiments\R32Sandbox`；internal winner 是 `r32_real_eq_finetune`，但 external GMF compare 已確認 FAIL，不能升級 baseline。**  
One-line verdict: **`Round32` has moved into `Experiments\R32Sandbox`; the internal winner is `r32_real_eq_finetune`, but the external GMF compare confirmed FAIL, so it cannot be promoted.**

internal chain 正式入口 / Formal internal-chain entry points：

- sandbox README:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- decision memo:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
- runtime status:
  `D:\GMM_2_Final\Experiments\R32Sandbox\runtime\R32_STATUS.md`

這些檔案承載 `R32Sandbox` 的正式 internal decision path 與 canonical runtime truth。  
These files carry the formal internal decision path for the `R32Sandbox` line and the canonical runtime truth for the sandbox.

已確認事實 / Confirmed facts：

- shared mainline 已還原，不再混 `R32` 專用 loader / audit / monitor
- sandbox internal winner：`r32_real_eq_finetune`
- selected checkpoint：
  `D:\GMM_2_Final\Experiments\R32Sandbox\artifacts\training_progress_GESR_v1_v5_ST0p8_SWP_r32realeq_20260319_165431\weights\best_tradeoff.pth.tar`
- `0.8px` / `8px` internal audits 已完成
- decision memo 已確認 `r32_real_eq_finetune` 通過 calibrated pairmix / macro guard
- external compare 已完成，verdict = FAIL

internal winner 的確存在且通過 internal chain，但 final external compare 已完成且失敗。  
The internal winner exists and passed the internal chain, but the final external compare has already completed and failed.

external compare 核心數字 / Core external compare numbers：

| scale | baseline `r30_b1_dironly` | `r32_real_eq_finetune` | delta |
|------|-----------|-----------|-----------|
| `8px` | `0.205193` | `0.319667` | `+0.114475` |
| `0.8px` | `0.167862` | `0.331821` | `+0.163960` |
| `0.08px` | `0.157720` | `0.230119` | `+0.072399` |

補充 / Additional notes：

- `0.8px` outlier filtered 仍是 `0.303349`
- `0.8px` main battlefield 相對 `R30` 惡化 `+97.7%`
- `8px` guard 也失守

這不是邊際失敗；`0.8px` 主戰場相對 `Round30` 明顯惡化，`8px` guard 也一起失守。  
This is not a marginal failure. The `0.8px` battlefield deteriorated sharply relative to `Round30`, and the `8px` guard also failed.

## 3. Current Active State / 目前 active 狀態

目前 active 主線是 / The current active state is：

- **沒有可直接挑戰 baseline 的 current winning line**
- `R32 real_eq` 這條線已完成 external FAIL，R32 Sandbox 已關閉
- **目前 active 沙盒：`R26NewPSFCheck`**（2026-03-26 啟動，外部 GMF 結果等待中）
- **新實驗沙盒：`R33RobustLoss`**（2026-04-05 啟動，Winsorize 空間損失降權缺陷離群值）

### R26NewPSFCheck 現況（2026-03-27）

| 項目 | 狀態 |
|------|------|
| 新 Whole-FOV PSF 擬合 | ✓ 完成（2026-03-26） |
| 新 PSF 重訓模型 checkpoint | ✓ 已建立並快照至 sandbox |
| 外部三尺度重建（external recon） | ✓ 已完成 |
| PSF 正式流程審核 | ✓ 已完成，無執行層面問題 |
| pure_psf_control 對照實驗 | ✓ 已完成，確認新 PSF 本身不是崩壞原因 |
| formal_newpsf_candidate promote | ✓ 已完成，verdict：PROMOTE |
| PSF 政策切換 | ✓ **2026-03-27 正式切換**，見下方 Section 6 |
| 外部 GMF 結果（主要比較） | ⏳ 等待中（GMF 工具由外部執行） |

正式入口 / Formal entry points：

- sandbox 說明：`D:\GMM_2_Final\Experiments\R26NewPSFCheck\README.md`
- 整體進度摘要：`D:\GMM_2_Final\Experiments\R26NewPSFCheck\reports\STATUS_20260326.md`
- PSF 審核記錄：`D:\GMM_2_Final\Experiments\R26NewPSFCheck\psf_audit\PSF_FORMAL_AUDIT_20260326.md`
- promote 比較報告：`D:\GMM_2_Final\Experiments\R26NewPSFCheck\formal_newpsf_candidate\reports\NEW_PSF_FORMAL_R26_COMPARE.md`

### R33RobustLoss 現況（2026-04-05）

| 項目 | 狀態 |
|------|------|
| 假說 | residual_std 2.9 px 的瓶頸源於不可修缺陷像素的離群梯度拉扯 |
| 機制 | 對 W_GRADMAG + W_HF_LAP 做 per-pixel Winsorize（截尾） |
| 候選 | p90 / p85 / p95 三個 percentile，warmup=10 epoch |
| 程式碼修改 | `_winsorize()` 函式 + 2 個 loss 函式加 robust_pct 參數 |
| 訓練 | ⏳ 尚未開始 |
| 分支 | `sandbox/r33` |

正式入口：`D:\GMM_2_Final\Experiments\R33RobustLoss\README.md`

Git-tracked 的 `000_LONGRUN_ROUND32_STATUS.*` 現在保留於 `docs/runtime/legacy/root_status/` 作為 legacy bridge，不再視為 canonical runtime state；若 root 再生成同名檔案，視為本地 runtime 輸出即可。
The Git-tracked `000_LONGRUN_ROUND32_STATUS.*` files are now kept under `docs/runtime/legacy/root_status/` as a legacy bridge only; if the same filenames reappear at the repository root, treat them as local runtime output rather than canonical truth.

## 4. External Validation Status / 外部驗證狀態

`Round32` external validation 已完成 / `Round32` external validation is complete:

- selected candidate 的三個 pitch reconstruction 已生成
- sandbox external compare 已完成並確認 FAIL

正式入口 / Formal entry points：

- external compare README:
  `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\README.md`
- final compare markdown:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`
- final compare json:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.json`

外部驗證已完全關閉，Markdown 與 JSON verdict artifacts 都已具備。  
The external validation is fully closed. Both the human-readable Markdown and the machine-readable JSON verdict artifacts are available.

目前真正的結論是 / The real conclusion is：

- `r32_real_eq_finetune` 不能升級
- `Round30 / r30_b1_dironly` baseline unchanged
- 若要續做 `R32`，需要**另立新分支 / 新機制**

## 5. PSF Policy Status / PSF 政策狀態（2026-03-27）

R26 研究線的 PSF 已於 2026-03-27 正式完成政策切換。

| 身份 | PSF | 說明 |
|------|-----|------|
| **current standard** | 新 Whole-FOV PSF（2026-03-26 完成） | 物理上較合理；same-recipe 對照確認不引發崩壞；為目前研究採用的正式 PSF |
| **legacy empirical baseline** | 舊 PSF | 歷史上取得較好經驗數值；保留用於引用與對照，不刪除，不再作為正式預設 |

切換依據 / Basis for transition：
- pure_psf_control 實驗確認：old_recipe + new_psf 到 epoch 40 不重現先前崩壞
- 先前崩壞根因是「PSF 變更 + recipe drift」共同造成，非 PSF 本身問題
- formal_newpsf_candidate 已完成 same-recipe promote 驗證，verdict：PROMOTE
- physics-first 原則下，物理上較合理的 PSF 應成為目前標準

機器可讀 PSF 政策 / Machine-readable PSF policy：`D:\GMM_2_Final\docs\policy\PSF_STANDARD_POLICY.json`
詳細說明 / Full details：`D:\GMM_2_Final\docs\policy\PSF_POLICY_TRANSITION_R26.md`

## 6. Next Decision Boundary / 下一個決策邊界

下一個決策邊界只有一個 / There is only one next decision boundary:

**任何新候選若要升級 baseline，必須在 external GMF 主戰場 `0.8px` 擊敗 `R30 B1 dironly = 0.167862`。**

這包含 `R26NewPSFCheck` 的外部 GMF 結果（等待中）以及任何未來的新候選。

正式升級條件 / Formal promotion conditions：

1. external `0.8px step std < 0.167862`
2. `8px` 不能明顯退步
3. `0.08px` 改善不能補償 `0.8px` 主戰場退步

任何候選都必須在 external `0.8px` battlefield 擊敗 `0.167862`，同時不能用 `8px` 退步或主戰場退步去換取 `0.08px` 改善。
Any candidate must beat `0.167862` on the external `0.8px` battlefield, avoid meaningful `8px` regression, and cannot trade away the main battlefield just to improve `0.08px`.
