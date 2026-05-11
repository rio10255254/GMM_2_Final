# R39 外部 GMF 比較 — `r39_combo_strong_avg_a030`

候選:`COMBO` 與 `r39_shape_mix_strong` 兩組權重 checkpoint 的 **alpha = 0.30** 線性插值。

方法:`Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md`(原始 step_std,只移除 `|z| > 5` 的 GMF 失敗 step)。

## Headline 數字

| scale | a030 step_std | COMBO 外部 step_std | delta | delta % | status |
|---|---:|---:|---:|---:|:---:|
| 8px | 0.143794 | 0.154515 | -0.010721 | -6.94% | **IMPROVED** |
| 0p8px | 0.140008 | 0.131560 | +0.008448 | +6.42% | **TRADEOFF_OK** |
| 0p08px | 0.083941 | 0.099891 | -0.015950 | -15.97% | **IMPROVED** |

整體 verdict:**PASS_TRADEOFF**(tradeoff_max_pct = 7.0%)

## 各 scale 詳細

### 8px (pitch8px)

- frames: 100 (steps=99)
- first / last: `VisionTop_20251029182704617.bmp` ... `VisionTop_20251029184451292.bmp`
- median step: -8.0400
- raw std: `0.143794`
- filtered std (headline): `0.143794`
- outliers ( |z| > 5 ): 0

### 0p8px (pitch0p8px)

- frames: 60 (steps=59)
- first / last: `VisionTop_20251029185341723.bmp` ... `VisionTop_20251029190416478.bmp`
- median step: -0.7980
- raw std: `0.140008`
- filtered std (headline): `0.140008`
- outliers ( |z| > 5 ): 0

### 0p08px (pitch0p08px)

- frames: 40 (steps=39)
- first / last: `VisionTop_20251029193126446.bmp` ... `VisionTop_20251029193825916.bmp`
- median step: -0.0620
- raw std: `0.083941`
- filtered std (headline): `0.083941`
- outliers ( |z| > 5 ): 0

## Cross-Alternate 比較

參考數字來自 `ESTIMATOR_POLICY.json`。

| candidate | 8px | 0.8px | 0.08px |
|---|---:|---:|---:|
| COMBO (formal_baseline) | 0.154515 | 0.131560 | 0.099891 |
| R33 (gmf_extreme_alternate) | 0.153343 | 0.119049 | 0.086274 |
| R38v2 (visual_priority_alternate) | 0.143988 | 0.134205 | 0.106457 |
| R30 (former_baseline) | 0.205193 | 0.167862 | 0.157720 |
| **a030 (this candidate)** | 0.143794 | 0.140008 | 0.083941 |

### 各 scale 排名(越低越好,只列有外部 GMF 的候選)

- **8px**: a030 (0.1438) < R38v2 (0.1440) < R33 (0.1533) < COMBO (0.1545)
- **0p8px**: R33 (0.1190) < COMBO (0.1316) < R38v2 (0.1342) < a030 (0.1400)
- **0p08px**: a030 (0.0839) < R33 (0.0863) < COMBO (0.0999) < R38v2 (0.1065)

## 建議角色

從上面的 cross-alternate 排名來看,a030 的特性是:

- **8px**:在頭部與 R38v2 統計打平(0.1438 vs 0.1440,~0.1% 差距落在 GMF noise 之下)
- **0.08px**:全候選之冠,連 R33 都贏(比 R33 再低約 2.7%)
- **0.8px**:四者中最弱(vs COMBO +6.4%,但仍比 R30 former baseline 低 −16.6%)

建議角色:**shape_generalization_endpoint_alternate** —— 同時需要形狀泛化與 8px / 0.08px 端點精度的 deployment;0.8px 取向的 deployment 不適合(那邊用 COMBO 或 R33)。

附帶軸(held-out shape PSNR,不在傳統 GMF 表上):a030 = 25.03 vs COMBO = 22.84(+2.19 PSNR)。來源:`Experiments/R39_ShapeGeneralization/results/weight_sweep/sweep_summary.md`

## 等待升級決定

這份報告只記錄外部 GMF 量測。要不要把 a030 升進 `ESTIMATOR_POLICY.json` 的 `approved_alternates`,是專案 owner 必須明確拍板的另一個決定。在那之前 a030 掛在 `open_side_tracks`,狀態 `external_gmf_complete_alternate_grade_pending_promotion`。
