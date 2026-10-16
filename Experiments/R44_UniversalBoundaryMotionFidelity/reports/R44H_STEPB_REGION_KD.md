# R44H Step B 局部老師蒸餾結果

## 結論

R44H Step B 已完成，但**沒有通過概念驗證**。

這次做法確實保住了 `R44B from R42` 的通用位移能力，整體位移誤差只從 `0.3813 px` 小幅變成 `0.3837 px`。但是它沒有救回大區塊邊界形狀，反而讓大區塊與混合場景合併形狀錯誤從 `0.3384` 變差到 `0.3481`。

因此目前不建議進入 R44H Step C 多老師蒸餾。單一老師、局部遮罩都已經不能改善目標形狀，多老師版本很可能只是把干擾放大。

## 本次設定

| 項目 | 設定 |
|---|---|
| 學生起點 | `R44B from R42` |
| 老師 | `R44B from COMBO` |
| 訓練方式 | 只在大區塊邊界帶做局部老師蒸餾 |
| 訓練資料 | 大區塊靜態邊界資料 + 大區塊位移資料 |
| epoch | 12 |
| 每 epoch batch 上限 | 50 |
| 評估權重 | `latest.pth.tar`，因短訓練未達 best checkpoint 更新門檻 |

## 完成項目

- 新增預設關閉的局部老師蒸餾設定；未開啟時不影響舊實驗。
- 新增 R44H Step B 啟動腳本。
- 完成 dry-run、1 epoch smoke test、12 epoch 正式短訓練。
- 完成 R44 位移重建與分項指標。
- 完成 R44G 邊界形狀診斷。
- 完成本地三尺度環形代理紀錄。

## 位移結果

| 指標 | R44B from R42 | R44H Step B | 判讀 |
|---|---:|---:|---|
| 整體位移誤差↓ | `0.3813 px` | `0.3837 px` | 保住，僅小幅變差 |
| 格線位移誤差↓ | `2.2457 px` | `2.2393 px` | 持平略好 |
| 邊界位移距離↓ | `3.7276 px` | `3.6648 px` | 小幅改善 |

分族位移重點：

| 分族 | 位移誤差↓ |
|---|---:|
| 細線 | `0.0746 px` |
| 格線 | `2.2393 px` |
| 交叉線 | `0.0703 px` |
| 曲線 | `0.0940 px` |
| 大區塊 | `0.0755 px` |
| 缺陷 | `0.0666 px` |
| 混合場景 | `0.0653 px` |

## 形狀結果

大區塊與混合場景合併排名：

| 模型 | 形狀錯誤↓ | 邊界 F↑ | 碎裂比↓ |
|---|---:|---:|---:|
| R44B from R40 | `0.3110` | `0.8114` | `4.3366` |
| R44B from COMBO | `0.3288` | `0.8073` | `3.5495` |
| R44B from R42 | `0.3384` | `0.8027` | `5.9485` |
| R44H Step B | `0.3481` | `0.8029` | `6.0827` |

分族形狀：

| 分族 | R44B from R42 | R44H Step B | 判讀 |
|---|---:|---:|---|
| 大區塊形狀錯誤↓ | `0.4538` | `0.4667` | 變差 |
| 混合場景形狀錯誤↓ | `0.2230` | `0.2294` | 變差 |
| 大區塊碎裂比↓ | `10.7108` | `10.9029` | 變差 |
| 混合場景碎裂比↓ | `1.1862` | `1.2625` | 變差 |

## 本地環形代理紀錄

R44H Step B 不是環形升級候選，以下只作紀錄：

| 尺度 | Step B | COMBO local | vs COMBO |
|---|---:|---:|---:|
| 8px | `0.2016` | `0.1389` | `+45.1%` |
| 0.8px | `0.2146` | `0.1509` | `+42.2%` |
| 0.08px | `0.1623` | `0.1185` | `+37.0%` |

## 判讀

Step B 最重要的訊號不是「老師蒸餾完全沒用」，而是目前這種形式的局部老師蒸餾太弱，沒有把大區塊邊界從 R44B from R42 推向 R44B from COMBO，反而讓碎裂略增。

這代表 R44H 原本規劃的 Step C 多老師版本風險很高：若單一老師在單一場景都不能改善，多老師同時加入只會更容易互相拉扯。

## 下一步建議

1. 不進 R44H Step C 多老師蒸餾。
2. 不再把「全模型微調」當成主要匯聚方法，因為 R44E、R44H Step A、R44H Step B 都顯示它會造成能力交換。
3. 下一步應轉向「保留主模型，分族加小模組或分族選擇」的方向，例如 adapter / 小頭 / 推論時分族路由。
4. 若仍要留在單一模型路線，應先做更強的局部邊界形狀 loss 診斷，而不是直接加更多老師。

## 主要產物

- Step B 計畫：`reports/R44H_STEPB_REGION_KD_PLAN.md`
- Step B 啟動腳本：`scripts/launch_r44h_stepb.py`
- Step B 測試：`tests/test_r44h_region_kd.py`、`tests/test_r44h_stepb_launcher.py`
- 訓練 run：完整歷史依 `../ARCHIVE_POINTER_20260824.md` 從 H 槽恢復；D 槽保留 `results/r44h_stepb_region_kd/` 的代表模型與結果。
- 評估 checkpoint：`results/r44h_stepb_region_kd/checkpoints/r44h_stepb_region_kd_main_latest.pth.tar`
- 位移摘要：`results/r44h_stepb_region_kd/r44h_stepb_motion_summary.json`
- 位移逐項表：`results/r44h_stepb_region_kd/r44h_stepb_motion_rows.csv`
- 環形代理摘要：`results/r44h_stepb_region_kd/r44h_stepb_ring_guard_summary.json`
- 更新後 R44G 形狀表：`results/diagnostics/r44g_boundary_shape_scorecard.csv`
- 更新後 R44G 目標排名：`results/diagnostics/r44g_boundary_shape_target_rank.csv`
