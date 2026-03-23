# PROJECT CURRENT STATE
Last updated: 2026-03-20

Cross-interface entry: `PROJECT_SESSION_CONTINUITY.md`

## 1. Current Adopted Baseline

目前正式 baseline：**Round30 / `r30_b1_dironly`**

| 指標 | R30 B1 dironly |
|------|-----------|
| internal `0.8px center_err` | `0.0804` |
| internal `0.8px step_err` | `0.0693` |
| external `8px step std` | `0.205193` |
| external `0.8px step std` | `0.167862` |
| external `0.08px step std` | `0.157720` |
| `0.8px` lag-1 autocorr | `0.267027` |

正式入口：

- seed: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round30\selected\current_round30_arch_breakthrough_seed.json`
- internal decision: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round30\selected\reports\ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md`
- external compare: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round30\selected\reports\ROUND30_EXTERNAL_COMPARE.md`

## 2. Latest Verified Outcomes

### Round31

一句話 verdict：**measured B1 hyperparam candidates external 全部退步；baseline 維持 `Round30 / r30_b1_dironly`。**

正式入口：

- decision: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
- external compare: `D:\GMM_2_Final\Traing_Progress\organized_20260316\round31\selected\reports\ROUND31_EXTERNAL_COMPARE.md`

measured candidates：

| candidate | external `0.8px step std` | vs `R30` |
|------|-----------|-----------|
| `r31_eq_prob_up` | `0.184867` | `+10.1%` |
| `r31_eq_weight_up` | `0.185458` | `+10.5%` |
| `r31_edge_ratio_low` | `0.179347` | `+6.8%` |

artifact caveat：

- `r31_eq_combo` 缺 `GMF_score.txt`
- 判定：**external artifact missing**，不是 measured regression

### Round32

一句話 verdict：**`Round32` 已切到 `Experiments\R32Sandbox`；internal winner 是 `r32_real_eq_finetune`，但 external GMF compare 已確認 FAIL，不能升級 baseline。**

internal chain 正式入口：

- sandbox README:
  `D:\GMM_2_Final\Experiments\R32Sandbox\README.md`
- decision memo:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
- runtime status:
  `D:\GMM_2_Final\Experiments\R32Sandbox\runtime\R32_STATUS.md`

已確認事實：

- shared mainline 已還原，不再混 `R32` 專用 loader / audit / monitor
- sandbox internal winner：`r32_real_eq_finetune`
- selected checkpoint：
  `D:\GMM_2_Final\Experiments\R32Sandbox\artifacts\training_progress_GESR_v1_v5_ST0p8_SWP_r32realeq_20260319_165431\weights\best_tradeoff.pth.tar`
- `0.8px` / `8px` internal audits 已完成
- decision memo 已確認 `r32_real_eq_finetune` 通過 calibrated pairmix / macro guard
- external compare 已完成，verdict = FAIL

external compare 核心數字：

| scale | baseline `r30_b1_dironly` | `r32_real_eq_finetune` | delta |
|------|-----------|-----------|-----------|
| `8px` | `0.205193` | `0.319667` | `+0.114475` |
| `0.8px` | `0.167862` | `0.331821` | `+0.163960` |
| `0.08px` | `0.157720` | `0.230119` | `+0.072399` |

補充：

- `0.8px` outlier filtered 仍是 `0.303349`
- `0.8px` main battlefield 相對 `R30` 惡化 `+97.7%`
- `8px` guard 也失守

## 3. Current Active State

目前 active 主線是：

- **沒有可直接挑戰 baseline 的 current winning line**
- `R32 real_eq` 這條線已完成 external FAIL
- 若要續做 `R32`，下一步必須是新的 sandbox branch / 新機制

現在 process-level / runtime truth 入口是：

- `D:\GMM_2_Final\Experiments\R32Sandbox\runtime\R32_STATUS.md`

Git-tracked 的 `000_LONGRUN_ROUND32_STATUS.*` 現在保留於 `docs/runtime/legacy/root_status/` 作為 legacy bridge，不再視為 canonical runtime state；若 root 再生成同名檔案，視為本地 runtime 輸出即可。

## 4. External Validation Status

`Round32` external validation 已完成：

- selected candidate 的三個 pitch reconstruction 已生成
- sandbox external compare 已完成並確認 FAIL

正式入口：

- external compare README:
  `D:\GMM_2_Final\Experiments\R32Sandbox\external_compare\README.md`
- final compare markdown:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.md`
- final compare json:
  `D:\GMM_2_Final\Experiments\R32Sandbox\reports\ROUND32_EXTERNAL_COMPARE.json`

目前真正的結論是：

- `r32_real_eq_finetune` 不能升級
- `Round30 / r30_b1_dironly` baseline unchanged
- 若要續做 `R32`，需要**另立新分支 / 新機制**

## 5. Next Decision Boundary

下一個決策邊界只有一個：

**下一個 `R32` 候選若要成立，必須是新的 sandbox branch / 新機制，並在 external GMF 主戰場 `0.8px` 擊敗 `R30 B1 dironly = 0.167862`。**

正式升級條件：

1. external `0.8px step std < 0.167862`
2. `8px` 不能明顯退步
3. `0.08px` 改善不能補償 `0.8px` 主戰場退步
