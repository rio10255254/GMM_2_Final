# R44D 診斷 — 分族與位移尺度盤點

## 摘要

R44D 不開新 round、不訓練新模型。它只讀取 R44A/R44B/R44C 已經產生的逐 pair 位移結果，拆成結構類型與位移段來看，目的是判斷下一步是否真的需要新機制。

結論：**現在不應立刻開 R45。R44 內部已足夠證明，問題不是單一權重比例，而是不同顯微結構需要不同處理。**

最重要發現：

- `R44B from R42` 仍是最佳整體位移候選，尤其格線位移最強。
- `R44C static heavy` 只把 R44B 稍微拉回平衡，沒有解開大區塊問題。
- 大區塊與混合場景的最佳模型不是同一個，代表單一模型目前很難同時吃下所有結構。
- 目前的格線 phase 欄位對所有模型幾乎相同，不能拿來排名模型；格線應改看輸出影像的位移誤差與邊界距離。
- `family holdout` 先前已被 R44C 否定；排除某些結構不學位移，並不能保住它們。

## 分族最佳模型

### 邊界距離最佳

| 結構類型 | 最佳模型 | 數值 | 第二名 | 差距 |
| --- | --- | --- | --- | --- |
| curves | R44C static heavy | 1.8398 | R44B from R42 | 0.0130 |
| defects | R44C family holdout | 5.3442 | R44C static heavy | 0.0027 |
| grids | R42 best | 0.3806 | R44C family holdout | 0.0032 |
| junctions | R44C family holdout | 1.6259 | R44C static heavy | 0.0023 |
| large_regions | R41 direct | 4.9915 | R44B from COMBO | 0.9521 |
| mixed_fields | R44B from R40 | 5.9151 | R41 direct | 0.4733 |
| thin_lines | R44C static heavy | 2.3291 | R44C family holdout | 0.0010 |

### 位移向量最佳

| 結構類型 | 最佳模型 | 數值 | 第二名 | 差距 |
| --- | --- | --- | --- | --- |
| curves | R41 direct | 0.0689 | R40 a045 | 0.0095 |
| defects | R41 direct | 0.0430 | R40 a045 | 0.0089 |
| grids | R44B from R42 | 2.2457 | R44C static heavy | 0.1363 |
| junctions | R40 a045 | 0.0587 | R44B from COMBO | 0.0001 |
| large_regions | R40 a045 | 0.0613 | COMBO | 0.0073 |
| mixed_fields | R41 direct | 0.0447 | R40 a045 | 0.0117 |
| thin_lines | R44B from R42 | 0.0719 | R44C low motion | 0.0002 |

### 格線 phase 欄位檢查

目前 `grid_phase_motion_error_px` 在格線與混合場景上對所有模型幾乎相同，代表它不是有效的模型比較欄位。R44D 保留這個 finding，但不再用它判斷誰比較好。

## 單一模型 vs 分族上限

- 最佳單一模型平均邊界距離：`R42 best`，`3.6726 px`。
- 如果每個結構類型都拿目前最佳模型，分族上限是 `3.2038 px`。
- 分族上限相對最佳單一模型還有 `12.77%` 空間。

這表示下一步如果還是只做單一全域權重，天花板可能很低；真正值得做的是讓不同結構的邊界與位移目標分開設計。

## 位移段觀察

以下只列大區塊、混合場景與格線，因為它們是目前最影響下一步設計的三類：

| 結構類型 | 目標位置 px | 邊界最佳模型 | 邊界距離 | 同列位移誤差 |
| --- | --- | --- | --- | --- |
| grids | 0.0800 | R42 best | 0.4376 | 0.1365 |
| grids | 0.1600 | R44C family holdout | 0.2967 | 0.1285 |
| grids | 0.4000 | R42 best | 0.2464 | 0.2073 |
| grids | 0.8000 | R42 best | 0.4405 | 1.0881 |
| grids | 2.0000 | R42 best | 0.4310 | 9.7090 |
| grids | 8.0000 | R44C static heavy | 0.4202 | 3.0056 |
| large_regions | 0.0800 | R41 direct | 4.1507 | 0.0388 |
| large_regions | 0.1600 | R41 direct | 3.9024 | 0.0514 |
| large_regions | 0.4000 | R41 direct | 3.9848 | 0.0586 |
| large_regions | 0.8000 | R41 direct | 3.6767 | 0.1109 |
| large_regions | 2.0000 | R41 direct | 2.8403 | 0.0950 |
| large_regions | 8.0000 | R41 direct | 11.3943 | 0.0734 |
| mixed_fields | 0.0800 | R44B from R40 | 5.1220 | 0.0323 |
| mixed_fields | 0.1600 | R44B from R40 | 5.6227 | 0.0562 |
| mixed_fields | 0.4000 | R44B from R40 | 5.0189 | 0.0871 |
| mixed_fields | 0.8000 | R44B from R40 | 5.3288 | 0.1185 |
| mixed_fields | 2.0000 | R44B from R40 | 7.3468 | 0.0924 |
| mixed_fields | 8.0000 | R41 direct | 6.8194 | 0.0443 |

## 大區塊瓶頸確認

- `R42 best` 大區塊邊界距離：`7.3401 px`。
- `R44B from R42` 大區塊邊界距離：`7.5878 px`。
- `R44C static heavy` 大區塊邊界距離：`7.7098 px`。

大區塊不是被 R44C 修好，而是仍然卡住。這也解釋了為什麼 R44B 的整體位移變好，但肉眼與邊界距離沒有同步明顯變好。

## 產物

- 分族總表：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_family_scorecard.csv`
- 位移段總表：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_shift_scorecard.csv`
- 每族最佳模型表：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_best_by_family.csv`
- 指標有效性檢查：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_metric_discrimination.csv`
- JSON 彙整：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_summary.json`
- 邊界熱圖：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_boundary_heatmap.png`
- 位移熱圖：`Experiments\R44_UniversalBoundaryMotionFidelity\results\diagnostics\r44d_motion_heatmap.png`

## 下一步判斷

不建議立刻開新 round。建議把下一個動作留在 R44 內部，做一個非常小的 R44E 探針：只針對大區塊與混合場景建立專門保護，不重新挑戰所有結構。若 R44E 仍不能改善，再開新 round 才合理。
