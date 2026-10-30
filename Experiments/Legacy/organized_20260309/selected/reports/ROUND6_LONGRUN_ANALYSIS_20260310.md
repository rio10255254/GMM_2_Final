# Round6 + LongRun 分析結論 2026-03-10

## 狀態
- 背景程序已全部結束。
- `round6 pipeline` 狀態：`stopped`
- `LongRunSupervisor` 狀態：`stopped`
- `plan_done = 4 / 4`

## 核心發現
1. 所有流程都是正常跑完，不是 crash。
2. 各尺度的 **sweep best** 仍有參考價值，但 **final continuation 幾乎一致退化**。
3. 這代表目前 autotune 的主要價值在於：
   - 找出早期可用 checkpoint
   - 而不是再做長的 final continuation
4. `0.08 px` 這條線已經有可用趨勢，但 final 仍會掉分。
5. `0.8 px` 目前仍偏弱；有候選，但離穩定可用還有距離。
6. `8 px` cross-scale anchor 在這次 long-run 裡沒有打贏現有主基準，甚至 final 明顯崩掉。

## 目前主基準
- 全域 current seed 仍維持不變：
  `Experiments/Legacy/organized_20260309/selected/current_seed.json`
- 仍指向：
  `Experiments/Legacy/organized_20260307/selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`
- 原因：後續 long-run 沒有出現一個足以取代它的全域贏家。

## 各尺度目前最值得保留的 sweep 候選
### 0.08 px
- manifest:
  `Experiments/Legacy/organized_20260309/selected/multiscale/best_step_0p08.json`
- best candidate:
  `micro_general_curve`
- sweep score:
  `3.1387377283436457`
- sweep run:
  `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p08_SWP_mgc_20260310_035426`
- final run:
  `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p08_FIN_mgc_20260310_040642`
- 判讀：
  sweep 可保留；final 不建議當部署版本。

### 0.8 px
- manifest:
  `Experiments/Legacy/organized_20260309/selected/multiscale/best_step_0p8.json`
- best candidate:
  `micro_general_curve`
- sweep score:
  `1.253649689100726`
- sweep run:
  `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_SWP_mgc_20260310_073521`
- final run:
  `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST0p8_FIN_mgc_20260310_074408`
- 判讀：
  有候選，但整體仍偏弱；final 仍退化。

### 8 px
- manifest:
  `Experiments/Legacy/organized_20260309/selected/multiscale/best_step_8.json`
- best candidate:
  `subpix_general_curve`
- sweep score:
  `4.377482514122981`
- sweep run:
  `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST8_SWP_spg_20260310_053804`
- final run:
  `Experiments/Training_Runs/training_progress_GESR_v1_v5_ST8_FIN_spg_20260310_055939`
- 判讀：
  final 明顯崩壞，且 sweep 也沒有打贏既有全域基準 `4.732227216384246`。

## 明顯的模式
- `0.08 px` initial round6:
  sweep `3.1279` -> final `1.2415`
- `0.8 px` deeper guard:
  sweep `1.1900` -> final `-7.7691`
- `0.08 px` deeper probe:
  sweep `3.1387` -> final `0.6894`
- `8 px` cross-scale anchor:
  sweep `4.3775` -> final `-162.1385`
- `0.8 px` micro bias:
  sweep `1.2536` -> final `-5.9773`

結論：
- 問題不在 sweep 選不出候選。
- 問題在 final continuation 仍然過長、過重，會把已經可用的早期點訓壞。

## 建議
1. 接下來若要做外部驗證，優先拿 **sweep best**，不要先拿 final。
2. 下一輪 autotune 應考慮：
   - 直接把 sweep checkpoint 當 deploy candidate
   - 或 final 只做非常短的 continuation
3. `0.08 px` 比 `0.8 px` 更早出現可用訊號，值得優先追。
