# PROJECT STATE / 專案狀態

Last updated: 2026-09-06（R119 原始碼與小型重現稽核揭露交接實作偏差；修正機制解釋，保留實際訓練與量測紀錄；正式基準不變）

專案控制與整體巡檢請使用 `python Tools/project_control_center.py`。
機器真相：`ESTIMATOR_POLICY.json`。

<!-- QUICK_HANDOFF_START -->
## 🟢 Quick Handoff (3-min read)

### Current Formal Baseline
**COMBO / r38v2_8px_gate_p95** (effective 2026-04-08)

### Storage / Historical Archive
專案已完成 13 個大型執行批次，涵蓋 23 個獨立快照或封存單位；H 槽保存約 208.940 GiB 完整歷史，D 槽累計淨回收約 161.555 GiB。2026-08-24 的 R1–R51 全面整理新增四批：R16–R31 舊日期批次、主專案 R32/R33Contrast/R38Seq/R42/R44/R45/R46、Lab R46/R47，以及共享訓練歷史中的 61 個已結案 run；新增 H 槽完整歷史 116.3116 GiB，四次精簡量測合計回收 80.8936 GiB，所有清單在精簡前後均 PASS。補回相容性代表模型、Lab 精簡核心與 R26 compact recipe 後，本輪 D 槽淨增加 79.6502 GiB，目前約 202.59 GiB，仍已離開緊急線。R30、COMBO、R33、R38v2、R39/R40、Lab R39/R40/R51、原始量測與未能可靠對應的歷史均保留；R87–R95 不在本次範圍。完整位置見 `docs/operations/PROJECT_ARCHIVE_INDEX.md`，本輪完整決策見 `docs/operations/PROJECT_R1_R51_STORAGE_REVIEW_20260824.md`。這些存放調整不改變任何實驗 verdict、正式 baseline 或候選身分。

2026-08-10 已完成全專案唯讀結構清冊：2,822,006 個檔案、341,031 個資料夾、1,067.416 GiB，零掃描錯誤；清冊成果已逐檔核對並保存到 H 槽 `inventory_snapshots/20260810_full_project`。這次只建立索引、專案地圖與未來結構藍圖，沒有搬動大型資料，也不改變任何科學結論。現況盤點與分階段設計見 `docs/operations/PROJECT_STRUCTURE_INVENTORY_20260810.md`、`docs/operations/PROJECT_FUTURE_STRUCTURE_PLAN.md`。

### Approved Alternates
- `R33 / r33_robust_p95` — GMF extreme alternate
- `R38v2 / r38v2_8px_gate` — visual priority alternate
- `R39R40_avg_a025 / r39r40_complementary_avg_a025` — **balanced full-spectrum alternate（2026-05-11 升級）**；R39 a030 與 R40 a043 跨輪權重平均 α=0.25 點；外部 GMF 三尺度都在 ±5.18% 內（首個過 3% 升級上限的候選）；12 個顯微/形狀分類 PSNR 全勝 COMBO 跟 a030；視覺在 sharp band（vs R30 約 +78.1%）

### Former Baseline
`Round30 / r30_b1_dironly` — historical former baseline (歷史前任 baseline)

