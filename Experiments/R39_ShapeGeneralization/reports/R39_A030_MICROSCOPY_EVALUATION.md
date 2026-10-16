# R39 a030 在多樣顯微圖形上的詳細評估

## 摘要

本評估目的是把 a030（`r39_combo_strong_avg_a030`，COMBO 與 R39_strong 在 alpha=0.30 的權重平均）
在不同類型顯微結構重建上的表現，跟 COMBO 直接對比。所有評估都重用既有重建，沒有跑新的 inference。

本份報告只忠實紀錄觀察與數字，不下 verdict、不寫推薦。

2026-05-10 補測：把 R40 a045（R40 路線在 alpha=0.45 的權重平均，本地三尺度環形守門過、外部 8 px 退步 +22.80%）拉進來作第三個對比候選，產生 R39 shape_val_unseen 上的新重建（210 張）。下面對比表跟「R40 a045 補測對比」一節都已包含三方對照。

## 測試集

| 資料集 | 場景類型 | 對數 | 重建路徑 |
|---|---|---:|---|
| R39 `shape_val_unseen` | 訓練分布內：純幾何形狀 7 類（三角形、圓、矩形、橢圓、多邊形、簡單混合、複雜混合） | 210 | `results/weight_sweep/shape_recon/{a000\|a030}` |
| R40 `micro_val_unseen` | 訓練分布外：5 類顯微結構（細線/格、IC 風格大區塊、紋理、邊緣缺陷、混合場景） | 100 | `Experiments/R40_MicroscopyFeatureCoverage/results/micro_recon` |

兩個資料集都用同一套指標重新計算：PSNR、SSIM、高頻保留比、邊緣能量比、對比保留比、邊界 F1、
形狀錯誤分數（R44G），讓 in-distribution 跟 out-of-distribution 的數字直接可比。

## R40 micro_val_unseen 逐 stage 數字

### a030 vs COMBO PSNR

| Stage | COMBO | a030 | a030 - COMBO |
|---|---:|---:|---:|
| stage_29_micro_lines_grid | 17.7067 | 18.3261 | +0.6194 |
| stage_30_micro_large_regions | 23.1418 | 26.6334 | +3.4916 |
| stage_31_micro_textures | 27.0644 | 28.2059 | +1.1415 |
| stage_32_micro_edge_defects | 23.8592 | 27.5255 | +3.6663 |
| stage_33_micro_mixed_fields | 21.8909 | 24.4705 | +2.5796 |

（正值=a030 比 COMBO 高）

### a030 vs COMBO 邊界 F1

| Stage | COMBO | a030 | a030 - COMBO |
|---|---:|---:|---:|
| stage_29_micro_lines_grid | 0.2431 | 0.3654 | +0.1223 |
| stage_30_micro_large_regions | 0.4641 | 0.4922 | +0.0281 |
| stage_31_micro_textures | 0.4097 | 0.4835 | +0.0738 |
| stage_32_micro_edge_defects | 0.6878 | 0.6966 | +0.0088 |
| stage_33_micro_mixed_fields | 0.6525 | 0.6895 | +0.0370 |

（正值=a030 比 COMBO 高）

### a030 vs COMBO 形狀錯誤分數

| Stage | COMBO | a030 | a030 - COMBO |
|---|---:|---:|---:|
| stage_29_micro_lines_grid | 0.6548 | 0.5845 | -0.0703 |
| stage_30_micro_large_regions | 1.1003 | 1.1570 | +0.0567 |
| stage_31_micro_textures | 0.3879 | 0.3612 | -0.0267 |
| stage_32_micro_edge_defects | 0.6875 | 0.5517 | -0.1358 |
| stage_33_micro_mixed_fields | 0.9141 | 0.8555 | -0.0586 |

（負值=a030 比 COMBO 低）

### 整體（5 個 stage 平均）

| 指標 | COMBO | a030 | a030 - COMBO |
|---|---:|---:|---:|
| PSNR | 22.7326 | 25.0323 | +2.2997 |
| SSIM | 0.8588 | 0.8904 | +0.0316 |
| HF retention | 0.2234 | 0.2206 | -0.0028 |
| Edge retention | 0.6607 | 0.6181 | -0.0426 |
| Contrast retention | 0.8857 | 0.9252 | +0.0395 |
| 邊界 F1 | 0.4914 | 0.5454 | +0.0540 |
| 形狀錯誤 | 0.7489 | 0.7020 | -0.0469 |

## R39 shape_val_unseen（訓練分布內對照）

### a030 vs COMBO PSNR

