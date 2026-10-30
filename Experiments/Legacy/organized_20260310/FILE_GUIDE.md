# 2026-03-10 批次：三尺度外部驗證與 uint16 微步修正（R7～R10）

[研究時間線](<../../../docs/research/TIMELINE.md>) · [早期輪次對照](<../../../docs/reproducibility/lineage/EARLY_ROUNDS.md>) · [前一個批次 3/09](<../organized_20260309/FILE_GUIDE.md>) · [下一個批次 3/11](<../organized_20260311/FILE_GUIDE.md>)

**一句話：** 第一次用三個尺度做外部 GMF：代表模型在 8 px 可用（標準差 0.245 px），0.8 px 平均很準但標準差太大（0.260 px，變異係數 32%），0.08 px 不穩定、甚至有負步長。資料面最可能的原因是微步影像在訓練前就失去訊號：stage 17、18 的清晰影像存成 8 bit BMP，卷積加雜訊後又量化回 8 bit。這一批把它們改成 uint16 TIFF，再做序列與微步的 R7～R10 探測。

| | |
|---|---|
| 結果 | **分析**（找出 8 bit 量化吃掉微步訊號，改成 uint16；R7～R10 都未採用） |
| 時間 | 2026-03-10 |
| 實驗條件 | A：NTU 三尺度外部 GMF（Pitch 1、0.1、0.01 µm）；程式資料：重建後的 uint16 微步與序列資料 |
| 起點 | 當時的代表模型 |

## 代表模型的三尺度外部 GMF

| 尺度 | 平均步長 | 標準差 | 變異係數 |
|---|---:|---:|---:|
| 8 px（1 µm） | 8.017 px | 0.245 px | 3.1% |
| 0.8 px（0.1 µm） | 0.800 px | 0.260 px | 32.5% |
| 0.08 px（0.01 µm） | 0.067 px | 0.149 px | 223% |

## 讀這些內容要知道的事

1. **uint16 修正的證據**：同一個種子重新生成 stage 17 的影像，8 bit 版只有 142 個灰階值、uint16 版有 2,404 個；把新版降回 8 bit，跟舊檔逐像素完全相同。
2. **R7～R10 的教訓**（見[早期輪次對照](<../../../docs/reproducibility/lineage/EARLY_ROUNDS.md>)）：內部步長零波動同時伴隨步長誤差，不能解讀成實際量測零誤差；R9 有兩種驗證來源（val_batch 與 seq_val），分數不能混排；R10 其實是 R9 長跑的第二、三步。
3. **大型內容已移到 H 槽**（2026-08-01）：完整 928 個檔、2.19 GiB 在 H 槽快照；D 槽保留精度修正報告與 38 份核心證據。恢復方式見 [ARCHIVE_POINTER](<ARCHIVE_POINTER.md>)。

## 原始報告

[微步資料精度修正](<reports/MICROSTEP_DATA_PRECISION_FIX_20260310.md>)、[代表模型三尺度摘要](<selected_evidence/representative_multiscale/reports/representative_multiscale_posy_step_summary.md>)、[uint16 微步探測](<selected_evidence/microstep_uint16_probe/reports/pitch0p01um_y_40_posy_step_stats.md>)、[精選證據說明](<selected_evidence/README.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本批次保存紀錄](<../../../docs/reproducibility/experiments/legacy__organized_20260310.md>)。
