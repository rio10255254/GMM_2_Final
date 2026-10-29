# 實驗重建影像 Gallery / Experiment Recon Gallery

_Last updated: 2026-09-08_

## R128 — 四組完整訓練的實拍結果（2026-09-09）

訓練與檢查全部完成。只留第四組作後續修正：一般亮度36/36物件改善，但暗圖29/36退步；所有版本的16個暗圖內部物件都退步。沒有正式採用。見 [完整結果](Experiments/R128_SourceOnlyFullTraining/reports/R128_RESULTS.md)。

![固定物件的SEM尺寸比對](Experiments/R128_SourceOnlyFullTraining/reports/figures/final_SEM_comparison.png)

![同一實拍位置的原圖與四份結果](Experiments/R128_SourceOnlyFullTraining/reports/figures/final_real_object_comparison.png)

## R127 — 對照與位移讀法修正（2026-09-08）

完整視野提供了小區塊缺少的配對線索；48份重算保留原來小區塊的每個像素，24組模型全圖位移與相同讀法下的Raw最大差0.000511像素。這是影像前後一致性，不是位移台絕對精度。SEM亮邊的定義範圍另行保留；核心模型尚未採用。見 [完整結果與限制](Experiments/R127_MeasurementPreservationRepair/reports/R127_RESULTS.md)。

![影像範圍與配對資訊](Experiments/R127_MeasurementPreservationRepair/reports/figures/motion_information_scope.png)

![原生SEM邊界定義](Experiments/R127_MeasurementPreservationRepair/reports/figures/native_SEM_edge_definitions.png)

## R126 — 學習改善，實拍量測仍未可靠（2026-09-08）

同一固定例子只調整學習幅度，誤差下降由約7–10%提高至38–61%；這不是實拍改善率。亮暗擴充對照顯示暗例子有幫助，但真實SEM的對照方式會影響結論，位移匹配也會跳值。四個模型均未採用。見 [完整驗證與限制](Experiments/R126_LearnabilityPhotometry/reports/R126_RESULTS.md)。

![固定例子的學習對照](Experiments/R126_LearnabilityPhotometry/reports/figures/fixed_learning.png)

![同一批實拍與SEM的完整對照](Experiments/R126_LearnabilityPhotometry/results/real_comparison/bounded_sem_comparison.png)

## R125 — 資料修正後的六組小試：不採用（2026-09-08）

已完成六組各64次更新及全部初始／最終實拍評估。A正常曝光稍好、暗曝光退步；B/C未顯示可靠改善。此圖是固定SEM參考的半對比讀值，未完成物理材料邊界資格判定。見 [R125 完整結果](Experiments/R125_DataAlignedPilot/reports/R125_RESULTS.md)。

![同一共同人口下的小試結果](Experiments/R125_DataAlignedPilot/results/real_comparison/bounded_sem_comparison.png)

## R124 — 未訓練原型的實際輸出與SEM讀值（2026-09-08）

模型已實作，以下是沒有訓練、沒有儀器校準的工程輸出，不能當作改善證據。六張實拍走過兩個設定；SEM參考半對比讀值在假設Gaussian設定下略增加。完整範圍見 [R124 原型驗證](Experiments/R124_RealFirstPrototype/reports/R124_RESULTS.md)。

![未訓練的實拍預覽](Experiments/R124_RealFirstPrototype/results/real_smoke_v1/untrained_real_previews.png)

![未訓練SEM參考讀值，並非效益通過](Experiments/R124_RealFirstPrototype/results/sem_smoke_v1/followup_v2/untrained_sem_half_readout.png)

## R123 — 下一代設計與真實開發面板（2026-09-08）

本輪只有設計與既有資料核對，沒有新模型重建圖。主要開發光學資料為12張SEM對應曝光、301張全視野序列、51張棋盤；既有模型的兩種讀法矛盾也重新核算。見 [R123 本輪完成範圍](Experiments/R123_RealFirstModelDesign/reports/R123_RESULTS.md)。

![實際原圖面板，非新模型输出](Experiments/R123_RealFirstModelDesign/results/real_input_panel.png)

![既有模型真實讀法矛盾重算](Experiments/R123_RealFirstModelDesign/results/real_baseline_replay.png)

## R122 — 成像歧義與量測原理診斷（2026-09-08）

本輪是診斷，沒有新模型。不同物體可能產生相同觀測；位移穩定也不保證絕對邊界正確。圖表與失敗条件見 [R122 原理驗證報告](Experiments/R122_OperatorPrinciples/reports/R122_RESULTS.md)。下列物理結果使用修正後的面積積分模擬器；第一版離散化失敗另行保留。

![不同物體的相同觀測](Experiments/R122_OperatorPrinciples/results/identifiability.png)

![修正後成像與位置／位移誤差](Experiments/R122_OperatorPrinciples/results/area_render_v2/physical_fit.png)

這份文件收集**每一輪實驗所有 tracked 的重建影像、指標圖表、分析圖**，供 demo / report 時快速查閱。
所有連結皆為 git 追蹤檔案的相對路徑，GitHub 上會自動渲染圖片。

## 🎨 色彩圖例 / Color Legend

| 色圓 | 狀態 | 含義 |
|------|------|------|
| 🟢 | active | 正式 baseline 或 approved alternate — 目前可安全引用 |
| 🟡 | open side track | 研究中的 side track，尚未完成外部驗證 |
| 🔵 | historical | 前任 baseline 或歷史基準線（保留作參考，已被取代）|
| 🔴 | closed / falsified | 已經否定或 external FAIL，不可再引用為 active line |

## 📑 快速導覽 / Table of Contents