### Open Research / Side Tracks
- **R119 controlled boundary factors and decision (2026-09-06):** `Experiments/R119_SequenceGeometryValidation/reports/R119_CONTROLLED_BOUNDARY_FACTORS.md` records 240 physical blur/gain/motion fixtures, 100 declared radiometric follow-ups and 432 existing real profile observations. Clean standard fixtures do not support deleting the position path or rewriting the width operator. Independent intensity offset/contrast exposes limited unwanted shifts. A calibrated half-contrast readout finds real Raw already outward versus SEM (median +0.661px), full E42 +0.934px and position-off +0.792px, unlike the inward bias of standard blurred synthetic circles. Decision: first validate optical/SEM boundary-reference correspondence and observation coverage; retain model capabilities, no hardcoded shrink, no long training. Exact physical cause of the reference discrepancy remains unresolved. All 93 protected inputs unchanged; controls are diagnostics, not a new holdout or promotion.
- **R119 training-position diagnosis (2026-09-06):** `Experiments/R119_SequenceGeometryValidation/reports/R119_TRAINING_POSITION_DIAGNOSIS.md` records known-answer objective tests and frozen E24/E42 comparisons on 96 train + 96 development scenes. The objective penalizes uncompensated dilation but cannot distinguish an allowed position/detail compensation with identical final output. E42 position removal worsens image MAE in 61/96 train and 59/96 development scenes; these image metrics are not interchangeable with real SEM contour metrics. Real predicted normals align with SEM outward direction (median dot 0.99775), while all 432 observations have positive median implied outward output displacement. This narrows the diagnosis; neither a simple sign error nor one historical loss term is proven causal. No weights or protected evidence changed, no training launched.
- **R119 cross-exposure position diagnosis (2026-09-06):** The new report `Experiments/R119_SequenceGeometryValidation/reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md` extends the corrected exposure-13 experiment to all 12 existing exposures and 36 pillars. With E42 frozen, disabling only the position path improves paired contour error in 431/432 observations, 36/36 pillar medians, and 12/12 exposure medians; 430/432 also improve the matched-global-amplitude control. All 432 areas decrease relative to full E42. However 282/432 contours remain worse than Raw; real texture fidelity and modified-output displacement stability are not certified. Historical masks/tables reproduce exactly and 88 protected historical files remain unchanged. No training, confirmation evaluation, or promotion. Initial crop-export parity failure and its normalization-based diagnosis are preserved separately.
- **Current thesis research status (2026-09-06):** Read `Experiments/R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md` before the older R118/R119 completion notes. R119 B E42 did finish 42 epochs and retains measured ACM/LSC capability, but the claim of faithful P00–P12 execution is withdrawn: B did not implement fixed-optics sequences, controls/readouts contain verified confounds, and confirmation did not cover every planned readout. Exposure-13 frozen-path tests implicate boundary-position correction in SEM expansion while preserving detail. Existing receipts are historical integrity evidence, not semantic proof. No new training or promotion; thesis criteria remain ACM, displacement stability and faithful detail; external GMF is separate.
- `Experiments / R61_STEP_Generalization_20260623` — Recent R61 multi-round tests are now organized as an R-series research line with thesis relevance, not scratch output. The key thesis/main-model candidate is `R61_stepguard_v16_dpv96_matched_20260623`, tied to the Step boundary/displacement/CD validation package. Current status: supports Step-sample boundary/CD preservation and displacement stability evidence; not a formal COMBO replacement and not a universal cross-sample guarantee.
- `LabSystem_MOSR / R51_BlurSourceProbe` — Lab-system short training probe only, not a main-project baseline challenger. It tested Gaussian, weak-BADS alpha `0.50`, and mixed-PSF corner blur packages after R50. Best result was mixed-PSF `best_tradeoff`: median real-corner shift improved from Lab R40 control `4.243 px` to `2.828 px`, but large-shift corner rate worsened from `24.581%` to `36.872%`. Directional evidence only; not promotable. Next Lab work should keep the mixed-PSF direction but add a real-corner stability guard before another long run.
- `LabSystem_MOSR / R52_CornerStabilityGuard` — Lab-system formal long run completed, not a main-project baseline challenger and not promoted. It kept the R51 mixed-PSF direction, added 4000-pair corner-stability training data with geometry sidecars, completed 100 epochs from the R51 mixed-PSF `best_tradeoff` checkpoint, and reconstructed the real Lab `20250605_checkboard` sequence. Best R52 result was the epoch-100 `latest` checkpoint: median real-corner shift `3.606 px` versus Lab R40 `4.243 px`, but large-shift corner rate worsened to `30.447%` versus R40 `24.581%`; real-corner gate failed. The final 23,858-file history is hash-verified on H; D retains reports, code, tests, manifests, logs, three representative checkpoints, complete corner evidence, the restore entry and final execution record. Seven large D sources were removed on 2026-08-24 after double verification, reclaiming 9.4306 GiB. No R52 external GMF score text is present.
- `LabSystem_MOSR / R53_RealisticDatasetCalibration` — Lab-system formal long run completed, not a main-project baseline challenger and not promoted. It rebuilt the Lab training data as a 6000-pair main-project-like mix with 700 ring, 700 shape, 900 micro/detail, 300 mixed-PSF corner, 2050 realistic-boundary, 950 real-background/texture, and 400 masked real CAD-anchor pairs. The 100-epoch scratch run improved internal validation through epoch 100 (`PSNR 26.39`, `SSIM 0.9353`), but real `20250605_checkboard` reconstruction failed the corner gate. R53 `best_tradeoff` had median real-corner shift `3.606 px` but worsened large-shift corner rate to `40.782%`; R53 `latest` regressed to median `9.220 px` and `58.939%` large-shift corners, versus Lab R40 control `4.243 px` / `24.581%`. GMF-ready image folders exist, but no R53 external GMF score text is present yet.
- `LabSystem_MOSR / R54_GeometryRootCauseProbe` — Lab-system diagnostic + masked small-overfit probe completed, not a main-project baseline challenger and not a usable Lab model. It confirmed reconstruction geometry damage, then showed the model can fit local CAD edge supervision when the 20260613 strict-rectangle CAD references are used with an added edge-band mask: masked-package inside MAE improved from input `61.145` to R54 epoch20 `9.268`. However, the same checkpoint failed on the real `20250605_checkboard` sequence: median real-corner shift `9.220 px` and `60.056%` corners above 5 px, versus Lab R40 `4.243 px` / `24.581%`. Conclusion: capacity to fit CAD edges exists, but generalization/output drift is unsafe; do not continue from R54 edge-band as a formal training candidate.
- `LabSystem_MOSR / R55_SourceStyleRealisticTraining` — Lab-system source-style repair validation completed locally, not a main-project baseline challenger and not yet externally GMF-validated. It used the repaired R55 rebuild of the R53-style 6000-pair core package, with generated boundary geometry sidecars restored so the standard R53 recipe stayed comparable. The 50-epoch scratch run produced a useful `best_tradeoff` checkpoint: real `20250605_checkboard` median corner shift improved to `2.828 px` versus Lab R40 `4.243 px`, large-shift corner rate improved to `21.788%` versus R40 `24.581%`, and tail shift improved to `3.606 px` versus R40 `5.000 px`. The `latest` checkpoint failed badly (`8.485 px` median / `51.397%` >5px), so R55 confirms source-style repair helps but overtraining/oversmoothing remains a risk. R55 best is GMF-ready for external follow-up; do not promote without external GMF.
- `LabSystem_MOSR / R56_LabelCoreRepairTraining` — Lab-system label-core repair follow-up completed, not a main-project baseline challenger and not adopted. It used the R56 repaired version of the R53/R55 source-style 6000-pair package and completed a 50-epoch scratch run. Internal validation kept improving to epoch 50 (`PSNR 26.40`, `SSIM 0.9333`), but real `20250605_checkboard` validation failed: R56 `best_tradeoff` matched R55 best median shift (`2.828 px`) but worsened large-shift corner rate (`26.816%` vs R55 `21.788%`) and tail shift (`9.899 px` vs R55 `3.606 px`); R56 `latest` failed badly (`9.899 px` median / `59.777%` >5px). R56 should not replace R55 best, and external GMF is not recommended from this R56 result.
- `LabSystem_MOSR / R50_PSFControlDiagnosis` — Lab-system diagnostic only, not a main-project baseline challenger and not a model-training round. It compared real `20250605_checkboard` edges against clean, Gaussian, weak-BADS, and formal-BADS checkboard-corner controls. Real median edge-width proxy was `7.0 px`; formal BADS was `11.0 px`; Gaussian was `9.0 px`; weak-BADS alpha `0.50` matched width at `7.0 px`. Conclusion: the selected BADS PSF is usable but too soft as the only Lab checkboard-corner blur truth; this diagnosis led to the R51 Gaussian / weak-BADS / mixed-PSF probe.
- `LabSystem_MOSR / R49_CADAnchorRealGeometry` — Lab-system method-transfer line only, not a main-project baseline challenger. R49 completed the 4000-pair CAD-anchor + geometry-sidecar training line and reconstructed the real `20250605_checkboard` sequence, but all tested R49 checkpoints failed the real Lab corner validation (best R49 median corner shift `9.000 px`; previous Lab control `4.243 px`; best R48 `6.708 px`). Negative transfer evidence; not promotable. Its full history was hash-verified on H on 2026-08-10; D retains the canonical reports, scripts, manifests, validation evidence and restore entry.
- `LabSystem_MOSR / R48_RealCornerTransfer` — Lab-system method-transfer line only, not a main-project baseline challenger. R48 completed the 6000-pair real-corner + geometry-sidecar training line and reconstructed the real `20250605_checkboard` sequence, but all tested R48 checkpoints failed the real Lab corner validation (best R48 median corner shift `6.708 px` vs previous Lab control `4.243 px`). Negative transfer evidence; not promotable.
- `R45_FamilyBoundaryAdapter` — R45A/R45B 完成：輸出端小校正守住位移但沒有改善大區塊/混合形狀；R45B 診斷確認能力分散存在（逐張 oracle `0.2253` vs R44B `0.3384`，改善 `33.42%`；固定分族 oracle `0.2968`，改善 `12.30%`），但老師優勢不乾淨，多數老師在邊界像素殘差方向比 R44B 更差；**研究負結果，不送外部 GMF。下一步若繼續單一入口，應做中間特徵層小分支 + 局部選擇器，而不是輸出端校正或全圖蒸餾**
- `R44_UniversalBoundaryMotionFidelity` — R44A-R44H Step B 皆完成；`r44_motion_from_r42_best` 仍是最佳通用位移候選（整體位移 `0.3813 px`、格線位移 `2.2457 px`）。R44H Step A 顯示家族平均可改善大區塊/混合形狀但會犧牲位移；Step B 單一老師局部蒸餾守住位移（`0.3837 px`）但形狀錯誤變差（`0.3481` vs `0.3384`）；**研究成功但不可升級，不建議進 Step C 多老師全模型蒸餾，下一步應轉向 adapter / 分族小頭 / 分族選擇**
- `R43_CandidateUsabilityAudit` — analysis-only 近期候選堪用性盤點與肉眼檢查圖已完成；結論是沒有新候選可全面取代 COMBO，但 `R39 a030` 是目前最接近正式替代討論的近期候選，`R42` full endpoints 是顯微邊界重建最有價值的研究/人工檢查候選；完整表見 `reports/R43A_USABILITY_AUDIT.md`
- `R42_MicroscopyBoundaryFidelity` — 訓練、本地分析、低比例權重平均、守門 KD 診斷與外部 GMF 補測皆已完成；未看過顯微邊界重建明顯改善（`PSNR 34.18`、boundary F1 `0.87`，COMBO 為 `20.55` / `0.63`），但最佳外部候選 `r42_r41_best` 仍退步過大（8px +24.63%、0.8px +94.33%、0.08px +98.87%）；**研究用途，不可作量測替代**
- `R41_RingDistillation` — training + COMBO/R41 sweep complete; direct endpoint proves microscopy capacity (`PSNR 29.4556`, HF `0.7241`), but no alpha passes both microscopy and local ring guard; high-alpha 0.45/0.50 passes microscopy but fails ring 0.8px/0.08px; **research-only, no external GMF candidate**. Full historical payload was hash-verified and archived to H on 2026-08-01; D retains canonical reports, summaries, scripts, one representative checkpoint, and restore context.
- `R39_ShapeGeneralization` — `r39_combo_strong_avg_a030`（COMBO 與 R39_strong 在 α=0.30 的權重平均）external GMF **PASS_TRADEOFF**（8px −6.94%、0.08px −15.97%、0.8px +6.42%）；0.08px 為專案歷史最低；視覺在 sharp band（edge_steepness 比 COMBO 退 5.64%，遠優於 R33 −22%）；**alternate-grade，等專案決策是否升級為 approved alternate**
- `R40_MicroscopyFeatureCoverage` — 顯微特徵能力上限成立,`r40_combo_best_avg_a045` 明顯改善格線/紋理/缺陷驗證,但 external GMF 8px `0.189750` vs COMBO `0.154515`（+22.80%）;**research-only,不升級**。α 補密 sweep（2026-05-11）跑 `0.42`/`0.43`/`0.44`：α=0.43 外部 8 px `−5.91%` / 0.8 px `−3.15%` 但 0.08 px `+21.52%`，三個 α 都仍 RESEARCH_CAPACITY_ONLY；揭露 weight averaging trade-off 在 α 軸上非線性
- `R26NewPSFCheck` (pending external GMF; **not** the active mainline)

### Closed Lines
`Round31`（external regression）、`Round32`（external FAIL）、`R34/R35/R37/R38/R33c`（falsified）

### Working Rules (7)
1. 先讀本檔 Quick Handoff 區完整理解現況
2. 以 repo 正式文件為準，不以 `.codex` / `.claude` 內部 session 檔為準
3. root prose current state 以 COMBO + approved alternates 為主，R26NewPSFCheck 不是 active mainline
4. legacy root runtime 快照已封存到 `docs/archive/legacy_runtime_status/`
5. baseline / verdict / taxonomy 有變時，優先更新本檔 + `ESTIMATOR_POLICY.json`
6. external FAIL 或 closed 的候選，不再以 promising / active 的語氣描述
7. 已移出 D 槽的大型歷史，先從 `docs/operations/PROJECT_ARCHIVE_INDEX.md` 找到 H 槽快照並依清單核對後再恢復