| Stage | COMBO | a030 | a030 - COMBO |
|---|---:|---:|---:|
| stage_01_triangles | 22.6721 | 24.2827 | +1.6106 |
| stage_02_circles | 23.1395 | 25.9399 | +2.8004 |
| stage_03_rectangles | 22.2520 | 23.8121 | +1.5601 |
| stage_04_ellipses | 25.3973 | 27.3630 | +1.9657 |
| stage_05_polygons | 22.5575 | 25.2764 | +2.7189 |
| stage_06_mixed_simple | 22.5800 | 25.2347 | +2.6547 |
| stage_07_mixed_complex | 21.2897 | 23.3196 | +2.0299 |

（正值=a030 比 COMBO 高）

### 整體（7 個 stage 平均）

| 指標 | COMBO | a030 | a030 - COMBO |
|---|---:|---:|---:|
| PSNR | 22.8411 | 25.0326 | +2.1915 |
| SSIM | 0.9078 | 0.9461 | +0.0383 |
| HF retention | 0.3021 | 0.4598 | +0.1577 |
| Edge retention | 0.7913 | 0.8797 | +0.0884 |
| Contrast retention | 0.8118 | 0.8864 | +0.0746 |
| 邊界 F1 | 0.8230 | 0.8752 | +0.0522 |
| 形狀錯誤 | 0.3386 | 0.2718 | -0.0668 |

## 跨資料集 headline

| 資料集 | 模型 | PSNR | SSIM | HF | Edge | Contrast | ring 8px | ring 0.8px | ring 0.08px |
|---|---|---|---|---|---|---|---|---|---|
| R40 micro_val_unseen | COMBO | 22.7326 | 0.8588 | 0.2234 | 0.6607 | 0.8857 |  |  |  |
| R40 micro_val_unseen | a030 | 25.0323 | 0.8904 | 0.2206 | 0.6181 | 0.9252 |  |  |  |
| R39 shape_val_unseen | COMBO | 22.8411 | 0.8502 |  |  |  | 0.1389 | 0.1509 | 0.1185 |
| R39 shape_val_unseen | a030 | 25.0326 | 0.8798 |  |  |  | 0.1384 | 0.1507 | 0.1114 |

## 視覺對比

![a030 vs COMBO 多 stage 代表](results/a030_microscopy_eval/visuals/contact_sheet_r40.png)

每個 stage 取四個代表性 frame，三聯為 GT、COMBO 重建、a030 重建。

## 觀察記錄

（以下為事實描述，依數字與視覺整理；判斷與下一步留給後續決策。）

- R40 微觀資料集上，a030 對 5 個 stage 的 PSNR 變化範圍為 `+0.6194` 到 `+3.6663` dB；
  五個 stage 全部 a030 比 COMBO 高的 stage 數：5/5。
- R39 形狀資料集（訓練分布內）上，a030 對 7 個 stage 的 PSNR 變化範圍為 `+1.5601` 到 `+2.8004` dB；
  全部 a030 比 COMBO 高的 stage 數：7/7。
- R40 邊界 F1：a030 對 COMBO 變化範圍 `+0.0088` 到 `+0.1223`；
  a030 較高的 stage 數：5/5。
- R40 形狀錯誤分數（越低越好）：a030 對 COMBO 變化範圍 `-0.1358` 到 `+0.0567`；
  a030 較低（即較好）的 stage 數：4/5。

逐 stage 細節見上面三張 PSNR / 邊界 F1 / 形狀錯誤分數對比表。

分布內 vs 分布外對照（PSNR）：

- R39 shape_val_unseen 七類平均 PSNR delta：`+2.1915` dB（訓練分布內）。
- R40 micro_val_unseen 五類平均 PSNR delta：`+2.2997` dB（訓練分布外）。

## R40 a045 對比拼圖

把 R40 a045（R40 路線在 alpha=0.45 的權重平均，本地三尺度環形守門過、外部 8 px 退步 +22.80%）
拉進來跟 a030 / COMBO 並列，看「廣譜變強」 vs 「換顯微強度」這個取捨。

### R39 shape_val_unseen 逐 stage PSNR（訓練分布內）

| Stage | COMBO | a030 | R40 a045 | a030 - COMBO | R40 a045 - COMBO |
|---|---|---|---|---|---|
| stage_01_triangles | 22.6721 | 24.2827 | 25.8914 | +1.6106 | +3.2193 |
| stage_02_circles | 23.1395 | 25.9399 | 28.1914 | +2.8004 | +5.0519 |
| stage_03_rectangles | 22.2520 | 23.8121 | 25.2591 | +1.5601 | +3.0071 |
| stage_04_ellipses | 25.3973 | 27.3630 | 29.1682 | +1.9657 | +3.7709 |
| stage_05_polygons | 22.5575 | 25.2764 | 27.6274 | +2.7189 | +5.0699 |
| stage_06_mixed_simple | 22.5800 | 25.2347 | 27.3018 | +2.6547 | +4.7218 |
| stage_07_mixed_complex | 21.2897 | 23.3196 | 24.9640 | +2.0299 | +3.6743 |

