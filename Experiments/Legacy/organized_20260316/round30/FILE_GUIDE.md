# Round 30：架構突破，r30_b1_dironly 成為正式基準

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 29](<../round29/FILE_GUIDE.md>) · [下一輪 Round 31](<../round31/FILE_GUIDE.md>) · [之後的 R32](<../../../R32Sandbox/FILE_GUIDE.md>)

**一句話：** R27～R29 證明只調步長權重已經到頂，2026-03-17～03-18 改架構，試三個 B1 系列候選。內部第一名是功能最完整的 `r30_b1a1a5_full`，但外部 GMF 的 0.8 px 贏家是只加方向約束的 `r30_b1_dironly`：步長標準差 0.1679，比 R26 的 0.1913 改善 0.023。依外部結果，`r30_b1_dironly` 正式升級為正式基準，一直用到 COMBO（4/8）。

| | |
|---|---|
| 結果 | **採用**（正式基準 `r30_b1_dironly`，直到 COMBO） |
| 時間 | 2026-03-17 訓練；03-18 決策與外部比較 |
| 實驗條件 | A：環形影像，內部 0.8 px 稽核；外部 GMF 三尺度 |
| 起點 | R26 時代的路線 |

## 外部 GMF 步長標準差

| 尺度 | R26 sm035 | **r30_b1_dironly** | r30_b1a1_dir_lblur | r30_b1a1a5_full |
|---|---:|---:|---:|---:|
| 8 px | 0.2010 | 0.2052 | 0.2042 | **0.1993** |
| 0.8 px | 0.1913 | **0.1679** | 0.1855 | 0.1843 |
| 0.08 px | 0.1803 | 0.1577 | **0.1414** | 0.1574 |

內部稽核：`r30_b1a1a5_full` 中心 0.3020、步長 0.0445（內部第一）；`r30_b1_dironly` 中心 0.0804、步長 0.0693。

## 讀這些數字要知道的事

1. **內部第一名不是外部贏家**，最後依外部 0.8 px 決定，這是 R22 教訓之後的標準做法。
2. 三個候選在 0.8 px 都比 R26 好；`b1a1a5_full` 在 8 px 最好，但正式決策以 0.8 px 主戰場優先。
3. 外部比較的 GMF 分數與重建影像保存在本資料夾的 `gmf_results/` 與 `reconstruct_progress_*`。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round30_arch_breakthrough_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[外部比較](<selected/reports/ROUND30_EXTERNAL_COMPARE.md>)、[架構突破決策](<selected/reports/ROUND30_ARCH_BREAKTHROUGH_DECISION_20260318_003739.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../../docs/reproducibility/experiments/legacy__round30.md>)。
