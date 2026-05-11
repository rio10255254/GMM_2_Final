# R45C 分區理想上限與殘差診斷

## 摘要

- 本診斷不訓練模型，沿用 R44 既有的 motion_val_unseen 重建結果。
- 每張影像切成 patch，對每個 patch 計算 7 個候選模型的 R44G 形狀錯誤分數，找分區理想上限。
- 對比 R45B 整張理想上限改善 `33.42%`、固定分族理想上限改善 `12.30%`。
- 同時看：在分區理想上限選到的老師上，邊界帶殘差方向是否乾淨。

## 主要結果

| Patch 大小 | 有效 patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |
|---:|---:|---:|---:|---:|
| 64 | 8887 | 0.6339 | 0.3804 | 40.00% |
| 128 | 3466 | 0.5145 | 0.2843 | 44.75% |

R45B 整張層級基準（參考）：R44B from R42 整張平均 `0.3384`，整張理想上限 `0.2253`，改善 `33.42%`；
固定分族理想上限改善 `12.30%`。

## 殘差方向乾淨比例

若分區理想老師在邊界帶 `mean_error_reduction > 0` 比例越高，代表分區層級老師優勢比 R45B image-level 更乾淨。

| Patch 大小 | 含老師理想 patch 數 | mean_reduction>0 比例 | better_fraction>0.5 比例 | 兩條件都滿足比例 | 平均 mean_reduction | 平均 better_fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 64 | 6649 | 7.61% | 4.18% | 3.68% | -0.0700 | 0.1590 |
| 128 | 2983 | 7.78% | 3.82% | 3.32% | -0.0660 | 0.1677 |

殘差乾淨比例極低（7-8%）跟 R45B image-level 觀察一致，但暴露一個更深問題：**形狀 oracle 選到的老師在 pixel 上反而比 base 差**。下節改用 pixel-residual oracle 對照。

## Pixel-residual oracle 對照

每個 patch 改用 `mean_error_reduction` 最高的老師當 oracle（正值代表老師在邊界帶絕對 pixel error 比 base 低）。

| Patch 大小 | Patch 數 | 老師能 pixel 改善 base 的 patch | 比例 | base 仍是 pixel 最佳的 patch | 平均改善（在改善 patch 上） |
|---:|---:|---:|---:|---:|---:|
| 64 | 8887 | 7462 | 83.97% | 1425 (16.03%) | `0.0030` |
| 128 | 3466 | 2981 | 86.01% | 485 (13.99%) | `0.0025` |

關鍵：**base 邊界帶平均絕對 pixel error 大約 `0.07–0.10`**（從 R45B 老師表反推），所以 pixel oracle 改善 `0.0025–0.0030` 相對 base 只有 `3–5%`。形狀 oracle 改善 40–45% 是個假象——形狀 metric 把 boundary mask 對齊算得很高，但 pixel 上其實沒有真正的分區能力分散空間。

## 兩個 oracle 老師選擇對照

形狀 oracle 王（R41 direct）跟 pixel oracle 王（R44H StepB region KD）幾乎不重疊。

| 模型 | 形狀 oracle 占比（patch 64） | pixel oracle 占比（patch 64） |
|---|---:|---:|
| R41 direct | 30.48% | 0.32% |
| R44B from R42（形狀 oracle 內含 base 自選） | 25.18% | — |
| R44B from COMBO | 17.55% | 1.25% |
| R44B from R40 | 10.26% | 2.14% |
| R42 best | 5.69% | 2.84% |
| **R44H StepB region KD** | 5.65% | **70.55%** |
| R44C static heavy | 5.18% | 6.88% |
| base R44B from R42（pixel 上仍最佳的 patch） | — | 16.03% |

R44B from COMBO 形狀分數第二高，但 pixel 殘差幾乎 worst（1.25%）。R41 direct 形狀分數最高但 pixel 殘差最差（0.32%）。R44H StepB region KD 形狀分數倒數但 pixel 絕對王（70.55%）。

