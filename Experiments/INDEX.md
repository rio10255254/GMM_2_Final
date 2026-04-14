# 實驗索引 / Experiment Index

Last updated: 2026-04-09

一頁式快速索引——看這張表就能知道所有實驗的身份、狀態、關鍵路徑。
One-page index for all experiments in this project.

---

## 正式 baseline 與核准候選（External GMF 通過）

| Round | 目錄 | Branch | 機制 | 0.8px GMF | 視覺 | 定位 |
|-------|------|--------|------|----------|------|------|
| **R33** | `R33RobustLoss/` | `sandbox/r33` | Winsorize spatial loss p95 | **0.119** (-29%) | steep -22% | approved GMF extreme alternate |
| **R38v2** | `R38v2SeqFixed/` | `sandbox/r38v2` | Seq 8px gate + warmup 15, no Winsorize | **0.134** (-20%) | steep +89% | approved visual-priority alternate |
| **COMBO** | `R38v2SeqFixed/` | `sandbox/r38v2` | Winsorize p95 + seq 8px gate + warmup | **0.132** (-22%) | steep +89%, best res | formal adopted baseline |

## 否定實驗（Internal 或方法論層面失敗）

| Round | 目錄 | Branch | 機制 | 失敗原因 |
|-------|------|--------|------|---------|
| R33 ablation | `R33RobustLoss/` | `sandbox/r33` | lap_only_p95 | W_GRADMAG 不能拿掉 |
| R33 ablation | `R33RobustLoss/` | `sandbox/r33` | soft_p95 (Charbonnier) | 比 hard 更差 |
| R33c | `R33ContrastFix/` | `sandbox/r33-contrast` | W_STAT 0.30 | Contrast 反而更差 |
| R34 | *(sandbox/r34 only)* | `sandbox/r34` | Loss 層 Gaussian 分頻 | lo/hi 梯度在 patch 上高度相關 |
| R35 | *(sandbox/r35 only)* | `sandbox/r35` | Physics alpha 0.25 | 均勻放大含噪 HF |
| R37 | *(sandbox/r37 only)* | `sandbox/r37` | PSF 頻率依賴 reg | HF 低 reg 放大 Wiener 噪聲 |
| R38 | `R38SeqConsistency/` | `sandbox/r38` | Seq 全 stages, no gate | 0.8px delta 太小，噪聲梯度干擾 |

## 歷史實驗（promotion 前主線與 side track）

| Round | 目錄 | Branch | 狀態 | 說明 |
|-------|------|--------|------|------|
| R30 former baseline | *(legacy mainline)* | — | former production baseline | B1 dironly breakthrough before COMBO promotion |
| R26 PSF | `R26NewPSFCheck/` | — (merged to main) | open side track | Whole-FOV PSF 驗證 + formal audit |
| R32 | `R32Sandbox/` | `sandbox/r32` | External FAIL | domain rebalancing, 0.8px +97.7% |

## Checkpoint 對照表

| 時間戳 | Round | 候選 | Best Epoch | 0.8px External |
|--------|-------|------|-----------|---------------|
| 20260405_091941 | R33 | hard_p95 | 23 | 0.119049 |
| 20260406_235957 | R38v2 | 8px_gate | 54 | 0.134205 |
| 20260408_003525 | COMBO | 8px_gate_p95 | 21 | 0.131560 |
| 20260405_073906 | R33 | hard_p90 | 23 | — (internal only) |
| 20260405_114824 | R33 | lap_only | 32 | — (否定) |
| 20260405_153826 | R33 | soft_p95 | 22 | — (否定) |
| 20260406_122842 | R38 | seq_only | 22 | — (8px 好但 0.8px 弱) |
| 20260406_222404 | R33c | stat03 | 21 | — (否定) |

所有 checkpoint 在 `Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_[TIMESTAMP]/weights/best_tradeoff.pth.tar`。

## 關鍵報告快速連結

| 報告 | 位置 |
|------|------|
| 完整系列報告 | `R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md` |
| COMBO 結果 | `R38v2SeqFixed/reports/COMBO_RESULTS.md` |
| GMF 計算方法論 | `R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md` |
| 量化修復分析 | `R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md` |
| Internal/External 偏差分析 | `R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md` |
| 資料流審計 | `R38v2SeqFixed/reports/DATA_FLOW_AUDIT.md` |

## 規範文件

新實驗建立前請先讀：
- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 命名規則
- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 目錄結構模板
- `docs/operations/QUIRKS.md` — 歷史遺留事項