| 色 | Round | 角色 | 關鍵數字（external 0.8px step std）|
|----|-------|------|-----------------------------------|
| 🟢 | [**COMBO**](#-combo) | formal production baseline (2026-04-08) | **`0.132`** · steepness +89% · residual 歷史最佳 |
| 🟢 | [**R38v2**](#-r38v2) | visual priority alternate | `0.134` · steepness +89% |
| 🟢 | [**R33**](#-r33) | GMF extreme alternate | **`0.119`** · 三尺度全面最低 |
| 🟢 | [**R39R40_avg_a025**](#-r39r40_avg_a025) | balanced full-spectrum alternate (2026-05-11) | `0.134` · 三尺度都在 ±5.18% · 12 分類 PSNR 全勝 COMBO/a030 |
| 🔴 | [R33 ablations](#-r33-ablations) | lap_only / soft_p95 / hard_p90 — closed | — |
| 🔵 | [**R30**](#-r30) | historical former baseline (pre-COMBO) | `0.168` · B1 dironly |
| 🔵 | [**R26 sm035**](#-r26-sm035) | 歷史 step_mag=0.35 基準線 | `0.191` |
| 🟡 | [**R26NewPSFCheck**](#-r26newpsfcheck) | open side track — PSF 政策切換 | pending external GMF |
| 🟡 | [**R39-R45 microscopy generalization**](#-r39-r45-microscopy-generalization) | 形狀、顯微特徵、邊界、位移與分族校正研究線 | R39 a030 可討論；R45 確認輸出端小校正不足以匯聚能力 |
| 🔴 | [R33c](#-r33c) | 對比度修復失敗 | 視覺 + 指標雙退步 |
| 🔴 | [R38 seq-all-stages](#-r38-seq-all-stages) | seq 全 stages 噪聲干擾 | 8px 好但 0.8px 弱 |
| 🔴 | [R32](#-r32) | domain rebalancing external FAIL | `0.332` (+97.7%) |
| 🔴 | [R34 / R35 / R37](#-r34--r35--r37) | sandbox-only 銳度修復 — 全部失敗 | — |
| 📚 | [Legacy visuals](#-legacy-visuals) | R18/R22/R25 0.8px 比較（封存） | — |

---


## 🟢 COMBO

![🟢 COMBO 跨尺度步距標準差](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/cross_dataset/08_cross_scale_step_std.png)

> [!TIP]
> **`r38v2_8px_gate_p95`** · formal baseline (2026-04-08) · 0.8px **`0.132`** · steepness **+89%** · residual 2.044（歷史最佳）


### 📊 測試重建影像（實際模型輸出 BMP）

三個尺度的重建樣本（每張圖取重建序列的中間一幀）：

**0.08 px 子像素**

![](Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp)

**0.8 px 主戰場**

![](Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp)

**8 px guard**

![](Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp)

📁 完整重建序列：

- [41 frames · 0.08 px 子像素](Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525/pitch0p01um_y_40_odd/)
- [61 frames · 0.8 px 主戰場](Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525/pitch0p1um_y_60_odd/)
- [101 frames · 8 px guard](Experiments/R38v2SeqFixed/results/combo_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260408_003525/pitch1um_y_100_odd/)


### 📈 所有 24 張 720-angle 指標圖 + 其他方法論版本

**跨尺度總結：**

- [跨尺度步距標準差（08）](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/cross_dataset/08_cross_scale_step_std.png)
- [跨尺度 Residual 改善（09）](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/cross_dataset/09_cross_scale_residual_improvement.png)
- [跨尺度 K2 穩定性（10）](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/cross_dataset/10_cross_scale_k2_stability.png)

**Per-pitch 詳細指標（每 pitch 7 張）：**

- **0.08 px 子像素（`pitch0p01um_y_40`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p01um_y_40/07_center_offset_drift.png)
- **0.8 px 主戰場（`pitch0p1um_y_60`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch0p1um_y_60/07_center_offset_drift.png)
- **8 px guard（`pitch1um_y_100`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/COMBO/pitch1um_y_100/07_center_offset_drift.png)

**量化修復（np.rint）後的 recon 與其他方法論版本：**

- [量化修復版 recon（`8px_gate_recon_quantfix/`）](Experiments/R38v2SeqFixed/results/8px_gate_recon_quantfix/)
- [720-angle IRLS 分析](Experiments/R38v2SeqFixed/results/720angle_irls_analysis/COMBO/)
- [720-angle Soft-L1 分析](Experiments/R38v2SeqFixed/results/720angle_soft_l1/COMBO/)
- [獨立 sequence_analysis](Experiments/R38v2SeqFixed/results/combo_sequence_analysis/)


📄 [COMBO_RESULTS](Experiments/R38v2SeqFixed/reports/COMBO_RESULTS.md) · [完整系列報告](Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md)

---

## 🟢 R38v2

![🟢 R38v2 跨尺度步距標準差](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/cross_dataset/08_cross_scale_step_std.png)

> [!TIP]
> **`r38v2_8px_gate`** · visual priority alternate · 0.8px **`0.134`** · steepness **+89%** · Seq training（8px-only + signal gate + warmup 15，未加 Winsorize）


### 📊 測試重建影像（實際模型輸出 BMP）

三個尺度的重建樣本（每張圖取重建序列的中間一幀）：

**0.08 px 子像素**

![](Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp)

**0.8 px 主戰場**

![](Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp)

**8 px guard**

![](Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp)

📁 完整重建序列：

- [41 frames · 0.08 px 子像素](Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957/pitch0p01um_y_40_odd/)
- [61 frames · 0.8 px 主戰場](Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957/pitch0p1um_y_60_odd/)
- [101 frames · 8 px guard](Experiments/R38v2SeqFixed/results/8px_gate_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_235957/pitch1um_y_100_odd/)


### 📈 所有 24 張 720-angle 指標圖 + 其他方法論版本

**跨尺度總結：**

- [跨尺度步距標準差（08）](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/cross_dataset/08_cross_scale_step_std.png)
- [跨尺度 Residual 改善（09）](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/cross_dataset/09_cross_scale_residual_improvement.png)
- [跨尺度 K2 穩定性（10）](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/cross_dataset/10_cross_scale_k2_stability.png)

**Per-pitch 詳細指標（每 pitch 7 張）：**

- **0.08 px 子像素（`pitch0p01um_y_40`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p01um_y_40/07_center_offset_drift.png)
- **0.8 px 主戰場（`pitch0p1um_y_60`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch0p1um_y_60/07_center_offset_drift.png)
- **8 px guard（`pitch1um_y_100`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R38v2/pitch1um_y_100/07_center_offset_drift.png)

**其他方法論版本：**

- [720-angle IRLS 分析](Experiments/R38v2SeqFixed/results/720angle_irls_analysis/R38v2/)
- [720-angle Soft-L1 分析](Experiments/R38v2SeqFixed/results/720angle_soft_l1/R38v2/)
- [通用 sequence_analysis](Experiments/R38v2SeqFixed/results/sequence_analysis/)
- [量化修復版 recon（`8px_gate_recon_quantfix/`）](Experiments/R38v2SeqFixed/results/8px_gate_recon_quantfix/)


📄 [R38v2_RESULTS](Experiments/R38v2SeqFixed/reports/R38v2_RESULTS.md)

---

## 🟢 R33

![🟢 R33 跨尺度步距標準差](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/cross_dataset/08_cross_scale_step_std.png)

> [!TIP]
> **`r33_robust_p95`** · GMF extreme alternate · 0.8px **`0.119`**（三尺度全面最低）· 視覺銳度 -22% · Winsorize spatial loss p95


### 📊 測試重建影像（實際模型輸出 BMP）

三個尺度的重建樣本（每張圖取重建序列的中間一幀）：

**0.08 px 子像素**

![](Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp)

**0.8 px 主戰場**

![](Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp)

**8 px guard**

![](Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp)

📁 完整重建序列：

- [41 frames · 0.08 px 子像素](Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941/pitch0p01um_y_40_odd/)
- [61 frames · 0.8 px 主戰場](Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941/pitch0p1um_y_60_odd/)
- [101 frames · 8 px guard](Experiments/R33RobustLoss/results/p95_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_091941/pitch1um_y_100_odd/)


### 📈 所有 24 張 720-angle 指標圖 + 其他方法論版本

**跨尺度總結：**

- [跨尺度步距標準差（08）](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/cross_dataset/08_cross_scale_step_std.png)
- [跨尺度 Residual 改善（09）](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/cross_dataset/09_cross_scale_residual_improvement.png)
- [跨尺度 K2 穩定性（10）](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/cross_dataset/10_cross_scale_k2_stability.png)

**Per-pitch 詳細指標（每 pitch 7 張）：**

- **0.08 px 子像素（`pitch0p01um_y_40`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p01um_y_40/07_center_offset_drift.png)
- **0.8 px 主戰場（`pitch0p1um_y_60`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch0p1um_y_60/07_center_offset_drift.png)
- **8 px guard（`pitch1um_y_100`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R33/pitch1um_y_100/07_center_offset_drift.png)

**R33 候選獨立 sequence_analysis 與量化修復：**

- [R33 候選獨立 sequence_analysis（24 張）](Experiments/R33RobustLoss/results/p95_sequence_analysis/)
- [量化修復版 recon（`p95_recon_quantfix/`）](Experiments/R33RobustLoss/results/p95_recon_quantfix/)


📄 [R33_EXPERIMENT_SUMMARY](Experiments/R33RobustLoss/reports/R33_EXPERIMENT_SUMMARY.md) · [完整系列報告](Experiments/R33RobustLoss/reports/R33_R38v2_COMPLETE_EXPERIMENT_SERIES.md) · [GMF 方法論](Experiments/R33RobustLoss/reports/GMF_STEP_STD_METHODOLOGY.md) · [量化修復分析](Experiments/R33RobustLoss/reports/QUANTIZATION_FIX_ANALYSIS.md) · [Internal/External 偏差分析](Experiments/R33RobustLoss/reports/INTERNAL_EXTERNAL_DIVERGENCE_ANALYSIS.md)

---

## 🟢 R39R40_avg_a025

![🟢 R39R40_avg_a025 R40 micro 五聯對比](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_micro_five_panel.png)

> [!TIP]
> **`r39r40_complementary_avg_a025`** · balanced full-spectrum alternate（2026-05-11 升級）· 外部 GMF 三尺度 Δ 都在 ±5.18% 內（8 px `−5.18%` / 0.8 px `+1.51%` / 0.08 px `+0.51%`，verdict `PASS_UPGRADE_GUARD`）· 12 顯微/形狀分類 PSNR 全勝 COMBO 與 a030 · 視覺在 sharp band（vs R30 推算 +78.1%）


### 📊 五聯視覺對比

R39 a030 與 R40 a043 在 α=0.25（75% a030 + 25% a043）的跨輪權重平均：

- [R40 micro_val_unseen 五聯](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_micro_five_panel.png) — GT / COMBO / a030 / R40 a043 / a025；5 顯微類 × 4 frame
- [R39 shape_val_unseen 五聯](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_shape_five_panel.png) — GT / COMBO / a030 / R40 a043 / a025；7 形狀類 × 3 frame
- [R40 micro_val_unseen 四聯](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/visuals/contact_sheet_a025_four_panel.png) — GT / COMBO / a030 / a025；cell 較大（320×320）


### 📊 測試重建影像（實際模型輸出 BMP）

外部三尺度 ring 重建：

- [`8 px`（Pitch1um_Y_100）101 frames](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260511_151845/pitch1um_y_100_odd/)
- [`0.8 px`（Pitch0.1um_Y_60）61 frames](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260511_151845/pitch0p1um_y_60_odd/)
- [`0.08 px`（Pitch0.01um_Y_40）41 frames](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/external_recon/a025/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260511_151845/pitch0p01um_y_40_odd/)

合成顯微特徵 5 類重建：

- [`stage_29_micro_lines_grid`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025/reconstruct_progress_best_tradeoff_in_stage_29_micro_lines_grid_20260511_151845/)
- [`stage_30_micro_large_regions`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025/reconstruct_progress_best_tradeoff_in_stage_30_micro_large_regions_20260511_151845/)
- [`stage_31_micro_textures`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025/reconstruct_progress_best_tradeoff_in_stage_31_micro_textures_20260511_151845/)
- [`stage_32_micro_edge_defects`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025/reconstruct_progress_best_tradeoff_in_stage_32_micro_edge_defects_20260511_151845/)
- [`stage_33_micro_mixed_fields`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025/reconstruct_progress_best_tradeoff_in_stage_33_micro_mixed_fields_20260511_151845/)

合成幾何形狀 7 類重建：

- [`stage_01_triangles`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_01_triangles_20260511_151845/)
- [`stage_02_circles`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_02_circles_20260511_151845/)
- [`stage_03_rectangles`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_03_rectangles_20260511_151845/)
- [`stage_04_ellipses`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_04_ellipses_20260511_151845/)
- [`stage_05_polygons`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_05_polygons_20260511_151845/)
- [`stage_06_mixed_simple`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_06_mixed_simple_20260511_151845/)
- [`stage_07_mixed_complex`](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025/reconstruct_progress_best_tradeoff_in_stage_07_mixed_complex_20260511_151845/)


### 📈 升級依據與評估報告

- [Capability eval（升級依據）](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md) — 四項驗證（外部 GMF + R40 顯微 + R39 形狀 + 視覺四項）
- [Sweep 5 點 trade-off 結果](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md) — α=0 / 0.25 / 0.5 / 0.75 / 1.0 跨輪 sweep
- [外部 GMF 解析（α=0.25）](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md)


### 📈 指標 CSV / JSON

- [Per-pair 指標](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/capability_eval/per_pair_metrics.csv)（4 候選 × 310 對逐張）
- [逐 stage 平均](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/capability_eval/stage_summary.csv)
- [整體平均](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/capability_eval/overall_summary.csv)
- [視覺四項統計](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/capability_eval/visual_stats.csv)
- [Capability summary JSON](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/capability_eval/capability_summary.json)


📄 [Capability eval](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_CAPABILITY_EVAL.md) · [Sweep 結果](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_COMPLEMENTARY_AVG_RESULTS.md) · [外部 GMF](Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/reports/R39R40_AVG_a025_EXTERNAL_COMPARE.md)

---

## 🔴 R33 ablations

> [!NOTE]
> R33 系列的三個否定分支，保留作為「為什麼 p95 才成立」的對照。

| 候選 | verdict | recon 目錄 | sequence analysis |
|------|---------|-----------|-------------------|
| `hard_p90`（internal only） | 未送外部 GMF | [`reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_073906/`](Experiments/R33RobustLoss/results/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_073906/) | [`sequence_analysis/`](Experiments/R33RobustLoss/results/sequence_analysis/) |
| `lap_only`（Laplacian 單獨） | W_GRADMAG 不能拿掉 | [`lap_only_recon/`](Experiments/R33RobustLoss/results/lap_only_recon/) | [`lap_only_sequence_analysis/`](Experiments/R33RobustLoss/results/lap_only_sequence_analysis/) |
| `soft_p95`（Charbonnier 軟 p95） | 比 hard 更差 | [`soft_p95_recon/`](Experiments/R33RobustLoss/results/soft_p95_recon/) | [`soft_p95_sequence_analysis/`](Experiments/R33RobustLoss/results/soft_p95_sequence_analysis/) |

每個 sequence_analysis 皆含 cross_dataset（3 張）+ 3 pitches × 7 張 = 24 張 PNG。

---

## 🔵 R30

![R30 跨尺度步距標準差](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/cross_dataset/08_cross_scale_step_std.png)

> [!NOTE]
> **`r30_b1_dironly`** · historical former baseline（pre-COMBO）· 0.8px **`0.168`** · B1 dironly 首次在主戰場超越 R26
>
> R30 的 recon BMP 在 legacy batch 內且未 tracked；本輪只有 720-angle 跨候選比較的指標圖。


### 📈 Per-pitch 指標縮圖（720-angle analysis）

三個尺度的步距穩定性圖（720-angle analysis）：

**0.08 px 子像素**

![](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/02_step_stability.png)

**0.8 px 主戰場**

![](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/02_step_stability.png)

**8 px guard**

![](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/02_step_stability.png)


### 📈 所有 24 張 720-angle 指標圖 + 其他方法論版本

**跨尺度總結：**

- [跨尺度步距標準差（08）](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/cross_dataset/08_cross_scale_step_std.png)
- [跨尺度 Residual 改善（09）](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/cross_dataset/09_cross_scale_residual_improvement.png)
- [跨尺度 K2 穩定性（10）](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/cross_dataset/10_cross_scale_k2_stability.png)

**Per-pitch 詳細指標（每 pitch 7 張）：**

- **0.08 px 子像素（`pitch0p01um_y_40`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p01um_y_40/07_center_offset_drift.png)
- **0.8 px 主戰場（`pitch0p1um_y_60`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch0p1um_y_60/07_center_offset_drift.png)
- **8 px guard（`pitch1um_y_100`）**
  - [中心軌跡](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/02_step_stability.png)
  - [Residual std 時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38v2SeqFixed/results/720angle_analysis/R30/pitch1um_y_100/07_center_offset_drift.png)

**其他方法論版本：**

- [720-angle IRLS 分析](Experiments/R38v2SeqFixed/results/720angle_irls_analysis/R30/)
- [720-angle Soft-L1 分析](Experiments/R38v2SeqFixed/results/720angle_soft_l1/R30/)


📄 [External compare](docs/evidence/baseline/ROUND30_EXTERNAL_COMPARE.md) · [Architecture breakthrough decision](docs/evidence/baseline/ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md)

---

## 🔵 R26 sm035

> [!NOTE]
> **`r26_sm035`** · 歷史 step_mag=0.35 基準線 (R14–R29 線的 externally verified optimum)
>
> 已被 R30 取代。AnalysisLab 保留完整 single_image + sequence 分析作為研究參考
>
> external 0.8px **`0.191`**

📄 Entry: [Analyses/AnalysisLab/r26/README](Analyses/AnalysisLab/r26/README.md)

### 📊 測試重建影像（single-image demo）

![R26 single-image output](Analyses/AnalysisLab/r26/single_image/recon/output_preview.png)

- Input：[`VisionTop_20251029182653732.bmp`](Analyses/AnalysisLab/r26/single_image/inputs/VisionTop_20251029182653732.bmp) · [preview](Analyses/AnalysisLab/r26/single_image/inputs/input_preview.png)
- Output (r26_sm035 best_tradeoff)：[`VisionTop_*.bmp`](Analyses/AnalysisLab/r26/single_image/recon/reconstruct_progress_r26_sm035_best_tradeoff_in_Demo_Input_20260327_122202/VisionTop_20251029182653732.bmp) · [preview](Analyses/AnalysisLab/r26/single_image/recon/output_preview.png)

### 📈 指標圖表（single_image analysis，8 張）

完整報告：[`Analyses/AnalysisLab/r26/single_image/reports/R26_SingleImage_Analysis_Report.md`](Analyses/AnalysisLab/r26/single_image/reports/R26_SingleImage_Analysis_Report.md)

- [01 edge profiles](Analyses/AnalysisLab/r26/single_image/results/01_edge_profiles.png)
- [02 circle fit](Analyses/AnalysisLab/r26/single_image/results/02_circle_fit.png)
- [03 angular consistency](Analyses/AnalysisLab/r26/single_image/results/03_angular_consistency.png)
- [04 frequency spectrum](Analyses/AnalysisLab/r26/single_image/results/04_frequency_spectrum.png)
- [05 overview and artifacts](Analyses/AnalysisLab/r26/single_image/results/05_overview_and_artifacts.png)
- [06 edge width angular](Analyses/AnalysisLab/r26/single_image/results/06_edge_width_angular.png)
- [07 residual harmonics](Analyses/AnalysisLab/r26/single_image/results/07_residual_harmonics.png)
- [08 residual hotspot](Analyses/AnalysisLab/r26/single_image/results/08_residual_hotspot.png)

### 📈 指標圖表（sequence analysis）

完整報告：[`Analyses/AnalysisLab/r26/sequence/reports/R26_Sequence_Analysis_Report.md`](Analyses/AnalysisLab/r26/sequence/reports/R26_Sequence_Analysis_Report.md)

- Cross-scale：[08 step std](Analyses/AnalysisLab/r26/sequence/results/cross_dataset/08_cross_scale_step_std.png) · [09 residual](Analyses/AnalysisLab/r26/sequence/results/cross_dataset/09_cross_scale_residual_improvement.png) · [10 k2](Analyses/AnalysisLab/r26/sequence/results/cross_dataset/10_cross_scale_k2_stability.png)

### Per-pitch（21 張）
- `pitch0p01um_y_40`: [01](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/01_center_trajectory.png) · [02](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/02_step_stability.png) · [03](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/03_residual_std_timeseries.png) · [04](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/04_k2_amplitude_timeseries.png) · [05](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/05_hotspot_persistence.png) · [06](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/06_edge_width_consistency.png) · [07](Analyses/AnalysisLab/r26/sequence/results/pitch0p01um_y_40/07_center_offset_drift.png)
- `pitch0p1um_y_60`: [01](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/01_center_trajectory.png) · [02](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/02_step_stability.png) · [03](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/03_residual_std_timeseries.png) · [04](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/04_k2_amplitude_timeseries.png) · [05](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/05_hotspot_persistence.png) · [06](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/06_edge_width_consistency.png) · [07](Analyses/AnalysisLab/r26/sequence/results/pitch0p1um_y_60/07_center_offset_drift.png)
- `pitch1um_y_100`: [01](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/01_center_trajectory.png) · [02](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/02_step_stability.png) · [03](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/03_residual_std_timeseries.png) · [04](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/04_k2_amplitude_timeseries.png) · [05](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/05_hotspot_persistence.png) · [06](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/06_edge_width_consistency.png) · [07](Analyses/AnalysisLab/r26/sequence/results/pitch1um_y_100/07_center_offset_drift.png)

### 🔍 分析圖（performance benchmark）

- [01 inference latency comparison](Analyses/AnalysisLab/r26/performance/results/cross_device/01_inference_latency_comparison.png)
- [02 inference throughput comparison](Analyses/AnalysisLab/r26/performance/results/cross_device/02_inference_throughput_comparison.png)
- [03 training throughput comparison](Analyses/AnalysisLab/r26/performance/results/cross_device/03_training_throughput_comparison.png)
- [04 gpu memory comparison](Analyses/AnalysisLab/r26/performance/results/cross_device/04_gpu_memory_comparison.png)

---

## 🟡 R26NewPSFCheck

> [!IMPORTANT]
> **Open side track** · pending external GMF · **不是** active mainline
>
> 新 Whole-FOV PSF (2026-03-26 完成) 取代舊 empirical PSF，作為目前物理上較合理的標準

📄 Reports: [STATUS](Experiments/R26NewPSFCheck/reports/STATUS_20260326.md) · [PSF audit](Experiments/R26NewPSFCheck/psf_audit/PSF_FORMAL_AUDIT_20260326.md) · [Promote compare](Experiments/R26NewPSFCheck/formal_newpsf_candidate/reports/NEW_PSF_FORMAL_R26_COMPARE.md)

### 📊 測試重建影像（ablation 2×2）

舊 vs 新 checkpoint × 舊 vs 新 PSF 四象限對照。每張都是同一張 `VisionTop_20251029182653732.bmp` 輸入。

| | **Old PSF** | **New PSF** |
|---|---|---|
| **Old checkpoint (r26_sm035)** | [`old_ckpt_oldpsf/`](Experiments/R26NewPSFCheck/ablation_single_sample/reconstruct_progress_r26_sm035_best_tradeoff_in_input_20260324_233331/old_ckpt_oldpsf/VisionTop_20251029182653732.bmp) | [`old_ckpt_newpsf/`](Experiments/R26NewPSFCheck/ablation_single_sample/reconstruct_progress_r26_sm035_best_tradeoff_in_input_20260324_233331/old_ckpt_newpsf/VisionTop_20251029182653732.bmp) |
| **New checkpoint (新 PSF 重訓)** | [`new_ckpt_oldpsf/`](Experiments/R26NewPSFCheck/ablation_single_sample/reconstruct_progress_best_tradeoff_in_input_20260326_115148/new_ckpt_oldpsf/VisionTop_20251029182653732.bmp) | [`new_ckpt_newpsf/`](Experiments/R26NewPSFCheck/ablation_single_sample/reconstruct_progress_best_tradeoff_in_input_20260326_115148/new_ckpt_newpsf/VisionTop_20251029182653732.bmp) |

原始 input：[`ablation_single_sample/input/VisionTop_20251029182653732.bmp`](Experiments/R26NewPSFCheck/ablation_single_sample/input/VisionTop_20251029182653732.bmp)

### 📊 測試重建影像（pure PSF control，epoch 進度）

Same-recipe 對照：old recipe + new PSF → epoch 10/20/40 沒有重現先前「新 PSF 重訓崩壞」的模式。

- Old PSF：[epoch 10](Experiments/R26NewPSFCheck/pure_psf_control/reconstructions/old_psf/epoch_010.bmp) · [epoch 20](Experiments/R26NewPSFCheck/pure_psf_control/reconstructions/old_psf/epoch_020.bmp) · [epoch 40](Experiments/R26NewPSFCheck/pure_psf_control/reconstructions/old_psf/epoch_040.bmp)
- New PSF：[epoch 10](Experiments/R26NewPSFCheck/pure_psf_control/reconstructions/new_psf/epoch_010.bmp) · [epoch 20](Experiments/R26NewPSFCheck/pure_psf_control/reconstructions/new_psf/epoch_020.bmp) · [epoch 40](Experiments/R26NewPSFCheck/pure_psf_control/reconstructions/new_psf/epoch_040.bmp)

### 🔍 分析圖

![PSF old vs new investigation](Experiments/R26NewPSFCheck/reports/psf_old_vs_new_investigation_20260326.png)

- [PSF old vs new investigation](Experiments/R26NewPSFCheck/reports/psf_old_vs_new_investigation_20260326.png) · [ASCII 版](Experiments/R26NewPSFCheck/reports/psf_old_vs_new_investigation_ascii_20260326.png)
- [Old vs new recon investigation](Experiments/R26NewPSFCheck/reports/old_vs_new_recon_investigation_20260326.png) · [ASCII 版](Experiments/R26NewPSFCheck/reports/old_vs_new_recon_investigation_ascii_20260326.png)
- [Root cause centering — selector audit key epochs](Experiments/R26NewPSFCheck/root_cause_centering/figures/selector_audit_key_epochs_20260326.png)

---

## 🟡 R39-R45 Microscopy Generalization

> [!IMPORTANT]
> **Open research side track** · 目標是通用顯微結構忠實重建，不只是環形。環形外部 GMF 仍保留作正式量測守門，但 R39-R45 的主要價值是理解多形狀、多顯微特徵、邊界位置、已知位移忠實度與單一入口分族校正是否能推高。

### 近期結論

| Round | 主要用途 | 關鍵結論 |
|---|---|---|
| R39 | 多形狀泛化 | `r39_combo_strong_avg_a030` 外部 GMF 在替代容忍帶內：8px -6.94%、0.8px +6.42%、0.08px -15.97%。這是近期最接近正式替代討論的候選。 |
| R40 | 顯微特徵能力上限 | 顯微測試明顯改善，但最佳折衷外部 8px 退步 +22.80%，研究用。 |
| R41 | 知識蒸餾回拉 | 顯微能力仍強，但沒有找到同時守住本地環形與顯微能力的折衷點，研究用。 |
| R42 | 顯微邊界忠實度 | 邊界測試大幅勝過 COMBO，但後補外部 GMF 三尺度都退步；最佳外部候選 `r42_r41_best` 為 8px +24.63%、0.8px +94.33%、0.08px +98.87%。 |
| R43 | 堪用性盤點 | 確認沒有新候選可全面取代 COMBO；R39 a030 最可討論，R42 最適合顯微邊界研究與人工檢查。 |
| R44 | 通用邊界位移忠實度 | `r44_motion_from_r42_best` 把整體位移誤差降到 `0.3813 px`、格線位移誤差降到 `2.2457 px`；R44G 顯示大區塊/混合場景形狀能力分散在不同候選，沒有單一現成模型全面勝出，研究用。 |
| R45 | 分族邊界校正模組 | R45A 輸出端小校正守住位移但沒改善形狀；R45B 顯示逐張 oracle 有 `33.42%` 上限、固定分族 oracle 有 `12.30%`，但老師殘差不乾淨，研究負結果。 |

### R43 肉眼檢查圖

**顯微特徵總覽**

![](Experiments/R43_CandidateUsabilityAudit/results/visual_review/micro_feature_visual_sheet.png)

**邊界特徵總覽**

![](Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_feature_visual_sheet.png)

**邊界局部放大**

![](Experiments/R43_CandidateUsabilityAudit/results/visual_review/boundary_zoom_visual_sheet.png)

### R42 邊界代表圖

![](Experiments/R42_MicroscopyBoundaryFidelity/results/boundary_recon/r42_representative_boundary_sheet.png)

### R44 位移代表圖

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44_motion_r42_vs_r44_contact_sheet.png)

### R44C 探針代表圖

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44c_probe_r42_r44b_r44c_sheet.png)

### R44D 分族診斷熱圖

**邊界距離**

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/diagnostics/r44d_boundary_heatmap.png)

