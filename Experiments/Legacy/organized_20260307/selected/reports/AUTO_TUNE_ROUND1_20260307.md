# 0307 自動化調整 Round 1

## 狀態

- 狀態：執行中
- 日期：2026-03-07
- 目標：
  - 優先壓低 `8 px` 位移步長的波動
  - 保持邊界位置重建正確
  - 在不犧牲 GMF/PM 穩定度的前提下，讓邊界更真實、更銳利

## 已做變更

### 1. 訓練選模邏輯對齊真正 KPI

已更新：
- `Model/GeoEdgeAlignSR_v1_Train_v5_NoCoord_return_v2_SimpleTest.py`
- `Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py`

重點：
- `gmf_obj` 不再只偏 proxy score
- 直接納入：
  - `kpi_step_std`
  - `kpi_outlier_rate`
  - `kpi_step_mean_err`
- autotune 候選排名也同步改成以這些指標為主

### 2. 自動化流程修正

第一版 `round1` 在執行中暴露出兩個流程問題，已在 `round1b` 修正：

- run 命名過長
  - 原本 autotune run 會產生過長的 Windows 路徑
  - `texture_guard_v2` 曾出現 checkpoint 寫檔失敗
  - 現已改為短名：
    - base：`GESR_v1_v5_ST8`
    - sweep：`GESR_v1_v5_ST8_SWP_<tag>`
    - final：`GESR_v1_v5_ST8_FIN_<tag>`

- sweep 選模視窗過晚
  - 原本短 sweep 只看第 5 epoch，容易錯過像 `general_v2` 這種在第 3 epoch 較好的候選
  - 現改為 sweep 允許在第 `3~5 epoch` 內更新 best

- autotune proxy 額外負擔過高
  - 對 autotune 排名沒有直接幫助的 `weak-PSF bypass proxy eval` 已關閉
  - sweep 內部 GMF frame 數改為 `5`
  - final 仍維持 `7`

### 3. 新增 0307 曲邊資料 stage

已新增：
- `stage_15_annulus_sparse_clean`
- `stage_16_annulus_sparse_defect_clean`

用途：
- 增加更貼近單圓環 / 稀疏曲邊樣本的訓練分布
- 降低高密度場景把目標邊界學習稀釋掉的問題
- 保留少量真實缺口 / 崩邊型態，避免邊界只學到理想化光滑輪廓

### 4. 新 stage 已完成生成與卷積

已完成：
- clean generation：stage 15/16
- PSF convolution：stage 15/16

## 本輪候選

目前 round 1 候選包含：
- `step8_curve_sharp_ref`
- `step8_curve_stdguard_v2`
- `step8_curve_texture_guard_v2`
- `step8_curve_general_v2`

## 已知中止與重啟

### 已中止的 4-epoch 嘗試

先前曾啟動一個 `sweep_epochs=4` 的批次，但已中止並清除。

原因：
- 內部 warmup 與 best selection 的最早可評估 epoch 不對齊
- 導致 sweep ranking 在流程上不成立

### 已保留但不採信的第一版 round1

第一版有效命令為：
- `sweep_epochs=5`
- `final_epochs=18`

但這一版流程中已出現：
- 長路徑 checkpoint 問題
- run log 與實際執行進度不同步
- 舊批次雖然後續已進入 `AUTO_FINAL_step8_curve_sharp_ref_20260307_134155`，但因流程污染與中途被終止，不採信其結果

因此目前採用的是修正後重啟的 `round1b`。

## 目前正在跑的有效命令

```powershell
python -u Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py --sweep-epochs 5 --final-epochs 18 --deterministic
```

## 目前 log

### 現行有效批次：round1b

- `Experiments/Legacy/organized_20260307/pending/logs/auto_tune_console_20260307_134626_round1b.out.log`
- `Experiments/Legacy/organized_20260307/pending/logs/auto_tune_console_20260307_134626_round1b.err.log`
- `Experiments/Legacy/organized_20260307/pending/logs/auto_tune_console_20260307_134626_round1b.meta.txt`

### 舊版保留參考：round1

- `Experiments/Legacy/organized_20260307/pending/logs/auto_tune_console_20260307_120032_round1.out.log`
- `Experiments/Legacy/organized_20260307/pending/logs/auto_tune_console_20260307_120032_round1.err.log`
- `Experiments/Legacy/organized_20260307/pending/logs/auto_tune_console_20260307_120032_round1.meta.txt`

## 暫時觀察

從舊版 `round1` 已寫出的 sweep 結果看：
- `step8_curve_sharp_ref` 雖然在舊 scoring 下排名第一，但其 `pass02=0`，`step_std / step_mean_err` 仍不夠理想
- `step8_curve_general_v2` 在第 3 epoch 曾短暫出現很好的內部 known-step KPI，但舊 sweep 因為只看第 5 epoch，沒有把這個訊號轉成候選優勢
- 這就是本次把 sweep best window 改為 `3~5 epoch` 的直接原因

因此本輪仍然要等修正後的 `round1b`：
1. sweep 排名完成
2. final run 完成
3. 之後再由你提供外部 `GMF_score.txt`

才會做最終升級判定

## round1b 中間結果

### 已完成候選

- `step8_curve_sharp_ref`
  - `score_shift_first = 2.909712`
  - best 被記在 `epoch 3`
  - `best_step_err = 0.000000`
  - `best_pos_std_sum = 0.741300`
  - `best_kpi_step_std = 0.0311`
  - `best_kpi_outlier_rate = 0.0000`
  - `best_kpi_step_mean_err = 0.0311`

### 目前判讀

- 這個結果比舊版 round1 明顯合理
  - 舊版只看第 5 epoch，`sharp_ref` 被後段崩掉拖成大幅負分
  - 新版改成 `3~5 epoch` 視窗後，成功保留其早期穩定點
- 這證明目前的流程修正是有效的
- 但這還不是最終結論
  - `step8_curve_stdguard_v2`
  - `step8_curve_texture_guard_v2`
  - `step8_curve_general_v2`
  仍在排隊執行
