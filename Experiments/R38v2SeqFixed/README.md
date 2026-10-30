# Round 38v2 — Sequence Consistency Training (Fixed)

## 假說

R38 原版的 seq training 在 8px 上取得最佳 step_std（0.136），edge steepness 超越 R30（+9%），
但被 0.8px/0.08px stage 的噪聲梯度干擾，導致 0.8px 退步、contrast 被壓縮。

R38v2 透過三重修復解決：
1. **Signal-strength gate**: `SEQ_MIN_DELTA_THRESHOLD=0.002`
2. **Warmup**: 前 15 epoch 只跑 reconstruction
3. **只用 8px stages**: 120 pairs，100% crop 覆蓋率

## 結果

此目錄包含兩個生產候選：

### R38v2（視覺優先型）
- 機制：Seq 8px-only + gate + warmup，**無 Winsorize**
- 0.8px: **0.134** (-20%)，Edge steepness: **+89%** vs R30
- Checkpoint: `Experiments/Legacy/..._20260406_235957/weights/best_tradeoff.pth.tar`

### COMBO（最均衡型）
- 機制：R38v2 的 seq + R33 的 Winsorize p95（`r38v2_8px_gate_p95`）
- 0.8px: **0.132** (-22%)，Edge steepness: **+89%**，Residual_std 歷史最佳
- Checkpoint: `Experiments/Legacy/..._20260408_003525/weights/best_tradeoff.pth.tar`
- COMBO 同時繼承 R33 和 R38v2 的機制——詳見 `reports/COMBO_RESULTS.md`

## 資料

- Seq data: `Training_Data/generated_convolved/stage_25,26/`（用新 PSF 重新卷積 2026-04-06）
- External GMF: `results/external_gmf/`（R38v2）、`results/external_gmf_combo/`（COMBO）

## 分支

`sandbox/r38v2`
