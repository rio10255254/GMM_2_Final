# Pure PSF Control Interpretation (2026-03-26)

## Key Verdict

在 `old_recipe + old_psf` 與 `old_recipe + new_centered_psf` 的純對照下，兩條線在 `epoch 10 / 20 / 40` 的單張重建指標幾乎重合，沒有重現先前那次「新 PSF 重訓版明顯退步」的現象。

這表示：

- **new centered PSF 本身不是那次崩壞的充分原因**
- 先前觀察到的大幅退步，更合理地應歸因於 **recipe drift**，而不是「只要把 PSF 置中，模型就一定會亂掉」

## Core Evidence

| epoch | metric | old_psf | new_psf | comment |
| --- | --- | ---: | ---: | --- |
| 10 | edge_width_main_px | 33.74 | 33.74 | 幾乎一致 |
| 10 | max_slope_main | 6.49 | 6.51 | 幾乎一致 |
| 10 | CNR_main | 19.71 | 19.95 | 幾乎一致 |
| 10 | background_std | 0.613 | 0.610 | 幾乎一致 |
| 20 | edge_width_main_px | 35.69 | 35.67 | 幾乎一致 |
| 20 | max_slope_main | 6.34 | 6.34 | 幾乎一致 |
| 20 | CNR_main | 19.73 | 19.66 | 幾乎一致 |
| 20 | background_std | 0.505 | 0.501 | 幾乎一致 |
| 40 | edge_width_main_px | 35.27 | 35.31 | 幾乎一致 |
| 40 | max_slope_main | 6.51 | 6.53 | 幾乎一致 |
| 40 | CNR_main | 15.94 | 15.89 | 幾乎一致 |
| 40 | background_std | 0.486 | 0.489 | 幾乎一致 |

`checkerboard_ratio`、`ring_thickness_std_px` 也沒有出現足以支持「new PSF 自身導致崩壞」的差距。

## What This Means

這輪純對照已經把因果鏈收斂成比較清楚的版本：

1. `new centered PSF` 改變的是 prior 語意，不是 width。
2. 但 **在舊 R26 recipe 等價條件下**，模型其實可以適應這個新 PSF，至少到 `epoch 40` 都沒有明顯退步。
3. 因此，先前那次 `newpsf_r26_retrain` 的大幅惡化，不應再寫成「PSF 一置中就崩」。
4. 更合理的說法是：
   - **真正出問題的是新 PSF 與另一套訓練/選模 recipe 被一起更換**
   - 崩壞主要來自 `PSF 變更 + recipe drift` 的組合，而不是純 PSF 單因子

## Practical Implication

- 正式 root/package 預設先維持舊 PSF，這是保守做法。
- 但如果要讓新 PSF 進正式線，優先方向已經不是「回去質疑 PSF fitting 是否必然錯誤」。
- 更正確的下一步是：
  - 以舊 R26 recipe 為基底
  - 一次只重新引入一個改動
  - 找出真正導致退步的 recipe drift 因子

## Safe Statement

目前最安全的結論是：

> `new centered PSF` 在舊 R26 recipe 等價條件下，至少到 `epoch 40` 並未顯示出明顯劣化；因此先前新 PSF 重訓版的崩壞，不應被解讀為純 PSF 置中本身所致，而更可能來自訓練與選模流程的 drift。
