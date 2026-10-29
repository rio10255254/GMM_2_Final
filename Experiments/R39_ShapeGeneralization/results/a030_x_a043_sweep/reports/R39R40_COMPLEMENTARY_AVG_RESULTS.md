# R39 a030 × R40 a043 互補權重平均 — 外部 GMF 補測結果

## 摘要

R39 a030 與 R40 a043 在外部 GMF 三尺度上的取捨方向互補（2026-05-11 量測）：

| 候選 | 8 px Δ | 0.8 px Δ | 0.08 px Δ |
|---|---:|---:|---:|
| R39 a030 | `−6.94%` | `+6.42%` | `−15.97%` |
| R40 a043 | `−5.91%` | `−3.15%` | `+21.52%` |

兩者 8 px 改善幅度相當；a030 改善 0.08 px 但 0.8 px 退步、a043 改善 0.8 px 但 0.08 px 退步。本實驗線性平均兩個 checkpoint 在 α=0.25 / 0.50 / 0.75 三個中間點，加上 α=0 跟 α=1 兩端組成 5 點 sweep，量測互補取捨能否讓三尺度都進 7 % 替代容忍區或 3 % 升級上限。

本份報告只忠實紀錄觀察數字，不下推薦也不寫升級判定（升級判定由 `r40_external_compare.py` 依其內建門檻自動標出）。

## 實驗設計

- 平均方法：用 `r39_weight_sweep.interpolate_state_dicts` 對兩個 state_dict 做線性插值（α=0 是純 a030、α=1 是純 a043）。
- 平均腳本：`Experiments/R39_ShapeGeneralization/scripts/r39r40_complementary_average.py`
- 中間 α 補測點：0.25 / 0.50 / 0.75（兩端已有結果不重跑）
- 外部 ring 三尺度重建：用 `Tools/RunRepresentativeExternalRecon.ps1` 對每個 α 跑 Pitch1um_Y_100 / Pitch0.1um_Y_60 / Pitch0.01um_Y_40 三組
- 外部 GMF：使用者將重建 BMP 餵外部視覺定位工具產生 `GMF_score.txt`，由 `r40_external_compare.py` 解析
- 量測日期：2026-05-11

## 五點 trade-off 完整結果

COMBO 基準：8 px `0.154515`、0.8 px `0.131560`、0.08 px `0.099891`。

| α | 8 px step_std | Δ vs COMBO | 0.8 px step_std | Δ vs COMBO | 0.08 px step_std | Δ vs COMBO | 自動 verdict（3 % 升級上限） |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0.00（a030） | `0.143794` | `−6.94%` | `0.140008` | `+6.42%` | `0.083941` | `−15.97%` | `PASS_TRADEOFF`（7 % 容忍區）|
| 0.25 | `0.146505` | `−5.18%` | `0.133546` | `+1.51%` | `0.100400` | `+0.51%` | **`PASS_UPGRADE_GUARD`** |
| 0.50 | `0.151365` | `−2.01%` | `0.149209` | `+13.42%` | `0.093177` | `−6.73%` | `RESEARCH_CAPACITY_ONLY` |
| 0.75 | `0.144254` | `−6.62%` | `0.152095` | `+15.61%` | `0.111468` | `+11.59%` | `RESEARCH_CAPACITY_ONLY` |
| 1.00（a043） | `0.145379` | `−5.91%` | `0.127411` | `−3.15%` | `0.121382` | `+21.52%` | `RESEARCH_CAPACITY_ONLY` |

## 觀察

### α=0.25 是唯一過 3 % 升級上限的點

α=0.25 三尺度 Δ 全部在 ±5.18 % 內：

- 8 px `−5.18%`（改善）
- 0.8 px `+1.51%`（退步但小於 3 %）
- 0.08 px `+0.51%`（退步但小於 3 %）

`r40_external_compare.py` 用預設 `upgrade_cap_pct=3.0` 標 `PASS_UPGRADE_GUARD`——意思是三尺度都沒超過 3 % 升級上限。專案歷史上至 2026-05-11 為止，沒有任何升級候選同時在三個外部 GMF 尺度都在 3 % 內：

- COMBO 是基準
- R33：0.8 px 改善 9.5 %、0.08 px 改善 13.6 %（被列為 GMF extreme alternate）
- R38v2：0.8 px +2.0 %、0.08 px +6.6 %（被列為 visual priority alternate）
- a030：0.8 px +6.42 %（過 7 % 容忍區但超過 3 % 上限）
- a045：8 px +22.80 %
- a042 / a043：各有單一尺度超過 7 %

