# R45C 分區理想上限與殘差診斷

## 摘要

- 本診斷不訓練模型，沿用 R44 既有的 motion_val_unseen 重建結果。
- 每張影像切成 patch，對每個 patch 計算 7 個候選模型的 R44G 形狀錯誤分數，找分區理想上限。
- 對比 R45B 整張理想上限改善 `33.42%`、固定分族理想上限改善 `12.30%`。
- 同時看：在分區理想上限選到的老師上，邊界帶殘差方向是否乾淨。

## 主要結果

| Patch 大小 | 有效 patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |
|---:|---:|---:|---:|---:|
| 64 | 48 | 0.8981 | 0.1981 | 77.94% |

R45B 整張層級基準（參考）：R44B from R42 整張平均 `0.3384`，整張理想上限 `0.2253`，改善 `33.42%`；
固定分族理想上限改善 `12.30%`。

## 殘差方向乾淨比例

若分區理想老師在邊界帶 `mean_error_reduction > 0` 比例越高，代表分區層級老師優勢比 R45B image-level 更乾淨。

| Patch 大小 | 含老師理想 patch 數 | mean_reduction>0 比例 | better_fraction>0.5 比例 | 兩條件都滿足比例 | 平均 mean_reduction | 平均 better_fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 64 | 44 | 0.00% | 0.00% | 0.00% | -0.1006 | 0.0597 |

## 分族分析

### Patch 64

| 結構類型 | Patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |
|---|---:|---:|---:|---:|
| large_regions | 48 | 0.8981 | 0.1981 | 77.94% |

## 分區理想選擇老師統計

### Patch 64

| 模型 | 被選次數 | 占比 |
|---|---:|---:|
| R44B from COMBO | 21 | 43.75% |
| R41 direct | 18 | 37.50% |
| R44B from R42 | 4 | 8.33% |
| R44B from R40 | 4 | 8.33% |
| R44C static heavy | 1 | 2.08% |

## 判定

分區理想上限改善 `77.94%` ≥ 25%，**但殘差方向乾淨比例只有 `0.00%` < 50%**。形狀分數有空間，但老師依然不乾淨；selector 學形狀標籤恐學到風格與過衝。**建議轉路線 B（多模型路由）**，或先研究新的 supervision 訊號讓 selector 不依賴老師形狀標籤。

## 產物

- `results/r45c_region_oracle/r45c_patch_rows_<size>.csv`：每 patch、每模型的形狀錯誤分數。
- `results/r45c_region_oracle/r45c_patch_residuals_<size>.csv`：每 patch、每老師的邊界帶殘差統計。
- `results/r45c_region_oracle/r45c_region_oracle_summary.json`：理想上限與殘差乾淨比例彙整。

## 方法

- Patch 切法：non-overlapping，最後一塊向內錨定避免出界；最小邊界 GT 像素數 `8`。
- 邊界帶：GT boundary 經 `7x7` dilation（與 R45B 一致）。
- 預測 boundary：整張影像用 `matched_gradient_boundary` 取與 GT 等量像素，再切 patch。
- 形狀錯誤：直接套 R44G 的 `boundary_shape_metrics`。Patch 內若 component bbox 被 reject（min_pixels=16, min_span=10），對應 component metric 走 default penalty，但 ranking 仍成立。
- 對比基準：R44B from R42（與 R45B 一致）；目標分族 `large_regions` + `mixed_fields`。