這證實一個底層觀察：**形狀 metric（density、fragmentation、F-score、直邊、角點）跟 pixel quality 在這個資料集上是正交軸**。一個老師可以做出對齊很好的 boundary mask（高 F-score、密度接近 1.0），但 pixel 強度、紋理、過衝完全不對。反之亦然。

## R44H Step B 重新解讀

R44H Step B 在 R44 主報告被判 fail：

- 大區塊/混合形狀錯誤 `0.3481` vs base `0.3384`（變差 +2.87%）
- 整體位移幾乎守住（`0.3837 px` vs `0.3813 px`）
- ring guard 三尺度 +37–45%

但在 R45C 的 pixel oracle 對照下：

- 70-77% 的 patch 它在 pixel level 比 R44B from R42 更接近 GT
- 平均 `mean_error_reduction` 微正（R45B 表記 `+0.0019`）
- 這跟它的設計目標一致——它從 R44B from R42 出發、用 R44B from COMBO 作老師、只在大區塊邊界帶做局部蒸餾，目的是「邊界帶位置」更穩，而不是「整張形狀」更乾淨

也就是說，R44H Step B 沒救回形狀（碎裂、厚度仍差），但 pixel 邊界帶位置確實穩住了。這個訊息在 R44 評估時被「形狀 metric 變差」蓋過。它是 silent pixel winner。

不過 pixel 改善幅度只有 `3–5%`，不足以推動升級。

## 分族分析

### Patch 64

| 結構類型 | Patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |
|---|---:|---:|---:|---:|
| large_regions | 3755 | 0.5864 | 0.3226 | 44.99% |
| mixed_fields | 5132 | 0.6687 | 0.4227 | 36.80% |

### Patch 128

| 結構類型 | Patch 數 | R44B from R42 patch 平均 | 分區理想上限 | 改善% |
|---|---:|---:|---:|---:|
| large_regions | 1517 | 0.5059 | 0.2707 | 46.48% |
| mixed_fields | 1949 | 0.5212 | 0.2948 | 43.44% |

## 分區理想選擇老師統計

### Patch 64

| 模型 | 被選次數 | 占比 |
|---|---:|---:|
| R41 direct | 2709 | 30.48% |
| R44B from R42 | 2238 | 25.18% |
| R44B from COMBO | 1560 | 17.55% |
| R44B from R40 | 912 | 10.26% |
| R42 best | 506 | 5.69% |
| R44H StepB region KD | 502 | 5.65% |
| R44C static heavy | 460 | 5.18% |

### Patch 128

| 模型 | 被選次數 | 占比 |
|---|---:|---:|
| R41 direct | 1162 | 33.53% |
| R44B from COMBO | 655 | 18.90% |
| R44B from R42 | 483 | 13.94% |
| R44B from R40 | 405 | 11.68% |
| R42 best | 292 | 8.42% |
| R44H StepB region KD | 247 | 7.13% |
| R44C static heavy | 222 | 6.41% |

## 觀察整合

兩個理想上限對比下出現幾個跟 R45B 互補的觀察，以下都是事實描述，判斷與下一步策略留給後續決策討論。

### 形狀理想上限路徑下的觀察

- 分區形狀理想上限改善 40-45%，比 R45B 整張理想上限 33.42% 高 7-12 個百分點。
- 形狀理想上限選到的老師（R41 direct 占 30%、R44B from COMBO 占 17.5% 為主）在邊界帶 `mean_error_reduction` 全部負值，乾淨比例只有 7.6-7.8%。
- 平均 `mean_error_reduction` 為 `-0.07` 上下，平均 `teacher_better_fraction` 為 `0.16` 上下。
- 也就是說，形狀分數選出的老師，邊界帶絕對像素誤差比 R44B from R42 更大。

### 像素殘差理想上限路徑下的觀察

- 每個小塊改用 `mean_error_reduction` 最大的老師當理想上限，84-86% 的小塊有老師能在像素上改善 R44B from R42。
- 但平均改善幅度 `0.0025-0.0030`，相對 R44B from R42 邊界帶誤差（從 R45B 表反推約 `0.07-0.10`）只有 3-5%。
- 70-77% 的小塊集中選到 R44H StepB region KD 一個老師，其他六個候選加起來只占 14% 上下。
- 14-16% 的小塊裡 R44B from R42 在像素上仍是最佳，沒有任何老師能改善。

