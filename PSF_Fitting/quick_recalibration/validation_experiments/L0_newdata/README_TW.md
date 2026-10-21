# L0 New-Data Formal Circle-Edge Summary

這裡保存本次用新拍攝資料整理後的正式 L0 總結與主控腳本。

## 本次規則

- 正式 L0 只採用 `Circle_Round1`：同一批影像重複擬合 15 次，用來看擬合本身的波動。
- `Circle_Round2`、`Circle_Round3` 是 L1 的來源資料；它們各自也有 15 次擬合結果，但不再被合併成正式 L0。
- 每個 Round 是 11x11，共 121 個位置；每個位置有連續兩張影像。
- 目前擬合主跑使用每個位置的第一張影像。
- 舊 L0 九點標準換到 11x11 後為：1、6、11、56、61、66、111、116、121。
- 擬合目標只看圓形邊界；中心方塊先填平，並用邊界遮罩排除。

## 主要檔案

- `run_L0_newdata_rounds.m`：當初產生三輪擬合結果的 MATLAB 啟動器。
- `L0_newdata_summary.md`：人看的正式 L0 總結。
- `L0_newdata_summary.json`：後續程式可讀的正式 L0 總結。

各 Round 的詳細報告放在各自的 `outputs` 內，檔名是 `L0_newdata_noise_floor_report.md`。

## 正式 L0 結果

| Round | Trials | Clean median | Clean mean | FOV max/min |
|---|---:|---:|---:|---:|
| Circle_Round1 | 15 | 0.027055 | 0.065377 | 1.211 |

## L1 來源擬合清單

| Round | Trials | Clean median | Clean mean | FOV max/min |
|---|---:|---:|---:|---:|
| Circle_Round2 | 15 | 0.022559 | 0.051162 | 1.377 |
| Circle_Round3 | 15 | 0.027294 | 0.058550 | 1.194 |

Round2/3 的結果用來支撐 L1，不再被當成正式 L0 聚合。三輪擬合底噪接近，代表 Round1 作為正式 L0 錨點不是孤立異常。
