# R39R40 a025 全面能力評估

## 摘要

`r39r40_complementary_avg_a025`（R39 a030 與 R40 a043 在 α=0.25 的權重平均）已在外部 GMF 拿到 `PASS_UPGRADE_GUARD`（三尺度都在 ±5.18%）。本評估補上升級為正式替代候選前的四項驗證：

1. R40 `micro_val_unseen`（顯微特徵 5 類 / 100 對）詳細指標
2. R39 `shape_val_unseen`（純幾何 7 類 / 210 對）詳細指標
3. 視覺四項統計（gradient magnitude / edge steepness / contrast / edge contrast）—— sharp band 還是 soft band
4. 五聯視覺對比 sheet（GT / COMBO / a030 / a043 / a025）

**升級紀錄（2026-05-11）**：本檔四項驗證全過後，a025 於 2026-05-11 升級為 approved alternate（role: `balanced_full_spectrum_alternate`，跟 R33 GMF 極致 / R38v2 視覺優先 並列為第三個特化位置）。`ESTIMATOR_POLICY.json` 的 `approved_alternates` 已加 entry；`PROJECT_STATE.md` Quick Handoff 區跟「## 2. Approved Alternates」section 同步更新。

## R40 micro_val_unseen 整體（5 類平均）

| 指標 | COMBO | a030 | a043 | R39R40_a025 |
|---|---:|---:|---:|---:|
| PSNR | `22.7326` | `25.0323` | `26.7150` | `25.4091` |
| SSIM | `0.8588` | `0.8904` | `0.9176` | `0.8968` |
| HF retention | `0.2234` | `0.2206` | `0.3250` | `0.2428` |
| Edge retention | `0.6607` | `0.6181` | `0.7386` | `0.6434` |
| Contrast retention | `0.8857` | `0.9252` | `0.9534` | `0.9348` |
| 邊界 F1 | `0.4914` | `0.5454` | `0.6103` | `0.5635` |
| 形狀錯誤（越低越好） | `0.7489` | `0.7020` | `0.6845` | `0.6989` |

## R39 shape_val_unseen 整體（7 類平均）

| 指標 | COMBO | a030 | a043 | R39R40_a025 |
|---|---:|---:|---:|---:|
| PSNR | `22.8411` | `25.0326` | `26.7544` | `25.5098` |
| SSIM | `0.9078` | `0.9461` | `0.9621` | `0.9512` |
| HF retention | `0.3021` | `0.4598` | `0.5007` | `0.4740` |
| Edge retention | `0.7913` | `0.8797` | `0.9849` | `0.9087` |
| Contrast retention | `0.8118` | `0.8864` | `0.9592` | `0.9072` |
| 邊界 F1 | `0.8230` | `0.8752` | `0.8982` | `0.8816` |
| 形狀錯誤（越低越好） | `0.3386` | `0.2718` | `0.2557` | `0.2683` |

## R40 micro_val_unseen 逐 stage（PSNR）

| stage | COMBO | a030 | a043 | R39R40_a025 |
|---|---:|---:|---:|---:|
| stage_29_micro_lines_grid | `17.7067` | `18.3261` | `19.4414` | `18.5564` |
| stage_30_micro_large_regions | `23.1418` | `26.6334` | `28.4800` | `27.1094` |
| stage_31_micro_textures | `27.0644` | `28.2059` | `30.9453` | `28.7351` |
| stage_32_micro_edge_defects | `23.8592` | `27.5255` | `29.0793` | `27.8573` |
| stage_33_micro_mixed_fields | `21.8909` | `24.4705` | `25.6291` | `24.7873` |

## R39 shape_val_unseen 逐 stage（PSNR）

| stage | COMBO | a030 | a043 | R39R40_a025 |
|---|---:|---:|---:|---:|
| stage_01_triangles | `22.6721` | `24.2827` | `25.7382` | `24.6495` |
| stage_02_circles | `23.1395` | `25.9399` | `28.0209` | `26.5521` |
| stage_03_rectangles | `22.2520` | `23.8121` | `25.1209` | `24.1482` |
| stage_04_ellipses | `25.3973` | `27.3630` | `29.0177` | `27.8257` |
| stage_05_polygons | `22.5575` | `25.2764` | `27.4278` | `25.8797` |
| stage_06_mixed_simple | `22.5800` | `25.2347` | `27.1342` | `25.7844` |
| stage_07_mixed_complex | `21.2897` | `23.3196` | `24.8210` | `23.7289` |

## 視覺四項統計（ring 重建 frame-wise mean）

依 R39_RESULTS 的 inline 公式計算（灰階 Sobel 梯度幅值 / p95 梯度 / 像素 std / p99−p1）。

