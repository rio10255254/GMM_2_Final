# Round 34 — Frequency-Split Robust Loss

## 假說

R33 hard_p95 在 GMF step_std 上取得 -29% 突破，但視覺銳度退步 -32%（gradient）/ -47%（Laplacian）。
深度分析揭示：Winsorize 同時壓制了所有頻段的離群值，但 GMF 在乎的是低頻邊界位置，
人眼在乎的是高頻邊緣銳度。R34 嘗試在頻域分離這兩個目標。

## 設計

在 `gradient_magnitude_loss` 內部，用 Gaussian blur (σ=1.5) 把圖像分成 lo/hi 兩個頻段：

- **Lo-freq（邊界位置）**: Sobel on blurred images → Winsorize → 穩定 GMF
- **Hi-freq（邊緣銳度）**: Sobel on residual → 不截尾 → 保留銳度

```
pred, target
  ├── gaussian_blur(σ) → lo → Sobel → diff → Winsorize → l_lo
  └── (原圖 - lo)     → hi → Sobel → diff → 完整信號 → l_hi
l_gradmag = w_lo * l_lo + w_hi * l_hi
```

## 和 R33 的差異

| | R33 hard_p95 | R34 freq-split |
|-|-------------|---------------|
| 低頻 gradient | Winsorize | Winsorize（相同） |
| 高頻 gradient | Winsorize（銳度退步 -32%） | **不截尾**（保留銳度） |
| 預期 step_std | 0.129 (-37%) | 類似或略高 |
| 預期銳度 | -32% | 接近 R30 baseline |

## 候選

| Tag | FREQ_SPLIT | PERCENTILE | SIGMA | W_LO | W_HI |
|-----|-----------|-----------|-------|------|------|
| `r34_freq_s15_p95` | True | 0.95 | 1.5 | 0.5 | 0.5 |
| `r34_freq_s20_p95` | True | 0.95 | 2.0 | 0.5 | 0.5 |
| `r34_freq_s15_p90` | True | 0.90 | 1.5 | 0.5 | 0.5 |

## 分支

`sandbox/r34`（基於 `sandbox/r33`）
