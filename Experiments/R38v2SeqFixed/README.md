# Round 38v2 — Sequence Consistency Training (Fixed)

## 假說

R38 原版的 seq training 在 8px 上取得最佳 step_std（0.136），edge steepness 超越 R30（+9%），
但被 0.8px/0.08px stage 的噪聲梯度干擾，導致 0.8px 退步、contrast 被壓縮。

R38v2 透過三重修復解決：
1. **Signal-strength gate**: `SEQ_MIN_DELTA_THRESHOLD=0.002`
2. **Warmup**: 前 15 epoch 只跑 reconstruction
3. **只用 8px stages**: 120 pairs，100% crop 覆蓋率

## 結果

外部 GMF 三尺度全通過（均衡型候選）：
- 0.8px: 0.134 (-20%)，Edge steepness: +89% vs R30
- 8px: 0.144 (-30%)，比 R33 還好

## 資料

- Checkpoint: `Traing_Progress/..._20260406_235957/weights/best_tradeoff.pth.tar`
- Seq data: `Training_Data/generated_convolved/stage_25,26/`（用新 PSF 重新卷積 2026-04-06）
- External GMF: `results/external_gmf/`

## 分支

`sandbox/r38v2`