**位移誤差**

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/diagnostics/r44d_motion_heatmap.png)

### R44E 大區塊與混合場景探針代表圖

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44e_region_mixed_probe_sheet.png)

### R44F 錯誤解剖代表圖

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44f_error_dissection_sheet.png)

### R44G 邊界形狀熱圖

![](Experiments/R44_UniversalBoundaryMotionFidelity/results/visual_samples/r44g_boundary_shape_heatmap.png)

### R45 分族校正代表圖

![](Experiments/R45_FamilyBoundaryAdapter/results/visual_samples/r45_s08_vs_r44b_target_compare.png)

### R45B 老師診斷代表圖

![](Experiments/R45_FamilyBoundaryAdapter/results/visual_samples/r45b_teacher_diagnostics_sheet.png)

📄 Reports: [R39_RESULTS](Experiments/R39_ShapeGeneralization/reports/R39_RESULTS.md) · [R40_RESULTS](Experiments/R40_MicroscopyFeatureCoverage/reports/R40_RESULTS.md) · [R41_RESULTS](Experiments/R41_RingDistillation/reports/R41_RESULTS.md) · [R42_RESULTS](Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_RESULTS.md) · [R42_EXTERNAL_COMPARE](Experiments/R42_MicroscopyBoundaryFidelity/reports/R42_EXTERNAL_COMPARE.md) · [R43A_USABILITY_AUDIT](Experiments/R43_CandidateUsabilityAudit/reports/R43A_USABILITY_AUDIT.md) · [R44_RESULTS](Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44_RESULTS.md) · [R44E_TARGETED_PROBE](Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44E_TARGETED_PROBE.md) · [R44F_ERROR_DIAGNOSTIC](Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44F_ERROR_DIAGNOSTIC.md) · [R44G_BOUNDARY_SHAPE_METRICS](Experiments/R44_UniversalBoundaryMotionFidelity/reports/R44G_BOUNDARY_SHAPE_METRICS.md) · [R45_RESULTS](Experiments/R45_FamilyBoundaryAdapter/reports/R45_RESULTS.md) · [R45B_TEACHER_DIAGNOSTICS](Experiments/R45_FamilyBoundaryAdapter/reports/R45B_TEACHER_DIAGNOSTICS.md)