### Canonical sandbox branch
`sandbox/r38v2`（COMBO 的 origin experiment branch）

<!-- QUICK_HANDOFF_END -->

---

## Full Current State / 完整現況

### R119 controlled blur, radiometry and motion decision (2026-09-06)

The controlled study under `Experiments/R119_SequenceGeometryValidation/analysis/controlled_boundary_factors_20260906` separates blur, gain and true object translation before sensor integration. The three simple geometries pass the declared readout calibration; all 340 synthetic cases retain 720 common-valid profiles for seven output paths. Standard blurred circles benefit from outward correction, whereas existing real Raw profiles already lie outward relative to the current SEM digital reference. This is a data/reference discrepancy to resolve, not proof that a fixed inward offset or new loss weight is correct. The independent-level follow-up exposes brightness/contrast dependence but does not fully reproduce real expansion. The chosen priority is the optical/SEM reference contract and independently varied intensity/contrast coverage; no architecture change, training, confirmation access or promotion occurred. See `reports/R119_CONTROLLED_BOUNDARY_FACTORS.md` within R119 for preserved initial calibration failures, revised geometry-only readout calibration, invalid-profile counts and the distinction from locked ACM/LSC metrics.

### R119 training-position diagnostic extension (2026-09-06)

See `Experiments/R119_SequenceGeometryValidation/reports/R119_TRAINING_POSITION_DIAGNOSIS.md` and its `analysis/training_position_diagnosis_20260906` data. Four known-answer cases show that center/pair consistency misses common dilation while local image/edge losses penalize it; equal-output position/detail compensation is not identified by the current objective. These are operator counterexamples, not proof of learned historical compensation. Fixed synthetic tests and real SEM operator-field measurements further narrow the question to necessary versus unnecessary displacement under different imaging conditions. No complete training root cause, new model, or universal solution is claimed. Earlier cross-exposure and causal-audit corrections remain valid.

### R119 cross-exposure diagnostic extension (2026-09-06)

The fixed-E42 position-path diagnosis now covers 36 pillars in all 12 existing SEM-linked exposures. See `Experiments/R119_SequenceGeometryValidation/reports/R119_CROSS_EXPOSURE_POSITION_AUDIT.md` and `analysis/sem_position_audit_20260906` within that experiment. Full / position-off / Raw pooled median contour errors are 0.66176 / 0.58756 / 0.57419 percent of pitch. The within-pillar paired median effect is -0.07691 pitch-percentage-points; a pillar-level bootstrap gives [-0.07976, -0.07112] within this sample only. There is one adverse full-vs-position-off observation (exposure 22, pillar 6). The exact additive detail is retained but output texture changes, so no lossless-detail claim is made. This diagnoses a harmful contribution of the existing position path; it does not justify globally disabling position correction or starting a long training run. Earlier causal corrections and consumed-confirmation status remain in force. All old scientific evidence and receipts are preserved.

### R119 research correction (2026-09-06)

The canonical causal review is `Experiments/R119_SequenceGeometryValidation/reports/R119_CAUSAL_AUDIT.md`, with reproducible diagnostics under that experiment's `analysis/causal_audit_20260905`. It supersedes the earlier coherent-sequence success explanation and the approximately 0.9-pixel confirmation position error. The actual checkpoint and locked ACM/SEM/LSC observations are retained; training/data/weights were not changed by the review. Further design should first restore the intended physical observation and fair-control contracts, then verify local boundary motion independently of width/detail. COMBO production roles are unchanged.

## 1. Current Formal Baseline / 目前正式 baseline

目前正式 baseline：**COMBO / `r38v2_8px_gate_p95`**
The formal production baseline is now **COMBO / `r38v2_8px_gate_p95`**.

升級生效日期 / Promotion effective date：**2026-04-08**

| 指標 | COMBO |
|------|-------|
| external `8px step std` | `0.154515` |
| external `0.8px step std` | `0.131560` |
| external `0.08px step std` | `0.099891` |
| `0.8px` lag-1 autocorr | `-0.5176` |
| edge steepness vs R30 | `+89.4%` |
| contrast std vs R30 | `-6.6%` |
| gradient magnitude vs R30 | `-19.7%` |
| residual std (`0.8px` inner) | `2.044` |

正式入口 / Formal entry points：

- checkpoint:
  `Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525/weights/best_tradeoff.pth.tar`
- promoted baseline report:
  `Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md`
- complete series context:
  `Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md`
- machine-readable truth:
  `ESTIMATOR_POLICY.json`

COMBO 之所以被升級，不是因為它在單一 GMF 指標上最極端，而是因為它在 `0.8px` 主戰場、`8px` 宏觀守門、視覺 steepness、以及 residual_std 四個面向同時最均衡。
COMBO was promoted not because it is the most extreme on any single metric, but because it best balances the `0.8px` battlefield, the `8px` guard, visual steepness, and residual quality.

### Former Baseline / 前任 baseline

前任正式 baseline：**Round30 / `r30_b1_dironly`**
Former formal baseline: **Round30 / `r30_b1_dironly`**.

| 指標 | R30 former baseline |
|------|---------------------|
| external `8px step std` | `0.205193` |
| external `0.8px step std` | `0.167862` |
| external `0.08px step std` | `0.157720` |
| `0.8px` lag-1 autocorr | `0.267027` |

## 2. Approved Alternates / 已核准特化候選

### R33 / r33_robust_p95 — GMF Extreme Alternate

一句話定位：**GMF 極致型特化候選；不是正式 baseline。**
One-line role: **GMF-extreme approved alternate; not the formal baseline.**

| 指標 | R33 |
|------|-----|
| external `8px step std` | `0.153343` |
| external `0.8px step std` | `0.119049` |
| external `0.08px step std` | `0.086274` |
| `0.8px` lag-1 autocorr | `-0.5549` |
| edge steepness vs R30 | `-22%` |

適用場景 / Recommended use：
- 以 GMF 幾何精度為唯一主目標
- 可以接受視覺邊界更柔

正式入口 / Formal entry points：
- report:
  `Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md`
- checkpoint:
  `Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260405_091941/weights/best_tradeoff.pth.tar`

### R38v2 / r38v2_8px_gate — Visual Priority Alternate

一句話定位：**視覺優先型特化候選；不是正式 baseline。**
One-line role: **visual-priority approved alternate; not the formal baseline.**

| 指標 | R38v2 |
|------|-------|
| external `8px step std` | `0.143988` |
| external `0.8px step std` | `0.134205` |
| external `0.08px step std` | `0.106457` |
| `0.8px` lag-1 autocorr | `-0.5459` |
| edge steepness vs R30 | `+89.4%` |

適用場景 / Recommended use：
- 需要外部 GMF 改善，同時維持接近 R30 的視覺銳度
- 視覺品質比極致 GMF 更重要

正式入口 / Formal entry points：
- report:
  `Experiments/R38v2SeqFixed/reports/R38v2_RESULTS.md`
- checkpoint:
  `Traing_Progress/training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260406_235957/weights/best_tradeoff.pth.tar`

### R39R40_avg_a025 / r39r40_complementary_avg_a025 — Balanced Full-Spectrum Alternate

一句話定位：**全方位平衡替代候選；外部 GMF 三尺度都在 3% 內，顯微/形狀能力全勝 COMBO 與 a030；不是正式 baseline。**

升級生效日期 / Promotion effective date：**2026-05-11**

| 指標 | R39R40_avg_a025 |
|------|-----------------|
| external `8px step std` | `0.146505` |
| external `0.8px step std` | `0.133546` |
| external `0.08px step std` | `0.100400` |
| external 8px Δ vs COMBO | `−5.18%` |
| external 0.8px Δ vs COMBO | `+1.51%` |
| external 0.08px Δ vs COMBO | `+0.51%` |
| external verdict | **`PASS_UPGRADE_GUARD`**（三尺度都過 3% 升級上限）|
| R40 micro 整體 PSNR | `25.4091`（+2.68 dB vs COMBO，5 類全勝）|
| R39 shape 整體 PSNR | `25.5098`（+2.67 dB vs COMBO，7 類全勝）|
| edge steepness vs R30（推算） | `+78.1%`（sharp band）|

導生方式 / Derivation：

R39 a030（COMBO ↔ R39_strong α=0.30 權重平均）與 R40 a043（COMBO ↔ R40 micro_capacity_combo α=0.43 權重平均）兩個 checkpoint，在 α=0.25 做跨輪線性插值（75% a030 + 25% a043）。

