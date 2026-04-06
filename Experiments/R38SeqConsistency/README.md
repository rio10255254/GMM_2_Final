# Round 38 — Sequence Consistency Training

## 假說

R33 Winsorize 靠「壓制所有角度的梯度」來達成幀間一致性 → 銳度退步 -32%。
但數據顯示銳度和穩定性的相關性接近零（corr = -0.107）——不穩定不是因為銳度。

如果用 sequence pair loss 直接教模型幀間一致，就不需要壓制銳度。
模型可以在穩定的角度保持銳利，只在不穩定的角度被推去修正。

## 設計

兩條平行資料流：
1. **Single-crop**（和 R30 一樣）：隨機 256×256 crop → reconstruction + gradient + EQ loss → 管銳度
2. **Sequence pair**（R38 新增）：連續幀 crop pair → 幀間 delta + gradient loss → 管一致性

不用 Winsorize（ROBUST_LOSS_PERCENTILE = 1.0）。

## 資料

合成 sequence 資料，已用新 Whole-FOV PSF 重新卷積（2026-04-06）：
- src: `Training_Data/generated_convolved/stage_19~28/`
- lbl: `Training_Data/generated/stage_19~28/`
- 624 pairs，0.08/0.8/8px 三尺度

## 候選

| Tag | SEQ_ENABLE | PERCENTILE | SEQ_LOSS_W | SEQ_GRAD_W |
|-----|-----------|-----------|-----------|-----------|
| `r38_seq_only` | True | 1.0（無 Winsorize） | 0.3 | 0.1 |
| `r38_seq_p95` | True | 0.95（有 Winsorize） | 0.3 | 0.1 |

## 分支

`sandbox/r38`