---

## 🔴 R33c

![🔴 R33c 跨尺度步距標準差](Experiments/R33ContrastFix/results/sequence_analysis/cross_dataset/08_cross_scale_step_std.png)

> [!CAUTION]
> **`R33ContrastFix / stat03`** · **Closed · falsified** · W_STAT 提高（0.30）反而讓 contrast 更差 — 視覺與指標同時退步


### 📊 測試重建影像（實際模型輸出 BMP）

三個尺度的重建樣本（每張圖取重建序列的中間一幀）：

**0.08 px 子像素**

![](Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp)

**0.8 px 主戰場**

![](Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp)

**8 px guard**

![](Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp)

📁 完整重建序列：

- [41 frames · 0.08 px 子像素](Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404/pitch0p01um_y_40_odd/)
- [61 frames · 0.8 px 主戰場](Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404/pitch0p1um_y_60_odd/)
- [101 frames · 8 px guard](Experiments/R33ContrastFix/results/stat03_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_222404/pitch1um_y_100_odd/)


### 📈 所有 24 張 720-angle 指標圖 + 其他方法論版本

**跨尺度總結：**

- [跨尺度步距標準差（08）](Experiments/R33ContrastFix/results/sequence_analysis/cross_dataset/08_cross_scale_step_std.png)
- [跨尺度 Residual 改善（09）](Experiments/R33ContrastFix/results/sequence_analysis/cross_dataset/09_cross_scale_residual_improvement.png)
- [跨尺度 K2 穩定性（10）](Experiments/R33ContrastFix/results/sequence_analysis/cross_dataset/10_cross_scale_k2_stability.png)