適用場景 / Recommended use：
- 需要外部 GMF 三尺度都接近 COMBO，又要比 COMBO 更強的形狀泛化與顯微特徵能力的部署
- 不需要單一尺度極致優化（用 R33）也不需要極致視覺銳度（用 R38v2）時的預設替代
- 為「balanced full-spectrum」這個之前空缺的特化位置

升級依據 / Promotion basis（四項驗證 2026-05-11 通過）：
1. 外部 GMF 三尺度都過 3% 升級上限（首個專案候選做到）
2. R40 micro_val_unseen 5 類顯微結構 PSNR 全勝 COMBO 與 a030（+0.20 到 +0.47 dB vs a030）
3. R39 shape_val_unseen 7 類純幾何形狀 PSNR 全勝 COMBO 與 a030（+0.37 到 +0.61 dB vs a030）
4. 視覺 edge_steepness vs R30 約 +78.1%，與 a030（+78.8%）跟 a043（+79.2%）幾乎一致，落在 COMBO/R38v2 同一個 sharp band，遠優於 R33 soft band（−22%）

正式入口 / Formal entry points：
- promotion report:
  `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md`
- sweep results:
  `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md`
- external GMF compare:
  `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md`
- checkpoint:
  `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar`
- 視覺對比 sheet（R40 micro 5 聯 / R39 shape 5 聯）:
  `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_micro_five_panel.png`
  `Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_shape_five_panel.png`

## 3. Current Promoted State / 目前正式狀態

目前 mainline 狀態是 / The current mainline state is：

- **formal production baseline 已升級為 COMBO**
- `R33`、`R38v2` 與 `R39R40_avg_a025`（2026-05-11 升）為 approved alternates；前兩者是特化位置（GMF 極致 / 視覺優先），a025 是 balanced full-spectrum 位置
- **目前沒有開放中的 baseline challenger**
- `R39_ShapeGeneralization` 的 `r39_combo_strong_avg_a030` 仍為 alternate-grade pending（用作 a025 sweep 端點，本身未獨立升級）
- `R40_MicroscopyFeatureCoverage` 已完成訓練、本地評估、外部 GMF：顯微特徵重建變好，但 8px 外部守門退步；不升級
- `R41_RingDistillation` 已完成設施、訓練、本地評估與權重混合掃描：顯微特徵能力成立，但沒有任何混合點同時守住 microscopy 與 local ring guard；不送外部 GMF
- `R42_MicroscopyBoundaryFidelity` 已完成正式訓練、本地分析、低比例權重平均、守門 KD 診斷與外部 GMF 補測：通用顯微邊界能力明顯提升，但外部補測確認退步過大；不升級，也不建議作量測替代
- `R43_CandidateUsabilityAudit` 已完成 analysis-only 盤點：沒有新候選可全面取代 COMBO；`R39 a030` 最接近正式替代討論，`R42` full endpoints 可作顯微邊界研究/人工檢查候選
- `R44_UniversalBoundaryMotionFidelity` 已完成 R44A 診斷、R44B 三候選訓練、R44C 三個短探針、R44D 分族診斷、R44E 專項探針、R44F 錯誤解剖、R44G 邊界形狀體檢、R44H Step A 家族平均探測與 Step B 局部老師蒸餾：通用位移忠實度有進展，但仍未找到可直接堪用或可升級的平衡模型；研究成功但不可升級
- `R45_FamilyBoundaryAdapter` 已完成 R45A 單一入口小模組驗證與 R45B 老師殘差診斷：輸出端小校正可守住位移但沒有改善大區塊/混合場景；能力分散有 oracle 上限，但老師優勢不乾淨，不能直接拿來輸出端蒸餾
- `LabSystem_MOSR / R51_BlurSourceProbe` 是論文 Lab-system blur-source 小訓練探針：Gaussian、weak-BADS alpha `0.50`、mixed-PSF 三組短訓練與 real `20250605_checkboard` 重建/角點驗證皆完成。最佳 R51 是 mixed-PSF `best_tradeoff`，median corner shift `2.828 px`，優於 Lab R40 control `4.243 px`，但 large-shift corner rate `36.872%` 仍差於 R40 的 `24.581%`；方向有幫助但不可升級，下一步需加入真實角點穩定守門
- `LabSystem_MOSR / R52_CornerStabilityGuard` 是論文 Lab-system formal long run：R52 以 R51 mixed-PSF `best_tradeoff` 為起點，加入 4000-pair corner-stability training data 與 geometry sidecars，完成 100 epochs、真實 `20250605_checkboard` 重建與角點驗證。最佳 R52 是 epoch-100 `latest`，median corner shift `3.606 px` 優於 Lab R40 control `4.243 px`，但 large-shift corner rate `30.447%` 仍差於 R40 的 `24.581%`；R52 failed real-corner gate，不升級，不當 Lab baseline
- `LabSystem_MOSR / R53_RealisticDatasetCalibration` 是論文 Lab-system realistic-data formal round：R53 以 6000-pair main-project-like Lab training mix 從頭訓練 100 epochs，內部驗證到 epoch 100 仍改善（`PSNR 26.39` / `SSIM 0.9353`），但真實 `20250605_checkboard` 重建與角點驗證失敗。R53 `best_tradeoff` median corner shift `3.606 px`，但 large-shift corner rate `40.782%` 差於 Lab R40 的 `24.581%`；R53 `latest` 更退到 median `9.220 px` / `58.939%` large-shift corners。R53 不升級，不當 Lab baseline
- `LabSystem_MOSR / R54_GeometryRootCauseProbe` 是論文 Lab-system root-cause diagnostic + masked small-overfit probe：R54 先確認重建本身正在傷害真實角點（raw input >5 px 角點 `1.676%`，Lab R40 `24.581%`，R53 latest `58.939%`），再用 20260613 strict-rectangle CAD GT 做 edge-band masked small-overfit。小探針能成功貼近 CAD 監督（inside MAE input `61.145` -> R54 epoch20 `9.268`），但套到真實 `20250605_checkboard` 失敗：R54 epoch20 median corner shift `9.220 px`、>5 px `60.056%`，比 Lab R40 `4.243 px` / `24.581%` 更差。R54 證明問題不是「模型完全學不動 CAD 邊」，而是小範圍 CAD 適應會造成真實影像輸出漂移；不可作 Lab baseline
- `LabSystem_MOSR / R56_LabelCoreRepairTraining` 是論文 Lab-system label-core repair follow-up：R56 使用 R53/R55 source-style 6000-pair package 的 label-core 修復版本，完成 50 epoch scratch training，內部驗證到 epoch 50 仍改善（`PSNR 26.40` / `SSIM 0.9333`），但真實 `20250605_checkboard` 角點驗證失敗。R56 `best_tradeoff` median corner shift `2.828 px` 與 R55 best 相同，但 tail shift `9.899 px` 與 >5 px corners `26.816%` 都比 R55 best 的 `3.606 px` / `21.788%` 更差；R56 `latest` 更退到 median `9.899 px` / `59.777%` >5 px corners。R56 不採用，不送外部 GMF；R55 best 仍是目前較好的 Lab 候選
- `LabSystem_MOSR / R50_PSFControlDiagnosis` 是論文 Lab-system PSF/degradation 診斷：real Lab checkboard edge-width proxy 是 `7.0 px`，formal BADS 是 `11.0 px`，Gaussian 是 `9.0 px`，weak-BADS alpha `0.50` 是 `7.0 px`；結論是 BADS PSF 可用但不適合作為唯一 checkboard-corner blur truth，並已導向 R51 Gaussian / weak-BADS / mixed-PSF 小訓練探針
- `LabSystem_MOSR / R49_CADAnchorRealGeometry` 是論文 Lab-system replication side track：R49 CAD-anchor data/geometry packages, formal 100-epoch training, real Lab checkboard reconstruction, and real-corner validation are complete; validation failed (best R49 median corner shift `9.000 px` vs Lab R40 control `4.243 px`), so it remains negative method-transfer evidence and not a main-project baseline challenger. Full history is hash-verified on H; D keeps canonical context and restore instructions
- `LabSystem_MOSR / R48_RealCornerTransfer` 是論文 Lab-system replication side track：R48 data/geometry packages, formal 200-epoch training, real Lab checkboard reconstruction, and real-corner validation are complete; validation failed, so it remains negative method-transfer evidence and not a main-project baseline challenger
- `Round31` 已關閉，`Round32` 已關閉
- `R26NewPSFCheck` 仍保留為 **open side track**，但不是 active mainline

### R39 Shape Generalization

一句話 verdict：**訓練端點不升級；`r39_combo_strong_avg_a030`（COMBO ↔ R39_strong 權重平均，alpha=0.30）external GMF 通過 PASS_TRADEOFF（兩個尺度改善、0.8px 退 6.42% 在 R38v2 alternate 退步幅度內），達 alternate-grade，等專案決策是否正式升級為 approved alternate。**
One-line verdict: **trained endpoints not promotable; `r39_combo_strong_avg_a030` (COMBO ↔ R39_strong weight average at alpha=0.30) cleared external GMF as PASS_TRADEOFF (two scales improved, 0.8px regressed within the R38v2 alternate band). Alternate-grade; awaiting project-owner promotion decision.**

