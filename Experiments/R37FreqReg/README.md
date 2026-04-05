# Round 37 — Frequency-Dependent PSF Regularization

## 假說

R33/R34/R35 都無法打破 sharpness-stability trade-off，因為它們都在 loss 層或 alpha 層做均勻調整。

根本問題在 PSF physics layer 的 Wiener 反卷積：`reg=10` 是純量，對所有頻率一視同仁。
低頻（邊界位置）和高頻（邊緣銳度）被同等壓制。

R37 把 reg 從純量變成頻率依賴的 profile：
- 低頻：高 reg（保守 → 位置穩定）
- 高頻：低 reg（激進 → 銳度恢復）

## 設計

```
reg(f) = reg_base × (lo_mult × exp(-f²/σ²) + hi_floor)

DC:      reg ≈ 10 × (2.0 + 0.3) = 23  → 幾乎不反卷積
Nyquist: reg ≈ 10 × 0.3 = 3           → 激進反卷積
```

三個參數（sigma, lo_mult, hi_floor）都是 learnable，訓練中自適應調整。

## 候選

| Tag | FREQ_REG | ALPHA | WINSORIZE | 說明 |
|-----|---------|-------|-----------|------|
| `r37_freqreg_p95` | True (σ=0.15, lo=2.0, hi=0.3) | 0.10 | p95 | 主候選：freq reg + R33 Winsorize |
| `r37_freqreg_only` | True | 0.10 | 無 (1.0) | 純 freq reg，不搭配 Winsorize |

## 分支

`sandbox/r37`
