# Pairwise Delta Probe：單幀錨點加成對位移估計器（找到 pairmix_algblend）

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [起因 Round 21](<../round21/FILE_GUIDE.md>) · [正式驗證 Round 22](<../round22/FILE_GUIDE.md>)

**一句話：** 2026-03-15 晚間，Round 21 顯示問題出在成對位移的重建方式，所以改用分治：單幀的絕對位置照樣用 `soft_band_refine` 錨定，成對位移另外找更穩的估計器。三種成對混合方式裡，`pairmix_algblend` 把 0.8 px 的中心誤差（0.1845）與步長誤差（0.0657）一起壓進了校準後的關卡，8 px 也通過，判定 Round 22 可以立案。

| | |
|---|---|
| 結果 | **研究候選**（`pairmix_algblend` 通過內部探針，交給 Round 22 正式驗證） |
| 時間 | 2026-03-15 晚間 |
| 實驗條件 | A：環形影像 0.8 px 的估計器稽核，使用 Round 18 的選定保存點；8 px 為總體關卡；沒有外部 GMF |
| 起點 | 不訓練 |

## 結果

| 候選 | 中心誤差 | 步長誤差 | 中尺度通過 | 總體通過 | 最終 |
|---|---:|---:|---|---|---|
| **pairmix_algblend** | 0.1845 | **0.0657** | 是 | 是 | **通過** |
| pairmix_softcentroid | 0.1851 | 0.4147 | 是 | 是 | 通過 |
| pairmix_softblend | 0.1854 | 0.4756 | 否 | 是 | 否 |
| soft_band | 0.1862 | 0.5804 | 否 | 是 | 否 |
| edge_ctrl（控制組） | 6.9723 | 1.3555 | 否 | 是 | 否 |

## 拿資料與重做

可重做程度：**partial**，依賴舊的流程探針框架與外部工具。

## 原始報告

[成對位移探針摘要](<selected/reports/PAIRWISE_DELTA_PROBE_SUMMARY_20260315_224024.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本面保存紀錄](<../../../../docs/reproducibility/experiments/legacy__pairwise_delta_probe.md>)。
