# TTA 實驗：R26 加測試時增強（cross5）

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [基線 Round 26](<../round26/FILE_GUIDE.md>)

**一句話：** 一個支線實驗：在 R26 基線 `r26_sm035` 上，推論時加入 cross5 的測試時增強（TTA），看能不能改善外部 GMF。結果是 0.8 px 主戰場反而變差（步長標準差 0.1913→0.2140，退步 11.9%），0.08 px 改善 15.1%，8 px 幾乎不變。報告的結論是 TTA 無效，原本「等變性與銳利度衝突」的假說可能不對，應該先回頭檢查根因分析再繼續。

| | |
|---|---|
| 結果 | **未採用**（0.8 px 退步，不是升級方向） |
| 時間 | 2026-03-16（重建時間戳 `20260316_190408`） |
| 實驗條件 | A：環形影像，外部 GMF 三尺度 |
| 起點 | R26 的 `r26_sm035`（只在推論時加 TTA） |

## 外部 GMF 步長標準差

| 尺度 | R26 | R26 加 TTA | 變化 |
|---|---:|---:|---:|
| 8 px | 0.2010 | 0.2009 | 0.0% |
| 0.8 px | **0.1913** | 0.2140 | −11.9% |
| 0.08 px | 0.1803 | **0.1531** | +15.1% |

## 拿資料與重做

可重做程度：**historical-only**（子資料夾 `r26_tta_cross5/` 本身標為 partial）。GMF 分數與重建在 `r26_tta_cross5/gmf_results/raw/` 與 `r26_tta_cross5/reconstruct_progress_*`。

## 原始報告

[TTA 對基線比較](<r26_tta_cross5/reports/TTA_VS_BASELINE_CROSS5_COMPARISON.md>)、[子資料夾說明](<r26_tta_cross5/README.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本面保存紀錄](<../../../../docs/reproducibility/experiments/legacy__tta_experiment.md>)。