核心數字 / Core numbers（local + external GMF / Local + external GMF）：

| candidate | held-out shape PSNR | local 8px | local 0.8px | local 0.08px | external 8px | external 0.8px | external 0.08px |
|------|---:|---:|---:|---:|---:|---:|---:|
| COMBO | `22.8411` | `0.1389` | `0.1509` | `0.1185` | `0.154515` | `0.131560` | `0.099891` |
| `r39_shape_mix_safe` | `26.6799` | `0.3693` | `0.1811` | `0.1338` | — | — | — |
| `r39_shape_mix_strong` | `30.0722` | `0.2004` | `0.1691` | `0.1750` | — | — | — |
| **`r39_combo_strong_avg_a030`** | **`25.0326`** | **`0.1384`** | **`0.1507`** | **`0.1114`** | **`0.143794`** | **`0.140008`** | **`0.083941`** |

External GMF verdict（a030 vs COMBO，方法論：raw step_std，0 outliers removed）：

| scale | a030 | COMBO | delta % | 狀態 |
|---|---:|---:|---:|:---:|
| 8px | `0.143794` | `0.154515` | **−6.94%** | IMPROVED |
| 0.8px | `0.140008` | `0.131560` | +6.42% | TRADEOFF_OK（< 7% alternate cap） |
| 0.08px | `0.083941` | `0.099891` | **−15.97%** | IMPROVED（**專案歷史最低**） |

跨 alternate ranking：
- 8px:`a030 (0.1438)` ≈ `R38v2 (0.1440)` < R33 < COMBO（a030 與 R38v2 統計上並列頭部）
- 0.8px:R33 < COMBO < R38v2 < `a030`（a030 是最差,但仍優於 former baseline R30 0.168）
- 0.08px:`a030 (0.0839)` < R33 (0.0863) < COMBO < R38v2(**a030 為專案歷史最低**)

Visual profile（a030 vs COMBO,frame-wise mean over 203 ring BMP）：
- gradient_magnitude_mean −2.97%
- **edge_steepness_p95 −5.64%**(主指標)
- contrast_std −2.00%
- edge_contrast_p99_minus_p1 −2.64%

a030 屬 sharp band（接近 COMBO / R38v2,推算對 R30 約 +78.8% edge_steepness）,**不在 R33 的 soft band（R33 對 R30 −22% edge_steepness）**。視覺沒有崩壞,只輕微妥協。

正式入口 / Formal entry points：

- experiment results:
  `Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md`
- external GMF compare:
  `Experiments/R39_ShapeGeneralization/reports/R39_EXTERNAL_COMPARE.md`
- weight sweep summary + plot:
  `Experiments/R39_ShapeGeneralization/results/weight_sweep/sweep_summary.md`
  `Experiments/R39_ShapeGeneralization/results/weight_sweep/sweep_tradeoff.png`
- representative visual sheet:
  `Experiments/R39_ShapeGeneralization/results/shape_recon/r39_representative_shape_sheet.png`
- averaged checkpoint:
  `Experiments/R39_ShapeGeneralization/results/weight_sweep/checkpoints/a030/best_tradeoff.pth.tar`
- external GMF score files:
  `Experiments/R39_ShapeGeneralization/results/external_gmf_a030/pitch{8px,0p8px,0p08px}\GMF_score.txt`

a030 在 ESTIMATOR_POLICY.json 的位置：`open_side_tracks[].candidate_id = "R39_a030"`，狀態 `external_gmf_complete_alternate_grade_pending_promotion`。
未升級進 `approved_alternates` 之前，COMBO 仍是唯一正式 baseline，R33 / R38v2 仍是現有 approved alternates；a030 是 alternate-grade 但等專案決策。

R39 收尾 finding：a030 在訓練分布內(ring + 簡單幾何形狀)是 alternate-grade，但合成的「IC + grid + 紋理」這類訓練分布外顯微內容,a030 跟 COMBO 都重建不好(grid 完全消失、紋理被當雜訊濾掉)。雜訊調輕後重建幾乎沒變,證實限制是訓練分布而非雜訊或 PSF。詳見 `Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md` 的 "Synthetic Microscopy Demo" 段落。R40 已沿著這個 finding 擴大顯微特徵訓練覆蓋，證明能力可被推高，但外部 8px 守門未守住。

### R43 Candidate Usability Audit

一句話 verdict：**R43A 是 analysis-only 堪用性盤點，不是訓練輪次；結論是沒有近期候選可全面取代 COMBO，但 R39 a030 是最值得進入正式替代討論的候選，R42 full endpoints 是最值得保留的顯微邊界研究/人工檢查候選。**

核心產物：

- 報告：`Experiments/R43_CandidateUsabilityAudit/reports/R43A_USABILITY_AUDIT.md`
- 分數表：`Experiments/R43_CandidateUsabilityAudit/results/candidate_usability/usability_scorecard.json`
- CSV：`Experiments/R43_CandidateUsabilityAudit/results/candidate_usability/usability_scorecard.csv`
- 肉眼檢查圖：
  - `Experiments/R43_CandidateUsabilityAudit/results/visual_review/micro_feature_visual_sheet.png`
  - `Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_feature_visual_sheet.png`
  - `Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_zoom_visual_sheet.png`

重點結論：
- `R39 a030`：外部 GMF PASS_TRADEOFF，形狀泛化明顯改善，是近期最接近「堪用替代候選」的結果。
- `R42` full endpoints：顯微邊界、格線、缺陷重建能力強，但本地環形守門與後補外部 GMF 都失敗，不適合正式量測替代。
- R40/R41：證明顯微細節能力可被學到，但更適合作為能力來源，不適合部署。
- R42 low-alpha：守住舊能力時，新能力幾乎沒有帶回來，暫時不值得使用。

### R45 Family Boundary Adapter

一句話 verdict：**R45A 輸出端小校正沒有比 R44B from R42 更好；R45B 確認能力分散存在，但老師優勢不乾淨，不能直接拿來輸出端蒸餾。**

R45 的目標不是啟動多個完整模型，而是測試「單一入口 + 內部小校正模組」是否能把 R44 後分散的能力收回來。

本輪設計：

- 主模型：R44B from R42，保持凍結。
- 小模組：只在 `large_regions` 與 `mixed_fields` 啟動。
- 訓練資料：R44 motion train 的 stage 45/47，共 960 對。
- 驗證資料：R44 motion_val_unseen 七類全部，共 980 張、840 對位移比較。

R44B from R42 基準：

| 指標 | R44B from R42 |
|---|---:|
| 大區塊/混合合併形狀錯誤 | `0.338390` |
| 整體位移誤差 | `0.381330 px` |

R45 縮放掃描：

| 版本 | 校正強度 | 目標形狀錯誤 | 相對 R44B 形狀變化 | 整體位移誤差 | 判定 |
|---|---:|---:|---:|---:|---|
| `r45_oracle_adapter_large_mixed_s04` | 0.04 | `0.341758` | `-0.995%` | `0.381437` | FAIL |
| `r45_oracle_adapter_large_mixed_s08` | 0.08 | `0.340286` | `-0.560%` | `0.381685` | FAIL |
| `r45_oracle_adapter_large_mixed_s12` | 0.12 | `0.344523` | `-1.813%` | `0.381704` | FAIL |
| `r45_oracle_adapter_large_mixed` | 0.18 | `0.349675` | `-3.335%` | `0.382155` | FAIL |

關鍵解讀：

- 小模組沒有破壞非目標類型，位移也幾乎守住。
- 但目標形狀沒有變好；最佳 s08 只讓大區塊微幅改善，卻讓混合場景變差，合併後仍輸給 R44B。
- 因此問題不是「多模型入口」本身，而是輸出端小校正太晚、太弱，修不到模型內部形成邊界的能力。

正式入口 / Canonical files：

- 實驗根目錄：`Experiments/R45_FamilyBoundaryAdapter`
- 主結果報告：`Experiments/R45_FamilyBoundaryAdapter/reports/R45_RESULTS.md`
- 縮放掃描總表：`Experiments/R45_FamilyBoundaryAdapter/results/diagnostics/r45_adapter_scale_sweep_summary.csv`
- 代表圖：`Experiments/R45_FamilyBoundaryAdapter/results/visual_samples/r45_s08_vs_r44b_target_compare.png`

下一步判斷：

- 不建議繼續調輸出端小校正。
- 不建議用全圖蒸餾或直接老師輸出當答案。
- 若仍要維持單一入口，下一步應改成中間特徵層小分支，並且加入局部選擇器，只在老師確實優於 R44B 的區域啟動。