**Per-pitch 詳細指標（每 pitch 7 張）：**

- **0.08 px 子像素（`pitch0p01um_y_40`）**
  - [中心軌跡](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/01_center_trajectory.png)
  - [步距穩定性](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/02_step_stability.png)
  - [Residual std 時序](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p01um_y_40/07_center_offset_drift.png)
- **0.8 px 主戰場（`pitch0p1um_y_60`）**
  - [中心軌跡](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/01_center_trajectory.png)
  - [步距穩定性](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/02_step_stability.png)
  - [Residual std 時序](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R33ContrastFix/results/sequence_analysis/pitch0p1um_y_60/07_center_offset_drift.png)
- **8 px guard（`pitch1um_y_100`）**
  - [中心軌跡](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/01_center_trajectory.png)
  - [步距穩定性](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/02_step_stability.png)
  - [Residual std 時序](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R33ContrastFix/results/sequence_analysis/pitch1um_y_100/07_center_offset_drift.png)


📄 [R33ContrastFix/results](Experiments/R33ContrastFix/results/)

---

## 🔴 R38 seq-all-stages

![🔴 R38 seq-all-stages 跨尺度步距標準差](Experiments/R38SeqConsistency/results/sequence_analysis/cross_dataset/08_cross_scale_step_std.png)