（正值=該模型比 COMBO 高）

### R39 shape_val_unseen 逐 stage 形狀錯誤分數

| Stage | COMBO | a030 | R40 a045 | a030 - COMBO | R40 a045 - COMBO |
|---|---|---|---|---|---|
| stage_01_triangles | 0.3430 | 0.2811 | 0.2679 | -0.0619 | -0.0751 |
| stage_02_circles | 0.2981 | 0.1919 | 0.1878 | -0.1062 | -0.1103 |
| stage_03_rectangles | 0.3135 | 0.2714 | 0.2589 | -0.0421 | -0.0546 |
| stage_04_ellipses | 0.3120 | 0.2596 | 0.2546 | -0.0524 | -0.0574 |
| stage_05_polygons | 0.4284 | 0.3238 | 0.3073 | -0.1046 | -0.1211 |
| stage_06_mixed_simple | 0.2837 | 0.2316 | 0.1986 | -0.0521 | -0.0851 |
| stage_07_mixed_complex | 0.3916 | 0.3433 | 0.2933 | -0.0483 | -0.0983 |

（負值=該模型比 COMBO 低）

### R39 shape_val_unseen 整體（7 個 stage 平均）

| 指標 | COMBO | a030 | R40 a045 |
|---|---:|---:|---:|
| PSNR | 22.8411 | 25.0326 | 26.9147 |
| SSIM | 0.9078 | 0.9461 | 0.9633 |
| HF retention | 0.3021 | 0.4598 | 0.5083 |
| Edge retention | 0.7913 | 0.8797 | 0.9925 |
| Contrast retention | 0.8118 | 0.8864 | 0.9643 |
| 邊界 F1 | 0.8230 | 0.8752 | 0.9009 |
| 形狀錯誤 | 0.3386 | 0.2718 | 0.2526 |

### R40 micro_val_unseen 逐 stage PSNR（訓練分布外）

| Stage | COMBO | a030 | R40 a045 | a030 - COMBO | R40 a045 - COMBO |
|---|---|---|---|---|---|
| stage_29_micro_lines_grid | 17.7067 | 18.3261 | 19.5394 | +0.6194 | +1.8327 |
| stage_30_micro_large_regions | 23.1418 | 26.6334 | 28.6523 | +3.4916 | +5.5105 |
| stage_31_micro_textures | 27.0644 | 28.2059 | 31.1857 | +1.1415 | +4.1213 |
| stage_32_micro_edge_defects | 23.8592 | 27.5255 | 29.3510 | +3.6663 | +5.4918 |
| stage_33_micro_mixed_fields | 21.8909 | 24.4705 | 25.7272 | +2.5796 | +3.8363 |

（正值=該模型比 COMBO 高）

### R40 micro_val_unseen 逐 stage 邊界 F1

| Stage | COMBO | a030 | R40 a045 | a030 - COMBO | R40 a045 - COMBO |
|---|---|---|---|---|---|
| stage_29_micro_lines_grid | 0.2431 | 0.3654 | 0.4428 | +0.1223 | +0.1997 |
| stage_30_micro_large_regions | 0.4641 | 0.4922 | 0.5137 | +0.0281 | +0.0496 |
| stage_31_micro_textures | 0.4097 | 0.4835 | 0.6689 | +0.0738 | +0.2592 |
| stage_32_micro_edge_defects | 0.6878 | 0.6966 | 0.7391 | +0.0088 | +0.0513 |
| stage_33_micro_mixed_fields | 0.6525 | 0.6895 | 0.7175 | +0.0370 | +0.0650 |

（正值=該模型比 COMBO 高）

### R40 micro_val_unseen 逐 stage 形狀錯誤分數

| Stage | COMBO | a030 | R40 a045 | a030 - COMBO | R40 a045 - COMBO |
|---|---|---|---|---|---|
| stage_29_micro_lines_grid | 0.6548 | 0.5845 | 0.5750 | -0.0703 | -0.0798 |
| stage_30_micro_large_regions | 1.1003 | 1.1570 | 1.1552 | +0.0567 | +0.0549 |
| stage_31_micro_textures | 0.3879 | 0.3612 | 0.2739 | -0.0267 | -0.1140 |
| stage_32_micro_edge_defects | 0.6875 | 0.5517 | 0.5325 | -0.1358 | -0.1550 |
| stage_33_micro_mixed_fields | 0.9141 | 0.8555 | 0.8784 | -0.0586 | -0.0357 |

