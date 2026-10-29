# 20260309 離線連跑計畫

## 目的

- 讓目前 round2 跑完後，自動接兩輪不同策略
- 第一輪偏向 GMF / 8px 步長穩定
- 第二輪偏向邊界真實銳利，但仍保留步長守門

## 佇列

1. `round3_gmf_guard`
   - 命令：`python -u Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py --profile round3_gmf_guard --sweep-epochs 6 --final-epochs 12 --deterministic`
2. `round3_sharp_balance`
   - 命令：`python -u Model/GeoEdgeAlignSR_v1_AutoTuneTrain.py --profile round3_sharp_balance --sweep-epochs 6 --final-epochs 12 --deterministic`

## 備註

- 每輪都會讀 `organized_20260307/selected/current_seed.json`
- 如果前一輪內部分數提升，seed 會自動晉升
- 如果前一輪沒有提升，下一輪仍會繼續探索，但沿用目前最佳 seed
