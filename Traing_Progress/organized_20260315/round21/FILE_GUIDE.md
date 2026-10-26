# Round 21：soft_band 估計器加強步長訓練（死路）

[研究時間線](<../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一步 Branch E Follow-up](<../branch_e_followup/FILE_GUIDE.md>) · [接手的成對位移探針](<../pairwise_delta_probe/FILE_GUIDE.md>) · [Round 22](<../round22/FILE_GUIDE.md>)

**一句話：** 2026-03-15 驗證一個假說：固定用 `soft_band_refine` 當 0.8 px 的中尺度估計器，再加重 `SEQ_STEP_MAG_WEIGHT`，訓練能不能保住中心優勢、同時把步長拉回關卡。三個候選最後在稽核裡都回到第 0 輪基準（中心 0.1862、步長 0.5804），8 px 通過，唯一失敗的仍是 0.8 px 步長超過 0.45。假說被否定。

| | |
|---|---|
| 結果 | **未採用**（混合估計器加步長訓練拉不回中尺度步長） |
| 時間 | 2026-03-15 |
| 實驗條件 | A：環形影像，只跑 0.8 px（另以 8 px 當總體關卡）；沒有外部 GMF |
| 起點 | 沿用前面的保存點；三個候選都設定確定性、跳過最終階段 |

## 讀這些內容要知道的事

1. **三個候選**：`r21_midsoft_ctrlguard`、`r21_midsoft_stepup`、`r21_midsoft_stephard`，共同點是中尺度估計器固定為 `soft_band_refine`。
2. **失敗不代表估計器方向錯。** 報告的判讀是：中心優勢是真的，但單幀估計器加同型的訓練權重調整，修不好成對的步長；問題更像是成對位移的重建方式本身有系統性抖動或偏差。所以下一步不是 Round 21b，而是另外為成對位移找更穩的估計器，結果就是 [`pairmix_algblend`](<../pairwise_delta_probe/FILE_GUIDE.md>)。

## 拿資料與重做

可重做程度：**partial**。選定種子 `selected/current_round21_hybrid_seed.json` 不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡。

## 原始報告

[事後檢討](<ROUND21_POSTMORTEM.md>)、[混合估計器決策](<selected/reports/ROUND21_HYBRID_ESTIMATOR_DECISION_20260315_220621.md>)、[混合估計器摘要](<selected/reports/ROUND21_HYBRID_ESTIMATOR_SUMMARY_20260315_220410.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../docs/reproducibility/experiments/legacy__round21.md>)。
