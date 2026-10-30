# 0307 Round1 整理與續訓狀態

## 結論

- `20260307` round1 已整理完成
- `0307` 內部 autotune 最佳 sweep 候選為：
  - `step8_curve_stdguard_v2`
- 但其 `final 18 epoch` 版本明顯退化，因此沒有升級成新的正式採用版
- `20260306` 的正式基準版不變
- `0307 selected/` 目前保留的是後續續訓 seed，不是新的手動推理正式版

## round1 關鍵結果

### 最佳 sweep 候選

- run：
  - `selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625`
- 權重：
  - `selected/runs/training_progress_GESR_v1_v5_ST8_SWP_stdg_20260307_135625/weights/best_tradeoff.pth.tar`
- 內部最佳點：
  - `best_epoch = 3`
  - `best_gmf_obj = 37.1653`
  - `best_pos_std_sum = 0.0000`
  - `best_kpi_step_std = 0.0000`
  - `best_kpi_outlier_rate = 0.0000`
  - `best_kpi_step_mean_err = 0.0000`

### 為何沒有直接採用 final

- run：
  - `rejected/runs/training_progress_GESR_v1_v5_ST8_FIN_stdg_20260307_142448`
- final 最佳點：
  - `best_epoch = 9`
  - `best_gmf_obj = -27.4557`
  - `best_step_err = 0.3333`
  - `best_pos_std_sum = 2.9652`
  - `best_kpi_step_std = 7.3779`
  - `best_kpi_outlier_rate = 0.8333`
  - `best_kpi_step_mean_err = 6.1150`

判讀：
- sweep 早期點很穩
- 一旦訓練進入後段 stage，內部 known-step KPI 明顯崩掉
- 所以 round1 的主要結論不是「stdg 已經完成」，而是「stdg 的早期狀態值得當續訓 seed」

## 這次整理做了什麼

### selected

- 保留 `SWP_stdg` 作為 round2 續訓種子
- 只保留：
  - `best_tradeoff.pth.tar`
  - `run_meta.json`
  - `val_log_v5.csv`
  - `batch_log_v5.csv`
  - `attribution_log.txt`
  - round1b 的 md/json/log

### rejected

- 放入：
  - `SWP_sharp`
  - `SWP_texg`
  - `SWP_genv2`
  - `FIN_stdg`
- 刪除其不需要的：
  - `_repro`
  - 重複或未採用 weights
  - monitor bmp
  - epoch checkpoints

### archive

- 舊的長命名 round1 污染 run 已全部移到 `archive/runs`
- 只保留 csv / meta / attribution
- 舊 round1 log 移到 `archive/logs`

## 容量

- 目前 `Traing_Progress` 約：
  - `0.353 GB`

## 接下來的 round2 方向

從 round1 可直接得到的策略訊號是：

1. `best` 幾乎都出現在非常早期的 epoch
2. 後段的 weak-PSF / physics / 幾何 ramp 使內部 8px 已知步長 KPI 惡化
3. round2 應優先測：
   - 延長 stage0/early-freeze
   - 延後 weak-PSF 與 physics 介入
   - 用 `SWP_stdg best_tradeoff.pth.tar` 當 warm start 種子

這會是後續長時間自動化優化的起點。