R45B 診斷結果：

| 診斷 | 形狀錯誤 | 相對 R44B 改善 |
|---|---:|---:|
| R44B from R42 | `0.3384` | `0.00%` |
| 固定分族 oracle | `0.2968` | `12.30%` |
| 逐張 oracle | `0.2253` | `33.42%` |

固定分族 oracle：

| 結構類型 | 最佳固定模型 | 平均形狀錯誤 |
|---|---|---:|
| large_regions | R44B from COMBO | `0.3755` |
| mixed_fields | R44C static heavy | `0.2181` |

老師可轉移性判斷：

- `R44B from R40` 與 `R41 direct` 形狀分數好，但位移退步過大，且邊界像素殘差方向不穩。
- `R44B from COMBO` 與 `R44C static heavy` 有局部參考價值，但不適合直接全圖或輸出端蒸餾。
- `R44H StepB region KD` 的殘差方向最接近穩定，但形狀能力不足。

R45B 正式入口：

- 診斷報告：`Experiments/R45_FamilyBoundaryAdapter/reports/R45B_TEACHER_DIAGNOSTICS.md`
- oracle 總結：`Experiments/R45_FamilyBoundaryAdapter/results/r45b_teacher_diagnostics/r45b_oracle_summary.json`
- 老師殘差表：`Experiments/R45_FamilyBoundaryAdapter/results/r45b_teacher_diagnostics/r45b_residual_summary.csv`
- 代表圖：`Experiments/R45_FamilyBoundaryAdapter/results/visual_samples/r45b_teacher_diagnostics_sheet.png`

### R44 Universal Boundary Motion Fidelity

一句話 verdict：**R44A-R44H Step B 已完成；R44B from R42 仍是最佳通用位移候選。R44H Step A 的全域平均會犧牲位移，Step B 的局部老師蒸餾雖守住位移但沒有救回形狀，因此不建議進 Step C 多老師全模型蒸餾。**

核心設計：

| 項目 | 內容 |
|------|------|
| R44A | 已完成診斷：COMBO、R39 a030、R40 a045、R41、R42 主要候選在已知位移顯微結構上的漂移程度 |
| R44B | 已完成訓練：三個候選各 24 epoch，分別從 R42、R40 a045、COMBO 出發 |
| R44C | 已完成短探針：三個候選各 21 epoch，檢查降低 motion、排除部分結構、加強靜態邊界是否能取得平衡 |
| R44D | 已完成診斷：不訓練，只按結構類型、位移段與模型來源拆解既有結果 |
| R44E | 已完成短探針：三個候選各 14 epoch，只針對大區塊與混合場景做修補 |
| R44F | 已完成診斷：不訓練，檢查大區塊/混合場景錯誤是否來自指標誤判或真邊界形狀問題 |
| R44G | 已完成診斷：不訓練，量化邊界厚度、破碎、直邊與角點保留 |
| R44H Step A | 已完成診斷：不訓練，檢查 R44C 老師乾淨度，並測試 R44B 家族權重平均是否能匯聚能力 |
| R44H Step B | 已完成短訓練：從 R44B from R42 出發，只在大區塊邊界帶向 R44B from COMBO 做局部老師蒸餾 |
| 位移資料 | `0 / 0.08 / 0.16 / 0.4 / 0.8 / 2 / 8 px` 的細線、格線、交叉線、曲線、大區塊、缺陷、混合場景序列 |
| 主候選 | `r44_motion_from_r42_best`、`r44_motion_from_r40_a045`、`r44_motion_from_combo`；R44C/R44E 是內部短探針，不是升級候選 |

主要結果：
- `R44B from R42` 是目前最佳通用位移候選：整體位移誤差 `0.3813 px`，優於 R42 `0.4609 px` 與 COMBO `0.8253 px`
- 格線位移誤差 `2.2457 px`，優於 R42 `2.7911 px` 與 COMBO `5.3567 px`
- 整體邊界距離沒有同步變好：R44B from R42 `3.7276 px`，略差於 R42 `3.6726 px`
- 本地三尺度環形代理退步：8px +45.1%、0.8px +46.7%、0.08px +32.3% vs COMBO
- R44C 最佳探針 `r44c_static_heavy_all_motion`：整體位移 `0.4011 px`、整體邊界 `3.7198 px`、格線位移 `2.3820 px`；比 R44B 稍微平衡，但位移優勢被拉回，大區塊仍未改善
- R44C 本地環形代理仍退步：8px +36.6%、0.8px +47.2%、0.08px +33.8% vs COMBO
- R44D 分族診斷：最佳單一邊界模型仍是 R42 best（平均 `3.6726 px`），分族上限為 `3.2038 px`，仍有 `12.77%` 空間
- R44D 確認大區塊最佳邊界來源是 R41 direct，混合場景最佳邊界來源是 R44B from R40；單一模型目前很難同時吃下所有結構
- R44D 也確認現有 `grid_phase_motion_error_px` 對所有模型幾乎相同，不能拿來排名模型
- R44E 最接近可用的 `r44e_region_mix_repair_from_r44b_r42` 幾乎保住 R44B 位移（`0.3820 px`），但大區塊退到 `7.7581 px`；另外兩個探針會讓格線與整體位移大幅退步
- R44F 壓力測試：大區塊 1px/5px 人工偏移為 `0.5335 / 2.5477`，混合場景為 `0.5673 / 2.6217`，代表指標能抓到偏移；但邊界變厚也會明顯變差
- R44G 形狀體檢：大區塊與混合場景合併最低形狀錯誤是 `R44B from R40`（`0.3110`），`R41 direct` 幾乎並列（`0.3119`）；大區塊單項最好是 `R44B from COMBO`（`0.3755`），混合場景單項最好是 `R44C static heavy`（`0.2181`）
- R44H Step 0：`R44C static heavy` 可暫作混合場景局部老師，混合場景形狀錯誤 `0.2181` 優於 R44B from R42 的 `0.2230`，相關位移最大退步 `6.07%`
- R44H Step A：四個 R44B 家族平均候選都能改善大區塊/混合形狀，最佳 `r44h_b42_bcombo_a050` 形狀錯誤 `0.2955`；但整體位移退到 `0.5298 px`，其他平均候選也退到 `0.4843-0.6277 px`
- R44H Step B：`r44h_stepb_region_kd_main` 整體位移 `0.3837 px`，幾乎守住 R44B from R42 的 `0.3813 px`；但大區塊/混合形狀錯誤從 `0.3384` 變差到 `0.3481`
- 結論：R44 證明 motion 資料能推動位移忠實度，也證明單純調權重、排除分族、大區塊/混合場景短訓練修補、把問題歸咎於指標誤判、R44B 家族全域平均、或單一老師局部蒸餾都不足；現成候選能力分散，下一步應轉向 adapter / 分族小頭 / 推論時分族選擇

正式入口：
- 實驗根目錄：`Experiments/R44_UniversalBoundaryMotionFidelity`
- 主結果報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44_RESULTS.md`
- 資料產生器：`Experiments/R44_UniversalBoundaryMotionFidelity/scripts/r44_motion_data.py`
- 訓練啟動器：`Experiments/R44_UniversalBoundaryMotionFidelity/scripts/launch_r44.py`
- 代表圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44_motion_r42_vs_r44_contact_sheet.png`
- R44C 代表圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44c_probe_r42_r44b_r44c_sheet.png`
- 總表：`Experiments/R44_UniversalBoundaryMotionFidelity/results/summary/r44_motion_summary_all.csv`
- R44C 探針總表：`Experiments/R44_UniversalBoundaryMotionFidelity/results/summary/r44c_probe_summary.csv`
- R44D 診斷報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44D_FAMILY_DIAGNOSTIC.md`
- R44D 邊界熱圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/diagnostics/r44d_boundary_heatmap.png`
- R44D 位移熱圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/diagnostics/r44d_motion_heatmap.png`
- R44E 專項報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44E_TARGETED_PROBE.md`
- R44E 探針總表：`Experiments/R44_UniversalBoundaryMotionFidelity/results/summary/r44e_probe_summary.csv`
- R44E 代表圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44e_region_mixed_probe_sheet.png`
- R44F 錯誤解剖報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44F_ERROR_DIAGNOSTIC.md`
- R44F 指標壓力測試：`Experiments/R44_UniversalBoundaryMotionFidelity/results/diagnostics/r44f_metric_stress.csv`
- R44F 代表圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44f_error_dissection_sheet.png`
- R44G 邊界形狀報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44G_BOUNDARY_SHAPE_METRICS.md`
- R44G 邊界形狀分數表：`Experiments/R44_UniversalBoundaryMotionFidelity/results/diagnostics/r44g_boundary_shape_scorecard.csv`
- R44G 邊界形狀熱圖：`Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44g_boundary_shape_heatmap.png`
- R44H Step A 報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44H_STEPA_FAMILY_AVERAGE.md`
- R44H Step A 總表：`Experiments/R44_UniversalBoundaryMotionFidelity/results/r44h_family_average/r44h_stepa_summary.csv`
- R44H Step B 報告：`Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44H_STEPB_REGION_KD.md`
- R44H Step B 位移摘要：`Experiments/R44_UniversalBoundaryMotionFidelity/results/r44h_stepb_region_kd/r44h_stepb_motion_summary.json`

