# Round 19 ABSANCHOR：直接錨定絕對中心（否定性驗證）

[研究時間線](<../../../../docs/research/TIMELINE.md>) · [本批次說明](<../README.md>) · [早期輪次操作指南](<../../../../docs/operations/LEGACY_ROUNDS_OPERATIONS.md>) · [前一輪 Round 18](<../round18/FILE_GUIDE.md>) · [下一輪 Round 20](<../../organized_20260314/round20/FILE_GUIDE.md>)

**一句話：** 2026-03-13 晚間，想用新增的 `SEQ_ABS_CENTER_WEIGHT`（`abs_center`）直接對準絕對中心誤差，突破 Round 18 留下的 0.8 px 中心平台。四個候選選了 `r19_abs_anchor`：步長誤差依舊安全，但 0.8 px 中心誤差沒有突破（約 0.8560）。結論是這種注入方式沒有形成足夠有效的新梯度方向。沒通過內部關卡，也沒進外部 GMF。

| | |
|---|---|
| 結果 | **未採用**（否定性驗證：直接加這版絕對中心錨定解決不了主瓶頸） |
| 時間 | 2026-03-13 晚間 |
| 實驗條件 | A：環形影像三個尺度（0.08、0.8、8 px）的內部序列評分；沒有外部 GMF |
| 起點 | Round 18 的路線 |

## 結果

依批次 README，選中的 `r19_abs_anchor`：0.8 px 中心誤差約 0.8560、0.8 px 步長誤差約 0.2789、8 px 步長誤差約 0.0289。

| 候選 | 綜合分數 | 部署分數 |
|---|---:|---:|
| **r19_abs_anchor** | 348.672 | −110.006 |
| r19_abs_strong | 348.638 | −110.006 |
| r19_af_abs | 348.403 | −110.006 |
| r19_abs_only | 348.403 | −110.006 |

## 讀這些數字要知道的事

1. **四個候選的部署分數完全相同**（−110.006，都選 0.08 px 保存點），表示這次改動在部署層面幾乎沒有分出差別。
2. 部署分數 −110 比 Round 18 的 −112 略好，但關鍵的 0.8 px 中心誤差沒有突破，所以不升級。

## 拿資料與重做

可重做程度：**partial**，應當成歷史否定性輪次讀，不是可直接重跑的包。選定種子 `selected/current_absanchor_seed.json`（不在 git 樹上，在 Release `research-results-models-20261016` 的壓縮包裡）。

## 原始報告

[多尺度摘要](<selected/reports/ROUND19_ABSANCHOR_MULTISCALE_SUMMARY_20260313_190541.md>)、[檢查點稽核摘要](<selected/reports/ROUND19_ABSANCHOR_CHECKPOINT_AUDIT_SUMMARY_20260313_190541.md>)、[README](<README.md>)、[MANIFEST](<MANIFEST.md>)。保存紀錄見[本輪保存紀錄](<../../../../docs/reproducibility/experiments/legacy__round19.md>)。