### 兩個理想上限的老師選擇對照

| 模型 | 形狀理想上限占比（小塊 64) | 像素理想上限占比（小塊 64) |
|---|---:|---:|
| R41 direct | 30.48% | 0.32% |
| R44B from COMBO | 17.55% | 1.25% |
| R44B from R40 | 10.26% | 2.14% |
| R42 best | 5.69% | 2.84% |
| R44H StepB region KD | 5.65% | 70.55% |
| R44C static heavy | 5.18% | 6.88% |

形狀對得好的老師跟像素對得好的老師基本上不重疊。R44G `shape_error_score`（厚度比、破碎比、直邊覆蓋、角點保留、F 分數）測的是邊界遮罩對齊度，對像素強度、紋理、過衝不敏感。

### R44H Step B 的像素層級觀察

R44 主報告把它判失敗：形狀錯誤 `0.3481` vs 基準 `0.3384`（變差 +2.87%）、環形守門退 37-45%。R45C 補的像素觀察：

- 70-77% 的小塊它在像素上比 R44B from R42 更接近答案
- 平均 `mean_error_reduction` 微正（R45B 表記 `+0.0019`)

它的設計目標是「邊界帶位置穩住」，像素觀察跟設計目標一致；形狀指標沒救回。

### 對應到 R45 原本要驗證的問題

R45B 對下一步的設想是：能力分散在分區層級是否成立？分區選擇器是否有空間？

R45C 補上的事實：

- 形狀理想上限在分區層級確實有空間（40-45%），但選到的老師像素殘差全負
- 像素理想上限在分區層級空間 3-5%，且 70-77% 集中在單一個老師
- R44B from R42 在 14-16% 的小塊上像素殘差仍是最佳
- 形狀指標跟像素品質在這個資料集上幾乎是正交軸

這些事實如何解讀（路線 A 是否仍有空間、路線 B 是否退化成單模型替換、是否該改評估指標、是否暫停）留給後續決策討論。

## 待釐清的問題與決策邊界

R45C 揭露但沒解決的問題：

1. R44G `shape_error_score` 是不是適合作為「顯微邊界忠實度」的單一評估指標？是否需要把像素殘差、序列位置一致性一起看？
2. R44H Step B 的像素層級表現，是否值得重新評估它在 R44 結果中的位置？
3. 若選擇器路線繼續，監督訊號該用形狀分數、像素殘差，還是其他？
4. 若不繼續單模型整合或多模型路由，下一條路是改評估指標、改訓練資料，還是先擱置？

以上不在 R45C 範圍內，留給專案 owner 決策。

## 產物

- `results/r45c_region_oracle/r45c_patch_rows_<size>.csv`：每 patch、每模型的形狀錯誤分數。
- `results/r45c_region_oracle/r45c_patch_residuals_<size>.csv`：每 patch、每老師的邊界帶殘差統計。
- `results/r45c_region_oracle/r45c_region_oracle_summary.json`：形狀理想上限與殘差乾淨比例彙整。
- `results/r45c_region_oracle/r45c_pixel_oracle_summary.json`：pixel-residual 理想上限與老師選擇對照。
- `scripts/r45c_pixel_oracle_postprocess.py`：從 residuals CSV 算 pixel-residual oracle 的 post-process 腳本（不需重跑全量重建）。

## 方法

- Patch 切法：non-overlapping，最後一塊向內錨定避免出界；最小邊界 GT 像素數 `8`。
- 邊界帶：GT boundary 經 `7x7` dilation（與 R45B 一致）。
- 預測 boundary：整張影像用 `matched_gradient_boundary` 取與 GT 等量像素，再切 patch。
- 形狀錯誤：直接套 R44G 的 `boundary_shape_metrics`。Patch 內若 component bbox 被 reject（min_pixels=16, min_span=10），對應 component metric 走 default penalty，但 ranking 仍成立。
- 對比基準：R44B from R42（與 R45B 一致）；目標分族 `large_regions` + `mixed_fields`。
