# 實驗索引 / Experiment Index

Last updated: 2026-05-11

一頁式快速索引——完整數字、checkpoint 路徑、外部 GMF 結果見 `ESTIMATOR_POLICY.json` 與各實驗 `reports/`。

視覺 demo 圖（每輪代表性重建圖 / 指標圖）見根目錄的 [`RECON_GALLERY.md`](../RECON_GALLERY.md)。

---

## Active（formal baseline + approved alternates）

| Round | 目錄 | Branch | 角色 | 關鍵報告 |
|-------|------|--------|------|---------|
| **COMBO** | `R38v2SeqFixed/` | `sandbox/r38v2` | formal production baseline | `R38v2SeqFixed/reports/COMBO_RESULTS.md` |
| **R33** | `R33RobustLoss/` | `sandbox/r33` | GMF extreme alternate | `R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md` |
| **R38v2** | `R38v2SeqFixed/` | `sandbox/r38v2` | visual priority alternate | `R38v2SeqFixed/reports/R38v2_RESULTS.md` |
| **R39R40_avg_a025** | `R39_ShapeGeneralization/results/a030_x_a043_sweep/` | (cross-round; checkpoints from `sandbox/r39` + `sandbox/r40`) | balanced full-spectrum alternate（2026-05-11 升級）| `R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md` |

## Open Research / Side Tracks

| Round | 目錄 | 狀態 |
|-------|------|------|
| R45 Family Boundary Adapter | `R45_FamilyBoundaryAdapter/` | R45A/R45B 完成：輸出端小校正守住位移但沒有改善大區塊/混合形狀；R45B 確認能力分散存在（逐張 oracle `0.2253` vs R44B `0.3384`，改善 `33.42%`；固定分族 oracle `0.2968`，改善 `12.30%`），但老師優勢不乾淨，多數老師在邊界像素殘差方向比 R44B 更差。研究負結果，不送外部 GMF；下一步若繼續單一入口，應做中間特徵層小分支 + 局部選擇器 |
| R44 Universal Boundary Motion Fidelity | `R44_UniversalBoundaryMotionFidelity/` | R44A-R44H Step B 皆已完成；`r44_motion_from_r42_best` 仍是最佳通用位移候選（整體位移 `0.3813 px`、格線位移 `2.2457 px`）。R44H Step A 證明家族平均可改善大區塊/混合形狀但會犧牲位移；Step B 單一老師局部蒸餾守住位移（`0.3837 px`）但形狀錯誤變差（`0.3481` vs `0.3384`）。研究成功但不可升級；不建議進 Step C 多老師全模型蒸餾，下一步應轉向 adapter / 分族小頭 / 分族選擇 |
| R43 Candidate Usability Audit | `R43_CandidateUsabilityAudit/` | analysis-only 近期候選堪用性盤點與肉眼檢查圖完成；沒有新候選可全面取代 COMBO；`R39 a030` 是最接近正式替代討論的近期候選，`R42` full endpoints 是顯微邊界重建最有價值的研究/人工檢查候選，但後補外部 GMF 確認不能作正式量測替代 |
| R42 Microscopy Boundary Fidelity | `R42_MicroscopyBoundaryFidelity/` | 訓練、本地完整分析、低比例權重平均、守門 KD 診斷與外部 GMF 補測皆已完成；R42 明顯改善未看過顯微邊界重建（最佳 PSNR 34.18、boundary F1 0.87，COMBO 為 20.55 / 0.63），但最佳外部候選 `r42_r41_best` 仍退步過大（8px +24.63%、0.8px +94.33%、0.08px +98.87%），所以 R42 僅保留研究用途，不建議作量測替代 |
| R41 Ring Distillation | `R41_RingDistillation/` | 訓練與 COMBO/R41 權重掃描已完成；direct endpoint 證明顯微能力很強（PSNR `29.4556` / HF `0.7241`），但沒有任何平均 alpha 同時通過顯微能力與本地環形守門；高 alpha 0.45/0.50 顯微通過但 0.8px/0.08px 環形失敗，所以 R41 僅作研究紀錄，不送外部 GMF |
| R40 Microscopy Feature Coverage | `R40_MicroscopyFeatureCoverage/` | 訓練、本地分析與外部 GMF 已完成；端點證明顯微特徵能力可被推高，但環形能力退步；`r40_combo_best_avg_a045` 改善顯微驗證，外部 8px 卻比 COMBO 退步 +22.80%，所以 R40 僅作研究紀錄，不升級 |
| R39 Shape Generalization | `R39_ShapeGeneralization/` | 訓練 endpoint 不可升級；`r39_combo_strong_avg_a030`（α=0.30 權重平均）external GMF PASS_TRADEOFF（8px −6.94%、0.08px −15.97% 專案歷史最低、0.8px +6.42% 在 alternate 容忍區內）；視覺在 sharp band（edge_steepness 比 COMBO 退 5.6%，遠優於 R33 soft band）；alternate-grade，等專案決策是否升級 |
| R26 PSF | `R26NewPSFCheck/` | pending external GMF; not active mainline |

## Closed / Falsified

| Round | 目錄 | Branch | Verdict |
|-------|------|--------|---------|
| R32 | `R32Sandbox/` | `sandbox/r32` | external FAIL, 0.8px +97.7% |
| R33c | `R33ContrastFix/` | `sandbox/r33-contrast` | contrast fix did not recover |
| R34 / R35 / R37 | (sandbox only) | `sandbox/r34` / `r35` / `r37` | all failed to restore sharpness |
| R38 | `R38SeqConsistency/` | `sandbox/r38` | seq all-stages noise corrupted 0.8px |

Round31（legacy batch）亦 closed，見 `Traing_Progress/organized_20260316/round31/`。

## 完整系列報告

R33 → R38v2 → COMBO 的 12 候選 / 7 輪完整系列見 `R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`。

## 規範文件

- `docs/operations/STARTING_NEW_EXPERIMENT.md` — 命名、模板、SOP 三合一
- `docs/operations/QUIRKS.md` — 歷史遺留事項