（負值=該模型比 COMBO 低）

### R40 micro_val_unseen 整體（5 個 stage 平均）

| 指標 | COMBO | a030 | R40 a045 |
|---|---:|---:|---:|
| PSNR | 22.7326 | 25.0323 | 26.8911 |
| SSIM | 0.8588 | 0.8904 | 0.9199 |
| HF retention | 0.2234 | 0.2206 | 0.3414 |
| Edge retention | 0.6607 | 0.6181 | 0.7459 |
| Contrast retention | 0.8857 | 0.9252 | 0.9554 |
| 邊界 F1 | 0.4914 | 0.5454 | 0.6164 |
| 形狀錯誤 | 0.7489 | 0.7020 | 0.6830 |

### 觀察

- R39 shape_val_unseen 七類 PSNR：a030 對 COMBO 全勝 7/7；R40 a045 對 COMBO 勝出 7/7。
  PSNR 平均差距 vs COMBO：a030 `+2.1915` dB、R40 a045 `+4.0736` dB。
- R40 micro_val_unseen 五類 PSNR：a030 對 COMBO 勝出 5/5；R40 a045 對 COMBO 勝出 5/5。
  PSNR 平均差距 vs COMBO：a030 `+2.2997` dB、R40 a045 `+4.1585` dB。
- R40 micro_val_unseen 形狀錯誤（越低越好）：a030 比 COMBO 低的 stage 數 4/5；R40 a045 比 COMBO 低的 stage 數 4/5。

跨資料集對照（R40 a045）：
- R39 整體 PSNR：COMBO `22.8411`、a030 `25.0326`、R40 a045 `26.9147`
- R40 整體 PSNR：COMBO `22.7326`、a030 `25.0323`、R40 a045 `26.8911`
- R40 a045 在訓練分布外（R40）跟分布內（R39）的整體 PSNR 落差：`-0.0236` dB

外部 GMF 升級門檻方向（已知數字，這次沒重算）：
- COMBO 是基準。
- a030 三尺度都在容忍區內：8 px −6.94%、0.8 px +6.42%、0.08 px −15.97%（PASS_TRADEOFF）。
- R40 a045 8 px 退 +22.80%（超出 3% 升級上限與 7% 替代容忍區），0.8 px +1.33%、0.08 px −2.85%（RESEARCH_CAPACITY_ONLY）。

## 產物

- `results/a030_microscopy_eval/per_pair_metrics.csv`：所有資料集所有 pair 的逐張指標。
- `results/a030_microscopy_eval/stage_summary.csv`：逐資料集逐 stage 平均。
- `results/a030_microscopy_eval/overall_summary.csv`：每個資料集的整體平均。
- `results/a030_microscopy_eval/cross_dataset_headline.json`：a030 / COMBO 跨資料集 headline。
- `results/a030_microscopy_eval/visuals/contact_sheet_r40.png`：R40 5 個 stage × 4 個 frame 三聯對比。
- `results/a030_microscopy_eval/r40_a045_on_shape/`：R40 a045 在 R39 shape_val_unseen 的重建 BMP（2026-05-10 inference）。
- `results/a030_microscopy_eval/delta_three_*.csv`：三方對比的逐 stage pivot 表（PSNR、邊界 F1、形狀錯誤）。

## 方法

- 重建：直接讀取 R40 已有的 a030（`*_20260430_121954`）與 COMBO（`*_20260408_003525`）BMP；
  R39 shape_val_unseen 用 sweep 已存的 `shape_recon/a030` 與 `shape_recon/a000`（即 COMBO）。
  R40 a045 在 R40 micro_val_unseen 用既有 `combo_best_low_alpha/micro_recon/a045/` 重建；
  R40 a045 在 R39 shape_val_unseen 由 2026-05-10 補跑 inference 產生（`results/a030_microscopy_eval/r40_a045_on_shape/`）。
- PSNR / SSIM / 高頻保留比 / 邊緣能量比 / 對比保留比：直接用 `r40_micro_metrics.image_metric_row`。
- 邊界 F1 / 形狀錯誤分數：用 `r44_motion_metrics.matched_gradient_boundary` 取每張 GT、預測各自 3% 強梯度像素為邊界遮罩，
  再套 `r44g_boundary_shape_metrics.boundary_shape_metrics`。GT 跟預測用相同方法取 boundary 是為了讓 R39/R40 兩套
  資料集（沒附 boundary mask）跟 R42/R44（有 boundary mask）一致可比。
- Contact sheet：每 stage 等距挑 4 個 frame，BMP 縮放至 192×204 三聯顯示。
