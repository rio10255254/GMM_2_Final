# R38v2 Sequence Consistency Training (Fixed) Results

**Date**: 2026-04-07
**Branch**: `sandbox/r38v2`
**Checkpoint**: `Traing_Progress/training_progress_..._20260406_235957/weights/best_tradeoff.pth.tar`
**Best Epoch**: 54

## 設計：三重修復

R38 原版的問題：0.8px/0.08px stage 的 delta 太小，seq_loss 注入噪聲梯度。

R38v2 的三項修復：
1. **Signal-strength gate**: `SEQ_MIN_DELTA_THRESHOLD=0.002`，delta < 0.002 的 batch 跳過
2. **Warmup**: `SEQ_WARMUP_EPOCH=15`，前 15 epoch 只跑 reconstruction（無 seq_loss）
3. **只用 8px stages**: stage_25/26（120 pairs），信號最強、100% crop 覆蓋

## 外部 GMF 結果 — 三尺度全部通過

| 尺度 | R30 baseline | R33 p95 | **R38v2** | vs R30 | vs R33 |
|------|-------------|---------|----------|--------|--------|
| **0.8px** | 0.167862 | 0.119049 | **0.134205** | **-20.1%** | +12.7% |
| 0.08px | 0.157720 | 0.086274 | **0.106457** | **-32.5%** | +23.4% |
| 8px | 0.205193 | 0.153343 | **0.143988** | **-29.8%** | **-6.1%** |

零 outliers。Lag-1 autocorrelation: -0.55 (0.8px)、-0.41 (0.08px)、-0.46 (8px)。

## 視覺品質 — 相比 R33 大幅回升

| 指標 | R30 | R33 p95 | **R38v2** | R38v2 vs R30 |
|------|-----|---------|----------|-------------|
| **Edge steepness** | 4.05 | 3.16 (-22%) | **7.67** | **+89%** |
| **Edge contrast** | 89.1 | 50.8 (-43%) | **77.5** | **-13%** |
| **Contrast std** | 34.64 | 26.49 (-24%) | **30.92** | -11% |
| Gradient mag | 3.46 | 2.36 (-32%) | **2.67** | -23% |
| Mean intensity | 145.9 | 133.2 | 139.6 | -4% |
| 8px k2 verdict | stable | moderate | **stable** | — |

## R38v2 vs R33 的 trade-off 定位

| 維度 | R33 p95 | R38v2 | 誰贏 |
|------|---------|-------|------|
| 0.8px GMF step_std | **0.119** | 0.134 | R33（極致精度） |
| 8px GMF step_std | 0.153 | **0.144** | R38v2 |
| Edge steepness | 3.16 | **7.67** | R38v2（+143%） |
| Edge contrast | 50.8 | **77.5** | R38v2（+53%） |
| Contrast std | 26.49 | **30.92** | R38v2 |
| k2 stability (8px) | moderate | **stable** | R38v2 |

**R33 是 GMF 極致型：step_std 最低但視覺退步。**
**R38v2 是均衡型：GMF 改善 -20% 且視覺品質接近 R30。**

## 修復效果驗證

| 修復 | R38 (broken) | R38v2 (fixed) | 改善 |
|------|-------------|--------------|------|
| Signal gate 效果 | Total loss E1=0.338 | E1=0.160 → E16=0.193 | 噪聲梯度被過濾 |
| Warmup 效果 | GradMag% E1=24.6% | E15=23.0% → E16=22.2% | 銳度先穩定再加 seq |
| 8px-only 效果 | 624 pairs (多數無效) | 120 pairs (全部有效) | 信號品質大幅提升 |
| Edge steepness | 4.41 | **7.67** | +74%（warmup 讓 encoder 先學好銳度） |
| Contrast | 49.3 | **77.5** | +57%（無噪聲干擾，reconstruction 正常） |

## Checkpoint Registry

| Timestamp | Round | Candidate | Result |
|-----------|-------|-----------|--------|
| 20260405_073906 | R33 | hard_p90 | 0.8px internal 0.146 |
| **20260405_091941** | **R33** | **hard_p95** | **External PASS: 0.8px 0.119** |
| 20260405_114824 | R33 | lap_only_p95 | FAILED |
| 20260405_153826 | R33 | soft_p95 | FAILED |
| 20260405_225024 | R34 | freq_split_s15_p95 | FAILED |
| 20260405_235455 | R35 | alpha025_p95 | FAILED |
| 20260406_004833 | R37 | freqreg_p95 | FAILED |
| 20260406_122842 | R38 | seq_only | 8px good, 0.8px weak |
| 20260406_222404 | R33c | stat03 | FAILED (contrast worse) |
| **20260406_235957** | **R38v2** | **8px_gate** | **External PASS: 0.8px 0.134** |
