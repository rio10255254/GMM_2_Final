# R85：光學前處理在整張畫布只算一次

[研究時間線](<../../docs/research/TIMELINE.md>) · [前一種修法 R84（含三輪總結案）](<../R84_R79TileStableRootRepair/FILE_GUIDE.md>) · [下一種修法 R86](<../R86_R79BlockGroupNormRepair/FILE_GUIDE.md>)

**一句話：** R84 的局部網路修好了切塊一致性，但 SEM 變差很多。R85 保留 R84 的局部網路，把 R79 原本的光學前處理改成在整張畫布只算一次、讓整張與切塊共用，並只用 R79 當程式生成輸入上的行為保持約束。2026-08-10 篩選的兩個保存點都通過切塊一致性，但邊界誤差是 R79 的 1.18 與 1.16 倍，超過鎖定的上限，所以新的外部保留資料一直沒有打開，R79 仍是預設。

| | |
|---|---|
| 結果 | **未採用**（切塊一致通過，邊界誤差超過 R79 的鎖定上限） |
| 時間 | 2026-08-10 |
| 實驗條件 | 純合成資料，答案是解析式超取樣繪製；不使用 SEM 或任何實拍像素 |
| 起點 | R84 的局部網路 |

## 讀這些內容要知道的事

1. **沒有保存點通過篩選**，所以依規則不做最終確認，外部保留資料保持封存。
2. **三輪的總結與後來的決定**（保留 R79、只允許整張推論）寫在 [R84 的結案報告](<../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md>)。

## 拿資料與重做

| 需要什麼 | 在哪裡 |
|---|---|
| 資料生成、鎖定訓練子集、訓練、篩選、推論程式與設定 | 本資料夾 [scripts/](<scripts>)、[training/](<training>)、[inference/](<inference>)、[config/](<config>)，已在 GitHub；執行順序見 [README](<README.md>) |

查某個檔案現在在哪：`python Tools/cloud_locator.py where <路徑>`。

> **目前的限制：** 兩個保存點與篩選結果表不在 GitHub 上。

## 原始報告

| 文件 | 內容 |
|---|---|
| [README](<README.md>) | 設計、執行順序與最終狀態 |
| [三輪總結案](<../R84_R79TileStableRootRepair/reports/R79_ROOT_REPAIR_CLOSEOUT.md>) | R84、R85、R86 的比較與最後的修改 |

2026 年 10 月的保存與核對紀錄見[保存紀錄](<../../docs/reproducibility/experiments/main__R85_R79SharedCanvasOpticalRepair.md>)。