### R40 Microscopy Feature Coverage

一句話 verdict：**R40 成功證明顯微特徵訓練資料能提高格線、紋理、缺陷等重建能力；但最佳折衷 `r40_combo_best_avg_a045` 外部 8px GMF 退步 +22.80%，所以只能列為研究結果，不升級。**
One-line verdict: **R40 proves the capacity gain from microscopy-feature coverage, but `r40_combo_best_avg_a045` regressed the 8px external GMF guard by +22.80%, so it is research-only and not promotable.**

核心數字 / Core numbers：

| candidate | held-out micro PSNR | held-out micro SSIM | high-frequency retention | local 8px | local 0.8px | local 0.08px | external 8px | external 0.8px | external 0.08px |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBO | `22.7326` | `0.8588` | `0.2234` | `0.1389` | `0.1509` | `0.1185` | `0.154515` | `0.131560` | `0.099891` |
| `r40_combo_best_avg_a045` | `26.8911` | `0.9199` | `0.3414` | `0.1510` | `0.1379` | `0.1199` | `0.189750` | `0.133314` | `0.097048` |

External GMF verdict（a045 vs COMBO，方法論：raw step_std，0 outliers removed）：

| scale | a045 | COMBO | delta % | 狀態 |
|---|---:|---:|---:|:---:|
| 8px | `0.189750` | `0.154515` | **+22.80%** | REGRESSED |
| 0.8px | `0.133314` | `0.131560` | +1.33% | TRADEOFF_OK |
| 0.08px | `0.097048` | `0.099891` | **-2.85%** | IMPROVED |

Step audit：8px `99` steps、0.8px `59` steps、0.08px `39` steps 全部納入；三個尺度 `z>5` 移除數都是 `0`。

正式入口 / Formal entry points：

- experiment results:
  `Experiments/R40_MicroscopyFeatureCoverage/reports/R40_RESULTS.md`
- external GMF compare:
  `Experiments/R40_MicroscopyFeatureCoverage/reports/R40_EXTERNAL_COMPARE.md`
- external step audit:
  `Experiments/R40_MicroscopyFeatureCoverage/results/external_gmf/step_audit/step_audit_summary.json`
- representative visual sheet:
  `Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/r40_a045_micro_comparison_sheet.png`
- averaged checkpoint:
  `Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/checkpoints/a045/best_tradeoff.pth.tar`

R40 在 ESTIMATOR_POLICY.json 的位置：`open_side_tracks[].candidate_id = "R40_a045"`，狀態 `external_gmf_complete_research_capacity_only_not_promotable`。COMBO 仍是唯一正式 baseline；R40 不進 approved alternates。

R40 收尾 finding：合成顯微特徵覆蓋有效，代表模型確實有能力學更清楚的格線、紋理、小缺陷；問題不是能力不存在，而是目前資料/訓練策略把顯微能力推高時仍會拉動既有環形能力。下一輪應保留 R40 顯微特徵資料，但用更溫和的保留策略守住 COMBO。

### R41 Ring Distillation

一句話 verdict：**R41 訓練與權重混合掃描已完成；顯微特徵能力確實保住，但沒有任何混合點同時通過 microscopy 與 local ring guard，所以 R41 是 research-only，不送外部 GMF。**
One-line verdict: **R41 training and weight sweep are complete; microscopy-feature capacity is preserved, but no averaged checkpoint passes both microscopy capacity and local ring guard, so R41 is research-only and no external GMF candidate is sent.**

核心數字 / Core numbers：

| candidate | held-out micro PSNR | held-out micro SSIM | high-frequency retention | local 8px | local 0.8px | local 0.08px | external 8px | external 0.8px | external 0.08px |
|------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| COMBO local reference | — | — | — | `0.1389` | `0.1509` | `0.1185` | `0.154515` | `0.131560` | `0.099891` |
| `r41_kd_from_a045` direct best | `29.4556` | `0.9513` | `0.7241` | `0.1628` | `0.1652` | `0.1543` | not sent | not sent | not sent |
| `r41_combo_avg_a045` diagnostic | `26.1840` | — | `0.3012` | `0.1577` | `0.1515` | `0.1322` | not sent | not sent | not sent |
| `r41_combo_avg_a050` diagnostic | `26.6662` | — | `0.3358` | `0.1534` | `0.1595` | `0.1475` | not sent | not sent | not sent |

R41 在 ESTIMATOR_POLICY.json 的位置：`open_side_tracks[].candidate_id = "R41_direct_best"`，狀態 `weight_sweep_complete_no_guarded_tradeoff`。COMBO 仍是正式 baseline；R41 不是 approved alternate。

R41 當前 finding：知識蒸餾加強了顯微能力保留，沒有把 R40 的顯微能力洗掉，甚至在 unseen micro validation 上高於 R40 a045。但這條路線沒有產生 ring/micro 共同通過點。低 alpha 守環形較好但顯微不夠；0.45/0.50 顯微過線但 0.8px / 0.08px 環形不過。下一輪若要繼續，應改機制，不要只沿 R41 的 teacher anchoring + weight averaging 加測。

Storage note (2026-08-01)：R41 封存前完整快照、正式訓練與專用資料共 6,075 個檔案，已透過三份 SHA-256 清單核對後保存到 `H:\GMM_2_Final_Archive\experiments\R41_RingDistillation\20260801_full_history`。D 槽的 `Experiments/R41_RingDistillation/ARCHIVE_POINTER.md` 保留完整恢復方式；此存放變更不改變上述研究 verdict。

### R42 Microscopy Boundary Fidelity

一句話判定：**R42 研究成功但不可升級：通用顯微邊界能力被明顯推起來，但本地三尺度環形守門與後續外部 GMF 補測都明顯退步；即使允許環形有限退步，也不建議作量測替代。**

核心結果：

| 模型 | 邊界 PSNR | 高頻保留 | 邊界距離 | 邊界 F1@1px |
|------|---:|---:|---:|---:|
| COMBO | `20.55` | `0.20` | `7.82` | `0.63` |
| R40 a045 | `23.35` | `0.51` | `6.77` | `0.72` |
| R41 直接端點 | `22.73` | `0.92` | `5.04` | `0.73` |
| `r42_combo_best` | `31.81` | `0.70` | **`3.35`** | **`0.87`** |
| `r42_combo_latest` | `34.09` | `0.75` | `3.48` | `0.87` |
| `r42_r41_best` | `32.89` | `0.75` | `3.48` | `0.87` |
| `r42_r41_latest` | **`34.18`** | **`0.80`** | `3.60` | `0.87` |

本地環形守門：

| 候選 | 8px | 0.8px | 0.08px | 判讀 |
|------|---:|---:|---:|---|
| COMBO 本地參考 | `0.1389` | `0.1509` | `0.1185` | 正式基準參考 |
| `r42_combo_best` | `9.5592` | `0.3621` | `0.6579` | 明顯崩壞 |
| `r42_combo_latest` | `0.1807` | `0.2158` | `0.2132` | 失敗 |
| `r42_r41_best` | `0.1715` | `0.2121` | `0.1673` | R42 中最好但仍失敗 |
| `r42_r41_latest` | `0.2442` | `0.2513` | `0.2154` | 失敗 |

外部 GMF 補測（2026-05-06）：

| 候選 | 8px 外部 | vs COMBO | 0.8px 外部 | vs COMBO | 0.08px 外部 | vs COMBO | 判讀 |
|------|---:|---:|---:|---:|---:|---:|------|
| `r42_r41_best` | `0.192577` | `+24.63%` | `0.255665` | `+94.33%` | `0.198651` | `+98.87%` | R42 中最好但仍退步過大 |
| `r42_combo_latest` | `0.286248` | `+85.26%` | `0.274479` | `+108.63%` | `0.251685` | `+151.96%` | 不建議使用 |
| `r42_r41_latest` | `0.279891` | `+81.14%` | `0.208713` | `+58.64%` | `0.225730` | `+125.98%` | 能力上限參考 |

深度補測：

