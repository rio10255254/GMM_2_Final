# Round 35 — Alpha Boost + R33 Winsorize

## 假說

R33 hard_p95 的銳度退步（-32%）部分源於 physics layer alpha 只有 0.10——
encoder 收到幾乎未處理的模糊影像，必須同時學「反卷積」和「銳化」，
兩者在 Winsorize 下互相競爭。

如果提高 alpha（0.20~0.25），physics layer 先做更多 Wiener 反卷積，
encoder 收到更乾淨的輸入 → 需要的銳化梯度更小 → Winsorize 截掉的比例更少
→ 銳度損失可能減小，穩定性保持。

## 設計

不改任何程式碼——只改 TrainConfig 的 `PSF_PHYS_ALPHA_INIT`。
R33 Winsorize (ROBUST_LOSS_PERCENTILE=0.95, WARMUP=10) 保持不變。

## 候選

| Tag | ALPHA_INIT | PERCENTILE | 說明 |
|-----|-----------|-----------|------|
| `r35_alpha025_p95` | 0.25 | 0.95 | 主候選：大幅提升 physics layer |
| `r35_alpha020_p95` | 0.20 | 0.95 | 保守版 |

## 和先前 Rounds 的差異

| Round | 改了什麼 | 類型 |
|-------|---------|------|
| R33 | Winsorize spatial losses | Loss 內部統計 |
| R34 | 頻域分離 gradient loss | Loss 計算方式 |
| **R35** | **Physics layer alpha 初始值** | **模型輸入品質** |

R35 改的不是 loss，是模型「看到的世界」——這和 R31 改 loss weight 本質不同。

## 風險

- alpha 有硬限 [0.05, 0.35]，0.25 在安全範圍
- alpha 是 learnable 參數，訓練中會自適應調整
- Pure PSF Control 已驗證新 PSF 不會崩潰
- 最差結果是沒改善

## 分支

`sandbox/r35`