> [!CAUTION]
> **`R38SeqConsistency / seq_only`** · **Closed · falsified** · R38v2 的前身：0.8px delta 太小被噪聲梯度干擾 — 三重修復（warmup + gate + 8px-only）→ R38v2 才成功


### 📊 測試重建影像（實際模型輸出 BMP）

三個尺度的重建樣本（每張圖取重建序列的中間一幀）：

**0.08 px 子像素**

![](Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842/pitch0p01um_y_40_odd/VisionTop_20251029193450691.bmp)

**0.8 px 主戰場**

![](Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842/pitch0p1um_y_60_odd/VisionTop_20251029185853613.bmp)

**8 px guard**

![](Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842/pitch1um_y_100_odd/VisionTop_20251029183552176.bmp)

📁 完整重建序列：

- [41 frames · 0.08 px 子像素](Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842/pitch0p01um_y_40_odd/)
- [61 frames · 0.8 px 主戰場](Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842/pitch0p1um_y_60_odd/)
- [101 frames · 8 px guard](Experiments/R38SeqConsistency/results/seq_only_recon/reconstruct_progress_best_tradeoff_in_Cropped_Output_20260406_122842/pitch1um_y_100_odd/)


### 📈 所有 24 張 720-angle 指標圖 + 其他方法論版本

**跨尺度總結：**