| 模型 | pitch | gradient_magnitude_mean | edge_steepness_p95 | contrast_std | edge_contrast_p99−p1 |
|---|---|---:|---:|---:|---:|
| COMBO | pitch1um_y_100_odd | `0.008000` | `0.102400` | `0.111200` | `0.455100` |
| COMBO | pitch0p1um_y_60_odd | `0.010900` | `0.140000` | `0.126800` | `0.423500` |
| COMBO | pitch0p01um_y_40_odd | `0.010900` | `0.139500` | `0.126800` | `0.420700` |
| a030 | pitch1um_y_100_odd | `0.007700` | `0.096600` | `0.108300` | `0.441200` |
| a030 | pitch0p1um_y_60_odd | `0.010600` | `0.132200` | `0.124700` | `0.411800` |
| a030 | pitch0p01um_y_40_odd | `0.010500` | `0.131700` | `0.124600` | `0.411800` |
| a043 | pitch1um_y_100_odd | `0.008100` | `0.098300` | `0.113500` | `0.460300` |
| a043 | pitch0p1um_y_60_odd | `0.011000` | `0.131700` | `0.131200` | `0.434500` |
| a043 | pitch0p01um_y_40_odd | `0.011000` | `0.131400` | `0.131100` | `0.434100` |
| R39R40_a025 | pitch1um_y_100_odd | `0.007800` | `0.097300` | `0.109800` | `0.447300` |
| R39R40_a025 | pitch0p1um_y_60_odd | `0.010700` | `0.131200` | `0.126500` | `0.419500` |
| R39R40_a025 | pitch0p01um_y_40_odd | `0.010700` | `0.130700` | `0.126400` | `0.419500` |

### COMBO 為基準，三 pitch 平均後對比

| 指標 | COMBO | a030 Δ% | a043 Δ% | R39R40_a025 Δ% |
|---|---:|---:|---:|---:|
| gradient_magnitude_mean | `0.009933` | `-3.36%` | `+1.01%` | `-2.01%` |
| edge_steepness_p95 | `0.127300` | `-5.60%` | `-5.37%` | `-5.94%` |
| contrast_std | `0.121600` | `-1.97%` | `+3.02%` | `-0.58%` |
| edge_contrast_p99_minus_p1 | `0.433100` | `-2.66%` | `+2.28%` | `-1.00%` |

### 視覺帶定位（edge_steepness_p95 對 COMBO 的偏移量）

依 R39_RESULTS 的視覺帶分類，R30 是 0%、COMBO/R38v2 約 +89.4%、R33 是 −22%（soft band）：

- a030: vs COMBO `-5.60%`、推算 vs R30 約 `+78.8%`
- a043: vs COMBO `-5.37%`、推算 vs R30 約 `+79.2%`
- R39R40_a025: vs COMBO `-5.94%`、推算 vs R30 約 `+78.1%`

## 五聯視覺對比

### R40 micro_val_unseen 五聯（5 顯微類 × 4 frame）

`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\visuals\contact_sheet_a025_micro_five_panel.png`

GT / COMBO / a030 / R40 a043 / R39R40_a025 五欄對比，cell 大小 260×260。

逐 stage 肉眼觀察：

- **lines_grid（細線 / 格）**：COMBO 把格線抹得最厲害；a030 留下模糊輪廓但細節含糊；a043 格線最清楚；**a025 比 a030 多保留一些格線**，介於兩者之間
- **large_regions（IC 風格大區塊）**：四個重建都還原大形狀，邊界銳度排序 a043 > a025 > a030 > COMBO
- **textures（紋理）**：差別最明顯——COMBO 跟 a030 把紋理當雜訊抹掉，a043 留有顆粒，**a025 看得到淡淡紋理但比 a043 弱**
- **edge_defects（邊緣缺陷）**：四個都看得到缺陷凸起，a043 跟 a025 邊角較銳利
- **mixed_fields（混合場景）**：複雜場景下 a043 跟 a025 都比 COMBO / a030 更接近 GT 的整體層次

### R39 shape_val_unseen 五聯（7 形狀類 × 3 frame）

`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\visuals\contact_sheet_a025_shape_five_panel.png`

純幾何形狀的差異比顯微小很多。COMBO 邊界較糊、其他三個（a030 / a043 / a025）都重建得不錯。a025 跟 a030 視覺幾乎一樣，跟 a043 比稍微淡一點銳度。

### 四聯版本（沒有 a043）

`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\visuals\contact_sheet_a025_four_panel.png`

cell 較大（320×320），純粹聚焦 GT / COMBO / a030 / a025 三個候選對比。

## 產物

- 逐張指標：`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\capability_eval\per_pair_metrics.csv`
- 逐 stage 平均：`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\capability_eval\stage_summary.csv`
- 整體平均：`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\capability_eval\overall_summary.csv`
- 視覺四項統計：`D:\GMM_2_Final\Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\capability_eval\visual_stats.csv`
- 視覺對比 sheet：`D:/GMM_2_Final/Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_four_panel.png`（由 r39r40_a025_four_panel_contact.py 產生）

## 方法

- 顯微/形狀指標：複用 `r39_a030_microscopy_evaluation.evaluate_pair`，含 PSNR / SSIM / HF retention / Edge retention / Contrast retention（R40 micro_metrics）+ 邊界 F1 / 形狀錯誤分數（R44G 邊界遮罩取 3% 強梯度後算）
- 視覺四項：對既有 ring 重建（COMBO 跟 a030 在 weight_sweep/ring_recon、a043 在 combo_best_low_alpha/ring_recon、a025 在 a030_x_a043_sweep/external_recon）逐 frame 用灰階 Sobel + percentile 算
- 推算 vs R30：用 `(1 + Δ%) × 1.894 − 1` 串接 R39_RESULTS 既有的視覺帶錨點（R30=0%、COMBO/R38v2=+89.4%、R33=−22%）
- 沒下 verdict 或推薦；升級判定留給專案 owner