α=0.25 (`r39r40_avg_a025`) 是這個 sweep 系列首次出現的 `PASS_UPGRADE_GUARD` 結果，但**這是 verdict 標籤的事實紀錄，升級決策本身留給專案 owner**。

### 中間 α 跟線性外推不符

若取 α=0 跟 α=1 兩端做線性插值，預估的 trade-off：

| α | 8 px Δ 預估 | 8 px Δ 實際 | 0.8 px Δ 預估 | 0.8 px Δ 實際 | 0.08 px Δ 預估 | 0.08 px Δ 實際 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.25 | `−6.69%` | `−5.18%` | `+4.03%` | `+1.51%` | `−6.60%` | `+0.51%` |
| 0.50 | `−6.43%` | `−2.01%` | `+1.64%` | `+13.42%` | `+2.78%` | `−6.73%` |
| 0.75 | `−6.17%` | `−6.62%` | `−0.75%` | `+15.61%` | `+12.15%` | `+11.59%` |

α=0.25 跟 α=0.75 的 8 px 差距較小；但 0.8 px 在 α=0.50 / 0.75 實際遠高於預估（凸點到 +13 % / +15 %），0.08 px 在 α=0.25 比預估好很多（+0.51% vs −6.60%）、α=0.50 走負方向（−6.73% vs +2.78%）。

也就是說 α=0.25 在 0.08 px 軸出現一個比兩端都好的「插值意外」，但 α=0.50 / 0.75 在 0.8 px 軸出現一個比兩端都差的「插值反彈」。整體看，weight averaging 在 α 軸上不是平滑插值——這跟 R40 α 補密 sweep（2026-05-11）觀察到的非線性一致。

### 顯微跟形狀重建能力（暫未量測）

本實驗只跑外部 ring GMF 三尺度，沒對中間 α 的 R40 micro_val_unseen 跟 R39 shape_val_unseen 跑詳細指標。未來若要把 α=0.25 推升正式替代，需要補：

- α=0.25 在 R40 micro_val_unseen（PSNR / SSIM / HF / Edge / 邊界 F1 / 形狀錯誤）
- α=0.25 在 R39 shape_val_unseen（同樣指標）
- 視覺對比 sheet（跟 a030 / a043 / COMBO 四聯比較）

## 產物

### Checkpoint

- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a050/best_tradeoff.pth.tar`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a075/best_tradeoff.pth.tar`

### 外部 ring 重建

- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260511_151845/pitch{1um_y_100_odd,0p1um_y_60_odd,0p01um_y_40_odd}\`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a050/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260511_151845/pitch{...}\`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a075/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260511_151845/pitch{...}\`

### 外部 GMF 解析結果

- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/external_compare_summary.json`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a050/external_compare_summary.json`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a075/external_compare_summary.json`

### 各 α 報告

- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a050_EXTERNAL_COMPARE.md`
- `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a075_EXTERNAL_COMPARE.md`

## 方法

- 兩個 source checkpoint：R39 a030（`results/weight_sweep/checkpoints/a030/best_tradeoff.pth.tar`）跟 R40 a043（`Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/checkpoints/a043/best_tradeoff.pth.tar`）。
- 線性插值：`(1−α) * sd_a030 + α * sd_a043`；非浮點 tensor（如 BatchNorm `num_batches_tracked`）取 sd_a043。
- 外部 ring 重建沿用既有 `Tools/RunRepresentativeExternalRecon.ps1`，input 來自 NTU 影像集 Pitch1um/Pitch0.1um/Pitch0.01um Cropped_Output 各 101/61/41 張。
- 外部 GMF：使用者送 BMP 給外部視覺定位工具產生 `GMF_score.txt`，每張取 PosY，依時間排序，計算 step_std（連續兩張 PosY 差的標準差），移除 `|z|>5` outlier。
- 自動 verdict：`r40_external_compare.py` 用 `upgrade_cap_pct=3.0` 預設；`PASS_UPGRADE_GUARD` 表示三尺度都在 ±3 % 內，`PASS_TRADEOFF` 表示在 7 % 替代容忍區內但超過 3 % 上限，`RESEARCH_CAPACITY_ONLY` 表示至少一尺度超出 7 % 容忍區。
- 升級判定本身留給專案 owner，本報告只記錄量測事實。
