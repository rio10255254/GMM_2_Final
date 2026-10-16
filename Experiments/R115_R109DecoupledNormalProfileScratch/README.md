# R115 — R109 Decoupled Normal-Profile Scratch

R115 以 R109 的中點位移與單調寬度修正為唯一影像動作，新增一條完全
獨立的法線剖面證據線。證據線只能決定 R109 兩種既有動作是否採用、
採用多少，不能重畫影像，也不能回頭修改邊界、法線或幾何基底。

資料同時保留兩個可重跑版本：

- A：R109 原始 5,000 / 512 張資料；
- B：R114 的 240 張針對性替換版，總量仍為 5,000 / 512。

正式模型一律隨機初始化；R109 E48 只允許用於訓練前的資料與架構短探針，
不得載入正式訓練。

執行順序：

1. `scripts/prepare_data.ps1`
2. `scripts/validate.ps1`
3. `scripts/run_ablation_probe.ps1`
4. 只有短探針通過後才可執行 `scripts/train.ps1`

真實顯微影像、SEM、R73、R74、GMF 與 HS100MG 都只作封閉驗證。

