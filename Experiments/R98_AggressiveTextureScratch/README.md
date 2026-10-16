# Round 98 — Aggressive Texture Scratch

## 假說

R97 的主要限制不是位移或分塊架構，而是紋理目標過稀、紋理表示不足，以及各修正分支在真實影像上互相抵消。R98 在保留 R97 位移與零接縫特性的前提下，讓來源影像中仍存在的多尺度紋理能被更大膽地恢復。

## 設計

- 完全從零訓練，不載入 R97 或任何舊權重。
- 沿用 R97 的程序化資料，不複製大型資料，也不混入真實 SEM、HS100MG 或其他顯微影像作為訓練答案。
- 保留局部全卷積處理、來源相位鎖定、對稱濾波與固定 halo 分塊推論。
- 將紋理由三個頻帶擴充為六個來源頻帶，並加入局部紋理能量提示；仍不能自由繪製不存在的圖樣。
- 加強紋理與邊界的直接監督、提高紋理場景取樣量，並提高分支互相抵消的代價。
- 移除 R97 最後把輸出拉回保守直通的低率收斂段，改成保留細節的最後階段。

## 候選

| Tag | 說明 |
|-----|------|
| `r98_aggressive_texture_scratch` | 唯一正式候選，48 輪，seed 980047 |

## 結果

訓練中。代表性真實影像會每 4 輪重建一次，並與 R97 固定指標對照。

## 資料

- Experiment profile: `self-contained`
- Training data: 共享 R93/R97 程序化資料包，只讀引用；不複製 payload
- Training truth: 程序化 clean/noise-free/noisy 三層真值
- Real microscopy: 僅做即時驗證，不參與梯度或選擇訓練答案
- Checkpoint: 本輪 `weights/formal/` 下唯一正式 run
- Closeout: 保留完整訓練紀錄、每兩輪權重與代表性重建

## 分支

`sandbox/r98-aggressive-texture-scratch`