- [跨尺度步距標準差（08）](Experiments/R38SeqConsistency/results/sequence_analysis/cross_dataset/08_cross_scale_step_std.png)
- [跨尺度 Residual 改善（09）](Experiments/R38SeqConsistency/results/sequence_analysis/cross_dataset/09_cross_scale_residual_improvement.png)
- [跨尺度 K2 穩定性（10）](Experiments/R38SeqConsistency/results/sequence_analysis/cross_dataset/10_cross_scale_k2_stability.png)

**Per-pitch 詳細指標（每 pitch 7 張）：**

- **0.08 px 子像素（`pitch0p01um_y_40`）**
  - [中心軌跡](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/02_step_stability.png)
  - [Residual std 時序](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p01um_y_40/07_center_offset_drift.png)
- **0.8 px 主戰場（`pitch0p1um_y_60`）**
  - [中心軌跡](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/02_step_stability.png)
  - [Residual std 時序](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38SeqConsistency/results/sequence_analysis/pitch0p1um_y_60/07_center_offset_drift.png)
- **8 px guard（`pitch1um_y_100`）**
  - [中心軌跡](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/01_center_trajectory.png)
  - [步距穩定性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/02_step_stability.png)
  - [Residual std 時序](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/03_residual_std_timeseries.png)
  - [K2 振幅時序](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/04_k2_amplitude_timeseries.png)
  - [熱點持久性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/05_hotspot_persistence.png)
  - [邊緣寬度一致性](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/06_edge_width_consistency.png)
  - [中心偏移漂移](Experiments/R38SeqConsistency/results/sequence_analysis/pitch1um_y_100/07_center_offset_drift.png)


