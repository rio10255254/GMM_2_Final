# R44H Step 0 / Step A — R44B 家族權重平均探測

## 摘要

- 本文件是 R44 內部分析，不開新 round，也不是正式升級候選。
- Step 0 檢查 `R44C static heavy` 是否能作為混合場景老師。
- Step A 只在 R44B 家族內做權重平均，避免跨太遠模型造成權重落到壞區域。
- 初步決策：**Step A 沒有找到可用平均點；下一步應跳過平均起點，直接做 Step B 的單老師區域蒸餾。**

## Step 0：R44C 乾淨度

- 是否足夠乾淨，可作混合場景老師：**True**
- 混合場景形狀錯誤：R44B from R42 `0.2230`，R44C static heavy `0.2181`。
- 大區塊/混合相關位移最大退步：`6.07%`（門檻 `10.0%`）。
- 解讀：若這裡為 True，R44C 可以在 Step C 當混合場景局部老師；若為 False，先不要把它放進多老師蒸餾。

## Step A：候選結果

| 候選 | 大區塊+混合錯誤↓ | 位移誤差 px↓ | 邊界位移距離↓ | 環形 8px | 環形 0.8px | 環形 0.08px | 判定 |
|---|---|---|---|---|---|---|---|
| R44H r44h_b42_bcombo_a050 | 0.2955 | 0.5298 | 3.7279 | 0.2385 | 0.1902 | 0.1768 | fail_motion_regression |
| R44H r44h_b42_bcombo_a030 | 0.3036 | 0.5115 | 3.6455 | 0.1882 | 0.1865 | 0.1695 | fail_motion_regression |
| R44H r44h_b42_b40_bcombo_050_025_025 | 0.3093 | 0.6277 | 3.6750 | 0.2295 | 0.1907 | 0.1878 | fail_motion_regression |
| R44H r44h_b42_b40_a030 | 0.3262 | 0.4843 | 3.7053 | 0.1904 | 0.2168 | 0.1593 | fail_motion_regression |

## 參考模型

| 模型 | 大區塊+混合錯誤↓ | 位移誤差 px↓ | 邊界位移距離↓ | 環形 8px | 環形 0.8px | 環形 0.08px | 判定 |
|---|---|---|---|---|---|---|---|
| R44B from R40 | 0.3110 | 0.9087 | 3.7808 | — | — | — | fail_motion_regression |
| R44B from COMBO | 0.3288 | 0.5313 | 3.9081 | — | — | — | fail_motion_regression |
| R44C static heavy | 0.3345 | 0.4011 | 3.7198 | 0.1897 | 0.2222 | 0.1585 | fail |
| R44B from R42 | 0.3384 | 0.3813 | 3.7276 | 0.2015 | 0.2214 | 0.1568 | fail |

## 判定規則

- 強通過：大區塊+混合形狀錯誤優於或等於 `R44B from R40` 的 `0.3110`，且整體位移退步不超過 `R44B from R42` 的 10%。
- 弱通過：形狀錯誤至少比 `R44B from R42` 改善 3%，且位移退步不超過 10%。
- 失敗：形狀沒有改善，或位移退步超過 10%。

## 產物

- 平均候選權重：`Experiments/R44_UniversalBoundaryMotionFidelity/results/r44h_family_average/checkpoints`
- Step A 表格：`Experiments/R44_UniversalBoundaryMotionFidelity/results/r44h_family_average/r44h_stepa_summary.csv`
- Step A JSON：`Experiments/R44_UniversalBoundaryMotionFidelity/results/r44h_family_average/r44h_stepa_summary.json`

## 下一步

Step A 沒有找到可用平均點；下一步應跳過平均起點，直接做 Step B 的單老師區域蒸餾。
