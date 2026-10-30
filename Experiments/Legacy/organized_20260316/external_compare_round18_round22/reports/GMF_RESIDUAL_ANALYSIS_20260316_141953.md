# GMF Residual Analysis — 20260316_141953

## Summary

- Pitches analyzed: 3
- pitch1um_y_100: 100 aligned frames, sg drift=0.094126, h drift=0.118317
- pitch0p1um_y_60: 60 aligned frames, sg drift=-0.063645, h drift=-0.032134
- pitch0p01um_y_40: 40 aligned frames, sg drift=-0.054832, h drift=0.147947

## Per-Pitch Results

### pitch1um_y_100

| Metric | R22_stepguard | R22_hold |
|--------|--------------|----------|
| N frames | 100 | 100 |
| Mean residual (px) | 0.068950 | 3.568970 |
| Std residual (px) | 0.223464 | 0.223689 |
| Max \|residual\| (px) | 0.575000 | 4.180000 |
| Drift (Pearson r) | 0.094126 | 0.118317 |
| Std(steps) | 0.245431 | 0.288654 |
| Lag-1 autocorr | 0.099548 | 0.026597 |

### pitch0p1um_y_60

| Metric | R22_stepguard | R22_hold |
|--------|--------------|----------|
| N frames | 60 | 60 |
| Mean residual (px) | 0.989033 | 2.579050 |
| Std residual (px) | 0.212982 | 0.254851 |
| Max \|residual\| (px) | 1.511000 | 3.305000 |
| Drift (Pearson r) | -0.063645 | -0.032134 |
| Std(steps) | 0.333639 | 0.285453 |
| Lag-1 autocorr | -0.035291 | 0.198915 |

Outlier frames (only for pitch0p1um_y_60, max 10):

| FileName | R18 step | R22sg step | diff |
|----------|----------|------------|------|
| VisionTop_20251029185446254.bmp | -0.552000 | -1.245000 | -0.693000 |
| VisionTop_20251029190030535.bmp | -0.493000 | -1.149000 | -0.656000 |
| VisionTop_20251029190156571.bmp | -0.789000 | -1.725000 | -0.936000 |

### pitch0p01um_y_40

| Metric | R22_stepguard | R22_hold |
|--------|--------------|----------|
| N frames | 40 | 40 |
| Mean residual (px) | 0.066600 | 0.937550 |
| Std residual (px) | 0.164230 | 0.221131 |
| Max \|residual\| (px) | 0.429000 | 1.497000 |
| Drift (Pearson r) | -0.054832 | 0.147947 |
| Std(steps) | 0.169440 | 0.189303 |
| Lag-1 autocorr | 0.234002 | 0.214462 |

## Core Questions

Q1: Is residual random or drift?  Residual looks more random than drifting: no pitch exceeds |Pearson r| > 0.3.

Q2: Are outlier frames clustered or uniformly distributed?  Outlier frames appear spread out in pitch0p1um_y_60 (max gap 32 >= n_frames/3).

Q3: Do R22h and R22sg show different residual patterns?  R22_hold and R22_stepguard show different residual patterns: pitch1um_y_100 exceeds the 0.1 threshold.

---

## Deeper Analysis：為什麼 R22sg 比 R22h 差？

### 關鍵對比（pitch0p1um_y_60，主戰場）

| 指標 | R22sg | R22h |
|------|-------|------|
| Mean residual vs R18 | 0.989 px | 2.579 px |
| Std residual | 0.213 px | 0.255 px |
| Lag-1 autocorr | **-0.035**（接近零） | **+0.199**（正相關） |
| External GMF step std | **0.334**（退步） | **0.285**（與 R18 相同）|

### Autocorrelation 是關鍵

- **R22sg autocorr ≈ 0**：每幀的絕對位置誤差是**獨立隨機噪聲**，每幀互不相關
  - step[i] = position[i+1] - position[i]，兩個獨立噪聲相減 → sqrt(2) 倍放大
  - → step std 上升

- **R22h autocorr = +0.199**：每幀的絕對位置誤差是**平滑漂移**，相鄰幀誤差相關
  - 相鄰幀有相似的偏移 → 步長中誤差部分相消
  - → step std 保持與 R18 相同

### 根本原因：Step-first 訓練讓 absolute position 失去平滑性

pairmix 的 step_err 訓練 loss = error(predicted_delta, GT_delta)

這個 loss：
- ✅ 約束了「兩幀之間的相對位移」是準確的
- ❌ **完全不約束「每幀的絕對位置」是否穩定**

stepguard（step_err=0.0657，最優化）讓 SR 模型學到：
- 相鄰幀的 delta 非常準確
- 但每幀的 absolute anchor 可以任意浮動

浮動的 absolute anchor → 每幀的 GMF 偵測位置隨機跳動 → step std 上升

R22h（center_err=0.1508 更佳）：由於更好的 center 優化，absolute anchor 更一致 → smooth drift → step std 保持

### 結論

外部 GMF step std 的決定因素不是 step_err，而是 **absolute position 的 frame-to-frame 平滑性**。

pairmix 架構只優化 relative delta，不優化 absolute position 平滑性。要修這個問題，需要：

1. 在訓練 loss 中加入 **absolute anchor consistency** 項（相鄰幀 absolute anchor 應穩定）
2. 或改善 soft_band_refine 作為 absolute anchor 的一致性
3. 不能只靠 step_err 作為 gate 來預測 external GMF 表現