| 補測 | 邊界 PSNR | 高頻保留 | 邊界 F1@1px | 環形 8px | 環形 0.8px | 環形 0.08px | 判讀 |
|------|---:|---:|---:|---:|---:|---:|---|
| 低 alpha 權重平均，邊界最佳 `a005` | `21.0094` | `0.2214` | `0.6518` | `0.1483` | `0.1555` | `0.1291` | 沒有共同通過；邊界改善太小且環形已退步 |
| 低 alpha 權重平均，守門較穩 `a003` | `20.8252` | `0.2127` | `0.6420` | `0.1399` | `0.1487` | `0.1232` | 環形較接近，但邊界仍接近 COMBO |
| `r42_guarded_kd_probe_latest` | `32.6607` | `0.7591` | `0.8705` | `0.2108` | `0.4257` | `0.1986` | 邊界仍強，但環形守門更差 |

已完成：
- 合成邊界資料 stages 34–40：細線、格線、交叉線、曲線、大區塊、缺陷、混合場景
- 每張 R42 圖的邊界遮罩、中心線遮罩、距離圖與 metadata
- 訓練資料包 `r42_boundary_research_train`：1660 pairs（環形 500 / 形狀 250 / 顯微特徵 350 / 邊界 560）
- 診斷資料包 `r42_guarded_kd_probe_train`：1530 pairs（環形 700 / 形狀 300 / 顯微特徵 250 / 邊界 280）
- 測試資料包 `boundary_val_unseen`：140 pairs（7 類邊界資料階段各 20）
- 訓練器可開關的邊界幾何損失
- `r42_boundary_from_combo` 1 epoch / 1 batch CPU 快速接線測試
- `r42_boundary_from_combo` 與 `r42_boundary_from_r41` 各 50 epoch 正式訓練
- COMBO / R39 / R40 / R41 / R42 共 8 組顯微邊界重建與分項評估
- R42 四個權重的本地三尺度環形守門
- COMBO ↔ `r42_r41_best` 低 alpha 權重平均補測（0.01 / 0.02 / 0.03 / 0.05）
- `r42_guarded_kd_probe` 1 epoch 快速接線測試、8 epoch 短訓練、顯微邊界驗證與本地三尺度環形守門
- `r42_r41_best`、`r42_combo_latest`、`r42_r41_latest` 外部 GMF 補測完成；三者皆不堪作量測替代

正式入口：
- 實驗主報告：`Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_RESULTS.md`
- 外部比較報告：`Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_EXTERNAL_COMPARE.md`
- 訓練啟動器：`Experiments/R42_MicroscopyBoundaryFidelity/scripts/launch_r42.py`
- 資料包根目錄：`Training_Data/r42_microscopy_boundary_fidelity`
- 代表圖：`Experiments/R42_MicroscopyBoundaryFidelity/results/boundary_recon/r42_representative_boundary_sheet.png`

R42 當前發現：資料與幾何目標可以推起通用顯微邊界忠實度；問題不在「模型完全學不會」，而在「推高通用邊界能力後，連續位移下的位置穩定性會退步」。低 alpha 權重平均證明能力不是小幅混合就能安全帶回；守門 KD 診斷證明單張影像老師牽引也不夠；外部 GMF 補測進一步確認這不是本地分析假象。下一輪應改做通用邊界位置一致性：對線條、格線、曲線、缺陷與大區塊建立已知位移 / phase / pitch 的序列約束，讓所有顯微結構的邊界位置穩定，不只是補環形。

### Closed Follow-up: Round31

一句話 verdict：**measured B1 hyperparam candidates external 全部退步；沒有形成升級。**
One-line verdict: **all measured Round31 B1 hyperparameter candidates regressed externally; no upgrade was produced.**

正式入口 / Formal entry points：

- decision:
  `Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_B1_HYPERPARAM_DECISION_20260318_113938.md`
- external compare:
  `Traing_Progress/organized_20260316/round31/selected/reports/ROUND31_EXTERNAL_COMPARE.md`

measured candidates / 已量測候選：

| candidate | external `0.8px step std` | vs former baseline `R30` |
|------|-----------|-----------|
| `r31_eq_prob_up` | `0.184867` | `+10.1%` |
| `r31_eq_weight_up` | `0.185458` | `+10.5%` |
| `r31_edge_ratio_low` | `0.179347` | `+6.8%` |

artifact caveat / artifact 注意事項：
- `r31_eq_combo` 缺 `GMF_score.txt`
- 判定：**artifact missing**，不是 measured regression

### Closed Sandbox: Round32

一句話 verdict：**`R32Sandbox` internal winner external FAIL；sandbox 已關閉。**
One-line verdict: **the `R32Sandbox` internal winner failed the final external gate; the sandbox is closed.**

正式入口 / Formal entry points：

- sandbox README:
  `Experiments/R32Sandbox/README.md`
- decision memo:
  `Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md`
- final external compare:
  `Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md`

核心數字 / Core numbers：

| scale | former baseline `R30` | `r32_real_eq_finetune` | delta |
|------|-----------|-----------|-----------|
| `8px` | `0.205193` | `0.319667` | `+0.114475` |
| `0.8px` | `0.167862` | `0.331821` | `+0.163960` |
| `0.08px` | `0.157720` | `0.230119` | `+0.072399` |

## 4. Open Side Track / 開放中的 side track

### R26NewPSFCheck

一句話定位：**PSF 驗證 side track；pending external GMF；不是 active mainline。**
One-line role: **PSF-validation side track; pending external GMF; not the active mainline.**

| 項目 | 狀態 |
|------|------|
| 新 Whole-FOV PSF 擬合 | ✓ 完成（2026-03-26） |
| 新 PSF 重訓模型 checkpoint | ✓ 已建立 |
| 外部三尺度重建（external recon） | ✓ 已完成 |
| PSF 正式流程審核 | ✓ 已完成 |
| pure_psf_control 對照實驗 | ✓ 已完成 |
| formal_newpsf_candidate promote | ✓ 已完成，verdict：PROMOTE |
| 外部 GMF 結果 | ⏳ 等待中 |

正式入口 / Formal entry points：

- sandbox README:
  `Experiments/R26NewPSFCheck/README.md`
- status:
  `Experiments/R26NewPSFCheck/reports/STATUS_20260326.md`
- PSF audit:
  `Experiments/R26NewPSFCheck/psf_audit/PSF_FORMAL_AUDIT_20260326.md`
- promote compare:
  `Experiments/R26NewPSFCheck/formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md`

## 5. Measurement Policy Status / 量測政策狀態

目前穩定結論 / Current stable conclusion：

- **external GMF remains the final gate**
- internal step_std **不再適合作為硬門檻**，尤其在 residual_std 進入低噪聲區後
- 720-angle unweighted circle fit 已驗證能降低 internal/external gap
- weighted fit 可用，但不是統一預設

正式入口 / Formal entry points：

- divergence analysis:
  `Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md`
- machine-readable policy:
  `ESTIMATOR_POLICY.json`

量化修復狀態 / Quantization policy：

- canonical inference now uses `np.rint`
- R33 修復後 `0.8px` 改善，R38v2 修復後 `8px` 改善但 `0.8px` 退步
- 這個差異被視為 **model-dependent quantization sensitivity**，不推翻 COMBO promotion

## 6. PSF Policy Status / PSF 政策狀態（2026-03-27）

R26 研究線的 PSF 已於 2026-03-27 正式完成政策切換。

| 身份 | PSF | 說明 |
|------|-----|------|
| **current standard** | 新 Whole-FOV PSF（2026-03-26 完成） | 物理上較合理；same-recipe 對照確認不引發崩壞；為目前研究採用的正式 PSF |
| **legacy empirical baseline** | 舊 PSF | 歷史上取得較好經驗數值；保留用於引用與對照，不刪除，不再作為正式預設 |

機器可讀 PSF 政策 / Machine-readable PSF policy：
`docs/policy/PSF_STANDARD_POLICY.json`

詳細說明 / Full details：
`docs/policy/PSF_POLICY_TRANSITION_R26.md`

## 7. Next Decision Boundary / 下一個決策邊界

下一個決策邊界已經不再是「三候選誰升級」，因為這件事已完成。
The next decision boundary is no longer "which of the three candidates gets promoted," because that decision is now closed.

接下來只在以下情況才值得立新 round：

1. 有明確新機制，不是 R33/R38v2/COMBO 的微幅重掃
2. 有 deployment-specific 需求，足以合理地偏向某個 alternate 或新線
3. 能同時說清楚 external GMF 目標、`8px` guard、與視覺取捨

不再合理的下一步 / What is no longer a sensible next step：

- 把 `R26NewPSFCheck` 寫成 active mainline
- 把 `R33` 或 `R38v2` 繼續寫成 pending promotion
- 把 720-angle 當成未完成 action item

目前真正的決策邊界是：
**若要再開新 round，必須是新的機制或新的 deployment 條件，而不是重複討論已完成的 baseline promotion。**
