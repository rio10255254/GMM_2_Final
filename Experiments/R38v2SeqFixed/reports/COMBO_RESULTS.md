# COMBO: Winsorize p95 + Seq 8px Gate + Warmup — Results

**Date**: 2026-04-08
**Branch**: `sandbox/r38v2`
**Candidate**: `r38v2_8px_gate_p95`
**Checkpoint**: `Traing_Progress/..._20260408_003525/weights/best_tradeoff.pth.tar`
**Best Epoch**: 21

## 設計

同時啟用 R33 的 Winsorize（p95）和 R38v2 的 sequence training（8px gate + warmup 15）。
三重 warmup 時序：
- Epoch 1-10: 純 reconstruction（無 Winsorize、無 seq）
- Epoch 11-15: Winsorize 啟用（GradMag 23%→15%），seq 仍關閉
- Epoch 16+: seq 啟用（total loss 0.063→0.190 跳升）

## 外部 GMF — 三尺度全部通過

| 尺度 | R30 | R33 p95 | R38v2 | **COMBO** | vs R30 |
|------|-----|---------|-------|----------|--------|
| **0.8px** | 0.167862 | **0.119049** | 0.134205 | **0.131560** | **-21.6%** |
| 0.08px | 0.157720 | **0.086274** | 0.106457 | **0.099891** | **-36.7%** |
| 8px | 0.205193 | 0.153343 | **0.143988** | 0.154515 | -24.7% |

Outlier policy: only remove GMF tool failures (z > 5). See `GMF_STEP_STD_METHODOLOGY.md`.
- R30, R38v2, COMBO: all scales 0 outliers → headline = raw std.
- **R33 8px is the sole exception**: raw 0.932763, 2 GMF failures (z=6.98, 6.90) removed → headline 0.153343.
- R33 0.8px and 0.08px: 0 outliers → headline = raw std.
- COMBO 0.8px borderline step (z=3.01) is real stage variation, correctly retained.

Lag-1: -0.52 (0.8px), -0.47 (0.08px), -0.24 (8px).

## 視覺品質

| 指標 | R30 | R33 | R38v2 | **COMBO** |
|------|-----|-----|-------|----------|
| Edge steepness | 4.05 | 3.16 | **7.67** | **7.67** |
| Contrast std | 34.64 | 26.49 | 30.92 | **32.35** |
| Gradient mag | 3.46 | 2.36 | 2.67 | **2.78** |
| Edge contrast | 89.1 | 50.8 | 77.5 | 74.1 |

## Residual_std — 全面歷史最佳

| 尺度 / 邊界 | R30 | R33 | R38v2 | **COMBO** |
|-------------|-----|-----|-------|----------|
| 0.8px outer | 2.599 | 2.905 | 3.154 | **2.329** |
| 0.8px inner | 2.894 | 2.684 | 3.187 | **2.044** |
| 8px outer | 2.468 | 3.211 | 2.810 | **2.192** |
| 8px inner | 2.719 | 2.970 | 2.839 | **2.000** |
| 0.08px outer | 2.608 | 2.875 | 3.166 | **2.335** |
| 0.08px inner | 2.915 | 2.682 | 3.368 | **2.102** |

## 三候選定位

| 候選 | 定位 | 0.8px GMF | 視覺 | 最佳用途 |
|------|------|----------|------|---------|
| R33 p95 | GMF 極致 | **0.119** | 退步 | 純 GMF 定位精度 |
| R38v2 | 視覺優先 | 0.134 | **+89% steep** | 需要人看的場景 |
| **COMBO** | **最均衡** | **0.132** | **+89% steep, best contrast** | **同時需要 GMF + 視覺** |

## Internal vs External 的驚喜

Internal step_std 0.178（超過 0.168 門檻），但 external 0.132（大幅低於門檻）。
COMBO 的 internal-to-external 比率 0.742（R33: 0.922, R38v2: 0.789）。

原因推測：COMBO 的 residual_std 是歷史最低（0.8px inner 2.044 vs R30 2.894, -29%），
更低的 residual 讓 GMF 的 edgel detection 在每一幀更精確，降低了 step_std。
Internal step_std 用 circle-fit（對 residual 敏感），GMF 用 template matching（更穩健），
所以 residual 改善對 external 的影響比對 internal 更大。

## Checkpoint

`D:\GMM_2_Final\Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\weights\best_tradeoff.pth.tar`