📄 [R38_RESULTS](Experiments/R38SeqConsistency/reports/R38_RESULTS.md)

---

## 🔴 R32

> [!CAUTION]
> **`r32_real_eq_finetune`** · **External FAIL · Closed sandbox**
>
> Internal winner 但 external 0.8px 惡化 **+97.7%** (`0.332`)
>
> 「internal pass ≠ external pass」的反例

📄 Reports: [External compare](Experiments/R32Sandbox/reports/ROUND32_EXTERNAL_COMPARE.md) · [Decision memo](Experiments/R32Sandbox/reports/ROUND32_DOMAIN_CAPACITY_DECISION_20260319_183614.md) · [Runtime status](Experiments/R32Sandbox/runtime/R32_STATUS.md)

**視覺輸出**：`R32Sandbox/artifacts/` 下有 process probe 的 loss curve 與 GMF proxy metrics PNG，但這些 artifacts 目錄**被 gitignore 排除**，不在 tracked 範圍。本地執行可看：`R32Sandbox/artifacts/training_progress_process_probe_r32_real_eq_finetune_*`。

---

## 🔴 R34 / R35 / R37

> [!CAUTION]
> 三輪嘗試恢復 R33 視覺銳度的 side attempt · **全部 falsified** · 只存在於 sandbox 分支 · **無 tracked 視覺輸出**

三輪的否定結論：

- **R34 freq-split**（`sandbox/r34`）：loss 層 Gaussian 分頻，lo/hi 梯度在 patch 上高度相關，無效
- **R35 alpha-boost 0.25**（`sandbox/r35`）：physics alpha 提升，均勻放大含噪 HF
- **R37 PSF 頻率依賴 reg**（`sandbox/r37`）：HF 低 reg 放大 Wiener 噪聲

這三輪只在各自 sandbox 分支，**未建立 `Experiments/` 目錄**，沒有產生可展示的 tracked 視覺輸出。

---

## 📚 Legacy visuals

> [!NOTE]
> R18/R22/R25 時代的 0.8px 主戰場對比表（2026-04-08 封存於 `docs/archive/legacy_visuals/`）。

- [`comparison_0p8px_case_01.png`](docs/archive/legacy_visuals/comparison_0p8px_case_01.png)
- [`comparison_0p8px_case_02.png`](docs/archive/legacy_visuals/comparison_0p8px_case_02.png)

這些是當時跨候選視覺比較，保留作為歷史引用錨點。完整 legacy 歷史與每一輪的敘事脈絡見 [`docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md`](docs/history/PROJECT_FULL_HISTORY_AND_STRATEGY_20260312.md)。

---

## Adding new entries

新完成一輪實驗後，請依以下格式在**對應分類區段**底下新增 `## <emoji> <Round>` section，全部使用純 markdown 語法（不要再引入 HTML）：

1. Section heading 前綴 emoji 對應輪次狀態（🟢 active / 🟡 open / 🔵 historical / 🔴 closed / 📚 legacy）
2. Hero 大圖：`![alt](path)` — 選本輪最具代表性的跨尺度總結圖
3. GitHub Alert block（`> [!TIP]` / `[!NOTE]` / `[!IMPORTANT]` / `[!CAUTION]`）一行摘要 + 關鍵數字
4. `### 📊 測試重建影像（實際模型輸出 BMP）` — 三個尺度各一張代表樣本，用 `**0.08 px 子像素**` 等粗體小標加 `![](path)`
5. `📁 完整重建序列：` + bullet 清單（每 pitch 一個目錄連結）
6. `### 📈 所有指標圖 + 方法論版本` — bullet 清單，使用中文標籤（例如「中心軌跡」、「步距穩定性」），每 pitch 一組 7 張
7. `📄 Reports:` 連結
8. 底部 `---` 分隔線
9. 在最上面 TOC 加一行

所有路徑用**相對於本檔目錄（`Experiments/`）的相對路徑**；跨到其他 tracked 目錄（`Analyses/AnalysisLab/`、`docs/archive/`）時用 `../` 前綴。

**這份文件不是 mandatory 更新項**（不列入 `CLAUDE.md` 的 5 項強制清單），但**強烈建議**在每輪有視覺輸出時更新——demo / 會議 / PR review 時會非常省時。


## R121：四組修正短測的負結果（2026-09-06）

八次有效短測完成；資料、位置與合併改動均未同時保住真實輪廓和細節，不採用、不進長訓練。

- [兩套 SEM 參考的配對輪廓結果](Experiments/R121_BoundaryAnchorFactorial/results/gallery_v2/paired_sem_effects.png)
- [細節與位移條件](Experiments/R121_BoundaryAnchorFactorial/results/gallery_v2/quality_guards.png)
- [固定真實影像對照](Experiments/R121_BoundaryAnchorFactorial/results/gallery_v2/fixed_real_examples.png)
- [完整結果與失敗紀錄](Experiments/R121_BoundaryAnchorFactorial/reports/R121_RESULTS.md)


## R109／R119：讀法差異與位置寬度耦合（2026-09-07）

固定模型與共同對齊，分開檢查輪廓、中點、最陡點的可靠性。沒有新訓練或升級。

- [讀法與有效覆蓋](Experiments/R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/readout_comparison.png)
- [位置路徑影響](Experiments/R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/position_path_effects.png)
- [位置也會壓窄邊緣](Experiments/R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/position_width_coupling.png)
- [完整比較報告](Experiments/R119_SequenceGeometryValidation/reports/R119_R109_READOUT_COMPARISON.md)
