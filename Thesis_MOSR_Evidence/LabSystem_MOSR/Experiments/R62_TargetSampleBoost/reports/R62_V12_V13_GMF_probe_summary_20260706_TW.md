# R62 V12/V13 GMF 探針摘要

日期：2026-07-06

## 目的

這輪測試不是要立刻宣稱新模型更好，而是驗證一件事：

> 如果把訓練目標更直接對準 GMF/邊界定位，100MG 位移資料的重建後穩定度是否會明顯超過目前最好的 V7。

## 新增嘗試

- V12：加入全圖邊界中心位移約束。
- V13：加入局部格子邊界中心位移約束，用來避免多個 pillar 互相抵銷，讓局部錯位被抓出來。

兩者都從 V7 最佳權重接著短訓練：

- 1 epoch
- 300 train batches
- batch size 8
- clean motion package：`r62_target_sample_boost_v4_motion_clean`

## 主要結果：100MG pairwise GMF

### 亮度 GMF

| 位移組 | Raw std um | V7 std um | V12 std um | V13 std um | 最好 |
|---|---:|---:|---:|---:|---|
| x_1um | 0.009536 | 0.009362 | 0.009386 | 0.009387 | V7 |
| x_0p5um | 0.052563 | 0.052373 | 0.052472 | 0.052461 | V7 |

### 邊界 GMF

| 位移組 | Raw std um | V7 std um | V12 std um | V13 std um | 最好 |
|---|---:|---:|---:|---:|---|
| x_1um | 0.009449 | 0.009017 | 0.009249 | 0.009403 | V7 |
| x_0p5um | 0.052380 | 0.052086 | 0.052253 | 0.052392 | V7 |

## 根因檢查

對 100MG x_0p5um，Raw 與重建後每一步位移起伏幾乎完全同步：

| 比較 | Raw 對候選逐步相關係數 | 候選與 Raw 的差異標準差 |
|---|---:|---:|
| Raw vs V7 | 0.999937 | 0.000614 um |
| Raw vs V12 | 0.999952 | 0.000518 um |
| Raw vs V13 | 0.999954 | 0.000510 um |

這表示 x_0p5um 的主要不穩定不是模型造成的定位噪聲，而是資料本身每一步共同存在的位移起伏。模型能改動的量約只有 0.0005 um 等級，但整體標準差約 0.052 um。

## ROI 掃描

同一張 100MG 影像上，不同 ROI 的 GMF 結果不同。V7 在某些 ROI 比目前主 ROI 更能看出改善。

### x_1um，邊界 GMF

| ROI | Raw std um | V7 std um | 改善 |
|---|---:|---:|---:|
| top_right_dark_pillar_array | 0.009449 | 0.009017 | 4.56% |
| upper_left_vertical_lines | 0.009324 | 0.009126 | 2.13% |
| bottom_left_bright_hole_array | 0.008670 | 0.008768 | -1.13% |

### x_0p5um，邊界 GMF

| ROI | Raw std um | V7 std um | 改善 |
|---|---:|---:|---:|
| upper_left_vertical_lines | 0.053105 | 0.051715 | 2.62% |
| top_right_dark_pillar_array | 0.052380 | 0.052086 | 0.56% |
| bottom_left_bright_hole_array | 0.052457 | 0.052288 | 0.32% |

右下水平線 ROI 在 x 位移上不可靠，平均步距接近 0，不建議用來做 x 方向位移分析。

## 判斷

目前不建議對 V12 或 V13 開長訓練，因為短探針已經顯示它們沒有超過 V7。  
目前主力仍應該是 V7。

比較合理的下一步不是盲目加長訓練，而是：

1. 用 V7 作為主力重建模型。
2. 論文中把位移穩定性分成兩層說明：
   - 模型可改善的定位噪聲。
   - 平台本身每一步實際位移起伏。
3. 若要展現模型價值，使用更能反映邊界定位的 ROI，例如：
   - 1 um：top-right dark pillar array。
   - 0.5 um：upper-left vertical lines。

## 主要輸出位置

- V12 訓練：`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_motion_center_v12_v12_motion_center_from_v7_probe_e1_mtb300_b8_20260706_20260706_042902`
- V13 訓練：`LabSystem_MOSR/Traing_Progress/training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r62_target_selfshift_local_motion_center_v13_v13_local_motion_center_from_v7_probe_e1_mtb300_b8_20260706_20260706_044344`
- V12 GMF：`reports/thesis_gmf_fit_v12_pairwise_intensity_20260706`、`reports/thesis_gmf_fit_v12_pairwise_edge_20260706`
- V13 GMF：`reports/thesis_gmf_fit_v13_pairwise_intensity_20260706`、`reports/thesis_gmf_fit_v13_pairwise_edge_20260706`
- ROI 掃描：`reports/roi_scan_pairwise_edge_raw_vs_v7_100mg_20260706`
