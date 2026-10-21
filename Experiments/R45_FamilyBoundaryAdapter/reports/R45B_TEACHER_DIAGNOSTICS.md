# R45B 老師殘差與理想分族診斷

## 摘要

- 本診斷不訓練模型，只讀取 R44 已有的 motion_val_unseen 重建結果。
- 目的：確認局部較強的老師模型是否真的有穩定可轉移的邊界優勢，以及理想分族選擇的上限有多大。
- 基準仍是 `R44B from R42`，因為它目前位移最穩。

## 主要結論

- R44B from R42 的大區塊/混合合併形狀錯誤是 `0.3384`。
- 完美逐張選擇器的理論形狀錯誤是 `0.2253`，改善 `33.42%`。
- 只按結構類型選固定老師的理論形狀錯誤是 `0.2968`，改善 `12.30%`。
- 這代表能力分散確實存在，但不是很乾淨；逐張 oracle 有明顯空間，單純分族固定老師的空間較小。

## 老師可轉移性判定

| 老師 | 可轉移 | 理由 | 形狀改善% | 殘差改善 | 老師較好比例 | 位移變化% |
|---|---|---|---|---|---|---|
| R44B from R40 | False | 殘差方向不穩；位移退步過大 | 8.1020 | -0.0274 | 0.1844 | 138.3069 |
| R41 direct | False | 殘差方向不穩；位移退步過大 | 7.8303 | -0.1324 | 0.0902 | 281.3872 |
| R44B from COMBO | False | 形狀優勢不足；殘差方向不穩；位移退步過大 | 2.8478 | -0.0356 | 0.1747 | 39.3284 |
| R42 best | False | 形狀優勢不足；殘差方向不穩；位移退步過大 | 2.5268 | -0.0043 | 0.2327 | 20.8734 |
| R44C static heavy | False | 形狀優勢不足；殘差方向不穩 | 1.1370 | -0.0018 | 0.2970 | 5.1810 |
| R44H StepB region KD | False | 形狀優勢不足；殘差方向不穩 | -2.8664 | 0.0019 | 0.4608 | 0.6147 |

## 大區塊/混合總排名

| 模型 | 形狀錯誤↓ | 邊界 F↑ | 厚度比≈1 | 破碎比≈1 | 直邊保留↑ | 角點保留↑ |
|---|---|---|---|---|---|---|
| R44B from R40 | 0.3110 | 0.8114 | 1.0011 | 4.3366 | 0.8023 | 0.7413 |
| R41 direct | 0.3119 | 0.8304 | 1.0004 | 4.1915 | 0.8313 | 0.7371 |
| R44B from COMBO | 0.3288 | 0.8073 | 1.0008 | 3.5495 | 0.7947 | 0.7010 |
| R42 best | 0.3298 | 0.8062 | 1.0009 | 5.2584 | 0.7942 | 0.7533 |
| R44C static heavy | 0.3345 | 0.8029 | 1.0011 | 5.4792 | 0.7899 | 0.7485 |
| R44B from R42 | 0.3384 | 0.8027 | 1.0012 | 5.9485 | 0.7901 | 0.7436 |
| R44H StepB region KD | 0.3481 | 0.8029 | 1.0014 | 6.0827 | 0.7902 | 0.7333 |

## 理想分族選擇

| 結構類型 | 最佳固定模型 | 平均形狀錯誤 | 樣本數 |
|---|---|---|---|
| large_regions | R44B from COMBO | 0.3755 | 140 |
| mixed_fields | R44C static heavy | 0.2181 | 140 |

## 逐張 oracle 選擇次數

| 模型 | 次數 |
|---|---|
| R41 direct | 73 |
| R44B from COMBO | 63 |
| R44B from R40 | 49 |
| R44C static heavy | 31 |
| R42 best | 24 |
| R44B from R42 | 21 |
| R44H StepB region KD | 19 |

## 代表圖

![R45B 老師比較](D:/GMM_2_Final/Experiments/R45_FamilyBoundaryAdapter/results/visual_samples/r45b_teacher_diagnostics_sheet.png)

## 下一步

- 若要繼續單一入口路線，下一步不應再做輸出端校正。
- 較合理的是做中間特徵層的小分支，並且不要只用粗略 family label；至少需要能判斷單張圖內哪一塊邊界該由哪個老師引導。
- 若只做固定分族老師，改善空間有限；若要追逐張 oracle 的上限，必須加入場景/區域選擇器。

## 產物

- `results/r45b_teacher_diagnostics/r45b_shape_rows.csv`：逐張形狀指標。
- `results/r45b_teacher_diagnostics/r45b_target_rank.csv`：目標結構總排名。
- `results/r45b_teacher_diagnostics/r45b_residual_summary.csv`：老師殘差方向統計。
- `results/r45b_teacher_diagnostics/r45b_oracle_summary.json`：oracle 上限。
- `results/visual_samples/r45b_teacher_diagnostics_sheet.png`：代表圖。
